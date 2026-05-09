from datetime import datetime

from pydantic import BaseModel, Field


class LogisticsProviderCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=100)
    provider_type: str = Field(default="express", pattern=r"^(express|air|sea|rail|multi)$")
    api_endpoint: str = Field(default="", max_length=500)
    api_key_encrypted: str = ""
    supported_regions: str = Field(default="", max_length=500)


class LogisticsProviderUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    api_endpoint: str | None = Field(default=None, max_length=500)
    api_key_encrypted: str | None = None
    supported_regions: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class LogisticsProviderResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    code: str
    provider_type: str = "express"
    api_endpoint: str = ""
    supported_regions: str = ""
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ShippingMethodCreateRequest(BaseModel):
    provider_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=100)
    shipping_type: str = Field(default="standard", max_length=30)
    estimated_days_min: int = Field(default=0, ge=0)
    estimated_days_max: int = Field(default=0, ge=0)
    first_weight: float = Field(default=0.0, ge=0)
    first_weight_price: float = Field(default=0.0, ge=0)
    additional_weight: float = Field(default=0.0, ge=0)
    additional_weight_price: float = Field(default=0.0, ge=0)
    min_price: float = Field(default=0.0, ge=0)
    currency: str = Field(default="CNY", max_length=10)


class ShippingMethodResponse(BaseModel):
    id: str
    tenant_id: str
    provider_id: str
    name: str
    code: str
    shipping_type: str = "standard"
    estimated_days_min: int = 0
    estimated_days_max: int = 0
    first_weight: float = 0.0
    first_weight_price: float = 0.0
    additional_weight: float = 0.0
    additional_weight_price: float = 0.0
    min_price: float = 0.0
    currency: str = "CNY"
    status: str = "active"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ShipmentCreateRequest(BaseModel):
    shipment_no: str = Field(..., min_length=1, max_length=100)
    order_id: str = Field(..., min_length=1)
    warehouse_id: str = Field(..., min_length=1)
    provider_id: str = Field(..., min_length=1)
    shipping_method_id: str = Field(..., min_length=1)
    weight: float = Field(default=0.0, ge=0)
    shipping_cost: float = Field(default=0.0, ge=0)
    currency: str = Field(default="CNY", max_length=10)
    recipient_name: str = Field(default="", max_length=200)
    recipient_phone: str = Field(default="", max_length=50)
    recipient_address: str = ""
    recipient_country: str = Field(default="", max_length=50)
    items: list = Field(default_factory=list)


class ShipmentStatusRequest(BaseModel):
    status: str = Field(..., min_length=1)
    tracking_no: str = ""


class ShipmentResponse(BaseModel):
    id: str
    tenant_id: str
    shipment_no: str
    order_id: str
    warehouse_id: str
    provider_id: str
    shipping_method_id: str
    tracking_no: str = ""
    status: str = "pending"
    weight: float = 0.0
    shipping_cost: float = 0.0
    currency: str = "CNY"
    recipient_name: str = ""
    recipient_country: str = ""
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class FreightTemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    calculation_type: str = Field(..., pattern=r"^(by_weight|by_volume|by_item|by_fixed)$")
    rules: list = Field(default_factory=list)


class FreightTemplateResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    calculation_type: str
    rules: list = Field(default_factory=list)
    status: str = "active"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProviderCreateRequest(BaseModel):
    """物流商创建请求 (兼容router旧字段名)"""
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=100)
    provider_type: str = Field(default="express", max_length=30)
    api_endpoint: str = Field(default="", max_length=500)
    supported_regions: str = Field(default="", max_length=500)


class TrackingUpdateRequest(BaseModel):
    """物流追踪更新请求"""
    tracking_no: str = Field(..., min_length=1, max_length=100)
    events: list = Field(default_factory=list)


class RateEstimateRequest(BaseModel):
    """运费估算请求"""
    origin: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    weight: float = Field(..., ge=0)
    dimensions: str = ""


