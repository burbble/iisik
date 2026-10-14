from dataclasses import dataclass
from datetime import datetime

from app.shared.errors import NotFoundError, ValidationError
from .repository import ReportingRepository


@dataclass(frozen=True)
class ReportExportDTO:
    id: str
    status: str
    format: str
    requested_by: str
    file_ref: str | None
    error_message: str | None


class ReportingService:
    def __init__(self, repository: ReportingRepository | None = None):
        self.repository = repository or ReportingRepository()

    @staticmethod
    def _dto(row) -> ReportExportDTO:
        return ReportExportDTO(
            id=row.export_id,
            status=row.status,
            format=row.format,
            requested_by=row.requested_by,
            file_ref=row.file_ref,
            error_message=row.error_message,
        )

    def get_report_export(self, export_id: str):
        row = self.repository.get_report_export(export_id)
        return None if row is None else self._dto(row)

    def create_export(self, format: str, requested_by: str, report_id: str | None = None):
        format = format.upper()
        if format not in {"XLSX", "CSV", "PDF"}:
            raise ValidationError("Export format must be XLSX, CSV or PDF")
        if not requested_by:
            raise ValidationError("requestedBy is required")
        if report_id is not None and not self.repository.saved_report_exists(report_id):
            raise NotFoundError("Saved report was not found")
        row = self.repository.create_export(
            report_id=report_id,
            requested_by=requested_by,
            format=format,
            created_at=datetime.now(),
        )
        return self._dto(row)

    def update_profitability_projection(
        self, source_result_id: str, product_id: str, group_id: str, period,
        revenue, total_cost, profit, margin_percent, updated_at
    ):
        return self.repository.upsert_profitability_read_model(
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
