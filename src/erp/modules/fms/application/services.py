"""
FMS (财务域) 应用服务层

职责: 编排领域服务 + 仓储接口，实现业务用例

设计原则:
  1. 核心CRUD服务通过仓储接口操作数据 (CostEvent/PlatformSettlement/PaymentRecord/ExchangeRate)
  2. 复杂聚合查询服务保留 Session 直接操作 (ProfitCalculation/CostBreakdown)
  3. 业务校验委托给 domain/services.py 中的领域服务
  4. 状态变更通过领域服务的状态机校验
  5. 所有服务构造函数接受 (session, repo=None)，优先使用 repo，回退到 session

仓储接口使用规则:
  - CostEventRepository: 被 CostEventService / WriteOffService / ReconciliationService /
    InvoiceService / ExpenseService / ForexTransactionService / PlatformBillService /
    JournalEntryService 共享 (这些服务底层都操作 CostEvent 实体)
  - PlatformSettlementRepository: 被 PlatformSettlementService 使用
  - PaymentRecordRepository: 被 PaymentRecordService / PaymentRequestService 使用
  - ExchangeRateRepository: 被 ExchangeRateService / ForexTransactionService 使用
"""
from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING

from sqlalchemy import func as sa_func
from sqlalchemy import select

from erp.modules.fms.domain.models import CostEvent, ExchangeRate, PaymentRecord, PlatformSettlement
from erp.modules.fms.domain.repositories import (
    CostEventRepository,
    ExchangeRateRepository,
    PaymentRecordRepository,
    PlatformSettlementRepository,
)
from erp.modules.fms.domain.services import (
    COST_EVENT_STATUS_TRANSITIONS,
    EXPENSE_STATUS_TRANSITIONS,
    FOREX_TRANSACTION_STATUS_TRANSITIONS,
    INVOICE_STATUS_TRANSITIONS,
    PAYMENT_REQUEST_STATUS_TRANSITIONS,
    PLATFORM_BILL_STATUS_TRANSITIONS,
    RECONCILIATION_STATUS_TRANSITIONS,
    WRITEOFF_STATUS_TRANSITIONS,
    VALID_COST_TYPES,
    CostBreakdownDomainService,
    CostEventDomainService,
    ExpenseDomainService,
    ForexDomainService,
    InvoiceDomainService,
    JournalEntryDomainService,
    PaymentRequestDomainService,
    PlatformBillDomainService,
    ProfitDomainService,
    ReconciliationDomainService,
    SettlementDomainService,
    VoucherEngineDomainService,
    WriteOffDomainService,
)
from erp.shared.context import actor_id_var
from erp.shared.exceptions import DuplicateCodeException, NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.fms")

PAYMENT_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["processing", "cancelled"],
    "processing": ["completed", "failed"],
    "completed": [],
    "failed": ["pending"],
    "cancelled": [],
}


# ============================================================
# 成本事件 (Cost Event) — 核心聚合根
# ============================================================

