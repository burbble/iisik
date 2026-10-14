from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from app.shared.errors import ValidationError
from .models import CalculationJob, ProfitabilityResult
from .repository import AnalyticsRepository


@dataclass(frozen=True)
class ProfitabilityDTO:
    id: str
    product_id: str
    period: date
    revenue: Decimal
    cost_of_sales: Decimal
    profit: Decimal
    margin_percent: Decimal
    calculated_at: datetime


@dataclass(frozen=True)
class CalculationJobDTO:
    id: str
    status: str
    period: date
    product_ids: list[str]


@dataclass(frozen=True)
class ProfitabilitySummaryDTO:
    count: int
    total_revenue: Decimal
    total_cost: Decimal
    total_profit: Decimal
    average_margin_percent: Decimal


@dataclass(frozen=True)
class ProfitabilityCalculationInput:
    calculation_id: str
    product_id: str
    unit_cost: Decimal
    sold_quantity: Decimal
    revenue: Decimal


class ProfitabilityAnalyticsService:
    def __init__(self, repository: AnalyticsRepository | None = None):
        self.repository = repository or AnalyticsRepository()

    @staticmethod
    def _dto(row) -> ProfitabilityDTO:
        return ProfitabilityDTO(
            id=row.result_id,
            product_id=row.product_id,
            period=row.period,
            revenue=row.revenue,
            cost_of_sales=row.cost_of_sales,
            profit=row.profit,
            margin_percent=row.margin_percent,
            calculated_at=row.calculated_at,
        )

    def list_profitability(
        self,
        product_ids,
        period_from,
        period_to,
        min_margin_percent=None,
        sort_by="PERIOD",
        sort_direction="ASC",
    ):
        if period_from > period_to:
            raise ValidationError("periodFrom must be less than or equal to periodTo")
        if sort_by not in {"PERIOD", "REVENUE", "PROFIT", "MARGIN_PERCENT"}:
            raise ValidationError("Unsupported profitability sort field")
        if sort_direction not in {"ASC", "DESC"}:
            raise ValidationError("Sort direction must be ASC or DESC")
        rows = self.repository.list_profitability(
            product_ids=product_ids,
            period_from=period_from,
            period_to=period_to,
            min_margin_percent=min_margin_percent,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )
        return [self._dto(row) for row in rows]

    def aggregate_profitability(self, product_ids, period_from, period_to, min_margin_percent=None):
        rows = self.list_profitability(
            product_ids=product_ids,
            period_from=period_from,
            period_to=period_to,
            min_margin_percent=min_margin_percent,
        )
        if not rows:
            return ProfitabilitySummaryDTO(
                count=0,
                total_revenue=Decimal("0.00"),
                total_cost=Decimal("0.00"),
                total_profit=Decimal("0.00"),
                average_margin_percent=Decimal("0.00"),
            )
        total_revenue = sum((r.revenue for r in rows), Decimal("0"))
        total_cost = sum((r.cost_of_sales for r in rows), Decimal("0"))
        total_profit = sum((r.profit for r in rows), Decimal("0"))
        avg_margin = (sum((r.margin_percent for r in rows), Decimal("0")) / len(rows)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return ProfitabilitySummaryDTO(
            count=len(rows),
            total_revenue=total_revenue,
            total_cost=total_cost,
            total_profit=total_profit,
            average_margin_percent=avg_margin,
        )

    def calculate_profitability(
        self,
        period: date,
        items: list[ProfitabilityCalculationInput],
    ) -> CalculationJobDTO:
        if not items:
            raise ValidationError("At least one product is required for profitability calculation")
        now = datetime.now()
        product_ids: list[str] = []
        for item in items:
            if item.revenue <= 0:
                raise ValidationError("Revenue must be greater than zero")
            if item.sold_quantity < 0 or item.unit_cost < 0:
                raise ValidationError("Quantity and unit cost cannot be negative")
            cost_of_sales = (item.unit_cost * item.sold_quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            profit = (item.revenue - cost_of_sales).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            margin = ((profit / item.revenue) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            row = ProfitabilityResult(
                result_id=str(uuid4()),
                calculation_id=item.calculation_id,
                product_id=item.product_id,
                period=period,
                revenue=item.revenue,
                cost_of_sales=cost_of_sales,
                profit=profit,
                margin_percent=margin,
                calculated_at=now,
            )
            self.repository.save_profitability(row)
            product_ids.append(item.product_id)

        job = CalculationJob(
            job_id=str(uuid4()),
            status="COMPLETED",
            period=period,
            product_ids=product_ids,
        )
        saved = self.repository.save_job(job)
        return CalculationJobDTO(
            id=saved.job_id,
            status=saved.status,
            period=saved.period,
            product_ids=list(saved.product_ids),
        )

    def get_calculation_status(self, job_id: str):
        row = self.repository.get_calculation_job(job_id)
        if row is None:
            return None
        return CalculationJobDTO(
            id=row.job_id,
            status=row.status,
            period=row.period,
            product_ids=list(row.product_ids),
        )

    def get_profitability_detail(self, product_id: str, period: date):
        row = self.repository.get_profitability_detail(product_id, period)
        return None if row is None else self._dto(row)
