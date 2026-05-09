"""
TMS 外部交互 API 路由

本模块定义运输管理系统与外部系统交互的 REST API 端点。
路径规范: /tms/out/v1/{resource}

端点:
  - 运费计算:   POST /freight-calculate       (供 OMS 系统计算运费)
  - 物流轨迹:   GET  /tracking/{tracking_no}   (供 OMS 系统查询物流轨迹)
  - 发货通知:   POST /shipment-notify          (供 WMS 系统通知发货)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.tms.application.services import ShipmentService, TrackingService
from erp.modules.tms.interfaces.deps import get_shipment_service, get_tracking_service
from erp.shared.context import get_current_tenant_id, trace_id_var
from erp.shared.exceptions import Result

router = APIRouter(prefix="/tms/out/v1", tags=["TMS-Outbound"])


class FreightCalculateRequest(BaseModel):
    origin: str = Field(default="", description="始发地")
    destination: str = Field(default="", description="目的地")
    weight: float = Field(default=0.0, ge=0, description="重量(kg)")
    shipping_method_id: str = Field(default="", description="物流方式ID")
    items: list[dict] = Field(default_factory=list, description="商品明细")


class ShipmentNotifyRequest(BaseModel):
    order_id: str = Field(..., min_length=1, description="关联订单ID")
    warehouse_id: str = Field(default="", description="仓库ID")
    tracking_no: str = Field(default="", description="运单号")
    carrier: str = Field(default="", description="承运商")
    shipping_method: str = Field(default="", description="物流方式")
    source: str = Field(default="wms", description="来源系统")


@router.post("/freight-calculate", response_model=None, summary="运费计算(外部)")
async def calculate_freight(
    req: FreightCalculateRequest,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """供外部系统 (OMS) 计算运费"""
    return Result.ok(data={
        "origin": req.origin, "destination": req.destination,
        "weight": req.weight, "shipping_method_id": req.shipping_method_id,
        "estimated_freight": 0.0, "estimated_days": 0,
        "currency": "CNY",
    }, trace_id=trace_id_var.get(""))


@router.get("/tracking/{tracking_no}", response_model=None, summary="物流轨迹查询(外部)")
async def query_tracking(
    tracking_no: str,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """供外部系统 (OMS) 查询物流轨迹"""
    return Result.ok(data={"tracking_no": tracking_no, "status": "unknown", "events": []},
                     trace_id=trace_id_var.get(""))


@router.post("/shipment-notify", response_model=None, summary="发货通知(外部)")
async def shipment_notify(
    req: ShipmentNotifyRequest,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """供外部系统 (WMS) 通知发货"""
    return Result.ok(data={
        "order_id": req.order_id, "tracking_no": req.tracking_no,
        "carrier": req.carrier, "status": "notified",
    }, trace_id=trace_id_var.get(""))
