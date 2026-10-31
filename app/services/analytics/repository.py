from datetime import date
from decimal import Decimal

from sqlalchemy import asc, desc, select, func

from .database import SessionLocal
from .models import CalculationJob, ProfitabilityResult


class AnalyticsRepository:
    def list_profitability(
        self,
        product_ids: list[str] | None,
        period_from: date,
        period_to: date,
        min_margin_percent: Decimal | None,
        sort_by: str = "PERIOD",
        sort_direction: str = "ASC",
    ) -> list[ProfitabilityResult]:
        latest = (
            select(
                ProfitabilityResult.product_id.label("product"),
                ProfitabilityResult.period.label("period"),
                func.max(ProfitabilityResult.cost_version).label("version"),
            )
            .where(ProfitabilityResult.status == "COMPLETED")
            .group_by(ProfitabilityResult.product_id, ProfitabilityResult.period)
            .subquery()
        )
        stmt = (
            select(ProfitabilityResult)
            .join(
                latest,
                (ProfitabilityResult.product_id == latest.c.product)
                & (ProfitabilityResult.period == latest.c.period)
                & (ProfitabilityResult.cost_version == latest.c.version),
            )
            .where(
                ProfitabilityResult.status == "COMPLETED",
                ProfitabilityResult.period >= period_from,
                ProfitabilityResult.period <= period_to,
            )
        )
        if product_ids is not None:
            stmt = stmt.where(ProfitabilityResult.product_id.in_(product_ids))
        if min_margin_percent is not None:
            stmt = stmt.where(ProfitabilityResult.margin_percent >= min_margin_percent)
        sort_columns = {
            "PERIOD": ProfitabilityResult.period,
            "REVENUE": ProfitabilityResult.revenue,
            "PROFIT": ProfitabilityResult.profit,
            "MARGIN_PERCENT": ProfitabilityResult.margin_percent,
        }
        column = sort_columns.get(sort_by, ProfitabilityResult.period)
        order = desc(column) if sort_direction == "DESC" else asc(column)
        stmt = stmt.order_by(order, ProfitabilityResult.product_id)
        with SessionLocal() as session:
            return list(session.scalars(stmt))

    def get_calculation_job(self, job_id: str) -> CalculationJob | None:
        with SessionLocal() as session:
            return session.scalar(
                select(CalculationJob).where(CalculationJob.job_id == job_id)
            )

    def save_profitability(self, row: ProfitabilityResult) -> ProfitabilityResult:
        with SessionLocal.begin() as session:
            existing = session.scalar(
                select(ProfitabilityResult).where(
                    ProfitabilityResult.calculation_id == row.calculation_id
                )
            )
            if existing is None:
                session.add(row)
                target = row
            else:
                existing.cost_version = row.cost_version
                existing.status = "COMPLETED"
                existing.product_id = row.product_id
                existing.period = row.period
                existing.revenue = row.revenue
                existing.cost_of_sales = row.cost_of_sales
                existing.profit = row.profit
                existing.margin_percent = row.margin_percent
                existing.calculated_at = row.calculated_at
                target = existing
            session.flush()
            session.refresh(target)
            return target

    def save_job(self, row: CalculationJob) -> CalculationJob:
        with SessionLocal.begin() as session:
            session.add(row)
            session.flush()
            session.refresh(row)
            return row

    def get_profitability_detail(
        self, product_id: str, period: date
    ) -> ProfitabilityResult | None:
        with SessionLocal() as session:
            return session.scalar(
                select(ProfitabilityResult)
                .where(
                    ProfitabilityResult.status == "COMPLETED",
                    ProfitabilityResult.product_id == product_id,
                    ProfitabilityResult.period == period,
                )
                .order_by(
                    ProfitabilityResult.cost_version.desc(),
                    ProfitabilityResult.calculated_at.desc(),
                )
                .limit(1)
            )

    def invalidate(self, period=None):
        from sqlalchemy import update

        with SessionLocal.begin() as session:
            results = update(ProfitabilityResult)
            jobs = update(CalculationJob)
            if period is not None:
                results = results.where(ProfitabilityResult.period == period)
                jobs = jobs.where(CalculationJob.period == period)
            session.execute(results.values(status="INVALIDATED"))
            session.execute(jobs.values(status="INVALIDATED"))

    def get_by_calculation(self, calculation_id):
        with SessionLocal() as session:
            return session.scalar(
                select(ProfitabilityResult).where(
                    ProfitabilityResult.calculation_id == calculation_id
                )
            )
