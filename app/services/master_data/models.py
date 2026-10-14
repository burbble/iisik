from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProductGroup(Base):
    __tablename__ = "product_groups"
    group_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("product_groups.group_id"))
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class Product(Base):
    __tablename__ = "products"
    product_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("product_groups.group_id"), nullable=False)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Material(Base):
    __tablename__ = "materials"
    material_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    standard_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))


class ProductMaterial(Base):
    __tablename__ = "product_materials"
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), primary_key=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.material_id"), primary_key=True)
    valid_from: Mapped[date] = mapped_column(Date, primary_key=True)
    standard_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)


class CostCenter(Base):
    __tablename__ = "cost_centers"
    cost_center_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    allocation_base: Mapped[str] = mapped_column(String(40), nullable=False)


class ExternalMapping(Base):
    __tablename__ = "external_mappings"
    mapping_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    external_code: Mapped[str] = mapped_column(String(80), nullable=False)
    internal_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
