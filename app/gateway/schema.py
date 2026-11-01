from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

import strawberry
from strawberry.types import Info


@strawberry.enum
class ImportSource(Enum):
    ERP = "ERP"
    MES = "MES"
    FINANCE = "FINANCE"


@strawberry.enum
class ImportStatus(Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@strawberry.enum
class CalculationStatus(Enum):
    COMPLETED = "COMPLETED"
    INVALIDATED = "INVALIDATED"


@strawberry.enum
class ExportFormat(Enum):
    XLSX = "XLSX"
    CSV = "CSV"
    PDF = "PDF"


@strawberry.enum
class SortDirection(Enum):
    ASC = "ASC"
    DESC = "DESC"


@strawberry.enum
class ProductSortField(Enum):
    CODE = "CODE"
    NAME = "NAME"


@strawberry.enum
class ProfitabilitySortField(Enum):
    PERIOD = "PERIOD"
    REVENUE = "REVENUE"
    PROFIT = "PROFIT"
    MARGIN_PERCENT = "MARGIN_PERCENT"


@strawberry.input(name="ProductFilterInput")
class ProductFilterInput:
    group_id: strawberry.ID | None = None
    active: bool | None = None
    search: str | None = None


@strawberry.input(name="ProductSortInput")
class ProductSortInput:
    field: ProductSortField = ProductSortField.CODE
    direction: SortDirection = SortDirection.ASC


@strawberry.input(name="ProfitabilityFilterInput")
class ProfitabilityFilterInput:
    period_from: date
    period_to: date
    product_ids: list[strawberry.ID] | None = None
    group_ids: list[strawberry.ID] | None = None
    min_margin_percent: Decimal | None = None
    cost_center_ids: list[strawberry.ID] | None = None


@strawberry.input(name="ProfitabilitySortInput")
class ProfitabilitySortInput:
    field: ProfitabilitySortField = ProfitabilitySortField.PERIOD
    direction: SortDirection = SortDirection.ASC


@strawberry.input(name="StartImportInput")
class StartImportInput:
    source: ImportSource
    period: date


@strawberry.input(name="ResolveMappingInput")
class ResolveMappingInput:
    source_system: str
    entity_type: str
    external_code: str
    internal_id: strawberry.ID


@strawberry.input(name="CostCalculationInput")
class CostCalculationInput:
    period: date
    product_ids: list[strawberry.ID]
    allocation_base: str


@strawberry.input(name="ProfitabilityCalculationInput")
class ProfitabilityCalculationInput:
    period: date
    product_ids: list[strawberry.ID]


@strawberry.input(name="ExportReportInput")
class ExportReportInput:
    format: ExportFormat
    report_id: strawberry.ID | None = None


@strawberry.input(name="CredentialsInput")
class CredentialsInput:
    email: str
    password: str


@strawberry.type(name="AuthUser")
class AuthUserType:
    id: strawberry.ID
    email: str
    roles: list[str]


@strawberry.type(name="AuthPayload")
class AuthPayloadType:
    access_token: str
    token_type: str
    expires_at: str
    user: AuthUserType


@strawberry.type(name="CurrentUser")
class CurrentUserType:
    id: strawberry.ID
    email: str
    roles: list[str]


@strawberry.type(name="Product")
class ProductType:
    id: strawberry.ID
    code: str
    name: str
    group_id: strawberry.ID
    unit: str
    active: bool


@strawberry.type(name="ImportError")
class ImportErrorType:
    record_key: str | None
    error_code: str
    message: str


@strawberry.type(name="ImportRun")
class ImportRunType:
    id: strawberry.ID
    source: ImportSource
    period: date
    status: ImportStatus
    records_loaded: int
    records_failed: int
    errors: list[ImportErrorType]
    started_at: datetime
    finished_at: datetime | None


@strawberry.type(name="CostBreakdown")
class CostBreakdownType:
    calculation_id: strawberry.ID
    product_id: strawberry.ID
    period: date
    version: int
    material_cost: Decimal
    labor_cost: Decimal
    overhead_cost: Decimal
    total_cost: Decimal
    produced_qty: Decimal
    unit_cost: Decimal
    planned_unit_cost: Decimal | None
    unit_cost_deviation: Decimal | None


@strawberry.type(name="OverheadAllocation")
class OverheadAllocationType:
    calculation_id: strawberry.ID
    production_order_id: strawberry.ID
    cost_center_id: strawberry.ID
    basis_type: str
    basis_value: Decimal
    amount: Decimal


@strawberry.type(name="ProfitabilityResult")
class ProfitabilityResultType:
    id: strawberry.ID
    product_id: strawberry.ID
    period: date
    revenue: Decimal
    cost_of_sales: Decimal
    profit: Decimal
    margin_percent: Decimal
    calculated_at: datetime


@strawberry.type(name="ProfitabilitySummary")
class ProfitabilitySummaryType:
    count: int
    total_revenue: Decimal
    total_cost: Decimal
    total_profit: Decimal
    average_margin_percent: Decimal


@strawberry.type(name="CalculationJob")
class CalculationJobType:
    id: strawberry.ID
    status: CalculationStatus
    period: date
    product_ids: list[strawberry.ID]


@strawberry.type(name="ReportExport")
class ReportExportType:
    id: strawberry.ID
    status: str
    format: ExportFormat
    file_ref: str | None
    error_message: str | None


@strawberry.type(name="ExternalMapping")
class ExternalMappingType:
    id: strawberry.ID
    source_system: str
    entity_type: str
    external_code: str
    internal_id: strawberry.ID
    status: str
    updated_at: datetime


def product_type(dto) -> ProductType:
    return ProductType(
        id=dto.id,
        code=dto.code,
        name=dto.name,
        group_id=dto.group_id,
        unit=dto.unit,
        active=dto.active,
    )


def import_run_type(dto) -> ImportRunType:
    return ImportRunType(
        id=dto.id,
        source=ImportSource(dto.source),
        period=dto.period,
        status=ImportStatus(dto.status),
        records_loaded=dto.records_loaded,
        records_failed=dto.records_failed,
        errors=[
            ImportErrorType(e.record_key, e.error_code, e.message) for e in dto.errors
        ],
        started_at=dto.started_at,
        finished_at=dto.finished_at,
    )


def cost_type(row) -> CostBreakdownType:
    return CostBreakdownType(
        calculation_id=row.calculation_id,
        product_id=row.product_id,
        period=row.period,
        version=row.version,
        material_cost=row.material_cost,
        labor_cost=row.labor_cost,
        overhead_cost=row.overhead_cost,
        total_cost=row.total_cost,
        produced_qty=row.produced_qty,
        unit_cost=row.unit_cost,
        planned_unit_cost=row.planned_unit_cost,
        unit_cost_deviation=row.unit_cost_deviation,
    )


def profitability_type(row) -> ProfitabilityResultType:
    return ProfitabilityResultType(
        id=row.id,
        product_id=row.product_id,
        period=row.period,
        revenue=row.revenue,
        cost_of_sales=row.cost_of_sales,
        profit=row.profit,
        margin_percent=row.margin_percent,
        calculated_at=row.calculated_at,
    )


def job_type(row) -> CalculationJobType:
    return CalculationJobType(
        id=row.id,
        status=CalculationStatus(row.status),
        period=row.period,
        product_ids=[strawberry.ID(x) for x in row.product_ids],
    )


def export_type(row) -> ReportExportType:
    return ReportExportType(
        id=row.id,
        status=row.status,
        format=ExportFormat(row.format),
        file_ref=row.file_ref,
        error_message=row.error_message,
    )


@strawberry.type
class Query:
    @strawberry.field
    def me(self, info: Info) -> CurrentUserType:
        actor = info.context.get("actor")
        if actor is None:
            from app.shared.errors import AuthenticationError

            raise AuthenticationError("Authentication required")
        return CurrentUserType(
            id=actor.user_id, email=actor.email, roles=list(actor.roles)
        )

    @strawberry.field
    def products(
        self,
        info: Info,
        filter: ProductFilterInput | None = None,
        sort: ProductSortInput | None = None,
    ) -> list[ProductType]:
        f = filter or ProductFilterInput()
        s = sort or ProductSortInput()
        rows = info.context["facade"].products(
            info.context.get("actor"),
            group_id=str(f.group_id) if f.group_id is not None else None,
            active=f.active,
            search=f.search,
            sort_by=s.field.value,
            sort_direction=s.direction.value,
        )
        return [product_type(row) for row in rows]

    @strawberry.field
    def import_runs(
        self,
        info: Info,
        source: ImportSource | None = None,
        period: date | None = None,
    ) -> list[ImportRunType]:
        rows = info.context["facade"].import_runs(
            info.context.get("actor"),
            source=source.value if source is not None else None,
            period=period,
        )
        return [import_run_type(row) for row in rows]

    @strawberry.field
    def cost_breakdown(
        self,
        info: Info,
        product_id: strawberry.ID,
        period: date,
        version: int | None = None,
    ) -> CostBreakdownType | None:
        row = info.context["facade"].cost_breakdown(
            info.context.get("actor"), str(product_id), period, version
        )
        return None if row is None else cost_type(row)

    @strawberry.field
    def overhead_allocations(
        self,
        info: Info,
        product_id: strawberry.ID,
        period: date,
        version: int | None = None,
        cost_center_id: strawberry.ID | None = None,
    ) -> list[OverheadAllocationType]:
        rows = info.context["facade"].overhead_allocations(
            info.context.get("actor"),
            str(product_id),
            period,
            version,
            str(cost_center_id) if cost_center_id is not None else None,
        )
        return [
            OverheadAllocationType(
                calculation_id=r["calculation_id"],
                production_order_id=r["production_order_id"],
                cost_center_id=r["cost_center_id"],
                basis_type=r["basis_type"],
                basis_value=Decimal(r["basis_value"]),
                amount=Decimal(r["amount"]),
            )
            for r in rows
        ]

    @strawberry.field
    def profitability(
        self,
        info: Info,
        filter: ProfitabilityFilterInput,
        sort: ProfitabilitySortInput | None = None,
    ) -> list[ProfitabilityResultType]:
        s = sort or ProfitabilitySortInput()
        rows = info.context["facade"].profitability(
            info.context.get("actor"),
            product_ids=[str(x) for x in filter.product_ids]
            if filter.product_ids is not None
            else None,
            group_ids=[str(x) for x in filter.group_ids]
            if filter.group_ids is not None
            else None,
            period_from=filter.period_from,
            period_to=filter.period_to,
            min_margin_percent=filter.min_margin_percent,
            cost_center_ids=[str(x) for x in filter.cost_center_ids]
            if filter.cost_center_ids is not None
            else None,
            sort_by=s.field.value,
            sort_direction=s.direction.value,
        )
        return [profitability_type(row) for row in rows]

    @strawberry.field
    def profitability_summary(
        self,
        info: Info,
        filter: ProfitabilityFilterInput,
    ) -> ProfitabilitySummaryType:
        row = info.context["facade"].profitability_summary(
            info.context.get("actor"),
            product_ids=[str(x) for x in filter.product_ids]
            if filter.product_ids is not None
            else None,
            group_ids=[str(x) for x in filter.group_ids]
            if filter.group_ids is not None
            else None,
            period_from=filter.period_from,
            period_to=filter.period_to,
            min_margin_percent=filter.min_margin_percent,
            cost_center_ids=[str(x) for x in filter.cost_center_ids]
            if filter.cost_center_ids is not None
            else None,
        )
        return ProfitabilitySummaryType(
            count=row.count,
            total_revenue=row.total_revenue,
            total_cost=row.total_cost,
            total_profit=row.total_profit,
            average_margin_percent=row.average_margin_percent,
        )

    @strawberry.field
    def calculation_status(
        self, info: Info, id: strawberry.ID
    ) -> CalculationJobType | None:
        row = info.context["facade"].calculation_status(
            info.context.get("actor"), str(id)
        )
        return None if row is None else job_type(row)

    @strawberry.field
    def report_export(self, info: Info, id: strawberry.ID) -> ReportExportType | None:
        row = info.context["facade"].report_export(info.context.get("actor"), str(id))
        return None if row is None else export_type(row)


@strawberry.type
class Mutation:
    @strawberry.mutation
    def register(self, info: Info, input: CredentialsInput) -> AuthUserType:
        actor = info.context["auth_client"].register(input.email, input.password)
        return AuthUserType(
            id=actor.user_id, email=actor.email, roles=list(actor.roles)
        )

    @strawberry.mutation
    def login(self, info: Info, input: CredentialsInput) -> AuthPayloadType:
        result = info.context["auth_client"].login(input.email, input.password)
        return AuthPayloadType(
            access_token=result.access_token,
            token_type=result.token_type,
            expires_at=result.expires_at,
            user=AuthUserType(
                id=result.user_id, email=result.email, roles=list(result.roles)
            ),
        )

    @strawberry.mutation
    def logout(self, info: Info) -> bool:
        token = info.context.get("access_token")
        if not token:
            from app.shared.errors import AuthenticationError

            raise AuthenticationError("Authentication required")
        info.context["auth_client"].logout(token)
        return True

    @strawberry.mutation
    def start_production_import(
        self, info: Info, input: StartImportInput
    ) -> ImportRunType:
        row = info.context["facade"].start_production_import(
            info.context.get("actor"), input.source.value, input.period
        )
        return import_run_type(row)

    @strawberry.mutation
    def start_financial_import(
        self, info: Info, input: StartImportInput
    ) -> ImportRunType:
        row = info.context["facade"].start_financial_import(
            info.context.get("actor"), input.source.value, input.period
        )
        return import_run_type(row)

    @strawberry.mutation
    def retry_import(self, info: Info, id: strawberry.ID) -> ImportRunType:
        return import_run_type(
            info.context["facade"].retry_import(info.context.get("actor"), str(id))
        )

    @strawberry.mutation
    def resolve_external_mapping(
        self, info: Info, input: ResolveMappingInput
    ) -> ExternalMappingType:
        row = info.context["facade"].resolve_external_mapping(
            info.context.get("actor"),
            input.source_system,
            input.entity_type,
            input.external_code,
            str(input.internal_id),
        )
        return ExternalMappingType(
            id=row.id,
            source_system=row.source_system,
            entity_type=row.entity_type,
            external_code=row.external_code,
            internal_id=row.internal_id,
            status=row.status,
            updated_at=row.updated_at,
        )

    @strawberry.mutation
    def calculate_cost(
        self, info: Info, input: CostCalculationInput
    ) -> list[CostBreakdownType]:
        rows = info.context["facade"].calculate_cost(
            info.context.get("actor"),
            period=input.period,
            product_ids=[str(x) for x in input.product_ids],
            allocation_base=input.allocation_base,
        )
        return [cost_type(row) for row in rows]

    @strawberry.mutation
    def calculate_profitability(
        self,
        info: Info,
        input: ProfitabilityCalculationInput,
    ) -> CalculationJobType:
        row = info.context["facade"].calculate_profitability(
            info.context.get("actor"),
            period=input.period,
            product_ids=[str(x) for x in input.product_ids],
        )
        return job_type(row)

    @strawberry.mutation
    def export_report(self, info: Info, input: ExportReportInput) -> ReportExportType:
        row = info.context["facade"].export_report(
            info.context.get("actor"),
            format=input.format.value,
            report_id=str(input.report_id) if input.report_id is not None else None,
        )
        return export_type(row)


schema = strawberry.Schema(query=Query, mutation=Mutation)
