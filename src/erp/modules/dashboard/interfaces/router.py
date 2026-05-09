from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from erp.modules.dashboard.application.dtos import (
    DashboardSearchRequest,
    TodoItemCreateRequest,
)
from erp.modules.dashboard.application.services import (
    BusinessAggregationService,
    DashboardComponentService,
    DashboardQueryService,
    DashboardService,
    DashboardShareService,
    KpiMetricService,
    TodoItemService,
)
from erp.modules.dashboard.interfaces.deps import (
    get_business_service,
    get_component_service,
    get_dashboard_query_service,
    get_dashboard_service,
    get_kpi_service,
    get_share_service,
    get_todo_service,
)
from erp.shared.context import actor_id_var, tenant_id_var, trace_id_var
from erp.shared.exceptions import NotFoundException, Result

router = APIRouter(prefix="/dashboard/v1", tags=["Dashboard - 工作台域"])


class DashboardCreateRequest(BaseModel):
    name: str
    code: str
    description: str = ""
    layout_json: str = "{}"
    is_default: bool = False
    is_public: bool = True
    owner_id: str = ""
    sort_order: int = 0


class DashboardLayoutRequest(BaseModel):
    layout_json: str


class ComponentCreateRequest(BaseModel):
    dashboard_id: str
    component_type: str = "metric_card"
    title: str = ""
    description: str = ""
    data_source: str = ""
    config_json: str = "{}"
    layout_config_json: str = "{}"
    style_json: str = "{}"
    refresh_interval: int = 300
    sort_order: int = 0


class ComponentConfigRequest(BaseModel):
    config_json: str = ""
    layout_config_json: str = ""


class ShareCreateRequest(BaseModel):
    dashboard_id: str
    share_type: str = "user"
    target_id: str = ""
    permission: str = "view"


@router.post("/dashboards", response_model=None)
async def create_dashboard(req: DashboardCreateRequest,
                           svc: DashboardService = Depends(get_dashboard_service)):
    dashboard = await svc.create(tenant_id_var.get(""), **req.model_dump())
    return Result.ok(data={"id": dashboard.id, "name": dashboard.name, "code": dashboard.code},
                     trace_id=trace_id_var.get(""))


@router.get("/dashboards", response_model=None)
async def list_dashboards(svc: DashboardService = Depends(get_dashboard_service)):
    dashboards = await svc.list_by_tenant(tenant_id_var.get(""))
    items = [{"id": d.id, "name": d.name, "code": d.code, "is_default": d.is_default,
              "is_public": d.is_public, "owner_id": d.owner_id} for d in dashboards]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.get("/dashboards/{dashboard_id}", response_model=None)
async def get_dashboard(dashboard_id: str,
                        svc: DashboardService = Depends(get_dashboard_service),
                        comp_svc: DashboardComponentService = Depends(get_component_service)):
    dashboard = await svc.get_or_raise(dashboard_id, tenant_id_var.get(""))
    components = await comp_svc.list_by_dashboard(dashboard_id, tenant_id_var.get(""))
    return Result.ok(data={
        "id": dashboard.id, "name": dashboard.name, "code": dashboard.code,
        "layout_json": dashboard.layout_json, "is_default": dashboard.is_default,
        "components": [{"id": c.id, "component_type": c.component_type, "title": c.title,
                        "config_json": c.config_json, "layout_config_json": c.layout_config_json,
                        "sort_order": c.sort_order} for c in components],
    }, trace_id=trace_id_var.get(""))


@router.put("/dashboards/{dashboard_id}/layout", response_model=None)
async def update_dashboard_layout(dashboard_id: str, req: DashboardLayoutRequest,
                                   svc: DashboardService = Depends(get_dashboard_service)):
    dashboard = await svc.update_layout(dashboard_id, tenant_id_var.get(""), req.layout_json)
    return Result.ok(data={"id": dashboard.id}, trace_id=trace_id_var.get(""))


