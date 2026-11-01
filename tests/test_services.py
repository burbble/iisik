from datetime import date
from decimal import Decimal

import pytest

from app.bootstrap import get_container
from app.scripts.seed import (
    COST_CENTER_ID,
    FAILED_RUN_ID,
    PRODUCT_A,
    PRODUCT_B,
    REPORT_ID,
    USER_ID,
    clear_and_seed,
)
from app.services.costing.service import ProductCostInput
from app.shared.errors import ConflictError, ValidationError


def setup_function():
    clear_and_seed()
    get_container.cache_clear()


def test_product_filter_and_sort():
    services = get_container()
    rows = services.master_data.list_products(
        active=True, sort_by="NAME", sort_direction="DESC"
    )
    assert len(rows) == 2
    assert rows[0].name >= rows[1].name


def test_retry_failed_import_changes_state():
    services = get_container()
    row = services.production.retry_import(FAILED_RUN_ID)
    assert row.status == "COMPLETED"
    assert row.records_loaded > 0
    assert row.records_failed == 0
    assert row.errors == []


def test_retry_completed_import_is_rejected():
    services = get_container()
    completed_id = services.production.list_import_runs(source="ERP")[0].id
    with pytest.raises(ConflictError):
        services.production.retry_import(completed_id)


def test_resolve_mapping_updates_master_data():
    services = get_container()
    row = services.master_data.resolve_external_mapping(
        "MES", "PRODUCT", "MES-DET-01", PRODUCT_B
    )
    assert row.status == "RESOLVED"
    assert row.internal_id == PRODUCT_B


def test_cost_calculation_allocates_overhead():
    services = get_container()
    a = services.production.get_cost_data(PRODUCT_A, date(2026, 9, 1))
    b = services.production.get_cost_data(PRODUCT_B, date(2026, 9, 1))
    rows = services.costing.calculate_costs(
        period=date(2026, 9, 1),
        items=[
            ProductCostInput(
                PRODUCT_A,
                a.produced_qty,
                a.material_cost,
                a.labor_cost,
                a.labor_hours,
                allocation_lines=services.production.repository.allocation_data(
                    PRODUCT_A, date(2026, 9, 1)
                ),
            ),
            ProductCostInput(
                PRODUCT_B,
                b.produced_qty,
                b.material_cost,
                b.labor_cost,
                b.labor_hours,
                allocation_lines=services.production.repository.allocation_data(
                    PRODUCT_B, date(2026, 9, 1)
                ),
            ),
        ],
        overhead_amount=Decimal("1400.00"),
        allocation_base="LABOR_HOURS",
        overhead_by_center={COST_CENTER_ID: Decimal("1400")},
    )
    assert len(rows) == 2
    assert sum((r.overhead_cost for r in rows), Decimal("0")) == Decimal("1400.00")
    assert all(r.version == 2 for r in rows)


def test_invalid_allocation_base_is_rejected():
    services = get_container()
    with pytest.raises(ValidationError):
        services.costing.calculate_costs(
            date(2026, 9, 1), [], Decimal("100"), "UNKNOWN"
        )


def test_profitability_aggregation():
    services = get_container()
    summary = services.analytics.aggregate_profitability(
        product_ids=None,
        period_from=date(2026, 9, 1),
        period_to=date(2026, 9, 30),
    )
    assert summary.count == 2
    assert summary.total_revenue == Decimal("12400.00")
    assert summary.total_profit == Decimal("6350.00")
    assert summary.average_margin_percent == Decimal("51.25")


def test_export_business_operation_creates_file():
    services = get_container()
    row = services.reporting.create_export("CSV", USER_ID, REPORT_ID)
    assert row.status == "READY"
    from pathlib import Path

    assert Path(row.file_ref).is_file()
    assert row.format == "CSV"
