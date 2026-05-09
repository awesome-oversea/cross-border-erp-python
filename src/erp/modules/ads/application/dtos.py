from datetime import datetime

from pydantic import BaseModel, Field


class AdCampaignCreateRequest(BaseModel):
    campaign_no: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=500)
    platform: str = Field(..., min_length=1, max_length=50)
    store_id: str = Field(..., min_length=1)
    campaign_type: str = Field(default="sponsored_products", max_length=30)
    targeting_type: str = Field(default="manual", max_length=30)
    daily_budget: float = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=10)
    start_date: datetime | None = None
    end_date: datetime | None = None


class AdCampaignUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=500)
    daily_budget: float | None = Field(default=None, gt=0)
    end_date: datetime | None = None
    status: str | None = Field(default=None, pattern=r"^(draft|pending|active|paused|completed|cancelled)$")


class AdCampaignResponse(BaseModel):
    id: str
    tenant_id: str
    campaign_no: str
    name: str
    platform: str
    store_id: str
    campaign_type: str = "sponsored_products"
    targeting_type: str = "manual"
    status: str = "draft"
    daily_budget: float = 0.0
    currency: str = "USD"
    start_date: datetime | None = None
    end_date: datetime | None = None
    total_spend: float = 0.0
    total_sales: float = 0.0
    total_impressions: int = 0
    total_clicks: int = 0
    total_orders: int = 0
    acos: float = 0.0
    roas: float = 0.0
    platform_campaign_id: str = ""
    created_by: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AdGroupCreateRequest(BaseModel):
    campaign_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=500)
    default_bid: float = Field(..., gt=0)
    sku_id: str = Field(default="", max_length=36)
    listing_id: str = Field(default="", max_length=36)


class AdGroupResponse(BaseModel):
    id: str
    tenant_id: str
    campaign_id: str
    name: str
    default_bid: float = 0.0
    status: str = "enabled"
    sku_id: str = ""
    listing_id: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AdKeywordCreateRequest(BaseModel):
    campaign_id: str = Field(..., min_length=1)
    ad_group_id: str = Field(..., min_length=1)
    keyword_text: str = Field(..., min_length=1, max_length=500)
    match_type: str = Field(default="broad", pattern=r"^(broad|phrase|exact)$")
    bid: float = Field(..., gt=0)


class AdKeywordUpdateRequest(BaseModel):
    bid: float | None = Field(default=None, gt=0)
    status: str | None = Field(default=None, pattern=r"^(enabled|paused|archived)$")


class AdKeywordResponse(BaseModel):
    id: str
    tenant_id: str
    campaign_id: str
    ad_group_id: str
    keyword_text: str
    match_type: str = "broad"
    bid: float = 0.0
    status: str = "enabled"
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    sales: float = 0.0
    orders: int = 0
    ctr: float = 0.0
    cpc: float = 0.0
    conversion_rate: float = 0.0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AdReportResponse(BaseModel):
    id: str
    tenant_id: str
    campaign_id: str
    report_date: datetime | None = None
    granularity: str = "daily"
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    sales: float = 0.0
    orders: int = 0
    units: int = 0
    ctr: float = 0.0
    cpc: float = 0.0
    acos: float = 0.0
    roas: float = 0.0
    currency: str = "USD"
    store_id: str = ""
    platform: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AdReportCreateRequest(BaseModel):
    """创建广告报表请求"""
    campaign_id: str = Field(..., min_length=1, description="广告活动ID")
    report_date: datetime = Field(description="报表日期")
    granularity: str = Field(default="daily", max_length=20, description="粒度: daily/weekly/monthly")
    impressions: int = Field(default=0, ge=0, description="展示量")
    clicks: int = Field(default=0, ge=0, description="点击量")
    spend: float = Field(default=0.0, ge=0, description="花费")
    sales: float = Field(default=0.0, ge=0, description="销售额")
    orders: int = Field(default=0, ge=0, description="订单数")
    units: int = Field(default=0, ge=0, description="销量")
    currency: str = Field(default="USD", max_length=10, description="币种")
    store_id: str = Field(default="", description="店铺ID")
    platform: str = Field(default="", description="平台")


class PageRequest(BaseModel):
    """通用分页请求参数"""
    page: int = Field(default=1, ge=1, description="页码，从1开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数，最大100")


class AdCampaignSearchRequest(BaseModel):
    """广告活动搜索请求"""
    keyword: str = Field(default="", description="关键词搜索 (活动编号/名称)")
    platform: str = Field(default="", description="平台筛选")
    status: str = Field(default="", description="状态筛选")
    campaign_type: str = Field(default="", description="活动类型筛选")
    store_id: str = Field(default="", description="店铺ID筛选")
    min_budget: float | None = Field(default=None, ge=0, description="最低日预算")
    max_budget: float | None = Field(default=None, ge=0, description="最高日预算")
    start_date: datetime | None = Field(default=None, description="开始日期")
    end_date: datetime | None = Field(default=None, description="结束日期")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class AdCampaignBatchStatusRequest(BaseModel):
    """广告活动批量状态变更请求"""
    campaign_ids: list[str] = Field(..., min_length=1, description="活动ID列表")
    status: str = Field(..., min_length=1, description="目标状态")


class AdKeywordBatchBidRequest(BaseModel):
    """关键词批量出价调整请求"""
    bid_updates: list[dict] = Field(..., min_length=1, description="出价调整列表 [{keyword_id, bid}]")


class AdKeywordSearchRequest(BaseModel):
    """关键词搜索请求"""
    keyword_text: str = Field(default="", description="关键词文本搜索")
    campaign_id: str = Field(default="", description="活动ID筛选")
    ad_group_id: str = Field(default="", description="广告组ID筛选")
    match_type: str = Field(default="", description="匹配类型筛选")
    status: str = Field(default="", description="状态筛选")
    min_bid: float | None = Field(default=None, ge=0, description="最低出价")
    max_bid: float | None = Field(default=None, ge=0, description="最高出价")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class ADSStatisticsResponse(BaseModel):
    """ADS 运营统计概览响应"""
    total_campaigns: int = 0
    active_campaigns: int = 0
    paused_campaigns: int = 0
    total_spend: float = 0.0
    total_sales: float = 0.0
    total_impressions: int = 0
    total_clicks: int = 0
    total_orders: int = 0
    overall_acos: float = 0.0
    overall_roas: float = 0.0
    overall_ctr: float = 0.0
    campaigns_by_platform: dict[str, int] = {}
    campaigns_by_type: dict[str, int] = {}
    campaigns_by_status: dict[str, int] = {}
    spend_by_platform: dict[str, float] = {}
    sales_by_platform: dict[str, float] = {}
    total_keywords: int = 0
    active_keywords: int = 0
    total_ad_groups: int = 0
    smart_bid_rules_count: int = 0
    active_smart_bid_rules: int = 0
