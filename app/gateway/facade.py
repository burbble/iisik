from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.shared.errors import AuthenticationError, AuthorizationError, NotFoundError, ValidationError
from app.shared.security import Actor
from .clients.factory import ClientBundle


class ApplicationFacade:
    """Application layer used by GraphQL resolvers.

    In Lab 7 the facade performs authorization and routes requests to real gRPC
    service clients. Cross-service business orchestration lives inside domain
    services rather than inside GraphQL resolvers.
    """

    def __init__(self, clients: ClientBundle):
        self.clients = clients

    @staticmethod
    def _require(actor: Actor | None, *roles: str) -> Actor:
        if actor is None:
            raise AuthenticationError("Authentication required")
        if roles and not actor.has_role(*roles):
            raise AuthorizationError("Operation is not allowed for current role")
        return actor

    def products(self, actor: Actor | None, group_id=None, active=None, search=None, sort_by="CODE", sort_direction="ASC"):
        self._require(actor, "ANALYST", "PRODUCTION_ACCOUNTANT", "FINANCE_ACCOUNTANT", "MANAGER")
        return self.clients.master_data.list_products(
            group_id=group_id,
            active=active,
            search=search,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )

    def import_runs(self, actor: Actor | None, source: str | None = None, period: date | None = None):
        self._require(actor, "ANALYST", "PRODUCTION_ACCOUNTANT", "FINANCE_ACCOUNTANT")
        if source == "FINANCE":
            return self.clients.financial.list_import_runs(source=source, period=period)
        if source in {"ERP", "MES"}:
            return self.clients.production.list_import_runs(source=source, period=period)
        return (
            self.clients.production.list_import_runs(period=period)
            + self.clients.financial.list_import_runs(period=period)
        )

    def cost_breakdown(self, actor: Actor | None, product_id: str, period: date, version: int | None = None):
        self._require(actor, "ANALYST", "MANAGER")
        return self.clients.costing.get_cost_breakdown(product_id, period, version)

    def _resolve_profitability_product_ids(
        self,
        product_ids: list[str] | None,
        group_ids: list[str] | None,
    ) -> list[str] | None:
        group_product_ids: set[str] | None = None
        if group_ids:
            group_product_ids = set()
            for group_id in group_ids:
                rows = self.clients.master_data.list_products(group_id=group_id, active=True)
                group_product_ids.update(row.id for row in rows)
        explicit = set(product_ids) if product_ids else None
        if explicit is not None and group_product_ids is not None:
            return sorted(explicit & group_product_ids)
        if explicit is not None:
            return sorted(explicit)
        if group_product_ids is not None:
            return sorted(group_product_ids)
        return None

    def profitability(
        self,
        actor: Actor | None,
        product_ids: list[str] | None,
        group_ids: list[str] | None,
        period_from: date,
        period_to: date,
        min_margin_percent: Decimal | None = None,
        sort_by: str = "PERIOD",
        sort_direction: str = "ASC",
    ):
        self._require(actor, "ANALYST", "MANAGER")
        resolved = self._resolve_profitability_product_ids(product_ids, group_ids)
        return self.clients.analytics.list_profitability(
            product_ids=resolved,
            period_from=period_from,
            period_to=period_to,
            min_margin_percent=min_margin_percent,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )

    def profitability_summary(
        self,
        actor: Actor | None,
        product_ids: list[str] | None,
        group_ids: list[str] | None,
        period_from: date,
        period_to: date,
        min_margin_percent: Decimal | None = None,
    ):
        self._require(actor, "ANALYST", "MANAGER")
        resolved = self._resolve_profitability_product_ids(product_ids, group_ids)
        return self.clients.analytics.aggregate_profitability(
            resolved, period_from, period_to, min_margin_percent
        )

    def calculation_status(self, actor: Actor | None, job_id: str):
        self._require(actor, "ANALYST")
        return self.clients.analytics.get_calculation_status(job_id)

    def report_export(self, actor: Actor | None, export_id: str):
        actor = self._require(actor, "ANALYST", "MANAGER")
        row = self.clients.reporting.get_report_export(export_id)
        if row is not None and "ADMIN" not in actor.roles and row.requested_by != actor.user_id:
            raise AuthorizationError("Cannot read another user's export")
        return row

    def start_production_import(self, actor: Actor | None, source: str, period: date):
        self._require(actor, "PRODUCTION_ACCOUNTANT")
        return self.clients.production.start_import(source, period)

    def start_financial_import(self, actor: Actor | None, source: str, period: date):
        self._require(actor, "FINANCE_ACCOUNTANT")
        return self.clients.financial.start_import(source, period)

    def retry_import(self, actor: Actor | None, run_id: str):
        if self.clients.production.get_import_run(run_id) is not None:
            self._require(actor, "PRODUCTION_ACCOUNTANT")
            return self.clients.production.retry_import(run_id)
        if self.clients.financial.get_import_run(run_id) is not None:
            self._require(actor, "FINANCE_ACCOUNTANT")
            return self.clients.financial.retry_import(run_id)
        raise NotFoundError("Import run was not found")

    def resolve_external_mapping(self, actor: Actor | None, source_system, entity_type, external_code, internal_id):
        self._require(actor, "PRODUCTION_ACCOUNTANT", "FINANCE_ACCOUNTANT")
        return self.clients.master_data.resolve_external_mapping(
            source_system, entity_type, external_code, internal_id
        )

    def calculate_cost(self, actor: Actor | None, period: date, product_ids: list[str], allocation_base: str):
        self._require(actor, "ANALYST")
        if not product_ids:
            raise ValidationError("productIds cannot be empty")
        return self.clients.costing.calculate_costs_remote(period, product_ids, allocation_base)

    def calculate_profitability(self, actor: Actor | None, period: date, product_ids: list[str]):
        self._require(actor, "ANALYST")
        if not product_ids:
            raise ValidationError("productIds cannot be empty")
        return self.clients.analytics.calculate_profitability_remote(period, product_ids)

    def export_report(self, actor: Actor | None, format: str, report_id: str | None = None):
        actor = self._require(actor, "ANALYST", "MANAGER")
        return self.clients.reporting.create_export(format, actor.user_id, report_id)


QueryFacade = ApplicationFacade
