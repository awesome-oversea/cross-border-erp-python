"""
WMS 库存快照与预警路由

内部域路径规范: /wms/api/v1/{resource}
涵盖: 库存快照、预警规则、预警记录
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from erp.modules.wms.application.dtos import (
    AlertResolveRequest,
    AlertResponse,
    AlertRuleCreateRequest,
    AlertRuleResponse,
    InventorySnapshotResponse,
)
from erp.modules.wms.domain.inventory_alert_models import (
    InventoryAlertService,
    InventorySnapshotService,
)
from erp.modules.wms.interfaces.deps import (
    get_inventory_alert_service,
    get_inventory_snapshot_service,
)
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import Result

router = APIRouter(prefix="/wms/v1", tags=["WMS-InventoryAlert"])


@router.post("/inventory-snapshots", response_model=None)
async def take_snapshot(
    snapshot_date: str = Query(default=""),
    svc: InventorySnapshotService = Depends(get_inventory_snapshot_service),
):
    count = await svc.take_snapshot(tenant_id_var.get(""), snapshot_date or None)
    return Result.ok(
        data={"snapshot_date": snapshot_date, "items_captured": count},
        trace_id=trace_id_var.get(""),
    )


@router.get("/inventory-snapshots/{snapshot_date}", response_model=None)
async def get_snapshot(
    snapshot_date: str,
    warehouse_id: str = Query(default=""),
    sku_id: str = Query(default=""),
    svc: InventorySnapshotService = Depends(get_inventory_snapshot_service),
):
    snapshots = await svc.get_snapshot(
        tenant_id_var.get(""), snapshot_date,
        warehouse_id=warehouse_id, sku_id=sku_id,
    )
    data = [InventorySnapshotResponse.model_validate(s).model_dump() for s in snapshots]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/alert-rules", response_model=None)
async def create_alert_rule(
    req: AlertRuleCreateRequest,
    svc: InventoryAlertService = Depends(get_inventory_alert_service),
):
    rule = await svc.create_alert_rule(
        tenant_id=tenant_id_var.get(""), rule_name=req.rule_name,
        alert_type=req.alert_type, severity=req.severity,
        condition=req.condition, warehouse_scope=req.warehouse_scope,
        sku_scope=req.sku_scope, category_scope=req.category_scope,
        cooldown_hours=req.cooldown_hours, notify_channels=req.notify_channels,
    )
    return Result.ok(
        data=AlertRuleResponse.model_validate(rule).model_dump(),
        trace_id=trace_id_var.get(""),
    )


@router.post("/alert-rules/evaluate", response_model=None)
async def evaluate_alerts(
    svc: InventoryAlertService = Depends(get_inventory_alert_service),
):
    alerts = await svc.evaluate_alerts(tenant_id_var.get(""))
    return Result.ok(
        data={"alerts_generated": len(alerts), "alert_ids": [a.id for a in alerts]},
        trace_id=trace_id_var.get(""),
    )


@router.post("/alert-rules/init-defaults", response_model=None)
async def init_default_rules(
    svc: InventoryAlertService = Depends(get_inventory_alert_service),
):
    rules = await svc.init_default_rules(tenant_id_var.get(""))
    return Result.ok(
        data={"rules_created": len(rules)},
        trace_id=trace_id_var.get(""),
    )


@router.get("/alerts", response_model=None)
async def list_alerts(
    alert_type: str = Query(default=""),
    severity: str = Query(default=""),
    status: str = Query(default=""),
    warehouse_id: str = Query(default=""),
    sku_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: InventoryAlertService = Depends(get_inventory_alert_service),
):
    alerts, total = await svc.list_alerts(
        tenant_id_var.get(""), alert_type=alert_type, severity=severity,
        status=status, warehouse_id=warehouse_id, sku_id=sku_id,
        page=page, page_size=page_size,
    )
    data = [AlertResponse.model_validate(a).model_dump() for a in alerts]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/alerts/{alert_id}/acknowledge", response_model=None)
async def acknowledge_alert(
    alert_id: str,
    svc: InventoryAlertService = Depends(get_inventory_alert_service),
):
    alert = await svc.acknowledge_alert(alert_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": alert.id, "status": alert.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/alerts/{alert_id}/resolve", response_model=None)
async def resolve_alert(
    alert_id: str,
    req: AlertResolveRequest,
    svc: InventoryAlertService = Depends(get_inventory_alert_service),
):
    alert = await svc.resolve_alert(alert_id, tenant_id_var.get(""), resolution_note=req.resolution_note)
    return Result.ok(
        data={"id": alert.id, "status": alert.status},
        trace_id=trace_id_var.get(""),
    )
