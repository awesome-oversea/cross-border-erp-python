from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.billing.domain.engine import (
    PACKAGING_COSTS,
    PLATFORM_COMMISSION_RATES,
    WAREHOUSE_FEE_RATES,
    BillingEngine,
    BillingSimulationInput,
)
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.billing")


class BillingService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = BillingEngine()

    async def get_platform_fees(self, platform: str = "") -> list[dict]:
        if platform:
            rates = PLATFORM_COMMISSION_RATES.get(platform)
            if not rates:
                return []
            return [{"platform": platform, "default_rate": rates.get("default", 0),
                      "categories": rates.get("categories", {})}]
        return [{"platform": k, "default_rate": v.get("default", 0), "categories": v.get("categories", {})}
                for k, v in PLATFORM_COMMISSION_RATES.items()]

    async def simulate(self, tenant_id: str, platform: str, sale_price: float, quantity: int = 1,
                        category: str = "", currency: str = "USD", weight_kg: float = 0.0,
                        warehouse_type: str = "fba", shipping_cost: float = 0.0,
                        cost_price: float = 0.0, packaging_type: str = "medium_box") -> dict:
        input_data = BillingSimulationInput(
            platform=platform, category=category, sale_price=sale_price,
            quantity=quantity, currency=currency, weight_kg=weight_kg,
            warehouse_type=warehouse_type, shipping_cost=shipping_cost,
            cost_price=cost_price, packaging_type=packaging_type,
        )
        return self._engine.simulate(input_data)

    async def get_warehouse_fees(self, warehouse_type: str = "") -> list[dict]:
        if warehouse_type:
            rates = WAREHOUSE_FEE_RATES.get(warehouse_type)
            return [{"warehouse_type": warehouse_type, "rates": rates}] if rates else []
        return [{"warehouse_type": k, "rates": v} for k, v in WAREHOUSE_FEE_RATES.items()]

    async def get_freight_pool(self, tenant_id: str) -> list[dict]:
        return [{"route": "CN->US", "provider": "yanwen", "cost_per_kg": 5.0},
                {"route": "CN->GB", "provider": "4px", "cost_per_kg": 4.5},
                {"route": "CN->DE", "provider": "dhl", "cost_per_kg": 15.0}]

    async def allocate_freight(self, tenant_id: str, total_freight: float, items: list[dict]) -> list[dict]:
        return self._engine.calculate_freight_allocate(total_freight, items)

    async def get_packaging_costs(self) -> list[dict]:
        return [{"type": k, "cost": v} for k, v in PACKAGING_COSTS.items()]

    async def calculate_fba_head_cost(self, tenant_id: str, shipment_cost: float, total_units: int,
                                       damaged_units: int = 0, lost_units: int = 0) -> dict:
        return self._engine.calculate_fba_head_cost(shipment_cost, total_units, damaged_units, lost_units)
