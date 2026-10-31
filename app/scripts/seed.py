from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import delete

from app.bootstrap import init_databases
from app.services.identity.database import SessionLocal as IdentitySession
from app.services.identity.models import Role, User, UserRole
from app.services.auth.passwords import hash_password
from app.services.master_data.database import SessionLocal as MasterSession
from app.services.master_data.models import (
    CostCenter,
    ExternalMapping,
    Material,
    Product,
    ProductGroup,
    ProductMaterial,
    PlannedCost,
)
from app.services.production.database import SessionLocal as ProductionSession
from app.services.production.models import (
    OutboxEvent as ProdOutbox,
    ImportError as ProdImportError,
    ImportRun as ProdImportRun,
    LaborEntry,
    MaterialConsumption,
    ProductionOrder,
)
from app.services.financial.database import SessionLocal as FinancialSession
from app.services.financial.models import (
    OutboxEvent as FinOutbox,
    FinancialEntry,
    ImportError as FinImportError,
    ImportRun as FinImportRun,
    SalesDocument,
    SalesItem,
)
from app.services.costing.database import SessionLocal as CostingSession
from app.services.costing.models import (
    CostCalculation,
    OverheadAllocation,
    OutboxEvent,
    IntegrationReadiness,
)
from app.services.analytics.database import SessionLocal as AnalyticsSession
from app.services.analytics.models import (
    CalculationJob,
    ProfitabilityAggregate,
    ProfitabilityResult,
)
from app.services.reporting.database import SessionLocal as ReportingSession
from app.services.reporting.models import (
    ProfitabilityReadModel,
    ReportExport,
    SavedReport,
)

GROUP_ID = "11111111-1111-1111-1111-111111111111"
PRODUCT_A = "22222222-2222-2222-2222-222222222222"
PRODUCT_B = "33333333-3333-3333-3333-333333333333"
MATERIAL_ID = "44444444-4444-4444-4444-444444444444"
COST_CENTER_ID = "55555555-5555-5555-5555-555555555555"
COST_CALC_ID = "66666666-6666-6666-6666-666666666666"
COST_CALC_B_ID = "66666666-6666-6666-6666-666666666667"
RESULT_ID = "77777777-7777-7777-7777-777777777777"
RESULT_B_ID = "77777777-7777-7777-7777-777777777778"
JOB_ID = "88888888-8888-8888-8888-888888888888"
EXPORT_ID = "99999999-9999-9999-9999-999999999999"
USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PRODUCTION_USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaab"
FINANCE_USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaac"
MANAGER_USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaad"
ADMIN_USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaae"
DEMO_PASSWORD = "Lab5Password!"
FAILED_RUN_ID = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeef"
REPORT_ID = "f9999999-9999-9999-9999-999999999999"


