from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProductionOrder(Base):
    __tablename__ = "production_orders"
    order_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    period: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class MaterialConsumption(Base):
    __tablename__ = "material_consumptions"
    consumption_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("production_orders.order_id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class LaborEntry(Base):
    __tablename__ = "labor_entries"
    labor_entry_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("production_orders.order_id"), nullable=False)
    cost_center_id: Mapped[str] = mapped_column(String(36), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


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
