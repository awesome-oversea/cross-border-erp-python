from datetime import datetime

from pydantic import BaseModel, Field


class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=100)
    parent_id: str | None = None
    sort_order: int = Field(default=0, ge=0)


class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    sort_order: int | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class CategoryResponse(BaseModel):
    id: str
    tenant_id: str
    parent_id: str | None = None
    name: str
    code: str
    path: str = ""
    level: int = 1
    sort_order: int = 0
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class BrandCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=100)
    name_en: str = Field(default="", max_length=200)
    logo_url: str = Field(default="", max_length=500)


class BrandUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)
    logo_url: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class BrandResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    name_en: str = ""
    code: str
    logo_url: str = ""
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SPUCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    code: str = Field(..., min_length=1, max_length=100)
    name_en: str = Field(default="", max_length=500)
    category_id: str | None = None
    brand_id: str | None = None
    description: str = ""
    main_image: str = Field(default="", max_length=500)
    images: list[str] = Field(default_factory=list)
    attributes: dict = Field(default_factory=dict)
    spu_type: str = Field(default="normal", pattern=r"^(normal|bundle|virtual)$")
    origin_country: str = Field(default="", max_length=50)
    hs_code: str = Field(default="", max_length=30)
    declared_value: float = Field(default=0.0, ge=0)
    declared_currency: str = Field(default="CNY", max_length=10)


class SPUUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=500)
    name_en: str | None = Field(default=None, max_length=500)
    category_id: str | None = None
    brand_id: str | None = None
    description: str | None = None
    main_image: str | None = Field(default=None, max_length=500)
    images: list[str] | None = None
    attributes: dict | None = None
    origin_country: str | None = Field(default=None, max_length=50)
    hs_code: str | None = Field(default=None, max_length=30)
    declared_value: float | None = Field(default=None, ge=0)
    declared_currency: str | None = Field(default=None, max_length=10)


class SPUStatusRequest(BaseModel):
    status: str = Field(..., min_length=1)


class SPUResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    name_en: str = ""
    code: str
    category_id: str | None = None
    brand_id: str | None = None
    description: str = ""
    main_image: str = ""
    images: list = Field(default_factory=list)
    attributes: dict = Field(default_factory=dict)
    status: str = "draft"
    spu_type: str = "normal"
    origin_country: str = ""
    hs_code: str = ""
    declared_value: float = 0.0
    declared_currency: str = "CNY"
    created_by: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SKUCreateRequest(BaseModel):
    spu_id: str = Field(..., min_length=1)
    sku_code: str = Field(..., min_length=1, max_length=100)
    barcode: str = Field(default="", max_length=50)
    name: str = Field(default="", max_length=500)
    variant_attrs: dict = Field(default_factory=dict)
    spec: dict = Field(default_factory=dict)
    weight: float = Field(default=0.0, ge=0)
    length: float = Field(default=0.0, ge=0)
    width: float = Field(default=0.0, ge=0)
    height: float = Field(default=0.0, ge=0)
    cost_price: float = Field(default=0.0, ge=0)
    cost_currency: str = Field(default="CNY", max_length=10)
    purchase_price: float = Field(default=0.0, ge=0)
    supplier_id: str | None = None
    image: str = Field(default="", max_length=500)


class SKUUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=500)
    barcode: str | None = Field(default=None, max_length=50)
    variant_attrs: dict | None = None
    spec: dict | None = None
    weight: float | None = Field(default=None, ge=0)
    length: float | None = Field(default=None, ge=0)
    width: float | None = Field(default=None, ge=0)
    height: float | None = Field(default=None, ge=0)
    cost_price: float | None = Field(default=None, ge=0)
    purchase_price: float | None = Field(default=None, ge=0)
    supplier_id: str | None = None
    image: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class SKUResponse(BaseModel):
    id: str
    tenant_id: str
    spu_id: str
    sku_code: str
    barcode: str = ""
    name: str = ""
    variant_attrs: dict = Field(default_factory=dict)
    spec: dict = Field(default_factory=dict)
    weight: float = 0.0
    length: float = 0.0
    width: float = 0.0
    height: float = 0.0
    cost_price: float = 0.0
    cost_currency: str = "CNY"
    purchase_price: float = 0.0
    supplier_id: str | None = None
    status: str = "active"
    image: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelMappingCreateRequest(BaseModel):
    sku_id: str = Field(..., min_length=1)
    channel: str = Field(..., min_length=1, max_length=50)
    channel_sku: str = Field(..., min_length=1, max_length=200)
    channel_product_id: str = Field(default="", max_length=200)
    store_id: str = Field(default="", max_length=36)


