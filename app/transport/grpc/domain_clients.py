from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import grpc

from app.config import (
    MASTER_DATA_GRPC_TARGET,
    PRODUCTION_GRPC_TARGET,
    FINANCIAL_GRPC_TARGET,
    COSTING_GRPC_TARGET,
    ANALYTICS_GRPC_TARGET,
    COSTING_CONTEXT_CACHE_TTL_SECONDS,
)
from app.contracts import profitability_pb as pb
from app.shared.cache import cache_get, cache_set
from app.shared.errors import NotFoundError
from app.shared.resilience import call_grpc_with_retry
from .typed import (
    MasterDataStub,
    ProductionDataStub,
    FinancialDataStub,
    CostingStub,
    ProfitabilityStub,
)


@dataclass(frozen=True)
class CostingContext:
    product_id: str
    materials: list[tuple[str, Decimal]]
    allocation_base: str
    data_version: str


@dataclass(frozen=True)
class ProductionCostData:
    product_id: str
    period: date
    produced_qty: Decimal
    material_cost: Decimal
    labor_cost: Decimal
    labor_hours: Decimal
    production_order_ids: list[str]
    allocation_lines: list[dict]
    data_version: str


@dataclass(frozen=True)
class OverheadData:
    items: list[tuple[str, Decimal]]
    correction_amount: Decimal
    data_version: str

    @property
    def total_amount(self) -> Decimal:
        return (
            sum((amount for _, amount in self.items), Decimal("0"))
            + self.correction_amount
        )


@dataclass(frozen=True)
class SalesData:
    product_id: str
    period: date
    sold_qty: Decimal
    revenue: Decimal
    currency: str
    data_version: str


@dataclass(frozen=True)
class ApprovedCost:
    calculation_id: str
    version: int
    unit_cost: Decimal
    total_cost: Decimal
    produced_qty: Decimal
    status: str


@dataclass(frozen=True)
class ProfitabilityDetail:
    result_id: str
    revenue: Decimal
    cost_of_sales: Decimal
    profit: Decimal
    margin_percent: Decimal
    calculated_at: datetime


def _call(rpc, request, not_found: str, *, operation: str, target: str):
    try:
        return call_grpc_with_retry(
            rpc,
            request,
            operation=operation,
            target=target,
            metadata=__import__(
                "app.transport.grpc.security", fromlist=["rpc_metadata"]
            ).rpc_metadata(),
        )
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.NOT_FOUND:
            raise NotFoundError(not_found) from exc
        raise RuntimeError(exc.details() or "gRPC call failed") from exc


class MasterDataDomainClient:
    def __init__(self, target: str = MASTER_DATA_GRPC_TARGET):
        self.target = target
        self.channel = grpc.insecure_channel(target)
        self.stub = MasterDataStub(self.channel)

    def get_costing_context(self, product_id: str, period: date) -> CostingContext:
        cache_key = f"costing-context:{product_id}:{period.isoformat()}"
        cached = cache_get(cache_key)
        if cached is not None:
            return CostingContext(
                product_id=cached["product_id"],
                materials=[(x[0], Decimal(x[1])) for x in cached["materials"]],
                allocation_base=cached["allocation_base"],
                data_version=cached["data_version"],
            )
        response = _call(
            self.stub.GetCostingContext,
            pb.GetCostingContextRequest(
                product_id=product_id, period=period.isoformat()
            ),
            "Master data for product was not found",
            operation="MasterDataService.GetCostingContext",
            target=self.target,
        )
        value = {
            "product_id": response.product_id,
            "materials": [[x.material_id, x.standard_qty] for x in response.materials],
            "allocation_base": response.allocation_base,
            "data_version": response.data_version,
        }
        cache_set(cache_key, value, COSTING_CONTEXT_CACHE_TTL_SECONDS)
        return CostingContext(
            product_id=response.product_id,
            materials=[
                (x.material_id, Decimal(x.standard_qty)) for x in response.materials
            ],
            allocation_base=response.allocation_base,
            data_version=response.data_version,
        )


