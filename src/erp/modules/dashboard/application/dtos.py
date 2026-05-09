from datetime import datetime

from pydantic import BaseModel, Field


class DashboardCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    layout: dict = Field(default_factory=dict)
    is_default: bool = False
    is_public: bool = True
    sort_order: int = Field(default=0, ge=0)


class DashboardUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    layout: dict | None = None
    is_default: bool | None = None
    is_public: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class DashboardResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    code: str
    description: str = ""
    layout: dict = Field(default_factory=dict)
    is_default: bool = False
    is_public: bool = True
    owner_id: str = ""
    sort_order: int = 0
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class DashboardComponentCreateRequest(BaseModel):
    dashboard_id: str = Field(..., min_length=1)
    component_type: str = Field(default="metric_card", max_length=50)
    title: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=500)
    data_source: str = Field(default="", max_length=100)
    config: dict = Field(default_factory=dict)
    layout_config: dict = Field(default_factory=dict)
    style: dict = Field(default_factory=dict)
    refresh_interval: int = Field(default=300, ge=0)
    sort_order: int = Field(default=0, ge=0)


class DashboardComponentUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    data_source: str | None = Field(default=None, max_length=100)
    config: dict | None = None
    layout_config: dict | None = None
    style: dict | None = None
    refresh_interval: int | None = Field(default=None, ge=0)
    sort_order: int | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class DashboardComponentResponse(BaseModel):
    id: str
    tenant_id: str
    dashboard_id: str
    component_type: str = "metric_card"
    title: str = ""
    description: str = ""
    data_source: str = ""
    config: dict = Field(default_factory=dict)
    layout_config: dict = Field(default_factory=dict)
    style: dict = Field(default_factory=dict)
    refresh_interval: int = 300
    sort_order: int = 0
    status: str = "active"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class DashboardShareCreateRequest(BaseModel):
    dashboard_id: str = Field(..., min_length=1)
    share_type: str = Field(default="user", pattern=r"^(user|role|org)$")
    target_id: str = Field(..., min_length=1)
    permission: str = Field(default="view", pattern=r"^(view|edit|admin)$")


class DashboardShareResponse(BaseModel):
    id: str
    tenant_id: str
    dashboard_id: str
    share_type: str = "user"
    target_id: str = ""
    permission: str = "view"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class DashboardSearchRequest(BaseModel):
    keyword: str = Field(default="", description="关键词搜索 (名称/编码)")
    owner_id: str = Field(default="", description="所有者ID筛选")
    is_public: bool | None = Field(default=None, description="是否公开筛选")
    status: str = Field(default="", description="状态筛选")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class TodoItemCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    todo_type: str = Field(default="manual", max_length=50)
    priority: str = Field(default="medium", pattern=r"^(critical|high|medium|low)$")
    priority_score: int = Field(default=50, ge=0, le=100)
    due_date: datetime | None = None
    related_type: str = Field(default="", max_length=50)
    related_id: str = Field(default="", max_length=50)
    assigned_to: str = Field(default="", max_length=50)
    description: str = Field(default="", max_length=1000)


class TodoItemUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    priority: str | None = Field(default=None, pattern=r"^(critical|high|medium|low)$")
    priority_score: int | None = Field(default=None, ge=0, le=100)
    due_date: datetime | None = None
    status: str | None = Field(default=None, pattern=r"^(pending|in_progress|completed|dismissed|cancelled)$")


class DashboardStatisticsResponse(BaseModel):
    total_dashboards: int = 0
    active_dashboards: int = 0
    total_components: int = 0
    total_shares: int = 0
    total_todos: int = 0
    pending_todos: int = 0
    completed_todos: int = 0
    kpi_metrics_count: int = 0
    dashboards_by_owner: dict[str, int] = {}
    components_by_type: dict[str, int] = {}
