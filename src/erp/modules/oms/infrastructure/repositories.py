from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.oms.domain.models import OrderAuditLog, OrderSplitRule, Promotion, RefundOrder, SalesOrder, SalesOrderItem
from erp.modules.oms.domain.repositories import (
    OrderAuditLogRepository,
    OrderSplitRuleRepository,
    PromotionRepository,
    RefundOrderRepository,
    SalesOrderItemRepository,
    SalesOrderRepository,
)


class SqlSalesOrderRepository(SalesOrderRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, order_id: str, tenant_id: str) -> SalesOrder | None:
        stmt = select(SalesOrder).where(SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id, SalesOrder.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_order_no(self, order_no: str, tenant_id: str) -> SalesOrder | None:
        stmt = select(SalesOrder).where(SalesOrder.order_no == order_no, SalesOrder.tenant_id == tenant_id, SalesOrder.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "", platform: str = "", store_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[SalesOrder], int]:
        conditions = [SalesOrder.tenant_id == tenant_id, SalesOrder.deleted_at.is_(None)]
        if status:
            conditions.append(SalesOrder.status == status)
        if platform:
            conditions.append(SalesOrder.platform == platform)
        if store_id:
            conditions.append(SalesOrder.store_id == store_id)
        total = (await self._session.execute(select(func.count()).select_from(SalesOrder).where(*conditions))).scalar() or 0
        stmt = select(SalesOrder).where(*conditions).order_by(SalesOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, order: SalesOrder) -> SalesOrder:
        self._session.add(order)
        await self._session.flush()
        return order

    async def update(self, order: SalesOrder) -> SalesOrder:
        await self._session.flush()
        return order

    async def soft_delete(self, order_id: str, tenant_id: str) -> bool:
        stmt = update(SalesOrder).where(SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlSalesOrderItemRepository(SalesOrderItemRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_order(self, order_id: str, tenant_id: str) -> Sequence[SalesOrderItem]:
        stmt = select(SalesOrderItem).where(SalesOrderItem.order_id == order_id, SalesOrderItem.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, item: SalesOrderItem) -> SalesOrderItem:
        self._session.add(item)
        await self._session.flush()
        return item

    async def update(self, item: SalesOrderItem) -> SalesOrderItem:
        await self._session.flush()
        return item


class SqlRefundOrderRepository(RefundOrderRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, refund_id: str, tenant_id: str) -> RefundOrder | None:
        stmt = select(RefundOrder).where(RefundOrder.id == refund_id, RefundOrder.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_refund_no(self, refund_no: str, tenant_id: str) -> RefundOrder | None:
        stmt = select(RefundOrder).where(RefundOrder.refund_no == refund_no, RefundOrder.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_original_order(self, original_order_id: str, tenant_id: str) -> Sequence[RefundOrder]:
        stmt = select(RefundOrder).where(RefundOrder.original_order_id == original_order_id, RefundOrder.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_tenant(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[RefundOrder], int]:
        conditions = [RefundOrder.tenant_id == tenant_id]
        if status:
            conditions.append(RefundOrder.status == status)
        total = (await self._session.execute(select(func.count()).select_from(RefundOrder).where(*conditions))).scalar() or 0
        stmt = select(RefundOrder).where(*conditions).order_by(RefundOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, refund: RefundOrder) -> RefundOrder:
        self._session.add(refund)
        await self._session.flush()
        return refund

    async def update(self, refund: RefundOrder) -> RefundOrder:
        await self._session.flush()
        return refund


class SqlOrderSplitRuleRepository(OrderSplitRuleRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_tenant(self, tenant_id: str, status: str = "") -> Sequence[OrderSplitRule]:
        conditions = [OrderSplitRule.tenant_id == tenant_id]
        if status:
            conditions.append(OrderSplitRule.status == status)
        stmt = select(OrderSplitRule).where(*conditions).order_by(OrderSplitRule.priority)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, rule: OrderSplitRule) -> OrderSplitRule:
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def update(self, rule: OrderSplitRule) -> OrderSplitRule:
        await self._session.flush()
        return rule


class SqlOrderAuditLogRepository(OrderAuditLogRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, log: OrderAuditLog) -> OrderAuditLog:
        self._session.add(log)
        await self._session.flush()
        return log

    async def list_by_order(self, order_id: str, tenant_id: str) -> Sequence[OrderAuditLog]:
        stmt = select(OrderAuditLog).where(OrderAuditLog.order_id == order_id, OrderAuditLog.tenant_id == tenant_id).order_by(OrderAuditLog.created_at)
        return (await self._session.execute(stmt)).scalars().all()


class SqlPromotionRepository(PromotionRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, promo_id: str, tenant_id: str) -> Promotion | None:
        stmt = select(Promotion).where(
            Promotion.id == promo_id, Promotion.tenant_id == tenant_id, Promotion.deleted_at.is_(None)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_promo_no(self, promo_no: str, tenant_id: str) -> Promotion | None:
        stmt = select(Promotion).where(
            Promotion.promo_no == promo_no, Promotion.tenant_id == tenant_id, Promotion.deleted_at.is_(None)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "", promo_type: str = "",
                             platform: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[Promotion], int]:
        conditions = [Promotion.tenant_id == tenant_id, Promotion.deleted_at.is_(None)]
        if status:
            conditions.append(Promotion.status == status)
        if promo_type:
            conditions.append(Promotion.promo_type == promo_type)
        if platform:
            conditions.append(Promotion.platform == platform)
        total = (await self._session.execute(select(func.count()).select_from(Promotion).where(*conditions))).scalar() or 0
        stmt = select(Promotion).where(*conditions).order_by(Promotion.priority, Promotion.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def list_active_for_discount(self, tenant_id: str, order_amount: float,
                                       platform: str = "", store_id: str = "") -> Sequence[Promotion]:
        conditions = [
            Promotion.tenant_id == tenant_id, Promotion.status == "active",
            Promotion.deleted_at.is_(None), Promotion.min_purchase_amount <= order_amount,
        ]
        if platform:
            conditions.append(Promotion.platform == "")
        if store_id:
            conditions.append(Promotion.store_id == "")
        stmt = select(Promotion).where(*conditions).order_by(Promotion.priority)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, promo: Promotion) -> Promotion:
        self._session.add(promo)
        await self._session.flush()
        return promo

    async def update(self, promo: Promotion) -> Promotion:
        await self._session.flush()
        return promo

    async def soft_delete(self, promo_id: str, tenant_id: str) -> bool:
        stmt = update(Promotion).where(Promotion.id == promo_id, Promotion.tenant_id == tenant_id).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0
