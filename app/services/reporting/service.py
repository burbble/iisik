from dataclasses import dataclass
from datetime import datetime

from app.shared.errors import NotFoundError, ValidationError, AuthorizationError
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

    def create_export(
        self, format: str, requested_by: str, report_id: str | None = None
    ):
        format = format.upper()
        if format not in {"XLSX", "CSV", "PDF"}:
            raise ValidationError("Export format must be XLSX, CSV or PDF")
        if not requested_by:
            raise ValidationError("requestedBy is required")
        saved = self.repository.get_saved_report(report_id) if report_id else None
        if report_id and saved is None:
            raise NotFoundError("Saved report was not found")
        if saved is not None and saved.user_id != requested_by:
            raise AuthorizationError("Cannot export another user's saved report")
        row = self.repository.create_export(
            report_id=report_id,
            requested_by=requested_by,
            format=format,
            created_at=datetime.now(),
        )
        try:
            path = self._write_export(row, saved.parameters if saved else {})
            row = self.repository.finish_export(row.export_id, str(path))
        except Exception as exc:
            row = self.repository.finish_export(row.export_id, error=str(exc))
        return self._dto(row)

    def _write_export(self, export, parameters):
        import csv
        from datetime import date
        from app.config import DATA_DIR

        period = parameters.get("period")
        start = (
            date.fromisoformat(parameters["period_from"])
            if parameters.get("period_from")
            else date.fromisoformat(period[:7] + "-01")
            if period
            else date.min
        )
        end = (
            date.fromisoformat(parameters["period_to"])
            if parameters.get("period_to")
            else date(start.year, start.month, 28)
            if period
            else date.max
        )
        rows = self.repository.list_profitability(
            parameters.get("product_ids"),
            start,
            end,
            parameters.get("min_margin_percent"),
        )
        if parameters.get("group_ids") is not None:
            rows = [r for r in rows if r.group_id in parameters["group_ids"]]
        headers = [
            "product_id",
            "period",
            "revenue",
            "cost_of_sales",
            "profit",
            "margin_percent",
        ]
        values = [[str(getattr(r, key)) for key in headers] for r in rows]
        folder = DATA_DIR / "exports"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{export.export_id}.{export.format.lower()}"
        temp = path.with_suffix(path.suffix + ".tmp")
        if export.format == "CSV":
            with temp.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(headers)
                writer.writerows(values)
        elif export.format == "XLSX":
            from openpyxl import Workbook

            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Profitability"
            sheet.append(headers)
            for value in values:
                sheet.append(value)
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width = 22
            workbook.save(temp)
        else:
            from reportlab.platypus import (
                SimpleDocTemplate,
                Table,
                TableStyle,
                Paragraph,
                Spacer,
            )
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape

            document = SimpleDocTemplate(str(temp), pagesize=landscape(A4))
            table = Table(
                [headers] + values, repeatRows=1, colWidths=[225, 80, 85, 85, 85, 110]
            )
            table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            document.build(
                [
                    Paragraph("Product profitability", getSampleStyleSheet()["Title"]),
                    Spacer(1, 12),
                    table,
                ]
            )
        temp.replace(path)
        return path.resolve()

    def list_profitability(self, *args, **kwargs):
        from app.services.analytics.service import ProfitabilityAnalyticsService

        return ProfitabilityAnalyticsService(self.repository).list_profitability(
            *args, **kwargs
        )

    def aggregate_profitability(self, *args, **kwargs):
        from app.services.analytics.service import ProfitabilityAnalyticsService

        return ProfitabilityAnalyticsService(self.repository).aggregate_profitability(
            *args, **kwargs
        )

    def update_profitability_projection(
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
    ):
        return self.repository.upsert_profitability_read_model(
            cost_version=cost_version,
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
