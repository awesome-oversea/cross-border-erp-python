"""
BI 模块内部路由 - 商业智能域 API 端点

路径规范: /api/bi/v1/{resource} (内部域子系统, main.py 注册 prefix=/api)
依赖注入: 通过 deps.py 工厂函数获取已注入仓储的服务实例
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from erp.modules.bi.application.dtos import (
    BiDashboardWidgetCreateRequest,
    BiMetricCreateRequest,
    BiMetricSearchRequest,
    BiMetricValueCreateRequest,
    BiMetricValueSearchRequest,
    BiReportCreateRequest,
    BiReportSearchRequest,
)
from erp.modules.bi.application.services import (
    BIQueryService,
    BiDashboardWidgetService,
    BiMetricService,
    BiMetricValueService,
    BiReportService,
)
from erp.modules.bi.interfaces.deps import (
    get_bi_query_service,
    get_metric_service,
    get_metric_value_service,
    get_report_service,
    get_widget_service,
)
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import NotFoundException, Result

router = APIRouter(prefix="/bi/v1", tags=["BI - 商业智能"])


# ──── 指标管理 ────


@router.post("/metrics", response_model=None)
async def create_metric(req: BiMetricCreateRequest, svc: BiMetricService = Depends(get_metric_service)):
    metric = await svc.create(tenant_id_var.get(""), **req.model_dump())
    return Result.ok(data={"id": metric.id, "metric_code": metric.metric_code}, trace_id=trace_id_var.get(""))


@router.get("/metrics", response_model=None)
async def list_metrics(category: str | None = None, svc: BiMetricService = Depends(get_metric_service)):
    metrics = await svc.list_by_tenant(tenant_id_var.get(""), category=category)
    items = [{"id": m.id, "metric_code": m.metric_code, "metric_name": m.metric_name,
              "metric_category": m.metric_category, "metric_unit": m.metric_unit} for m in metrics]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.get("/metrics/{metric_id}", response_model=None)
async def get_metric(metric_id: str, svc: BiMetricService = Depends(get_metric_service)):
    metric = await svc.get_or_raise(metric_id, tenant_id_var.get(""))
    return Result.ok(data={"id": metric.id, "metric_code": metric.metric_code, "metric_name": metric.metric_name,
                           "metric_category": metric.metric_category, "metric_unit": metric.metric_unit,
                           "description": metric.description}, trace_id=trace_id_var.get(""))


# ──── 指标值 ────


@router.post("/metric-values", response_model=None)
async def record_metric_value(req: BiMetricValueCreateRequest, svc: BiMetricValueService = Depends(get_metric_value_service)):
    val = await svc.record(
        tenant_id_var.get(""), metric_id=req.metric_id, metric_code=req.metric_code,
        period_type=req.period_type, period_date=req.period_date,
        numeric_value=req.numeric_value, text_value=req.text_value,
        store_id=req.store_id, platform=req.platform,
    )
    return Result.ok(data={"id": val.id, "numeric_value": val.numeric_value}, trace_id=trace_id_var.get(""))


@router.get("/metric-values/{metric_code}", response_model=None)
async def query_metric_values(metric_code: str, period_type: str = "daily",
                               store_id: str | None = None, limit: int = Query(30, ge=1, le=365),
                               svc: BiMetricValueService = Depends(get_metric_value_service)):
    values = await svc.query(tenant_id_var.get(""), metric_code=metric_code,
                              period_type=period_type, store_id=store_id, limit=limit)
    items = [{"period_date": v.period_date.isoformat() if v.period_date else "",
              "numeric_value": v.numeric_value, "store_id": v.store_id} for v in values]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.get("/metric-values/{metric_code}/latest", response_model=None)
async def get_latest_metric_value(metric_code: str, store_id: str = Query(default=""),
                                   svc: BiMetricValueService = Depends(get_metric_value_service)):
    values = await svc.query(tenant_id_var.get(""), metric_code=metric_code, period_type="daily",
                              store_id=store_id or None, limit=1)
    if values:
        v = values[0]
        return Result.ok(data={"metric_code": metric_code, "numeric_value": v.numeric_value,
                               "period_date": v.period_date.isoformat() if v.period_date else "",
                               "store_id": v.store_id}, trace_id=trace_id_var.get(""))
    return Result.ok(data={"metric_code": metric_code, "numeric_value": 0.0}, trace_id=trace_id_var.get(""))


# ──── 报表 ────


@router.post("/reports", response_model=None)
async def create_report(req: BiReportCreateRequest, svc: BiReportService = Depends(get_report_service)):
    report = await svc.create(tenant_id_var.get(""), **req.model_dump())
    return Result.ok(data={"id": report.id, "report_code": report.report_code}, trace_id=trace_id_var.get(""))


@router.get("/reports", response_model=None)
async def list_reports(category: str | None = None, svc: BiReportService = Depends(get_report_service)):
    reports = await svc.list_by_tenant(tenant_id_var.get(""), category=category)
    items = [{"id": r.id, "report_code": r.report_code, "name": r.name,
              "report_type": r.report_type, "category": r.category} for r in reports]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.get("/reports/{report_id}", response_model=None)
async def get_report(report_id: str, svc: BiReportService = Depends(get_report_service)):
    report = await svc.get_or_raise(report_id, tenant_id_var.get(""))
    return Result.ok(data={"id": report.id, "report_code": report.report_code, "name": report.name,
                           "report_type": report.report_type, "category": report.category,
                           "description": report.description}, trace_id=trace_id_var.get(""))


@router.get("/reports/{report_id}/data", response_model=None)
async def get_report_data(report_id: str, svc: BiReportService = Depends(get_report_service)):
    report = await svc.get_or_raise(report_id, tenant_id_var.get(""))
    return Result.ok(data={"id": report.id, "report_code": report.report_code, "name": report.name,
                           "report_type": report.report_type, "data": []}, trace_id=trace_id_var.get(""))


@router.delete("/reports/{report_id}", response_model=None)
async def delete_report(report_id: str, svc: BiReportService = Depends(get_report_service)):
    report = await svc.get_or_raise(report_id, tenant_id_var.get(""))
    report.is_active = False
    return Result.ok(data={"id": report_id, "is_active": False}, trace_id=trace_id_var.get(""))


# ──── 仪表盘 ────


@router.post("/widgets", response_model=None)
async def create_widget(req: BiDashboardWidgetCreateRequest, svc: BiDashboardWidgetService = Depends(get_widget_service)):
    widget = await svc.create(tenant_id_var.get(""), **req.model_dump())
    return Result.ok(data={"id": widget.id, "widget_type": widget.widget_type, "title": widget.title},
                     trace_id=trace_id_var.get(""))


@router.get("/dashboards", response_model=None)
async def list_dashboards(svc: BiReportService = Depends(get_report_service)):
    reports = await svc.list_by_tenant(tenant_id_var.get(""))
    items = [{"id": r.id, "report_code": r.report_code, "name": r.name,
              "report_type": r.report_type, "category": r.category} for r in reports]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.get("/dashboards/{dashboard_id}", response_model=None)
async def get_dashboard_data(dashboard_id: str, svc: BiDashboardWidgetService = Depends(get_widget_service)):
    widgets = await svc.list_by_dashboard(dashboard_id)
    items = [{"id": w.id, "widget_type": w.widget_type, "title": w.title,
              "metric_code": w.metric_code, "sort_order": w.sort_order} for w in widgets]
    return Result.ok(data={"dashboard_id": dashboard_id, "widgets": items}, trace_id=trace_id_var.get(""))


@router.get("/dashboards/{dashboard_id}/widgets", response_model=None)
async def list_widgets(dashboard_id: str, svc: BiDashboardWidgetService = Depends(get_widget_service)):
    widgets = await svc.list_by_dashboard(dashboard_id)
    items = [{"id": w.id, "widget_type": w.widget_type, "title": w.title,
              "metric_code": w.metric_code, "sort_order": w.sort_order} for w in widgets]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


# ──── KPI ────


@router.get("/kpis", response_model=None)
async def list_kpis(category: str | None = None, svc: BiMetricService = Depends(get_metric_service)):
    metrics = await svc.list_by_tenant(tenant_id_var.get(""), category=category)
    items = [{"id": m.id, "metric_code": m.metric_code, "metric_name": m.metric_name,
              "metric_category": m.metric_category, "metric_unit": m.metric_unit,
              "target_value": 0.0, "current_value": 0.0} for m in metrics]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


# ──── 统计与搜索端点 ────


@router.get("/statistics", response_model=None, summary="BI运营统计概览")
async def get_bi_statistics(
    svc: BIQueryService = Depends(get_bi_query_service),
):
    """获取BI运营统计概览: 指标数/报表数/Widget数等核心指标"""
    result = await svc.get_statistics(tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/metrics/search", response_model=None, summary="搜索指标")
async def search_metrics(
    req: BiMetricSearchRequest,
    svc: BIQueryService = Depends(get_bi_query_service),
):
    """多维度搜索指标: 关键词/分类/状态"""
    items, total = await svc.search_metrics(
        tenant_id_var.get(""), keyword=req.keyword, metric_category=req.metric_category,
        status=req.status, page=req.page, page_size=req.page_size,
    )
    data = [{"id": m.id, "metric_code": m.metric_code, "metric_name": m.metric_name,
             "metric_category": m.metric_category, "metric_unit": m.metric_unit,
             "status": m.status} for m in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


@router.post("/metric-values/search", response_model=None, summary="搜索指标值")
async def search_metric_values(
    req: BiMetricValueSearchRequest,
    svc: BIQueryService = Depends(get_bi_query_service),
):
    """多维度搜索指标值: 指标编码/周期类型/店铺/平台/日期范围"""
    items, total = await svc.search_metric_values(
        tenant_id_var.get(""), metric_code=req.metric_code, period_type=req.period_type,
        store_id=req.store_id, platform=req.platform,
        start_date=req.start_date, end_date=req.end_date,
        page=req.page, page_size=req.page_size,
    )
    data = [{"id": v.id, "metric_code": v.metric_code, "period_type": v.period_type,
             "period_date": v.period_date.isoformat() if v.period_date else "",
             "numeric_value": v.numeric_value, "store_id": v.store_id} for v in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


@router.post("/reports/search", response_model=None, summary="搜索报表")
async def search_reports(
    req: BiReportSearchRequest,
    svc: BIQueryService = Depends(get_bi_query_service),
):
    """多维度搜索报表: 关键词/分类/报表类型"""
    items, total = await svc.search_reports(
        tenant_id_var.get(""), keyword=req.keyword, category=req.category,
        report_type=req.report_type, page=req.page, page_size=req.page_size,
    )
    data = [{"id": r.id, "report_code": r.report_code, "name": r.name,
             "report_type": r.report_type, "category": r.category} for r in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))
