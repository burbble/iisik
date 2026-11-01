from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.config import (
    MASTER_DATA_GRPC_TARGET,
    PRODUCTION_GRPC_TARGET,
    FINANCIAL_GRPC_TARGET,
    COSTING_GRPC_TARGET,
    ANALYTICS_GRPC_TARGET,
    REPORTING_GRPC_TARGET,
)
from app.services.master_data.service import ProductDTO, ExternalMappingDTO
from app.services.production.service import (
    ImportRunDTO as ProductionImportRunDTO,
    ImportErrorDTO as ProductionImportErrorDTO,
)
from app.services.financial.service import (
    ImportRunDTO as FinancialImportRunDTO,
    ImportErrorDTO as FinancialImportErrorDTO,
)
from app.services.costing.service import CostBreakdownDTO
from app.services.analytics.service import (
    ProfitabilityDTO,
    ProfitabilitySummaryDTO,
    CalculationJobDTO,
)
from app.services.reporting.service import ReportExportDTO
from app.transport.grpc.bridge import JsonGrpcClient


def _date(v):
    return None if v is None else date.fromisoformat(v)


def _dt(v):
    return None if v is None else datetime.fromisoformat(v)


class GrpcMasterDataClient:
    def __init__(self, target=MASTER_DATA_GRPC_TARGET):
        self.rpc = JsonGrpcClient(target, "profitability.gateway.MasterDataGateway")

    def list_products(self, group_id=None, active=None, search=None, sort_by="CODE", sort_direction="ASC"):
        rows = self.rpc.call("ListProducts", {
            "group_id": group_id, "active": active, "search": search,
            "sort_by": sort_by, "sort_direction": sort_direction,
        })
        return [ProductDTO(
            id=x["id"], code=x["code"], name=x["name"], group_id=x["group_id"], unit=x["unit"], active=x["active"]
        ) for x in rows]

    def get_product(self, product_id: str):
        x = self.rpc.call("GetProduct", {"product_id": product_id})
        if x is None:
            return None
        return ProductDTO(id=x["id"], code=x["code"], name=x["name"], group_id=x["group_id"], unit=x["unit"], active=x["active"])

    def resolve_external_mapping(self, source_system, entity_type, external_code, internal_id):
        x = self.rpc.call("ResolveExternalMapping", {
            "source_system": source_system, "entity_type": entity_type,
            "external_code": external_code, "internal_id": internal_id,
        })
        return ExternalMappingDTO(
            id=x["id"], source_system=x["source_system"], entity_type=x["entity_type"],
            external_code=x["external_code"], internal_id=x["internal_id"], status=x["status"], updated_at=_dt(x["updated_at"]),
        )


class _ImportMixin:
    dto_cls = None
    error_cls = None

    def _dto(self, x):
        return self.dto_cls(
            id=x["id"], source=x["source"], period=_date(x["period"]), status=x["status"],
            records_loaded=x["records_loaded"], records_failed=x["records_failed"],
            errors=[self.error_cls(e.get("record_key"), e["error_code"], e["message"]) for e in x.get("errors", [])],
            started_at=_dt(x["started_at"]), finished_at=_dt(x.get("finished_at")),
        )

    def list_import_runs(self, source=None, period=None):
        rows = self.rpc.call("ListImportRuns", {"source": source, "period": period.isoformat() if period else None})
        return [self._dto(x) for x in rows]

    def get_import_run(self, run_id):
        x = self.rpc.call("GetImportRun", {"run_id": run_id})
        return None if x is None else self._dto(x)

    def start_import(self, source, period):
        return self._dto(self.rpc.call("StartImport", {"source": source, "period": period.isoformat()}))

    def retry_import(self, run_id):
        return self._dto(self.rpc.call("RetryImport", {"run_id": run_id}))


class GrpcProductionClient(_ImportMixin):
    dto_cls = ProductionImportRunDTO
    error_cls = ProductionImportErrorDTO

    def __init__(self, target=PRODUCTION_GRPC_TARGET):
        self.rpc = JsonGrpcClient(target, "profitability.gateway.ProductionGateway")


class GrpcFinancialClient(_ImportMixin):
    dto_cls = FinancialImportRunDTO
    error_cls = FinancialImportErrorDTO

    def __init__(self, target=FINANCIAL_GRPC_TARGET):
        self.rpc = JsonGrpcClient(target, "profitability.gateway.FinancialGateway")


