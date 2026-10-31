from __future__ import annotations

import argparse
import os
from concurrent import futures
from datetime import date, datetime
from decimal import Decimal

import grpc

from app.bootstrap import init_databases
from app.config import (
    MASTER_DATA_GRPC_TARGET,
    PRODUCTION_GRPC_TARGET,
    FINANCIAL_GRPC_TARGET,
    COSTING_GRPC_TARGET,
    ANALYTICS_GRPC_TARGET,
    REPORTING_GRPC_TARGET,
    KAFKA_GROUP_PREFIX,
    LAB7_EVENT_BACKEND,
)
from app.contracts import profitability_pb as pb
from app.services.master_data.service import MasterDataService
from app.services.production.service import ProductionIntegrationService
from app.services.financial.service import FinancialIntegrationService
from app.services.costing.service import CostingService, ProductCostInput
from app.services.analytics.service import (
    ProfitabilityAnalyticsService,
    ProfitabilityCalculationInput,
)
from app.services.reporting.service import ReportingService
from app.shared.errors import NotFoundError
from app.shared.cache import cache_delete_prefix
from app.shared.logging_config import get_logger
from app.transport.grpc.bridge import JsonGrpcClient, add_json_service
from app.transport.grpc.domain_clients import (
    MasterDataDomainClient,
    ProductionDomainClient,
    FinancialDomainClient,
    CostingDomainClient,
)
from app.transport.grpc.typed import (
    add_master_data_handler,
    add_production_handler,
    add_financial_handler,
    add_costing_handler,
    add_profitability_handler,
)
from app.transport.kafka import (
    EventEnvelope,
    InMemoryEventPublisher,
    KafkaEventConsumer,
    KafkaEventPublisher,
)

logger = get_logger("transport.grpc.server")


def _publisher():
    if LAB7_EVENT_BACKEND.lower() == "memory":
        return InMemoryEventPublisher()
    return KafkaEventPublisher()


def _port_from_target(target: str) -> int:
    return int(target.rsplit(":", 1)[1])


def _abort_not_found(context, message: str):
    context.abort(grpc.StatusCode.NOT_FOUND, message)


def _master_server(server, publisher):
    service = MasterDataService()

    def costing_context(request, context):
        period = date.fromisoformat(request.period)
        product = service.get_product(request.product_id)
        if product is None:
            _abort_not_found(context, "Product was not found")
        materials = service.repository.get_product_materials(request.product_id, period)
        response = pb.GetCostingContextResponse(
            product_id=request.product_id,
            allocation_base=service.repository.get_default_allocation_base(),
            data_version=service.repository.data_version(request.product_id, period),
        )
        for row in materials:
            response.materials.add(
                material_id=row.material_id, standard_qty=str(row.standard_qty)
            )
        return response

    def typed_mapping(request, context):
        row = service.repository.lookup_mapping(
            request.source_system, request.entity_type, request.external_code
        )
        if row is None:
            _abort_not_found(context, "External code mapping was not found")
        return pb.LookupExternalMappingResponse(
            internal_id=row.internal_id, mapping_version=row.updated_at.isoformat()
        )

    add_master_data_handler(server, costing_context, typed_mapping)

    def list_products(p):
        return service.list_products(
            group_id=p.get("group_id"),
            active=p.get("active"),
            search=p.get("search"),
            sort_by=p.get("sort_by", "CODE"),
            sort_direction=p.get("sort_direction", "ASC"),
        )

    def get_product(p):
        return service.get_product(p["product_id"])

    def resolve_mapping(p):
        row = service.resolve_external_mapping(
            p["source_system"], p["entity_type"], p["external_code"], p["internal_id"]
        )
        publisher.publish(
            EventEnvelope.create(
                "MasterDataChanged",
                "master-data-service",
                {
                    "entityType": row.entity_type,
                    "entityId": row.internal_id,
                    "changeType": "UPDATED",
                    "mappingVersion": 1,
                },
            )
        )
        return row

    def get_plan(p):
        return service.repository.get_plan(
            p["product_id"], date.fromisoformat(p["period"])
        )

    def lookup_mapping(p):
        row = service.repository.lookup_mapping(
            p["source_system"], p["entity_type"], p["external_code"]
        )
        if row is None:
            raise NotFoundError("External code mapping was not found")
        return {
            "internal_id": row.internal_id,
            "mapping_version": row.updated_at.isoformat(),
        }

    add_json_service(
        server,
        "profitability.gateway.MasterDataGateway",
        {
            "ListProducts": list_products,
            "GetProduct": get_product,
            "ResolveExternalMapping": resolve_mapping,
            "LookupExternalMapping": lookup_mapping,
            "GetPlannedCost": get_plan,
        },
    )


