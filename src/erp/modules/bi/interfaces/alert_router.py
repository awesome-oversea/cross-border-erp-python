"""
BI 告警路由 - 业务告警管理 API 端点

路径规范: /api/bi/v1/alerts/{resource}
依赖注入: 通过 domain 服务直接操作
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from erp.modules.bi.domain.metric_alert_models import BusinessAlertService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

router = APIRouter(prefix="/bi/v1/alerts", tags=["BI-Alerts"])


@router.post("/rules", response_model=None)
async def create_alert_rule(
    alert_name: str, alert_code: str, alert_type: str, category: str,
    metric_code: str, threshold_value: float, threshold_operator: str = "lt",
    severity: str = "warning", description: str = "",
    session=Depends(get_db_session),
):
    svc = BusinessAlertService(session)
    a = await svc.create_alert_rule(
        tenant_id=tenant_id_var.get(""), alert_name=alert_name,
        alert_code=alert_code, alert_type=alert_type,
        category=category, metric_code=metric_code,
        threshold_value=threshold_value, threshold_operator=threshold_operator,
        severity=severity, description=description,
    )
    return Result.ok(data={"id": a.id, "alert_name": a.alert_name, "alert_code": a.alert_code},
                     trace_id=trace_id_var.get(""))


@router.get("/rules", response_model=None)
async def list_alert_rules(category: str = Query(default=""),
                            alert_type: str = Query(default=""),
                            session=Depends(get_db_session)):
    svc = BusinessAlertService(session)
    rules = await svc.list_alert_rules(tenant_id_var.get(""), category=category, alert_type=alert_type)
    data = [{
        "id": r.id, "alert_name": r.alert_name, "alert_code": r.alert_code,
        "alert_type": r.alert_type, "category": r.category,
        "metric_code": r.metric_code, "threshold_value": r.threshold_value,
        "threshold_operator": r.threshold_operator, "severity": r.severity,
        "is_active": r.is_active, "trigger_count": r.trigger_count,
        "last_triggered_at": r.last_triggered_at.isoformat() if r.last_triggered_at else None,
    } for r in rules]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/trigger", response_model=None)
async def trigger_alert(
    alert_id: str, current_value: float, title: str,
    message: str = "", suggested_action: str = "",
    session=Depends(get_db_session),
):
    svc = BusinessAlertService(session)
    instance = await svc.trigger_alert(
        tenant_id=tenant_id_var.get(""), alert_id=alert_id,
        current_value=current_value, title=title,
        message=message, suggested_action=suggested_action,
    )
    return Result.ok(
        data={"id": instance.id, "title": instance.title, "severity": instance.severity,
              "current_value": instance.current_value, "threshold_value": instance.threshold_value},
        trace_id=trace_id_var.get(""))


@router.get("/instances", response_model=None)
async def list_alert_instances(
    alert_type: str = Query(default=""), status: str = Query(default=""),
    severity: str = Query(default=""),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    session=Depends(get_db_session),
):
    svc = BusinessAlertService(session)
    items, total = await svc.list_alert_instances(
        tenant_id_var.get(""), alert_type=alert_type, status=status,
        severity=severity, page=page, page_size=page_size,
    )
    data = [{
        "id": i.id, "alert_id": i.alert_id, "alert_type": i.alert_type,
        "severity": i.severity, "title": i.title, "message": i.message,
        "current_value": i.current_value, "threshold_value": i.threshold_value,
        "metric_code": i.metric_code, "suggested_action": i.suggested_action,
        "status": i.status,
        "acknowledged_by": i.acknowledged_by,
        "resolved_by": i.resolved_by,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    } for i in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/instances/{instance_id}/acknowledge", response_model=None)
async def acknowledge_alert(instance_id: str, session=Depends(get_db_session)):
    svc = BusinessAlertService(session)
    instance = await svc.acknowledge_alert(instance_id, tenant_id_var.get(""))
    return Result.ok(data={"id": instance.id, "status": instance.status}, trace_id=trace_id_var.get(""))


@router.post("/instances/{instance_id}/resolve", response_model=None)
async def resolve_alert(instance_id: str, resolution_note: str = "", session=Depends(get_db_session)):
    svc = BusinessAlertService(session)
    instance = await svc.resolve_alert(instance_id, tenant_id_var.get(""), resolution_note=resolution_note)
    return Result.ok(data={"id": instance.id, "status": instance.status}, trace_id=trace_id_var.get(""))
