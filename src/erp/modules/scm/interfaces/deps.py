"""
SCM 依赖注入工厂

本模块为 SCM (供应链管理) 模块的所有应用服务提供 FastAPI Depends() 注入。
每个服务通过仓储接口访问数据，仓储实例由本模块创建并注入。

注入链路:
  Router → Depends(get_xxx_service) → Service(Repo) → SqlRepo(Session)

仓储清单:
  - SupplierRepository:            供应商
  - PurchaseOrderRepository:       采购订单
  - PurchaseOrderItemRepository:   采购订单明细
  - ReplenishmentPlanRepository:   补货计划
  - SupplierEvaluationRepository:  供应商评价
  - InquiryRepository:             询价单
  - InquiryQuoteRepository:        询价报价
"""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.scm.application.services import (
    InquiryService,
    PurchaseOrderService,
    ReplenishmentPlanService,
    SCMQueryService,
    SupplierEvaluationService,
    SupplierService,
)
from erp.modules.scm.domain.repositories import (
    InquiryQuoteRepository,
    InquiryRepository,
    PurchaseOrderItemRepository,
    PurchaseOrderRepository,
    ReplenishmentPlanRepository,
    SupplierEvaluationRepository,
    SupplierRepository,
)
from erp.modules.scm.infrastructure.repositories import (
    SqlInquiryQuoteRepository,
    SqlInquiryRepository,
    SqlPurchaseOrderItemRepository,
    SqlPurchaseOrderRepository,
    SqlReplenishmentPlanRepository,
    SqlSupplierEvaluationRepository,
    SqlSupplierRepository,
)
from erp.shared.context import get_current_tenant_id
from erp.shared.db.session import get_db_session


# ---------------------------------------------------------------------------
# 仓储工厂 — 每个请求创建新实例，持有当前 Session
# ---------------------------------------------------------------------------

def _supplier_repo(session: AsyncSession = Depends(get_db_session)) -> SupplierRepository:
    return SqlSupplierRepository(session)


def _purchase_order_repo(session: AsyncSession = Depends(get_db_session)) -> PurchaseOrderRepository:
    return SqlPurchaseOrderRepository(session)


def _purchase_order_item_repo(session: AsyncSession = Depends(get_db_session)) -> PurchaseOrderItemRepository:
    return SqlPurchaseOrderItemRepository(session)


def _replenishment_plan_repo(session: AsyncSession = Depends(get_db_session)) -> ReplenishmentPlanRepository:
    return SqlReplenishmentPlanRepository(session)


def _supplier_evaluation_repo(session: AsyncSession = Depends(get_db_session)) -> SupplierEvaluationRepository:
    return SqlSupplierEvaluationRepository(session)


def _inquiry_repo(session: AsyncSession = Depends(get_db_session)) -> InquiryRepository:
    return SqlInquiryRepository(session)


def _inquiry_quote_repo(session: AsyncSession = Depends(get_db_session)) -> InquiryQuoteRepository:
    return SqlInquiryQuoteRepository(session)


# ---------------------------------------------------------------------------
# 服务工厂 — 注入仓储接口
# ---------------------------------------------------------------------------

def get_supplier_service(
    session: AsyncSession = Depends(get_db_session),
    supplier_repo: SupplierRepository = Depends(_supplier_repo),
) -> SupplierService:
    """获取供应商服务实例 — 注入 SupplierRepository"""
    return SupplierService(session=session, supplier_repo=supplier_repo)


def get_purchase_order_service(
    session: AsyncSession = Depends(get_db_session),
    po_repo: PurchaseOrderRepository = Depends(_purchase_order_repo),
    item_repo: PurchaseOrderItemRepository = Depends(_purchase_order_item_repo),
    supplier_repo: SupplierRepository = Depends(_supplier_repo),
) -> PurchaseOrderService:
    """获取采购订单服务实例 — 注入 PO / Item / Supplier 三个仓储"""
    return PurchaseOrderService(
        session=session, po_repo=po_repo, item_repo=item_repo, supplier_repo=supplier_repo,
    )


def get_replenishment_plan_service(
    session: AsyncSession = Depends(get_db_session),
    plan_repo: ReplenishmentPlanRepository = Depends(_replenishment_plan_repo),
) -> ReplenishmentPlanService:
    """获取补货计划服务实例 — 注入 ReplenishmentPlanRepository"""
    return ReplenishmentPlanService(session=session, plan_repo=plan_repo)


def get_inquiry_service(
    session: AsyncSession = Depends(get_db_session),
    inquiry_repo: InquiryRepository = Depends(_inquiry_repo),
    quote_repo: InquiryQuoteRepository = Depends(_inquiry_quote_repo),
    supplier_repo: SupplierRepository = Depends(_supplier_repo),
) -> InquiryService:
    """获取询价服务实例 — 注入 Inquiry / Quote / Supplier 三个仓储"""
    return InquiryService(
        session=session, inquiry_repo=inquiry_repo, quote_repo=quote_repo, supplier_repo=supplier_repo,
    )


def get_supplier_evaluation_service(
    session: AsyncSession = Depends(get_db_session),
    evaluation_repo: SupplierEvaluationRepository = Depends(_supplier_evaluation_repo),
    supplier_repo: SupplierRepository = Depends(_supplier_repo),
) -> SupplierEvaluationService:
    """获取供应商评价服务实例 — 注入 Evaluation / Supplier 两个仓储"""
    return SupplierEvaluationService(
        session=session, evaluation_repo=evaluation_repo, supplier_repo=supplier_repo,
    )


def get_scm_query_service(
    session: AsyncSession = Depends(get_db_session),
) -> SCMQueryService:
    return SCMQueryService(session=session)
