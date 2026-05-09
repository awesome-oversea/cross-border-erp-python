from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from erp.modules.fms.domain.models import CostEvent

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession


class CostType:
    PURCHASE = "purchase"
    LOGISTICS = "logistics"
    WAREHOUSE = "warehouse"
    PLATFORM_FEE = "platform_fee"
    ADVERTISING = "advertising"
    PACKING = "packing"
    RETURN = "return"
    OTHER = "other"


class CostAggregationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_cost(self, tenant_id: str, cost_type: str, amount: float,
                          currency: str = "CNY", exchange_rate: float = 1.0,
                          source_type: str = "", source_id: str = "",
                          order_id: str = "", sku_id: str = "",
                          store_id: str = "", shipment_id: str = "",
                          reference_type: str = "", reference_id: str = "",
                          occurred_date: datetime | None = None) -> CostEvent:
        amount_cny = amount * exchange_rate
        event = CostEvent(
            tenant_id=tenant_id, cost_type=cost_type,
            amount=amount, currency=currency, exchange_rate=exchange_rate,
            amount_cny=amount_cny, sku_id=sku_id, order_id=order_id,
            shipment_id=shipment_id, reference_type=reference_type or source_type,
            reference_id=reference_id or source_id,
            occurred_date=occurred_date,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_order_costs(self, tenant_id: str, order_id: str) -> list[CostEvent]:
        stmt = select(CostEvent).where(
            CostEvent.tenant_id == tenant_id,
            CostEvent.order_id == order_id,
        ).order_by(CostEvent.cost_type, CostEvent.occurred_date)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_sku_costs(self, tenant_id: str, sku_id: str,
                            start_date: datetime | None = None,
                            end_date: datetime | None = None) -> list[CostEvent]:
        stmt = select(CostEvent).where(
            CostEvent.tenant_id == tenant_id,
            CostEvent.sku_id == sku_id,
        )
        if start_date:
            stmt = stmt.where(CostEvent.occurred_date >= start_date)
        if end_date:
            stmt = stmt.where(CostEvent.occurred_date <= end_date)
        stmt = stmt.order_by(CostEvent.occurred_date.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def aggregate_order_cost(self, tenant_id: str, order_id: str) -> dict:
        events = await self.get_order_costs(tenant_id, order_id)
        total = 0.0
        by_type: dict[str, float] = {}
        for e in events:
            total += e.amount_cny or 0
            by_type[e.cost_type] = by_type.get(e.cost_type, 0) + (e.amount_cny or 0)
        return {
            "order_id": order_id,
            "total_cost_cny": round(total, 6),
            "cost_by_type": {k: round(v, 6) for k, v in by_type.items()},
            "event_count": len(events),
        }

    async def aggregate_sku_cost(self, tenant_id: str, sku_id: str,
                                  start_date: datetime | None = None,
                                  end_date: datetime | None = None) -> dict:
        events = await self.get_sku_costs(tenant_id, sku_id, start_date, end_date)
        total = 0.0
        by_type: dict[str, float] = {}
        for e in events:
            total += e.amount_cny or 0
            by_type[e.cost_type] = by_type.get(e.cost_type, 0) + (e.amount_cny or 0)
        return {
            "sku_id": sku_id,
            "total_cost_cny": round(total, 6),
            "cost_by_type": {k: round(v, 6) for k, v in by_type.items()},
            "event_count": len(events),
        }