class ProductionDomainClient:
    def __init__(self, target: str = PRODUCTION_GRPC_TARGET):
        self.target = target
        self.channel = grpc.insecure_channel(target)
        self.stub = ProductionDataStub(self.channel)

    def get_cost_data(self, product_id: str, period: date) -> ProductionCostData:
        response = _call(
            self.stub.GetProductionCostData,
            pb.GetProductionCostDataRequest(
                product_id=product_id, period=period.isoformat()
            ),
            "Production data for product and period was not found",
            operation="ProductionDataService.GetProductionCostData",
            target=self.target,
        )
        return ProductionCostData(
            product_id=product_id,
            period=period,
            produced_qty=Decimal(response.produced_qty),
            material_cost=Decimal(response.material_cost),
            labor_cost=Decimal(response.labor_cost),
            labor_hours=Decimal(response.labor_hours or "0"),
            production_order_ids=list(response.production_order_ids),
            allocation_lines=[
                {
                    "production_order_id": x.production_order_id,
                    "cost_center_id": x.cost_center_id,
                    "VOLUME": x.volume,
                    "LABOR_HOURS": x.labor_hours,
                    "DIRECT_COST": x.direct_cost,
                }
                for x in response.allocation_lines
            ],
            data_version=response.data_version,
        )


class FinancialDomainClient:
    def __init__(self, target: str = FINANCIAL_GRPC_TARGET):
        self.target = target
        self.channel = grpc.insecure_channel(target)
        self.stub = FinancialDataStub(self.channel)

    def get_overhead(
        self, period: date, cost_center_ids: list[str] | None = None
    ) -> OverheadData:
        request = pb.GetOverheadDataRequest(period=period.isoformat())
        request.cost_center_ids.extend(cost_center_ids or [])
        response = _call(
            self.stub.GetOverheadData,
            request,
            "Financial overhead data was not found",
            operation="FinancialDataService.GetOverheadData",
            target=self.target,
        )
        return OverheadData(
            items=[(x.cost_center_id, Decimal(x.amount)) for x in response.items],
            correction_amount=Decimal(response.correction_amount or "0"),
            data_version=response.data_version,
        )

    def get_sales(self, product_id: str, period: date) -> SalesData:
        response = _call(
            self.stub.GetSalesData,
            pb.GetSalesDataRequest(product_id=product_id, period=period.isoformat()),
            "Sales data for product and period was not found",
            operation="FinancialDataService.GetSalesData",
            target=self.target,
        )
        return SalesData(
            product_id=product_id,
            period=period,
            sold_qty=Decimal(response.sold_qty),
            revenue=Decimal(response.revenue),
            currency=response.currency,
            data_version=response.data_version,
        )


class CostingDomainClient:
    def __init__(self, target: str = COSTING_GRPC_TARGET):
        self.target = target
        self.channel = grpc.insecure_channel(target)
        self.stub = CostingStub(self.channel)

    def get_approved_cost(
        self, product_id: str, period: date, version: int | None = None
    ) -> ApprovedCost:
        response = _call(
            self.stub.GetApprovedCostCalculation,
            pb.GetApprovedCostCalculationRequest(
                product_id=product_id,
                period=period.isoformat(),
                version=version or 0,
            ),
            "Cost calculation was not found",
            operation="CostingService.GetApprovedCostCalculation",
            target=self.target,
        )
        return ApprovedCost(
            calculation_id=response.calculation_id,
            version=response.version,
            unit_cost=Decimal(response.unit_cost),
            total_cost=Decimal(response.total_cost),
            produced_qty=Decimal(response.produced_qty),
            status=response.status,
        )


class ProfitabilityDomainClient:
    def __init__(self, target: str = ANALYTICS_GRPC_TARGET):
        self.target = target
        self.channel = grpc.insecure_channel(target)
        self.stub = ProfitabilityStub(self.channel)

    def get_detail(self, product_id: str, period: date) -> ProfitabilityDetail:
        response = _call(
            self.stub.GetProfitabilityDetail,
            pb.GetProfitabilityDetailRequest(
                product_id=product_id, period=period.isoformat()
            ),
            "Profitability result was not found",
            operation="ProfitabilityService.GetProfitabilityDetail",
            target=self.target,
        )
        return ProfitabilityDetail(
            result_id=response.result_id,
            revenue=Decimal(response.revenue),
            cost_of_sales=Decimal(response.cost_of_sales),
            profit=Decimal(response.profit),
            margin_percent=Decimal(response.margin_percent),
            calculated_at=datetime.fromisoformat(response.calculated_at),
        )