def clear_and_seed() -> None:
    init_databases()
    now = datetime(2026, 9, 30, 12, 0, 0)
    period = date(2026, 9, 1)

    with IdentitySession.begin() as s:
        for model in [UserRole, Role, User]:
            s.execute(delete(model))
        password_hash = hash_password(DEMO_PASSWORD)
        users = [
            (USER_ID, "analyst@example.local", "ANALYST"),
            (PRODUCTION_USER_ID, "production@example.local", "PRODUCTION_ACCOUNTANT"),
            (FINANCE_USER_ID, "finance@example.local", "FINANCE_ACCOUNTANT"),
            (MANAGER_USER_ID, "manager@example.local", "MANAGER"),
            (ADMIN_USER_ID, "admin@example.local", "ADMIN"),
        ]
        role_rows = {
            "ANALYST": ("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1", "Экономист-аналитик"),
            "PRODUCTION_ACCOUNTANT": (
                "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2",
                "Специалист производственного учета",
            ),
            "FINANCE_ACCOUNTANT": (
                "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb3",
                "Специалист финансового учета",
            ),
            "MANAGER": ("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb4", "Руководитель"),
            "ADMIN": ("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb5", "Администратор"),
        }
        for role_name, (role_id, description) in role_rows.items():
            s.add(Role(role_id=role_id, name=role_name, description=description))
        for user_id, email, role_name in users:
            s.add(
                User(
                    user_id=user_id,
                    email=email,
                    password_hash=password_hash,
                    status="ACTIVE",
                    created_at=now,
                )
            )
            s.add(
                UserRole(
                    user_id=user_id, role_id=role_rows[role_name][0], assigned_at=now
                )
            )

    with MasterSession.begin() as s:
        for model in [
            PlannedCost,
            ProductMaterial,
            ExternalMapping,
            Product,
            Material,
            CostCenter,
            ProductGroup,
        ]:
            s.execute(delete(model))
        s.add(
            ProductGroup(
                group_id=GROUP_ID,
                parent_id=None,
                code="FIRE",
                name="Пожарное оборудование",
            )
        )
        s.add_all(
            [
                Product(
                    product_id=PRODUCT_A,
                    group_id=GROUP_ID,
                    code="PD-1",
                    name="Пульт управления ПД-1",
                    unit="шт",
                    active=True,
                ),
                Product(
                    product_id=PRODUCT_B,
                    group_id=GROUP_ID,
                    code="DET-01",
                    name="Пожарный извещатель",
                    unit="шт",
                    active=True,
                ),
            ]
        )
        s.add(
            Material(
                material_id=MATERIAL_ID,
                code="PCB-01",
                name="Печатная плата",
                unit="шт",
                standard_price=Decimal("18.50"),
            )
        )
        s.add(
            CostCenter(
                cost_center_id=COST_CENTER_ID,
                code="ASSEMBLY",
                name="Сборочный участок",
                allocation_base="LABOR_HOURS",
            )
        )
        s.add_all(
            [
                ProductMaterial(
                    product_id=PRODUCT_A,
                    material_id=MATERIAL_ID,
                    valid_from=date(2026, 1, 1),
                    standard_qty=Decimal("1.0000"),
                    valid_to=None,
                ),
                ProductMaterial(
                    product_id=PRODUCT_B,
                    material_id=MATERIAL_ID,
                    valid_from=date(2026, 1, 1),
                    standard_qty=Decimal("0.5000"),
                    valid_to=None,
                ),
            ]
        )
        s.add_all(
            [
                PlannedCost(
                    plan_id="plan-a",
                    product_id=PRODUCT_A,
                    period=period,
                    version=1,
                    unit_cost=Decimal("38"),
                    status="APPROVED",
                ),
                PlannedCost(
                    plan_id="plan-b",
                    product_id=PRODUCT_B,
                    period=period,
                    version=1,
                    unit_cost=Decimal("18"),
                    status="APPROVED",
                ),
            ]
        )
        s.add(
            ExternalMapping(
                mapping_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
                source_system="ERP",
                entity_type="PRODUCT",
                external_code="ERP-PD-1",
                internal_id=PRODUCT_A,
                status="RESOLVED",
                updated_at=now,
            )
        )

    from uuid import uuid4

    with MasterSession.begin() as s:
        for source in ["MES", "ERP", "FINANCE"]:
            for kind, code, internal in [
                ("PRODUCT", "PD-1", PRODUCT_A),
                ("PRODUCT", "DET-01", PRODUCT_B),
                ("MATERIAL", "PCB-01", MATERIAL_ID),
                ("COST_CENTER", "ASSEMBLY", COST_CENTER_ID),
            ]:
                s.add(
                    ExternalMapping(
                        mapping_id=str(uuid4()),
                        source_system=source,
                        entity_type=kind,
                        external_code=code,
                        internal_id=internal,
                        status="RESOLVED",
                        updated_at=now,
                    )
                )

    order_a = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    order_b = "dddddddd-dddd-dddd-dddd-ddddddddddde"
    prod_run_id = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    with ProductionSession.begin() as s:
        for model in [
            ProdOutbox,
            ProdImportError,
            MaterialConsumption,
            LaborEntry,
            ProductionOrder,
            ProdImportRun,
        ]:
            s.execute(delete(model))
        s.add(
            ProdImportRun(
                import_run_id=prod_run_id,
                source_system="ERP",
                period=period,
                status="COMPLETED",
                records_loaded=250,
                records_failed=0,
                started_at=now,
                finished_at=now,
            )
        )
        s.add(
            ProdImportRun(
                import_run_id=FAILED_RUN_ID,
                source_system="MES",
                period=date(2026, 8, 1),
                status="FAILED",
                records_loaded=14,
                records_failed=1,
                started_at=now,
                finished_at=now,
            )
        )
        s.add(
            ProdImportError(
                error_id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeee01",
                import_run_id=FAILED_RUN_ID,
                record_key="MES-15",
                error_code="MAPPING_NOT_FOUND",
                message="Не найдено сопоставление продукции",
                raw_payload={"product": "MES-X"},
            )
        )
        s.add_all(
            [
                ProductionOrder(
                    order_id=order_a,
                    external_id="ERP-ORD-9001",
                    product_id=PRODUCT_A,
                    period=period,
                    quantity=Decimal("100.0000"),
                    status="COMPLETED",
                ),
                ProductionOrder(
                    order_id=order_b,
                    external_id="ERP-ORD-9002",
                    product_id=PRODUCT_B,
                    period=period,
                    quantity=Decimal("200.0000"),
                    status="COMPLETED",
                ),
            ]
        )
        s.add_all(
            [
                MaterialConsumption(
                    consumption_id="f1111111-1111-1111-1111-111111111111",
                    order_id=order_a,
                    material_id=MATERIAL_ID,
                    quantity=Decimal("100.0000"),
                    amount=Decimal("1850.00"),
                    posted_at=now,
                ),
                MaterialConsumption(
                    consumption_id="f1111111-1111-1111-1111-111111111112",
                    order_id=order_b,
                    material_id=MATERIAL_ID,
                    quantity=Decimal("100.0000"),
                    amount=Decimal("2200.00"),
                    posted_at=now,
                ),
                LaborEntry(
                    labor_entry_id="f2222222-2222-2222-2222-222222222222",
                    order_id=order_a,
                    cost_center_id=COST_CENTER_ID,
                    hours=Decimal("45.00"),
                    amount=Decimal("1350.00"),
                ),
                LaborEntry(
                    labor_entry_id="f2222222-2222-2222-2222-222222222223",
                    order_id=order_b,
                    cost_center_id=COST_CENTER_ID,
                    hours=Decimal("30.00"),
                    amount=Decimal("1000.00"),
                ),
            ]
        )

    fin_run_id = "f3333333-3333-3333-3333-333333333333"
    sales_doc_id = "f4444444-4444-4444-4444-444444444444"
    with FinancialSession.begin() as s:
        for model in [
            FinOutbox,
            FinImportError,
            SalesItem,
            SalesDocument,
            FinancialEntry,
            FinImportRun,
        ]:
            s.execute(delete(model))
        s.add(
            FinImportRun(
                import_run_id=fin_run_id,
                source_system="FINANCE",
                period=period,
                status="COMPLETED",
                records_loaded=84,
                records_failed=0,
                started_at=now,
                finished_at=now,
            )
        )
        s.add(
            SalesDocument(
                sales_document_id=sales_doc_id,
                external_id="FIN-SALE-1001",
                document_date=date(2026, 9, 20),
                customer_ref="CUSTOMER-1",
                currency="USD",
            )
        )
        s.add_all(
            [
                SalesItem(
                    sales_item_id="f5555555-5555-5555-5555-555555555555",
                    sales_document_id=sales_doc_id,
                    product_id=PRODUCT_A,
                    quantity=Decimal("80.0000"),
                    revenue=Decimal("6400.00"),
                    discount=Decimal("0.00"),
                ),
                SalesItem(
                    sales_item_id="f5555555-5555-5555-5555-555555555556",
                    sales_document_id=sales_doc_id,
                    product_id=PRODUCT_B,
                    quantity=Decimal("150.0000"),
                    revenue=Decimal("6000.00"),
                    discount=Decimal("0.00"),
                ),
            ]
        )
        s.add(
            FinancialEntry(
                entry_id="f6666666-6666-6666-6666-666666666666",
                external_id="FIN-OH-1",
                period=period,
                cost_center_id=COST_CENTER_ID,
                entry_type="OVERHEAD",
                amount=Decimal("1400.00"),
                currency="USD",
                posted_at=now,
            )
        )

    with CostingSession.begin() as s:
        for model in [
            OutboxEvent,
            IntegrationReadiness,
            OverheadAllocation,
            CostCalculation,
        ]:
            s.execute(delete(model))
        s.add_all(
            [
                CostCalculation(
                    calculation_id=COST_CALC_ID,
                    product_id=PRODUCT_A,
                    period=period,
                    version=1,
                    status="COMPLETED",
                    material_cost=Decimal("1850.00"),
                    labor_cost=Decimal("1350.00"),
                    overhead_cost=Decimal("800.00"),
                    total_cost=Decimal("4000.00"),
                    produced_qty=Decimal("100.0000"),
                    unit_cost=Decimal("40.0000"),
                    created_at=now,
                ),
                CostCalculation(
                    calculation_id=COST_CALC_B_ID,
                    product_id=PRODUCT_B,
                    period=period,
                    version=1,
                    status="COMPLETED",
                    material_cost=Decimal("2200.00"),
                    labor_cost=Decimal("1000.00"),
                    overhead_cost=Decimal("600.00"),
                    total_cost=Decimal("3800.00"),
                    produced_qty=Decimal("200.0000"),
                    unit_cost=Decimal("19.0000"),
                    created_at=now,
                ),
            ]
        )
        s.add_all(
            [
                OverheadAllocation(
                    allocation_id="f7777777-7777-7777-7777-777777777777",
                    calculation_id=COST_CALC_ID,
                    production_order_id=order_a,
                    cost_center_id=COST_CENTER_ID,
                    basis_type="LABOR_HOURS",
                    basis_value=Decimal("45.0000"),
                    amount=Decimal("800.00"),
                ),
                OverheadAllocation(
                    allocation_id="f7777777-7777-7777-7777-777777777778",
                    calculation_id=COST_CALC_B_ID,
                    production_order_id=order_b,
                    cost_center_id=COST_CENTER_ID,
                    basis_type="LABOR_HOURS",
                    basis_value=Decimal("30.0000"),
                    amount=Decimal("600.00"),
                ),
            ]
        )

    with AnalyticsSession.begin() as s:
        for model in [ProfitabilityAggregate, ProfitabilityResult, CalculationJob]:
            s.execute(delete(model))
        s.add_all(
            [
                ProfitabilityResult(
                    cost_version=1,
                    result_id=RESULT_ID,
                    calculation_id=COST_CALC_ID,
                    product_id=PRODUCT_A,
                    period=period,
                    revenue=Decimal("6400.00"),
                    cost_of_sales=Decimal("3200.00"),
                    profit=Decimal("3200.00"),
                    margin_percent=Decimal("50.00"),
                    calculated_at=now,
                ),
                ProfitabilityResult(
                    cost_version=1,
                    result_id=RESULT_B_ID,
                    calculation_id=COST_CALC_B_ID,
                    product_id=PRODUCT_B,
                    period=period,
                    revenue=Decimal("6000.00"),
                    cost_of_sales=Decimal("2850.00"),
                    profit=Decimal("3150.00"),
                    margin_percent=Decimal("52.50"),
                    calculated_at=now,
                ),
            ]
        )
        s.add(
            ProfitabilityAggregate(
                aggregate_id="f8888888-8888-8888-8888-888888888888",
                dimension_type="PRODUCT_GROUP",
                dimension_id=GROUP_ID,
                period=period,
                revenue=Decimal("12400.00"),
                total_cost=Decimal("6050.00"),
                profit=Decimal("6350.00"),
                margin_percent=Decimal("51.21"),
                updated_at=now,
            )
        )
        s.add(
            CalculationJob(
                job_id=JOB_ID,
                status="COMPLETED",
                period=period,
                product_ids=[PRODUCT_A, PRODUCT_B],
            )
        )

    with ReportingSession.begin() as s:
        for model in [ReportExport, SavedReport, ProfitabilityReadModel]:
            s.execute(delete(model))
        s.add_all(
            [
                ProfitabilityReadModel(
                    cost_version=1,
                    row_id="ab111111-1111-1111-1111-111111111111",
                    source_result_id=RESULT_ID,
                    product_id=PRODUCT_A,
                    group_id=GROUP_ID,
                    period=period,
                    revenue=Decimal("6400.00"),
                    total_cost=Decimal("3200.00"),
                    profit=Decimal("3200.00"),
                    margin_percent=Decimal("50.00"),
                    updated_at=now,
                ),
                ProfitabilityReadModel(
                    cost_version=1,
                    row_id="ab111111-1111-1111-1111-111111111112",
                    source_result_id=RESULT_B_ID,
                    product_id=PRODUCT_B,
                    group_id=GROUP_ID,
                    period=period,
                    revenue=Decimal("6000.00"),
                    total_cost=Decimal("2850.00"),
                    profit=Decimal("3150.00"),
                    margin_percent=Decimal("52.50"),
                    updated_at=now,
                ),
            ]
        )
        s.add(
            SavedReport(
                report_id=REPORT_ID,
                user_id=USER_ID,
                name="Рентабельность за сентябрь",
                parameters={"period": "2026-09"},
                created_at=now,
                updated_at=now,
            )
        )
        s.add(
            ReportExport(
                export_id=EXPORT_ID,
                report_id=REPORT_ID,
                requested_by=USER_ID,
                format="XLSX",
                status="READY",
                file_ref="/exports/profitability-2026-09.xlsx",
                created_at=now,
                completed_at=now,
                error_message=None,
            )
        )

    print("Test data created")
    print(f"PRODUCT_A={PRODUCT_A}")
    print(f"PRODUCT_B={PRODUCT_B}")
    print(f"FAILED_RUN_ID={FAILED_RUN_ID}")
    print(f"JOB_ID={JOB_ID}")
    print(f"EXPORT_ID={EXPORT_ID}")
    print(f"DEMO_PASSWORD={DEMO_PASSWORD}")


if __name__ == "__main__":
    clear_and_seed()
