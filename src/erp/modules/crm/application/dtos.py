from datetime import datetime

from pydantic import BaseModel, Field


class CustomerCreateRequest(BaseModel):
    customer_no: str = Field(..., min_length=1, max_length=100)
    name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=50)
    platform: str = Field(default="", max_length=50)
    store_id: str = Field(default="", max_length=36)
    platform_customer_id: str = Field(default="", max_length=200)
    country: str = Field(default="", max_length=50)
    state: str = Field(default="", max_length=100)
    city: str = Field(default="", max_length=100)
    address: str = Field(default="", max_length=500)
    zip_code: str = Field(default="", max_length=30)


class CustomerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    country: str | None = Field(default=None, max_length=50)
    state: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    segment: str | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, pattern=r"^(active|inactive|blacklist)$")


class CustomerResponse(BaseModel):
    id: str
    tenant_id: str
    customer_no: str
    name: str = ""
    email: str = ""
    phone: str = ""
    platform: str = ""
    store_id: str = ""
    platform_customer_id: str = ""
    country: str = ""
    state: str = ""
    city: str = ""
    segment: str = "normal"
    total_orders: int = 0
    total_amount: float = 0.0
    avg_order_value: float = 0.0
    last_order_at: datetime | None = None
    first_order_at: datetime | None = None
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CustomerTagCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(default="#1890ff", max_length=20)
    tag_type: str = Field(default="manual", max_length=30)
    auto_rule: dict = Field(default_factory=dict)


class CustomerTagResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    color: str = "#1890ff"
    tag_type: str = "manual"
    auto_rule: dict = Field(default_factory=dict)
    customer_count: int = 0
    status: str = "active"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReviewResponse(BaseModel):
    id: str
    tenant_id: str
    platform: str = ""
    store_id: str = ""
    platform_review_id: str = ""
    order_id: str = ""
    sku_id: str = ""
    customer_id: str = ""
    rating: int = 0
    title: str = ""
    content: str = ""
    reply: str = ""
    is_negative: bool = False
    status: str = "pending"
    review_date: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReviewReplyRequest(BaseModel):
    reply: str = Field(..., min_length=1)


class ServiceTicketCreateRequest(BaseModel):
    ticket_no: str = Field(..., min_length=1, max_length=100)
    customer_id: str = Field(..., min_length=1)
    order_id: str = Field(default="", max_length=36)
    ticket_type: str = Field(default="inquiry", pattern=r"^(inquiry|complaint|return|exchange|other)$")
    priority: str = Field(default="normal", pattern=r"^(low|normal|high|urgent)$")
    channel: str = Field(default="email", max_length=30)
    platform: str = Field(default="", max_length=50)
    store_id: str = Field(default="", max_length=36)
    subject: str = Field(default="", max_length=500)
    description: str = ""
    assigned_to: str = ""
    assigned_group: str = ""


class ServiceTicketUpdateRequest(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(open|in_progress|waiting|resolved|closed)$")
    priority: str | None = Field(default=None, pattern=r"^(low|normal|high|urgent)$")
    assigned_to: str | None = None
    resolution: str | None = None


class ServiceTicketResponse(BaseModel):
    id: str
    tenant_id: str
    ticket_no: str
    customer_id: str
    order_id: str = ""
    ticket_type: str = "inquiry"
    priority: str = "normal"
    status: str = "open"
    channel: str = "email"
    platform: str = ""
    store_id: str = ""
    subject: str = ""
    description: str = ""
    resolution: str = ""
    assigned_to: str = ""
    assigned_group: str = ""
    sla_due_at: datetime | None = None
    first_response_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    satisfaction_score: int = 0
    created_by: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReturnRefundCreateRequest(BaseModel):
    return_no: str = Field(..., min_length=1, max_length=100)
    order_id: str = Field(..., min_length=1)
    customer_id: str = Field(..., min_length=1)
    sku_id: str = Field(..., min_length=1)
    ticket_id: str = ""
    return_type: str = Field(default="return", pattern=r"^(return|refund_only|exchange)$")
    reason: str = Field(default="", max_length=200)
    reason_code: str = Field(default="", max_length=50)
    quantity: int = Field(..., gt=0)
    refund_amount: float = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=10)
    platform: str = Field(default="", max_length=50)
    store_id: str = Field(default="", max_length=36)


