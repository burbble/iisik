from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from app.shared.errors import ValidationError
from .models import CostCalculation, OverheadAllocation
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
    planned_unit_cost: Decimal | None = None
    unit_cost_deviation: Decimal | None = None


@dataclass(frozen=True)
class ProductCostInput:
    product_id: str
    produced_qty: Decimal
    material_cost: Decimal
    labor_cost: Decimal
    labor_hours: Decimal
    allocation_lines: list[dict] = field(default_factory=list)
    source_versions: dict = field(default_factory=dict)
    planned_unit_cost: Decimal | None = None


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
            planned_unit_cost=row.planned_unit_cost,
            unit_cost_deviation=row.unit_cost - row.planned_unit_cost
            if row.planned_unit_cost is not None
            else None,
        )

    def get_cost_breakdown(
        self, product_id: str, period: date, version: int | None = None
    ):
        row = self.repository.find_cost_breakdown(product_id, period, version)
        return None if row is None else self._dto(row)

    def calculate_costs(
        self,
        period: date,
        items: list[ProductCostInput],
        overhead_amount: Decimal,
        allocation_base: str,
        overhead_by_center: dict | None = None,
    ) -> list[CostBreakdownDTO]:
        allocation_base = allocation_base.upper()
        if allocation_base not in {"VOLUME", "LABOR_HOURS", "DIRECT_COST"}:
            raise ValidationError(
                "allocationBase must be VOLUME, LABOR_HOURS or DIRECT_COST"
            )
        if not items:
            raise ValidationError(
                "At least one product is required for cost calculation"
            )
        if not overhead_amount.is_finite() or overhead_amount < 0:
            raise ValidationError("Overhead amount cannot be negative")
        for item in items:
            if not all(
                value.is_finite()
                for value in [
                    item.produced_qty,
                    item.material_cost,
                    item.labor_cost,
                    item.labor_hours,
                ]
            ):
                raise ValidationError("Cost values must be finite decimals")
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

        if len({x.product_id for x in items}) != len(items):
            raise ValidationError("Duplicate product IDs are not allowed")
        allocations = {x.product_id: [] for x in items}
        if overhead_by_center is not None:
            if (
                sum(
                    (Decimal(amount) for amount in overhead_by_center.values()),
                    Decimal(0),
                )
                != overhead_amount
            ):
                raise ValidationError(
                    "Center overhead totals must equal the financial source amount"
                )
            for center, amount in overhead_by_center.items():
                amount = Decimal(amount)
                lines = [
                    (item, line)
                    for item in items
                    for line in item.allocation_lines
                    if line["cost_center_id"] == center
                ]
                center_basis = sum(
                    (Decimal(line[allocation_base]) for _, line in lines), Decimal(0)
                )
                if center_basis <= 0 and amount != 0:
                    raise ValidationError(
                        f"No positive allocation basis for cost center {center}"
                    )
                assigned = Decimal(0)
                for i, (item, line) in enumerate(lines):
                    value = Decimal(line[allocation_base])
                    share = (
                        amount - assigned
                        if i == len(lines) - 1
                        else (amount * value / center_basis).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        )
                        if center_basis
                        else Decimal(0)
                    )
                    assigned += share
                    allocations[item.product_id].append((line, value, share))
        rows, details = [], []
        result: list[CostBreakdownDTO] = []
        allocated = Decimal("0.00")
        for index, item in enumerate(items):
            if index == len(items) - 1:
                overhead = overhead_amount - allocated
            else:
                share = basis(item) / total_basis
                overhead = (overhead_amount * share).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                allocated += overhead

            if overhead_by_center is not None:
                overhead = sum(
                    (value for _, _, value in allocations[item.product_id]), Decimal(0)
                )
            material = Decimal(item.material_cost).quantize(Decimal("0.01"))
            labor = Decimal(item.labor_cost).quantize(Decimal("0.01"))
            total = material + labor + overhead
            unit = (total / item.produced_qty).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
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
                source_versions=item.source_versions,
                planned_unit_cost=item.planned_unit_cost,
            )
            rows.append(row)
            for line, value, amount in allocations[item.product_id]:
                details.append(
                    OverheadAllocation(
                        allocation_id=str(uuid4()),
                        calculation_id=row.calculation_id,
                        production_order_id=line["production_order_id"],
                        cost_center_id=line["cost_center_id"],
                        basis_type=allocation_base,
                        basis_value=value,
                        amount=amount,
                    )
                )
            if overhead_by_center is None:
                # Direct API callers must supply enough source detail to audit a nonzero allocation.
                if overhead and not item.allocation_lines:
                    raise ValidationError(
                        "Allocation details and overhead_by_center are required for nonzero overhead"
                    )
                item_allocated = Decimal(0)
                for i, line in enumerate(item.allocation_lines):
                    value = Decimal(line[allocation_base])
                    amount = (
                        overhead - item_allocated
                        if i == len(item.allocation_lines) - 1
                        else (overhead * value / basis(item)).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        )
                    )
                    item_allocated += amount
                    details.append(
                        OverheadAllocation(
                            allocation_id=str(uuid4()),
                            calculation_id=row.calculation_id,
                            production_order_id=line["production_order_id"],
                            cost_center_id=line["cost_center_id"],
                            basis_type=allocation_base,
                            basis_value=value,
                            amount=amount,
                        )
                    )
            result.append(self._dto(row))
        self.repository.save_batch(rows, details)
        return [self._dto(row) for row in rows]

    def mark_production_ready(self, period: date):
        return self.repository.mark_readiness(period, production=True)

    def mark_financial_ready(self, period: date):
        return self.repository.mark_readiness(period, financial=True)

    def readiness(self, period: date):
        return self.repository.get_readiness(period)
