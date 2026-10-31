from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.shared.errors import ConflictError, NotFoundError, ValidationError
from .repository import ProductionRepository


@dataclass(frozen=True)
class ImportErrorDTO:
    record_key: str | None
    error_code: str
    message: str


@dataclass(frozen=True)
class ImportRunDTO:
    id: str
    source: str
    period: date
    status: str
    records_loaded: int
    records_failed: int
    errors: list[ImportErrorDTO]
    started_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True)
class ProductionCostDataDTO:
    product_id: str
    period: date
    produced_qty: Decimal
    material_cost: Decimal
    labor_cost: Decimal
    labor_hours: Decimal


class ProductionIntegrationService:
    def __init__(self, repository: ProductionRepository | None = None):
        self.repository = repository or ProductionRepository()

    @staticmethod
    def _import_dto(run, errors) -> ImportRunDTO:
        return ImportRunDTO(
            id=run.import_run_id,
            source=run.source_system,
            period=run.period,
            status=run.status,
            records_loaded=run.records_loaded,
            records_failed=run.records_failed,
            errors=[
                ImportErrorDTO(e.record_key, e.error_code, e.message) for e in errors
            ],
            started_at=run.started_at,
            finished_at=run.finished_at,
        )

    def list_import_runs(self, source=None, period=None) -> list[ImportRunDTO]:
        return [
            self._import_dto(run, errors)
            for run, errors in self.repository.list_import_runs(source, period)
        ]

    def get_import_run(self, run_id: str) -> ImportRunDTO | None:
        pair = self.repository.get_import_run(run_id)
        return None if pair is None else self._import_dto(*pair)

    def start_import(self, source: str, period: date) -> ImportRunDTO:
        if period.day != 1:
            raise ValidationError("Import period must be the first day of a month")
        source = source.upper()
        if source not in {"ERP", "MES"}:
            raise ValidationError("Production import source must be ERP or MES")
        if self.repository.find_active_import(source, period) is not None:
            raise ConflictError(
                "An active production import already exists for this source and period"
            )
        run = self.repository.create_import(source, period, datetime.now())
        from app.shared.importing import execute_import

        return execute_import(self, self._import_dto(run, []), "production")

    def retry_import(self, run_id: str) -> ImportRunDTO:
        current = self.get_import_run(run_id)
        if current is None:
            raise NotFoundError("Production import run was not found")
        if current.status != "FAILED":
            raise ConflictError("Only a failed import can be retried")
        run = self.repository.restart_failed_import(run_id, datetime.now())
        from app.shared.importing import execute_import

        return execute_import(self, self._import_dto(run, []), "production")

    def get_cost_data(self, product_id: str, period: date) -> ProductionCostDataDTO:
        values = self.repository.get_cost_data(product_id, period)
        if values["produced_qty"] <= 0:
            raise NotFoundError("No completed production data for product and period")
        return ProductionCostDataDTO(product_id=product_id, period=period, **values)

    def complete_import(self, run_id: str, records_loaded: int = 0) -> ImportRunDTO:
        row = self.repository.complete_import(run_id, records_loaded, datetime.now())
        if row is None:
            raise NotFoundError("Production import run was not found")
        return self._import_dto(row, [])

    def get_production_order_ids(self, product_id: str, period: date) -> list[str]:
        return self.repository.list_completed_order_ids(product_id, period)
