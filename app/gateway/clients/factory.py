from dataclasses import dataclass

from .interfaces import (
    AnalyticsClient,
    CostingClient,
    FinancialClient,
    MasterDataClient,
    ProductionClient,
    ReportingClient,
)
from .grpc_clients import (
    GrpcAnalyticsClient,
    GrpcCostingClient,
    GrpcFinancialClient,
    GrpcMasterDataClient,
    GrpcProductionClient,
    GrpcReportingClient,
)


@dataclass(frozen=True)
class ClientBundle:
    master_data: MasterDataClient
    production: ProductionClient
    financial: FinancialClient
    costing: CostingClient
    analytics: AnalyticsClient
    reporting: ReportingClient


def create_grpc_clients() -> ClientBundle:
    return ClientBundle(
        master_data=GrpcMasterDataClient(),
        production=GrpcProductionClient(),
        financial=GrpcFinancialClient(),
        costing=GrpcCostingClient(),
        analytics=GrpcAnalyticsClient(),
        reporting=GrpcReportingClient(),
    )
