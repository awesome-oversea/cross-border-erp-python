from datetime import datetime

from pydantic import BaseModel, Field


class SupplierCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=100)
    short_name: str = Field(default="", max_length=100)
    contact_person: str = Field(default="", max_length=100)
    contact_phone: str = Field(default="", max_length=50)
    contact_email: str = Field(default="", max_length=200)
    address: str = Field(default="", max_length=500)
    region: str = Field(default="", max_length=100)
    supplier_type: str = Field(default="general", pattern=r"^(general|factory|trading)$")
    cooperation_level: str = Field(default="normal", pattern=r"^(strategic|normal|trial)$")
    payment_terms: str = ""
    lead_time_days: int = Field(default=0, ge=0)
    min_order_qty: int = Field(default=0, ge=0)
    org_id: str | None = None


class SupplierUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    short_name: str | None = Field(default=None, max_length=100)
    contact_person: str | None = Field(default=None, max_length=100)
    contact_phone: str | None = Field(default=None, max_length=50)
    contact_email: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    region: str | None = Field(default=None, max_length=100)
    cooperation_level: str | None = Field(default=None, pattern=r"^(strategic|normal|trial)$")
    payment_terms: str | None = None
    lead_time_days: int | None = Field(default=None, ge=0)
    min_order_qty: int | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class SupplierResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    code: str
    short_name: str = ""
    contact_person: str = ""
    contact_phone: str = ""
    contact_email: str = ""
    address: str = ""
    region: str = ""
    supplier_type: str = "general"
    cooperation_level: str = "normal"
    payment_terms: str = ""
    lead_time_days: int = 0
    min_order_qty: int = 0
    quality_score: float = 0.0
    delivery_score: float = 0.0
    status: str = "active"
    org_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PurchaseOrderCreateRequest(BaseModel):
    po_no: str = Field(..., min_length=1, max_length=100)
    supplier_id: str = Field(..., min_length=1)
    warehouse_id: str = Field(..., min_length=1)
    po_type: str = Field(default="standard", pattern=r"^(standard|urgent|replenishment|sample)$")
    currency: str = Field(default="CNY", max_length=10)
    expected_delivery_date: datetime | None = None
    remark: str = ""


class PurchaseOrderStatusRequest(BaseModel):
    status: str = Field(..., min_length=1)


class PurchaseOrderItemRequest(BaseModel):
    sku_id: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    expected_date: datetime | None = None


class PurchaseOrderResponse(BaseModel):
    id: str
    tenant_id: str
    po_no: str
    supplier_id: str
    warehouse_id: str
    po_type: str = "standard"
    status: str = "draft"
    currency: str = "CNY"
    total_amount: float = 0.0
    paid_amount: float = 0.0
    expected_delivery_date: datetime | None = None
    actual_delivery_date: datetime | None = None
    remark: str = ""
    created_by: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PurchaseOrderItemResponse(BaseModel):
    id: str
    tenant_id: str
    po_id: str
    sku_id: str
    quantity: int = 0
    received_qty: int = 0
    unit_price: float = 0.0
    item_total: float = 0.0
    expected_date: datetime | None = None
    status: str = "pending"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReplenishmentPlanCreateRequest(BaseModel):
    plan_no: str = Field(..., min_length=1, max_length=100)
    warehouse_id: str = Field(..., min_length=1)
    plan_type: str = Field(default="auto", pattern=r"^(auto|manual|pms_suggested)$")
    items: list = Field(default_factory=list)


class ReplenishmentPlanResponse(BaseModel):
    id: str
    tenant_id: str
    plan_no: str
    warehouse_id: str
    plan_type: str = "auto"
    status: str = "draft"
    items: list = Field(default_factory=list)
    recommendation_id: str = ""
    created_by: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SupplierEvaluationCreateRequest(BaseModel):
    supplier_id: str = Field(..., min_length=1)
    period: str = Field(..., min_length=1, max_length=20)
    quality_score: float = Field(default=0.0, ge=0, le=100)
    delivery_score: float = Field(default=0.0, ge=0, le=100)
    price_score: float = Field(default=0.0, ge=0, le=100)
    service_score: float = Field(default=0.0, ge=0, le=100)
    remarks: str = ""


class SupplierEvaluationResponse(BaseModel):
    id: str
    tenant_id: str
    supplier_id: str
    period: str
    quality_score: float = 0.0
    delivery_score: float = 0.0
    price_score: float = 0.0
    service_score: float = 0.0
    overall_score: float = 0.0
    remarks: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class InquiryCreateRequest(BaseModel):
    inquiry_no: str = Field(..., min_length=1, max_length=100)
    title: str = Field(default="", max_length=500)
    deadline: datetime | None = None
    items: list = Field(default_factory=list)
    target_supplier_ids: list = Field(default_factory=list)


class InquiryQuoteRequest(BaseModel):
    supplier_id: str = Field(..., min_length=1)
    unit_price: float = Field(..., ge=0)
    min_order_qty: int = Field(default=0, ge=0)
    lead_time_days: int = Field(default=0, ge=0)
    remark: str = ""


class SupplierRatingRequest(BaseModel):
    quality_score: float = Field(..., ge=0, le=100)
    delivery_score: float = Field(..., ge=0, le=100)
    price_score: float = Field(..., ge=0, le=100)
    service_score: float = Field(..., ge=0, le=100)


class ProcessingOrderCreateRequest(BaseModel):
    order_no: str = Field(..., min_length=1, max_length=100)
    supplier_id: str = Field(..., min_length=1)
    sku_id: str = Field(default="", max_length=36)
    quantity: int = Field(default=0, ge=0)
    unit_price: float = Field(default=0.0, ge=0)
    currency: str = Field(default="CNY", max_length=10)
    remark: str = ""
    expected_completion_date: str | None = None


POCreateRequest = PurchaseOrderCreateRequest
POItemRequest = PurchaseOrderItemRequest
POStatusRequest = PurchaseOrderStatusRequest
ReplenishmentPlanRequest = ReplenishmentPlanCreateRequest


class SupplierBatchEvaluateRequest(BaseModel):
    evaluations: list[dict] = Field(..., min_length=1)


class POStatisticsResponse(BaseModel):
    total_orders: int = 0
    total_amount: float = 0.0
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}


class SupplierStatisticsResponse(BaseModel):
    total_suppliers: int = 0
    by_type: dict[str, int] = {}
    by_level: dict[str, int] = {}
    avg_quality_score: float = 0.0
