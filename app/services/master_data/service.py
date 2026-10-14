from dataclasses import dataclass
from datetime import datetime

from app.shared.errors import NotFoundError, ValidationError
from .repository import MasterDataRepository


@dataclass(frozen=True)
class ProductDTO:
    id: str
    code: str
    name: str
    group_id: str
    unit: str
    active: bool


@dataclass(frozen=True)
class ExternalMappingDTO:
    id: str
    source_system: str
    entity_type: str
    external_code: str
    internal_id: str
    status: str
    updated_at: datetime


class MasterDataService:
    def __init__(self, repository: MasterDataRepository | None = None):
        self.repository = repository or MasterDataRepository()

    @staticmethod
    def _dto(row) -> ProductDTO:
        return ProductDTO(
            id=row.product_id,
            code=row.code,
            name=row.name,
            group_id=row.group_id,
            unit=row.unit,
            active=row.active,
        )

    def list_products(
        self,
        group_id=None,
        active=None,
        search=None,
        sort_by="CODE",
        sort_direction="ASC",
    ) -> list[ProductDTO]:
        if sort_by not in {"CODE", "NAME"}:
            raise ValidationError("Unsupported product sort field")
        if sort_direction not in {"ASC", "DESC"}:
            raise ValidationError("Sort direction must be ASC or DESC")
        rows = self.repository.list_products(
            group_id=group_id,
            active=active,
            search=search,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )
        return [self._dto(row) for row in rows]

    def get_product(self, product_id: str) -> ProductDTO | None:
        row = self.repository.get_product(product_id)
        return None if row is None else self._dto(row)

    def resolve_external_mapping(
        self,
        source_system: str,
        entity_type: str,
        external_code: str,
        internal_id: str,
    ) -> ExternalMappingDTO:
        source_system = source_system.strip().upper()
        entity_type = entity_type.strip().upper()
        external_code = external_code.strip()
        if not source_system or not external_code:
            raise ValidationError("Source system and external code are required")
        if entity_type not in {"PRODUCT", "MATERIAL", "COST_CENTER"}:
            raise ValidationError("Unsupported mapping entity type")
        if not self.repository.internal_entity_exists(entity_type, internal_id):
            raise NotFoundError("Internal master-data object was not found")

        row = self.repository.upsert_mapping(
            source_system=source_system,
            entity_type=entity_type,
            external_code=external_code,
            internal_id=internal_id,
            updated_at=datetime.now(),
        )
        return ExternalMappingDTO(
            id=row.mapping_id,
            source_system=row.source_system,
            entity_type=row.entity_type,
            external_code=row.external_code,
            internal_id=row.internal_id,
            status=row.status,
            updated_at=row.updated_at,
        )
