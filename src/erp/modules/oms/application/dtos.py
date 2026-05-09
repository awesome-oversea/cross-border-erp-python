"""
OMS (订单域) 数据传输对象 (DTO)

所有 Pydantic 模型集中定义，供 router 层使用。
禁止在 router / service 中定义内联 DTO。

命名规范:
  - XxxCreateRequest: 创建请求
  - XxxUpdateRequest: 更新请求
  - XxxStatusRequest: 状态变更请求
  - XxxResponse: 响应模型 (from_attributes=True)
  - PageRequest: 分页请求
"""
from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================
# 销售订单 DTO
# ============================================================

class OrderCreateRequest(BaseModel):
    """创建销售订单请求"""
    order_no: str = Field(..., min_length=1, max_length=100)
    platform: str = Field(..., min_length=1, max_length=50)
    store_id: str = Field(..., min_length=1)
    platform_order_id: str = Field(default="", max_length=200)
    order_type: str = Field(default="standard", pattern=r"^(standard|refund|exchange)$")
    order_time: datetime | None = None
    buyer_id: str = Field(default="", max_length=200)
    buyer_name: str = Field(default="", max_length=200)
    recipient_name: str = Field(default="", max_length=200)
    recipient_phone: str = Field(default="", max_length=50)
    recipient_address: str = ""
    recipient_city: str = Field(default="", max_length=100)
    recipient_state: str = Field(default="", max_length=100)
    recipient_country: str = Field(default="", max_length=50)
    recipient_zip: str = Field(default="", max_length=30)
    currency: str = Field(default="USD", max_length=10)
    item_subtotal: float = Field(default=0.0, ge=0)
    shipping_fee: float = Field(default=0.0, ge=0)
    discount_amount: float = Field(default=0.0, ge=0)
    tax_amount: float = Field(default=0.0, ge=0)
    total_amount: float = Field(default=0.0, ge=0)
    warehouse_id: str | None = None
    logistics_channel: str = Field(default="", max_length=100)
    remark: str = ""
    tags: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    raw_data: dict = Field(default_factory=dict)


class OrderStatusRequest(BaseModel):
    """订单状态变更请求"""
    status: str = Field(..., min_length=1)
    remark: str = ""


class OrderItemCreateRequest(BaseModel):
    """添加订单明细请求"""
    sku_id: str = Field(..., min_length=1)
    channel_sku: str = Field(default="", max_length=200)
    product_name: str = Field(default="", max_length=500)
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    discount_amount: float = Field(default=0.0, ge=0)
    platform_item_id: str = Field(default="", max_length=200)


class OrderResponse(BaseModel):
    """销售订单响应"""
    id: str
    tenant_id: str
    order_no: str
    platform: str
    store_id: str
    platform_order_id: str = ""
    order_type: str = "standard"
    status: str = "pending"
    order_time: datetime | None = None
    pay_time: datetime | None = None
    ship_time: datetime | None = None
    complete_time: datetime | None = None
    buyer_name: str = ""
    recipient_name: str = ""
    recipient_country: str = ""
    currency: str = "USD"
    total_amount: float = 0.0
    settlement_amount: float = 0.0
    warehouse_id: str | None = None
    tracking_no: str = ""
    remark: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class OrderItemResponse(BaseModel):
    """订单明细响应"""
    id: str
    tenant_id: str
    order_id: str
    sku_id: str
    channel_sku: str = ""
    product_name: str = ""
    quantity: int = 1
    unit_price: float = 0.0
    discount_amount: float = 0.0
    item_total: float = 0.0
    status: str = "pending"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# ============================================================
# 退款单 DTO
# ============================================================

class RefundCreateRequest(BaseModel):
    """创建退款单请求"""
    refund_no: str = Field(..., min_length=1, max_length=100)
    original_order_id: str = Field(..., min_length=1)
    refund_type: str = Field(..., pattern=r"^(refund_only|return_refund|exchange)$")
    reason: str = Field(default="", max_length=500)
    refund_amount: float = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=10)
    platform_refund_id: str = Field(default="", max_length=200)
    items: list = Field(default_factory=list)


class RefundStatusRequest(BaseModel):
    """退款单状态变更请求"""
    status: str = Field(..., min_length=1)