def _production_server(server, publisher):
    service = ProductionIntegrationService()

    def get_cost_data(request, context):
        period = date.fromisoformat(request.period)
        try:
            row = service.get_cost_data(request.product_id, period)
        except NotFoundError:
            _abort_not_found(context, "No production data for product and period")
        response = pb.GetProductionCostDataResponse(
            produced_qty=str(row.produced_qty), material_cost=str(row.material_cost),
            labor_cost=str(row.labor_cost), labor_hours=str(row.labor_hours),
            data_version=f"prod-{period.isoformat()}-v1",
        )
        response.production_order_ids.extend(service.get_production_order_ids(request.product_id, period))
        return response

    add_production_handler(server, get_cost_data)

    def list_runs(p):
        return service.list_import_runs(
            source=p.get("source"), period=date.fromisoformat(p["period"]) if p.get("period") else None
        )

    def get_run(p):
        return service.get_import_run(p["run_id"])

    def _finish_and_event(run):
        completed = service.complete_import(run.id, records_loaded=0)
        publisher.publish(EventEnvelope.create(
            "ProductionDataImported", "production-integration-service",
            {
                "importRunId": completed.id,
                "period": completed.period.isoformat(),
                "sourceSystem": completed.source,
                "recordsLoaded": completed.records_loaded,
                "productionOrderIds": [],
                "dataVersion": f"prod-{completed.period.isoformat()}-v1",
            },
        ))
        return completed

    def start_import(p):
        try:
            return _finish_and_event(service.start_import(p["source"], date.fromisoformat(p["period"])))
        except Exception as exc:
            publisher.publish(EventEnvelope.create(
                "ImportFailed", "production-integration-service",
                {"importRunId": "", "sourceSystem": p.get("source", ""), "period": p.get("period", ""),
                 "errorCount": 1, "primaryErrorCode": type(exc).__name__},
            ))
            raise

    def retry_import(p):
        return _finish_and_event(service.retry_import(p["run_id"]))

    add_json_service(server, "profitability.gateway.ProductionGateway", {
        "ListImportRuns": list_runs,
        "GetImportRun": get_run,
        "StartImport": start_import,
        "RetryImport": retry_import,
    })


def _financial_server(server, publisher):
    service = FinancialIntegrationService()

    def overhead(request, context):
        period = date.fromisoformat(request.period)
        items, correction = service.get_overhead_breakdown(period, list(request.cost_center_ids))
        response = pb.GetOverheadDataResponse(
            correction_amount=str(correction), data_version=f"fin-{period.isoformat()}-v1"
        )
        for center_id, amount in items.items():
            response.items.add(cost_center_id=center_id, amount=str(amount))
        return response

    def sales(request, context):
        period = date.fromisoformat(request.period)
        try:
            row = service.get_sales_data(request.product_id, period)
        except NotFoundError:
            _abort_not_found(context, "No sales data for product and period")
        return pb.GetSalesDataResponse(
            sold_qty=str(row.quantity), revenue=str(row.revenue),
            currency=service.get_sales_currency(request.product_id, period),
            data_version=f"fin-{period.isoformat()}-v1",
        )

    add_financial_handler(server, overhead, sales)

    def list_runs(p):
        return service.list_import_runs(
            source=p.get("source"), period=date.fromisoformat(p["period"]) if p.get("period") else None
        )

    def get_run(p):
        return service.get_import_run(p["run_id"])

    def _finish_and_event(run):
        completed = service.complete_import(run.id, records_loaded=0)
        publisher.publish(EventEnvelope.create(
            "FinancialDataImported", "financial-integration-service",
            {
                "importRunId": completed.id,
                "period": completed.period.isoformat(),
                "sourceSystem": completed.source,
                "recordsLoaded": completed.records_loaded,
                "dataVersion": f"fin-{completed.period.isoformat()}-v1",
            },
        ))
        return completed

    def start_import(p):
        try:
            return _finish_and_event(service.start_import(p["source"], date.fromisoformat(p["period"])))
        except Exception as exc:
            publisher.publish(EventEnvelope.create(
                "ImportFailed", "financial-integration-service",
                {"importRunId": "", "sourceSystem": p.get("source", ""), "period": p.get("period", ""),
                 "errorCount": 1, "primaryErrorCode": type(exc).__name__},
            ))
            raise

    def retry_import(p):
        return _finish_and_event(service.retry_import(p["run_id"]))

    add_json_service(server, "profitability.gateway.FinancialGateway", {
        "ListImportRuns": list_runs,
        "GetImportRun": get_run,
        "StartImport": start_import,
        "RetryImport": retry_import,
    })


