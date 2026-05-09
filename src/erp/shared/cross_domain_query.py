"""
跨域查询服务层 - 替代业务域之间的直接import

设计目的:
  1. 打破DDD跨域直接import禁令
  2. 统一跨域数据访问入口,支持单体/微服务双模切换
  3. 可缓存/可审计/可脱敏

使用规范:
  - 业务域A需要业务域B的数据时,通过本服务查询
  - 禁止: from erp.modules.B.domain.models import Xxx
  - 允许: from erp.shared.cross_domain_query import OrderQueryService
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, func

from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.cross_domain_query")


class OrderQueryService:
    """订单跨域查询 - 被FMS/WMS/DASHBOARD复用"""

    def __init__(self, session: AsyncSession):
        """初始化订单跨域查询服务"""
        self._session = session

    async def get_by_id(self, order_id: str, tenant_id: str) -> dict | None:
        """根据ID和租户查询订单详情"""
        from erp.modules.oms.domain.models import SalesOrder
        stmt = select(SalesOrder).where(SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id,
                                         SalesOrder.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        order = result.scalar_one_or_none()
        if not order:
            return None
        return self._to_dict(order)

    async def list_by_tenant(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> dict:
        """分页查询租户下订单列表"""
        from erp.modules.oms.domain.models import SalesOrder
        conditions = [SalesOrder.tenant_id == tenant_id, SalesOrder.deleted_at.is_(None)]
        if status:
            conditions.append(SalesOrder.status == status)
        count_stmt = select(func.count()).select_from(SalesOrder).where(*conditions)
        total = (await self._session.execute(count_stmt)).scalar() or 0
        stmt = select(SalesOrder).where(*conditions).order_by(SalesOrder.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(stmt)
        items = [self._to_dict(o) for o in result.scalars().all()]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def _to_dict(self, order) -> dict:
        return {"id": order.id, "order_no": order.order_no, "status": order.status,
                "total_amount": float(order.total_amount), "currency": order.currency,
                "platform": order.platform, "store_id": order.store_id,
                "buyer_name": order.buyer_name, "order_time": str(order.order_time or ""),
                "warehouse_id": order.warehouse_id, "tracking_no": order.tracking_no}


class InventoryQueryService:
    """库存跨域查询 - 被OMS/SOM/DASHBOARD复用"""

    def __init__(self, session: AsyncSession):
        """初始化订单跨域查询服务"""
        self._session = session

    async def get_by_sku(self, sku_id: str, tenant_id: str, warehouse_id: str = "") -> dict | None:
        from erp.modules.wms.domain.models import Inventory
        conditions = [Inventory.sku_id == sku_id, Inventory.tenant_id == tenant_id]
        if warehouse_id:
            conditions.append(Inventory.warehouse_id == warehouse_id)
        stmt = select(Inventory).where(*conditions)
        result = await self._session.execute(stmt)
        inv = result.scalar_one_or_none()
        if not inv:
            return None
        return {"sku_id": inv.sku_id, "warehouse_id": inv.warehouse_id,
                "qty_on_hand": inv.qty_on_hand, "qty_reserved": inv.qty_reserved,
                "qty_available": inv.qty_available, "qty_inbound": inv.qty_inbound}

    async def list_low_stock(self, tenant_id: str, threshold: int = 10) -> list[dict]:
        from erp.modules.wms.domain.models import Inventory
        stmt = select(Inventory).where(Inventory.tenant_id == tenant_id,
                                        Inventory.qty_available <= threshold)
        result = await self._session.execute(stmt)
        return [{"sku_id": inv.sku_id, "warehouse_id": inv.warehouse_id,
                 "qty_available": inv.qty_available, "safety_qty": inv.safety_qty}
                for inv in result.scalars().all()]


class ShipmentQueryService:
    """物流跨域查询 - 被OMS/DASHBOARD复用"""

    def __init__(self, session: AsyncSession):
        """初始化订单跨域查询服务"""
        self._session = session

    async def get_by_order(self, order_id: str, tenant_id: str) -> list[dict]:
        from erp.modules.tms.domain.models import Shipment
        stmt = select(Shipment).where(Shipment.tenant_id == tenant_id,
                                       Shipment.source_order_id == order_id)
        result = await self._session.execute(stmt)
        return [{"id": s.id, "tracking_no": s.tracking_no, "carrier": s.carrier,
                 "status": s.status, "estimated_delivery": str(s.estimated_delivery_date or "")}
                for s in result.scalars().all()]


class FinanceQueryService:
    """财务跨域查询 - 被DASHBOARD/BI复用"""

    def __init__(self, session: AsyncSession):
        """初始化订单跨域查询服务"""
        self._session = session

    async def get_cost_events(self, tenant_id: str, order_id: str = "") -> list[dict]:
        from erp.modules.fms.domain.models import CostEvent
        conditions = [CostEvent.tenant_id == tenant_id]
        if order_id:
            conditions.append(CostEvent.order_id == order_id)
        stmt = select(CostEvent).where(*conditions).order_by(CostEvent.occurred_date)
        result = await self._session.execute(stmt)
        return [{"id": e.id, "cost_type": e.cost_type, "amount": float(e.amount),
                 "currency": e.currency, "order_id": e.order_id, "sku_id": e.sku_id}
                for e in result.scalars().all()]
