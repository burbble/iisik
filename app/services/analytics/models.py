from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, JSON, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProfitabilityResult(Base):
    __tablename__ = "profitability_results"
    result_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    calculation_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    period: Mapped[date] = mapped_column(Date, nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cost_of_sales: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    profit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    margin_percent: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ProfitabilityAggregate(Base):
    __tablename__ = "profitability_aggregates"
    aggregate_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dimension_type: Mapped[str] = mapped_column(String(30), nullable=False)
    dimension_id: Mapped[str] = mapped_column(String(36), nullable=False)
    period: Mapped[date] = mapped_column(Date, nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    profit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    margin_percent: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CalculationJob(Base):
    __tablename__ = "calculation_jobs"
    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    period: Mapped[date] = mapped_column(Date, nullable=False)
    product_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