def _costing_server(server, publisher):
    service = CostingService()
    master = MasterDataDomainClient()
    production = ProductionDomainClient()
    financial = FinancialDomainClient()

    def approved(request, context):
        row = service.get_cost_breakdown(
            request.product_id, date.fromisoformat(request.period), request.version or None
        )
        if row is None:
            _abort_not_found(context, "Cost calculation was not found")
        return pb.GetApprovedCostCalculationResponse(
            calculation_id=row.calculation_id, version=row.version, unit_cost=str(row.unit_cost),
            total_cost=str(row.total_cost), produced_qty=str(row.produced_qty), status="COMPLETED",
        )

    add_costing_handler(server, approved)

    def get_breakdown(p):
        return service.get_cost_breakdown(
            p["product_id"], date.fromisoformat(p["period"]), p.get("version")
        )

    def calculate(p):
        period = date.fromisoformat(p["period"])
        product_ids = list(p["product_ids"])
        allocation_base = p.get("allocation_base") or "DIRECT_COST"
        items = []
        for product_id in product_ids:
            master.get_costing_context(product_id, period)  # validation + real gRPC hop
            prod = production.get_cost_data(product_id, period)
            items.append(ProductCostInput(
                product_id=product_id,
                produced_qty=prod.produced_qty,
                material_cost=prod.material_cost,
                labor_cost=prod.labor_cost,
                labor_hours=prod.labor_hours,
            ))
        overhead = financial.get_overhead(period)
        rows = service.calculate_costs(period, items, overhead.total_amount, allocation_base)
        correlation = None
        for row in rows:
            event = EventEnvelope.create(
                "CostCalculationCompleted", "costing-service",
                {
                    "calculationId": row.calculation_id,
                    "productId": row.product_id,
                    "period": row.period.isoformat(),
                    "version": row.version,
                    "unitCost": str(row.unit_cost),
                    "totalCost": str(row.total_cost),
                }, correlation_id=correlation,
            )
            correlation = event.correlationId
            publisher.publish(event)
        return rows

    add_json_service(server, "profitability.gateway.CostingGateway", {
        "GetCostBreakdown": get_breakdown,
        "CalculateCost": calculate,
    })

    if LAB7_EVENT_BACKEND.lower() == "kafka":
        def production_ready(event):
            service.mark_production_ready(date.fromisoformat(event.payload["period"]))

        def financial_ready(event):
            service.mark_financial_ready(date.fromisoformat(event.payload["period"]))

        def master_changed(event):
            # Existing calculations remain versioned; the event marks that a recalculation may be required.
            cache_delete_prefix("costing-context:")
            logger.info("master data changed; costing cache invalidated", extra={"service": "costing", "event_type": event.eventType, "correlation_id": event.correlationId})

        consumer = KafkaEventConsumer(
            f"{KAFKA_GROUP_PREFIX}-costing",
            {
                "ProductionDataImported": production_ready,
                "FinancialDataImported": financial_ready,
                "MasterDataChanged": master_changed,
            },
        )
        consumer.start_in_thread("costing-kafka-consumer")


