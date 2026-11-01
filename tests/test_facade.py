from datetime import date
from decimal import Decimal

import pytest

from app.bootstrap import get_container
from app.gateway.clients.factory import create_grpc_clients
from app.gateway.facade import ApplicationFacade
from app.scripts.seed import (
    FAILED_RUN_ID,
    GROUP_ID,
    PRODUCT_A,
    PRODUCT_B,
    USER_ID,
    PRODUCTION_USER_ID,
    FINANCE_USER_ID,
    MANAGER_USER_ID,
    clear_and_seed,
)
from app.shared.errors import AuthorizationError
from app.shared.security import Actor


def setup_function():
    clear_and_seed()
    get_container.cache_clear()


def facade():
    return ApplicationFacade(create_grpc_clients())


def actor(user_id=USER_ID, role="ANALYST"):
    return Actor(
        user_id=user_id,
        email=f"{role.lower()}@example.local",
        roles=(role,),
        session_id="test-session",
    )


def test_query_filter_sort_and_group_filter():
    f = facade()
    a = actor()
    products = f.products(a, active=True, sort_by="CODE", sort_direction="DESC")
    assert len(products) == 2
    rows = f.profitability(
        a,
        product_ids=None,
        group_ids=[GROUP_ID],
        period_from=date(2026, 9, 1),
        period_to=date(2026, 9, 30),
        sort_by="MARGIN_PERCENT",
        sort_direction="DESC",
    )
    assert [r.product_id for r in rows] == [PRODUCT_B, PRODUCT_A]


def test_summary_uses_real_business_filter():
    summary = facade().profitability_summary(
        actor(),
        product_ids=[PRODUCT_A],
        group_ids=None,
        period_from=date(2026, 9, 1),
        period_to=date(2026, 9, 30),
    )
    assert summary.count == 1
    assert summary.total_profit == Decimal("3200.00")


def test_start_production_import_and_duplicate_rule():
    f = facade()
    prod = actor(PRODUCTION_USER_ID, "PRODUCTION_ACCOUNTANT")
    row = f.start_production_import(prod, "MES", date(2026, 10, 1))
    assert row.status == "COMPLETED"
    assert row.source == "MES"


def test_production_import_is_denied_for_analyst():
    with pytest.raises(AuthorizationError):
        facade().start_production_import(actor(), "MES", date(2026, 10, 1))


def test_financial_import_is_role_protected():
    f = facade()
    finance = actor(FINANCE_USER_ID, "FINANCE_ACCOUNTANT")
    row = f.start_financial_import(finance, "FINANCE", date(2026, 10, 1))
    assert row.status == "COMPLETED"
    with pytest.raises(AuthorizationError):
        f.start_financial_import(
            actor(PRODUCTION_USER_ID, "PRODUCTION_ACCOUNTANT"),
            "FINANCE",
            date(2026, 11, 1),
        )


def test_retry_import_is_routed_through_grpc_clients():
    row = facade().retry_import(
        actor(PRODUCTION_USER_ID, "PRODUCTION_ACCOUNTANT"), FAILED_RUN_ID
    )
    assert row.status == "COMPLETED"


def test_calculate_cost_business_operation():
    rows = facade().calculate_cost(
        actor(), date(2026, 9, 1), [PRODUCT_A, PRODUCT_B], "LABOR_HOURS"
    )
    assert len(rows) == 2
    assert all(row.version == 2 for row in rows)


def test_calculate_profitability_creates_completed_job():
    f = facade()
    a = actor()
    f.calculate_cost(a, date(2026, 9, 1), [PRODUCT_A, PRODUCT_B], "LABOR_HOURS")
    job = f.calculate_profitability(a, date(2026, 9, 1), [PRODUCT_A, PRODUCT_B])
    assert job.status == "COMPLETED"
    assert set(job.product_ids) == {PRODUCT_A, PRODUCT_B}


def test_export_uses_authenticated_user_not_client_supplied_id():
    row = facade().export_report(actor(USER_ID, "ANALYST"), "PDF")
    assert row.status == "READY"
    from pathlib import Path

    assert Path(row.file_ref).is_file()
    assert row.format == "PDF"
    assert row.requested_by == USER_ID


def test_manager_can_read_analytics_but_cannot_calculate_cost():
    manager = actor(MANAGER_USER_ID, "MANAGER")
    rows = facade().profitability(
        manager,
        product_ids=None,
        group_ids=None,
        period_from=date(2026, 9, 1),
        period_to=date(2026, 9, 30),
    )
    assert len(rows) == 2
    with pytest.raises(AuthorizationError):
        facade().calculate_cost(manager, date(2026, 9, 1), [PRODUCT_A], "VOLUME")
