from datetime import datetime
from uuid import uuid4

from sqlalchemy import asc, desc, func, select

from .database import SessionLocal
from .models import CostCenter, ExternalMapping, Material, Product


class MasterDataRepository:
    def list_products(
        self,
        group_id: str | None = None,
        active: bool | None = None,
        search: str | None = None,
        sort_by: str = "CODE",
        sort_direction: str = "ASC",
    ) -> list[Product]:
        stmt = select(Product)
        if group_id is not None:
            stmt = stmt.where(Product.group_id == group_id)
        if active is not None:
            stmt = stmt.where(Product.active == active)
        if search:
            pattern = f"%{search.lower()}%"
            stmt = stmt.where(
                func.lower(Product.name).like(pattern) | func.lower(Product.code).like(pattern)
            )

        sort_columns = {
            "CODE": Product.code,
            "NAME": Product.name,
        }
        column = sort_columns.get(sort_by, Product.code)
        stmt = stmt.order_by(desc(column) if sort_direction == "DESC" else asc(column))

        with SessionLocal() as session:
            return list(session.scalars(stmt))

    def get_product(self, product_id: str) -> Product | None:
        with SessionLocal() as session:
            return session.scalar(select(Product).where(Product.product_id == product_id))

    def internal_entity_exists(self, entity_type: str, internal_id: str) -> bool:
        model_and_key = {
            "PRODUCT": (Product, Product.product_id),
            "MATERIAL": (Material, Material.material_id),
            "COST_CENTER": (CostCenter, CostCenter.cost_center_id),
        }.get(entity_type)
        if model_and_key is None:
            return False
        model, key = model_and_key
        with SessionLocal() as session:
            return session.scalar(select(model).where(key == internal_id)) is not None

    def upsert_mapping(
        self,
        source_system: str,
        entity_type: str,
        external_code: str,
        internal_id: str,
        updated_at: datetime,
    ) -> ExternalMapping:
        with SessionLocal.begin() as session:
            row = session.scalar(
                select(ExternalMapping).where(
                    ExternalMapping.source_system == source_system,
                    ExternalMapping.entity_type == entity_type,
                    ExternalMapping.external_code == external_code,
                )
            )
            if row is None:
                row = ExternalMapping(
                    mapping_id=str(uuid4()),
                    source_system=source_system,
                    entity_type=entity_type,
                    external_code=external_code,
                    internal_id=internal_id,
                    status="RESOLVED",
                    updated_at=updated_at,
                )
                session.add(row)
            else:
                row.internal_id = internal_id
                row.status = "RESOLVED"
                row.updated_at = updated_at
            session.flush()
            session.refresh(row)
            return row

    def get_product_materials(self, product_id: str, period):
        from sqlalchemy import or_
        from .models import ProductMaterial
        with SessionLocal() as session:
            stmt = select(ProductMaterial).where(
                ProductMaterial.product_id == product_id,
                ProductMaterial.valid_from <= period,
                or_(ProductMaterial.valid_to.is_(None), ProductMaterial.valid_to >= period),
            )
            return list(session.scalars(stmt))

    def get_default_allocation_base(self) -> str:
        with SessionLocal() as session:
            row = session.scalar(select(CostCenter).order_by(CostCenter.code).limit(1))
            return "DIRECT_COST" if row is None else row.allocation_base
