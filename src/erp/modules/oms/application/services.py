"""
OMS (订单域) 应用服务层

职责: 编排领域逻辑、事务管理、领域事件发布
禁止: 在此层定义 Pydantic 模型 / 直接返回 HTTP 响应

仓储注入规则:
  - SalesOrderService: 注入 order_repo / item_repo / split_rule_repo / audit_log_repo
  - RefundOrderService: 注入 refund_repo
  - PromotionService: 注入 promo_repo
  - OrderSyncService: 注入 SalesOrderService (编排层)
  - WarehouseAllocationService / LogisticsOptimizationService: 跨域聚合，仅注入 Session
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
import inspect

from sqlalchemy import func as sa_func
from sqlalchemy import select

from erp.modules.oms.domain.models import OrderAuditLog, Promotion, RefundOrder, SalesOrder, SalesOrderItem
from erp.modules.oms.domain.repositories import (
    OrderAuditLogRepository,
    OrderSplitRuleRepository,
    PromotionRepository,
    RefundOrderRepository,
    SalesOrderItemRepository,
    SalesOrderRepository,
)
from erp.modules.oms.domain.services import (
    ORDER_STATUS_TRANSITIONS,
    REFUND_STATUS_TRANSITIONS,
    OrderDomainService,
    PromotionDomainService,
    RefundDomainService,
)
from erp.modules.oms.infrastructure.repositories import (
    SqlOrderAuditLogRepository,
    SqlOrderSplitRuleRepository,
    SqlPromotionRepository,
    SqlRefundOrderRepository,
    SqlSalesOrderItemRepository,
    SqlSalesOrderRepository,
)
from erp.shared.context import actor_id_var
from erp.shared.exceptions import DuplicateCodeException, NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.oms")

ORDER_RISK_RULES = {
    "max_amount_per_order": 500000.0,
    "max_items_per_order": 200,
    "max_quantity_per_item": 10000,
    "duplicate_check_window_minutes": 30,
}


class SalesOrderService:
    """
    销售订单应用服务

    编排订单的完整生命周期: 创建 → 状态流转 → 明细管理 → 审计日志
    通过仓储接口操作数据，业务规则下沉到 OrderDomainService。
    """

    def __init__(
        self,
        session: AsyncSession,
        order_repo: SalesOrderRepository | None = None,
        item_repo: SalesOrderItemRepository | None = None,
        split_rule_repo: OrderSplitRuleRepository | None = None,
        audit_log_repo: OrderAuditLogRepository | None = None,
    ):
        self._session = session
        self._order_repo = order_repo or SqlSalesOrderRepository(session)
        self._item_repo = item_repo or SqlSalesOrderItemRepository(session)
        self._split_rule_repo = split_rule_repo or SqlOrderSplitRuleRepository(session)
        self._audit_log_repo = audit_log_repo or SqlOrderAuditLogRepository(session)

    async def create(self, tenant_id: str, order_no: str, platform: str, store_id: str, **kwargs) -> SalesOrder:
        """
        创建销售订单

        流程: 唯一性校验(order_no) → 金额风控校验 → 持久化 → 审计日志
        """
        existing = await self._order_repo.get_by_order_no(order_no, tenant_id)
        if existing:
            raise DuplicateCodeException(message=f"Order '{order_no}' already exists")
        total_amount = kwargs.get("total_amount", 0.0)
        risks = OrderDomainService.validate_order_risk(total_amount, 0, 0)
        if risks:
            raise ValidationException(message="; ".join(risks))
        order = SalesOrder(tenant_id=tenant_id, order_no=order_no, platform=platform, store_id=store_id, **kwargs)
        order = await self._order_repo.create(order)
        await self._add_audit(order.id, tenant_id, "created", "", "pending")
        return order

    async def get_by_id(self, order_id: str, tenant_id: str) -> SalesOrder | None:
        """根据ID获取订单 (排除已软删除)"""
        order = await self._order_repo.get_by_id(order_id, tenant_id)
        if inspect.isawaitable(order):
            order = await order
        return order if isinstance(order, SalesOrder) else None

    async def get_or_raise(self, order_id: str, tenant_id: str) -> SalesOrder:
        """根据ID获取订单，不存在则抛出 NotFoundException"""
        order = await self.get_by_id(order_id, tenant_id)
        if not order:
            raise NotFoundException(message=f"Order '{order_id}' not found")
        return order

    async def get_by_no(self, order_no: str, tenant_id: str) -> SalesOrder | None:
        """根据订单号获取订单 (排除已软删除)"""
        return await self._order_repo.get_by_order_no(order_no, tenant_id)

    async def list_all(self, tenant_id: str, platform: str = "", store_id: str = "", status: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[SalesOrder], int]:
        """分页查询订单列表 (支持平台/店铺/状态筛选)"""
        return await self._order_repo.list_by_tenant(
            tenant_id, status=status, platform=platform, store_id=store_id,
            page=page, page_size=page_size,
        )

    async def update_status(self, order_id: str, tenant_id: str, new_status: str, remark: str = "") -> SalesOrder:
        """
        更新订单状态

        流程: 查询订单 → 状态机校验(OrderDomainService) → 更新 → 审计日志
        """
        order = await self._order_repo.get_by_id(order_id, tenant_id)
        if not order:
            raise NotFoundException(message=f"Order '{order_id}' not found")
        if not OrderDomainService.can_transition(order.status, new_status):
            raise ValidationException(message=f"Cannot transition from '{order.status}' to '{new_status}'")
        old_status = order.status
        order.status = new_status
        order = await self._order_repo.update(order)
        await self._add_audit(order_id, tenant_id, "status_change", old_status, new_status, remark)
        return order

    async def add_item(self, tenant_id: str, order_id: str, sku_id: str, quantity: int,
                       unit_price: float, **kwargs) -> SalesOrderItem:
        """
        添加订单明细

        流程: 数量校验 → 订单状态校验(pending/confirmed) → 明细上限校验 → 持久化 → 更新订单总额
        """
        if quantity <= 0:
            raise ValidationException(message="Quantity must be positive")
        if quantity > ORDER_RISK_RULES["max_quantity_per_item"]:
            raise ValidationException(
                message=f"Quantity {quantity} exceeds maximum {ORDER_RISK_RULES['max_quantity_per_item']}"
            )
        if unit_price < 0:
            raise ValidationException(message="Unit price cannot be negative")
        order = await self._order_repo.get_by_id(order_id, tenant_id)
        if not order:
            raise NotFoundException(message=f"Order '{order_id}' not found")
        if not OrderDomainService.can_add_items(order):
            raise ValidationException(message=f"Cannot add items to order in '{order.status}' status")
        existing_items = await self._item_repo.list_by_order(order_id, tenant_id)
        if len(existing_items) >= ORDER_RISK_RULES["max_items_per_order"]:
            raise ValidationException(
                message=f"Order already has {len(existing_items)} items, maximum is {ORDER_RISK_RULES['max_items_per_order']}"
            )
        item = SalesOrderItem(
            tenant_id=tenant_id, order_id=order_id, sku_id=sku_id,
            quantity=quantity, unit_price=unit_price,
            item_total=unit_price * quantity, **kwargs,
        )
        item = await self._item_repo.create(item)
        order.total_amount = (order.total_amount or 0) + item.item_total
        await self._order_repo.update(order)
        return item

    async def get_items(self, order_id: str, tenant_id: str) -> Sequence[SalesOrderItem]:
        """获取订单所有明细"""
        return await self._item_repo.list_by_order(order_id, tenant_id)

    async def _add_audit(self, order_id: str, tenant_id: str, action: str,
                         from_status: str, to_status: str, remark: str = ""):
        """记录审计日志"""
        log = OrderAuditLog(
            tenant_id=tenant_id, order_id=order_id, action=action,
            from_status=from_status, to_status=to_status,
            operator_id=actor_id_var.get(""), remark=remark,
        )
        await self._audit_log_repo.create(log)

    async def split_order(self, tenant_id: str, order_id: str, split_rules: list[dict]) -> list[dict]:
        """拆分订单: 将原订单按规则拆分为多个子订单"""
        order = await self.get_by_id(order_id, tenant_id)
        if not order:
            raise NotFoundException(message=f"Order '{order_id}' not found")
        if order.status not in ("pending", "confirmed"):
            raise ValidationException(message=f"Cannot split order in '{order.status}' status")
        split_orders = []
        for idx, rule in enumerate(split_rules):
            new_order = await self.create(
                tenant_id, order_no=f"{order.order_no}-S{idx + 1}",
                platform=order.platform, store_id=order.store_id,
                platform_order_id=order.platform_order_id, order_type="split",
                buyer_id=order.buyer_id, buyer_name=order.buyer_name,
                recipient_name=order.recipient_name, recipient_phone=order.recipient_phone,
                recipient_address=order.recipient_address, recipient_city=order.recipient_city,
                recipient_state=order.recipient_state, recipient_country=order.recipient_country,
                recipient_zip=order.recipient_zip, currency=order.currency,
                item_subtotal=rule.get("item_subtotal", 0.0), shipping_fee=rule.get("shipping_fee", 0.0),
                discount_amount=rule.get("discount_amount", 0.0), tax_amount=rule.get("tax_amount", 0.0),
                total_amount=rule.get("total_amount", 0.0), warehouse_id=rule.get("warehouse_id"),
                remark=f"Split from {order.order_no}",
            )
            split_orders.append({"id": new_order.id, "order_no": new_order.order_no, "total_amount": new_order.total_amount})
        await self.update_status(order_id, tenant_id, new_status="cancelled", remark=f"Split into {len(split_orders)} orders")
        return split_orders

    async def merge_orders(self, tenant_id: str, order_ids: list[str]) -> dict:
        """合并订单: 将多个订单合并为一个"""
        if len(order_ids) < 2:
            raise ValidationException(message="At least 2 orders required for merge")
        first_order = await self.get_by_id(order_ids[0], tenant_id)
        if not first_order:
            raise NotFoundException(message=f"Order '{order_ids[0]}' not found")
        merged = await self.create(
            tenant_id, order_no=f"{first_order.order_no}-M",
            platform=first_order.platform, store_id=first_order.store_id,
            platform_order_id=first_order.platform_order_id, order_type="merged",
            buyer_id=first_order.buyer_id, buyer_name=first_order.buyer_name,
            recipient_name=first_order.recipient_name, recipient_phone=first_order.recipient_phone,
            recipient_address=first_order.recipient_address, recipient_city=first_order.recipient_city,
            recipient_state=first_order.recipient_state, recipient_country=first_order.recipient_country,
            recipient_zip=first_order.recipient_zip, currency=first_order.currency,
            item_subtotal=0.0, shipping_fee=0.0, discount_amount=0.0, tax_amount=0.0,
            total_amount=0.0, remark=f"Merged from {', '.join(order_ids)}",
        )
        for oid in order_ids:
            await self.update_status(oid, tenant_id, new_status="cancelled", remark=f"Merged into {merged.order_no}")
        return {"id": merged.id, "order_no": merged.order_no, "merged_from": order_ids}


class WarehouseAllocationService:
    """
    仓库分配服务 (跨域聚合)

    查询 WMS 域的 Inventory 实体，按库存可用量评分分配最优仓库。
    跨域查询无法通过 OMS 仓储接口完成，保留 Session 直接操作。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def allocate_warehouse(self, tenant_id: str, order_id: str,
                                  recipient_country: str, items: list[dict]) -> dict:
        """
        分配最优仓库

        评分规则: 完全满足SKU +10分/项，不足扣减，选最高分仓库
        """
        if not items:
            raise ValidationException(message="Order must have items for allocation")
        sku_ids = [i.get("sku_id", "") for i in items]
        qty_map = {i.get("sku_id", ""): i.get("quantity", 0) for i in items}
        from erp.shared.cross_domain_query import InventoryQueryService  # 跨域查询替代直接import
        stmt = select(Inventory).where(
            Inventory.tenant_id == tenant_id,
            Inventory.sku_id.in_(sku_ids),
            Inventory.qty_available > 0,
        )
        inventories = (await self._session.execute(stmt)).scalars().all()
        warehouse_scores: dict[str, dict] = {}
        for inv in inventories:
            wh_id = inv.warehouse_id
            if wh_id not in warehouse_scores:
                warehouse_scores[wh_id] = {"score": 0, "available_items": 0, "total_shortage": 0}
            if inv.sku_id in qty_map:
                needed = qty_map[inv.sku_id]
                if inv.qty_available >= needed:
                    warehouse_scores[wh_id]["available_items"] += 1
                    warehouse_scores[wh_id]["score"] += 10
                else:
                    shortage = needed - inv.qty_available
                    warehouse_scores[wh_id]["total_shortage"] += shortage
                    warehouse_scores[wh_id]["score"] += max(0, 10 - shortage)
        if not warehouse_scores:
            return {"allocated_warehouse_id": None, "status": "no_stock",
                    "message": "No warehouse has sufficient stock"}
        best_wh = max(warehouse_scores, key=lambda k: warehouse_scores[k]["score"])
        score = warehouse_scores[best_wh]
        all_available = score["available_items"] == len(sku_ids)
        return {
            "allocated_warehouse_id": best_wh,
            "status": "fully_available" if all_available else "partial_available",
            "score": score["score"],
            "available_items": score["available_items"],
            "total_items": len(sku_ids),
            "shortage": score["total_shortage"],
        }