class BatchCreateRequest(BaseModel):
    """发货批次创建请求"""
    carrier_id: str = Field(..., min_length=1)
    shipment_ids: list[str] = Field(default_factory=list)
    remark: str = ""


class FreightCalculateRequest(BaseModel):
    """运费计算请求"""
    origin_country: str = Field(..., min_length=1)
    destination_country: str = Field(..., min_length=1)
    weight_kg: float = Field(..., ge=0)
    length_cm: float = Field(default=0.0, ge=0)
    width_cm: float = Field(default=0.0, ge=0)
    height_cm: float = Field(default=0.0, ge=0)
    shipping_method_id: str = ""
    carrier_id: str = ""


class LabelRequest(BaseModel):
    """面单申请请求"""
    shipment_id: str = Field(..., min_length=1)
    carrier_id: str = Field(..., min_length=1)
    label_format: str = Field(default="PDF", max_length=20)
    label_size: str = Field(default="100x100", max_length=20)


class StrategyCreateRequest(BaseModel):
    """物流策略创建请求"""
    strategy_code: str = Field(..., min_length=1, max_length=100)
    strategy_name: str = Field(..., min_length=1, max_length=200)
    strategy_type: str = Field(..., min_length=1, max_length=50)
    description: str = Field(default="", max_length=500)
    condition: dict | None = None
    action: dict | None = None
    priority: int = Field(default=0, ge=0)
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class StrategyUpdateRequest(BaseModel):
    """物流策略更新请求"""
    strategy_name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    condition: dict | None = None
    action: dict | None = None
    priority: int | None = Field(default=None, ge=0)


class StrategyExecutionRequest(BaseModel):
    """物流策略执行请求"""
    shipment_id: str = ""
    order_id: str = ""
    context: dict | None = None


class ConnectorCreateRequest(BaseModel):
    """物流连接器创建请求"""
    connector_name: str = Field(..., min_length=1, max_length=200)
    connector_code: str = Field(..., min_length=1, max_length=100)
    carrier_name: str = Field(..., min_length=1, max_length=200)
    carrier_code: str = Field(..., min_length=1, max_length=50)
    connector_type: str = Field(default="domestic", max_length=30)
    api_base_url: str = Field(default="", max_length=500)
    auth_type: str = Field(default="api_key", max_length=30)
    auth_config: dict | None = None
    supported_services: list | None = None
    supported_label_formats: list | None = None
    supported_origins: list | None = None
    supported_destinations: list | None = None
    rate_limit_per_minute: int = Field(default=60, ge=1)
    timeout_seconds: int = Field(default=30, ge=5)
    max_retries: int = Field(default=3, ge=0)
    description: str = Field(default="", max_length=500)


class LabelApplyRequest(BaseModel):
    """面单申请请求 (连接器维度)"""
    connector_id: str = Field(..., min_length=1)
    shipment_id: str = Field(..., min_length=1)
    service_code: str = ""
    label_format: str = Field(default="pdf", max_length=20)
    shipper: dict | None = None
    recipient: dict | None = None
    packages: list | None = None
    request_params: dict | None = None


class TrackingQueryRequest(BaseModel):
    """物流轨迹查询请求"""
    connector_id: str = Field(..., min_length=1)
    tracking_number: str = Field(..., min_length=1, max_length=100)
    shipment_id: str = ""
    carrier_code: str = ""


class FreightQuoteRequest(BaseModel):
    """运费报价请求"""
    connector_id: str = Field(..., min_length=1)
    origin_country: str = Field(..., min_length=1, max_length=10)
    destination_country: str = Field(..., min_length=1, max_length=10)
    weight_grams: int = Field(default=0, ge=0)
    dimensions: dict | None = None
    origin_zip: str = ""
    destination_zip: str = ""
    service_code: str = ""


class DispatchCreateRequest(BaseModel):
    """发货调度创建请求"""
    connector_id: str = Field(..., min_length=1)
    shipment_id: str = Field(..., min_length=1)
    service_code: str = ""
    packages: list | None = None
    request_params: dict | None = None


