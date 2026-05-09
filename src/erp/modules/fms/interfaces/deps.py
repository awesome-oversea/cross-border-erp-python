"""
FMS (财务域) 依赖注入工厂

所有 Service 和 Repository 实例通过 FastAPI Depends() 链式注入，
禁止在 router 中手动实例化 Service。

注入链路 (铁律):
  router → Depends(get_xxx_service) → Service(session, repo) → Repository(session)

仓储注入规则:
  - CostEventRepository: 被 CostEventService / WriteOffService / ReconciliationService /
    InvoiceService / ExpenseService / JournalEntryService / PlatformBillService 共享
  - PlatformSettlementRepository: 被 PlatformSettlementService 使用
  - PaymentRecordRepository: 被 PaymentRecordService / PaymentRequestService 共享
  - ExchangeRateRepository: 被 ExchangeRateService / ForexTransactionService 共享
  - ProfitCalculationService / CostBreakdownService / ProfitCalculationEnhancedService:
    复杂聚合查询，仅注入 Session，不通过仓储接口
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.fms.application.services import (
    CostBreakdownService,
    CostEventService,
    ExchangeRateService,
    ExpenseService,
    FMSQueryService,
    ForexTransactionService,
    InvoiceService,
    JournalEntryService,
    PaymentRecordService,
    PaymentRequestService,
    PlatformBillService,
    PlatformSettlementService,
    ProfitCalculationEnhancedService,
    ProfitCalculationService,
    ReconciliationService,
    WriteOffService,
)
from erp.modules.fms.domain.voucher_models import VoucherEngineService
from erp.modules.fms.domain.repositories import (
    CostEventRepository,
    ExchangeRateRepository,
    PaymentRecordRepository,
    PlatformSettlementRepository,
)
from erp.modules.fms.infrastructure.repositories import (
    SqlCostEventRepository,
    SqlExchangeRateRepository,
    SqlPaymentRecordRepository,
    SqlPlatformSettlementRepository,
)
from erp.shared.context import TenantContext, tenant_id_var
from erp.shared.db.session import get_db_session


# ============================================================
# 仓储工厂: Session → Repository 实例
# FastAPI 会自动缓存同一请求内相同依赖的结果，因此同一请求中
# 多个服务共享同一仓储实例时，Session 不会重复创建。
# ============================================================

def _cost_event_repo(session: AsyncSession = Depends(get_db_session)) -> CostEventRepository:
    """创建成本事件仓储实例 — 被7个服务共享 (CostEvent/WriteOff/Reconciliation/Invoice/Expense/JournalEntry/PlatformBill)"""
    return SqlCostEventRepository(session)


def _platform_settlement_repo(session: AsyncSession = Depends(get_db_session)) -> PlatformSettlementRepository:
    """创建平台结算仓储实例 — 被 PlatformSettlementService 使用"""
    return SqlPlatformSettlementRepository(session)


def _payment_record_repo(session: AsyncSession = Depends(get_db_session)) -> PaymentRecordRepository:
    """创建付款记录仓储实例 — 被 PaymentRecordService / PaymentRequestService 共享"""
    return SqlPaymentRecordRepository(session)


def _exchange_rate_repo(session: AsyncSession = Depends(get_db_session)) -> ExchangeRateRepository:
    """创建汇率仓储实例 — 被 ExchangeRateService / ForexTransactionService 共享"""
    return SqlExchangeRateRepository(session)


# ============================================================
# 服务工厂: Session + Repository → Service 实例
# 每个服务工厂通过 Depends() 注入对应的仓储实例，
# 确保服务层通过仓储接口操作数据，而非直接使用 Session。
# ============================================================

def get_cost_event_service(
    session: AsyncSession = Depends(get_db_session),
    repo: CostEventRepository = Depends(_cost_event_repo),
) -> CostEventService:
    """获取成本事件服务实例 — 注入 CostEventRepository"""
    return CostEventService(session=session, repo=repo)


def get_platform_settlement_service(
    session: AsyncSession = Depends(get_db_session),
    repo: PlatformSettlementRepository = Depends(_platform_settlement_repo),
) -> PlatformSettlementService:
    """获取平台结算服务实例 — 注入 PlatformSettlementRepository"""
    return PlatformSettlementService(session=session, repo=repo)


def get_payment_record_service(
    session: AsyncSession = Depends(get_db_session),
    repo: PaymentRecordRepository = Depends(_payment_record_repo),
) -> PaymentRecordService:
    """获取付款记录服务实例 — 注入 PaymentRecordRepository"""
    return PaymentRecordService(session=session, repo=repo)


def get_payment_request_service(
    session: AsyncSession = Depends(get_db_session),
    repo: PaymentRecordRepository = Depends(_payment_record_repo),
) -> PaymentRequestService:
    """获取付款申请服务实例 — 注入 PaymentRecordRepository (与 PaymentRecordService 共享同一仓储)"""
    return PaymentRequestService(session=session, repo=repo)


def get_write_off_service(
    session: AsyncSession = Depends(get_db_session),
    repo: CostEventRepository = Depends(_cost_event_repo),
) -> WriteOffService:
    """获取核销服务实例 — 注入 CostEventRepository (核销底层操作 CostEvent 实体)"""
    return WriteOffService(session=session, repo=repo)


def get_reconciliation_service(
    session: AsyncSession = Depends(get_db_session),
    repo: CostEventRepository = Depends(_cost_event_repo),
) -> ReconciliationService:
    """获取对账服务实例 — 注入 CostEventRepository (对账底层操作 CostEvent 实体)"""
    return ReconciliationService(session=session, repo=repo)


def get_invoice_service(
    session: AsyncSession = Depends(get_db_session),
    repo: CostEventRepository = Depends(_cost_event_repo),
) -> InvoiceService:
    """获取发票服务实例 — 注入 CostEventRepository (发票底层操作 CostEvent 实体)"""
    return InvoiceService(session=session, repo=repo)


def get_expense_service(
    session: AsyncSession = Depends(get_db_session),
    repo: CostEventRepository = Depends(_cost_event_repo),
) -> ExpenseService:
    """获取费用服务实例 — 注入 CostEventRepository (费用底层操作 CostEvent 实体)"""
    return ExpenseService(session=session, repo=repo)


def get_journal_entry_service(
    session: AsyncSession = Depends(get_db_session),
    repo: CostEventRepository = Depends(_cost_event_repo),
) -> JournalEntryService:
    """获取会计分录服务实例 — 注入 CostEventRepository (分录底层操作 CostEvent 实体)"""
    return JournalEntryService(session=session, repo=repo)


def get_platform_bill_service(
    session: AsyncSession = Depends(get_db_session),
    repo: CostEventRepository = Depends(_cost_event_repo),
) -> PlatformBillService:
    """获取平台账单服务实例 — 注入 CostEventRepository (账单底层操作 CostEvent 实体)"""
    return PlatformBillService(session=session, repo=repo)


def get_exchange_rate_service(
    session: AsyncSession = Depends(get_db_session),
    repo: ExchangeRateRepository = Depends(_exchange_rate_repo),
) -> ExchangeRateService:
    """获取汇率服务实例 — 注入 ExchangeRateRepository"""
    return ExchangeRateService(session=session, repo=repo)


def get_forex_transaction_service(
    session: AsyncSession = Depends(get_db_session),
    cost_event_repo: CostEventRepository = Depends(_cost_event_repo),
    exchange_rate_repo: ExchangeRateRepository = Depends(_exchange_rate_repo),
) -> ForexTransactionService:
    """获取外汇交易服务实例 — 注入 CostEventRepository + ExchangeRateRepository (双仓储)"""
    return ForexTransactionService(
        session=session,
        cost_event_repo=cost_event_repo,
        exchange_rate_repo=exchange_rate_repo,
    )


# ============================================================
# 复杂聚合查询服务 — 仅注入 Session，不通过仓储接口
# 这些服务涉及多表 JOIN / SUM / GROUP BY 等复杂查询，
# 仓储接口的 CRUD 粒度无法满足，保留 Session 直接操作。
# ============================================================

def get_profit_calculation_service(
    session: AsyncSession = Depends(get_db_session),
) -> ProfitCalculationService:
    """获取利润计算服务实例 — 复杂聚合查询，仅注入 Session"""
    return ProfitCalculationService(session=session)


def get_profit_calculation_enhanced_service(
    session: AsyncSession = Depends(get_db_session),
) -> ProfitCalculationEnhancedService:
    """获取增强利润计算服务实例 — 复杂聚合查询，仅注入 Session"""
    return ProfitCalculationEnhancedService(session=session)


def get_cost_breakdown_service(
    session: AsyncSession = Depends(get_db_session),
) -> CostBreakdownService:
    """获取成本分解服务实例 — 复杂聚合查询，仅注入 Session"""
    return CostBreakdownService(session=session)


def get_fms_query_service(
    session: AsyncSession = Depends(get_db_session),
) -> FMSQueryService:
    """获取FMS统计查询服务实例 — 复杂聚合查询，仅注入 Session"""
    return FMSQueryService(session=session)


def get_voucher_engine_service(
    session: AsyncSession = Depends(get_db_session),
    repo: CostEventRepository = Depends(_cost_event_repo),
) -> VoucherEngineService:
    """获取凭证引擎服务实例 — 注入 CostEventRepository (凭证生成需要读取 CostEvent)"""
    return VoucherEngineService(session=session, repo=repo)


# ============================================================
# 通用上下文依赖
# ============================================================

def get_tenant_context() -> TenantContext:
    """获取当前租户上下文 (从 ContextVar 读取)"""
    return TenantContext.current()


def get_current_tenant_id() -> str:
    """获取当前租户ID (从 ContextVar 读取)"""
    return tenant_id_var.get("")
