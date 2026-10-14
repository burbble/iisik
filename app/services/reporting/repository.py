from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

from .database import SessionLocal
from .models import ProfitabilityReadModel, ReportExport, SavedReport


class ReportingRepository:
    def get_report_export(self, export_id: str) -> ReportExport | None:
        with SessionLocal() as session:
            return session.scalar(select(ReportExport).where(ReportExport.export_id == export_id))

    def saved_report_exists(self, report_id: str) -> bool:
        with SessionLocal() as session:
            return session.scalar(select(SavedReport).where(SavedReport.report_id == report_id)) is not None

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
        self, source_result_id: str, product_id: str, group_id: str, period, revenue, total_cost, profit, margin_percent, updated_at
    ) -> ProfitabilityReadModel:
        with SessionLocal.begin() as session:
            row = session.scalar(select(ProfitabilityReadModel).where(ProfitabilityReadModel.source_result_id == source_result_id))
            if row is None:
                row = ProfitabilityReadModel(
                    row_id=str(uuid4()), source_result_id=source_result_id, product_id=product_id, group_id=group_id,
                    period=period, revenue=revenue, total_cost=total_cost, profit=profit,
                    margin_percent=margin_percent, updated_at=updated_at,
                )
                session.add(row)
            else:
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
