from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    JSON,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CostCalculation(Base):
    __tablename__ = "cost_calculations"
    calculation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    period: Mapped[date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    material_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    overhead_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    produced_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    planned_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    source_versions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class OverheadAllocation(Base):
    __tablename__ = "overhead_allocations"
    allocation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    calculation_id: Mapped[str] = mapped_column(
        ForeignKey("cost_calculations.calculation_id"), nullable=False
    )
    production_order_id: Mapped[str] = mapped_column(String(36), nullable=False)
    cost_center_id: Mapped[str] = mapped_column(String(36), nullable=False)
    basis_type: Mapped[str] = mapped_column(String(40), nullable=False)
    basis_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class IntegrationReadiness(Base):
    __tablename__ = "integration_readiness"
    period: Mapped[date] = mapped_column(Date, primary_key=True)
    production_ready: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    financial_ready: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    envelope: Mapped[dict] = mapped_column(JSON, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
