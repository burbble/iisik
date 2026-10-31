"""File adapter for accounting-system JSON snapshots; no fabricated successful imports."""

import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import delete
from app.config import DATA_DIR, MASTER_DATA_GRPC_TARGET
from app.shared.errors import ValidationError


def number(value, *, signed=False):
    result = Decimal(str(value))
    if not result.is_finite() or (not signed and result < 0):
        raise ValidationError("Invalid numeric value")
    return result


def identity(source, kind, key):
    return str(uuid5(NAMESPACE_URL, f"{source}:{kind}:{key}"))


def lookup(source, kind, code):
    from app.transport.grpc.typed import MasterDataStub
    from app.transport.grpc.security import rpc_metadata
    from app.contracts import profitability_pb as pb
    from app.shared.resilience import call_grpc_with_retry
    import grpc

    with grpc.insecure_channel(MASTER_DATA_GRPC_TARGET) as channel:
        result = call_grpc_with_retry(
            MasterDataStub(channel).LookupExternalMapping,
            pb.LookupExternalMappingRequest(
                source_system=source, entity_type=kind, external_code=code
            ),
            operation="MasterDataService.LookupExternalMapping",
            target=MASTER_DATA_GRPC_TARGET,
            metadata=rpc_metadata(),
        )
        return result.internal_id


def load_snapshot(source, period):
    path = (
        Path(os.environ.get("IMPORT_DATA_DIR", DATA_DIR / "imports"))
        / source
        / f"{period.isoformat()}.json"
    )
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValidationError("Import snapshot must contain a nonempty list of records")
    return records