@router.delete("/dashboards/{dashboard_id}", response_model=None)
async def delete_dashboard(dashboard_id: str,
                           svc: DashboardService = Depends(get_dashboard_service)):
    dashboard = await svc.delete(dashboard_id, tenant_id_var.get(""))
    return Result.ok(data={"id": dashboard.id, "status": "deleted"}, trace_id=trace_id_var.get(""))


@router.post("/components", response_model=None)
async def create_component(req: ComponentCreateRequest,
                           svc: DashboardComponentService = Depends(get_component_service)):
    component = await svc.create(tenant_id_var.get(""), **req.model_dump())
    return Result.ok(data={"id": component.id, "component_type": component.component_type, "title": component.title},
                     trace_id=trace_id_var.get(""))


@router.put("/components/{component_id}/config", response_model=None)
async def update_component_config(component_id: str, req: ComponentConfigRequest,
                                   svc: DashboardComponentService = Depends(get_component_service)):
    component = await svc.update_config(component_id, tenant_id_var.get(""),
                                         config_json=req.config_json,
                                         layout_config_json=req.layout_config_json)
    return Result.ok(data={"id": component.id}, trace_id=trace_id_var.get(""))


@router.delete("/components/{component_id}", response_model=None)
async def delete_component(component_id: str,
                           svc: DashboardComponentService = Depends(get_component_service)):
    component = await svc.delete(component_id, tenant_id_var.get(""))
    return Result.ok(data={"id": component.id, "status": "deleted"}, trace_id=trace_id_var.get(""))


@router.post("/shares", response_model=None)
async def share_dashboard(req: ShareCreateRequest,
                          svc: DashboardShareService = Depends(get_share_service)):
    share = await svc.share(tenant_id_var.get(""), dashboard_id=req.dashboard_id,
                             share_type=req.share_type, target_id=req.target_id, permission=req.permission)
    return Result.ok(data={"id": share.id, "permission": share.permission}, trace_id=trace_id_var.get(""))


@router.get("/dashboards/{dashboard_id}/shares", response_model=None)
async def list_shares(dashboard_id: str,
                      svc: DashboardShareService = Depends(get_share_service)):
    shares = await svc.list_by_dashboard(dashboard_id, tenant_id_var.get(""))
    items = [{"id": s.id, "share_type": s.share_type, "target_id": s.target_id, "permission": s.permission}
             for s in shares]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.delete("/shares/{share_id}", response_model=None)
async def revoke_share(share_id: str,
                       svc: DashboardShareService = Depends(get_share_service)):
    share = await svc.revoke(share_id, tenant_id_var.get(""))
    return Result.ok(data={"id": share.id, "revoked": True}, trace_id=trace_id_var.get(""))


