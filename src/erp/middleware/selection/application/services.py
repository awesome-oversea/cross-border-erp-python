from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.selection.domain.engine import MarketAnalysisInput, ProfitSimulationInput, SelectionEngine
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.selection")


class SelectionService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = SelectionEngine()

    async def market_analysis(self, tenant_id: str, category: str, marketplace: str = "amazon_us",
                               keywords: list[str] | None = None) -> dict:
        return self._engine.analyze_market(MarketAnalysisInput(
            category=category, marketplace=marketplace, keywords=keywords or []))

    async def competitor_analysis(self, tenant_id: str, category: str, marketplace: str = "amazon_us") -> dict:
        return self._engine.analyze_competitors(category, marketplace)

    async def profit_simulation(self, tenant_id: str, sale_price: float, cost_price: float,
                                 shipping_cost: float = 0.0, commission_rate: float = 0.15,
                                 vat_rate: float = 0.0, advertising_cost: float = 0.0,
                                 other_costs: float = 0.0, currency: str = "USD",
                                 monthly_sales_estimate: int = 100) -> dict:
        return self._engine.simulate_profit(ProfitSimulationInput(
            sale_price=sale_price, cost_price=cost_price, shipping_cost=shipping_cost,
            commission_rate=commission_rate, vat_rate=vat_rate,
            advertising_cost=advertising_cost, other_costs=other_costs,
            currency=currency, monthly_sales_estimate=monthly_sales_estimate))