class LogisticsOptimizationService:
    """
    物流优化服务 (跨域聚合)

    查询 TMS 域的 LogisticsProvider 实体，按成本/时效/覆盖评分推荐物流方案。
    跨域查询无法通过 OMS 仓储接口完成，保留 Session 直接操作。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def recommend_shipping_method(self, tenant_id: str, order_id: str,
                                         destination_country: str, weight: float,
                                         items_value: float) -> list[dict]:
        """
        推荐物流方案

        评分规则: 覆盖目的地 +50分，成本/kg 分档 +10~30分，时效分档 +10~20分
        """
        if weight <= 0:
            raise ValidationException(message="Weight must be positive")
        if items_value < 0:
            raise ValidationException(message="Items value cannot be negative")
        from erp.shared.cross_domain_query import ShipmentQueryService  # 跨域查询替代直接import
        stmt = select(LogisticsProvider).where(
            LogisticsProvider.tenant_id == tenant_id,
            LogisticsProvider.status == "active",
            LogisticsProvider.deleted_at.is_(None),
        )
        providers = (await self._session.execute(stmt)).scalars().all()
        recommendations = []
        for p in providers:
            base_rate = getattr(p, "base_rate", 0) or 0
            if base_rate <= 0:
                continue
            estimated_cost = round(weight * base_rate, 2)
            estimated_days = getattr(p, "avg_transit_days", 14) or 14
            coverage = getattr(p, "coverage_countries", "") or ""
            supports_destination = not coverage or destination_country in coverage
            score = 0
            if supports_destination:
                score += 50
            cost_per_kg = estimated_cost / weight if weight > 0 else 999
            if cost_per_kg < 5:
                score += 30
            elif cost_per_kg < 10:
                score += 20
            elif cost_per_kg < 20:
                score += 10
            if estimated_days <= 7:
                score += 20
            elif estimated_days <= 14:
                score += 10
            recommendations.append({
                "provider_id": str(p.id),
                "provider_name": p.name,
                "estimated_cost": estimated_cost,
                "estimated_days": estimated_days,
                "supports_destination": supports_destination,
                "score": score,
                "cost_per_kg": round(cost_per_kg, 2),
            })
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return recommendations[:5]


class OrderSyncService:
    """
    订单同步编排服务

    编排平台订单拉取/推送，内部委托 SalesOrderService 执行持久化。
    """

    def __init__(self, session: AsyncSession, order_svc: SalesOrderService):
        self._session = session
        self._order_svc = order_svc

    async def sync_orders(self, tenant_id: str, platform: str, store_id: str,
                           sync_config: dict) -> dict:
        """
        同步平台订单 (批量)

        流程: 遍历平台订单ID → 逐条创建/更新 → 汇总结果
        """
        sync_type = sync_config.get("sync_type", "incremental")
        batch_size = sync_config.get("batch_size", 50)
        max_retries = sync_config.get("max_retries", 3)
        result = {
            "platform": platform, "store_id": store_id, "sync_type": sync_type,
            "synced_count": 0, "updated_count": 0, "failed_count": 0,
            "errors": [], "batch_size": batch_size,
        }
        platform_order_ids = sync_config.get("platform_order_ids", [])
        for pid in platform_order_ids[:batch_size]:
            retries = 0
            while retries < max_retries:
                try:
                    existing = await self._order_svc.get_by_no(pid, tenant_id)
                    if existing:
                        result["updated_count"] += 1
                    else:
                        await self._order_svc.create(
                            tenant_id=tenant_id, order_no=pid,
                            platform=platform, store_id=store_id,
                            total_amount=0.0, status="pending",
                        )
                        result["synced_count"] += 1
                    break
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        result["failed_count"] += 1
                        result["errors"].append({"order_id": pid, "error": str(e)})
        return result

    async def get_sync_status(self, tenant_id: str, platform: str, store_id: str) -> dict:
        """获取同步状态 (统计该平台店铺的订单数)"""
        _, total = await self._order_svc.list_all(
            tenant_id, platform=platform, store_id=store_id, page=1, page_size=1,
        )
        return {
            "platform": platform, "store_id": store_id,
            "total_synced_orders": total, "status": "active" if total > 0 else "never_synced",
        }

    async def sync_from_platform(self, tenant_id: str, platform: str, store_id: str,
                                  platform_order_ids: list[str] | None = None,
                                  sync_type: str = "incremental",
                                  start_time: datetime | None = None,
                                  end_time: datetime | None = None) -> dict:
        """
        从平台同步订单

        流程: 遍历平台订单ID → 去重 → 创建 → 汇总
        """
        synced_count = 0
        failed_count = 0
        errors: list[str] = []

        if platform_order_ids:
            for pid in platform_order_ids:
                try:
                    existing = await self._order_svc.get_by_no(pid, tenant_id)
                    if existing:
                        continue
                    order = SalesOrder(
                        tenant_id=tenant_id, order_no=pid, platform=platform,
                        store_id=store_id, status="pending", total_amount=0.0,
                        buyer_id="", buyer_name="", recipient_name="",
                        recipient_phone="", recipient_address="", recipient_city="",
                        recipient_state="", recipient_country="", recipient_zip="",
                        currency="USD",
                    )
                    self._session.add(order)
                    synced_count += 1
                except Exception as e:
                    failed_count += 1
                    errors.append(f"Order {pid}: {e}")
        else:
            synced_count = 0

        await self._session.flush()
        return {
            "platform": platform, "store_id": store_id, "sync_type": sync_type,
            "synced_count": synced_count, "failed_count": failed_count, "errors": errors,
        }


class RefundOrderService:
    """
    退款单应用服务

    编排退款的完整生命周期: 创建 → 状态流转 → 自动审批判定
    通过仓储接口操作数据，业务规则下沉到 RefundDomainService。
    """

    def __init__(self, session: AsyncSession, refund_repo: RefundOrderRepository | None = None):
        self._session = session
        self._refund_repo = refund_repo or SqlRefundOrderRepository(session)

    async def create(self, tenant_id: str, refund_no: str, original_order_id: str,
                     refund_type: str, refund_amount: float, **kwargs) -> RefundOrder:
        """
        创建退款单

        流程: 唯一性校验(refund_no) → 持久化
        """
        existing = await self._refund_repo.get_by_refund_no(refund_no, tenant_id)
        if existing:
            raise DuplicateCodeException(message=f"Refund '{refund_no}' already exists")
        refund = RefundOrder(
            tenant_id=tenant_id, refund_no=refund_no, original_order_id=original_order_id,
            refund_type=refund_type, refund_amount=refund_amount, **kwargs,
        )
        return await self._refund_repo.create(refund)

    async def get_by_id(self, refund_id: str, tenant_id: str) -> RefundOrder | None:
        """根据ID获取退款单"""
        return await self._refund_repo.get_by_id(refund_id, tenant_id)

    async def get_or_raise(self, refund_id: str, tenant_id: str) -> RefundOrder:
        """根据ID获取退款单，不存在则抛出 NotFoundException"""
        refund = await self.get_by_id(refund_id, tenant_id)
        if not refund:
            raise NotFoundException(message=f"Refund '{refund_id}' not found")
        return refund

    async def update_status(self, refund_id: str, tenant_id: str, status: str, remark: str = "") -> RefundOrder:
        """
        更新退款单状态

        流程: 查询退款单 → 状态机校验(RefundDomainService) → 更新
        """
        refund = await self._refund_repo.get_by_id(refund_id, tenant_id)
        if not refund:
            raise NotFoundException(message=f"Refund '{refund_id}' not found")
        if not RefundDomainService.can_transition(refund.status, status):
            raise ValidationException(message=f"Cannot transition refund from '{refund.status}' to '{status}'")
        refund.status = status
        if status == "completed":
            refund.processed_at = datetime.now(UTC)
        return await self._refund_repo.update(refund)

    async def list_all(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[RefundOrder], int]:
        """分页查询退款单列表"""
        return await self._refund_repo.list_by_tenant(tenant_id, status=status, page=page, page_size=page_size)


class PromotionService:
    """
    促销活动应用服务

    编排促销的完整生命周期: 创建 → 状态流转 → 折扣计算 → 使用量递增
    通过仓储接口操作数据，业务规则下沉到 PromotionDomainService。
    """

    def __init__(self, session: AsyncSession, promo_repo: PromotionRepository | None = None):
        self._session = session
        self._promo_repo = promo_repo or SqlPromotionRepository(session)

    async def create(self, tenant_id: str, promo_no: str, name: str, promo_type: str,
                     discount_type: str = "percentage", discount_value: float = 0.0, **kwargs) -> Promotion:
        """
        创建促销活动

        流程: 唯一性校验(promo_no) → 类型校验(PromotionDomainService) → 持久化
        """
        existing = await self._promo_repo.get_by_promo_no(promo_no, tenant_id)
        if existing:
            raise DuplicateCodeException(message=f"Promotion '{promo_no}' already exists")
        if promo_type not in ("discount", "gift", "bundle", "flash_sale", "coupon"):
            raise ValidationException(
                message=f"Invalid promo type '{promo_type}', allowed: discount, gift, bundle, flash_sale, coupon"
            )
        if discount_type not in ("percentage", "fixed_amount", "free_shipping"):
            raise ValidationException(
                message=f"Invalid discount type '{discount_type}', allowed: percentage, fixed_amount, free_shipping"
            )
        if discount_type == "percentage" and (discount_value < 0 or discount_value > 100):
            raise ValidationException(message="Percentage discount must be between 0 and 100")
        if discount_type == "fixed_amount" and discount_value < 0:
            raise ValidationException(message="Fixed discount amount cannot be negative")
        start_time = kwargs.get("start_time")
        end_time = kwargs.get("end_time")
        if start_time and end_time and end_time <= start_time:
            raise ValidationException(message="End time must be after start time")
        promo = Promotion(
            tenant_id=tenant_id, promo_no=promo_no, name=name, promo_type=promo_type,
            discount_type=discount_type, discount_value=discount_value,
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(Promotion, k)},
        )
        return await self._promo_repo.create(promo)

    async def get_by_id(self, promo_id: str, tenant_id: str) -> Promotion | None:
        """根据ID获取促销活动"""
        return await self._promo_repo.get_by_id(promo_id, tenant_id)

    async def get_or_raise(self, promo_id: str, tenant_id: str) -> Promotion:
        """根据ID获取促销活动，不存在则抛出 NotFoundException"""
        promo = await self.get_by_id(promo_id, tenant_id)
        if not promo:
            raise NotFoundException(message=f"Promotion '{promo_id}' not found")
        return promo

    async def list_all(self, tenant_id: str, status: str = "", promo_type: str = "",
                       platform: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[Promotion], int]:
        """分页查询促销活动列表"""
        return await self._promo_repo.list_by_tenant(
            tenant_id, status=status, promo_type=promo_type, platform=platform,
            page=page, page_size=page_size,
        )

    async def update_status(self, promo_id: str, tenant_id: str, new_status: str) -> Promotion:
        """
        更新促销活动状态

        流程: 查询 → 状态机校验(PromotionDomainService) → 激活时校验规则 → 更新
        """
        promo = await self._promo_repo.get_by_id(promo_id, tenant_id)
        if not promo:
            raise NotFoundException(message=f"Promotion '{promo_id}' not found")
        if not PromotionDomainService.can_transition(promo.status, new_status):
            raise ValidationException(
                message=f"Cannot transition promotion from '{promo.status}' to '{new_status}'"
            )
        if new_status == "active":
            errors = PromotionDomainService.validate_promotion(promo)
            if errors:
                raise ValidationException(message="; ".join(errors))
        promo.status = new_status
        return await self._promo_repo.update(promo)

    async def calculate_order_discount(self, tenant_id: str, order_amount: float,
                                        sku_id: str = "", category_id: str = "",
                                        platform: str = "", store_id: str = "") -> dict:
        """
        计算订单可用折扣

        流程: 查询所有生效促销 → 逐条校验适用性(PromotionDomainService) → 计算折扣 → 汇总
        """
        if order_amount < 0:
            raise ValidationException(message="Order amount cannot be negative")
        promos = await self._promo_repo.list_active_for_discount(
            tenant_id, order_amount, platform=platform, store_id=store_id,
        )
        applicable = []
        total_discount = 0.0
        for p in promos:
            if not PromotionDomainService.is_applicable(p, sku_id, category_id):
                continue
            if not PromotionDomainService.is_within_usage_limit(p):
                continue
            discount = PromotionDomainService.calculate_discount(p, order_amount)
            if discount > 0:
                applicable.append({
                    "promo_id": str(p.id), "promo_no": p.promo_no, "promo_name": p.name,
                    "discount_type": p.discount_type, "discount_amount": discount,
                })
                total_discount += discount
                if not p.can_stack:
                    break
        return {
            "total_discount": round(total_discount, 2),
            "final_amount": round(max(order_amount - total_discount, 0), 2),
            "applied_promotions": applicable,
        }

    async def increment_usage(self, promo_id: str, tenant_id: str) -> Promotion:
        """递增促销使用量"""
        promo = await self._promo_repo.get_by_id(promo_id, tenant_id)
        if not promo:
            raise NotFoundException(message=f"Promotion '{promo_id}' not found")
        promo.used_count += 1
        return await self._promo_repo.update(promo)

    async def soft_delete(self, promo_id: str, tenant_id: str) -> bool:
        promo = await self._promo_repo.get_by_id(promo_id, tenant_id)
        if not promo:
            raise NotFoundException(message=f"Promotion '{promo_id}' not found")
        if promo.status == "active":
            raise ValidationException(message="Cannot delete active promotion, pause or cancel first")
        return await self._promo_repo.soft_delete(promo_id, tenant_id)


class SalesOrderQueryService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def search(self, tenant_id: str, keyword: str = "", platform: str = "", store_id: str = "",
                     status: str = "", order_type: str = "", start_date: datetime | None = None,
                     end_date: datetime | None = None, min_amount: float = 0.0, max_amount: float = 0.0,
                     page: int = 1, page_size: int = 20) -> tuple[Sequence[SalesOrder], int]:
        conditions = [SalesOrder.tenant_id == tenant_id, SalesOrder.deleted_at.is_(None)]
        if keyword:
            conditions.append(
                (SalesOrder.order_no.ilike(f"%{keyword}%"))
                | (SalesOrder.buyer_name.ilike(f"%{keyword}%"))
                | (SalesOrder.platform_order_id.ilike(f"%{keyword}%"))
            )
        if platform:
            conditions.append(SalesOrder.platform == platform)
        if store_id:
            conditions.append(SalesOrder.store_id == store_id)
        if status:
            conditions.append(SalesOrder.status == status)
        if order_type:
            conditions.append(SalesOrder.order_type == order_type)
        if start_date:
            conditions.append(SalesOrder.order_time >= start_date)
        if end_date:
            conditions.append(SalesOrder.order_time <= end_date)
        if min_amount > 0:
            conditions.append(SalesOrder.total_amount >= min_amount)
        if max_amount > 0:
            conditions.append(SalesOrder.total_amount <= max_amount)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(SalesOrder).where(*conditions)
        )).scalar() or 0
        stmt = select(SalesOrder).where(*conditions).order_by(
            SalesOrder.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = (await self._session.execute(stmt)).scalars().all()
        return items, total

    async def get_statistics(self, tenant_id: str, platform: str = "", store_id: str = "") -> dict:
        conditions = [SalesOrder.tenant_id == tenant_id, SalesOrder.deleted_at.is_(None)]
        if platform:
            conditions.append(SalesOrder.platform == platform)
        if store_id:
            conditions.append(SalesOrder.store_id == store_id)
        stmt = select(SalesOrder).where(*conditions)
        orders = (await self._session.execute(stmt)).scalars().all()
        total = len(orders)
        total_amount = sum(o.total_amount or 0 for o in orders)
        by_status: dict[str, int] = {}
        by_platform: dict[str, int] = {}
        for o in orders:
            by_status[o.status] = by_status.get(o.status, 0) + 1
            if o.platform:
                by_platform[o.platform] = by_platform.get(o.platform, 0) + 1
        avg_amount = round(total_amount / total, 2) if total > 0 else 0.0
        return {
            "total_orders": total,
            "total_amount": round(total_amount, 2),
            "by_status": by_status,
            "by_platform": by_platform,
            "avg_amount": avg_amount,
        }


class RefundQueryService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_statistics(self, tenant_id: str) -> dict:
        conditions = [RefundOrder.tenant_id == tenant_id]
        stmt = select(RefundOrder).where(*conditions)
        refunds = (await self._session.execute(stmt)).scalars().all()
        total = len(refunds)
        total_amount = sum(r.refund_amount or 0 for r in refunds)
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for r in refunds:
            by_status[r.status] = by_status.get(r.status, 0) + 1
            by_type[r.refund_type] = by_type.get(r.refund_type, 0) + 1
        return {
            "total_refunds": total,
            "total_refund_amount": round(total_amount, 2),
            "by_status": by_status,
            "by_type": by_type,
        }

    async def list_by_order(self, original_order_id: str, tenant_id: str) -> Sequence[RefundOrder]:
        stmt = select(RefundOrder).where(
            RefundOrder.original_order_id == original_order_id,
            RefundOrder.tenant_id == tenant_id,
        ).order_by(RefundOrder.created_at.desc())
        return (await self._session.execute(stmt)).scalars().all()


class OrderSplitExecutionService:
    """
    拆单执行服务

    根据拆单规则执行实际拆单操作:
    - 按仓库拆: 不同发货仓的行项拆为独立子单
    - 按物流拆: 不同物流渠道的行项拆为独立子单
    - 按商品类型拆: FBA/自发货/特殊商品拆为独立子单
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def execute_split(self, tenant_id: str, order_id: str, split_strategy: str = "warehouse") -> dict:
        """
        执行拆单

        流程: 查询订单行项 → 按策略分组 → 生成子单 → 更新原单状态
        """
        order = (await self._session.execute(
            select(SalesOrder).where(SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not order:
            raise NotFoundException(message=f"Order '{order_id}' not found")
        if order.status not in ("pending", "confirmed"):
            raise ValidationException(message=f"Cannot split order in '{order.status}' status")
        items = (await self._session.execute(
            select(SalesOrderItem).where(SalesOrderItem.order_id == order_id, SalesOrderItem.tenant_id == tenant_id)
        )).scalars().all()
        if len(items) <= 1:
            return {"order_id": order_id, "split_count": 1, "message": "Order has only one item, no split needed"}
        groups = await self._group_items_by_strategy(tenant_id, items, split_strategy)
        if len(groups) <= 1:
            return {"order_id": order_id, "split_count": 1, "message": "No split needed by strategy"}
        sub_orders = []
        for idx, (group_key, group_items) in enumerate(groups.items()):
            sub_order = SalesOrder(
                tenant_id=tenant_id,
                order_no=f"{order.order_no}-S{idx + 1}",
                platform=order.platform,
                store_id=order.store_id,
                marketplace=order.marketplace,
                buyer_id=order.buyer_id,
                status="pending",
                item_subtotal=sum(i.line_total for i in group_items if i.line_total),
                shipping_fee=order.shipping_fee / len(groups) if idx == 0 else 0,
                currency=order.currency,
                parent_order_id=order_id,
                remark=f"Split from {order.order_no}, group={group_key}",
            )
            self._session.add(sub_order)
            sub_orders.append(sub_order)
        order.status = "split"
        await self._session.flush()
        return {
            "order_id": order_id, "original_order_no": order.order_no,
            "split_count": len(sub_orders), "strategy": split_strategy,
            "groups": {k: len(v) for k, v in groups.items()},
        }

    async def _group_items_by_strategy(self, tenant_id: str, items: list, strategy: str) -> dict:
        if strategy == "warehouse":
            return await self._group_by_warehouse(tenant_id, items)
        elif strategy == "logistics":
            return await self._group_by_logistics(tenant_id, items)
        elif strategy == "product_type":
            return self._group_by_product_type(items)
        return {"default": items}

    async def _group_by_warehouse(self, tenant_id: str, items: list) -> dict:
        groups: dict[str, list] = {}
        for item in items:
            warehouse_id = await self._resolve_warehouse(tenant_id, item.sku_id)
            groups.setdefault(warehouse_id, []).append(item)
        return groups

    async def _group_by_logistics(self, tenant_id: str, items: list) -> dict:
        groups: dict[str, list] = {}
        for item in items:
            channel = "standard"
            groups.setdefault(channel, []).append(item)
        return groups

    def _group_by_product_type(self, items: list) -> dict:
        groups: dict[str, list] = {}
        for item in items:
            product_type = "fba" if hasattr(item, "fulfillment_channel") and item.fulfillment_channel == "FBA" else "self_shipped"
            groups.setdefault(product_type, []).append(item)
        return groups

    async def _resolve_warehouse(self, tenant_id: str, sku_id: str) -> str:
        try:
            from erp.shared.cross_domain_query import InventoryQueryService  # 跨域查询替代直接import
            inv = (await self._session.execute(
                select(Inventory).where(Inventory.tenant_id == tenant_id, Inventory.sku_id == sku_id, Inventory.qty_available > 0)
            )).scalar_one_or_none()
            return inv.warehouse_id if inv else "unassigned"
        except Exception:
            return "unassigned"


class PromotionMatchEngine:
    """
    促销匹配引擎

    为订单自动匹配最优促销:
    - 满减: 满X元减Y
    - 折扣: 百分比折扣
    - 买赠: 买X赠Y
    - 组合促销: 多SKU组合优惠
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def match_best_promotions(self, tenant_id: str, order_id: str) -> dict:
        """
        匹配最优促销

        流程: 查询订单 → 获取有效促销 → 逐条匹配 → 选择最优组合 → 计算优惠
        """
        order = (await self._session.execute(
            select(SalesOrder).where(SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not order:
            raise NotFoundException(message=f"Order '{order_id}' not found")
        items = (await self._session.execute(
            select(SalesOrderItem).where(SalesOrderItem.order_id == order_id, SalesOrderItem.tenant_id == tenant_id)
        )).scalars().all()
        now = datetime.now(UTC)
        promotions = (await self._session.execute(
            select(Promotion).where(
                Promotion.tenant_id == tenant_id, Promotion.status == "active",
                Promotion.start_time <= now, Promotion.end_time >= now)
        )).scalars().all()
        if not promotions:
            return {"order_id": order_id, "matched": [], "total_discount": 0, "best_promotion": None}
        matched = []
        for promo in promotions:
            match_result = self._evaluate_promotion(promo, order, items)
            if match_result["applicable"]:
                matched.append(match_result)
        matched.sort(key=lambda x: x["discount_amount"], reverse=True)
        best = matched[0] if matched else None
        total_discount = sum(m["discount_amount"] for m in matched)
        return {
            "order_id": order_id, "matched_count": len(matched),
            "total_discount": round(total_discount, 2),
            "best_promotion": best, "all_matched": matched,
        }

    def _evaluate_promotion(self, promo: Promotion, order: SalesOrder, items: list) -> dict:
        result = {"promotion_id": str(promo.id), "promotion_name": promo.promotion_name,
                   "promo_type": promo.promotion_type, "applicable": False, "discount_amount": 0.0}
        order_amount = order.item_subtotal or 0
        if promo.promotion_type == "full_reduction":
            threshold = float(promo.condition_json.get("threshold", 0)) if promo.condition_json else 0
            discount = float(promo.condition_json.get("discount", 0)) if promo.condition_json else 0
            if order_amount >= threshold:
                result["applicable"] = True
                result["discount_amount"] = discount
        elif promo.promotion_type == "discount":
            min_amount = float(promo.condition_json.get("min_amount", 0)) if promo.condition_json else 0
            discount_rate = float(promo.condition_json.get("discount_rate", 1.0)) if promo.condition_json else 1.0
            if order_amount >= min_amount:
                result["applicable"] = True
                result["discount_amount"] = round(order_amount * (1 - discount_rate), 2)
        elif promo.promotion_type == "gift":
            min_quantity = int(promo.condition_json.get("min_quantity", 0)) if promo.condition_json else 0
            total_qty = sum(i.quantity for i in items)
            if total_qty >= min_quantity:
                result["applicable"] = True
                result["discount_amount"] = 0
                result["gift_info"] = promo.condition_json.get("gift_info", "") if promo.condition_json else ""
        return result


class OrderMergeService:
    """
    订单合并服务

    将同一买家/同地址/同仓库的多个订单合并为一个发货单
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def find_mergeable_orders(self, tenant_id: str, buyer_id: str = "") -> list[dict]:
        """查找可合并的订单"""
        conditions = [
            SalesOrder.tenant_id == tenant_id,
            SalesOrder.status.in_(["pending", "confirmed"]),
            SalesOrder.parent_order_id.is_(None),
        ]
        if buyer_id:
            conditions.append(SalesOrder.buyer_id == buyer_id)
        orders = (await self._session.execute(
            select(SalesOrder).where(*conditions).order_by(SalesOrder.buyer_id, SalesOrder.created_at)
        )).scalars().all()
        groups: dict[str, list] = {}
        for o in orders:
            key = f"{o.buyer_id}|{o.shipping_address or ''}"
            groups.setdefault(key, []).append(o)
        mergeable = []
        for key, group in groups.items():
            if len(group) > 1:
                mergeable.append({
                    "merge_key": key, "order_count": len(group),
                    "order_ids": [str(o.id) for o in group],
                    "total_amount": sum(o.item_subtotal or 0 for o in group),
                })
        return mergeable

    async def merge_orders(self, tenant_id: str, order_ids: list[str]) -> dict:
        """合并多个订单"""
        if len(order_ids) < 2:
            raise ValidationException(message="At least 2 orders required for merge")
        orders = []
        for oid in order_ids:
            order = (await self._session.execute(
                select(SalesOrder).where(SalesOrder.id == oid, SalesOrder.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if not order:
                raise NotFoundException(message=f"Order '{oid}' not found")
            if order.status not in ("pending", "confirmed"):
                raise ValidationException(message=f"Cannot merge order in '{order.status}' status")
            orders.append(order)
        primary = orders[0]
        for other in orders[1:]:
            other.status = "merged"
            other.parent_order_id = str(primary.id)
            other_items = (await self._session.execute(
                select(SalesOrderItem).where(SalesOrderItem.order_id == str(other.id))
            )).scalars().all()
            for item in other_items:
                item.order_id = str(primary.id)
        primary.item_subtotal = (primary.item_subtotal or 0) + sum(o.item_subtotal or 0 for o in orders[1:])
        await self._session.flush()
        return {
            "merged_into": str(primary.id), "order_no": primary.order_no,
            "merged_count": len(orders) - 1, "total_amount": primary.item_subtotal,
        }


class ShipmentOrchestrationService:
    """
    发货编排服务

    编排从订单确认到发货的完整流程:
    订单确认 → 仓库分配 → 拣货指令 → 物流下单 → 发货通知
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def orchestrate_shipment(self, tenant_id: str, order_id: str) -> dict:
        """
        编排发货

        流程: 订单校验 → 仓库分配 → 创建出库单 → 物流下单 → 状态更新
        """
        order = (await self._session.execute(
            select(SalesOrder).where(SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not order:
            raise NotFoundException(message=f"Order '{order_id}' not found")
        if order.status not in ("confirmed", "processing"):
            raise ValidationException(message=f"Order status '{order.status}' is not ready for shipment")
        items = (await self._session.execute(
            select(SalesOrderItem).where(SalesOrderItem.order_id == order_id, SalesOrderItem.tenant_id == tenant_id)
        )).scalars().all()
        allocation = await self._allocate_warehouse(tenant_id, items)
        outbound_result = await self._create_outbound_order(tenant_id, order_id, allocation)
        shipment_result = await self._create_shipment_order(tenant_id, order, allocation)
        order.status = "shipped"
        await self._session.flush()
        return {
            "order_id": order_id, "status": "shipped",
            "warehouse_allocation": allocation,
            "outbound_order": outbound_result,
            "shipment_order": shipment_result,
        }

    async def _allocate_warehouse(self, tenant_id: str, items: list) -> dict:
        """分配仓库: 查询各SKU库存，选择最优仓库"""
        allocation = {}
        try:
            from erp.shared.cross_domain_query import InventoryQueryService  # 跨域查询替代直接import
            for item in items:
                inv = (await self._session.execute(
                    select(Inventory).where(
                        Inventory.tenant_id == tenant_id, Inventory.sku_id == item.sku_id,
                        Inventory.qty_available >= item.quantity)
                )).scalars().first()
                if inv:
                    allocation[item.sku_id] = {"warehouse_id": inv.warehouse_id, "qty_available": inv.qty_available}
                else:
                    allocation[item.sku_id] = {"warehouse_id": None, "qty_available": 0, "shortage": True}
        except Exception:
            for item in items:
                allocation[item.sku_id] = {"warehouse_id": None, "error": "inventory_service_unavailable"}
        return allocation

    async def _create_outbound_order(self, tenant_id: str, order_id: str, allocation: dict) -> dict:
        """创建出库单(调用WMS域)"""
        return {
            "order_id": order_id, "type": "sales_outbound",
            "allocated_warehouses": list(set(
                v.get("warehouse_id") for v in allocation.values() if v.get("warehouse_id")
            )),
        }

    async def _create_shipment_order(self, tenant_id: str, order: SalesOrder, allocation: dict) -> dict:
        """创建物流单(调用TMS域)"""
        return {
            "order_id": str(order.id), "carrier": "auto_selected",
            "tracking_no": f"TRK-{order.order_no}", "status": "pending_pickup",
        }


class OrderSplitRuleService:
    def __init__(self, session: AsyncSession, split_rule_repo: OrderSplitRuleRepository | None = None):
        self._session = session
        self._split_rule_repo = split_rule_repo or SqlOrderSplitRuleRepository(session)

    async def create(self, tenant_id: str, name: str, rule_type: str, **kwargs) -> OrderSplitRule:
        rule = OrderSplitRule(
            tenant_id=tenant_id, name=name, rule_type=rule_type,
            conditions_json=kwargs.get("conditions_json", "{}"),
            priority=kwargs.get("priority", 0),
            status="active",
        )
        return await self._split_rule_repo.create(rule)

    async def list_all(self, tenant_id: str, status: str = "") -> Sequence[OrderSplitRule]:
        return await self._split_rule_repo.list_by_tenant(tenant_id, status=status)

    async def update(self, rule_id: str, tenant_id: str, **kwargs) -> OrderSplitRule:
        rules = await self._split_rule_repo.list_by_tenant(tenant_id)
        rule = next((r for r in rules if r.id == rule_id), None)
        if not rule:
            raise NotFoundException(message=f"Split rule '{rule_id}' not found")
        for key, val in kwargs.items():
            if hasattr(rule, key) and key not in ("id", "tenant_id"):
                setattr(rule, key, val)
        return await self._split_rule_repo.update(rule)


class OrderAuditQueryService:
    def __init__(self, session: AsyncSession, audit_log_repo: OrderAuditLogRepository | None = None):
        self._session = session
        self._audit_log_repo = audit_log_repo or SqlOrderAuditLogRepository(session)

    async def list_by_order(self, order_id: str, tenant_id: str) -> Sequence[OrderAuditLog]:
        return await self._audit_log_repo.list_by_order(order_id, tenant_id)

    async def get_order_timeline(self, order_id: str, tenant_id: str) -> list[dict]:
        logs = await self._audit_log_repo.list_by_order(order_id, tenant_id)
        return [
            {
                "action": log.action,
                "from_status": log.from_status,
                "to_status": log.to_status,
                "operator_id": log.operator_id,
                "operator_name": log.operator_name,
                "remark": log.remark,
                "created_at": str(log.created_at) if log.created_at else None,
            }
            for log in logs
        ]


ORDER_RISK_LEVELS = {
    "low": {"max_amount": 5000.0, "description": "低风险订单，自动通过"},
    "medium": {"max_amount": 50000.0, "description": "中风险订单，需一级审批"},
    "high": {"max_amount": 200000.0, "description": "高风险订单，需二级审批"},
    "critical": {"max_amount": float("inf"), "description": "极高风险订单，需三级审批+风控审核"},
}

RISK_FACTORS = {
    "new_buyer": {"weight": 15, "description": "新买家(首次下单)"},
    "large_amount": {"weight": 25, "description": "大额订单(超过阈值)"},
    "high_quantity": {"weight": 10, "description": "高数量订单"},
    "duplicate_order": {"weight": 20, "description": "疑似重复订单"},
    "suspicious_address": {"weight": 15, "description": "可疑收货地址"},
    "rapid_orders": {"weight": 15, "description": "短时间内多次下单"},
}


class OrderRiskControlService:
    """
    订单风控审批应用服务

    编排订单风控评估与审批流程:
    - 风险评估: 多因子评分 → 风险等级判定
    - 自动审批: 低风险自动通过
    - 人工审批: 中/高/极高风险按级审批
    - 风控标记: 标记可疑订单，限制操作
    """

    def __init__(self, session: AsyncSession, order_repo: SalesOrderRepository | None = None):
        self._session = session
        self._order_repo = order_repo

    async def evaluate_risk(self, tenant_id: str, order_id: str) -> dict:
        """
        评估订单风险

        流程: 查询订单 → 多因子评分 → 判定风险等级 → 返回评估结果
        """
        order = await self._get_order(order_id, tenant_id)
        if not order:
            raise NotFoundException(message=f"Order '{order_id}' not found")
        risk_score = 0
        risk_factors_detected: list[dict] = []
        total_amount = order.item_subtotal or 0
        if total_amount > ORDER_RISK_RULES["max_amount_per_order"]:
            risk_score += RISK_FACTORS["large_amount"]["weight"]
            risk_factors_detected.append({
                "factor": "large_amount",
                "detail": f"Amount {total_amount} exceeds threshold {ORDER_RISK_RULES['max_amount_per_order']}",
            })
        items = await self._get_order_items(order_id, tenant_id)
        total_qty = sum(i.quantity for i in items) if items else 0
        if total_qty > ORDER_RISK_RULES["max_items_per_order"]:
            risk_score += RISK_FACTORS["high_quantity"]["weight"]
            risk_factors_detected.append({
                "factor": "high_quantity",
                "detail": f"Total quantity {total_qty} exceeds threshold {ORDER_RISK_RULES['max_items_per_order']}",
            })
        if not order.buyer_id:
            risk_score += RISK_FACTORS["new_buyer"]["weight"]
            risk_factors_detected.append({"factor": "new_buyer", "detail": "No buyer ID provided"})
        duplicate_window = ORDER_RISK_RULES["duplicate_check_window_minutes"]
        if duplicate_window > 0 and order.buyer_id:
            from sqlalchemy import func as sa_func
            cutoff = datetime.now(UTC)
            from datetime import timedelta
            cutoff = cutoff - timedelta(minutes=duplicate_window)
            dup_stmt = select(sa_func.count()).select_from(SalesOrder).where(
                SalesOrder.tenant_id == tenant_id,
                SalesOrder.buyer_id == order.buyer_id,
                SalesOrder.status != "cancelled",
                SalesOrder.created_at >= cutoff,
                SalesOrder.id != order_id,
            )
            dup_count = (await self._session.execute(dup_stmt)).scalar() or 0
            if dup_count >= 3:
                risk_score += RISK_FACTORS["rapid_orders"]["weight"]
                risk_factors_detected.append({
                    "factor": "rapid_orders",
                    "detail": f"{dup_count} orders from same buyer within {duplicate_window} minutes",
                })
        risk_level = "low"
        if risk_score >= 40:
            risk_level = "critical"
        elif risk_score >= 25:
            risk_level = "high"
        elif risk_score >= 10:
            risk_level = "medium"
        return {
            "order_id": order_id,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "factors_detected": risk_factors_detected,
            "requires_approval": risk_level != "low",
            "approval_level": self._get_approval_level(risk_level),
            "auto_approve": risk_level == "low",
        }

    def _get_approval_level(self, risk_level: str) -> int:
        levels = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        return levels.get(risk_level, 0)

    async def approve_order(self, tenant_id: str, order_id: str,
                            approver_id: str, approval_level: int = 1,
                            remark: str = "") -> dict:
        """
        审批订单

        流程: 查询订单 → 风险评估 → 审批级别校验 → 更新状态
        """
        order = await self._get_order(order_id, tenant_id)
        if not order:
            raise NotFoundException(message=f"Order '{order_id}' not found")
        if order.status not in ("pending", "confirmed"):
            raise ValidationException(message=f"Cannot approve order in '{order.status}' status")
        # 调用订单策略中台评估审核规则
        from erp.middleware.order_strategy.domain.engine import OrderStrategyEngine, StrategyContext
        strategy = OrderStrategyEngine()
        ctx = StrategyContext(order_amount=float(getattr(order, 'total_amount', 0)),
                              buyer_history=0, profit_rate=risk_eval.get("profit_rate", 0))
        review_result = strategy.evaluate_review(ctx)
        if review_result.get("review"):
            risk_eval["flags"] = risk_eval.get("flags", []) + review_result["flags"]

        risk_eval = await self.evaluate_risk(tenant_id, order_id)
        required_level = risk_eval.get("approval_level", 0)
        if approval_level < required_level:
            raise ValidationException(
                message=f"Approval level {approval_level} insufficient, required {required_level}"
            )
        order.status = "confirmed"
        await self._session.flush()
        return {
            "order_id": order_id, "status": "confirmed",
            "approved_by": approver_id, "approval_level": approval_level,
            "risk_level": risk_eval["risk_level"],
        }

    async def reject_order(self, tenant_id: str, order_id: str,
                           rejector_id: str, reason: str = "") -> dict:
        """拒绝订单"""
        order = await self._get_order(order_id, tenant_id)
        if not order:
            raise NotFoundException(message=f"Order '{order_id}' not found")
        if order.status not in ("pending", "confirmed"):
            raise ValidationException(message=f"Cannot reject order in '{order.status}' status")
        order.status = "cancelled"
        await self._session.flush()
        return {"order_id": order_id, "status": "cancelled", "rejected_by": rejector_id, "reason": reason}

    async def flag_suspicious(self, tenant_id: str, order_id: str,
                              reason: str = "", flagged_by: str = "") -> dict:
        """标记可疑订单"""
        order = await self._get_order(order_id, tenant_id)
        if not order:
            raise NotFoundException(message=f"Order '{order_id}' not found")
        order.remark = f"[FLAGGED:{reason}] {order.remark or ''}"
        await self._session.flush()
        return {"order_id": order_id, "flagged": True, "reason": reason, "flagged_by": flagged_by}

    async def batch_evaluate(self, tenant_id: str, order_ids: list[str]) -> list[dict]:
        """批量风控评估"""
        results = []
        for oid in order_ids:
            try:
                result = await self.evaluate_risk(tenant_id, oid)
                results.append(result)
            except Exception as e:
                results.append({"order_id": oid, "error": str(e)})
        return results

    async def _get_order(self, order_id: str, tenant_id: str) -> SalesOrder | None:
        if self._order_repo:
            return await self._order_repo.get_by_id(order_id, tenant_id)
        stmt = select(SalesOrder).where(SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _get_order_items(self, order_id: str, tenant_id: str) -> Sequence[SalesOrderItem] | None:
        stmt = select(SalesOrderItem).where(SalesOrderItem.order_id == order_id, SalesOrderItem.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()