@router.get("/kpi-overview", response_model=None)
async def get_kpi_overview(svc: BusinessAggregationService = Depends(get_business_service)):
    result = await svc.get_kpi_overview(tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/todo-items", response_model=None)
async def get_todo_items(svc: BusinessAggregationService = Depends(get_business_service)):
    result = await svc.get_todo_items(tenant_id_var.get(""), user_id=actor_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/alerts", response_model=None)
async def get_alerts(svc: BusinessAggregationService = Depends(get_business_service)):
    result = await svc.get_alerts(tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/trend", response_model=None)
async def get_trend_data(metric_type: str = Query(default="orders"),
                         days: int = Query(default=30, ge=1, le=365),
                         svc: BusinessAggregationService = Depends(get_business_service)):
    result = await svc.get_trend_data(tenant_id_var.get(""), metric_type=metric_type, days=days)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


# ──── 统计与搜索端点 ────


@router.get("/statistics", response_model=None, summary="Dashboard运营统计概览")
async def get_dashboard_statistics(
    svc: DashboardQueryService = Depends(get_dashboard_query_service),
):
    """获取Dashboard运营统计概览: 仪表盘/组件/待办等核心指标"""
    result = await svc.get_statistics(tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/dashboards/search", response_model=None, summary="搜索仪表盘")
async def search_dashboards(
    req: DashboardSearchRequest,
    svc: DashboardQueryService = Depends(get_dashboard_query_service),
):
    """多维度搜索仪表盘: 关键词/所有者/公开状态"""
    items, total = await svc.search_dashboards(
        tenant_id_var.get(""), keyword=req.keyword, owner_id=req.owner_id,
        is_public=req.is_public, status=req.status,
        page=req.page, page_size=req.page_size,
    )
    data = [{"id": d.id, "name": d.name, "code": d.code, "is_default": d.is_default,
             "is_public": d.is_public, "owner_id": d.owner_id, "status": d.status} for d in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


# ──── 待办事项管理端点 ────


@router.post("/todos", response_model=None, summary="创建待办事项")
async def create_todo(
    req: TodoItemCreateRequest,
    svc: TodoItemService = Depends(get_todo_service),
):
    """创建待办事项"""
    todo = await svc.create(tenant_id_var.get(""), title=req.title,
                             todo_type=req.todo_type, priority=req.priority,
                             priority_score=req.priority_score, due_date=req.due_date,
                             related_type=req.related_type, related_id=req.related_id,
                             assigned_to=req.assigned_to, description=req.description)
    return Result.ok(data={"id": todo.id, "title": todo.title, "status": todo.status},
                     trace_id=trace_id_var.get(""))


@router.get("/todos", response_model=None, summary="待办事项列表")
async def list_todos(
    status: str = Query(default=""),
    todo_type: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    svc: TodoItemService = Depends(get_todo_service),
):
    """获取待办事项列表"""
    items = await svc.list_by_user(tenant_id_var.get(""), user_id=actor_id_var.get(""),
                                    status=status, todo_type=todo_type, limit=limit)
    data = [{"id": t.id, "title": t.title, "todo_type": t.todo_type,
             "priority": t.priority, "status": t.status,
             "due_date": t.due_date.isoformat() if t.due_date else None,
             "assigned_to": t.assigned_to} for t in items]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/todos/{todo_id}/complete", response_model=None, summary="完成待办")
async def complete_todo(
    todo_id: str,
    svc: TodoItemService = Depends(get_todo_service),
):
    """标记待办事项为已完成"""
    todo = await svc.complete(todo_id, tenant_id_var.get(""), completed_by=actor_id_var.get(""))
    return Result.ok(data={"id": todo.id, "status": todo.status}, trace_id=trace_id_var.get(""))


@router.post("/todos/{todo_id}/dismiss", response_model=None, summary="忽略待办")
async def dismiss_todo(
    todo_id: str,
    svc: TodoItemService = Depends(get_todo_service),
):
    """忽略待办事项"""
    todo = await svc.dismiss(todo_id, tenant_id_var.get(""))
    return Result.ok(data={"id": todo.id, "status": todo.status}, trace_id=trace_id_var.get(""))


# ──── KPI指标管理端点 ────


@router.get("/kpi-metrics", response_model=None, summary="KPI指标列表")
async def list_kpi_metrics(
    metric_group: str = Query(default=""),
    svc: KpiMetricService = Depends(get_kpi_service),
):
    """获取KPI指标列表"""
    items = await svc.list_by_group(tenant_id_var.get(""), metric_group=metric_group)
    data = [{"id": m.id, "metric_code": m.metric_code, "metric_name": m.metric_name,
             "current_value": m.current_value, "target_value": m.target_value,
             "metric_group": m.metric_group, "unit": m.unit,
             "status": m.status} for m in items]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/kpi-metrics/refresh", response_model=None, summary="刷新KPI指标")
async def refresh_kpi_metrics(
    svc: KpiMetricService = Depends(get_kpi_service),
):
    """刷新所有KPI指标数据"""
    count = await svc.refresh_all(tenant_id_var.get(""))
    return Result.ok(data={"refreshed_count": count}, trace_id=trace_id_var.get(""))


# ──── Widget数据端点 ────


@router.get("/widget-data", response_model=None, summary="获取Widget数据")
async def get_widget_data(
    component_type: str = Query(default="metric_card"),
    svc: BusinessAggregationService = Depends(get_business_service),
):
    """根据组件类型获取Widget数据"""
    result = await svc.get_widget_data(tenant_id_var.get(""), component_type=component_type)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