class ChannelMappingResponse(BaseModel):
    id: str
    tenant_id: str
    sku_id: str
    channel: str
    channel_sku: str
    channel_product_id: str = ""
    store_id: str = ""
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProductProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    code: str = Field(..., min_length=1, max_length=100)
    category_id: str | None = None
    priority: str = Field(default="medium", pattern=r"^(low|medium|high|urgent)$")
    owner_id: str = Field(default="", max_length=36)
    target_market: str = Field(default="", max_length=200)
    target_platform: str = Field(default="", max_length=200)
    recommendation_id: str = Field(default="", max_length=36)


class ProductProjectStageRequest(BaseModel):
    stage: str = Field(..., min_length=1)


class ProductProjectResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    code: str
    category_id: str | None = None
    stage: str = "proposing"
    priority: str = "medium"
    owner_id: str = ""
    target_market: str = ""
    target_platform: str = ""
    status: str = "draft"
    recommendation_id: str = ""
    spu_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class QualityStandardCreateRequest(BaseModel):
    category_id: str | None = None
    name: str = Field(..., min_length=1, max_length=200)
    standard_type: str = Field(default="general", max_length=50)
    items: list = Field(default_factory=list)
    logistics_attrs: dict = Field(default_factory=dict)
    packaging_cost: float = Field(default=0.0, ge=0)


class QualityStandardResponse(BaseModel):
    id: str
    tenant_id: str
    category_id: str | None = None
    name: str
    standard_type: str = "general"
    items: list = Field(default_factory=list)
    logistics_attrs: dict = Field(default_factory=dict)
    packaging_cost: float = 0.0
    status: str = "active"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class IPRecordCreateRequest(BaseModel):
    sku_id: str | None = None
    spu_id: str | None = None
    ip_type: str = Field(..., pattern=r"^(trademark|patent|copyright)$")
    ip_number: str = Field(default="", max_length=100)
    ip_name: str = Field(default="", max_length=200)
    risk_level: str = Field(default="none", pattern=r"^(none|low|medium|high)$")
    notes: str = ""


class IPRecordResponse(BaseModel):
    id: str
    tenant_id: str
    sku_id: str | None = None
    spu_id: str | None = None
    ip_type: str
    ip_number: str = ""
    ip_name: str = ""
    status: str = "active"
    risk_level: str = "none"
    notes: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SensitiveWordCreateRequest(BaseModel):
    word: str = Field(..., min_length=1, max_length=200)
    word_type: str = Field(default="general", pattern=r"^(general|trademark|prohibited)$")
    language: str = Field(default="en", max_length=10)
    platform: str = Field(default="", max_length=50)


class SensitiveWordResponse(BaseModel):
    id: str
    tenant_id: str
    word: str
    word_type: str = "general"
    language: str = "en"
    platform: str = ""
    status: str = "active"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class UPCAllocateRequest(BaseModel):
    sku_id: str = Field(..., min_length=1)


class UPCBatchCreateRequest(BaseModel):
    upc_codes: list[str] = Field(..., min_length=1)


class UPCResponse(BaseModel):
    id: str
    tenant_id: str
    upc_code: str
    sku_id: str | None = None
    status: str = "available"
    allocated_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SPUSearchRequest(BaseModel):
    keyword: str = Field(default="", description="关键词搜索 (SPU编码/名称)")
    category_id: str = Field(default="", description="分类ID筛选")
    brand_id: str = Field(default="", description="品牌ID筛选")
    status: str = Field(default="", description="状态筛选")
    spu_type: str = Field(default="", description="SPU类型筛选")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class SKUSearchRequest(BaseModel):
    keyword: str = Field(default="", description="关键词搜索 (SKU编码/名称)")
    spu_id: str = Field(default="", description="SPU ID筛选")
    status: str = Field(default="", description="状态筛选")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class PDMStatisticsResponse(BaseModel):
    total_categories: int = 0
    total_brands: int = 0
    total_spus: int = 0
    active_spus: int = 0
    total_skus: int = 0
    active_skus: int = 0
    total_channel_mappings: int = 0
    total_product_projects: int = 0
    active_projects: int = 0
    total_ip_records: int = 0
    high_risk_ip: int = 0
    total_quality_standards: int = 0
    total_sensitive_words: int = 0
    available_upc_count: int = 0
    spus_by_category: dict[str, int] = {}
    spus_by_status: dict[str, int] = {}


class BundleProductCreateRequest(BaseModel):
    """组合产品(Bundle)创建请求"""
    spu_id: str = Field(..., min_length=1, description="组合产品SPU ID")
    component_sku_id: str = Field(..., min_length=1, description="子组件SKU ID")
    quantity: int = Field(default=1, ge=1, description="子组件数量")
    discount_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="组合折扣百分比")
    sort_order: int = Field(default=0, ge=0, description="排序序号")


class BundleProductUpdateRequest(BaseModel):
    """组合产品(Bundle)更新请求"""
    quantity: int | None = Field(default=None, ge=1, description="子组件数量")
    discount_pct: float | None = Field(default=None, ge=0.0, le=100.0, description="组合折扣百分比")
    sort_order: int | None = Field(default=None, ge=0, description="排序序号")


