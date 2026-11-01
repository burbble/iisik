"""Regression scenarios for the review of labs 1, 2 and 4–7."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import json

import grpc
import pytest
from google.protobuf.wrappers_pb2 import StringValue
from sqlalchemy import select, func

from app.bootstrap import get_container
from app.gateway.facade import ApplicationFacade
from app.gateway.clients.factory import create_grpc_clients
from app.scripts.seed import (
    clear_and_seed,
    PRODUCT_A,
    PRODUCT_B,
    USER_ID,
    MANAGER_USER_ID,
    REPORT_ID,
    COST_CENTER_ID,
)
from app.shared.security import Actor
from app.shared.errors import AuthorizationError
from app.services.costing.database import SessionLocal as CostSession
from app.services.costing.models import CostCalculation, OverheadAllocation, OutboxEvent
from app.services.production.database import SessionLocal as ProdSession
from app.services.production.models import ProductionOrder, MaterialConsumption
from app.services.reporting.database import SessionLocal as ReportSession
from app.services.reporting.models import ReportExport
from app.transport.kafka import InMemoryEventPublisher, EventEnvelope
from app.transport.kafka.consumer import KafkaEventConsumer
from app.transport.kafka.outbox import OutboxDispatcher

PERIOD = date(2026, 9, 1)


def setup_function():
    clear_and_seed()
    get_container.cache_clear()


def actor(role="ANALYST", user=USER_ID):
    return Actor(user, "test@example.local", (role,), "test")


def facade():
    return ApplicationFacade(create_grpc_clients())


def test_registration_cannot_grant_analytics_access():
    from app.services.auth.service import AuthService
    from app.services.auth.sessions import InMemorySessionStore
    from app.services.auth.tokens import JWTManager

    auth = AuthService(
        InMemorySessionStore(), JWTManager("test-secret-that-is-long-enough-1234567890")
    )
    registered = auth.register("untrusted@example.local", "Password123!")
    logged = auth.login(registered.email, "Password123!")
    assert logged.actor.roles == ("PENDING",)
    with pytest.raises(AuthorizationError):
        facade().cost_breakdown(logged.actor, PRODUCT_A, PERIOD)


@pytest.mark.parametrize(
    "role,allowed,forbidden",
    [
        ("PRODUCTION_ACCOUNTANT", {"ERP", "MES"}, "FINANCE"),
        ("FINANCE_ACCOUNTANT", {"FINANCE"}, "ERP"),
    ],
)
def test_import_visibility_is_restricted_by_direction(role, allowed, forbidden):
    f = facade()
    assert all(r.source in allowed for r in f.import_runs(actor(role)))
    with pytest.raises(AuthorizationError):
        f.import_runs(actor(role), forbidden)


def test_empty_product_group_and_explicit_empty_set_match_no_results():
    f = facade()
    for products, groups in [
        (None, ["empty-group"]),
        ([], None),
        ([PRODUCT_A], ["empty-group"]),
    ]:
        args = (actor(), products, groups, PERIOD, date(2026, 9, 30))
        assert f.profitability(*args) == []
        assert f.profitability_summary(*args).count == 0
    assert (
        get_container().analytics.list_profitability([], PERIOD, date(2026, 9, 30))
        == []
    )


def test_foreign_report_is_rejected_before_creating_job():
    with ReportSession() as s:
        before = s.scalar(select(func.count()).select_from(ReportExport))
    with pytest.raises(AuthorizationError):
        get_container().reporting.create_export("CSV", MANAGER_USER_ID, REPORT_ID)
    with ReportSession() as s:
        assert s.scalar(select(func.count()).select_from(ReportExport)) == before


@pytest.mark.parametrize("format", ["CSV", "XLSX", "PDF"])
def test_export_builds_parseable_file_with_report_data(format):
    result = get_container().reporting.create_export(format, USER_ID, REPORT_ID)
    assert result.status == "READY" and result.error_message is None
    path = Path(result.file_ref)
    if format == "PDF":
        from pypdf import PdfReader

        assert "6400" in PdfReader(path).pages[0].extract_text()
    elif format == "XLSX":
        from openpyxl import load_workbook

        assert load_workbook(path).active.max_row == 3
    else:
        import csv

        with path.open(encoding="utf-8-sig") as stream:
            rows = list(csv.reader(stream))
        assert len(rows) == 3 and PRODUCT_A in rows[1][0] + rows[2][0]


def test_export_failure_is_recorded(monkeypatch):
    reporting = get_container().reporting
    monkeypatch.setattr(
        reporting,
        "_write_export",
        lambda *_: (_ for _ in ()).throw(OSError("disk full")),
    )
    result = reporting.create_export("CSV", USER_ID)
    assert (
        result.status == "FAILED"
        and result.file_ref is None
        and "disk full" in result.error_message
    )


def test_import_persists_facts_and_retry_does_not_duplicate(accounting_snapshots):
    service = get_container().production
    first = service.start_import("MES", date(2026, 10, 1))
    second = service.start_import("MES", date(2026, 10, 1))
    assert first.records_loaded == second.records_loaded == 1
    with ProdSession() as s:
        orders = list(
            s.scalars(
                select(ProductionOrder).where(
                    ProductionOrder.period == date(2026, 10, 1)
                )
            )
        )
        assert len(orders) == 1
        assert s.scalar(
            select(func.sum(MaterialConsumption.amount)).where(
                MaterialConsumption.order_id == orders[0].order_id
            )
        ) == Decimal("185")


def test_failed_record_is_rolled_back_and_retry_loads_fixed_snapshot(
    accounting_snapshots,
):
    service = get_container().production
    path = accounting_snapshots / "MES" / "2026-10-01.json"
    original = json.loads(path.read_text())
    broken = json.loads(path.read_text())
    broken[0]["materials"][0]["material_code"] = "UNKNOWN"
    path.write_text(json.dumps(broken))
    failed = service.start_import("MES", date(2026, 10, 1))
    assert (
        failed.status == "FAILED"
        and failed.records_loaded == 0
        and failed.records_failed == 1
        and failed.errors
    )
    with ProdSession() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(ProductionOrder)
                .where(ProductionOrder.period == date(2026, 10, 1))
            )
            == 0
        )
    path.write_text(json.dumps(original))
    retried = service.retry_import(failed.id)
    assert (
        retried.status == "COMPLETED"
        and retried.records_loaded == 1
        and not retried.errors
    )


def test_missing_source_publishes_failure_instead_of_success(grpc_runtime):
    result = create_grpc_clients().production.start_import("MES", date(2030, 1, 1))
    assert result.status == "FAILED" and result.errors
    event = grpc_runtime["production"].events[-1]
    assert (
        event.eventType == "ImportFailed" and event.payload["importRunId"] == result.id
    )


def test_financial_import_writes_sales_and_net_center_overhead():
    service = get_container().financial
    result = service.start_import("FINANCE", date(2026, 10, 1))
    assert result.status == "COMPLETED" and result.records_loaded == 2
    assert service.get_sales_data(PRODUCT_A, date(2026, 10, 1)).revenue == Decimal(
        "640"
    )
    centers, correction = service.get_overhead_breakdown(date(2026, 10, 1))
    assert centers[COST_CENTER_ID] == Decimal("20") and correction == 0


def test_overhead_details_and_versions_are_saved_atomically():
    rows = create_grpc_clients().costing.calculate_costs_remote(
        PERIOD, [PRODUCT_A, PRODUCT_B], "LABOR_HOURS"
    )
    with CostSession() as s:
        for dto in rows:
            row = s.get(CostCalculation, dto.calculation_id)
            assert set(row.source_versions) == {
                "production",
                "master",
                "financial",
                "plan",
            }
            allocations = list(
                s.scalars(
                    select(OverheadAllocation).where(
                        OverheadAllocation.calculation_id == row.calculation_id
                    )
                )
            )
            assert (
                allocations and sum(a.amount for a in allocations) == row.overhead_cost
            )
            assert all(
                a.production_order_id
                and a.cost_center_id == COST_CENTER_ID
                and a.basis_value > 0
                for a in allocations
            )
    assert rows[0].planned_unit_cost == Decimal("38")
    assert rows[0].unit_cost_deviation == rows[0].unit_cost - Decimal("38")


def test_raw_grpc_rejects_missing_or_wrong_service_role():
    from app.transport.grpc.security import rpc_metadata

    with grpc.insecure_channel("127.0.0.1:50054") as channel:
        rpc = channel.unary_unary(
            "/profitability.gateway.CostingGateway/CalculateCost",
            request_serializer=StringValue.SerializeToString,
            response_deserializer=StringValue.FromString,
        )
        request = StringValue(
            value=json.dumps(
                {
                    "period": str(PERIOD),
                    "product_ids": [PRODUCT_A],
                    "allocation_base": "VOLUME",
                }
            )
        )
        with pytest.raises(grpc.RpcError) as error:
            rpc(request, timeout=2)
        assert error.value.code() == grpc.StatusCode.UNAUTHENTICATED
        with pytest.raises(grpc.RpcError) as error:
            rpc(request, timeout=2, metadata=rpc_metadata("costing"))
        assert error.value.code() == grpc.StatusCode.PERMISSION_DENIED


def test_mutation_transport_does_not_retry_lost_response(monkeypatch):
    from app.transport.grpc.bridge import JsonGrpcClient

    client = JsonGrpcClient("127.0.0.1:1", "test", backoff_seconds=0)
    attempts = []

    class Timeout(grpc.RpcError):
        def code(self):
            return grpc.StatusCode.DEADLINE_EXCEEDED

        def details(self):
            return "reply lost after commit"

    def rpc(*args, **kwargs):
        attempts.append(1)
        raise Timeout()

    monkeypatch.setattr(
        client, "channel", SimpleNamespace(unary_unary=lambda *a, **k: rpc)
    )
    with pytest.raises(RuntimeError):
        client.call("CalculateCost", {})
    assert len(attempts) == 1


def test_outbox_survives_broker_failure_and_recovers():
    from app.services.costing.service import ProductCostInput

    service = get_container().costing
    service.calculate_costs(
        PERIOD,
        [ProductCostInput(PRODUCT_A, Decimal(1), Decimal(1), Decimal(1), Decimal(1))],
        Decimal(0),
        "VOLUME",
    )

    class Unavailable:
        def publish(self, event):
            raise OSError("Kafka unavailable")

    dispatcher = OutboxDispatcher(Unavailable())
    dispatcher.flush()
    with CostSession() as s:
        row = s.scalar(select(OutboxEvent))
        assert row.published_at is None and row.last_error
        assert s.scalar(select(func.count()).select_from(CostCalculation)) == 3
    publisher = InMemoryEventPublisher()
    dispatcher.publisher = publisher
    dispatcher.flush()
    dispatcher.flush()
    assert len(publisher.events) == 1
    with CostSession() as s:
        assert s.scalar(select(OutboxEvent)).published_at is not None


def test_consumer_cannot_ack_when_dlq_fails():
    class Broken:
        def publish(self, event):
            raise OSError("DLQ unavailable")

    consumer = KafkaEventConsumer(
        "test",
        {"Fail": lambda _: (_ for _ in ()).throw(ValueError("bad"))},
        max_attempts=1,
    )
    consumer._dead_letter = Broken()
    assert consumer._process(EventEnvelope.create("Fail", "test", {})) is False


def test_malformed_record_is_retried_until_dlq_ack_then_next_record(monkeypatch):
    import kafka

    commits = []
    attempts = []
    records = [
        SimpleNamespace(value=b"broken-json", topic="events", partition=0, offset=0),
        SimpleNamespace(
            value=EventEnvelope.create("Ignored", "test", {}).to_bytes(),
            topic="events",
            partition=0,
            offset=1,
        ),
    ]

    class FakeConsumer:
        def __init__(self, *a, **kw):
            assert kw.get("value_deserializer") is None

        def __iter__(self):
            return iter(records)

        def commit(self, offsets):
            commits.extend(x.offset for x in offsets.values())

        def close(self):
            pass

    monkeypatch.setattr(kafka, "KafkaConsumer", FakeConsumer)
    consumer = KafkaEventConsumer("test", {}, backoff_seconds=0)

    def dlq(event, error):
        assert commits == []
        attempts.append(event)
        return len(attempts) > 1

    monkeypatch.setattr(consumer, "_send_to_dead_letter", dlq)
    consumer.run_forever()
    assert len(attempts) == 2 and commits == [1, 2]


def test_event_chain_uses_requested_cost_version_and_correlation(monkeypatch):
    import app.transport.grpc.server as servers

    handlers = {}

    class Consumer:
        def __init__(self, group, callbacks):
            handlers[group] = callbacks

        def start_in_thread(self, *a):
            pass

    monkeypatch.setattr(servers, "KafkaEventConsumer", Consumer)
    monkeypatch.setattr(servers, "LAB7_EVENT_BACKEND", "kafka")
    publisher = InMemoryEventPublisher()
    server, _ = servers.build_server("analytics", port=0, publisher=publisher)
    create_grpc_clients().costing.calculate_costs_remote(PERIOD, [PRODUCT_A], "VOLUME")
    event = EventEnvelope.create(
        "CostCalculationCompleted",
        "test",
        {"productId": PRODUCT_A, "period": str(PERIOD), "version": 1},
        correlation_id="scenario-123",
    )
    callbacks = next(iter(handlers.values()))
    callbacks["CostCalculationCompleted"](event)
    assert publisher.events[-1].correlationId == "scenario-123"
    # Version 1 unit cost is 40; version 2 differs. Analytics must use the event snapshot.
    assert Decimal(publisher.events[-1].payload["costOfSales"]) == Decimal("3200")
    assert {
        "ImportFailed",
        "ProductionDataImported",
        "FinancialDataImported",
        "MasterDataChanged",
    } <= callbacks.keys()
    callbacks["MasterDataChanged"](
        EventEnvelope.create("MasterDataChanged", "test", {})
    )
    assert get_container().analytics.list_profitability(None, PERIOD, PERIOD) == []
    server.stop(0)


def test_reporting_projection_is_used_by_graphql_scenario():
    # Alter only the reporting projection; GraphQL facade must see that projection.
    from app.services.reporting.models import ProfitabilityReadModel

    with ReportSession.begin() as s:
        row = s.scalar(
            select(ProfitabilityReadModel).where(
                ProfitabilityReadModel.product_id == PRODUCT_A
            )
        )
        row.revenue = Decimal("123")
    result = facade().profitability(actor(), [PRODUCT_A], None, PERIOD, PERIOD)
    assert result[0].revenue == Decimal("123")


def test_cost_center_filter_and_overhead_details_are_available_in_graphql():
    from app.gateway.schema import schema

    query = """query {
      profitability(filter: {costCenterIds: ["missing"], periodFrom: "2026-09-01", periodTo: "2026-09-30"}) { productId }
      overheadAllocations(productId:"22222222-2222-2222-2222-222222222222",period:"2026-09-01") { costCenterId basisValue amount }
    }"""
    result = schema.execute_sync(
        query, context_value={"facade": facade(), "actor": actor()}
    )
    assert not result.errors
    assert result.data["profitability"] == []
    assert result.data["overheadAllocations"][0]["amount"] == "800.00"


def test_master_data_event_invalidates_calculations_and_cache(monkeypatch):
    import app.transport.grpc.server as servers
    from app.shared.cache import cache_set, cache_get

    callbacks = {}

    class Consumer:
        def __init__(self, group, handlers):
            callbacks.update(handlers)

        def start_in_thread(self, *args):
            pass

    monkeypatch.setattr(servers, "KafkaEventConsumer", Consumer)
    monkeypatch.setattr(servers, "LAB7_EVENT_BACKEND", "kafka")
    server, _ = servers.build_server(
        "costing", port=0, publisher=InMemoryEventPublisher()
    )
    cache_set("costing-context:test", {"version": "old"}, 300)
    callbacks["MasterDataChanged"](
        EventEnvelope.create("MasterDataChanged", "test", {})
    )
    assert cache_get("costing-context:test") is None
    with CostSession() as session:
        assert all(
            row.status == "INVALIDATED"
            for row in session.scalars(select(CostCalculation))
        )
    server.stop(0)


def test_late_old_profitability_event_cannot_replace_newer_projection():
    from datetime import datetime, timedelta

    reporting = get_container().reporting
    now = datetime.now()
    reporting.update_profitability_projection(
        "new-result",
        PRODUCT_A,
        "group",
        PERIOD,
        Decimal(100),
        Decimal(50),
        Decimal(50),
        Decimal(50),
        now,
        cost_version=3,
    )
    reporting.update_profitability_projection(
        "old-result",
        PRODUCT_A,
        "group",
        PERIOD,
        Decimal(10),
        Decimal(8),
        Decimal(2),
        Decimal(20),
        now + timedelta(seconds=1),
        cost_version=2,
    )
    rows = reporting.list_profitability([PRODUCT_A], PERIOD, PERIOD)
    assert rows[0].revenue == Decimal(100)
