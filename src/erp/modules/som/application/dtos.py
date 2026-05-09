from datetime import datetime

from pydantic import BaseModel, Field


class StoreCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=100)
    platform: str = Field(..., min_length=1, max_length=50)
    region: str = Field(default="", max_length=50)
    store_id_on_platform: str = Field(default="", max_length=200)
    seller_id: str = Field(default="", max_length=200)
    currency: str = Field(default="USD", max_length=10)
    org_id: str | None = None


class StoreUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    region: str | None = Field(default=None, max_length=50)
    currency: str | None = Field(default=None, max_length=10)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class StoreAuthRequest(BaseModel):
    new_auth_status: str = Field(..., min_length=1)
    auth_token_encrypted: str = ""
    auth_expires_at: datetime | None = None


class StoreResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    code: str
    platform: str
    region: str = ""
    store_id_on_platform: str = ""
    seller_id: str = ""
    currency: str = "USD"
    status: str = "active"
    auth_status: str = "unauthorized"
    auth_expires_at: datetime | None = None
    org_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ListingCreateRequest(BaseModel):
    store_id: str = Field(..., min_length=1)
    sku_id: str = Field(..., min_length=1)
    channel_sku: str = Field(default="", max_length=200)
    title: str = Field(default="", max_length=1000)
    title_en: str = Field(default="", max_length=1000)
    description: str = ""
    bullet_points: list[str] = Field(default_factory=list)
    search_terms: str = Field(default="", max_length=500)
    main_image: str = Field(default="", max_length=500)
    images: list[str] = Field(default_factory=list)
    price: float = Field(default=0.0, ge=0)
    currency: str = Field(default="USD", max_length=10)
    msrp: float = Field(default=0.0, ge=0)
    sale_price: float = Field(default=0.0, ge=0)
    sale_start: datetime | None = None
    sale_end: datetime | None = None
    quantity: int = Field(default=0, ge=0)
    platform: str = Field(default="", max_length=50)
    category_id: str | None = None


class ListingUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=1000)
    title_en: str | None = Field(default=None, max_length=1000)
    description: str | None = None
    bullet_points: list[str] | None = None
    search_terms: str | None = Field(default=None, max_length=500)
    main_image: str | None = Field(default=None, max_length=500)
    images: list[str] | None = None
    quantity: int | None = Field(default=None, ge=0)
    category_id: str | None = None
    platform: str | None = Field(default=None, max_length=50)
    channel_sku: str | None = Field(default=None, max_length=200)


class ListingDuplicateRequest(BaseModel):
    target_store_id: str | None = None
    copy_images: bool = True
    copy_price: bool = True
    new_title: str | None = Field(default=None, max_length=1000)


class ListingBulkStatusRequest(BaseModel):
    listing_ids: list[str] = Field(..., min_length=1)
    status: str = Field(..., min_length=1)


