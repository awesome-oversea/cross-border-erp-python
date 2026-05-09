from datetime import datetime

from pydantic import BaseModel, Field


class BiMetricCreateRequest(BaseModel):
    metric_code: str = Field(..., min_length=1, max_length=100)
    metric_name: str = Field(..., min_length=1, max_length=200)
    metric_category: str = Field(default="general", max_length=50)
    metric_unit: str = Field(default="", max_length=30)
    description: str = Field(default="", max_length=500)
    calculation_sql: str = ""
    data_source: str = Field(default="", max_length=100)
    refresh_frequency: str = Field(default="daily", max_length=30)


class BiMetricUpdateRequest(BaseModel):
    metric_name: str | None = Field(default=None, max_length=200)
    metric_category: str | None = Field(default=None, max_length=50)
    metric_unit: str | None = Field(default=None, max_length=30)
    description: str | None = Field(default=None, max_length=500)
    calculation_sql: str | None = None
    data_source: str | None = Field(default=None, max_length=100)
    refresh_frequency: str | None = Field(default=None, max_length=30)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class BiMetricResponse(BaseModel):
    id: str
    tenant_id: str
    metric_code: str
    metric_name: str
    metric_category: str = "general"
    metric_unit: str = ""
    description: str = ""
    calculation_sql: str = ""
    data_source: str = ""
    refresh_frequency: str = "daily"
    status: str = "active"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class BiMetricValueCreateRequest(BaseModel):
    metric_id: str = Field(..., min_length=1)
    metric_code: str = Field(..., min_length=1, max_length=100)
    period_type: str = Field(default="daily", pattern=r"^(hourly|daily|weekly|monthly)$")
    period_date: datetime
    numeric_value: float = 0.0
    text_value: str = Field(default="", max_length=500)
    dimension: dict = Field(default_factory=dict)
    store_id: str = ""
    platform: str = ""


class BiMetricValueResponse(BaseModel):
    id: str
    tenant_id: str
    metric_id: str
    metric_code: str
    period_type: str = "daily"
    period_date: datetime | None = None
    numeric_value: float = 0.0
    text_value: str = ""
    dimension: dict = Field(default_factory=dict)
    store_id: str = ""
    platform: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class BiReportCreateRequest(BaseModel):
    report_code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    report_type: str = Field(default="table", max_length=50)
    category: str = Field(default="general", max_length=50)
    description: str = Field(default="", max_length=500)
    config: dict = Field(default_factory=dict)
    query: dict = Field(default_factory=dict)
    columns: list = Field(default_factory=list)
    filters: list = Field(default_factory=list)
    is_public: bool = True


class BiReportResponse(BaseModel):
    id: str
    tenant_id: str
    report_code: str
    name: str
    report_type: str = "table"
    category: str = "general"
    description: str = ""
    config: dict = Field(default_factory=dict)
    query: dict = Field(default_factory=dict)
    columns: list = Field(default_factory=list)
    filters: list = Field(default_factory=list)
    is_public: bool = True
    owner_id: str = ""
    status: str = "active"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class BiDashboardWidgetCreateRequest(BaseModel):
    dashboard_id: str = Field(..., min_length=1)
    widget_type: str = Field(default="metric_card", max_length=50)
    title: str = Field(default="", max_length=200)
    metric_id: str = ""
    metric_code: str = ""
    report_id: str = ""
    config: dict = Field(default_factory=dict)
    layout: dict = Field(default_factory=dict)
    refresh_interval: int = Field(default=300, ge=0)
    sort_order: int = Field(default=0, ge=0)


class BiDashboardWidgetResponse(BaseModel):
    id: str
    tenant_id: str
    dashboard_id: str
    widget_type: str = "metric_card"
    title: str = ""
    metric_id: str = ""
    metric_code: str = ""
    report_id: str = ""
    config: dict = Field(default_factory=dict)
    layout: dict = Field(default_factory=dict)
    refresh_interval: int = 300
    sort_order: int = 0
    status: str = "active"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class BiMetricSearchRequest(BaseModel):
    keyword: str = Field(default="", description="关键词搜索 (指标编码/名称)")
    metric_category: str = Field(default="", description="指标分类筛选")
    status: str = Field(default="", description="状态筛选")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class BiMetricValueSearchRequest(BaseModel):
    metric_code: str = Field(default="", description="指标编码筛选")
    period_type: str = Field(default="daily", description="周期类型")
    store_id: str = Field(default="", description="店铺ID筛选")
    platform: str = Field(default="", description="平台筛选")
    start_date: datetime | None = Field(default=None, description="开始日期")
    end_date: datetime | None = Field(default=None, description="结束日期")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class BiReportSearchRequest(BaseModel):
    keyword: str = Field(default="", description="关键词搜索 (报表编码/名称)")
    category: str = Field(default="", description="分类筛选")
    report_type: str = Field(default="", description="报表类型筛选")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class BIStatisticsResponse(BaseModel):
    total_metrics: int = 0
    active_metrics: int = 0
    total_metric_values: int = 0
    total_reports: int = 0
    total_widgets: int = 0
    metrics_by_category: dict[str, int] = {}
    kpi_count: int = 0
    alert_rules_count: int = 0
    active_alert_rules: int = 0
    alert_instances_count: int = 0
    pending_alerts: int = 0
