from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.cost_engine.domain.engine import CostAggregationEngine, CostEvent
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.cost_engine")


class CostEngineService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = CostAggregationEngine()

    async def collect_events(self, tenant_id: str, events: list[dict]) -> dict:
        cost_events = [CostEvent(**{k: v for k, v in e.items() if k in CostEvent.__dataclass_fields__}) for e in events]
        return self._engine.collect_events(cost_events)

    async def query_events(self, tenant_id: str, sku_id: str = "", cost_type: str = "",
                            start_date: str = "", end_date: str = "") -> list[dict]:
        return []

    async def generate_breakdown(self, tenant_id: str, sku_id: str, events: list[dict], period: str = "") -> dict:
        cost_events = [CostEvent(**{k: v for k, v in e.items() if k in CostEvent.__dataclass_fields__}) for e in events]
        breakdown = self._engine.generate_breakdown(sku_id, cost_events, period)
        return {"sku_id": breakdown.sku_id, "period": breakdown.period,
                "costs": breakdown.costs, "total": breakdown.total, "currency": breakdown.currency}

    async def allocate(self, tenant_id: str, shared_cost: float, sku_weights: dict[str, float]) -> dict:
        result = self._engine.allocate_shared_costs(shared_cost, sku_weights)
        return {"shared_cost": shared_cost, "allocations": result}

    async def calculate_fifo(self, tenant_id: str, layers: list[dict], quantity: int) -> dict:
        return self._engine.calculate_fifo_cost(layers, quantity)

    async def get_trend(self, tenant_id: str, sku_id: str = "", period_type: str = "monthly",
                         months: int = 6) -> dict:
        return {"sku_id": sku_id, "period_type": period_type, "trend": []}

    async def detect_anomaly(self, tenant_id: str, events: list[dict], threshold_pct: float = 50.0) -> dict:
        cost_events = [CostEvent(**{k: v for k, v in e.items() if k in CostEvent.__dataclass_fields__}) for e in events]
        anomalies = self._engine.detect_anomaly(cost_events, threshold_pct)
        return {"anomaly_count": len(anomalies), "anomalies": anomalies}
