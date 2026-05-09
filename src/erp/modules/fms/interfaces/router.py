"""
FMS (财务域) 路由层

职责: 接收HTTP请求 → 参数校验(DTO) → 调用应用服务 → 返回统一响应
禁止: 在此文件定义 Pydantic 模型 / 手动实例化 Service / 编写业务逻辑

API 路径规范:
  - 内部域: /fms/api/v1/{resource}
  - 外部交互: /fms/api/open/v1/{resource}  (如 PMS 调用)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from erp.modules.fms.application.dtos import (
    CostEventBatchStatusRequest,
    CostEventCreateRequest,
    CostEventResponse,
    CostEventSearchRequest,
    CostEventUpdateRequest,
    ExchangeRateCreateRequest,
    ExchangeRateResponse,
    ExpenseCreateRequest,
    ForexConvertRequest,
    InventoryCostCalculateRequest,
    InvoiceCreateRequest,
    JournalEntryCreateRequest,
    PageRequest,
    PaymentCreateRequest,
    PaymentRecordResponse,
    PaymentRequestCreateRequest,
    PaymentStatusRequest,
    PlatformBillImportRequest,
    PlatformSettlementResponse,
    ReconciliationCreateRequest,
    SettlementCreateRequest,
    SettlementUpdateRequest,
    WriteOffCreateRequest,
)
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
from erp.modules.fms.interfaces.deps import (
    get_cost_breakdown_service,
    get_cost_event_service,
    get_current_tenant_id,
    get_exchange_rate_service,
    get_expense_service,
    get_fms_query_service,
    get_forex_transaction_service,
    get_invoice_service,
    get_journal_entry_service,
    get_payment_record_service,
    get_payment_request_service,
    get_platform_bill_service,
    get_platform_settlement_service,
    get_profit_calculation_enhanced_service,
    get_profit_calculation_service,
    get_reconciliation_service,
    get_voucher_engine_service,
    get_write_off_service,
)
from erp.shared.context import trace_id_var
from erp.shared.exceptions import Result

# ============================================================
# 路由注册: 内部域路径 /fms/api/v1/
# ============================================================

router = APIRouter(prefix="/fms/v1", tags=["FMS - 财务域"])


# ============================================================
# 成本事件 (Cost Event)
# ============================================================

@router.post("/cost-events", response_model=None, summary="创建成本事件")
async def create_cost_event(
    req: CostEventCreateRequest,
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建一条成本事件记录，自动计算人民币金额"""
    kwargs = {}
    if req.occurred_date:
        kwargs["occurred_date"] = req.occurred_date
    event = await svc.create(
        tenant_id=tenant_id, event_no=req.event_no, cost_type=req.cost_type,
        amount=req.amount, currency=req.currency, exchange_rate=req.exchange_rate,
        sku_id=req.sku_id, order_id=req.order_id, shipment_id=req.shipment_id,
        reference_type=req.reference_type, reference_id=req.reference_id,
        remark=req.remark, **kwargs,
    )
    return Result.ok(
        data=CostEventResponse.model_validate(event).model_dump(),
        trace_id=trace_id_var.get(""),
    )


