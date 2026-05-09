"""
FMS (财务域) 请求/响应 DTO 定义

所有 Pydantic 模型集中定义于此文件，router.py 仅做导入使用。
- 请求模型: XxxCreateRequest / XxxUpdateRequest — 用于接收前端参数
- 响应模型: XxxResponse — 用于序列化 ORM 实体返回前端，使用 from_attributes=True
- 分页请求: PageRequest — 通用分页参数
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 通用分页请求
# ============================================================

class PageRequest(BaseModel):
    """通用分页请求参数"""
    page: int = Field(default=1, ge=1, description="页码，从1开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数，最大100")


# ============================================================
# 成本事件 (Cost Event)
# ============================================================

class CostEventCreateRequest(BaseModel):
    """创建成本事件请求"""
    event_no: str = Field(..., min_length=1, max_length=100, description="成本事件编号，租户内唯一")
    cost_type: str = Field(..., min_length=1, max_length=50, description="成本类型: purchase/shipping/platform_fee/advertising/warehouse/other")
    amount: float = Field(..., gt=0, description="金额，必须大于0")
    currency: str = Field(default="CNY", max_length=10, description="币种: CNY/USD/EUR/GBP/JPY/CAD/AUD")
    exchange_rate: float = Field(default=1.0, gt=0, description="汇率，必须大于0")
    sku_id: str | None = Field(default=None, description="关联SKU ID")
    order_id: str | None = Field(default=None, description="关联订单ID")
    shipment_id: str | None = Field(default=None, description="关联发货单ID")
    reference_type: str = Field(default="", description="来源类型: purchase_order/shipment/warehouse/platform_bill/ad_campaign/payment/refund")
    reference_id: str = Field(default="", description="来源ID")
    occurred_date: datetime | None = Field(default=None, description="发生日期")
    remark: str = Field(default="", description="备注")


class CostEventUpdateRequest(BaseModel):
    """更新成本事件请求"""
    cost_type: str | None = Field(default=None, min_length=1, max_length=50, description="成本类型")
    amount: float | None = Field(default=None, gt=0, description="金额")
    currency: str | None = Field(default=None, max_length=10, description="币种")
    exchange_rate: float | None = Field(default=None, gt=0, description="汇率")
    remark: str | None = Field(default=None, description="备注")


class CostEventSearchRequest(BaseModel):
    """成本事件搜索请求"""
    keyword: str = Field(default="", description="关键词搜索 (事件编号/备注)")
    cost_type: str = Field(default="", description="成本类型筛选")
    status: str = Field(default="", description="状态筛选")
    currency: str = Field(default="", description="币种筛选")
    start_date: datetime | None = Field(default=None, description="开始日期")
    end_date: datetime | None = Field(default=None, description="结束日期")
    min_amount: float | None = Field(default=None, ge=0, description="最小金额")
    max_amount: float | None = Field(default=None, ge=0, description="最大金额")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class CostEventBatchStatusRequest(BaseModel):
    """成本事件批量状态变更请求"""
    event_ids: list[str] = Field(..., min_length=1, description="成本事件ID列表")
    status: str = Field(..., min_length=1, description="目标状态")


class CostEventResponse(BaseModel):
    """成本事件响应，映射 ORM 实体"""
    id: str = Field(description="主键ID")
    tenant_id: str = Field(description="租户ID")
    event_no: str = Field(description="成本事件编号")
    cost_type: str = Field(description="成本类型")
    amount: float = Field(default=0.0, description="原始金额")
    currency: str = Field(default="CNY", description="币种")
    exchange_rate: float = Field(default=1.0, description="汇率")
    amount_cny: float = Field(default=0.0, description="人民币金额")
    sku_id: str | None = Field(default=None, description="SKU ID")
    order_id: str | None = Field(default=None, description="订单ID")
    shipment_id: str | None = Field(default=None, description="发货单ID")
    reference_type: str = Field(default="", description="来源类型")
    reference_id: str = Field(default="", description="来源ID")
    occurred_date: datetime | None = Field(default=None, description="发生日期")
    status: str = Field(default="confirmed", description="状态: draft/confirmed/settled/cancelled")
    remark: str = Field(default="", description="备注")
    created_by: str = Field(default="", description="创建人")
    created_at: datetime | None = Field(default=None, description="创建时间")

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 平台结算 (Platform Settlement)
# ============================================================

class SettlementCreateRequest(BaseModel):
    """创建平台结算请求"""
    settlement_no: str = Field(..., min_length=1, max_length=100, description="结算单号，租户内唯一")
    platform: str = Field(..., min_length=1, max_length=50, description="平台: amazon/shopify/tiktok等")
    store_id: str = Field(..., min_length=1, description="店铺ID")
    settlement_period_start: datetime | None = Field(default=None, description="结算周期开始")
    settlement_period_end: datetime | None = Field(default=None, description="结算周期结束")
    total_sales: float = Field(default=0.0, ge=0, description="总销售额")
    total_refund: float = Field(default=0.0, ge=0, description="总退款额")
    platform_fee: float = Field(default=0.0, ge=0, description="平台佣金")
    advertising_fee: float = Field(default=0.0, ge=0, description="广告费")
    shipping_fee: float = Field(default=0.0, ge=0, description="运费")
    other_fee: float = Field(default=0.0, ge=0, description="其他费用")
    net_amount: float = Field(default=0.0, description="净额 (销售额-退款-各项费用)")
    currency: str = Field(default="USD", max_length=10, description="币种")
    raw_data: dict = Field(default_factory=dict, description="原始数据JSON")


class SettlementUpdateRequest(BaseModel):
    """更新平台结算请求"""
    total_sales: float | None = Field(default=None, ge=0, description="总销售额")
    total_refund: float | None = Field(default=None, ge=0, description="总退款额")
    platform_fee: float | None = Field(default=None, ge=0, description="平台佣金")
    advertising_fee: float | None = Field(default=None, ge=0, description="广告费")
    shipping_fee: float | None = Field(default=None, ge=0, description="运费")
    other_fee: float | None = Field(default=None, ge=0, description="其他费用")
    remark: str | None = Field(default=None, description="备注")


class PlatformSettlementResponse(BaseModel):
    """平台结算响应，映射 ORM 实体"""
    id: str
    tenant_id: str
    settlement_no: str
    platform: str
    store_id: str
    settlement_period_start: datetime | None = None
    settlement_period_end: datetime | None = None
    total_sales: float = 0.0
    total_refund: float = 0.0
    platform_fee: float = 0.0
    advertising_fee: float = 0.0
    shipping_fee: float = 0.0
    other_fee: float = 0.0
    net_amount: float = 0.0
    currency: str = "USD"
    status: str = "pending"
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 付款记录 (Payment Record)
# ============================================================

class PaymentCreateRequest(BaseModel):
    """创建付款记录请求"""
    payment_no: str = Field(..., min_length=1, max_length=100, description="付款编号，租户内唯一")
    payment_type: str = Field(..., description="付款类型: supplier_payment/platform_payout/refund_payment/other")
    counterparty_id: str = Field(default="", description="对方ID (供应商/平台)")
    counterparty_name: str = Field(default="", max_length=200, description="对方名称")
    amount: float = Field(..., gt=0, description="金额，必须大于0")
    currency: str = Field(default="CNY", max_length=10, description="币种")
    payment_method: str = Field(default="bank_transfer", max_length=30, description="付款方式: bank_transfer/alipay/wechat等")
    reference_type: str = Field(default="", description="关联类型")
    reference_id: str = Field(default="", description="关联ID")


class PaymentStatusRequest(BaseModel):
    """更新付款状态请求"""
    status: str = Field(..., min_length=1, description="目标状态: pending/processing/completed/failed/cancelled")


class PaymentRecordResponse(BaseModel):
    """付款记录响应，映射 ORM 实体"""
    id: str
    tenant_id: str
    payment_no: str
    payment_type: str
    counterparty_id: str = ""
    counterparty_name: str = ""
    amount: float = 0.0
    currency: str = "CNY"
    payment_method: str = "bank_transfer"
    status: str = "pending"
    reference_type: str = ""
    reference_id: str = ""
    approval_instance_id: str = ""
    paid_at: datetime | None = None
    remark: str = ""
    created_by: str = ""
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 付款申请 (Payment Request)
# ============================================================

class PaymentRequestCreateRequest(BaseModel):
    """创建付款申请请求"""
    request_no: str = Field(..., min_length=1, max_length=100, description="申请编号，租户内唯一")
    request_type: str = Field(..., min_length=1, description="申请类型: purchase/logistics/other")
    counterparty_id: str = Field(default="", description="对方ID")
    counterparty_name: str = Field(default="", description="对方名称")
    amount: float = Field(..., gt=0, description="金额，必须大于0")
    currency: str = Field(default="CNY", max_length=10, description="币种")
    payment_method: str = Field(default="bank_transfer", max_length=30, description="付款方式")
    reference_type: str = Field(default="", description="关联类型")
    reference_id: str = Field(default="", description="关联ID")
    remark: str = Field(default="", description="备注")


# ============================================================
# 核销 (Write-Off)
# ============================================================

class WriteOffCreateRequest(BaseModel):
    """创建核销请求"""
    write_off_no: str = Field(..., min_length=1, max_length=100, description="核销编号，租户内唯一")
    write_off_type: str = Field(..., min_length=1, description="核销类型: inbound/exception/supplier_refund/repayment")
    amount: float = Field(..., gt=0, description="核销金额，必须大于0")
    currency: str = Field(default="CNY", max_length=10, description="币种")
    reference_type: str = Field(default="", description="关联类型: purchase_order/shipment/refund")
    reference_id: str = Field(default="", description="关联ID")
    counter_entry_type: str = Field(default="", description="对方分录类型")
    counter_entry_id: str = Field(default="", description="对方分录ID")
    remark: str = Field(default="", description="备注")


# ============================================================
# 对账 (Reconciliation)
# ============================================================

class ReconciliationCreateRequest(BaseModel):
    """创建对账请求"""
    reconciliation_no: str = Field(..., min_length=1, max_length=100, description="对账编号，租户内唯一")
    reconciliation_type: str = Field(..., min_length=1, description="对账类型: supplier/logistics/platform")
    counterparty_id: str = Field(default="", description="对方ID")
    counterparty_name: str = Field(default="", description="对方名称")
    period_start: str = Field(default="", description="对账周期开始")
    period_end: str = Field(default="", description="对账周期结束")
    our_amount: float = Field(default=0.0, description="我方金额")
    their_amount: float = Field(default=0.0, description="对方金额")
    currency: str = Field(default="CNY", max_length=10, description="币种")


# ============================================================
# 平台账单 (Platform Bill)
# ============================================================

class PlatformBillImportRequest(BaseModel):
    """导入平台账单请求"""
    platform: str = Field(..., min_length=1, description="平台: amazon/shopify/tiktok")
    store_id: str = Field(..., min_length=1, description="店铺ID")
    bill_period: str = Field(default="", description="账单周期")
    total_sales: float = Field(default=0.0, description="总销售额")
    total_refund: float = Field(default=0.0, description="总退款额")
    platform_fee: float = Field(default=0.0, description="平台佣金")
    advertising_fee: float = Field(default=0.0, description="广告费")
    shipping_fee: float = Field(default=0.0, description="运费")
    other_fee: float = Field(default=0.0, description="其他费用")
    net_amount: float = Field(default=0.0, description="净额")
    currency: str = Field(default="USD", max_length=10, description="币种")


# ============================================================
# 汇率转换 (Forex)
# ============================================================

class ForexConvertRequest(BaseModel):
    """汇率转换请求"""
    from_currency: str = Field(..., min_length=3, max_length=10, description="源币种")
    to_currency: str = Field(..., min_length=3, max_length=10, description="目标币种")
    amount: float = Field(..., gt=0, description="转换金额，必须大于0")
    rate_date: str | None = Field(default=None, description="汇率日期，为空则取最新")


class ExchangeRateCreateRequest(BaseModel):
    """创建汇率记录请求"""
    from_currency: str = Field(..., min_length=3, max_length=10, description="源币种")
    to_currency: str = Field(..., min_length=3, max_length=10, description="目标币种")
    rate: float = Field(..., gt=0, description="汇率，必须大于0")
    rate_date: datetime = Field(description="汇率日期")
    source: str = Field(default="manual", max_length=50, description="来源: manual/api/schedule")


class ExchangeRateResponse(BaseModel):
    """汇率记录响应，映射 ORM 实体"""
    id: str
    tenant_id: str
    from_currency: str
    to_currency: str
    rate: float = 1.0
    rate_date: datetime | None = None
    source: str = "manual"
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 发票 (Invoice)
# ============================================================

class InvoiceCreateRequest(BaseModel):
    """创建发票请求"""
    invoice_no: str = Field(..., min_length=1, max_length=100, description="发票编号，租户内唯一")
    invoice_type: str = Field(..., min_length=1, description="发票类型: purchase/sales/credit_note/debit_note")
    counterparty_id: str = Field(default="", description="对方ID")
    counterparty_name: str = Field(default="", description="对方名称")
    amount: float = Field(..., gt=0, description="金额，必须大于0")
    tax_amount: float = Field(default=0.0, ge=0, description="税额")
    currency: str = Field(default="CNY", max_length=10, description="币种")
    issue_date: str | None = Field(default=None, description="开票日期")
    due_date: str | None = Field(default=None, description="到期日期")
    remark: str = Field(default="", description="备注")


# ============================================================
# 费用 (Expense)
# ============================================================

class ExpenseCreateRequest(BaseModel):
    """创建费用请求"""
    expense_no: str = Field(..., min_length=1, max_length=100, description="费用编号，租户内唯一")
    expense_type: str = Field(..., min_length=1, description="费用类型: advertising/shipping/warehouse/refund/platform_fee/tax/labor/other")
    amount: float = Field(..., gt=0, description="金额，必须大于0")
    currency: str = Field(default="CNY", max_length=10, description="币种")
    source_domain: str = Field(default="", description="来源域: oms/scm/wms/ads等")
    reference_type: str = Field(default="", description="关联类型")
    reference_id: str = Field(default="", description="关联ID")
    remark: str = Field(default="", description="备注")


# ============================================================
# 会计分录 (Journal Entry)
# ============================================================

class JournalEntryCreateRequest(BaseModel):
    """创建会计分录请求"""
    entry_no: str = Field(..., min_length=1, max_length=100, description="分录编号，租户内唯一")
    entry_type: str = Field(..., min_length=1, description="分录类型: purchase/sales/expense/revenue/forex/settlement/inventory_in/inventory_out/inventory_adjust/write_off")
    description: str = Field(default="", description="描述")
    lines: list[dict] = Field(default_factory=list, description="分录行: [{account, debit, credit, amount}]")


# ============================================================
# 库存成本计算 (Inventory Cost Calculate)
# ============================================================

class InventoryCostCalculateRequest(BaseModel):
    """库存成本计算请求"""
    warehouse_id: str = Field(default="", description="仓库ID，为空则计算全部")
    period: str = Field(default="", description="计算周期，如 2026-01")
    cost_method: str = Field(default="fifo", description="成本计算方法: fifo/weighted_average/standard")


# ============================================================
# 核销响应 (Write-Off Response)
# ============================================================

class WriteOffResponse(BaseModel):
    """核销响应"""
    id: str
    tenant_id: str
    write_off_no: str = ""
    write_off_type: str = ""
    amount: float = 0.0
    currency: str = "CNY"
    reference_type: str = ""
    reference_id: str = ""
    counter_entry_type: str = ""
    counter_entry_id: str = ""
    status: str = "pending"
    remark: str = ""
    created_by: str = ""
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 对账响应 (Reconciliation Response)
# ============================================================

class ReconciliationResponse(BaseModel):
    """对账响应"""
    id: str
    tenant_id: str
    reconciliation_no: str = ""
    reconciliation_type: str = ""
    counterparty_id: str = ""
    counterparty_name: str = ""
    period_start: str = ""
    period_end: str = ""
    our_amount: float = 0.0
    their_amount: float = 0.0
    balance: float = 0.0
    currency: str = "CNY"
    status: str = "pending"
    remark: str = ""
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 发票响应 (Invoice Response)
# ============================================================

class InvoiceResponse(BaseModel):
    """发票响应"""
    id: str
    tenant_id: str
    invoice_no: str = ""
    invoice_type: str = ""
    counterparty_id: str = ""
    counterparty_name: str = ""
    amount: float = 0.0
    tax_amount: float = 0.0
    currency: str = "CNY"
    issue_date: str = ""
    due_date: str = ""
    status: str = "draft"
    remark: str = ""
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 费用响应 (Expense Response)
# ============================================================

class ExpenseResponse(BaseModel):
    """费用响应"""
    id: str
    tenant_id: str
    expense_no: str = ""
    expense_type: str = ""
    amount: float = 0.0
    currency: str = "CNY"
    source_domain: str = ""
    reference_type: str = ""
    reference_id: str = ""
    category: str = ""
    status: str = "pending"
    remark: str = ""
    created_by: str = ""
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 外汇交易响应 (Forex Transaction Response)
# ============================================================

class ForexTransactionResponse(BaseModel):
    """外汇交易响应"""
    id: str
    tenant_id: str
    forex_no: str = ""
    from_currency: str = ""
    to_currency: str = ""
    amount: float = 0.0
    rate: float = 1.0
    converted_amount: float = 0.0
    status: str = "pending"
    remark: str = ""
    created_by: str = ""
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 会计分录响应 (Journal Entry Response)
# ============================================================

class JournalEntryResponse(BaseModel):
    """会计分录响应"""
    id: str
    tenant_id: str
    entry_no: str = ""
    entry_type: str = ""
    debit_account: str = ""
    credit_account: str = ""
    amount: float = 0.0
    currency: str = "CNY"
    status: str = "confirmed"
    description: str = ""
    remark: str = ""
    created_by: str = ""
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 平台账单响应 (Platform Bill Response)
# ============================================================

class PlatformBillResponse(BaseModel):
    """平台账单响应"""
    id: str
    tenant_id: str
    bill_no: str = ""
    platform: str = ""
    store_id: str = ""
    bill_type: str = ""
    amount: float = 0.0
    currency: str = "USD"
    status: str = "pending"
    remark: str = ""
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 付款申请响应 (Payment Request Response)
# ============================================================

class PaymentRequestResponse(BaseModel):
    """付款申请响应"""
    id: str
    tenant_id: str
    request_no: str = ""
    request_type: str = ""
    counterparty_id: str = ""
    counterparty_name: str = ""
    amount: float = 0.0
    currency: str = "CNY"
    payment_method: str = "bank_transfer"
    status: str = "pending"
    reference_type: str = ""
    reference_id: str = ""
    remark: str = ""
    created_by: str = ""
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# FMS 统计响应 (FMS Statistics Response)
# ============================================================

class FMSStatisticsResponse(BaseModel):
    """FMS 运营统计概览响应"""
    cost_event_count: int = 0
    cost_event_by_type: dict[str, int] = {}
    cost_event_by_status: dict[str, int] = {}
    total_cost_cny: float = 0.0
    settlement_count: int = 0
    settlement_by_status: dict[str, int] = 0
    total_settlement_amount: float = 0.0
    payment_count: int = 0
    payment_by_status: dict[str, int] = {}
    total_payment_amount: float = 0.0
    pending_payment_count: int = 0
    payment_request_count: int = 0
    pending_approval_count: int = 0
    writeoff_count: int = 0
    writeoff_by_status: dict[str, int] = {}
    reconciliation_count: int = 0
    reconciliation_by_status: dict[str, int] = {}
    invoice_count: int = 0
    invoice_by_status: dict[str, int] = {}
    expense_count: int = 0
    expense_by_type: dict[str, int] = {}
    total_expense_amount: float = 0.0
    forex_transaction_count: int = 0
    voucher_count: int = 0
    voucher_by_status: dict[str, int] = {}
    billing_strategy_count: int = 0
    active_billing_strategy_count: int = 0
