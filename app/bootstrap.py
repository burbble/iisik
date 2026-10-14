from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.services.identity.database import init_db as init_identity_db
from app.services.identity.service import IdentityService
from app.services.master_data.database import init_db as init_master_data_db
from app.services.master_data.service import MasterDataService
from app.services.production.database import init_db as init_production_db
from app.services.production.service import ProductionIntegrationService
from app.services.financial.database import init_db as init_financial_db
from app.services.financial.service import FinancialIntegrationService
from app.services.costing.database import init_db as init_costing_db
from app.services.costing.service import CostingService
from app.services.analytics.database import init_db as init_analytics_db
from app.services.analytics.service import ProfitabilityAnalyticsService
from app.services.reporting.database import init_db as init_reporting_db
from app.services.reporting.service import ReportingService


def init_databases() -> None:
    init_identity_db()
    init_master_data_db()
    init_production_db()
    init_financial_db()
    init_costing_db()
    init_analytics_db()
    init_reporting_db()


@dataclass(frozen=True)
class ServiceContainer:
    identity: IdentityService
    master_data: MasterDataService
    production: ProductionIntegrationService
    financial: FinancialIntegrationService
    costing: CostingService
    analytics: ProfitabilityAnalyticsService
    reporting: ReportingService


@lru_cache(maxsize=1)
def get_container() -> ServiceContainer:
    init_databases()
    return ServiceContainer(
        identity=IdentityService(),
        master_data=MasterDataService(),
        production=ProductionIntegrationService(),
        financial=FinancialIntegrationService(),
        costing=CostingService(),
        analytics=ProfitabilityAnalyticsService(),
        reporting=ReportingService(),
    )