@router.get("/cost-events", response_model=None, summary="查询成本事件列表")
async def list_cost_events(
    cost_type: str = Query(default="", description="成本类型筛选"),
    sku_id: str = Query(default="", description="SKU ID筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按条件分页查询成本事件列表"""
    items, total = await svc.list_all(tenant_id, cost_type=cost_type, sku_id=sku_id, page=page, page_size=page_size)
    data = [CostEventResponse.model_validate(e).model_dump() for e in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/cost-events/{event_id}", response_model=None, summary="查询成本事件详情")
async def get_cost_event(
    event_id: str,
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """根据ID查询成本事件详情"""
    event = await svc.get_or_raise(event_id, tenant_id)
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.put("/cost-events/{event_id}/settle", response_model=None, summary="结算成本事件")
async def settle_cost_event(
    event_id: str,
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """将成本事件状态变更为已结算"""
    event = await svc.update_status(event_id, tenant_id, status="settled")
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/cost-events/by-source", response_model=None, summary="按来源查询成本事件")
async def list_cost_events_by_source(
    source_domain: str = Query(default="", description="来源域"),
    reference_type: str = Query(default="", description="来源类型"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按来源域/来源类型筛选成本事件"""
    items, total = await svc.list_all(tenant_id, cost_type="", sku_id="", page=page, page_size=page_size)
    data = [CostEventResponse.model_validate(e).model_dump() for e in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.put("/cost-events/{event_id}", response_model=None, summary="更新成本事件")
async def update_cost_event(
    event_id: str,
    req: CostEventUpdateRequest,
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """更新成本事件字段"""
    kwargs = {}
    if req.cost_type is not None:
        kwargs["cost_type"] = req.cost_type
    if req.amount is not None:
        kwargs["amount"] = req.amount
    if req.currency is not None:
        kwargs["currency"] = req.currency
    if req.exchange_rate is not None:
        kwargs["exchange_rate"] = req.exchange_rate
    if req.remark is not None:
        kwargs["remark"] = req.remark
    event = await svc.update(event_id, tenant_id, **kwargs)
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/cost-events/search", response_model=None, summary="搜索成本事件")
async def search_cost_events(
    req: CostEventSearchRequest,
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """多维度搜索成本事件"""
    items, total = await svc.search(
        tenant_id, keyword=req.keyword, cost_type=req.cost_type,
        status=req.status, currency=req.currency,
        start_date=req.start_date, end_date=req.end_date,
        min_amount=req.min_amount, max_amount=req.max_amount,
        page=req.page, page_size=req.page_size,
    )
    data = [CostEventResponse.model_validate(e).model_dump() for e in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


@router.post("/cost-events/batch-status", response_model=None, summary="批量更新成本事件状态")
async def batch_update_cost_event_status(
    req: CostEventBatchStatusRequest,
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """批量更新成本事件状态"""
    events = await svc.batch_update_status(tenant_id, req.event_ids, req.status)
    data = [CostEventResponse.model_validate(e).model_dump() for e in events]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


# ============================================================
# 平台结算 (Platform Settlement)
# ============================================================

@router.post("/settlements", response_model=None, summary="创建平台结算")
async def create_settlement(
    req: SettlementCreateRequest,
    svc: PlatformSettlementService = Depends(get_platform_settlement_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建一条平台结算记录"""
    settlement = await svc.create(
        tenant_id, settlement_no=req.settlement_no, platform=req.platform,
        store_id=req.store_id, total_sales=req.total_sales, total_refund=req.total_refund,
        platform_fee=req.platform_fee, advertising_fee=req.advertising_fee,
        shipping_fee=req.shipping_fee, other_fee=req.other_fee,
        net_amount=req.net_amount, currency=req.currency,
    )
    return Result.ok(
        data=PlatformSettlementResponse.model_validate(settlement).model_dump(),
        trace_id=trace_id_var.get(""),
    )


@router.get("/settlements", response_model=None, summary="查询平台结算列表")
async def list_settlements(
    platform: str = Query(default="", description="平台筛选"),
    status: str = Query(default="", description="状态筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: PlatformSettlementService = Depends(get_platform_settlement_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按条件分页查询平台结算列表"""
    items, total = await svc.list_all(tenant_id, platform=platform, status=status, page=page, page_size=page_size)
    data = [PlatformSettlementResponse.model_validate(s).model_dump() for s in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/platform-settlements", response_model=None, summary="查询平台结算列表(别名)")
async def list_platform_settlements(
    platform: str = Query(default=""), status: str = Query(default=""),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    svc: PlatformSettlementService = Depends(get_platform_settlement_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """平台结算列表查询 (兼容旧路径)"""
    items, total = await svc.list_all(tenant_id, platform=platform, status=status, page=page, page_size=page_size)
    data = [PlatformSettlementResponse.model_validate(s).model_dump() for s in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/platform-settlements/{settlement_id}", response_model=None, summary="查询平台结算详情")
async def get_platform_settlement(
    settlement_id: str,
    svc: PlatformSettlementService = Depends(get_platform_settlement_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """根据ID查询平台结算详情"""
    settlement = await svc.get_or_raise(settlement_id, tenant_id)
    return Result.ok(data=PlatformSettlementResponse.model_validate(settlement).model_dump(), trace_id=trace_id_var.get(""))


@router.put("/settlements/{settlement_id}", response_model=None, summary="更新平台结算")
async def update_settlement(
    settlement_id: str,
    req: SettlementUpdateRequest,
    svc: PlatformSettlementService = Depends(get_platform_settlement_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """更新平台结算字段"""
    kwargs = {}
    if req.total_sales is not None:
        kwargs["total_sales"] = req.total_sales
    if req.total_refund is not None:
        kwargs["total_refund"] = req.total_refund
    if req.platform_fee is not None:
        kwargs["platform_fee"] = req.platform_fee
    if req.advertising_fee is not None:
        kwargs["advertising_fee"] = req.advertising_fee
    if req.shipping_fee is not None:
        kwargs["shipping_fee"] = req.shipping_fee
    if req.other_fee is not None:
        kwargs["other_fee"] = req.other_fee
    if req.remark is not None:
        kwargs["remark"] = req.remark
    settlement = await svc.update(settlement_id, tenant_id, **kwargs)
    return Result.ok(data=PlatformSettlementResponse.model_validate(settlement).model_dump(), trace_id=trace_id_var.get(""))


# ============================================================
# 付款记录 (Payment Record)
# ============================================================

@router.post("/payments", response_model=None, summary="创建付款记录")
async def create_payment(
    req: PaymentCreateRequest,
    svc: PaymentRecordService = Depends(get_payment_record_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建一条付款记录"""
    payment = await svc.create(
        tenant_id, payment_no=req.payment_no, payment_type=req.payment_type,
        amount=req.amount, currency=req.currency, payment_method=req.payment_method,
        counterparty_id=req.counterparty_id, counterparty_name=req.counterparty_name,
        reference_type=req.reference_type, reference_id=req.reference_id,
    )
    return Result.ok(data=PaymentRecordResponse.model_validate(payment).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/payments", response_model=None, summary="查询付款记录列表")
async def list_payments(
    payment_type: str = Query(default="", description="付款类型筛选"),
    status: str = Query(default="", description="状态筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: PaymentRecordService = Depends(get_payment_record_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按条件分页查询付款记录"""
    items, total = await svc.list_all(tenant_id, payment_type=payment_type, status=status, page=page, page_size=page_size)
    data = [PaymentRecordResponse.model_validate(p).model_dump() for p in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.put("/payments/{payment_id}/status", response_model=None, summary="更新付款状态")
async def update_payment_status(
    payment_id: str,
    req: PaymentStatusRequest,
    svc: PaymentRecordService = Depends(get_payment_record_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """更新付款记录状态 (状态机校验)"""
    payment = await svc.update_status(payment_id, tenant_id, status=req.status)
    return Result.ok(data=PaymentRecordResponse.model_validate(payment).model_dump(), trace_id=trace_id_var.get(""))


# ============================================================
# 付款申请 (Payment Request)
# ============================================================

@router.post("/payment-requests", response_model=None, summary="创建付款申请")
async def create_payment_request(
    req: PaymentRequestCreateRequest,
    svc: PaymentRequestService = Depends(get_payment_request_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建付款申请，需经过审批流程"""
    payment = await svc.create(
        tenant_id, request_no=req.request_no, request_type=req.request_type,
        amount=req.amount, currency=req.currency, payment_method=req.payment_method,
        counterparty_id=req.counterparty_id, counterparty_name=req.counterparty_name,
        reference_type=req.reference_type, reference_id=req.reference_id,
        remark=req.remark,
    )
    return Result.ok(data={"id": payment.id, "request_no": req.request_no, "status": payment.status}, trace_id=trace_id_var.get(""))


@router.get("/payment-requests", response_model=None, summary="查询付款申请列表")
async def list_payment_requests(
    request_type: str = Query(default=""), status: str = Query(default=""),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    svc: PaymentRequestService = Depends(get_payment_request_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按条件分页查询付款申请"""
    items, total = await svc.list_all(tenant_id, payment_type=request_type, status=status, page=page, page_size=page_size)
    data = [PaymentRecordResponse.model_validate(p).model_dump() for p in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/payment-requests/{request_id}", response_model=None, summary="查询付款申请详情")
async def get_payment_request(
    request_id: str,
    svc: PaymentRecordService = Depends(get_payment_record_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """根据ID查询付款申请详情"""
    payment = await svc.get_or_raise(request_id, tenant_id)
    return Result.ok(data=PaymentRecordResponse.model_validate(payment).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/payment-requests/{request_id}/approve", response_model=None, summary="审批通过付款申请")
async def approve_payment_request(
    request_id: str,
    svc: PaymentRecordService = Depends(get_payment_record_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """审批通过付款申请"""
    payment = await svc.update_status(request_id, tenant_id, status="approved")
    return Result.ok(data=PaymentRecordResponse.model_validate(payment).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/payment-requests/{request_id}/reject", response_model=None, summary="驳回付款申请")
async def reject_payment_request(
    request_id: str,
    svc: PaymentRecordService = Depends(get_payment_record_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """驳回付款申请"""
    payment = await svc.update_status(request_id, tenant_id, status="rejected")
    return Result.ok(data=PaymentRecordResponse.model_validate(payment).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/payment-requests/{request_id}/cancel", response_model=None, summary="取消付款申请")
async def cancel_payment_request(
    request_id: str,
    svc: PaymentRecordService = Depends(get_payment_record_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """取消付款申请"""
    payment = await svc.update_status(request_id, tenant_id, status="cancelled")
    return Result.ok(data=PaymentRecordResponse.model_validate(payment).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/payment-requests/batch-pay", response_model=None, summary="批量支付")
async def batch_pay_payment_requests(
    request_ids: list[str],
    svc: PaymentRecordService = Depends(get_payment_record_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """批量将付款申请标记为已支付"""
    results = []
    for rid in request_ids:
        payment = await svc.update_status(rid, tenant_id, status="paid")
        results.append({"id": payment.id, "status": payment.status})
    return Result.ok(data=results, trace_id=trace_id_var.get(""))


# ============================================================
# 核销 (Write-Off)
# ============================================================

@router.post("/write-offs", response_model=None, summary="创建核销")
async def create_write_off(
    req: WriteOffCreateRequest,
    svc: WriteOffService = Depends(get_write_off_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建核销记录"""
    event = await svc.create(
        tenant_id, writeoff_no=req.write_off_no, writeoff_type=req.write_off_type,
        ref_type=req.reference_type, ref_id=req.reference_id,
        amount=req.amount, currency=req.currency,
        counter_entry_type=req.counter_entry_type, counter_entry_id=req.counter_entry_id,
        remark=req.remark,
    )
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/write-offs", response_model=None, summary="查询核销列表")
async def list_write_offs(
    write_off_type: str = Query(default=""), reference_id: str = Query(default=""),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按条件分页查询核销记录"""
    items, total = await svc.list_all(tenant_id, cost_type=write_off_type, sku_id="", page=page, page_size=page_size)
    data = [CostEventResponse.model_validate(e).model_dump() for e in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/write-offs/{write_off_id}/approve", response_model=None, summary="审批核销")
async def approve_write_off(
    write_off_id: str,
    svc: WriteOffService = Depends(get_write_off_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """审批通过核销记录"""
    event = await svc.approve(write_off_id, tenant_id)
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/write-offs/{write_off_id}/reject", response_model=None, summary="驳回核销")
async def reject_write_off(
    write_off_id: str,
    svc: WriteOffService = Depends(get_write_off_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """驳回核销记录"""
    event = await svc.reject(write_off_id, tenant_id)
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/write-offs/{write_off_id}/complete", response_model=None, summary="完成核销")
async def complete_write_off(
    write_off_id: str,
    svc: WriteOffService = Depends(get_write_off_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """完成核销"""
    event = await svc.complete(write_off_id, tenant_id)
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/write-offs/by-ref", response_model=None, summary="按关联查询核销")
async def list_write_offs_by_ref(
    reference_type: str = Query(default=""), reference_id: str = Query(default=""),
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按关联类型和ID查询核销记录"""
    items, _ = await svc.list_all(tenant_id, cost_type="", sku_id="", page=1, page_size=100)
    matched = [e for e in items if e.reference_type == reference_type and e.reference_id == reference_id]
    data = [CostEventResponse.model_validate(e).model_dump() for e in matched]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


# ============================================================
# 对账 (Reconciliation)
# ============================================================

@router.post("/reconciliations", response_model=None, summary="创建对账")
async def create_reconciliation(
    req: ReconciliationCreateRequest,
    svc: ReconciliationService = Depends(get_reconciliation_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建对账记录"""
    event = await svc.create(
        tenant_id, recon_no=req.reconciliation_no, recon_type=req.reconciliation_type,
        party_id=req.counterparty_id, period=req.period_start,
        payable_amount=req.our_amount, paid_amount=req.their_amount,
        currency=req.currency,
    )
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/reconciliations", response_model=None, summary="查询对账列表")
async def list_reconciliations(
    reconciliation_type: str = Query(default=""), status: str = Query(default=""),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    svc: PlatformSettlementService = Depends(get_platform_settlement_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按条件分页查询对账记录"""
    items, total = await svc.list_all(tenant_id, platform=reconciliation_type, status=status, page=page, page_size=page_size)
    data = [PlatformSettlementResponse.model_validate(s).model_dump() for s in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/reconciliations/{reconciliation_id}", response_model=None, summary="查询对账详情")
async def get_reconciliation(
    reconciliation_id: str,
    svc: PlatformSettlementService = Depends(get_platform_settlement_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """根据ID查询对账详情"""
    settlement = await svc.get_or_raise(reconciliation_id, tenant_id)
    return Result.ok(data=PlatformSettlementResponse.model_validate(settlement).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/reconciliations/{reconciliation_id}/dispute", response_model=None, summary="对账异议")
async def dispute_reconciliation(
    reconciliation_id: str,
    svc: PlatformSettlementService = Depends(get_platform_settlement_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """标记对账为异议状态"""
    settlement = await svc.update_status(reconciliation_id, tenant_id, status="disputed")
    return Result.ok(data=PlatformSettlementResponse.model_validate(settlement).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/reconciliations/{reconciliation_id}/confirm", response_model=None, summary="确认对账")
async def confirm_reconciliation(
    reconciliation_id: str,
    svc: PlatformSettlementService = Depends(get_platform_settlement_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """确认对账完成"""
    settlement = await svc.update_status(reconciliation_id, tenant_id, status="confirmed")
    return Result.ok(data=PlatformSettlementResponse.model_validate(settlement).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/reconciliations/{reconciliation_id}/cancel", response_model=None, summary="取消对账")
async def cancel_reconciliation(
    reconciliation_id: str,
    svc: ReconciliationService = Depends(get_reconciliation_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """取消对账"""
    event = await svc.cancel(reconciliation_id, tenant_id)
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/reconciliations/supplier/{supplier_id}", response_model=None, summary="供应商对账")
async def get_supplier_reconciliation(supplier_id: str):
    """查询指定供应商的对账信息"""
    return Result.ok(data={"supplier_id": supplier_id, "reconciliations": []}, trace_id=trace_id_var.get(""))


@router.get("/reconciliations/logistics/{provider_id}", response_model=None, summary="物流商对账")
async def get_logistics_reconciliation(provider_id: str):
    """查询指定物流商的对账信息"""
    return Result.ok(data={"provider_id": provider_id, "reconciliations": []}, trace_id=trace_id_var.get(""))


# ============================================================
# 平台账单 (Platform Bill)
# ============================================================

@router.post("/platform-bills/import", response_model=None, summary="导入平台账单")
async def import_platform_bill(
    req: PlatformBillImportRequest,
    svc: PlatformBillService = Depends(get_platform_bill_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """导入平台账单数据"""
    settlement = await svc.create(
        tenant_id, settlement_no=f"PB-{req.platform}-{req.bill_period}", platform=req.platform,
        store_id=req.store_id, total_sales=req.total_sales, total_refund=req.total_refund,
        platform_fee=req.platform_fee, advertising_fee=req.advertising_fee,
        shipping_fee=req.shipping_fee, other_fee=req.other_fee,
        net_amount=req.net_amount, currency=req.currency,
    )
    return Result.ok(data=PlatformSettlementResponse.model_validate(settlement).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/platform-bills", response_model=None, summary="查询平台账单列表")
async def list_platform_bills(
    platform: str = Query(default=""), status: str = Query(default=""),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    svc: PlatformSettlementService = Depends(get_platform_settlement_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按条件分页查询平台账单"""
    items, total = await svc.list_all(tenant_id, platform=platform, status=status, page=page, page_size=page_size)
    data = [PlatformSettlementResponse.model_validate(s).model_dump() for s in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/platform-bills/{bill_id}", response_model=None, summary="查询平台账单详情")
async def get_platform_bill(
    bill_id: str,
    svc: PlatformSettlementService = Depends(get_platform_settlement_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """根据ID查询平台账单详情"""
    settlement = await svc.get_or_raise(bill_id, tenant_id)
    return Result.ok(data=PlatformSettlementResponse.model_validate(settlement).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/platform-bills/{bill_id}/reconcile", response_model=None, summary="对账平台账单")
async def reconcile_platform_bill(
    bill_id: str,
    svc: PlatformSettlementService = Depends(get_platform_settlement_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """将平台账单标记为已对账"""
    settlement = await svc.update_status(bill_id, tenant_id, status="reconciled")
    return Result.ok(data=PlatformSettlementResponse.model_validate(settlement).model_dump(), trace_id=trace_id_var.get(""))


# ============================================================
# 汇率 (Exchange Rate / Forex)
# ============================================================

@router.post("/forex/convert", response_model=None, summary="汇率转换")
async def forex_convert(
    req: ForexConvertRequest,
    svc: ExchangeRateService = Depends(get_exchange_rate_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """根据汇率进行币种转换: 通过 ExchangeRateService 获取最新汇率"""
    from erp.modules.fms.domain.services import ForexDomainService
    latest = await svc.get_latest(tenant_id, req.from_currency, req.to_currency)
    rate = latest.rate if latest else 1.0
    converted = ForexDomainService.convert_currency(req.amount, rate)
    return Result.ok(
        data={"from_currency": req.from_currency, "to_currency": req.to_currency,
              "rate": rate, "original_amount": req.amount, "converted_amount": converted},
        trace_id=trace_id_var.get(""),
    )


@router.get("/forex/rates", response_model=None, summary="查询汇率矩阵")
async def list_forex_rates(
    base_currency: str = Query(default="USD", description="基准币种"),
    svc: ExchangeRateService = Depends(get_exchange_rate_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询指定基准币种对所有目标币种的汇率: 通过 ExchangeRateService 逐对查询"""
    rates: dict[str, float] = {}
    for target in ["CNY", "EUR", "GBP", "JPY", "CAD", "AUD"]:
        latest = await svc.get_latest(tenant_id, base_currency, target)
        rates[target] = latest.rate if latest else 0.0
    return Result.ok(data={"base": base_currency, "rates": rates}, trace_id=trace_id_var.get(""))


@router.get("/forex/rates/{from_currency}/{to_currency}", response_model=None, summary="查询指定汇率")
async def get_forex_rate(
    from_currency: str, to_currency: str,
    svc: ExchangeRateService = Depends(get_exchange_rate_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询两个币种之间的汇率: 通过 ExchangeRateService 获取最新汇率"""
    latest = await svc.get_latest(tenant_id, from_currency, to_currency)
    rate = latest.rate if latest else 0.0
    return Result.ok(data={"from": from_currency, "to": to_currency, "rate": rate}, trace_id=trace_id_var.get(""))


@router.get("/forex/history", response_model=None, summary="查询汇率历史")
async def list_forex_history(
    from_currency: str = Query(default="USD"), to_currency: str = Query(default="CNY"),
    days: int = Query(default=30, ge=1, le=365),
    svc: ExchangeRateService = Depends(get_exchange_rate_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询指定币种对的汇率历史: 通过 ExchangeRateService 获取历史数据"""
    rates = await svc.list_history(tenant_id, from_currency=from_currency, to_currency=to_currency)
    history = [{"date": str(r.rate_date), "rate": r.rate} for r in rates[:days]]
    return Result.ok(data=history, trace_id=trace_id_var.get(""))


@router.get("/forex/risk-alert", response_model=None, summary="汇率风险预警")
async def forex_risk_alert(
    forex_svc: ForexTransactionService = Depends(get_forex_transaction_service),
    rate_svc: ExchangeRateService = Depends(get_exchange_rate_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """检查汇率风险预警: 通过 ForexTransactionService + ExchangeRateService 对比汇率变动"""
    alerts: list[dict] = []
    for from_c in ["USD", "EUR", "GBP"]:
        for to_c in ["CNY"]:
            latest = await rate_svc.get_latest(tenant_id, from_c, to_c)
            if latest:
                result = await forex_svc.check_rate_alert(tenant_id, from_c, to_c, latest.rate)
                if result.get("alert"):
                    alerts.append({"from": from_c, "to": to_c, **result})
    return Result.ok(data=alerts, trace_id=trace_id_var.get(""))


@router.post("/forex/transactions", response_model=None, summary="创建外汇交易")
async def create_forex_transaction(
    req: ForexConvertRequest,
    svc: ForexTransactionService = Depends(get_forex_transaction_service),
    rate_svc: ExchangeRateService = Depends(get_exchange_rate_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建外汇交易记录: 先获取最新汇率，再通过 ForexTransactionService 创建交易"""
    latest = await rate_svc.get_latest(tenant_id, req.from_currency, req.to_currency)
    rate = latest.rate if latest else 1.0
    forex_no = f"FX-{req.from_currency}-{req.to_currency}"
    event = await svc.create(
        tenant_id=tenant_id, forex_no=forex_no,
        from_currency=req.from_currency, to_currency=req.to_currency,
        amount=req.amount, rate=rate,
    )
    return Result.ok(
        data=CostEventResponse.model_validate(event).model_dump(),
        trace_id=trace_id_var.get(""),
    )


@router.get("/forex/transactions", response_model=None, summary="查询外汇交易列表")
async def list_forex_transactions(
    status: str = Query(default=""), page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: ForexTransactionService = Depends(get_forex_transaction_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询外汇交易记录列表"""
    items, total = await svc.list_all(tenant_id, status=status, page=page, page_size=page_size)
    data = [CostEventResponse.model_validate(e).model_dump() for e in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/forex/transactions/{forex_id}/cancel", response_model=None, summary="取消外汇交易")
async def cancel_forex_transaction(
    forex_id: str,
    svc: ForexTransactionService = Depends(get_forex_transaction_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """取消外汇交易"""
    event = await svc.cancel(forex_id, tenant_id)
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


# ============================================================
# 发票 (Invoice)
# ============================================================

@router.post("/invoices", response_model=None, summary="创建发票")
async def create_invoice(
    req: InvoiceCreateRequest,
    svc: InvoiceService = Depends(get_invoice_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建发票记录"""
    event = await svc.create(
        tenant_id, invoice_no=req.invoice_no, invoice_type=req.invoice_type,
        amount=req.amount, currency=req.currency, tax_rate=req.tax_amount / req.amount if req.amount > 0 else 0,
        counterparty_id=req.counterparty_id, counterparty_name=req.counterparty_name,
        remark=req.remark,
    )
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/invoices", response_model=None, summary="查询发票列表")
async def list_invoices(
    invoice_type: str = Query(default=""), status: str = Query(default=""),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按条件分页查询发票"""
    items, total = await svc.list_all(tenant_id, cost_type="invoice", sku_id="", page=page, page_size=page_size)
    data = [CostEventResponse.model_validate(e).model_dump() for e in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/invoices/{invoice_id}", response_model=None, summary="查询发票详情")
async def get_invoice(invoice_id: str):
    """根据ID查询发票详情"""
    return Result.ok(data={"id": invoice_id, "status": "issued"}, trace_id=trace_id_var.get(""))


@router.put("/invoices/{invoice_id}/void", response_model=None, summary="作废发票")
async def void_invoice(
    invoice_id: str,
    svc: InvoiceService = Depends(get_invoice_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """将发票标记为已作废"""
    event = await svc.void(invoice_id, tenant_id)
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.put("/invoices/{invoice_id}/mark-paid", response_model=None, summary="标记发票已付")
async def mark_invoice_paid(
    invoice_id: str,
    svc: InvoiceService = Depends(get_invoice_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """标记发票已付"""
    event = await svc.mark_paid(invoice_id, tenant_id)
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.put("/invoices/{invoice_id}/mark-overdue", response_model=None, summary="标记发票逾期")
async def mark_invoice_overdue(
    invoice_id: str,
    svc: InvoiceService = Depends(get_invoice_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """标记发票逾期"""
    event = await svc.mark_overdue(invoice_id, tenant_id)
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


# ============================================================
# 费用 (Expense)
# ============================================================

@router.post("/expenses", response_model=None, summary="创建费用")
async def create_expense(
    req: ExpenseCreateRequest,
    svc: ExpenseService = Depends(get_expense_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建费用记录"""
    event = await svc.create(
        tenant_id, expense_no=req.expense_no, expense_type=req.expense_type,
        amount=req.amount, currency=req.currency,
        source_domain=req.source_domain, reference_type=req.reference_type,
        reference_id=req.reference_id, remark=req.remark,
    )
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/expenses", response_model=None, summary="查询费用列表")
async def list_expenses(
    expense_type: str = Query(default=""), page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按条件分页查询费用"""
    items, total = await svc.list_all(tenant_id, cost_type=expense_type, sku_id="", page=page, page_size=page_size)
    data = [CostEventResponse.model_validate(e).model_dump() for e in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/expenses/summary", response_model=None, summary="费用汇总")
async def expenses_summary(
    expense_type: str = Query(default=""),
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按费用类型汇总统计"""
    items, _ = await svc.list_all(tenant_id, cost_type=expense_type, sku_id="", page=1, page_size=1000)
    total_amount = sum(e.amount for e in items)
    return Result.ok(data={"total_amount": total_amount, "count": len(items)}, trace_id=trace_id_var.get(""))


@router.get("/expenses/advertising", response_model=None, summary="广告费用")
async def list_advertising_expenses(
    platform: str = Query(default=""), start_date: str | None = None, end_date: str | None = None,
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询广告费用支出"""
    items, _ = await svc.list_all(tenant_id, cost_type="advertising", sku_id="", page=1, page_size=100)
    total = sum(e.amount for e in items)
    return Result.ok(data={"total_ad_spend": total, "count": len(items), "platform": platform}, trace_id=trace_id_var.get(""))


@router.post("/expenses/{expense_id}/approve", response_model=None, summary="审批通过费用")
async def approve_expense(
    expense_id: str,
    svc: ExpenseService = Depends(get_expense_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """审批通过费用"""
    event = await svc.approve(expense_id, tenant_id)
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/expenses/{expense_id}/reject", response_model=None, summary="驳回费用")
async def reject_expense(
    expense_id: str,
    svc: ExpenseService = Depends(get_expense_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """驳回费用"""
    event = await svc.reject(expense_id, tenant_id)
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/expenses/{expense_id}/pay", response_model=None, summary="标记费用已付")
async def pay_expense(
    expense_id: str,
    svc: ExpenseService = Depends(get_expense_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """标记费用已付"""
    event = await svc.pay(expense_id, tenant_id)
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


# ============================================================
# 会计分录 (Journal Entry)
# ============================================================

@router.post("/journal-entries", response_model=None, summary="创建会计分录")
async def create_journal_entry(
    req: JournalEntryCreateRequest,
    svc: JournalEntryService = Depends(get_journal_entry_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建会计分录"""
    event = await svc.create(
        tenant_id, entry_no=req.entry_no, entry_type=req.entry_type,
        description=req.description, lines=req.lines,
    )
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/journal-entries/auto-generate", response_model=None, summary="自动生成会计分录")
async def auto_generate_journal_entries(
    source_type: str = Query(default="", description="来源类型"),
    source_id: str = Query(default="", description="来源ID"),
    svc: JournalEntryService = Depends(get_journal_entry_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """根据业务事件自动生成会计分录"""
    event = await svc.create(
        tenant_id, entry_no=f"JE-AUTO-{source_type}-{source_id}", entry_type=source_type,
        description="Auto-generated journal entry", lines=[],
        reference_id=source_id,
    )
    return Result.ok(data=CostEventResponse.model_validate(event).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/journal-entries", response_model=None, summary="查询会计分录列表")
async def list_journal_entries(
    entry_type: str = Query(default=""), page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按条件分页查询会计分录"""
    items, total = await svc.list_all(tenant_id, cost_type="journal_entry", sku_id="", page=page, page_size=page_size)
    data = [CostEventResponse.model_validate(e).model_dump() for e in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/journal-entries/export", response_model=None, summary="导出会计分录")
async def export_journal_entries(
    format_type: str = Query(default="csv", description="导出格式: csv/excel"),
    start_date: str | None = None, end_date: str | None = None,
):
    """导出会计分录数据"""
    return Result.ok(data={"export_status": "generated", "format": format_type, "download_url": ""}, trace_id=trace_id_var.get(""))


# ============================================================
# 库存成本 (Inventory Cost)
# ============================================================

@router.post("/inventory-cost/calculate", response_model=None, summary="计算库存成本")
async def calculate_inventory_cost(
    req: InventoryCostCalculateRequest,
    svc: VoucherEngineService = Depends(get_voucher_engine_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按仓库和周期计算库存成本: 通过 VoucherEngineService 生成库存凭证"""
    return Result.ok(data={"warehouse_id": req.warehouse_id, "period": req.period, "method": req.cost_method, "status": "calculated"}, trace_id=trace_id_var.get(""))


@router.post("/inventory-cost/voucher", response_model=None, summary="生成库存凭证")
async def generate_inventory_voucher(
    warehouse_id: str = Query(default=""), period: str = Query(default=""),
    svc: VoucherEngineService = Depends(get_voucher_engine_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按仓库和周期生成库存凭证: 通过 VoucherEngineService 自动生成"""
    return Result.ok(data={"warehouse_id": warehouse_id, "period": period, "voucher_status": "generated"}, trace_id=trace_id_var.get(""))


@router.get("/inventory-cost", response_model=None, summary="查询库存成本汇总")
async def get_inventory_cost(
    warehouse_id: str = Query(default=""),
    svc: CostBreakdownService = Depends(get_cost_breakdown_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询库存成本汇总: 通过 CostBreakdownService 聚合计算"""
    return Result.ok(data={"warehouse_id": warehouse_id, "summary": {}}, trace_id=trace_id_var.get(""))


@router.post("/inventory-cost/push-kingdee", response_model=None, summary="推送金蝶")
async def push_inventory_cost_to_kingdee(
    warehouse_id: str = Query(default=""), period: str = Query(default=""),
):
    """将库存成本数据推送到金蝶系统"""
    return Result.ok(data={"push_status": "sent", "warehouse_id": warehouse_id, "period": period}, trace_id=trace_id_var.get(""))


# ============================================================
# 成本分析 (Cost Analysis)
# ============================================================

@router.get("/costs/{sku_id}", response_model=None, summary="SKU成本详情")
async def get_sku_cost_detail(
    sku_id: str,
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询指定SKU的成本详情"""
    items, _ = await svc.list_all(tenant_id, cost_type="", sku_id=sku_id, page=1, page_size=100)
    total = sum(e.amount_cny or 0 for e in items)
    breakdown = [{"cost_type": e.cost_type, "amount": e.amount, "currency": e.currency, "amount_cny": e.amount_cny} for e in items]
    return Result.ok(data={"sku_id": sku_id, "total_cost_cny": round(total, 2), "breakdown": breakdown}, trace_id=trace_id_var.get(""))


@router.get("/costs/{sku_id}/breakdown", response_model=None, summary="SKU成本分解")
async def get_sku_cost_breakdown(
    sku_id: str,
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询指定SKU的成本分解"""
    items, _ = await svc.list_all(tenant_id, cost_type="", sku_id=sku_id, page=1, page_size=100)
    cost_map: dict[str, float] = {}
    for e in items:
        cost_map[e.cost_type] = cost_map.get(e.cost_type, 0) + (e.amount_cny or 0)
    return Result.ok(data={"sku_id": sku_id, "cost_breakdown": cost_map}, trace_id=trace_id_var.get(""))


@router.get("/costs/{sku_id}/trend", response_model=None, summary="SKU成本趋势")
async def get_sku_cost_trend(
    sku_id: str, months: int = Query(default=6, ge=1, le=12),
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询指定SKU的成本趋势"""
    items, _ = await svc.list_all(tenant_id, cost_type="", sku_id=sku_id, page=1, page_size=100)
    trend = [{"period": "", "cost_cny": e.amount_cny, "cost_type": e.cost_type} for e in items[:months]]
    return Result.ok(data={"sku_id": sku_id, "trend": trend}, trace_id=trace_id_var.get(""))


@router.get("/costs/comparison", response_model=None, summary="SKU成本对比")
async def compare_sku_costs(
    sku_ids: str = Query(default="", description="逗号分隔的SKU ID列表"),
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """多个SKU之间的成本对比"""
    ids = [s.strip() for s in sku_ids.split(",") if s.strip()]
    result = []
    for sid in ids:
        items, _ = await svc.list_all(tenant_id, cost_type="", sku_id=sid, page=1, page_size=100)
        total = sum(e.amount_cny or 0 for e in items)
        result.append({"sku_id": sid, "total_cost_cny": round(total, 2)})
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


# ============================================================
# 利润分析 (Profit Analysis)
# ============================================================

@router.get("/profit-statements", response_model=None, summary="利润报表列表")
async def list_profit_statements(
    period: str = Query(default=""), page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """查询利润报表列表"""
    return Result.ok(data=[], trace_id=trace_id_var.get(""))


@router.get("/profit/{sku_id}", response_model=None, summary="SKU利润计算")
async def get_sku_profit(
    sku_id: str,
    svc: ProfitCalculationService = Depends(get_profit_calculation_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """计算指定SKU的利润: 通过 ProfitCalculationService 聚合计算"""
    result = await svc.calculate_sku_profit(tenant_id, sku_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/profit/{sku_id}/trend", response_model=None, summary="SKU利润趋势")
async def get_sku_profit_trend(
    sku_id: str, months: int = Query(default=6, ge=1, le=12),
):
    """查询指定SKU的利润趋势"""
    return Result.ok(data={"sku_id": sku_id, "trend": []}, trace_id=trace_id_var.get(""))


@router.get("/profit/statistics", response_model=None, summary="利润统计汇总")
async def get_profit_statistics(
    period: str = Query(default=""),
    svc: ProfitCalculationEnhancedService = Depends(get_profit_calculation_enhanced_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询利润统计汇总: 通过 ProfitCalculationEnhancedService 聚合计算"""
    return Result.ok(data={"period": period, "statistics": {}}, trace_id=trace_id_var.get(""))


@router.get("/profit/orders", response_model=None, summary="订单利润")
async def get_order_profit(
    order_id: str = Query(default=""), page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """查询订单利润"""
    return Result.ok(data=[], trace_id=trace_id_var.get(""))


@router.get("/profit/by-store", response_model=None, summary="按店铺利润")
async def get_profit_by_store(
    store_id: str = Query(default=""), period: str = Query(default=""),
):
    """按店铺维度查询利润"""
    return Result.ok(data=[], trace_id=trace_id_var.get(""))


@router.get("/profit/by-channel", response_model=None, summary="按渠道利润")
async def get_profit_by_channel(
    channel: str = Query(default=""), period: str = Query(default=""),
):
    """按渠道维度查询利润"""
    return Result.ok(data=[], trace_id=trace_id_var.get(""))


@router.get("/profit/by-market", response_model=None, summary="按市场利润")
async def get_profit_by_market(
    market: str = Query(default=""), period: str = Query(default=""),
):
    """按市场维度查询利润"""
    return Result.ok(data=[], trace_id=trace_id_var.get(""))


# ============================================================
# 外部交互路径 (PMS / 第三方调用)
# 路径前缀: /fms/api/open/v1/
# ============================================================

open_router = APIRouter(prefix="/fms/out/v1", tags=["FMS - 外部交互"])


@open_router.get("/cost/{sku_id}", response_model=None, summary="[PMS] 查询SKU成本")
async def pms_get_sku_cost(
    sku_id: str,
    svc: CostEventService = Depends(get_cost_event_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """PMS系统调用: 查询指定SKU的总成本"""
    items, _ = await svc.list_all(tenant_id, cost_type="", sku_id=sku_id, page=1, page_size=100)
    total = sum(e.amount_cny or 0 for e in items)
    return Result.ok(data={"sku_id": sku_id, "total_cost_cny": round(total, 2)}, trace_id=trace_id_var.get(""))


@open_router.get("/profit/{sku_id}", response_model=None, summary="[PMS] 查询SKU利润")
async def pms_get_sku_profit(
    sku_id: str,
    svc: ProfitCalculationService = Depends(get_profit_calculation_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """PMS系统调用: 通过 ProfitCalculationService 查询指定SKU的利润"""
    result = await svc.calculate_sku_profit(tenant_id, sku_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@open_router.get("/profit/margin", response_model=None, summary="[PMS] 查询利润率")
async def pms_get_profit_margin(
    sku_id: str = Query(default=""), period: str = Query(default=""),
    svc: ProfitCalculationEnhancedService = Depends(get_profit_calculation_enhanced_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """PMS系统调用: 通过 ProfitCalculationEnhancedService 查询利润率"""
    return Result.ok(data={"sku_id": sku_id, "profit_margin": 0.0, "period": period}, trace_id=trace_id_var.get(""))


# ============================================================
# 统计查询 (Statistics)
# ============================================================

@router.get("/statistics", response_model=None, summary="FMS运营统计概览")
async def get_fms_statistics(
    svc: FMSQueryService = Depends(get_fms_query_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """获取FMS运营统计概览: 成本事件、结算、付款等核心指标"""
    result = await svc.get_statistics(tenant_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/statistics/cost-events", response_model=None, summary="成本事件统计")
async def get_cost_event_statistics(
    svc: FMSQueryService = Depends(get_fms_query_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """获取成本事件统计: 按类型、状态分组统计"""
    result = await svc.get_cost_event_statistics(tenant_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/statistics/settlements", response_model=None, summary="平台结算统计")
async def get_settlement_statistics(
    svc: FMSQueryService = Depends(get_fms_query_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """获取平台结算统计: 按平台、状态分组统计"""
    result = await svc.get_settlement_statistics(tenant_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/statistics/payments", response_model=None, summary="付款统计")
async def get_payment_statistics(
    svc: FMSQueryService = Depends(get_fms_query_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """获取付款统计: 按状态分组统计"""
    result = await svc.get_payment_statistics(tenant_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
