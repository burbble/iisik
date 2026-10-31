from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete, func, select

from .database import SessionLocal
from .models import FinancialEntry, ImportError, ImportRun, SalesDocument, SalesItem


class FinancialRepository:
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

    def get_overhead_amount(self, period: date) -> Decimal:
        with SessionLocal() as session:
            value = session.scalar(
                select(func.coalesce(func.sum(FinancialEntry.amount), 0)).where(
                    FinancialEntry.period == period,
                    FinancialEntry.entry_type.in_(["OVERHEAD", "CORRECTION"]),
                )
            )
            return Decimal(value)

    def get_sales_data(self, product_id: str, date_from: date, date_to_exclusive: date):
        with SessionLocal() as session:
            quantity = session.scalar(
                select(func.coalesce(func.sum(SalesItem.quantity), 0))
                .join(
                    SalesDocument,
                    SalesItem.sales_document_id == SalesDocument.sales_document_id,
                )
                .where(
                    SalesItem.product_id == product_id,
                    SalesDocument.document_date >= date_from,
                    SalesDocument.document_date < date_to_exclusive,
                )
            )
            revenue = session.scalar(
                select(
                    func.coalesce(func.sum(SalesItem.revenue - SalesItem.discount), 0)
                )
                .join(
                    SalesDocument,
                    SalesItem.sales_document_id == SalesDocument.sales_document_id,
                )
                .where(
                    SalesItem.product_id == product_id,
                    SalesDocument.document_date >= date_from,
                    SalesDocument.document_date < date_to_exclusive,
                )
            )
            return Decimal(quantity), Decimal(revenue)

    def get_overhead_breakdown(
        self, period: date, cost_center_ids: list[str] | None = None
    ):
        with SessionLocal() as session:
            stmt = select(FinancialEntry).where(FinancialEntry.period == period)
            if cost_center_ids:
                stmt = stmt.where(FinancialEntry.cost_center_id.in_(cost_center_ids))
            rows = list(session.scalars(stmt))
            overhead: dict[str, Decimal] = {}
            correction = Decimal("0")
            for row in rows:
                if row.entry_type == "CORRECTION":
                    overhead[row.cost_center_id] = overhead.get(
                        row.cost_center_id, Decimal("0")
                    ) + Decimal(row.amount)
                elif row.entry_type == "OVERHEAD":
                    overhead[row.cost_center_id] = overhead.get(
                        row.cost_center_id, Decimal("0")
                    ) + Decimal(row.amount)
            return overhead, correction

    def get_sales_currency(
        self, product_id: str, date_from: date, date_to_exclusive: date
    ) -> str:
        with SessionLocal() as session:
            row = session.execute(
                select(SalesDocument.currency)
                .join(
                    SalesItem,
                    SalesItem.sales_document_id == SalesDocument.sales_document_id,
                )
                .where(
                    SalesItem.product_id == product_id,
                    SalesDocument.document_date >= date_from,
                    SalesDocument.document_date < date_to_exclusive,
                )
                .limit(1)
            ).first()
            return "USD" if row is None else row[0]

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