class DispatchCancelRequest(BaseModel):
    """发货调度取消请求"""
    dispatch_id: str = Field(..., min_length=1)


class PageRequest(BaseModel):
    """通用分页请求"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ShippingBatchResponse(BaseModel):
    id: str
    tenant_id: str
    batch_no: str
    carrier_id: str
    carrier_name: str = ""
    shipment_count: int = 0
    total_weight: float = 0.0
    total_cost: float = 0.0
    currency: str = "CNY"
    status: str = "created"
    remark: str = ""
    shipped_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class TrackingEventResponse(BaseModel):
    shipment_id: str
    shipment_no: str
    tracking_no: str
    status: str
    latest_event: dict | None = None
    all_events: list = Field(default_factory=list)
    exception: dict | None = None
    is_delivered: bool = False


class CarrierPerformanceResponse(BaseModel):
    carrier_id: str
    carrier_name: str
    total_shipments: int = 0
    delivered: int = 0
    delivery_rate_pct: float = 0.0
    avg_delivery_days: float = 0.0
    avg_cost: float = 0.0


class ConnectorResponse(BaseModel):
    id: str
    tenant_id: str
    connector_name: str
    connector_code: str
    carrier_name: str
    carrier_code: str
    connector_type: str = "domestic"
    api_base_url: str = ""
    auth_type: str = "api_key"
    is_active: bool = True
    health_status: str = "unknown"
    description: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ConnectorUpdateRequest(BaseModel):
    connector_name: str | None = Field(default=None, max_length=200)
    api_base_url: str | None = Field(default=None, max_length=500)
    auth_type: str | None = Field(default=None, max_length=30)
    auth_config: dict | None = None
    rate_limit_per_minute: int | None = Field(default=None, ge=1)
    timeout_seconds: int | None = Field(default=None, ge=5)
    max_retries: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class StrategyResponse(BaseModel):
    id: str
    tenant_id: str
    strategy_code: str
    strategy_name: str
    strategy_type: str
    description: str = ""
    condition: dict | None = None
    action: dict | None = None
    priority: int = 0
    is_active: bool = True
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    version: int = 1
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class StrategyExecutionLogResponse(BaseModel):
    id: str
    strategy_id: str
    strategy_code: str
    strategy_type: str
    shipment_id: str = ""
    order_id: str = ""
    result: str = "applied"
    result_detail: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class FreightTemplateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    calculation_type: str | None = Field(default=None, pattern=r"^(by_weight|by_volume|by_item|by_fixed)$")
    rules: list | None = None
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class ShippingMethodUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    shipping_type: str | None = Field(default=None, max_length=30)
    estimated_days_min: int | None = Field(default=None, ge=0)
    estimated_days_max: int | None = Field(default=None, ge=0)
    first_weight: float | None = Field(default=None, ge=0)
    first_weight_price: float | None = Field(default=None, ge=0)
    additional_weight: float | None = Field(default=None, ge=0)
    additional_weight_price: float | None = Field(default=None, ge=0)
    min_price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=10)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class ShipmentSearchRequest(BaseModel):
    order_id: str = ""
    status: str = ""
    provider_id: str = ""
    tracking_no: str = ""
    recipient_country: str = ""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ShipmentBatchStatusRequest(BaseModel):
    shipment_ids: list[str] = Field(default_factory=list)
    status: str = Field(..., min_length=1)


class ProviderTestRequest(BaseModel):
    provider_id: str = Field(..., min_length=1)


class TMSStatisticsResponse(BaseModel):
    provider_count: int = 0
    active_provider_count: int = 0
    shipment_count: int = 0
    pending_shipment_count: int = 0
    in_transit_count: int = 0
    delivered_count: int = 0
    exception_count: int = 0
    batch_count: int = 0
    active_batch_count: int = 0
    method_count: int = 0
    active_method_count: int = 0
    strategy_count: int = 0
    active_strategy_count: int = 0
    connector_count: int = 0
    active_connector_count: int = 0
    total_shipping_cost: float = 0.0
    avg_delivery_days: float = 0.0