def execute_import(service, run, domain, *, records=None, resolver=lookup):
    from importlib import import_module

    models = import_module(f"app.services.{domain}.models")
    factory = import_module(f"app.services.{domain}.database").SessionLocal
    errors, loaded = [], 0
    try:
        records = load_snapshot(run.source, run.period) if records is None else records
        if not isinstance(records, list) or not records:
            raise ValidationError(
                "Import snapshot must contain a nonempty list of records"
            )
    except Exception as exc:
        errors.append((None, type(exc).__name__, str(exc), None))
        records = []
    for index, record in enumerate(records):
        try:
            with factory.begin() as session:
                if domain == "production":
                    key = str(record["external_id"])
                    order_id = identity(run.source, "order", key)
                    qty = number(record["quantity"])
                    if qty <= 0:
                        raise ValidationError("Produced quantity must be positive")
                    session.merge(
                        models.ProductionOrder(
                            order_id=order_id,
                            external_id=f"{run.source}:{key}",
                            product_id=resolver(
                                run.source, "PRODUCT", record["product_code"]
                            ),
                            period=run.period,
                            quantity=qty,
                            status="COMPLETED",
                        )
                    )
                    session.flush()
                    session.execute(
                        delete(models.MaterialConsumption).where(
                            models.MaterialConsumption.order_id == order_id
                        )
                    )
                    session.execute(
                        delete(models.LaborEntry).where(
                            models.LaborEntry.order_id == order_id
                        )
                    )
                    for i, item in enumerate(record.get("materials", [])):
                        session.add(
                            models.MaterialConsumption(
                                consumption_id=identity(
                                    run.source, "material", f"{key}:{i}"
                                ),
                                order_id=order_id,
                                material_id=resolver(
                                    run.source, "MATERIAL", item["material_code"]
                                ),
                                quantity=number(item["quantity"]),
                                amount=number(item["amount"]),
                                posted_at=datetime.now(),
                            )
                        )
                    for i, item in enumerate(record.get("labor", [])):
                        session.add(
                            models.LaborEntry(
                                labor_entry_id=identity(
                                    run.source, "labor", f"{key}:{i}"
                                ),
                                order_id=order_id,
                                cost_center_id=resolver(
                                    run.source, "COST_CENTER", item["cost_center_code"]
                                ),
                                hours=number(item["hours"]),
                                amount=number(item["amount"]),
                            )
                        )
                elif record["type"] in {"OVERHEAD", "CORRECTION"}:
                    key = str(record["external_id"])
                    session.merge(
                        models.FinancialEntry(
                            entry_id=identity(run.source, "entry", key),
                            external_id=f"{run.source}:{key}",
                            period=run.period,
                            cost_center_id=resolver(
                                run.source, "COST_CENTER", record["cost_center_code"]
                            ),
                            entry_type=record["type"],
                            amount=number(
                                record["amount"], signed=record["type"] == "CORRECTION"
                            ),
                            currency=record["currency"],
                            posted_at=datetime.now(),
                        )
                    )
                elif record["type"] == "SALE":
                    key = str(record["external_id"])
                    doc_id = identity(run.source, "sale", key)
                    document_date = date.fromisoformat(record["document_date"])
                    if (document_date.year, document_date.month) != (
                        run.period.year,
                        run.period.month,
                    ):
                        raise ValidationError(
                            "Sales document date is outside import period"
                        )
                    session.merge(
                        models.SalesDocument(
                            sales_document_id=doc_id,
                            external_id=f"{run.source}:{key}",
                            document_date=document_date,
                            currency=record["currency"],
                            customer_ref=record.get("customer_ref"),
                        )
                    )
                    session.flush()
                    session.execute(
                        delete(models.SalesItem).where(
                            models.SalesItem.sales_document_id == doc_id
                        )
                    )
                    for i, item in enumerate(record["items"]):
                        revenue, discount = (
                            number(item["revenue"]),
                            number(item.get("discount", 0)),
                        )
                        if discount > revenue:
                            raise ValidationError("Discount exceeds revenue")
                        session.add(
                            models.SalesItem(
                                sales_item_id=identity(
                                    run.source, "sale_item", f"{key}:{i}"
                                ),
                                sales_document_id=doc_id,
                                product_id=resolver(
                                    run.source, "PRODUCT", item["product_code"]
                                ),
                                quantity=number(item["quantity"]),
                                revenue=revenue,
                                discount=discount,
                            )
                        )
                else:
                    raise ValidationError("Unsupported financial record type")
            loaded += 1
        except Exception as exc:
            errors.append(
                (
                    str(record.get("external_id", index))
                    if isinstance(record, dict)
                    else str(index),
                    type(exc).__name__,
                    str(exc),
                    record,
                )
            )
    with factory.begin() as session:
        row = session.get(models.ImportRun, run.id)
        row.status = "FAILED" if errors else "COMPLETED"
        row.records_loaded = loaded
        row.records_failed = len(errors)
        row.finished_at = datetime.now()
        for key, code, message, payload in errors:
            session.add(
                models.ImportError(
                    error_id=str(uuid4()),
                    import_run_id=run.id,
                    record_key=key,
                    error_code=code,
                    message=message,
                    raw_payload=payload,
                )
            )
        from app.transport.kafka.events import EventEnvelope

        event = EventEnvelope.create(
            "ImportFailed"
            if errors
            else "ProductionDataImported"
            if domain == "production"
            else "FinancialDataImported",
            f"{domain}-integration-service",
            {
                "importRunId": run.id,
                "sourceSystem": run.source,
                "period": run.period.isoformat(),
                "recordsLoaded": loaded,
                "errorCount": len(errors),
                "primaryErrorCode": errors[0][1] if errors else None,
                "dataVersion": f"{run.id}:{row.finished_at.isoformat()}",
            },
        )
        if domain == "production":
            event.payload["productionOrderIds"] = (
                service.repository.list_period_order_ids(run.period)
            )
        session.add(
            models.OutboxEvent(
                event_id=event.eventId,
                envelope=event.to_dict(),
                published_at=None,
                last_error=None,
            )
        )
    return service.get_import_run(run.id)