def _analytics_server(server, publisher):
    service = ProfitabilityAnalyticsService()
    costing = CostingDomainClient()
    financial = FinancialDomainClient()
    master_bridge = JsonGrpcClient(MASTER_DATA_GRPC_TARGET, "profitability.gateway.MasterDataGateway")

    def detail(request, context):
        row = service.get_profitability_detail(request.product_id, date.fromisoformat(request.period))
        if row is None:
            _abort_not_found(context, "Profitability result was not found")
        return pb.GetProfitabilityDetailResponse(
            result_id=row.id, revenue=str(row.revenue), cost_of_sales=str(row.cost_of_sales),
            profit=str(row.profit), margin_percent=str(row.margin_percent),
            calculated_at=row.calculated_at.isoformat(),
        )

    add_profitability_handler(server, detail)

    def list_profitability(p):
        return service.list_profitability(
            product_ids=p.get("product_ids"),
            period_from=date.fromisoformat(p["period_from"]),
            period_to=date.fromisoformat(p["period_to"]),
            min_margin_percent=Decimal(p["min_margin_percent"]) if p.get("min_margin_percent") is not None else None,
            sort_by=p.get("sort_by", "PERIOD"), sort_direction=p.get("sort_direction", "ASC"),
        )

    def summary(p):
        return service.aggregate_profitability(
            p.get("product_ids"), date.fromisoformat(p["period_from"]), date.fromisoformat(p["period_to"]),
            Decimal(p["min_margin_percent"]) if p.get("min_margin_percent") is not None else None,
        )

    def calculate_for(period: date, product_ids: list[str]):
        items = []
        for product_id in product_ids:
            cost = costing.get_approved_cost(product_id, period)
            sales = financial.get_sales(product_id, period)
            items.append(ProfitabilityCalculationInput(
                calculation_id=cost.calculation_id,
                product_id=product_id,
                unit_cost=cost.unit_cost,
                sold_quantity=sales.sold_qty,
                revenue=sales.revenue,
            ))
        job = service.calculate_profitability(period, items)
        for product_id in product_ids:
            row = service.get_profitability_detail(product_id, period)
            product = master_bridge.call("GetProduct", {"product_id": product_id}) or {}
            publisher.publish(EventEnvelope.create(
                "ProfitabilityCalculated", "profitability-analytics-service",
                {
                    "resultId": row.id,
                    "productId": product_id,
                    "groupId": product.get("group_id", ""),
                    "period": period.isoformat(),
                    "revenue": str(row.revenue),
                    "costOfSales": str(row.cost_of_sales),
                    "profit": str(row.profit),
                    "marginPercent": str(row.margin_percent),
                },
            ))
        return job

    def calculate(p):
        return calculate_for(date.fromisoformat(p["period"]), list(p["product_ids"]))

    def status(p):
        return service.get_calculation_status(p["job_id"])

    add_json_service(server, "profitability.gateway.AnalyticsGateway", {
        "ListProfitability": list_profitability,
        "ProfitabilitySummary": summary,
        "CalculateProfitability": calculate,
        "GetCalculationStatus": status,
    })

    if LAB7_EVENT_BACKEND.lower() == "kafka":
        def cost_completed(event):
            try:
                calculate_for(date.fromisoformat(event.payload["period"]), [event.payload["productId"]])
            except Exception as exc:
                logger.exception("analytics failed to process CostCalculationCompleted", extra={"service": "analytics", "event_type": event.eventType, "correlation_id": event.correlationId, "error_type": type(exc).__name__})
                raise

        consumer = KafkaEventConsumer(
            f"{KAFKA_GROUP_PREFIX}-analytics",
            {"CostCalculationCompleted": cost_completed},
        )
        consumer.start_in_thread("analytics-kafka-consumer")


def _reporting_server(server, publisher):
    service = ReportingService()

    def get_export(p):
        return service.get_report_export(p["export_id"])

    def create_export(p):
        return service.create_export(p["format"], p["requested_by"], p.get("report_id"))

    add_json_service(server, "profitability.gateway.ReportingGateway", {
        "GetReportExport": get_export,
        "CreateExport": create_export,
    })

    if LAB7_EVENT_BACKEND.lower() == "kafka":
        def profitability_calculated(event):
            x = event.payload
            service.update_profitability_projection(
                source_result_id=x["resultId"], product_id=x["productId"], group_id=x.get("groupId", ""),
                period=date.fromisoformat(x["period"]), revenue=Decimal(x["revenue"]),
                total_cost=Decimal(x["costOfSales"]), profit=Decimal(x["profit"]),
                margin_percent=Decimal(x["marginPercent"]), updated_at=datetime.now(),
            )

        consumer = KafkaEventConsumer(
            f"{KAFKA_GROUP_PREFIX}-reporting",
            {"ProfitabilityCalculated": profitability_calculated},
        )
        consumer.start_in_thread("reporting-kafka-consumer")


BUILDERS = {
    "master_data": (_port_from_target(MASTER_DATA_GRPC_TARGET), _master_server),
    "production": (_port_from_target(PRODUCTION_GRPC_TARGET), _production_server),
    "financial": (_port_from_target(FINANCIAL_GRPC_TARGET), _financial_server),
    "costing": (_port_from_target(COSTING_GRPC_TARGET), _costing_server),
    "analytics": (_port_from_target(ANALYTICS_GRPC_TARGET), _analytics_server),
    "reporting": (_port_from_target(REPORTING_GRPC_TARGET), _reporting_server),
}


def build_server(service_name: str, *, port: int | None = None, publisher=None):
    if service_name not in BUILDERS:
        raise ValueError(f"Unknown service: {service_name}")
    configured_port, builder = BUILDERS[service_name]
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=16))
    builder(server, publisher or _publisher())
    bind_port = port if port is not None else configured_port
    actual_port = server.add_insecure_port(f"0.0.0.0:{bind_port}")
    return server, actual_port


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("service", choices=sorted(BUILDERS))
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    init_databases()
    server, port = build_server(args.service, port=args.port)
    server.start()
    logger.info("gRPC server listening", extra={"service": args.service, "operation": f"port:{port}"})
    server.wait_for_termination()


if __name__ == "__main__":
    main()