class GrpcCostingClient:
    def __init__(self, target=COSTING_GRPC_TARGET):
        self.rpc = JsonGrpcClient(target, "profitability.gateway.CostingGateway")

    @staticmethod
    def _dto(x):
        if x is None:
            return None
        return CostBreakdownDTO(
            calculation_id=x["calculation_id"],
            product_id=x["product_id"],
            period=_date(x["period"]),
            version=x["version"],
            material_cost=Decimal(x["material_cost"]),
            labor_cost=Decimal(x["labor_cost"]),
            overhead_cost=Decimal(x["overhead_cost"]),
            total_cost=Decimal(x["total_cost"]),
            produced_qty=Decimal(x["produced_qty"]),
            unit_cost=Decimal(x["unit_cost"]),
            planned_unit_cost=Decimal(x["planned_unit_cost"])
            if x.get("planned_unit_cost") is not None
            else None,
            unit_cost_deviation=Decimal(x["unit_cost_deviation"])
            if x.get("unit_cost_deviation") is not None
            else None,
        )

    def get_cost_breakdown(self, product_id, period, version=None):
        return self._dto(
            self.rpc.call(
                "GetCostBreakdown",
                {
                    "product_id": product_id,
                    "period": period.isoformat(),
                    "version": version,
                },
            )
        )

    def calculate_costs_remote(
        self, period: date, product_ids: list[str], allocation_base: str
    ):
        rows = self.rpc.call(
            "CalculateCost",
            {
                "period": period.isoformat(),
                "product_ids": product_ids,
                "allocation_base": allocation_base,
            },
        )
        return [self._dto(x) for x in rows]

    def list_center_products(self, cost_center_ids, period_from, period_to):
        return self.rpc.call(
            "ListCostCenterProducts",
            {
                "cost_center_ids": cost_center_ids,
                "period_from": period_from.isoformat(),
                "period_to": period_to.isoformat(),
            },
        )

    def list_allocations(self, product_id, period, version=None, cost_center_id=None):
        return self.rpc.call(
            "ListOverheadAllocations",
            {
                "product_id": product_id,
                "period": period.isoformat(),
                "version": version,
                "cost_center_id": cost_center_id,
            },
        )

    # Kept only for Protocol compatibility; LR6 orchestration uses calculate_costs_remote.
    def calculate_costs(self, period, items, overhead_amount, allocation_base):
        ids = [x.product_id for x in items]
        return self.calculate_costs_remote(period, ids, allocation_base)


class GrpcAnalyticsClient:
    def __init__(self, target=ANALYTICS_GRPC_TARGET):
        self.rpc = JsonGrpcClient(target, "profitability.gateway.AnalyticsGateway")

    @staticmethod
    def _dto(x):
        return ProfitabilityDTO(
            id=x["id"], product_id=x["product_id"], period=_date(x["period"]), revenue=Decimal(x["revenue"]),
            cost_of_sales=Decimal(x["cost_of_sales"]), profit=Decimal(x["profit"]), margin_percent=Decimal(x["margin_percent"]),
            calculated_at=_dt(x["calculated_at"]),
        )

    def list_profitability(self, product_ids, period_from, period_to, min_margin_percent=None, sort_by="PERIOD", sort_direction="ASC"):
        rows = self.rpc.call("ListProfitability", {
            "product_ids": product_ids, "period_from": period_from.isoformat(), "period_to": period_to.isoformat(),
            "min_margin_percent": str(min_margin_percent) if min_margin_percent is not None else None,
            "sort_by": sort_by, "sort_direction": sort_direction,
        })
        return [self._dto(x) for x in rows]

    def aggregate_profitability(self, product_ids, period_from, period_to, min_margin_percent=None):
        x = self.rpc.call("ProfitabilitySummary", {
            "product_ids": product_ids, "period_from": period_from.isoformat(), "period_to": period_to.isoformat(),
            "min_margin_percent": str(min_margin_percent) if min_margin_percent is not None else None,
        })
        return ProfitabilitySummaryDTO(
            count=x["count"], total_revenue=Decimal(x["total_revenue"]), total_cost=Decimal(x["total_cost"]),
            total_profit=Decimal(x["total_profit"]), average_margin_percent=Decimal(x["average_margin_percent"]),
        )

    def calculate_profitability_remote(self, period: date, product_ids: list[str]):
        x = self.rpc.call("CalculateProfitability", {"period": period.isoformat(), "product_ids": product_ids})
        return CalculationJobDTO(id=x["id"], status=x["status"], period=_date(x["period"]), product_ids=x["product_ids"])

    def calculate_profitability(self, period, items):
        ids = [x.product_id for x in items]
        return self.calculate_profitability_remote(period, ids)

    def get_calculation_status(self, job_id):
        x = self.rpc.call("GetCalculationStatus", {"job_id": job_id})
        if x is None:
            return None
        return CalculationJobDTO(id=x["id"], status=x["status"], period=_date(x["period"]), product_ids=x["product_ids"])


class GrpcReportingClient:
    def __init__(self, target=REPORTING_GRPC_TARGET):
        self.rpc = JsonGrpcClient(target, "profitability.gateway.ReportingGateway")

    @staticmethod
    def _dto(x):
        if x is None:
            return None
        return ReportExportDTO(
            id=x["id"], status=x["status"], format=x["format"], requested_by=x["requested_by"],
            file_ref=x.get("file_ref"), error_message=x.get("error_message"),
        )

    def get_report_export(self, export_id):
        return self._dto(self.rpc.call("GetReportExport", {"export_id": export_id}))

    def create_export(self, format, requested_by, report_id=None):
        return self._dto(self.rpc.call("CreateExport", {
            "format": format, "requested_by": requested_by, "report_id": report_id,
        }))