class CostEventService:
    """
    成本事件应用服务

    通过 CostEventRepository 仓储接口操作数据，是 FMS 域最核心的服务。
    成本事件是财务域的聚合根，其他子服务 (核销/对账/发票/费用等) 底层也操作 CostEvent 实体。
    """

    def __init__(self, session: AsyncSession, repo: CostEventRepository | None = None):
        """
        初始化成本事件服务

        Args:
            session: 数据库异步会话，用于回退场景
            repo: 成本事件仓储接口，优先使用；为 None 时回退到 session 直接操作
        """
        self._session = session
        self._repo = repo

    async def create(self, tenant_id: str, event_no: str, cost_type: str, amount: float,
                     currency: str = "CNY", exchange_rate: float = 1.0, **kwargs) -> CostEvent:
        """
        创建成本事件

        流程: 唯一性校验 → 领域校验 → 计算人民币金额 → 持久化

        Args:
            tenant_id: 租户ID
            event_no: 成本事件编号 (租户内唯一)
            cost_type: 成本类型 (product_cost/shipping_cost/platform_fee 等，兼容旧口径 purchase_cost/head_freight)
            amount: 金额
            currency: 币种，默认 CNY
            exchange_rate: 汇率，默认 1.0
            **kwargs: 其他字段 (sku_id/order_id/shipment_id/reference_type/reference_id 等)

        Returns:
            CostEvent: 已持久化的成本事件实体

        Raises:
            DuplicateCodeException: 事件编号已存在
            ValidationException: 成本类型/金额/币种不合法
        """
        if self._repo:
            existing = await self._repo.get_by_event_no(event_no, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.event_no == event_no, CostEvent.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Cost event '{event_no}' already exists")

        errors = CostEventDomainService.validate_cost_event(cost_type, amount, currency)
        if errors:
            raise ValidationException(message="; ".join(errors))
        if exchange_rate <= 0:
            raise ValidationException(message="Exchange rate must be positive")

        amount_cny = CostEventDomainService.calculate_amount_cny(amount, currency, exchange_rate)
        event = CostEvent(
            tenant_id=tenant_id, event_no=event_no, cost_type=cost_type,
            amount=amount, currency=currency, exchange_rate=exchange_rate,
            amount_cny=amount_cny, created_by=actor_id_var.get(""), **kwargs,
        )
        if self._repo:
            return await self._repo.create(event)
        self._session.add(event)
        await self._session.flush()
        return event

    async def get_by_id(self, event_id: str, tenant_id: str) -> CostEvent | None:
        """
        根据ID查询成本事件

        Args:
            event_id: 成本事件主键ID
            tenant_id: 租户ID (数据隔离)

        Returns:
            CostEvent | None: 查询到的实体，不存在返回 None
        """
        if self._repo:
            return await self._repo.get_by_id(event_id, tenant_id)
        stmt = select(CostEvent).where(CostEvent.id == event_id, CostEvent.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, event_id: str, tenant_id: str) -> CostEvent:
        event = await self.get_by_id(event_id, tenant_id)
        if not event:
            raise NotFoundException(message=f"Cost event '{event_id}' not found")
        return event

    async def update_status(self, event_id: str, tenant_id: str, status: str) -> CostEvent:
        """
        更新成本事件状态

        通过领域服务 CostEventDomainService.can_transition() 校验状态机合法性。
        合法转换: draft→confirmed→settled, draft→cancelled

        Args:
            event_id: 成本事件主键ID
            tenant_id: 租户ID
            status: 目标状态

        Returns:
            CostEvent: 更新后的实体

        Raises:
            NotFoundException: 事件不存在
            ValidationException: 状态转换不合法
        """
        if self._repo:
            event = await self._repo.get_by_id(event_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == event_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Cost event '{event_id}' not found")
        if not CostEventDomainService.can_transition(event.status, status):
            raise ValidationException(message=f"Cannot transition cost event from '{event.status}' to '{status}'")
        event.status = status
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def list_all(self, tenant_id: str, cost_type: str = "", sku_id: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[CostEvent], int]:
        """
        分页查询成本事件列表

        Args:
            tenant_id: 租户ID
            cost_type: 成本类型筛选 (可选)
            sku_id: SKU ID筛选 (可选)
            page: 页码，从1开始
            page_size: 每页条数

        Returns:
            tuple[Sequence[CostEvent], int]: (事件列表, 总条数)
        """
        if self._repo:
            return await self._repo.list_by_tenant(tenant_id, cost_type=cost_type, sku_id=sku_id, page=page, page_size=page_size)
        conditions = [CostEvent.tenant_id == tenant_id]
        if cost_type:
            conditions.append(CostEvent.cost_type == cost_type)
        if sku_id:
            conditions.append(CostEvent.sku_id == sku_id)
        total = (await self._session.execute(select(sa_func.count()).select_from(CostEvent).where(*conditions))).scalar() or 0
        stmt = select(CostEvent).where(*conditions).order_by(CostEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def update(self, event_id: str, tenant_id: str, **kwargs) -> CostEvent:
        """
        更新成本事件字段

        Args:
            event_id: 成本事件主键ID
            tenant_id: 租户ID
            **kwargs: 需要更新的字段 (cost_type/amount/currency/exchange_rate/remark等)

        Returns:
            CostEvent: 更新后的实体

        Raises:
            NotFoundException: 事件不存在
        """
        if self._repo:
            event = await self._repo.get_by_id(event_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == event_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Cost event '{event_id}' not found")
        if "amount" in kwargs or "currency" in kwargs or "exchange_rate" in kwargs:
            amount = kwargs.get("amount", event.amount)
            currency = kwargs.get("currency", event.currency)
            exchange_rate = kwargs.get("exchange_rate", event.exchange_rate)
            kwargs["amount_cny"] = CostEventDomainService.calculate_amount_cny(amount, currency, exchange_rate)
        for k, v in kwargs.items():
            if hasattr(event, k) and v is not None:
                setattr(event, k, v)
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def search(self, tenant_id: str, keyword: str = "", cost_type: str = "",
                     status: str = "", currency: str = "",
                     start_date=None, end_date=None,
                     min_amount: float | None = None, max_amount: float | None = None,
                     page: int = 1, page_size: int = 20) -> tuple[Sequence[CostEvent], int]:
        """
        搜索成本事件

        支持关键词搜索、状态筛选、日期范围、金额范围等多维度查询。
        """
        conditions = [CostEvent.tenant_id == tenant_id]
        if keyword:
            conditions.append((CostEvent.event_no.contains(keyword) | CostEvent.remark.contains(keyword)))
        if cost_type:
            conditions.append(CostEvent.cost_type == cost_type)
        if status:
            conditions.append(CostEvent.status == status)
        if currency:
            conditions.append(CostEvent.currency == currency)
        if start_date:
            conditions.append(CostEvent.occurred_date >= start_date)
        if end_date:
            conditions.append(CostEvent.occurred_date <= end_date)
        if min_amount is not None:
            conditions.append(CostEvent.amount >= min_amount)
        if max_amount is not None:
            conditions.append(CostEvent.amount <= max_amount)
        total = (await self._session.execute(select(sa_func.count()).select_from(CostEvent).where(*conditions))).scalar() or 0
        stmt = select(CostEvent).where(*conditions).order_by(CostEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def batch_update_status(self, tenant_id: str, event_ids: list[str], status: str) -> list[CostEvent]:
        """批量更新成本事件状态"""
        results = []
        for eid in event_ids:
            event = await self.update_status(eid, tenant_id, status)
            results.append(event)
        return results


# ============================================================
# 平台结算 (Platform Settlement)
# ============================================================

class PlatformSettlementService:
    """
    平台结算应用服务

    通过 PlatformSettlementRepository 仓储接口操作数据。
    管理各电商平台 (Amazon/Shopify/TikTok) 的结算单据。
    """

    def __init__(self, session: AsyncSession, repo: PlatformSettlementRepository | None = None):
        self._session = session
        self._repo = repo

    async def create(self, tenant_id: str, settlement_no: str, platform: str, store_id: str, **kwargs) -> PlatformSettlement:
        """创建平台结算记录: 唯一性校验 → 持久化"""
        if self._repo:
            existing = await self._repo.get_by_settlement_no(settlement_no, tenant_id)
        else:
            stmt = select(PlatformSettlement).where(PlatformSettlement.settlement_no == settlement_no, PlatformSettlement.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Settlement '{settlement_no}' already exists")

        settlement = PlatformSettlement(tenant_id=tenant_id, settlement_no=settlement_no, platform=platform, store_id=store_id, **kwargs)
        if self._repo:
            return await self._repo.create(settlement)
        self._session.add(settlement)
        await self._session.flush()
        return settlement

    async def get_by_id(self, settlement_id: str, tenant_id: str) -> PlatformSettlement | None:
        """根据ID查询平台结算"""
        if self._repo:
            return await self._repo.get_by_id(settlement_id, tenant_id)
        stmt = select(PlatformSettlement).where(PlatformSettlement.id == settlement_id, PlatformSettlement.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, settlement_id: str, tenant_id: str) -> PlatformSettlement:
        settlement = await self.get_by_id(settlement_id, tenant_id)
        if not settlement:
            raise NotFoundException(message=f"Platform settlement '{settlement_id}' not found")
        return settlement

    async def update_status(self, settlement_id: str, tenant_id: str, status: str) -> PlatformSettlement:
        """
        更新平台结算状态

        通过领域服务 SettlementDomainService.can_transition() 校验状态机合法性。
        合法转换: pending→confirmed→settled, pending→cancelled
        """
        if self._repo:
            settlement = await self._repo.get_by_id(settlement_id, tenant_id)
        else:
            stmt = select(PlatformSettlement).where(PlatformSettlement.id == settlement_id, PlatformSettlement.tenant_id == tenant_id)
            settlement = (await self._session.execute(stmt)).scalar_one_or_none()
        if not settlement:
            raise NotFoundException(message=f"Settlement '{settlement_id}' not found")
        if not SettlementDomainService.can_transition(settlement.status, status):
            raise ValidationException(message=f"Cannot transition settlement from '{settlement.status}' to '{status}'")
        settlement.status = status
        if self._repo:
            return await self._repo.update(settlement)
        await self._session.flush()
        return settlement

    async def list_all(self, tenant_id: str, platform: str = "", status: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[PlatformSettlement], int]:
        """分页查询平台结算列表"""
        if self._repo:
            return await self._repo.list_by_tenant(tenant_id, platform=platform, status=status, page=page, page_size=page_size)
        conditions = [PlatformSettlement.tenant_id == tenant_id]
        if platform:
            conditions.append(PlatformSettlement.platform == platform)
        if status:
            conditions.append(PlatformSettlement.status == status)
        total = (await self._session.execute(select(sa_func.count()).select_from(PlatformSettlement).where(*conditions))).scalar() or 0
        stmt = select(PlatformSettlement).where(*conditions).order_by(PlatformSettlement.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def update(self, settlement_id: str, tenant_id: str, **kwargs) -> PlatformSettlement:
        """
        更新平台结算字段

        Args:
            settlement_id: 结算主键ID
            tenant_id: 租户ID
            **kwargs: 需要更新的字段

        Returns:
            PlatformSettlement: 更新后的实体

        Raises:
            NotFoundException: 结算不存在
        """
        if self._repo:
            settlement = await self._repo.get_by_id(settlement_id, tenant_id)
        else:
            stmt = select(PlatformSettlement).where(PlatformSettlement.id == settlement_id, PlatformSettlement.tenant_id == tenant_id)
            settlement = (await self._session.execute(stmt)).scalar_one_or_none()
        if not settlement:
            raise NotFoundException(message=f"Settlement '{settlement_id}' not found")
        for k, v in kwargs.items():
            if hasattr(settlement, k) and v is not None:
                setattr(settlement, k, v)
        if any(k in kwargs for k in ("total_sales", "total_refund", "platform_fee", "advertising_fee", "shipping_fee", "other_fee")):
            settlement.net_amount = SettlementDomainService.calculate_net_amount(
                settlement.total_sales, settlement.total_refund,
                settlement.platform_fee, settlement.advertising_fee,
                settlement.shipping_fee, settlement.other_fee,
            )
        if self._repo:
            return await self._repo.update(settlement)
        await self._session.flush()
        return settlement


# ============================================================
# 付款记录 (Payment Record)
# ============================================================

class PaymentRecordService:
    """
    付款记录应用服务

    通过 PaymentRecordRepository 仓储接口操作数据。
    管理供应商付款、平台打款、退款付款等各类付款记录。
    """

    def __init__(self, session: AsyncSession, repo: PaymentRecordRepository | None = None):
        self._session = session
        self._repo = repo

    async def create(self, tenant_id: str, payment_no: str, payment_type: str,
                     amount: float, **kwargs) -> PaymentRecord:
        """创建付款记录: 唯一性校验 → 持久化"""
        if self._repo:
            existing = await self._repo.get_by_payment_no(payment_no, tenant_id)
        else:
            stmt = select(PaymentRecord).where(PaymentRecord.payment_no == payment_no, PaymentRecord.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Payment '{payment_no}' already exists")

        payment = PaymentRecord(
            tenant_id=tenant_id, payment_no=payment_no, payment_type=payment_type,
            amount=amount, created_by=actor_id_var.get(""), **kwargs,
        )
        if self._repo:
            return await self._repo.create(payment)
        self._session.add(payment)
        await self._session.flush()
        return payment

    async def get_by_id(self, payment_id: str, tenant_id: str) -> PaymentRecord | None:
        """根据ID查询付款记录"""
        if self._repo:
            return await self._repo.get_by_id(payment_id, tenant_id)
        stmt = select(PaymentRecord).where(PaymentRecord.id == payment_id, PaymentRecord.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, payment_id: str, tenant_id: str) -> PaymentRecord:
        payment = await self.get_by_id(payment_id, tenant_id)
        if not payment:
            raise NotFoundException(message=f"Payment record '{payment_id}' not found")
        return payment

    async def update_status(self, payment_id: str, tenant_id: str, status: str) -> PaymentRecord:
        """
        更新付款记录状态

        状态机: pending→processing→completed, pending→cancelled, processing→failed, failed→pending
        完成时自动设置 paid_at 时间戳。
        """
        if self._repo:
            payment = await self._repo.get_by_id(payment_id, tenant_id)
        else:
            stmt = select(PaymentRecord).where(PaymentRecord.id == payment_id, PaymentRecord.tenant_id == tenant_id)
            payment = (await self._session.execute(stmt)).scalar_one_or_none()
        if not payment:
            raise NotFoundException(message=f"Payment '{payment_id}' not found")

        allowed = PAYMENT_STATUS_TRANSITIONS.get(payment.status, [])
        if status not in allowed:
            raise ValidationException(message=f"Cannot transition payment from '{payment.status}' to '{status}'")
        payment.status = status
        if status == "completed":
            payment.paid_at = __import__("datetime").datetime.now(UTC)
        if self._repo:
            return await self._repo.update(payment)
        await self._session.flush()
        return payment

    async def list_all(self, tenant_id: str, payment_type: str = "", status: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[PaymentRecord], int]:
        """分页查询付款记录列表"""
        if self._repo:
            return await self._repo.list_by_tenant(tenant_id, payment_type=payment_type, status=status, page=page, page_size=page_size)
        conditions = [PaymentRecord.tenant_id == tenant_id]
        if payment_type:
            conditions.append(PaymentRecord.payment_type == payment_type)
        if status:
            conditions.append(PaymentRecord.status == status)
        total = (await self._session.execute(select(sa_func.count()).select_from(PaymentRecord).where(*conditions))).scalar() or 0
        stmt = select(PaymentRecord).where(*conditions).order_by(PaymentRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total


# ============================================================
# 付款申请 (Payment Request) — 基于 PaymentRecord 实体
# ============================================================

class PaymentRequestService:
    """
    付款申请应用服务

    底层使用 PaymentRecordRepository 操作 PaymentRecord 实体。
    付款申请是付款记录的一种特殊流程 (pending → approved → paid)，带有审批流。
    """

    def __init__(self, session: AsyncSession, repo: PaymentRecordRepository | None = None):
        self._session = session
        self._repo = repo

    async def create(self, tenant_id: str, request_no: str, request_type: str,
                     amount: float, currency: str = "CNY", **kwargs) -> PaymentRecord:
        """
        创建付款申请

        流程: 领域校验(金额/币种/类型) → 唯一性校验 → 持久化
        初始状态为 pending，需经过审批流程后才能变为 approved/paid。
        """
        errors = PaymentRequestDomainService.validate_payment_request(amount, currency, request_type)
        if errors:
            raise ValidationException(message="; ".join(errors))

        if self._repo:
            existing = await self._repo.get_by_payment_no(request_no, tenant_id)
        else:
            stmt = select(PaymentRecord).where(PaymentRecord.payment_no == request_no, PaymentRecord.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Payment request '{request_no}' already exists")

        payment = PaymentRecord(
            tenant_id=tenant_id, payment_no=request_no, payment_type=request_type,
            amount=amount, currency=currency, status="pending",
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(PaymentRecord, k)},
        )
        if self._repo:
            return await self._repo.create(payment)
        self._session.add(payment)
        await self._session.flush()
        return payment

    async def approve(self, payment_id: str, tenant_id: str, approver_level: int,
                      total_levels: int, remark: str = "") -> PaymentRecord:
        """
        审批通过付款申请

        多级审批流程: 按审批级别逐级审批，全部通过后自动变更为 approved 状态。
        """
        if self._repo:
            payment = await self._repo.get_by_id(payment_id, tenant_id)
        else:
            stmt = select(PaymentRecord).where(PaymentRecord.id == payment_id, PaymentRecord.tenant_id == tenant_id)
            payment = (await self._session.execute(stmt)).scalar_one_or_none()
        if not payment:
            raise NotFoundException(message=f"Payment request '{payment_id}' not found")
        if payment.status != "pending":
            raise ValidationException(message=f"Cannot approve payment in '{payment.status}' status")

        approval_flow = getattr(payment, "approval_flow", []) or []
        if not PaymentRequestDomainService.can_approve(approval_flow, approver_level):
            raise ValidationException(message=f"Approver level {approver_level} cannot approve at this stage")
        approval_flow.append({"level": approver_level, "status": "approved", "remark": remark})
        if PaymentRequestDomainService.is_fully_approved(approval_flow, total_levels):
            payment.status = "approved"
        payment.approval_instance_id = str(approval_flow)

        if self._repo:
            return await self._repo.update(payment)
        await self._session.flush()
        return payment

    async def reject(self, payment_id: str, tenant_id: str, remark: str = "") -> PaymentRecord:
        """驳回付款申请"""
        if self._repo:
            payment = await self._repo.get_by_id(payment_id, tenant_id)
        else:
            stmt = select(PaymentRecord).where(PaymentRecord.id == payment_id, PaymentRecord.tenant_id == tenant_id)
            payment = (await self._session.execute(stmt)).scalar_one_or_none()
        if not payment:
            raise NotFoundException(message=f"Payment request '{payment_id}' not found")
        if not PaymentRequestDomainService.can_transition(payment.status, "rejected"):
            raise ValidationException(message=f"Cannot reject payment in '{payment.status}' status")
        payment.status = "rejected"

        if self._repo:
            return await self._repo.update(payment)
        await self._session.flush()
        return payment

    async def get_writeoff_progress(self, payment_id: str, tenant_id: str) -> dict:
        """查询付款申请的核销进度"""
        if self._repo:
            payment = await self._repo.get_by_id(payment_id, tenant_id)
        else:
            stmt = select(PaymentRecord).where(PaymentRecord.id == payment_id, PaymentRecord.tenant_id == tenant_id)
            payment = (await self._session.execute(stmt)).scalar_one_or_none()
        if not payment:
            raise NotFoundException(message=f"Payment request '{payment_id}' not found")

        writeoff_amount = float(getattr(payment, "writeoff_amount", 0) or 0)
        progress = PaymentRequestDomainService.calculate_writeoff_progress(writeoff_amount, payment.amount)
        status = PaymentRequestDomainService.get_writeoff_status(writeoff_amount, payment.amount)
        return {"payment_id": payment_id, "writeoff_amount": writeoff_amount,
                "total_amount": payment.amount, "progress_pct": progress, "writeoff_status": status}

    async def list_all(self, tenant_id: str, request_type: str = "", status: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[PaymentRecord], int]:
        """分页查询付款申请列表"""
        if self._repo:
            return await self._repo.list_by_tenant(tenant_id, payment_type=request_type, status=status, page=page, page_size=page_size)
        conditions = [PaymentRecord.tenant_id == tenant_id]
        if request_type:
            conditions.append(PaymentRecord.payment_type == request_type)
        if status:
            conditions.append(PaymentRecord.status == status)
        total = (await self._session.execute(select(sa_func.count()).select_from(PaymentRecord).where(*conditions))).scalar() or 0
        stmt = select(PaymentRecord).where(*conditions).order_by(PaymentRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total


# ============================================================
# 核销 (Write-Off) — 基于 CostEvent 实体
# ============================================================

class WriteOffService:
    """
    核销应用服务

    底层使用 CostEventRepository 操作 CostEvent 实体。
    核销是将付款与应付进行匹配确认的业务流程。
    状态机: pending → approved → completed
    """

    def __init__(self, session: AsyncSession, repo: CostEventRepository | None = None):
        self._session = session
        self._repo = repo

    async def create(self, tenant_id: str, writeoff_no: str, writeoff_type: str,
                     ref_type: str, ref_id: str, amount: float, currency: str = "CNY",
                     **kwargs) -> CostEvent:
        """创建核销记录: 领域校验 → 唯一性校验 → 持久化"""
        errors = WriteOffDomainService.validate_writeoff(writeoff_type, ref_type, amount, currency)
        if errors:
            raise ValidationException(message="; ".join(errors))

        if self._repo:
            existing = await self._repo.get_by_event_no(writeoff_no, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.event_no == writeoff_no, CostEvent.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Writeoff '{writeoff_no}' already exists")

        event = CostEvent(
            tenant_id=tenant_id, event_no=writeoff_no, cost_type="other",
            amount=amount, currency=currency, status="pending",
            reference_type=ref_type, reference_id=ref_id,
            remark=f"Writeoff: {writeoff_type}",
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(CostEvent, k)},
        )
        if self._repo:
            return await self._repo.create(event)
        self._session.add(event)
        await self._session.flush()
        return event

    async def approve(self, writeoff_id: str, tenant_id: str) -> CostEvent:
        """审批通过核销 (状态: pending → approved)"""
        if self._repo:
            event = await self._repo.get_by_id(writeoff_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == writeoff_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Writeoff '{writeoff_id}' not found")
        if not WriteOffDomainService.can_transition(event.status, "approved"):
            raise ValidationException(message=f"Cannot approve writeoff in '{event.status}' status")
        event.status = "approved"
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def complete(self, writeoff_id: str, tenant_id: str) -> CostEvent:
        """完成核销 (状态: approved → completed)"""
        if self._repo:
            event = await self._repo.get_by_id(writeoff_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == writeoff_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Writeoff '{writeoff_id}' not found")
        if not WriteOffDomainService.can_transition(event.status, "completed"):
            raise ValidationException(message=f"Cannot complete writeoff in '{event.status}' status")
        event.status = "completed"
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def reject(self, writeoff_id: str, tenant_id: str) -> CostEvent:
        """驳回核销 (状态: pending → rejected)"""
        if self._repo:
            event = await self._repo.get_by_id(writeoff_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == writeoff_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Writeoff '{writeoff_id}' not found")
        if not WriteOffDomainService.can_transition(event.status, "rejected"):
            raise ValidationException(message=f"Cannot reject writeoff in '{event.status}' status")
        event.status = "rejected"
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def list_all(self, tenant_id: str, writeoff_type: str = "", status: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[CostEvent], int]:
        """分页查询核销列表"""
        conditions = [CostEvent.tenant_id == tenant_id, CostEvent.remark.contains("Writeoff")]
        if writeoff_type:
            conditions.append(CostEvent.remark.contains(writeoff_type))
        if status:
            conditions.append(CostEvent.status == status)
        total = (await self._session.execute(select(sa_func.count()).select_from(CostEvent).where(*conditions))).scalar() or 0
        stmt = select(CostEvent).where(*conditions).order_by(CostEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total


# ============================================================
# 对账 (Reconciliation) — 基于 CostEvent 实体
# ============================================================

class ReconciliationService:
    """
    对账应用服务

    底层使用 CostEventRepository 操作 CostEvent 实体。
    对账是核对供应商/物流商/平台账目的业务流程。
    状态机: pending → reconciled / disputed → reconciled
    """

    def __init__(self, session: AsyncSession, repo: CostEventRepository | None = None):
        self._session = session
        self._repo = repo

    async def create(self, tenant_id: str, recon_no: str, recon_type: str,
                     party_id: str, period: str, payable_amount: float,
                     paid_amount: float = 0, **kwargs) -> CostEvent:
        """创建对账记录: 领域校验 → 唯一性校验 → 计算差额 → 持久化"""
        errors = ReconciliationDomainService.validate_reconciliation(recon_type, party_id, period, payable_amount)
        if errors:
            raise ValidationException(message="; ".join(errors))

        if self._repo:
            existing = await self._repo.get_by_event_no(recon_no, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.event_no == recon_no, CostEvent.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Reconciliation '{recon_no}' already exists")

        balance = ReconciliationDomainService.calculate_balance(payable_amount, paid_amount)
        event = CostEvent(
            tenant_id=tenant_id, event_no=recon_no, cost_type="other",
            amount=payable_amount, currency="CNY", status="pending",
            remark=f"Reconciliation: {recon_type}, balance: {balance}",
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(CostEvent, k)},
        )
        if self._repo:
            return await self._repo.create(event)
        self._session.add(event)
        await self._session.flush()
        return event

    async def find_differences(self, tenant_id: str, expected_items: list[dict],
                               actual_items: list[dict], key_field: str = "ref_id") -> list[dict]:
        """查找对账差异 — 纯领域逻辑，委托给 ReconciliationDomainService"""
        return ReconciliationDomainService.find_differences(expected_items, actual_items, key_field)

    async def get_by_id(self, recon_id: str, tenant_id: str) -> CostEvent | None:
        if self._repo:
            return await self._repo.get_by_id(recon_id, tenant_id)
        stmt = select(CostEvent).where(CostEvent.id == recon_id, CostEvent.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, recon_id: str, tenant_id: str) -> CostEvent:
        event = await self.get_by_id(recon_id, tenant_id)
        if not event:
            raise NotFoundException(message=f"Reconciliation '{recon_id}' not found")
        return event

    async def reconcile(self, recon_id: str, tenant_id: str) -> CostEvent:
        """确认对账 (状态: pending/disputed → reconciled)"""
        if self._repo:
            event = await self._repo.get_by_id(recon_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == recon_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Reconciliation '{recon_id}' not found")
        if not ReconciliationDomainService.can_transition(event.status, "reconciled"):
            raise ValidationException(message=f"Cannot reconcile in '{event.status}' status")
        event.status = "reconciled"
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def dispute(self, recon_id: str, tenant_id: str) -> CostEvent:
        """标记对账异议 (状态: pending → disputed)"""
        if self._repo:
            event = await self._repo.get_by_id(recon_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == recon_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Reconciliation '{recon_id}' not found")
        if not ReconciliationDomainService.can_transition(event.status, "disputed"):
            raise ValidationException(message=f"Cannot dispute in '{event.status}' status")
        event.status = "disputed"
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def cancel(self, recon_id: str, tenant_id: str) -> CostEvent:
        """取消对账 (状态: pending/disputed → cancelled)"""
        if self._repo:
            event = await self._repo.get_by_id(recon_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == recon_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Reconciliation '{recon_id}' not found")
        if not ReconciliationDomainService.can_transition(event.status, "cancelled"):
            raise ValidationException(message=f"Cannot cancel in '{event.status}' status")
        event.status = "cancelled"
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def list_all(self, tenant_id: str, recon_type: str = "", status: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[CostEvent], int]:
        """分页查询对账列表"""
        conditions = [CostEvent.tenant_id == tenant_id, CostEvent.remark.contains("Reconciliation")]
        if recon_type:
            conditions.append(CostEvent.remark.contains(recon_type))
        if status:
            conditions.append(CostEvent.status == status)
        total = (await self._session.execute(select(sa_func.count()).select_from(CostEvent).where(*conditions))).scalar() or 0
        stmt = select(CostEvent).where(*conditions).order_by(CostEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total


# ============================================================
# 发票 (Invoice) — 基于 CostEvent 实体
# ============================================================

class InvoiceService:
    """
    发票应用服务

    底层使用 CostEventRepository 操作 CostEvent 实体。
    管理采购发票/销售发票/红字发票/蓝字发票。
    状态机: draft → issued → paid / voided / overdue
    """

    def __init__(self, session: AsyncSession, repo: CostEventRepository | None = None):
        self._session = session
        self._repo = repo

    async def create(self, tenant_id: str, invoice_no: str, invoice_type: str,
                     amount: float, currency: str = "CNY", tax_rate: float = 0,
                     **kwargs) -> CostEvent:
        """创建发票记录: 领域校验 → 计算税额 → 唯一性校验 → 持久化"""
        errors = InvoiceDomainService.validate_invoice(invoice_type, amount, currency)
        if errors:
            raise ValidationException(message="; ".join(errors))

        tax_amount = InvoiceDomainService.calculate_tax(amount, tax_rate)

        if self._repo:
            existing = await self._repo.get_by_event_no(invoice_no, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.event_no == invoice_no, CostEvent.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Invoice '{invoice_no}' already exists")

        event = CostEvent(
            tenant_id=tenant_id, event_no=invoice_no, cost_type="other",
            amount=amount + tax_amount, currency=currency, status="draft",
            remark=f"Invoice: {invoice_type}, tax: {tax_amount}",
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(CostEvent, k)},
        )
        if self._repo:
            return await self._repo.create(event)
        self._session.add(event)
        await self._session.flush()
        return event

    async def issue(self, invoice_id: str, tenant_id: str) -> CostEvent:
        """开出发票 (状态: draft → issued)"""
        if self._repo:
            event = await self._repo.get_by_id(invoice_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == invoice_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Invoice '{invoice_id}' not found")
        if not InvoiceDomainService.can_transition(event.status, "issued"):
            raise ValidationException(message=f"Cannot issue invoice in '{event.status}' status")
        event.status = "issued"
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def mark_paid(self, invoice_id: str, tenant_id: str) -> CostEvent:
        """标记发票已付 (状态: issued → paid)"""
        if self._repo:
            event = await self._repo.get_by_id(invoice_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == invoice_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Invoice '{invoice_id}' not found")
        if not InvoiceDomainService.can_transition(event.status, "paid"):
            raise ValidationException(message=f"Cannot mark invoice as paid in '{event.status}' status")
        event.status = "paid"
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def void(self, invoice_id: str, tenant_id: str) -> CostEvent:
        """作废发票 (状态: draft/issued → cancelled)"""
        if self._repo:
            event = await self._repo.get_by_id(invoice_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == invoice_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Invoice '{invoice_id}' not found")
        if not InvoiceDomainService.can_transition(event.status, "cancelled"):
            raise ValidationException(message=f"Cannot void invoice in '{event.status}' status")
        event.status = "cancelled"
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def mark_overdue(self, invoice_id: str, tenant_id: str) -> CostEvent:
        """标记发票逾期 (状态: issued → overdue)"""
        if self._repo:
            event = await self._repo.get_by_id(invoice_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == invoice_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Invoice '{invoice_id}' not found")
        if not InvoiceDomainService.can_transition(event.status, "overdue"):
            raise ValidationException(message=f"Cannot mark invoice as overdue in '{event.status}' status")
        event.status = "overdue"
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def list_all(self, tenant_id: str, invoice_type: str = "", status: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[CostEvent], int]:
        """分页查询发票列表"""
        conditions = [CostEvent.tenant_id == tenant_id, CostEvent.remark.contains("Invoice")]
        if invoice_type:
            conditions.append(CostEvent.remark.contains(invoice_type))
        if status:
            conditions.append(CostEvent.status == status)
        total = (await self._session.execute(select(sa_func.count()).select_from(CostEvent).where(*conditions))).scalar() or 0
        stmt = select(CostEvent).where(*conditions).order_by(CostEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total


# ============================================================
# 费用 (Expense) — 基于 CostEvent 实体
# ============================================================

class ExpenseService:
    """
    费用应用服务

    底层使用 CostEventRepository 操作 CostEvent 实体。
    管理广告费/运费/仓储费/退款/平台费/税费/人工费等各类费用。
    状态机: pending → approved → paid / cancelled
    """

    def __init__(self, session: AsyncSession, repo: CostEventRepository | None = None):
        self._session = session
        self._repo = repo

    async def create(self, tenant_id: str, expense_no: str, expense_type: str,
                     amount: float, currency: str = "CNY", **kwargs) -> CostEvent:
        """创建费用记录: 领域校验 → 费用分类 → 唯一性校验 → 持久化"""
        errors = ExpenseDomainService.validate_expense(expense_type, amount, currency)
        if errors:
            raise ValidationException(message="; ".join(errors))

        category = ExpenseDomainService.categorize_expense(expense_type)

        if self._repo:
            existing = await self._repo.get_by_event_no(expense_no, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.event_no == expense_no, CostEvent.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Expense '{expense_no}' already exists")

        event = CostEvent(
            tenant_id=tenant_id, event_no=expense_no, cost_type=expense_type,
            amount=amount, currency=currency, status="pending",
            remark=f"Expense category: {category}",
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(CostEvent, k)},
        )
        if self._repo:
            return await self._repo.create(event)
        self._session.add(event)
        await self._session.flush()
        return event

    async def approve(self, expense_id: str, tenant_id: str) -> CostEvent:
        """审批通过费用 (状态: pending → approved)"""
        if self._repo:
            event = await self._repo.get_by_id(expense_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == expense_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Expense '{expense_id}' not found")
        if not ExpenseDomainService.can_transition(event.status, "approved"):
            raise ValidationException(message=f"Cannot approve expense in '{event.status}' status")
        event.status = "approved"
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def reject(self, expense_id: str, tenant_id: str) -> CostEvent:
        """驳回费用 (状态: pending → rejected)"""
        if self._repo:
            event = await self._repo.get_by_id(expense_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == expense_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Expense '{expense_id}' not found")
        if not ExpenseDomainService.can_transition(event.status, "rejected"):
            raise ValidationException(message=f"Cannot reject expense in '{event.status}' status")
        event.status = "rejected"
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def pay(self, expense_id: str, tenant_id: str) -> CostEvent:
        """标记费用已付 (状态: approved → paid)"""
        if self._repo:
            event = await self._repo.get_by_id(expense_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == expense_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Expense '{expense_id}' not found")
        if not ExpenseDomainService.can_transition(event.status, "paid"):
            raise ValidationException(message=f"Cannot pay expense in '{event.status}' status")
        event.status = "paid"
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def list_all(self, tenant_id: str, expense_type: str = "", status: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[CostEvent], int]:
        """分页查询费用列表"""
        conditions = [CostEvent.tenant_id == tenant_id, CostEvent.remark.contains("Expense")]
        if expense_type:
            conditions.append(CostEvent.cost_type == expense_type)
        if status:
            conditions.append(CostEvent.status == status)
        total = (await self._session.execute(select(sa_func.count()).select_from(CostEvent).where(*conditions))).scalar() or 0
        stmt = select(CostEvent).where(*conditions).order_by(CostEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total


# ============================================================
# 外汇交易 (Forex Transaction) — 基于 CostEvent + ExchangeRate
# ============================================================

class ForexTransactionService:
    """
    外汇交易应用服务

    底层使用 CostEventRepository + ExchangeRateRepository 操作数据。
    管理币种兑换交易和汇率预警。
    状态机: pending → completed / cancelled
    """

    def __init__(self, session: AsyncSession,
                 cost_event_repo: CostEventRepository | None = None,
                 exchange_rate_repo: ExchangeRateRepository | None = None):
        self._session = session
        self._cost_event_repo = cost_event_repo
        self._exchange_rate_repo = exchange_rate_repo

    async def create(self, tenant_id: str, forex_no: str, from_currency: str,
                     to_currency: str, amount: float, rate: float, **kwargs) -> CostEvent:
        """创建外汇交易记录: 领域校验 → 币种转换 → 唯一性校验 → 持久化"""
        errors = ForexDomainService.validate_forex_transaction(from_currency, to_currency, amount, rate)
        if errors:
            raise ValidationException(message="; ".join(errors))

        converted = ForexDomainService.convert_currency(amount, rate)

        if self._cost_event_repo:
            existing = await self._cost_event_repo.get_by_event_no(forex_no, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.event_no == forex_no, CostEvent.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Forex transaction '{forex_no}' already exists")

        event = CostEvent(
            tenant_id=tenant_id, event_no=forex_no, cost_type="other",
            amount=amount, currency=from_currency, exchange_rate=rate,
            amount_cny=converted if to_currency == "CNY" else 0,
            status="pending",
            remark=f"Forex: {from_currency}->{to_currency}, converted: {converted}",
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(CostEvent, k)},
        )
        if self._cost_event_repo:
            return await self._cost_event_repo.create(event)
        self._session.add(event)
        await self._session.flush()
        return event

    async def complete(self, forex_id: str, tenant_id: str) -> CostEvent:
        """完成外汇交易 (状态: pending → completed)"""
        if self._cost_event_repo:
            event = await self._cost_event_repo.get_by_id(forex_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == forex_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Forex transaction '{forex_id}' not found")
        if not ForexDomainService.can_transition(event.status, "completed"):
            raise ValidationException(message=f"Cannot complete forex in '{event.status}' status")
        event.status = "completed"
        if self._cost_event_repo:
            return await self._cost_event_repo.update(event)
        await self._session.flush()
        return event

    async def cancel(self, forex_id: str, tenant_id: str) -> CostEvent:
        """取消外汇交易 (状态: pending → cancelled)"""
        if self._cost_event_repo:
            event = await self._cost_event_repo.get_by_id(forex_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == forex_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Forex transaction '{forex_id}' not found")
        if not ForexDomainService.can_transition(event.status, "cancelled"):
            raise ValidationException(message=f"Cannot cancel forex in '{event.status}' status")
        event.status = "cancelled"
        if self._cost_event_repo:
            return await self._cost_event_repo.update(event)
        await self._session.flush()
        return event

    async def list_all(self, tenant_id: str, status: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[CostEvent], int]:
        """分页查询外汇交易列表"""
        conditions = [CostEvent.tenant_id == tenant_id, CostEvent.remark.contains("Forex")]
        if status:
            conditions.append(CostEvent.status == status)
        total = (await self._session.execute(select(sa_func.count()).select_from(CostEvent).where(*conditions))).scalar() or 0
        stmt = select(CostEvent).where(*conditions).order_by(CostEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def check_rate_alert(self, tenant_id: str, from_currency: str,
                                to_currency: str, current_rate: float) -> dict:
        """检查汇率预警: 对比当前汇率与历史汇率，判断是否触发预警阈值"""
        if self._exchange_rate_repo:
            prev = await self._exchange_rate_repo.get_latest(from_currency, to_currency, tenant_id)
        else:
            stmt = select(ExchangeRate).where(
                ExchangeRate.tenant_id == tenant_id,
                ExchangeRate.from_currency == from_currency,
                ExchangeRate.to_currency == to_currency,
            ).order_by(ExchangeRate.rate_date.desc()).limit(1)
            prev = (await self._session.execute(stmt)).scalar_one_or_none()

        if not prev:
            return {"alert": False, "message": "No previous rate found"}

        is_alert = ForexDomainService.is_rate_alert(current_rate, prev.rate)
        gain_loss = ForexDomainService.calculate_gain_loss(1000, prev.rate, current_rate)
        return {
            "alert": is_alert,
            "previous_rate": prev.rate,
            "current_rate": current_rate,
            "change_pct": round(abs(current_rate - prev.rate) / prev.rate * 100, 4),
            "sample_gain_loss_1000": gain_loss,
        }


# ============================================================
# 平台账单 (Platform Bill) — 基于 CostEvent 实体
# ============================================================

class PlatformBillService:
    """
    平台账单应用服务

    底层使用 CostEventRepository 操作 CostEvent 实体。
    管理各电商平台 (Amazon/Shopify/TikTok) 的账单导入和对账。
    状态机: pending → reconciled / disputed → reconciled
    """

    def __init__(self, session: AsyncSession, repo: CostEventRepository | None = None):
        self._session = session
        self._repo = repo

    async def create(self, tenant_id: str, bill_no: str, platform: str,
                     store: str, bill_type: str, amount: float,
                     currency: str = "USD", **kwargs) -> CostEvent:
        """创建平台账单: 领域校验 → 唯一性校验 → 持久化"""
        errors = PlatformBillDomainService.validate_platform_bill(platform, store, bill_type, amount, currency)
        if errors:
            raise ValidationException(message="; ".join(errors))

        if self._repo:
            existing = await self._repo.get_by_event_no(bill_no, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.event_no == bill_no, CostEvent.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Platform bill '{bill_no}' already exists")

        event = CostEvent(
            tenant_id=tenant_id, event_no=bill_no, cost_type=bill_type,
            amount=amount, currency=currency, status="pending",
            remark=f"Platform bill: {platform}/{bill_type}",
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(CostEvent, k)},
        )
        if self._repo:
            return await self._repo.create(event)
        self._session.add(event)
        await self._session.flush()
        return event

    async def get_by_id(self, bill_id: str, tenant_id: str) -> CostEvent | None:
        if self._repo:
            return await self._repo.get_by_id(bill_id, tenant_id)
        stmt = select(CostEvent).where(CostEvent.id == bill_id, CostEvent.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, bill_id: str, tenant_id: str) -> CostEvent:
        event = await self.get_by_id(bill_id, tenant_id)
        if not event:
            raise NotFoundException(message=f"Platform bill '{bill_id}' not found")
        return event

    async def reconcile(self, bill_id: str, tenant_id: str) -> CostEvent:
        """对账平台账单 (状态: pending → reconciled)"""
        if self._repo:
            event = await self._repo.get_by_id(bill_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == bill_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Platform bill '{bill_id}' not found")
        if not PlatformBillDomainService.can_transition(event.status, "reconciled"):
            raise ValidationException(message=f"Cannot reconcile bill in '{event.status}' status")
        event.status = "reconciled"
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def dispute(self, bill_id: str, tenant_id: str) -> CostEvent:
        """标记平台账单异议 (状态: pending → disputed)"""
        if self._repo:
            event = await self._repo.get_by_id(bill_id, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.id == bill_id, CostEvent.tenant_id == tenant_id)
            event = (await self._session.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundException(message=f"Platform bill '{bill_id}' not found")
        if not PlatformBillDomainService.can_transition(event.status, "disputed"):
            raise ValidationException(message=f"Cannot dispute bill in '{event.status}' status")
        event.status = "disputed"
        if self._repo:
            return await self._repo.update(event)
        await self._session.flush()
        return event

    async def list_all(self, tenant_id: str, platform: str = "", status: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[CostEvent], int]:
        """分页查询平台账单列表"""
        conditions = [CostEvent.tenant_id == tenant_id, CostEvent.remark.contains("Platform bill")]
        if platform:
            conditions.append(CostEvent.remark.contains(platform))
        if status:
            conditions.append(CostEvent.status == status)
        total = (await self._session.execute(select(sa_func.count()).select_from(CostEvent).where(*conditions))).scalar() or 0
        stmt = select(CostEvent).where(*conditions).order_by(CostEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total


# ============================================================
# 会计分录 (Journal Entry) — 基于 CostEvent 实体
# ============================================================

class JournalEntryService:
    """
    会计分录应用服务

    底层使用 CostEventRepository 操作 CostEvent 实体。
    管理采购/销售/费用/收入/外汇/结算/库存等各类会计分录。
    支持自动生成库存凭证和金蝶推送。
    """

    def __init__(self, session: AsyncSession, repo: CostEventRepository | None = None):
        self._session = session
        self._repo = repo

    async def create(self, tenant_id: str, entry_no: str, entry_type: str,
                     debit_account: str = "", credit_account: str = "", amount: float = 0,
                     currency: str = "CNY", **kwargs) -> CostEvent:
        """创建会计分录: 领域校验 → 唯一性校验 → 持久化"""
        if debit_account and credit_account:
            errors = JournalEntryDomainService.validate_entry(entry_type, debit_account, credit_account, amount, currency)
            if errors:
                raise ValidationException(message="; ".join(errors))

        if self._repo:
            existing = await self._repo.get_by_event_no(entry_no, tenant_id)
        else:
            stmt = select(CostEvent).where(CostEvent.event_no == entry_no, CostEvent.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Journal entry '{entry_no}' already exists")

        remark = f"Journal: {debit_account}<->{credit_account}" if debit_account and credit_account else f"Journal: {entry_type}"
        event = CostEvent(
            tenant_id=tenant_id, event_no=entry_no, cost_type=entry_type,
            amount=amount, currency=currency, status="confirmed",
            remark=remark,
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(CostEvent, k)},
        )
        if self._repo:
            return await self._repo.create(event)
        self._session.add(event)
        await self._session.flush()
        return event

    async def generate_inventory_voucher(self, tenant_id: str, voucher_no: str,
                                          business_type: str, sku: str,
                                          quantity: int, unit_cost: float,
                                          ref_type: str, ref_id: str,
                                          period: str) -> CostEvent:
        """
        自动生成库存凭证

        根据业务类型自动映射到会计分录类型:
          purchase_inbound→inventory_in, sales_outbound→inventory_out,
          inventory_adjustment→inventory_adjust 等
        """
        entry_data = VoucherEngineDomainService.auto_generate_inventory_voucher(
            business_type, sku, quantity, unit_cost, ref_type, ref_id, period,
        )
        return await self.create(
            tenant_id=tenant_id, entry_no=voucher_no,
            entry_type=entry_data["entry_type"],
            debit_account=entry_data["debit_account"],
            credit_account=entry_data["credit_account"],
            amount=entry_data["amount"],
            currency=entry_data["currency"],
            reference_type=ref_type, reference_id=ref_id,
        )

    async def generate_kingdee_push(self, tenant_id: str, entry_ids: list[str]) -> dict:
        """生成金蝶推送数据: 将指定会计分录组装为金蝶系统可接收的推送格式"""
        entries: list[dict] = []
        for eid in entry_ids:
            if self._repo:
                event = await self._repo.get_by_id(eid, tenant_id)
            else:
                stmt = select(CostEvent).where(CostEvent.id == eid, CostEvent.tenant_id == tenant_id)
                event = (await self._session.execute(stmt)).scalar_one_or_none()
            if event:
                entries.append({"amount": event.amount, "cost_type": event.cost_type,
                                "remark": event.remark})
        return VoucherEngineDomainService.generate_kingdee_push_data(entries)

    async def list_all(self, tenant_id: str, entry_type: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[CostEvent], int]:
        """分页查询会计分录列表"""
        conditions = [CostEvent.tenant_id == tenant_id, CostEvent.remark.contains("Journal")]
        if entry_type:
            conditions.append(CostEvent.cost_type == entry_type)
        total = (await self._session.execute(select(sa_func.count()).select_from(CostEvent).where(*conditions))).scalar() or 0
        stmt = select(CostEvent).where(*conditions).order_by(CostEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total


# ============================================================
# 汇率 (Exchange Rate)
# ============================================================

class ExchangeRateService:
    """
    汇率应用服务

    通过 ExchangeRateRepository 仓储接口操作数据。
    管理各币种间的汇率记录，支持手动录入和API自动获取。
    """

    def __init__(self, session: AsyncSession, repo: ExchangeRateRepository | None = None):
        self._session = session
        self._repo = repo

    async def create(self, tenant_id: str, from_currency: str, to_currency: str,
                     rate: float, rate_date, source: str = "manual") -> ExchangeRate:
        """创建汇率记录"""
        if rate <= 0:
            raise ValidationException(message="Exchange rate must be positive")

        er = ExchangeRate(
            tenant_id=tenant_id, from_currency=from_currency,
            to_currency=to_currency, rate=rate,
            rate_date=rate_date, source=source,
        )
        if self._repo:
            return await self._repo.create(er)
        self._session.add(er)
        await self._session.flush()
        return er

    async def get_latest(self, tenant_id: str, from_currency: str, to_currency: str) -> ExchangeRate | None:
        """查询最新汇率"""
        if self._repo:
            return await self._repo.get_latest(from_currency, to_currency, tenant_id)
        stmt = select(ExchangeRate).where(
            ExchangeRate.tenant_id == tenant_id,
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
        ).order_by(ExchangeRate.rate_date.desc()).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_history(self, tenant_id: str, from_currency: str = "",
                           to_currency: str = "", rate_date=None) -> Sequence[ExchangeRate]:
        """
        查询汇率历史记录

        Args:
            tenant_id: 租户ID
            from_currency: 源币种筛选 (可选)
            to_currency: 目标币种筛选 (可选)
            rate_date: 指定日期筛选 (可选)

        Returns:
            Sequence[ExchangeRate]: 汇率记录列表
        """
        if self._repo:
            all_rates = await self._repo.list_by_tenant(tenant_id, rate_date=rate_date)
            if from_currency:
                all_rates = [r for r in all_rates if r.from_currency == from_currency]
            if to_currency:
                all_rates = [r for r in all_rates if r.to_currency == to_currency]
            return all_rates
        conditions = [ExchangeRate.tenant_id == tenant_id]
        if from_currency:
            conditions.append(ExchangeRate.from_currency == from_currency)
        if to_currency:
            conditions.append(ExchangeRate.to_currency == to_currency)
        if rate_date:
            conditions.append(ExchangeRate.rate_date == rate_date)
        stmt = select(ExchangeRate).where(*conditions).order_by(ExchangeRate.rate_date.desc())
        return (await self._session.execute(stmt)).scalars().all()


# ============================================================
# 利润计算 (Profit Calculation) — 复杂聚合查询，保留 Session
# ============================================================

class ProfitCalculationService:
    """
    利润计算应用服务

    复杂聚合查询服务，涉及多表 JOIN 和 SUM/GROUP BY 等操作，
    保留 Session 直接操作，不通过仓储接口。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def calculate_order_profit(self, tenant_id: str, order_id: str) -> dict:
        """计算订单利润: 从成本事件中聚合计算指定订单的收入、成本和利润率"""
        revenue_stmt = select(sa_func.coalesce(sa_func.sum(CostEvent.amount_cny), 0)).where(
            CostEvent.tenant_id == tenant_id,
            CostEvent.reference_type == "order",
            CostEvent.reference_id == order_id,
            CostEvent.cost_type == "product_cost",
        )
        revenue = float((await self._session.execute(revenue_stmt)).scalar() or 0)

        cost_stmt = select(sa_func.coalesce(sa_func.sum(CostEvent.amount_cny), 0)).where(
            CostEvent.tenant_id == tenant_id,
            CostEvent.reference_type == "order",
            CostEvent.reference_id == order_id,
        )
        total_cost = float((await self._session.execute(cost_stmt)).scalar() or 0)

        other_costs = total_cost - revenue
        profit = revenue - total_cost
        margin = (profit / revenue * 100) if revenue > 0 else 0.0

        return {
            "order_id": order_id,
            "revenue": revenue,
            "product_cost": revenue,
            "other_costs": other_costs,
            "total_cost": total_cost,
            "profit": profit,
            "margin_pct": round(margin, 2),
        }

    async def calculate_sku_profit(self, tenant_id: str, sku_id: str) -> dict:
        """计算SKU利润: 按成本类型分组聚合计算指定SKU的成本构成"""
        cost_stmt = select(
            CostEvent.cost_type,
            sa_func.coalesce(sa_func.sum(CostEvent.amount_cny), 0),
        ).where(
            CostEvent.tenant_id == tenant_id,
            CostEvent.sku_id == sku_id,
        ).group_by(CostEvent.cost_type)

        rows = (await self._session.execute(cost_stmt)).all()
        cost_breakdown = {row[0]: float(row[1]) for row in rows}
        total_cost = sum(cost_breakdown.values())
        product_cost = cost_breakdown.get("product_cost", 0.0)
        other_costs = total_cost - product_cost

        return {
            "sku_id": sku_id,
            "cost_breakdown": cost_breakdown,
            "product_cost": product_cost,
            "other_costs": other_costs,
            "total_cost": total_cost,
        }


# ============================================================
# 成本分解 (Cost Breakdown) — 复杂聚合查询，保留 Session
# ============================================================

class CostBreakdownService:
    """
    成本分解应用服务

    复杂聚合查询服务，按成本类型分组计算SKU的成本构成和占比。
    保留 Session 直接操作。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def calculate(self, tenant_id: str, sku_id: str) -> dict:
        """计算SKU成本分解: 从成本事件中按类型聚合，计算各项成本占比"""
        cost_stmt = select(
            CostEvent.cost_type,
            sa_func.coalesce(sa_func.sum(CostEvent.amount_cny), 0),
        ).where(
            CostEvent.tenant_id == tenant_id,
            CostEvent.sku_id == sku_id,
        ).group_by(CostEvent.cost_type)
        rows = (await self._session.execute(cost_stmt)).all()
        cost_map = {row[0]: float(row[1]) for row in rows}
        total = CostBreakdownDomainService.calculate_total(
            bom_cost=cost_map.get("product_cost", 0),
            shipping_cost=cost_map.get("shipping_cost", 0),
            fba_fees=cost_map.get("warehouse_fee", 0),
            tariff=cost_map.get("customs_duty", 0),
            advertising_cost=cost_map.get("ad_spend", 0),
            storage_cost=cost_map.get("warehouse_fee", 0) * 0.3,
            return_cost=cost_map.get("return_cost", 0),
            labor_cost=cost_map.get("other", 0) * 0.5,
            other_costs=cost_map.get("other", 0) * 0.5,
        )
        percentages = {k: CostBreakdownDomainService.calculate_cost_percentage(v, total)
                       for k, v in cost_map.items()}
        return {"sku_id": sku_id, "cost_map": cost_map, "total_cost": total, "percentages": percentages}


# ============================================================
# 增强利润计算 (Profit Calculation Enhanced) — 复杂聚合查询，保留 Session
# ============================================================

class ProfitCalculationEnhancedService:
    """
    增强利润计算应用服务

    复杂聚合查询服务，支持净利润/毛利率/ROI/FIFO成本等高级计算。
    保留 Session 直接操作。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def calculate(self, tenant_id: str, sku_id: str,
                        revenue: float, refund_amount: float = 0,
                        operating_expenses: float = 0) -> dict:
        """计算SKU增强利润: 综合计算净利润、毛利率、ROI，并判断是否触发利润预警"""
        cost_stmt = select(sa_func.coalesce(sa_func.sum(CostEvent.amount_cny), 0)).where(
            CostEvent.tenant_id == tenant_id,
            CostEvent.sku_id == sku_id,
        )
        total_cost = float((await self._session.execute(cost_stmt)).scalar() or 0)
        result = ProfitDomainService.calculate_profit(revenue, refund_amount, total_cost, operating_expenses)
        result["sku_id"] = sku_id
        result["profit_alert"] = ProfitDomainService.is_profit_alert(result["net_margin"])
        return result

    async def calculate_fifo(self, tenant_id: str, sku_id: str,
                              quantity_sold: int) -> dict:
        """计算FIFO成本: 按先进先出法计算指定数量销售的成本"""
        cost_stmt = select(CostEvent).where(
            CostEvent.tenant_id == tenant_id,
            CostEvent.sku_id == sku_id,
            CostEvent.cost_type == "product_cost",
        ).order_by(CostEvent.occurred_date.asc())
        rows = (await self._session.execute(cost_stmt)).scalars().all()
        layers = [{"date": str(r.occurred_date or ""), "quantity": int(r.amount),
                    "unit_cost": float(r.exchange_rate or 1)} for r in rows]
        fifo_cost = ProfitDomainService.calculate_fifo_cost(layers, quantity_sold)
        return {"sku_id": sku_id, "quantity_sold": quantity_sold, "fifo_cost": fifo_cost}


# ============================================================
# FMS 统计查询服务 (FMS Query Service)
# ============================================================

class FMSQueryService:
    """
    FMS 统计查询服务

    提供财务模块的运营统计概览、各子域统计数据聚合。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_statistics(self, tenant_id: str) -> dict:
        """获取FMS运营统计概览"""
        cost_event_count = (await self._session.execute(
            select(sa_func.count()).select_from(CostEvent).where(CostEvent.tenant_id == tenant_id)
        )).scalar() or 0

        cost_by_type_rows = (await self._session.execute(
            select(CostEvent.cost_type, sa_func.count()).where(CostEvent.tenant_id == tenant_id).group_by(CostEvent.cost_type)
        )).all()
        cost_event_by_type = {r[0]: r[1] for r in cost_by_type_rows}

        cost_by_status_rows = (await self._session.execute(
            select(CostEvent.status, sa_func.count()).where(CostEvent.tenant_id == tenant_id).group_by(CostEvent.status)
        )).all()
        cost_event_by_status = {r[0]: r[1] for r in cost_by_status_rows}

        total_cost_cny = float((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(CostEvent.amount_cny), 0)).where(CostEvent.tenant_id == tenant_id)
        )).scalar() or 0)

        settlement_count = (await self._session.execute(
            select(sa_func.count()).select_from(PlatformSettlement).where(PlatformSettlement.tenant_id == tenant_id)
        )).scalar() or 0

        settlement_by_status_rows = (await self._session.execute(
            select(PlatformSettlement.status, sa_func.count()).where(PlatformSettlement.tenant_id == tenant_id).group_by(PlatformSettlement.status)
        )).all()
        settlement_by_status = {r[0]: r[1] for r in settlement_by_status_rows}

        total_settlement_amount = float((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(PlatformSettlement.net_amount), 0)).where(PlatformSettlement.tenant_id == tenant_id)
        )).scalar() or 0)

        payment_count = (await self._session.execute(
            select(sa_func.count()).select_from(PaymentRecord).where(PaymentRecord.tenant_id == tenant_id)
        )).scalar() or 0

        payment_by_status_rows = (await self._session.execute(
            select(PaymentRecord.status, sa_func.count()).where(PaymentRecord.tenant_id == tenant_id).group_by(PaymentRecord.status)
        )).all()
        payment_by_status = {r[0]: r[1] for r in payment_by_status_rows}

        total_payment_amount = float((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(PaymentRecord.amount), 0)).where(PaymentRecord.tenant_id == tenant_id)
        )).scalar() or 0)

        pending_payment_count = (await self._session.execute(
            select(sa_func.count()).select_from(PaymentRecord).where(
                PaymentRecord.tenant_id == tenant_id, PaymentRecord.status == "pending")
        )).scalar() or 0

        payment_request_count = payment_count
        pending_approval_count = (await self._session.execute(
            select(sa_func.count()).select_from(PaymentRecord).where(
                PaymentRecord.tenant_id == tenant_id, PaymentRecord.status == "pending_approval")
        )).scalar() or 0

        return {
            "cost_event_count": cost_event_count,
            "cost_event_by_type": cost_event_by_type,
            "cost_event_by_status": cost_event_by_status,
            "total_cost_cny": total_cost_cny,
            "settlement_count": settlement_count,
            "settlement_by_status": settlement_by_status,
            "total_settlement_amount": total_settlement_amount,
            "payment_count": payment_count,
            "payment_by_status": payment_by_status,
            "total_payment_amount": total_payment_amount,
            "pending_payment_count": pending_payment_count,
            "payment_request_count": payment_request_count,
            "pending_approval_count": pending_approval_count,
        }

    async def get_cost_event_statistics(self, tenant_id: str) -> dict:
        """获取成本事件统计"""
        total = (await self._session.execute(
            select(sa_func.count()).select_from(CostEvent).where(CostEvent.tenant_id == tenant_id)
        )).scalar() or 0

        by_type_rows = (await self._session.execute(
            select(CostEvent.cost_type, sa_func.count(), sa_func.coalesce(sa_func.sum(CostEvent.amount_cny), 0))
            .where(CostEvent.tenant_id == tenant_id).group_by(CostEvent.cost_type)
        )).all()
        by_type = {r[0]: {"count": r[1], "total_amount": float(r[2])} for r in by_type_rows}

        by_status_rows = (await self._session.execute(
            select(CostEvent.status, sa_func.count()).where(CostEvent.tenant_id == tenant_id).group_by(CostEvent.status)
        )).all()
        by_status = {r[0]: r[1] for r in by_status_rows}

        total_amount = float((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(CostEvent.amount_cny), 0)).where(CostEvent.tenant_id == tenant_id)
        )).scalar() or 0)

        return {"total": total, "by_type": by_type, "by_status": by_status, "total_amount_cny": total_amount}

    async def get_settlement_statistics(self, tenant_id: str) -> dict:
        """获取平台结算统计"""
        total = (await self._session.execute(
            select(sa_func.count()).select_from(PlatformSettlement).where(PlatformSettlement.tenant_id == tenant_id)
        )).scalar() or 0

        by_platform_rows = (await self._session.execute(
            select(PlatformSettlement.platform, sa_func.count(), sa_func.coalesce(sa_func.sum(PlatformSettlement.net_amount), 0))
            .where(PlatformSettlement.tenant_id == tenant_id).group_by(PlatformSettlement.platform)
        )).all()
        by_platform = {r[0]: {"count": r[1], "total_amount": float(r[2])} for r in by_platform_rows}

        by_status_rows = (await self._session.execute(
            select(PlatformSettlement.status, sa_func.count()).where(PlatformSettlement.tenant_id == tenant_id).group_by(PlatformSettlement.status)
        )).all()
        by_status = {r[0]: r[1] for r in by_status_rows}

        total_amount = float((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(PlatformSettlement.net_amount), 0)).where(PlatformSettlement.tenant_id == tenant_id)
        )).scalar() or 0)

        return {"total": total, "by_platform": by_platform, "by_status": by_status, "total_amount": total_amount}

    async def get_payment_statistics(self, tenant_id: str) -> dict:
        """获取付款统计"""
        total = (await self._session.execute(
            select(sa_func.count()).select_from(PaymentRecord).where(PaymentRecord.tenant_id == tenant_id)
        )).scalar() or 0

        by_status_rows = (await self._session.execute(
            select(PaymentRecord.status, sa_func.count(), sa_func.coalesce(sa_func.sum(PaymentRecord.amount), 0))
            .where(PaymentRecord.tenant_id == tenant_id).group_by(PaymentRecord.status)
        )).all()
        by_status = {r[0]: {"count": r[1], "total_amount": float(r[2])} for r in by_status_rows}

        total_amount = float((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(PaymentRecord.amount), 0)).where(PaymentRecord.tenant_id == tenant_id)
        )).scalar() or 0)

        pending_count = (await self._session.execute(
            select(sa_func.count()).select_from(PaymentRecord).where(
                PaymentRecord.tenant_id == tenant_id, PaymentRecord.status == "pending")
        )).scalar() or 0

        return {"total": total, "by_status": by_status, "total_amount": total_amount, "pending_count": pending_count}


class AutoReconciliationService:
    """
    自动对账服务

    编排自动对账流程: 平台账单导入 → 本地订单匹配 → 差异检测 → 自动/人工处理
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def reconcile_settlement(self, tenant_id: str, settlement_id: str) -> dict:
        """
        对账单笔结算

        流程: 查询结算单 → 匹配本地订单 → 计算差异 → 生成对账结果
        """
        settlement = (await self._session.execute(
            select(PlatformSettlement).where(
                PlatformSettlement.id == settlement_id, PlatformSettlement.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not settlement:
            raise NotFoundException(message=f"Settlement '{settlement_id}' not found")
        matched_orders = await self._match_orders(tenant_id, settlement)
        total_matched = sum(o.get("amount", 0) for o in matched_orders)
        difference = float(settlement.net_amount or 0) - total_matched
        result = {
            "settlement_id": settlement_id, "settlement_amount": float(settlement.net_amount or 0),
            "matched_order_count": len(matched_orders), "matched_total": round(total_matched, 2),
            "difference": round(difference, 2),
            "status": "matched" if abs(difference) < 0.01 else "discrepancy",
        }
        if abs(difference) < 0.01 and settlement.status == "pending":
            settlement.status = "reconciled"
            await self._session.flush()
        return result

    async def batch_reconcile(self, tenant_id: str, platform: str = "",
                               period_start=None, period_end=None) -> dict:
        """批量自动对账"""
        conditions = [PlatformSettlement.tenant_id == tenant_id, PlatformSettlement.status == "pending"]
        if platform:
            conditions.append(PlatformSettlement.platform == platform)
        if period_start:
            conditions.append(PlatformSettlement.settlement_date >= period_start)
        if period_end:
            conditions.append(PlatformSettlement.settlement_date <= period_end)
        settlements = (await self._session.execute(
            select(PlatformSettlement).where(*conditions)
        )).scalars().all()
        results = {"total": len(settlements), "matched": 0, "discrepancy": 0, "details": []}
        for s in settlements:
            try:
                r = await self.reconcile_settlement(tenant_id, str(s.id))
                results["details"].append(r)
                if r["status"] == "matched":
                    results["matched"] += 1
                else:
                    results["discrepancy"] += 1
            except Exception:
                results["discrepancy"] += 1
        return results

    async def _match_orders(self, tenant_id: str, settlement: PlatformSettlement) -> list[dict]:
        try:
            from erp.shared.cross_domain_query import OrderQueryService
            orders = (await self._session.execute(
                select(SalesOrder).where(
                    SalesOrder.tenant_id == tenant_id,
                    SalesOrder.platform == settlement.platform,
                    SalesOrder.store_id == settlement.store_id,
                ).order_by(SalesOrder.created_at.desc()).limit(50)
            )).scalars().all()
            return [{"order_id": str(o.id), "order_no": o.order_no, "amount": float(o.item_subtotal or 0)} for o in orders]
        except Exception:
            return []


class ProfitAlertService:
    """
    利润预警服务

    多维度利润监控: SKU利润率/订单利润/店铺利润 → 预警阈值检测 → 通知
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def scan_profit_alerts(self, tenant_id: str,
                                  min_profit_rate: float = 5.0,
                                  loss_threshold: float = -100.0) -> dict:
        """
        扫描利润预警

        流程: 汇总各维度利润 → 阈值检测 → 分级预警
        """
        alerts = []
        alerts.extend(await self._scan_sku_profit(tenant_id, min_profit_rate, loss_threshold))
        alerts.extend(await self._scan_store_profit(tenant_id, min_profit_rate))
        alerts.sort(key=lambda x: {"critical": 0, "warning": 1, "info": 2}.get(x["severity"], 3))
        return {
            "total_alerts": len(alerts),
            "critical_count": sum(1 for a in alerts if a["severity"] == "critical"),
            "warning_count": sum(1 for a in alerts if a["severity"] == "warning"),
            "alerts": alerts,
        }

    async def _scan_sku_profit(self, tenant_id: str, min_rate: float, loss_threshold: float) -> list[dict]:
        alerts = []
        try:
            cost_events = (await self._session.execute(
                select(CostEvent.sku_id, sa_func.sum(CostEvent.amount_cny)).where(
                    CostEvent.tenant_id == tenant_id, CostEvent.sku_id != ""
                ).group_by(CostEvent.sku_id)
            )).all()
            for sku_id, total_cost in cost_events:
                if total_cost > 0:
                    profit_rate = 0
                    if profit_rate < min_rate and total_cost > abs(loss_threshold):
                        severity = "critical" if profit_rate < 0 else "warning"
                        alerts.append({
                            "type": "low_sku_profit", "severity": severity,
                            "sku_id": sku_id, "total_cost": float(total_cost),
                            "profit_rate": round(profit_rate, 2),
                            "message": f"SKU {sku_id} 利润率 {profit_rate:.1f}% 低于阈值 {min_rate}%",
                        })
        except Exception:
            pass
        return alerts

    async def _scan_store_profit(self, tenant_id: str, min_rate: float) -> list[dict]:
        alerts = []
        try:
            settlements = (await self._session.execute(
                select(PlatformSettlement.store_id, sa_func.sum(PlatformSettlement.net_amount)).where(
                    PlatformSettlement.tenant_id == tenant_id, PlatformSettlement.store_id != ""
                ).group_by(PlatformSettlement.store_id)
            )).all()
            for store_id, net_amount in settlements:
                if net_amount and float(net_amount) < 0:
                    alerts.append({
                        "type": "negative_store_profit", "severity": "critical",
                        "store_id": store_id, "net_amount": float(net_amount),
                        "message": f"店铺 {store_id} 净利润为负: {float(net_amount):.2f}",
                    })
        except Exception:
            pass
        return alerts


class CashFlowService:
    """
    资金流水服务

    编排资金流水管理: 收支流水登记/余额计算/现金流预测
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_cash_flow_summary(self, tenant_id: str, period_days: int = 30) -> dict:
        """
        获取资金流水摘要

        流程: 汇总收入/支出 → 计算净流 → 余额估算
        """
        from datetime import timedelta
        cutoff = datetime.now(UTC) - timedelta(days=period_days)
        total_income = float((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(PlatformSettlement.net_amount), 0)).where(
                PlatformSettlement.tenant_id == tenant_id,
                PlatformSettlement.status == "reconciled",
                PlatformSettlement.settlement_date >= cutoff)
        )).scalar() or 0)
        total_expense = float((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(PaymentRecord.amount), 0)).where(
                PaymentRecord.tenant_id == tenant_id,
                PaymentRecord.status == "completed",
                PaymentRecord.paid_at >= cutoff)
        )).scalar() or 0)
        net_flow = total_income - total_expense
        pending_income = float((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(PlatformSettlement.net_amount), 0)).where(
                PlatformSettlement.tenant_id == tenant_id,
                PlatformSettlement.status == "pending")
        )).scalar() or 0)
        pending_expense = float((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(PaymentRecord.amount), 0)).where(
                PaymentRecord.tenant_id == tenant_id,
                PaymentRecord.status.in_(["pending", "pending_approval"]))
        )).scalar() or 0)
        return {
            "period_days": period_days,
            "total_income": round(total_income, 2),
            "total_expense": round(total_expense, 2),
            "net_flow": round(net_flow, 2),
            "pending_income": round(pending_income, 2),
            "pending_expense": round(pending_expense, 2),
            "projected_balance": round(net_flow + pending_income - pending_expense, 2),
        }

    async def forecast_cash_flow(self, tenant_id: str, forecast_days: int = 30) -> dict:
        """现金流预测"""
        from datetime import timedelta
        cutoff_30d = datetime.now(UTC) - timedelta(days=30)
        avg_daily_income = float((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(PlatformSettlement.net_amount), 0)).where(
                PlatformSettlement.tenant_id == tenant_id,
                PlatformSettlement.status == "reconciled",
                PlatformSettlement.settlement_date >= cutoff_30d)
        )).scalar() or 0) / 30.0
        avg_daily_expense = float((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(PaymentRecord.amount), 0)).where(
                PaymentRecord.tenant_id == tenant_id,
                PaymentRecord.status == "completed",
                PaymentRecord.paid_at >= cutoff_30d)
        )).scalar() or 0) / 30.0
        projected_income = avg_daily_income * forecast_days
        projected_expense = avg_daily_expense * forecast_days
        return {
            "forecast_days": forecast_days,
            "avg_daily_income": round(avg_daily_income, 2),
            "avg_daily_expense": round(avg_daily_expense, 2),
            "projected_income": round(projected_income, 2),
            "projected_expense": round(projected_expense, 2),
            "projected_net": round(projected_income - projected_expense, 2),
            "risk_level": "high" if projected_net < 0 else "medium" if projected_net < projected_expense * 0.1 else "low",
        }


from datetime import UTC, datetime