class RefundApproveRequest(BaseModel):
    """退款审批请求"""
    action: str = Field(..., min_length=1, pattern=r"^(approve|reject)$")
    remark: str = ""


class RefundResponse(BaseModel):
    """退款单响应"""
    id: str
    tenant_id: str
    refund_no: str
    original_order_id: str
    refund_type: str
    reason: str = ""
    status: str = "pending"
    refund_amount: float = 0.0
    currency: str = "USD"
    platform_refund_id: str = ""
    approval_instance_id: str = ""
    processed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ============================================================
# 促销活动 DTO
# ============================================================

class PromotionCreateRequest(BaseModel):
    """创建促销活动请求"""
    promo_no: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=500)
    promo_type: str = Field(..., pattern=r"^(discount|gift|bundle|flash_sale|coupon)$")
    discount_type: str = Field(default="percentage", pattern=r"^(percentage|fixed_amount|free_shipping)$")
    discount_value: float = Field(default=0.0, ge=0)
    min_purchase_amount: float = Field(default=0.0, ge=0)
    max_discount_amount: float = Field(default=0.0, ge=0)
    usage_limit: int = Field(default=0, ge=0)
    per_customer_limit: int = Field(default=0, ge=0)
    platform: str = Field(default="", max_length=50)
    store_id: str = Field(default="", max_length=36)
    start_time: datetime | None = None
    end_time: datetime | None = None
    applicable_skus: list[str] = Field(default_factory=list)
    applicable_categories: list[str] = Field(default_factory=list)
    conditions: dict = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0)
    can_stack: bool = False


class PromotionStatusRequest(BaseModel):
    """促销活动状态变更请求"""
    status: str = Field(..., min_length=1)


class PromotionDiscountRequest(BaseModel):
    """计算订单折扣请求"""
    order_amount: float = Field(..., ge=0)
    sku_id: str = ""
    category_id: str = ""
    platform: str = ""
    store_id: str = ""


class PromotionResponse(BaseModel):
    """促销活动响应"""
    id: str
    tenant_id: str
    promo_no: str
    name: str
    promo_type: str
    discount_type: str = "percentage"
    discount_value: float = 0.0
    min_purchase_amount: float = 0.0
    max_discount_amount: float = 0.0
    usage_limit: int = 0
    used_count: int = 0
    status: str = "draft"
    platform: str = ""
    store_id: str = ""
    start_time: datetime | None = None
    end_time: datetime | None = None
    priority: int = 0
    can_stack: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ============================================================
# 拆单规则 DTO
# ============================================================

class OrderSplitRuleCreateRequest(BaseModel):
    """创建拆单规则请求"""
    name: str = Field(..., min_length=1, max_length=200)
    rule_type: str = Field(..., pattern=r"^(by_warehouse|by_platform|by_weight|by_sku)$")
    conditions: dict = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0)


class OrderSplitRuleResponse(BaseModel):
    """拆单规则响应"""
    id: str
    tenant_id: str
    name: str
    rule_type: str
    conditions: dict = Field(default_factory=dict)
    priority: int = 0
    status: str = "active"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# ============================================================
# 订单操作 DTO (同步/分配/发货/取消/拆单/合单/备注)
# ============================================================

class OrderSyncRequest(BaseModel):
    """订单同步请求"""
    platform: str = Field(..., min_length=1)
    store_id: str = Field(..., min_length=1)
    platform_order_ids: list[str] = Field(default_factory=list)
    sync_type: str = "incremental"
    start_time: datetime | None = None
    end_time: datetime | None = None


class OrderAllocateRequest(BaseModel):
    """订单分配仓库请求"""
    order_ids: list[str] = Field(default_factory=list)
    warehouse_id: str = ""
    strategy: str = "auto"


class OrderShipRequest(BaseModel):
    """订单发货请求"""
    order_id: str = Field(..., min_length=1)
    tracking_number: str = ""
    carrier: str = ""
    shipping_method: str = ""


class OrderCancelRequest(BaseModel):
    """订单取消请求"""
    reason: str = ""
    cancel_type: str = "buyer"