class ReturnRefundResponse(BaseModel):
    id: str
    tenant_id: str
    return_no: str
    order_id: str
    customer_id: str
    sku_id: str
    ticket_id: str = ""
    return_type: str = "return"
    reason: str = ""
    reason_code: str = ""
    quantity: int = 0
    refund_amount: float = 0.0
    currency: str = "USD"
    status: str = "requested"
    platform: str = ""
    store_id: str = ""
    received_at: datetime | None = None
    refunded_at: datetime | None = None
    created_by: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CustomerTagRequest(BaseModel):
    tags: list[str]


class CommunicationCreateRequest(BaseModel):
    customer_id: str = Field(..., min_length=1)
    channel: str = Field(default="email", max_length=30)
    direction: str = Field(default="outbound", max_length=20)
    subject: str = Field(default="", max_length=500)
    content: str = ""
    order_id: str = ""


class CommunicationResponse(BaseModel):
    id: str
    tenant_id: str
    customer_id: str
    channel: str = "email"
    direction: str = "outbound"
    subject: str = ""
    content: str = ""
    order_id: str = ""
    status: str = "sent"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReviewCreateRequest(BaseModel):
    platform: str = Field(..., min_length=1, max_length=50)
    store_id: str = Field(..., min_length=1, max_length=36)
    rating: int = Field(..., ge=1, le=5)
    title: str = Field(default="", max_length=500)
    content: str = ""
    sku_id: str = ""
    order_id: str = ""
    platform_review_id: str = ""


class ReviewStatusRequest(BaseModel):
    status: str = Field(..., min_length=1)


class TicketAssignRequest(BaseModel):
    assigned_to: str = Field(..., min_length=1)
    assigned_group: str = ""


class TicketResolveRequest(BaseModel):
    resolution: str = Field(..., min_length=1)
    satisfaction_score: int = Field(default=0, ge=0, le=5)


class ReturnProcessRequest(BaseModel):
    action: str = Field(default="approve", pattern=r"^(approve|reject)$")
    refund_amount: float = Field(default=0.0, ge=0)
    remark: str = ""


class ComplaintCreateRequest(BaseModel):
    customer_id: str = Field(..., min_length=1)
    complaint_type: str = Field(default="quality", max_length=50)
    channel: str = Field(default="email", max_length=30)
    platform: str = Field(default="", max_length=50)
    store_id: str = Field(default="", max_length=36)
    order_id: str = ""
    subject: str = Field(default="", max_length=500)
    description: str = ""
    priority: str = Field(default="normal", pattern=r"^(low|normal|high|urgent)$")


class ComplaintResolveRequest(BaseModel):
    resolution: str = Field(..., min_length=1)
    resolved_by: str = ""


class MessageReplyRequest(BaseModel):
    content: str = Field(..., min_length=1)
    replied_by: str = ""


class SentimentAnalysisRequest(BaseModel):
    review_id: str = Field(..., min_length=1)
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    sentiment_label: str = "neutral"
    keywords: list[str] = Field(default_factory=list)
    aspects: list[dict] = Field(default_factory=list)


class ReplyTemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    channel: str = Field(default="email", max_length=30)
    language: str = Field(default="en", max_length=10)
    template_content: str = Field(..., min_length=1)
    category: str = Field(default="general", pattern=r"^(general|positive|negative|neutral|complaint)$")


class ReplyTemplateResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    category: str = "general"
    language: str = "en"
    platform: str = ""
    content_template: str = ""
    is_default: bool = False
    usage_count: int = 0
    status: str = "active"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PageRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class CustomerSearchRequest(BaseModel):
    keyword: str = Field(default="", description="关键词搜索 (客户编号/名称/邮箱)")
    platform: str = Field(default="", description="平台筛选")
    segment: str = Field(default="", description="客户分群筛选")
    status: str = Field(default="", description="状态筛选")
    country: str = Field(default="", description="国家筛选")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class TicketSearchRequest(BaseModel):
    keyword: str = Field(default="", description="关键词搜索 (工单号/主题)")
    status: str = Field(default="", description="状态筛选")
    ticket_type: str = Field(default="", description="工单类型筛选")
    priority: str = Field(default="", description="优先级筛选")
    assigned_to: str = Field(default="", description="处理人筛选")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class CRMStatisticsResponse(BaseModel):
    total_customers: int = 0
    active_customers: int = 0
    customers_by_platform: dict[str, int] = {}
    customers_by_segment: dict[str, int] = {}
    total_tickets: int = 0
    open_tickets: int = 0
    overdue_tickets: int = 0
    avg_resolution_hours: float = 0.0
    total_returns: int = 0
    pending_returns: int = 0
    total_refund_amount: float = 0.0
    total_reviews: int = 0
    negative_reviews: int = 0
    unreplied_reviews: int = 0
    total_complaints: int = 0
    open_complaints: int = 0
