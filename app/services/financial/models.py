from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SalesDocument(Base):
    __tablename__ = "sales_documents"
    sales_document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    document_date: Mapped[date] = mapped_column(Date, nullable=False)
    customer_ref: Mapped[str | None] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)


class SalesItem(Base):
    __tablename__ = "sales_items"
    sales_item_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sales_document_id: Mapped[str] = mapped_column(ForeignKey("sales_documents.sales_document_id"), nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)


class FinancialEntry(Base):
    __tablename__ = "financial_entries"
    entry_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    period: Mapped[date] = mapped_column(Date, nullable=False)
    cost_center_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ImportRun(Base):
    __tablename__ = "import_runs"
    import_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    period: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    records_loaded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class ImportError(Base):
    __tablename__ = "import_errors"
    error_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    import_run_id: Mapped[str] = mapped_column(ForeignKey("import_runs.import_run_id"), nullable=False)
    record_key: Mapped[str | None] = mapped_column(String(120))
    error_code: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
