from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.logistics_strategy.domain.engine import LogisticsStrategyEngine, ShipmentEstimateContext
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.logistics_strategy")


class LogisticsStrategyService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = LogisticsStrategyEngine()

    async def select_provider(self, tenant_id: str, origin_country: str, destination_country: str,
                               weight_kg: float, declared_value: float = 0.0, currency: str = "USD",
                               service_level: str = "standard", priority: str = "balanced") -> dict:
        context = ShipmentEstimateContext(
            origin_country=origin_country, destination_country=destination_country,
            weight_kg=weight_kg, declared_value=declared_value,
            currency=currency, service_level=service_level,
        )
        options = self._engine.select_provider(context, priority)
        return {
            "origin": origin_country, "destination": destination_country,
            "weight_kg": weight_kg, "priority": priority,
            "options": [{"provider_id": o.provider_id, "provider_name": o.provider_name,
                         "estimated_days": o.estimated_days, "cost": o.cost,
                         "currency": o.currency, "score": round(o.score, 4)} for o in options],
            "recommended": {"provider_id": options[0].provider_id, "cost": options[0].cost} if options else None,
        }

    async def calculate_rate(self, tenant_id: str, origin_country: str, destination_country: str,
                              weight_kg: float, provider_id: str, currency: str = "USD") -> dict:
        context = ShipmentEstimateContext(
            origin_country=origin_country, destination_country=destination_country,
            weight_kg=weight_kg, currency=currency,
        )
        option = self._engine.calculate_rate(context, provider_id)
        if not option:
            return {"error": f"Provider '{provider_id}' not available for {origin_country}->{destination_country}"}
        return {"provider_id": option.provider_id, "provider_name": option.provider_name,
                "estimated_days": option.estimated_days, "cost": option.cost, "currency": option.currency}

    async def get_rules(self, tenant_id: str) -> list[dict]:
        return [{"rule_id": "default", "rule_name": "Default Logistics Strategy", "priority": "balanced"}]
