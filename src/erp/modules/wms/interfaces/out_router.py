"""
WMS 外部交互 API 路由

本模块定义仓储管理系统与外部系统交互的 REST API 端点。
路径规范: /wms/out/v1/{resource}

端点:
  - 库存查询:   GET  /inventory/query        (供 OMS/TMS 系统查询库存)
  - 库存预留:   POST /inventory/reserve       (供 OMS 系统预留库存)
  - 库存释放:   POST /inventory/release       (供 OMS 系统释放预留)
  - 出库通知:   POST /outbound-notify         (供 OMS 系统通知出库)
  - 入库通知:   POST /inbound-notify          (供 SCM 系统通知入库)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.wms.application.services import InventoryService, InboundService, OutboundService
from erp.modules.wms.interfaces.deps import get_inventory_service, get_inbound_service, get_outbound_service
from erp.shared.context import get_current_tenant_id, trace_id_var
from erp.shared.exceptions import Result

router = APIRouter(prefix="/wms/out/v1", tags=["WMS-Outbound"])


class InventoryReserveRequest(BaseModel):
    sku_id: str = Field(..., min_length=1, description="SKU ID")
    warehouse_id: str = Field(..., min_length=1, description="仓库ID")
    quantity: int = Field(..., ge=1, description="预留数量")
    order_id: str = Field(default="", description="关联订单ID")
    source: str = Field(default="oms", description="来源系统")


class InventoryReleaseRequest(BaseModel):
    sku_id: str = Field(..., min_length=1, description="SKU ID")
    warehouse_id: str = Field(..., min_length=1, description="仓库ID")
    quantity: int = Field(..., ge=1, description="释放数量")
    order_id: str = Field(default="", description="关联订单ID")
    source: str = Field(default="oms", description="来源系统")


class OutboundNotifyRequest(BaseModel):
    order_id: str = Field(..., min_length=1, description="关联订单ID")
    warehouse_id: str = Field(..., min_length=1, description="仓库ID")
    items: list[dict] = Field(default_factory=list, description="出库明细")
    shipping_method: str = Field(default="", description="物流方式")
    source: str = Field(default="oms", description="来源系统")


class InboundNotifyRequest(BaseModel):
    po_id: str = Field(default="", description="关联采购订单ID")
    warehouse_id: str = Field(..., min_length=1, description="仓库ID")
    items: list[dict] = Field(default_factory=list, description="入库明细")
    source: str = Field(default="scm", description="来源系统")


@router.get("/inventory/query", response_model=None, summary="查询库存(外部)")
async def query_inventory(
    sku_id: str = Query(default="", description="SKU ID"),
    warehouse_id: str = Query(default="", description="仓库ID"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: InventoryService = Depends(get_inventory_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """供外部系统 (OMS/TMS) 查询库存"""
    items, total = await svc.list_all(tenant_id, warehouse_id=warehouse_id, sku_id=sku_id, page=page, page_size=page_size)
    data = [{"sku_id": i.sku_id, "warehouse_id": i.warehouse_id,
             "qty_on_hand": i.qty_on_hand, "qty_available": i.qty_available,
             "qty_reserved": i.qty_reserved} for i in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/inventory/reserve", response_model=None, summary="预留库存(外部)")
async def reserve_inventory(
    req: InventoryReserveRequest,
    svc: InventoryService = Depends(get_inventory_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """供外部系统 (OMS) 预留库存"""
    result = await svc.reserve(tenant_id, sku_id=req.sku_id, warehouse_id=req.warehouse_id,
                                quantity=req.quantity, order_id=req.order_id)
    return Result.ok(data={"reserved": result}, trace_id=trace_id_var.get(""))


@router.post("/inventory/release", response_model=None, summary="释放预留(外部)")
async def release_inventory(
    req: InventoryReleaseRequest,
    svc: InventoryService = Depends(get_inventory_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """供外部系统 (OMS) 释放预留库存"""
    result = await svc.unreserve(tenant_id, sku_id=req.sku_id, warehouse_id=req.warehouse_id,
                                  quantity=req.quantity, order_id=req.order_id)
    return Result.ok(data={"released": result}, trace_id=trace_id_var.get(""))


@router.post("/outbound-notify", response_model=None, summary="出库通知(外部)")
async def outbound_notify(
    req: OutboundNotifyRequest,
    svc: OutboundService = Depends(get_outbound_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """供外部系统 (OMS) 通知出库"""
    return Result.ok(data={"order_id": req.order_id, "status": "notified",
                           "warehouse_id": req.warehouse_id}, trace_id=trace_id_var.get(""))


@router.post("/inbound-notify", response_model=None, summary="入库通知(外部)")
async def inbound_notify(
    req: InboundNotifyRequest,
    svc: InboundService = Depends(get_inbound_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """供外部系统 (SCM) 通知入库"""
    return Result.ok(data={"po_id": req.po_id, "status": "notified",
                           "warehouse_id": req.warehouse_id}, trace_id=trace_id_var.get(""))