class RiskCheckRequest(BaseModel):
    """订单风控检查请求"""
    order_id: str = Field(..., min_length=1)
    check_types: list[str] = Field(default_factory=lambda: ["amount", "frequency", "address"])


class OrderSplitRequest(BaseModel):
    """订单拆分请求"""
    order_id: str = Field(..., min_length=1)
    split_rules: list[dict] = Field(default_factory=list)


class OrderMergeRequest(BaseModel):
    """订单合并请求"""
    order_ids: list[str] = Field(..., min_length=1)
    merge_reason: str = ""


class OrderRemarkRequest(BaseModel):
    """订单备注更新请求"""
    remark: str = ""
    tags: list[str] = Field(default_factory=list)


# ============================================================
# 订单策略 DTO
# ============================================================

class StrategyCreateRequest(BaseModel):
    """创建订单策略请求"""
    strategy_code: str = Field(..., min_length=1, max_length=100)
    strategy_name: str = Field(..., min_length=1, max_length=200)
    strategy_type: str = Field(..., pattern=r"^(audit|split_merge|profit|risk_control)$")
    description: str = Field(default="")
    condition: dict = Field(default_factory=dict)
    action: dict = Field(default_factory=dict)
    priority: int = Field(default=0)
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class StrategyUpdateRequest(BaseModel):
    """更新订单策略请求"""
    strategy_name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    condition: dict | None = None
    action: dict | None = None
    priority: int | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class StrategyEvaluateRequest(BaseModel):
    """策略评估请求"""
    strategy_type: str = Field(..., pattern=r"^(audit|split_merge|profit|risk_control)$")
    context: dict = Field(default_factory=dict)


class StrategyExecuteRequest(BaseModel):
    """策略执行请求"""
    order_id: str = Field(..., min_length=1)
    order_no: str = Field(default="")
    context: dict = Field(default_factory=dict)


# ============================================================
# 外部交互 DTO (out_router)
# ============================================================

class RiskMarkRequest(BaseModel):
    """订单风控标记请求 (外部交互)"""
    risk_level: str = "medium"
    risk_flags: list[str] = []
    remark: str = ""


# ============================================================
# 通用分页请求
# ============================================================

class PageRequest(BaseModel):
    """通用分页请求"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ============================================================
# 订单搜索 DTO
# ============================================================

class OrderSearchRequest(BaseModel):
    keyword: str = Field(default="", max_length=200)
    platform: str = Field(default="", max_length=50)
    store_id: str = Field(default="", max_length=36)
    status: str = Field(default="", max_length=30)
    order_type: str = Field(default="", max_length=30)
    start_date: datetime | None = None
    end_date: datetime | None = None
    min_amount: float = Field(default=0.0, ge=0)
    max_amount: float = Field(default=0.0, ge=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ============================================================
# 订单统计 DTO
# ============================================================

class OrderStatisticsResponse(BaseModel):
    total_orders: int = 0
    total_amount: float = 0.0
    by_status: dict[str, int] = {}
    by_platform: dict[str, int] = {}
    avg_amount: float = 0.0


class RefundStatisticsResponse(BaseModel):
    total_refunds: int = 0
    total_refund_amount: float = 0.0
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}


# ============================================================
# 批量操作 DTO
# ============================================================

class OrderBatchStatusRequest(BaseModel):
    order_ids: list[str] = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    remark: str = ""


class RefundBatchApproveRequest(BaseModel):
    refund_ids: list[str] = Field(..., min_length=1)
    action: str = Field(..., pattern=r"^(approve|reject)$")
    remark: str = ""


# ============================================================
# 拆单规则 DTO
# ============================================================

class SplitRuleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    rule_type: str = Field(..., pattern=r"^(by_warehouse|by_platform|by_weight|by_sku)$")
    conditions: dict = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0)


class SplitRuleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    conditions: dict | None = None
    priority: int | None = None
    status: str | None = Field(default=None, max_length=20)


# ============================================================
# 审计日志 DTO
# ============================================================

class AuditLogResponse(BaseModel):
    id: str
    tenant_id: str
    order_id: str
    action: str
    from_status: str = ""
    to_status: str = ""
    operator_id: str = ""
    operator_name: str = ""
    remark: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
