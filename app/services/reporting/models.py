from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Integer, Date, DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProfitabilityReadModel(Base):
    __tablename__ = "profitability_read_model"
    row_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    cost_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_result_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False
    )
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    group_id: Mapped[str] = mapped_column(String(36), nullable=False)
    period: Mapped[date] = mapped_column(Date, nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    profit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    margin_percent: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    @property
    def result_id(self):
        return self.source_result_id

    @property
    def cost_of_sales(self):
        return self.total_cost

    @property
    def calculated_at(self):
        return self.updated_at


class SavedReport(Base):
    __tablename__ = "saved_reports"
    report_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ReportExport(Base):
    __tablename__ = "report_exports"
    export_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    report_id: Mapped[str | None] = mapped_column(ForeignKey("saved_reports.report_id"))
    requested_by: Mapped[str] = mapped_column(String(36), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    file_ref: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
