from datetime import date
from sqlalchemy import desc, func, select
from .database import SessionLocal
from .models import CostCalculation, IntegrationReadiness


class CostingRepository:
    def find_cost_breakdown(self, product_id: str, period: date, version: int | None = None):
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


    def mark_readiness(self, period: date, *, production: bool | None = None, financial: bool | None = None, updated_at=None):
        from datetime import datetime
        with SessionLocal.begin() as session:
            row = session.scalar(select(IntegrationReadiness).where(IntegrationReadiness.period == period))
            if row is None:
                row = IntegrationReadiness(period=period, production_ready=False, financial_ready=False, updated_at=updated_at or datetime.now())
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
            return session.scalar(select(IntegrationReadiness).where(IntegrationReadiness.period == period))
