from datetime import date
from decimal import Decimal

from app.contracts import profitability_pb as pb
from app.scripts.seed import PRODUCT_A, PRODUCT_B, clear_and_seed
from app.transport.grpc.domain_clients import (
    MasterDataDomainClient,
    ProductionDomainClient,
    FinancialDomainClient,
    CostingDomainClient,
    ProfitabilityDomainClient,
)
from app.gateway.clients.factory import create_grpc_clients
from app.transport.kafka.events import EventEnvelope


def setup_function():
    clear_and_seed()


def test_protobuf_contract_roundtrip():
    request = pb.GetSalesDataRequest(product_id=PRODUCT_A, period="2026-09-01")
    restored = pb.GetSalesDataRequest.FromString(request.SerializeToString())
    assert restored.product_id == PRODUCT_A
    assert restored.period == "2026-09-01"


def test_real_typed_grpc_reads_domain_data():
    period = date(2026, 9, 1)
    master = MasterDataDomainClient().get_costing_context(PRODUCT_A, period)
    production = ProductionDomainClient().get_cost_data(PRODUCT_A, period)
    overhead = FinancialDomainClient().get_overhead(period)
    sales = FinancialDomainClient().get_sales(PRODUCT_A, period)
    assert master.product_id == PRODUCT_A
    assert production.produced_qty == Decimal("100.0000")
    assert production.labor_hours == Decimal("45.00")
    assert overhead.total_amount == Decimal("1400.00")
    assert sales.revenue == Decimal("6400.00")


def test_costing_command_uses_network_and_publishes_event(grpc_runtime):
    clients = create_grpc_clients()
    rows = clients.costing.calculate_costs_remote(
        date(2026, 9, 1), [PRODUCT_A, PRODUCT_B], "LABOR_HOURS"
    )
    assert len(rows) == 2
    events = grpc_runtime["costing"].events
    assert [e.eventType for e in events[-2:]] == ["CostCalculationCompleted", "CostCalculationCompleted"]
    approved = CostingDomainClient().get_approved_cost(PRODUCT_A, date(2026, 9, 1))
    assert approved.version == 2


def test_analytics_command_uses_costing_and_financial_grpc(grpc_runtime):
    clients = create_grpc_clients()
    clients.costing.calculate_costs_remote(date(2026, 9, 1), [PRODUCT_A], "VOLUME")
    job = clients.analytics.calculate_profitability_remote(date(2026, 9, 1), [PRODUCT_A])
    assert job.status == "COMPLETED"
    detail = ProfitabilityDomainClient().get_detail(PRODUCT_A, date(2026, 9, 1))
    assert detail.revenue == Decimal("6400.00")
    assert grpc_runtime["analytics"].events[-1].eventType == "ProfitabilityCalculated"


def test_event_envelope_json_roundtrip():
    event = EventEnvelope.create(
        "CostCalculationCompleted",
        "costing-service",
        {"productId": PRODUCT_A, "period": "2026-09-01"},
        correlation_id="corr-1",
    )
    restored = EventEnvelope.from_bytes(event.to_bytes())
    assert restored.eventType == "CostCalculationCompleted"
    assert restored.correlationId == "corr-1"
    assert restored.payload["productId"] == PRODUCT_A
