from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete, func, select

from .database import SessionLocal
from .models import (
    ImportError,
    ImportRun,
    LaborEntry,
    MaterialConsumption,
    ProductionOrder,
)


class ProductionRepository:
    def list_import_runs(self, source: str | None = None, period: date | None = None):
        stmt = select(ImportRun)
        if source is not None:
            stmt = stmt.where(ImportRun.source_system == source)
        if period is not None:
            stmt = stmt.where(ImportRun.period == period)
        stmt = stmt.order_by(ImportRun.started_at.desc())
        with SessionLocal() as session:
            runs = list(session.scalars(stmt))
            result = []
            for run in runs:
                errors = list(
                    session.scalars(
                        select(ImportError).where(
                            ImportError.import_run_id == run.import_run_id
                        )
                    )
                )
                result.append((run, errors))
            return result

    def get_import_run(self, run_id: str):
        with SessionLocal() as session:
            row = session.scalar(
                select(ImportRun).where(ImportRun.import_run_id == run_id)
            )
            if row is None:
                return None
            errors = list(
                session.scalars(
                    select(ImportError).where(ImportError.import_run_id == run_id)
                )
            )
            return row, errors

    def find_active_import(self, source: str, period: date):
        with SessionLocal() as session:
            return session.scalar(
                select(ImportRun).where(
                    ImportRun.source_system == source,
                    ImportRun.period == period,
                    ImportRun.status.in_(["QUEUED", "RUNNING"]),
                )
            )

    def create_import(
        self, source: str, period: date, started_at: datetime
    ) -> ImportRun:
        row = ImportRun(
            import_run_id=str(uuid4()),
            source_system=source,
            period=period,
            status="RUNNING",
            records_loaded=0,
            records_failed=0,
            started_at=started_at,
            finished_at=None,
        )
        with SessionLocal.begin() as session:
            session.add(row)
            session.flush()
            session.refresh(row)
            return row

    def restart_failed_import(
        self, run_id: str, started_at: datetime
    ) -> ImportRun | None:
        with SessionLocal.begin() as session:
            row = session.scalar(
                select(ImportRun).where(ImportRun.import_run_id == run_id)
            )
            if row is None:
                return None
            row.status = "RUNNING"
            row.records_loaded = 0
            row.records_failed = 0
            row.started_at = started_at
            row.finished_at = None
            session.execute(
                delete(ImportError).where(ImportError.import_run_id == run_id)
            )
            session.flush()
            session.refresh(row)
            return row

    def get_cost_data(self, product_id: str, period: date):
        with SessionLocal() as session:
            produced_qty = session.scalar(
                select(func.coalesce(func.sum(ProductionOrder.quantity), 0)).where(
                    ProductionOrder.product_id == product_id,
                    ProductionOrder.period == period,
                    ProductionOrder.status == "COMPLETED",
                )
            )
            material_cost = session.scalar(
                select(func.coalesce(func.sum(MaterialConsumption.amount), 0))
                .join(
                    ProductionOrder,
                    MaterialConsumption.order_id == ProductionOrder.order_id,
                )
                .where(
                    ProductionOrder.product_id == product_id,
                    ProductionOrder.period == period,
                    ProductionOrder.status == "COMPLETED",
                )
            )
            labor_cost = session.scalar(
                select(func.coalesce(func.sum(LaborEntry.amount), 0))
                .join(ProductionOrder, LaborEntry.order_id == ProductionOrder.order_id)
                .where(
                    ProductionOrder.product_id == product_id,
                    ProductionOrder.period == period,
                    ProductionOrder.status == "COMPLETED",
                )
            )
            labor_hours = session.scalar(
                select(func.coalesce(func.sum(LaborEntry.hours), 0))
                .join(ProductionOrder, LaborEntry.order_id == ProductionOrder.order_id)
                .where(
                    ProductionOrder.product_id == product_id,
                    ProductionOrder.period == period,
                    ProductionOrder.status == "COMPLETED",
                )
            )
            return {
                "produced_qty": Decimal(produced_qty),
                "material_cost": Decimal(material_cost),
                "labor_cost": Decimal(labor_cost),
                "labor_hours": Decimal(labor_hours),
            }

    def list_completed_order_ids(self, product_id: str, period: date) -> list[str]:
        with SessionLocal() as session:
            return list(
                session.scalars(
                    select(ProductionOrder.order_id).where(
                        ProductionOrder.product_id == product_id,
                        ProductionOrder.period == period,
                        ProductionOrder.status == "COMPLETED",
                    )
                )
            )

    def complete_import(
        self, run_id: str, records_loaded: int, finished_at: datetime
    ) -> ImportRun | None:
        with SessionLocal.begin() as session:
            row = session.scalar(
                select(ImportRun).where(ImportRun.import_run_id == run_id)
            )
            if row is None:
                return None
            row.status = "COMPLETED"
            row.records_loaded = int(records_loaded)
            row.records_failed = 0
            row.finished_at = finished_at
            session.flush()
            session.refresh(row)
            return row

    def data_version(self, period):
        with SessionLocal() as session:
            runs = list(
                session.scalars(
                    select(ImportRun)
                    .where(ImportRun.period == period)
                    .order_by(ImportRun.started_at)
                )
            )
            values = [
                (
                    r.import_run_id,
                    r.status,
                    r.records_loaded,
                    r.finished_at.isoformat() if r.finished_at else None,
                )
                for r in runs
            ]
            return f"{values[-1][0]}:{values[-1][3]}" if values else "no-import"

    def list_period_order_ids(self, period):
        with SessionLocal() as session:
            return list(
                session.scalars(
                    select(ProductionOrder.order_id).where(
                        ProductionOrder.period == period
                    )
                )
            )

    def allocation_data(self, product_id, period):
        result = []
        with SessionLocal() as session:
            orders = list(
                session.scalars(
                    select(ProductionOrder).where(
                        ProductionOrder.product_id == product_id,
                        ProductionOrder.period == period,
                        ProductionOrder.status == "COMPLETED",
                    )
                )
            )
            for order in orders:
                labor = list(
                    session.scalars(
                        select(LaborEntry).where(LaborEntry.order_id == order.order_id)
                    )
                )
                material = session.scalar(
                    select(
                        func.coalesce(func.sum(MaterialConsumption.amount), 0)
                    ).where(MaterialConsumption.order_id == order.order_id)
                )
                if not labor:
                    raise ValueError(
                        "Cost center and allocation basis require labor entries for every production order"
                    )
                total_hours = sum((x.hours for x in labor), Decimal(0))
                total_labor = sum((x.amount for x in labor), Decimal(0))
                for entry in labor:
                    share = (
                        entry.hours / total_hours
                        if total_hours
                        else Decimal(1) / len(labor)
                    )
                    result.append(
                        {
                            "production_order_id": order.order_id,
                            "cost_center_id": entry.cost_center_id,
                            "VOLUME": str(order.quantity * share),
                            "LABOR_HOURS": str(entry.hours),
                            "DIRECT_COST": str(
                                (Decimal(material) + total_labor) * share
                            ),
                        }
                    )
        return result
