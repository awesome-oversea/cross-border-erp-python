"""
OMS (订单域) 依赖注入工厂

所有 Service 和 Repository 实例通过 FastAPI Depends() 链式注入，
禁止在 router 中手动实例化 Service。

注入链路 (铁律):
  router → Depends(get_xxx_service) → Service(session, repo) → Repository(session)

仓储注入规则:
  - SalesOrderRepository: 被 SalesOrderService 使用
  - SalesOrderItemRepository: 被 SalesOrderService 使用 (订单明细)
  - RefundOrderRepository: 被 RefundOrderService 使用
  - OrderSplitRuleRepository: 被 SalesOrderService 使用 (拆单规则)
  - OrderAuditLogRepository: 被 SalesOrderService 使用 (审计日志)
  - PromotionRepository: 被 PromotionService 使用
  - WarehouseAllocationService / LogisticsOptimizationService:
    跨域聚合查询，仅注入 Session，不通过仓储接口
  - OrderSyncService: 订单同步编排，注入 SalesOrderService 而非直接注入仓储
  - OrderStrategyService: 策略引擎，仅注入 Session (策略模型内嵌查询逻辑)
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.oms.application.services import (
    LogisticsOptimizationService,
    OrderAuditQueryService,
    OrderSplitRuleService,
    OrderSyncService,
    PromotionService,
    RefundOrderService,
    RefundQueryService,
    SalesOrderQueryService,
    SalesOrderService,
    WarehouseAllocationService,
)
from erp.modules.oms.domain.repositories import (
    OrderAuditLogRepository,
    OrderSplitRuleRepository,
    PromotionRepository,
    RefundOrderRepository,
    SalesOrderItemRepository,
    SalesOrderRepository,
)
from erp.modules.oms.infrastructure.repositories import (
    SqlOrderAuditLogRepository,
    SqlOrderSplitRuleRepository,
    SqlPromotionRepository,
    SqlRefundOrderRepository,
    SqlSalesOrderItemRepository,
    SqlSalesOrderRepository,
)
from erp.shared.context import TenantContext, tenant_id_var
from erp.shared.db.session import get_db_session


# ============================================================
# 仓储工厂: Session → Repository 实例
# FastAPI 会自动缓存同一请求内相同依赖的结果，因此同一请求中
# 多个服务共享同一仓储实例时，Session 不会重复创建。
# ============================================================

def _sales_order_repo(session: AsyncSession = Depends(get_db_session)) -> SalesOrderRepository:
    """创建销售订单仓储实例 — 被 SalesOrderService 使用"""
    return SqlSalesOrderRepository(session)


def _sales_order_item_repo(session: AsyncSession = Depends(get_db_session)) -> SalesOrderItemRepository:
    """创建销售订单明细仓储实例 — 被 SalesOrderService 使用 (订单明细)"""
    return SqlSalesOrderItemRepository(session)


def _refund_order_repo(session: AsyncSession = Depends(get_db_session)) -> RefundOrderRepository:
    """创建退款单仓储实例 — 被 RefundOrderService 使用"""
    return SqlRefundOrderRepository(session)


def _order_split_rule_repo(session: AsyncSession = Depends(get_db_session)) -> OrderSplitRuleRepository:
    """创建拆单规则仓储实例 — 被 SalesOrderService 使用 (拆单规则)"""
    return SqlOrderSplitRuleRepository(session)


def _order_audit_log_repo(session: AsyncSession = Depends(get_db_session)) -> OrderAuditLogRepository:
    """创建审计日志仓储实例 — 被 SalesOrderService 使用 (审计日志)"""
    return SqlOrderAuditLogRepository(session)


def _promotion_repo(session: AsyncSession = Depends(get_db_session)) -> PromotionRepository:
    """创建促销活动仓储实例 — 被 PromotionService 使用"""
    return SqlPromotionRepository(session)


# ============================================================
# 服务工厂: Session + Repository → Service 实例
# 每个服务工厂通过 Depends() 注入对应的仓储实例，
# 确保服务层通过仓储接口操作数据，而非直接使用 Session。
# ============================================================

def get_sales_order_service(
    session: AsyncSession = Depends(get_db_session),
    order_repo: SalesOrderRepository = Depends(_sales_order_repo),
    item_repo: SalesOrderItemRepository = Depends(_sales_order_item_repo),
    split_rule_repo: OrderSplitRuleRepository = Depends(_order_split_rule_repo),
    audit_log_repo: OrderAuditLogRepository = Depends(_order_audit_log_repo),
) -> SalesOrderService:
    """获取销售订单服务实例 — 注入4个仓储 (订单/明细/拆单规则/审计日志)"""
    return SalesOrderService(
        session=session,
        order_repo=order_repo,
        item_repo=item_repo,
        split_rule_repo=split_rule_repo,
        audit_log_repo=audit_log_repo,
    )


def get_refund_order_service(
    session: AsyncSession = Depends(get_db_session),
    refund_repo: RefundOrderRepository = Depends(_refund_order_repo),
) -> RefundOrderService:
    """获取退款单服务实例 — 注入 RefundOrderRepository"""
    return RefundOrderService(session=session, refund_repo=refund_repo)


def get_promotion_service(
    session: AsyncSession = Depends(get_db_session),
    promo_repo: PromotionRepository = Depends(_promotion_repo),
) -> PromotionService:
    """获取促销活动服务实例 — 注入 PromotionRepository"""
    return PromotionService(session=session, promo_repo=promo_repo)


def get_order_sync_service(
    session: AsyncSession = Depends(get_db_session),
    order_svc: SalesOrderService = Depends(get_sales_order_service),
) -> OrderSyncService:
    """获取订单同步服务实例 — 注入 SalesOrderService (编排层，不直接操作仓储)"""
    return OrderSyncService(session=session, order_svc=order_svc)


# ============================================================
# 跨域聚合查询服务 — 仅注入 Session，不通过仓储接口
# 这些服务涉及跨域 (WMS/TMS) 的 JOIN 查询，
# 仓储接口的 CRUD 粒度无法满足，保留 Session 直接操作。
# ============================================================

def get_warehouse_allocation_service(
    session: AsyncSession = Depends(get_db_session),
) -> WarehouseAllocationService:
    """获取仓库分配服务实例 — 跨域聚合查询 (WMS Inventory)，仅注入 Session"""
    return WarehouseAllocationService(session=session)


def get_logistics_optimization_service(
    session: AsyncSession = Depends(get_db_session),
) -> LogisticsOptimizationService:
    """获取物流优化服务实例 — 跨域聚合查询 (TMS LogisticsProvider)，仅注入 Session"""
    return LogisticsOptimizationService(session=session)


# ============================================================
# 通用上下文依赖
# ============================================================

def get_tenant_context() -> TenantContext:
    """获取当前租户上下文 (从 ContextVar 读取)"""
    return TenantContext.current()


def get_current_tenant_id() -> str:
    """获取当前租户ID (从 ContextVar 读取)"""
    return tenant_id_var.get("")


def get_sales_order_query_service(
    session: AsyncSession = Depends(get_db_session),
) -> SalesOrderQueryService:
    return SalesOrderQueryService(session=session)


def get_refund_query_service(
    session: AsyncSession = Depends(get_db_session),
) -> RefundQueryService:
    return RefundQueryService(session=session)


def get_order_split_rule_service(
    session: AsyncSession = Depends(get_db_session),
    split_rule_repo: OrderSplitRuleRepository = Depends(_order_split_rule_repo),
) -> OrderSplitRuleService:
    return OrderSplitRuleService(session=session, split_rule_repo=split_rule_repo)


def get_order_audit_query_service(
    session: AsyncSession = Depends(get_db_session),
    audit_log_repo: OrderAuditLogRepository = Depends(_order_audit_log_repo),
) -> OrderAuditQueryService:
    return OrderAuditQueryService(session=session, audit_log_repo=audit_log_repo)
