from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.profit_engine.domain.engine import ProfitCalculationInput, ProfitEngine
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.profit_engine")


class ProfitEngineService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = ProfitEngine()

    async def calculate(self, tenant_id: str, revenue: float, purchase_cost: float = 0.0,
                         head_freight: float = 0.0, warehouse_fee: float = 0.0,
                         platform_commission: float = 0.0, advertising_cost: float = 0.0,
                         payment_fee: float = 0.0, last_mile_cost: float = 0.0,
                         other_costs: float = 0.0, vat_amount: float = 0.0,
                         currency: str = "USD", quantity: int = 1) -> dict:
        result = self._engine.calculate(ProfitCalculationInput(
            revenue=revenue, purchase_cost=purchase_cost, head_freight=head_freight,
            warehouse_fee=warehouse_fee, platform_commission=platform_commission,
            advertising_cost=advertising_cost, payment_fee=payment_fee,
            last_mile_cost=last_mile_cost, other_costs=other_costs,
            vat_amount=vat_amount, currency=currency, quantity=quantity,
        ))
        return {"gross_profit": result.gross_profit, "gross_margin_pct": result.gross_margin_pct,
                "operating_profit": result.operating_profit, "operating_margin_pct": result.operating_margin_pct,
                "net_profit": result.net_profit, "net_margin_pct": result.net_margin_pct,
                "cost_breakdown": result.cost_breakdown, "currency": result.currency}

    async def calculate_settlement(self, tenant_id: str, order_amount: float, platform: str = "amazon",
                                    cost_price: float = 0.0, shipping_fee: float = 0.0,
                                    commission_rate: float = 0.15, vat_rate: float = 0.0,
                                    advertising_share: float = 0.0) -> dict:
        return self._engine.calculate_settlement(
            order_amount, platform, cost_price, shipping_fee, commission_rate, vat_rate, advertising_share)

    async def aggregate_by_period(self, tenant_id: str, records: list[dict], period_key: str = "month") -> dict:
        return self._engine.aggregate_by_period(records, period_key)
