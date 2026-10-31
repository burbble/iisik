from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

from .database import SessionLocal
from .models import ProfitabilityReadModel, ReportExport, SavedReport


class ReportingRepository:
    def get_report_export(self, export_id: str) -> ReportExport | None:
        with SessionLocal() as session:
            return session.scalar(
                select(ReportExport).where(ReportExport.export_id == export_id)
            )

    def saved_report_exists(self, report_id: str) -> bool:
        with SessionLocal() as session:
            return (
                session.scalar(
                    select(SavedReport).where(SavedReport.report_id == report_id)
                )
                is not None
            )

    def create_export(
        self,
        report_id: str | None,
        requested_by: str,
        format: str,
        created_at: datetime,
    ) -> ReportExport:
        row = ReportExport(
            export_id=str(uuid4()),
            report_id=report_id,
            requested_by=requested_by,
            format=format,
            status="QUEUED",
            file_ref=None,
            created_at=created_at,
            completed_at=None,
            error_message=None,
        )
        with SessionLocal.begin() as session:
            session.add(row)
            session.flush()
            session.refresh(row)
            return row

    def upsert_profitability_read_model(
        self,
        source_result_id: str,
        product_id: str,
        group_id: str,
        period,
        revenue,
        total_cost,
        profit,
        margin_percent,
        updated_at,
        cost_version=0,
    ) -> ProfitabilityReadModel:
        with SessionLocal.begin() as session:
            row = session.scalar(
                select(ProfitabilityReadModel).where(
                    ProfitabilityReadModel.product_id == product_id,
                    ProfitabilityReadModel.period == period,
                )
            )
            if row is None:
                row = ProfitabilityReadModel(
                    cost_version=cost_version,
                    row_id=str(uuid4()),
                    source_result_id=source_result_id,
                    product_id=product_id,
                    group_id=group_id,
                    period=period,
                    revenue=revenue,
                    total_cost=total_cost,
                    profit=profit,
                    margin_percent=margin_percent,
                    updated_at=updated_at,
                )
                session.add(row)
            else:
                if cost_version < row.cost_version or (
                    cost_version == row.cost_version and updated_at < row.updated_at
                ):
                    return row
                row.cost_version = cost_version
                row.source_result_id = source_result_id
                row.product_id = product_id
                row.group_id = group_id
                row.period = period
                row.revenue = revenue
                row.total_cost = total_cost
                row.profit = profit
                row.margin_percent = margin_percent
                row.updated_at = updated_at
            session.flush()
            session.refresh(row)
            return row

    def get_saved_report(self, report_id):
        with SessionLocal() as session:
            return session.get(SavedReport, report_id)

    def finish_export(self, export_id, file_ref=None, error=None):
        with SessionLocal.begin() as session:
            row = session.get(ReportExport, export_id)
            row.status = "FAILED" if error else "READY"
            row.file_ref = file_ref
            row.error_message = error
            row.completed_at = datetime.now()
            session.flush()
            return row

    def list_profitability(
        self,
        product_ids,
        period_from,
        period_to,
        min_margin_percent=None,
        sort_by="PERIOD",
        sort_direction="ASC",
    ):
        from sqlalchemy import asc, desc

        stmt = select(ProfitabilityReadModel).where(
            ProfitabilityReadModel.period >= period_from,
            ProfitabilityReadModel.period <= period_to,
        )
        if product_ids is not None:
            stmt = stmt.where(ProfitabilityReadModel.product_id.in_(product_ids))
        if min_margin_percent is not None:
            stmt = stmt.where(
                ProfitabilityReadModel.margin_percent >= min_margin_percent
            )
        columns = {
            "PERIOD": ProfitabilityReadModel.period,
            "REVENUE": ProfitabilityReadModel.revenue,
            "PROFIT": ProfitabilityReadModel.profit,
            "MARGIN_PERCENT": ProfitabilityReadModel.margin_percent,
        }
        column = columns[sort_by]
        with SessionLocal() as session:
            return list(
                session.scalars(
                    stmt.order_by(
                        desc(column) if sort_direction == "DESC" else asc(column),
                        ProfitabilityReadModel.product_id,
                    )
                )
            )

    def invalidate(self, period=None, product_id=None):
        from sqlalchemy import delete

        stmt = delete(ProfitabilityReadModel)
        if period is not None:
            stmt = stmt.where(ProfitabilityReadModel.period == period)
        if product_id is not None:
            stmt = stmt.where(ProfitabilityReadModel.product_id == product_id)
        with SessionLocal.begin() as session:
            session.execute(stmt)
