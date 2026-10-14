from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from app.shared.errors import ValidationError
from .models import CostCalculation
from .repository import CostingRepository


@dataclass(frozen=True)
class CostBreakdownDTO:
    calculation_id: str
    product_id: str
    period: date
    version: int
    material_cost: Decimal
    labor_cost: Decimal
    overhead_cost: Decimal
    total_cost: Decimal
    produced_qty: Decimal
    unit_cost: Decimal


@dataclass(frozen=True)
class ProductCostInput:
    product_id: str
    produced_qty: Decimal
    material_cost: Decimal
    labor_cost: Decimal
    labor_hours: Decimal


class CostingService:
    def __init__(self, repository: CostingRepository | None = None):
        self.repository = repository or CostingRepository()

    @staticmethod
    def _dto(row) -> CostBreakdownDTO:
        return CostBreakdownDTO(
            calculation_id=row.calculation_id,
            product_id=row.product_id,
            period=row.period,
            version=row.version,
            material_cost=row.material_cost,
            labor_cost=row.labor_cost,
            overhead_cost=row.overhead_cost,
            total_cost=row.total_cost,
            produced_qty=row.produced_qty,
            unit_cost=row.unit_cost,
        )

    def get_cost_breakdown(self, product_id: str, period: date, version: int | None = None):
        row = self.repository.find_cost_breakdown(product_id, period, version)
        return None if row is None else self._dto(row)

    def calculate_costs(
        self,
        period: date,
        items: list[ProductCostInput],
        overhead_amount: Decimal,
        allocation_base: str,
    ) -> list[CostBreakdownDTO]:
        allocation_base = allocation_base.upper()
        if allocation_base not in {"VOLUME", "LABOR_HOURS", "DIRECT_COST"}:
            raise ValidationError("allocationBase must be VOLUME, LABOR_HOURS or DIRECT_COST")
        if not items:
            raise ValidationError("At least one product is required for cost calculation")
        if overhead_amount < 0:
            raise ValidationError("Overhead amount cannot be negative")
        for item in items:
            if item.produced_qty <= 0:
                raise ValidationError("Produced quantity must be positive")
            if item.material_cost < 0 or item.labor_cost < 0 or item.labor_hours < 0:
                raise ValidationError("Cost values cannot be negative")

        def basis(item: ProductCostInput) -> Decimal:
            if allocation_base == "VOLUME":
                return item.produced_qty
            if allocation_base == "LABOR_HOURS":
                return item.labor_hours
            return item.material_cost + item.labor_cost

        total_basis = sum((basis(item) for item in items), Decimal("0"))
        if total_basis <= 0:
            raise ValidationError("Allocation basis must be greater than zero")

        result: list[CostBreakdownDTO] = []
        allocated = Decimal("0.00")
        for index, item in enumerate(items):
            if index == len(items) - 1:
                overhead = overhead_amount - allocated
            else:
                share = basis(item) / total_basis
                overhead = (overhead_amount * share).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                allocated += overhead

            material = Decimal(item.material_cost).quantize(Decimal("0.01"))
            labor = Decimal(item.labor_cost).quantize(Decimal("0.01"))
            total = material + labor + overhead
            unit = (total / item.produced_qty).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            row = CostCalculation(
                calculation_id=str(uuid4()),
                product_id=item.product_id,
                period=period,
                version=self.repository.next_version(item.product_id, period),
                status="COMPLETED",
                material_cost=material,
                labor_cost=labor,
                overhead_cost=overhead,
                total_cost=total,
                produced_qty=item.produced_qty,
                unit_cost=unit,
                created_at=datetime.now(),
            )
            result.append(self._dto(self.repository.save_calculation(row)))
        return result


    def mark_production_ready(self, period: date):
        return self.repository.mark_readiness(period, production=True)

    def mark_financial_ready(self, period: date):
        return self.repository.mark_readiness(period, financial=True)

    def readiness(self, period: date):
        return self.repository.get_readiness(period)
