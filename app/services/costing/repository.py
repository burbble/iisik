from datetime import date
from sqlalchemy import desc, func, select
from .database import SessionLocal
from .models import CostCalculation, IntegrationReadiness, OutboxEvent


class CostingRepository:
    def find_cost_breakdown(
        self, product_id: str, period: date, version: int | None = None
    ):
        stmt = select(CostCalculation).where(
            CostCalculation.product_id == product_id,
            CostCalculation.period == period,
        )
        if version is not None:
            stmt = stmt.where(CostCalculation.version == version)
        else:
            stmt = stmt.order_by(desc(CostCalculation.version)).limit(1)
        with SessionLocal() as session:
            return session.scalar(stmt)

    def next_version(self, product_id: str, period: date) -> int:
        with SessionLocal() as session:
            current = session.scalar(
                select(func.max(CostCalculation.version)).where(
                    CostCalculation.product_id == product_id,
                    CostCalculation.period == period,
                )
            )
            return int(current or 0) + 1

    def save_calculation(self, row: CostCalculation) -> CostCalculation:
        with SessionLocal.begin() as session:
            session.add(row)
            session.flush()
            session.refresh(row)
            return row

    def mark_readiness(
        self,
        period: date,
        *,
        production: bool | None = None,
        financial: bool | None = None,
        updated_at=None,
    ):
        from datetime import datetime

        with SessionLocal.begin() as session:
            row = session.scalar(
                select(IntegrationReadiness).where(
                    IntegrationReadiness.period == period
                )
            )
            if row is None:
                row = IntegrationReadiness(
                    period=period,
                    production_ready=False,
                    financial_ready=False,
                    updated_at=updated_at or datetime.now(),
                )
                session.add(row)
            if production is not None:
                row.production_ready = production
            if financial is not None:
                row.financial_ready = financial
            row.updated_at = updated_at or datetime.now()
            session.flush()
            session.refresh(row)
            return row

    def get_readiness(self, period: date):
        with SessionLocal() as session:
            return session.scalar(
                select(IntegrationReadiness).where(
                    IntegrationReadiness.period == period
                )
            )

    def save_batch(self, rows, allocations):
        from uuid import uuid4
        from app.transport.kafka.events import EventEnvelope

        correlation = str(uuid4())
        with SessionLocal.begin() as session:
            from sqlalchemy import text

            if session.bind.dialect.name == "sqlite":
                session.execute(text("BEGIN IMMEDIATE"))
            for row in rows:
                current = session.scalar(
                    select(func.max(CostCalculation.version)).where(
                        CostCalculation.product_id == row.product_id,
                        CostCalculation.period == row.period,
                    )
                )
                row.version = int(current or 0) + 1
            session.add_all(rows)
            session.flush()
            session.add_all(allocations)
            for row in rows:
                event = EventEnvelope.create(
                    "CostCalculationCompleted",
                    "costing-service",
                    {
                        "calculationId": row.calculation_id,
                        "productId": row.product_id,
                        "period": row.period.isoformat(),
                        "version": row.version,
                        "unitCost": str(row.unit_cost),
                        "totalCost": str(row.total_cost),
                        "sourceVersions": row.source_versions,
                    },
                    correlation_id=correlation,
                )
                session.add(
                    OutboxEvent(
                        event_id=event.eventId,
                        envelope=event.to_dict(),
                        published_at=None,
                        last_error=None,
                    )
                )

    def invalidate(self, period=None, product_id=None):
        from sqlalchemy import update

        stmt = update(CostCalculation).where(CostCalculation.status == "COMPLETED")
        if period is not None:
            stmt = stmt.where(CostCalculation.period == period)
        if product_id is not None:
            stmt = stmt.where(CostCalculation.product_id == product_id)
        with SessionLocal.begin() as session:
            session.execute(stmt.values(status="INVALIDATED"))

    def list_center_products(self, cost_center_ids, period_from, period_to):
        from .models import OverheadAllocation

        with SessionLocal() as session:
            return list(
                session.scalars(
                    select(CostCalculation.product_id)
                    .join(
                        OverheadAllocation,
                        OverheadAllocation.calculation_id
                        == CostCalculation.calculation_id,
                    )
                    .where(
                        CostCalculation.period >= period_from,
                        CostCalculation.period <= period_to,
                        CostCalculation.status == "COMPLETED",
                        OverheadAllocation.cost_center_id.in_(cost_center_ids),
                    )
                    .distinct()
                )
            )

    def list_allocations(self, product_id, period, version=None, cost_center_id=None):
        from .models import OverheadAllocation

        calculation = self.find_cost_breakdown(product_id, period, version)
        if calculation is None:
            return []
        stmt = select(OverheadAllocation).where(
            OverheadAllocation.calculation_id == calculation.calculation_id
        )
        if cost_center_id is not None:
            stmt = stmt.where(OverheadAllocation.cost_center_id == cost_center_id)
        with SessionLocal() as session:
            return list(session.scalars(stmt))