class BundleProductResponse(BaseModel):
    """组合产品(Bundle)响应"""
    id: str = ""
    tenant_id: str = ""
    spu_id: str = ""
    component_sku_id: str = ""
    quantity: int = 1
    discount_pct: float = 0.0
    sort_order: int = 0
    created_at: str = ""
    updated_at: str = ""


class TitleLibraryCreateRequest(BaseModel):
    """标题库创建请求"""
    category_id: str = Field(default="", description="分类ID")
    platform: str = Field(default="", max_length=50, description="适用平台: amazon/shopify/ebay/...")
    language: str = Field(default="en", max_length=10, description="语言: en/de/fr/es/ja/...")
    title: str = Field(..., min_length=1, max_length=1000, description="标题内容")
    keywords_json: str = Field(default="[]", description="关键词列表JSON")
    score: float = Field(default=0.0, ge=0.0, le=100.0, description="SEO评分")


class TitleLibraryUpdateRequest(BaseModel):
    """标题库更新请求"""
    title: str | None = Field(default=None, max_length=1000, description="标题内容")
    keywords_json: str | None = Field(default=None, description="关键词列表JSON")
    score: float | None = Field(default=None, ge=0.0, le=100.0, description="SEO评分")
    status: str | None = Field(default=None, description="状态: active/disabled")


class TitleLibraryResponse(BaseModel):
    """标题库响应"""
    id: str = ""
    tenant_id: str = ""
    category_id: str = ""
    platform: str = ""
    language: str = ""
    title: str = ""
    keywords_json: str = "[]"
    usage_count: int = 0
    score: float = 0.0
    status: str = "active"
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""


class ImageLibraryCreateRequest(BaseModel):
    """图片库创建请求"""
    sku_id: str = Field(default="", description="关联SKU ID")
    spu_id: str = Field(default="", description="关联SPU ID")
    image_type: str = Field(default="main", description="图片类型: main/detail/lifestyle/infographic/size_chart")
    url: str = Field(..., min_length=1, max_length=1000, description="图片URL")
    thumbnail_url: str = Field(default="", max_length=1000, description="缩略图URL")
    alt_text: str = Field(default="", max_length=500, description="替代文本")
    tags_json: str = Field(default="[]", description="标签列表JSON")
    platform: str = Field(default="", max_length=50, description="适用平台")


class ImageLibraryUpdateRequest(BaseModel):
    """图片库更新请求"""
    image_type: str | None = Field(default=None, description="图片类型")
    url: str | None = Field(default=None, max_length=1000, description="图片URL")
    thumbnail_url: str | None = Field(default=None, max_length=1000, description="缩略图URL")
    alt_text: str | None = Field(default=None, max_length=500, description="替代文本")
    tags_json: str | None = Field(default=None, description="标签列表JSON")
    platform: str | None = Field(default=None, max_length=50, description="适用平台")
    status: str | None = Field(default=None, description="状态: active/disabled")


class ImageLibraryResponse(BaseModel):
    """图片库响应"""
    id: str = ""
    tenant_id: str = ""
    sku_id: str = ""
    spu_id: str = ""
    image_type: str = "main"
    url: str = ""
    thumbnail_url: str = ""
    alt_text: str = ""
    tags_json: str = "[]"
    platform: str = ""
    status: str = "active"
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""


class ProductIssueCreateRequest(BaseModel):
    """产品问题创建请求"""
    sku_id: str = Field(default="", description="关联SKU ID")
    spu_id: str = Field(default="", description="关联SPU ID")
    issue_type: str = Field(..., description="问题类型: quality/packaging/labeling/safety/compliance")
    severity: str = Field(default="medium", description="严重程度: critical/high/medium/low")
    description: str = Field(default="", description="问题描述")
    evidence_json: str = Field(default="[]", description="证据附件JSON")
    assigned_to: str = Field(default="", description="处理人ID")


class ProductIssueUpdateRequest(BaseModel):
    """产品问题更新请求"""
    issue_type: str | None = Field(default=None, description="问题类型")
    severity: str | None = Field(default=None, description="严重程度")
    description: str | None = Field(default=None, description="问题描述")
    status: str | None = Field(default=None, description="状态: open/in_progress/resolved/closed")
    assigned_to: str | None = Field(default=None, description="处理人ID")
    resolution: str | None = Field(default=None, description="解决方案")


class ProductIssueResponse(BaseModel):
    """产品问题响应"""
    id: str = ""
    tenant_id: str = ""
    sku_id: str = ""
    spu_id: str = ""
    issue_type: str = ""
    severity: str = "medium"
    description: str = ""
    evidence_json: str = "[]"
    status: str = "open"
    assigned_to: str = ""
    resolution: str = ""
    resolved_at: str = ""
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""