class ListingSearchRequest(BaseModel):
    keyword: str = Field(default="", max_length=200)
    store_id: str = Field(default="", max_length=36)
    platform: str = Field(default="", max_length=50)
    status: str = Field(default="", max_length=20)
    listing_status: str = Field(default="", max_length=30)
    min_price: float = Field(default=0.0, ge=0)
    max_price: float = Field(default=0.0, ge=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ListingPriceRequest(BaseModel):
    price: float = Field(..., ge=0.01)
    sale_price: float = Field(default=0.0, ge=0)


class ListingStatusRequest(BaseModel):
    status: str = Field(..., min_length=1)


class ListingPlatformStatusRequest(BaseModel):
    listing_status: str = Field(..., min_length=1)


class ListingResponse(BaseModel):
    id: str
    tenant_id: str
    store_id: str
    sku_id: str
    channel_sku: str = ""
    platform_listing_id: str = ""
    title: str = ""
    title_en: str = ""
    description: str = ""
    bullet_points: list = Field(default_factory=list)
    search_terms: str = ""
    main_image: str = ""
    images: list = Field(default_factory=list)
    price: float = 0.0
    currency: str = "USD"
    msrp: float = 0.0
    sale_price: float = 0.0
    sale_start: datetime | None = None
    sale_end: datetime | None = None
    quantity: int = 0
    status: str = "draft"
    listing_status: str = "not_listed"
    platform: str = ""
    category_id: str | None = None
    is_pms_draft: bool = False
    recommendation_id: str = ""
    published_at: datetime | None = None
    created_by: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PriceRuleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    rule_type: str = Field(..., pattern=r"^(markup|markdown|fixed|competitive)$")
    platform: str = Field(default="", max_length=50)
    region: str = Field(default="", max_length=50)
    category_id: str | None = None
    formula: dict = Field(default_factory=dict)
    min_price: float = Field(default=0.0, ge=0)
    max_price: float = Field(default=0.0, ge=0)
    currency: str = Field(default="USD", max_length=10)
    priority: int = Field(default=0, ge=0)


class PriceRuleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    formula: dict | None = None
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    priority: int | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class PriceRuleResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    rule_type: str
    platform: str = ""
    region: str = ""
    category_id: str | None = None
    formula: dict = Field(default_factory=dict)
    min_price: float = 0.0
    max_price: float = 0.0
    currency: str = "USD"
    priority: int = 0
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PriceCalculateRequest(BaseModel):
    cost_price: float = Field(..., ge=0)
    platform: str = Field(default="", max_length=50)
    region: str = Field(default="", max_length=50)
    category_id: str = ""


class BatchJobCreateRequest(BaseModel):
    job_type: str = Field(..., pattern=r"^(publish|update|price_change|stock_sync)$")
    listing_ids: list[str] = Field(..., min_length=1)


class BatchJobResponse(BaseModel):
    id: str
    tenant_id: str
    job_type: str
    total_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    status: str = "pending"
    created_by: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class OperationMonitorRequest(BaseModel):
    store_id: str = Field(..., min_length=1)
    metric_type: str = Field(..., pattern=r"^(sales|traffic|conversion|ads_spend)$")
    metric_date: datetime
    metrics: dict = Field(default_factory=dict)


class OperationMonitorResponse(BaseModel):
    id: str
    tenant_id: str
    store_id: str
    metric_type: str
    metric_date: datetime | None = None
    metrics: dict = Field(default_factory=dict)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ListingOptimizationCreateRequest(BaseModel):
    listing_id: str = Field(..., min_length=1)
    opt_type: str = Field(default="full", pattern=r"^(title|keyword|image|bullet_point|description|full)$")


class ListingOptimizationApplyRequest(BaseModel):
    suggestion_indices: list[int] | None = None


class ListingOptimizationResponse(BaseModel):
    id: str
    tenant_id: str
    listing_id: str
    store_id: str
    opt_type: str
    status: str = "pending"
    score_before: float = 0.0
    score_after: float = 0.0
    suggestions: list = Field(default_factory=list)
    applied_suggestions: list = Field(default_factory=list)
    snapshot_before: dict = Field(default_factory=dict)
    snapshot_after: dict = Field(default_factory=dict)
    created_by: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ListingScoreResponse(BaseModel):
    listing_id: str
    scores: dict = Field(default_factory=dict)
    overall_score: float = 0.0


class AlertRuleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    metric_type: str = Field(..., pattern=r"^(sales|traffic|conversion|ads_spend|inventory|listing)$")
    condition_type: str = Field(..., pattern=r"^(gt|lt|eq|gte|lte|between|change_rate)$")
    threshold: float = 0.0
    threshold_max: float = Field(default=0.0, ge=0)
    time_window: int = Field(default=1, ge=1)
    severity: str = Field(default="warning", pattern=r"^(info|warning|critical)$")
    notify_channels: str = Field(default="email")
    notify_targets: list[str] = Field(default_factory=list)
    platform: str = Field(default="", max_length=50)
    store_id: str = Field(default="")
    cooldown_minutes: int = Field(default=60, ge=0)


class AlertRuleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    metric_type: str | None = None
    condition_type: str | None = None
    threshold: float | None = None
    threshold_max: float | None = None
    time_window: int | None = Field(default=None, ge=1)
    severity: str | None = None
    notify_channels: str | None = None
    notify_targets: list[str] | None = None
    platform: str | None = None
    store_id: str | None = None
    cooldown_minutes: int | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class AlertRuleResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    metric_type: str
    condition_type: str
    threshold: float = 0.0
    threshold_max: float = 0.0
    time_window: int = 1
    severity: str = "warning"
    notify_channels: str = "email"
    notify_targets: list = Field(default_factory=list)
    platform: str = ""
    store_id: str = ""
    cooldown_minutes: int = 60
    status: str = "active"
    created_by: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AlertRecordResponse(BaseModel):
    id: str
    tenant_id: str
    rule_id: str
    rule_name: str = ""
    store_id: str = ""
    metric_type: str = ""
    severity: str = "warning"
    actual_value: float = 0.0
    threshold_value: float = 0.0
    message: str = ""
    detail: dict = Field(default_factory=dict)
    status: str = "firing"
    notified: bool = False
    notified_at: datetime | None = None
    acknowledged_by: str = ""
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AlertCheckRequest(BaseModel):
    store_id: str = Field(..., min_length=1)
    metric_type: str = Field(..., min_length=1)
    actual_value: float = 0.0


class AlertBatchActionRequest(BaseModel):
    record_ids: list[str] = Field(..., min_length=1)


class StoreStatisticsResponse(BaseModel):
    total_stores: int = 0
    active_stores: int = 0
    authorized_stores: int = 0
    by_platform: dict[str, int] = Field(default_factory=dict)
    by_auth_status: dict[str, int] = Field(default_factory=dict)


class ListingStatisticsResponse(BaseModel):
    total_listings: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_listing_status: dict[str, int] = Field(default_factory=dict)
    by_platform: dict[str, int] = Field(default_factory=dict)
    avg_price: float = 0.0
    low_stock_count: int = 0


class MetricsSummaryResponse(BaseModel):
    store_id: str = ""
    metric_type: str = ""
    period_start: datetime | None = None
    period_end: datetime | None = None
    data_points: int = 0
    summary: dict = Field(default_factory=dict)
    trend: dict = Field(default_factory=dict)


class AlertSummaryResponse(BaseModel):
    firing: int = 0
    acknowledged: int = 0
    critical_firing: int = 0
