"""
FBA 模块内部路由 - FBA 货件管理域 API 端点

路径规范: /api/fba/v1/{resource} (内部域子系统, main.py 注册 prefix=/api)
依赖注入: 通过 deps.py 工厂函数获取已注入仓储的服务实例
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.fba.application.dtos import (
    FbaFeeSearchRequest,
    FbaInventorySearchRequest,
    FbaReplenishmentSearchRequest,
    FbaShipmentSearchRequest,
)
from erp.modules.fba.application.services import (
    FBAQueryService,
    FbaBoxLabelService,
    FbaFeeService,
    FbaInboundPlanService,
    FbaInventoryService,
    FbaReplenishmentPlanService,
    FbaShipmentService,
)
from erp.modules.fba.interfaces.deps import (
    get_box_label_service,
    get_fee_service,
    get_fba_query_service,
    get_inbound_plan_service,
    get_inventory_service,
    get_replenishment_service,
    get_shipment_service,
)
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/fba/v1", tags=["FBA - FBA货件管理"])


class ShipmentCreateRequest(BaseModel):
    shipment_id: str = Field(..., min_length=1)
    name: str = ""
    platform: str = "amazon"
    store_id: str = ""
    fba_shipment_id: str = ""
    destination_fulfillment_center_id: str = ""
    box_count: int = Field(default=0, ge=0)
    total_units: int = Field(default=0, ge=0)
    total_weight: float = Field(default=0.0, ge=0)
    currency: str = "USD"
    estimated_shipping_cost: float = Field(default=0.0, ge=0)


class ShipmentStatusRequest(BaseModel):
    status: str = Field(..., min_length=1)


class TrackingUpdateRequest(BaseModel):
    tracking_no: str = Field(..., min_length=1)
    carrier: str = Field(..., min_length=1)


class PartialReceiveRequest(BaseModel):
    received_units: int = Field(..., ge=0)
    actual_cost: float = Field(default=0.0, ge=0)


class InventoryCreateRequest(BaseModel):
    sku_id: str = Field(..., min_length=1)
    store_id: str = Field(..., min_length=1)
    platform: str = "amazon"
    fnsku: str = ""
    asin: str = ""
    fulfillment_center_id: str = ""
    qty_available: int = Field(default=0, ge=0)
    qty_fulfillable: int = Field(default=0, ge=0)
    qty_inbound: int = Field(default=0, ge=0)
    qty_reserved: int = Field(default=0, ge=0)


class InventoryUpdateRequest(BaseModel):
    qty_available: int | None = Field(default=None, ge=0)
    qty_fulfillable: int | None = Field(default=None, ge=0)
    qty_inbound: int | None = Field(default=None, ge=0)
    qty_reserved: int | None = Field(default=None, ge=0)
    qty_unfulfillable: int | None = Field(default=None, ge=0)


class InventoryAdjustRequest(BaseModel):
    sku_id: str = Field(..., min_length=1)
    store_id: str = Field(..., min_length=1)
    field: str = Field(..., min_length=1)
    delta: int


class FeeCreateRequest(BaseModel):
    sku_id: str = Field(..., min_length=1)
    store_id: str = Field(..., min_length=1)
    fee_type: str = Field(..., min_length=1)
    fee_amount: float = Field(default=0.0, ge=0)
    currency: str = "USD"
    fee_date: str | None = None
    quantity: int = Field(default=0, ge=0)
    per_unit_fee: float = Field(default=0.0, ge=0)
    platform: str = "amazon"


class BoxLabelCreateRequest(BaseModel):
    shipment_id: str = Field(..., min_length=1)
    box_no: int = Field(..., ge=1)
    sku_id: str = Field(..., min_length=1)
    quantity: int = Field(..., ge=1)
    weight: float = Field(default=0.0, ge=0)
    dimensions: str = ""


class ReplenishmentPlanCreateRequest(BaseModel):
    sku_id: str = Field(..., min_length=1)
    store_id: str = Field(..., min_length=1)
    suggested_qty: int = Field(..., ge=1)
    current_qty: int = Field(default=0, ge=0)
    avg_daily_sales: float = Field(default=0.0, ge=0)
    days_of_supply: int = Field(default=30, ge=1)
    destination_center: str = ""


class ApproveReplenishmentRequest(BaseModel):
    approved_qty: int | None = Field(default=None, ge=0)


class AutoGenerateReplenishmentRequest(BaseModel):
    store_id: str = Field(..., min_length=1)
    avg_daily_sales_map: dict[str, float] = Field(default_factory=dict)
    inventory_map: dict[str, dict] = Field(default_factory=dict)
    lead_time_days: int = Field(default=7, ge=1)
    safety_stock_days: int = Field(default=14, ge=1)
    days_of_supply: int = Field(default=30, ge=1)


# ──── 货件管理 ────


@router.post("/shipments", response_model=None)
async def create_shipment(req: ShipmentCreateRequest, svc: FbaShipmentService = Depends(get_shipment_service)):
    shipment = await svc.create(tenant_id_var.get(""), **req.model_dump())
    return Result.ok(data={"id": shipment.id, "shipment_id": shipment.shipment_id, "status": shipment.status},
                     trace_id=trace_id_var.get(""))


@router.get("/shipments", response_model=None)
async def list_shipments(status: str | None = None, platform: str | None = None,
                         offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                         svc: FbaShipmentService = Depends(get_shipment_service)):
    shipments = await svc.list_by_tenant(tenant_id_var.get(""), status=status, platform=platform,
                                          offset=offset, limit=limit)
    items = [{"id": s.id, "shipment_id": s.shipment_id, "name": s.name, "platform": s.platform,
              "status": s.status, "total_units": s.total_units, "fba_shipment_id": s.fba_shipment_id}
             for s in shipments]
    return Result.ok(data={"items": items, "total": len(items)}, trace_id=trace_id_var.get(""))


@router.get("/shipments/{shipment_pk}", response_model=None)
async def get_shipment(shipment_pk: str, svc: FbaShipmentService = Depends(get_shipment_service)):
    shipment = await svc.get_or_raise(shipment_pk, tenant_id_var.get(""))
    return Result.ok(data={"id": shipment.id, "shipment_id": shipment.shipment_id, "name": shipment.name,
                           "platform": shipment.platform, "status": shipment.status,
                           "total_units": shipment.total_units, "box_count": shipment.box_count,
                           "fba_shipment_id": shipment.fba_shipment_id,
                           "tracking_no": shipment.tracking_no, "carrier": shipment.carrier}, trace_id=trace_id_var.get(""))


@router.put("/shipments/{shipment_pk}/status", response_model=None)
async def update_shipment_status(shipment_pk: str, req: ShipmentStatusRequest,
                                  svc: FbaShipmentService = Depends(get_shipment_service)):
    shipment = await svc.update_status(shipment_pk, tenant_id_var.get(""), req.status)
    return Result.ok(data={"id": shipment.id, "status": shipment.status}, trace_id=trace_id_var.get(""))


@router.put("/shipments/{shipment_pk}/tracking", response_model=None)
async def update_tracking(shipment_pk: str, req: TrackingUpdateRequest,
                          svc: FbaShipmentService = Depends(get_shipment_service)):
    shipment = await svc.update_tracking(shipment_pk, tenant_id_var.get(""), req.tracking_no, req.carrier)
    return Result.ok(data={"id": shipment.id, "tracking_no": shipment.tracking_no, "carrier": shipment.carrier},
                     trace_id=trace_id_var.get(""))


@router.put("/shipments/{shipment_pk}", response_model=None, summary="更新FBA货件")
async def update_shipment(shipment_pk: str, box_count: int = 0, total_units: int = 0,
                          estimated_shipping_cost: float = 0.0,
                          svc: FbaShipmentService = Depends(get_shipment_service)):
    kwargs = {}
    if box_count > 0:
        kwargs["box_count"] = box_count
    if total_units > 0:
        kwargs["total_units"] = total_units
    if estimated_shipping_cost >= 0:
        kwargs["estimated_shipping_cost"] = estimated_shipping_cost
    shipment = await svc.update(shipment_pk, tenant_id_var.get(""), **kwargs)
    return Result.ok(data={"id": shipment.id, "updated": True}, trace_id=trace_id_var.get(""))


@router.post("/shipments/{shipment_pk}/receive-partial", response_model=None)
async def receive_partial(shipment_pk: str, req: PartialReceiveRequest,
                          svc: FbaShipmentService = Depends(get_shipment_service)):
    shipment = await svc.receive_partial(shipment_pk, tenant_id_var.get(),
                                          req.received_units, req.actual_cost)
    return Result.ok(data={"id": shipment.id, "status": shipment.status,
                           "actual_shipping_cost": shipment.actual_shipping_cost},
                     trace_id=trace_id_var.get(""))


@router.delete("/shipments/{shipment_pk}", response_model=None)
async def delete_shipment(shipment_pk: str, svc: FbaShipmentService = Depends(get_shipment_service)):
    deleted = await svc.soft_delete(shipment_pk, tenant_id_var.get(""))
    return Result.ok(data={"id": shipment_pk, "deleted": deleted}, trace_id=trace_id_var.get(""))


# ──── FBA 库存 ────


@router.post("/inventory", response_model=None)
async def create_inventory(req: InventoryCreateRequest, svc: FbaInventoryService = Depends(get_inventory_service)):
    inv = await svc.create(tenant_id_var.get(""), **req.model_dump())
    return Result.ok(data={"id": inv.id, "sku_id": inv.sku_id, "qty_available": inv.qty_available},
                     trace_id=trace_id_var.get(""))


@router.get("/inventory", response_model=None)
async def list_inventory(store_id: str | None = None,
                         offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                         svc: FbaInventoryService = Depends(get_inventory_service)):
    items_list = await svc.list_by_tenant(tenant_id_var.get(""), store_id=store_id,
                                           offset=offset, limit=limit)
    items = [{"id": i.id, "sku_id": i.sku_id, "fnsku": i.fnsku, "asin": i.asin,
              "qty_available": i.qty_available, "qty_fulfillable": i.qty_fulfillable,
              "qty_inbound": i.qty_inbound, "qty_reserved": i.qty_reserved}
             for i in items_list]
    return Result.ok(data={"items": items, "total": len(items)}, trace_id=trace_id_var.get(""))


@router.get("/inventory/{inv_id}", response_model=None)
async def get_inventory(inv_id: str, svc: FbaInventoryService = Depends(get_inventory_service)):
    inv = await svc.get_or_raise(inv_id, tenant_id_var.get(""))
    return Result.ok(data={"id": inv.id, "sku_id": inv.sku_id, "fnsku": inv.fnsku, "asin": inv.asin,
                           "qty_available": inv.qty_available, "qty_fulfillable": inv.qty_fulfillable,
                           "qty_inbound": inv.qty_inbound, "qty_reserved": inv.qty_reserved,
                           "store_id": inv.store_id}, trace_id=trace_id_var.get(""))


@router.put("/inventory/{inv_id}", response_model=None)
async def update_inventory(inv_id: str, req: InventoryUpdateRequest,
                            svc: FbaInventoryService = Depends(get_inventory_service)):
    qty_fields = {k: v for k, v in req.model_dump().items() if v is not None}
    inv = await svc.update_quantities(inv_id, tenant_id_var.get(""), **qty_fields)
    return Result.ok(data={"id": inv.id, "qty_available": inv.qty_available}, trace_id=trace_id_var.get(""))


@router.post("/inventory/adjust", response_model=None)
async def adjust_inventory(req: InventoryAdjustRequest, svc: FbaInventoryService = Depends(get_inventory_service)):
    inv = await svc.adjust_quantity(tenant_id_var.get(""), req.sku_id, req.store_id, req.field, req.delta)
    return Result.ok(data={"id": inv.id, "sku_id": inv.sku_id, req.field: getattr(inv, req.field)},
                     trace_id=trace_id_var.get(""))


@router.get("/inventory/low-stock", response_model=None)
async def get_low_stock(threshold: int = Query(10, ge=0), store_id: str | None = None,
                        svc: FbaInventoryService = Depends(get_inventory_service)):
    items = await svc.get_low_stock_items(tenant_id_var.get(""), threshold=threshold, store_id=store_id)
    data = [{"id": i.id, "sku_id": i.sku_id, "qty_fulfillable": i.qty_fulfillable, "store_id": i.store_id}
            for i in items]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


# ──── 统计与搜索端点 ────


@router.get("/statistics", response_model=None, summary="FBA运营统计概览")
async def get_fba_statistics(
    svc: FBAQueryService = Depends(get_fba_query_service),
):
    """获取FBA运营统计概览: 货件/库存/费用/补货计划等核心指标"""
    result = await svc.get_statistics(tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/shipments/search", response_model=None, summary="搜索FBA货件")
async def search_shipments(
    req: FbaShipmentSearchRequest,
    svc: FBAQueryService = Depends(get_fba_query_service),
):
    """多维度搜索FBA货件: 关键词/平台/状态/店铺/日期范围"""
    items, total = await svc.search_shipments(
        tenant_id_var.get(""), keyword=req.keyword, platform=req.platform,
        status=req.status, store_id=req.store_id,
        start_date=req.start_date, end_date=req.end_date,
        page=req.page, page_size=req.page_size,
    )
    data = [{"id": s.id, "shipment_id": s.shipment_id, "name": s.name,
             "platform": s.platform, "status": s.status, "total_units": s.total_units,
             "fba_shipment_id": s.fba_shipment_id} for s in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


@router.post("/inventory/search", response_model=None, summary="搜索FBA库存")
async def search_inventory(
    req: FbaInventorySearchRequest,
    svc: FBAQueryService = Depends(get_fba_query_service),
):
    """多维度搜索FBA库存: SKU/店铺/FNSKU/ASIN/低库存筛选"""
    items, total = await svc.search_inventory(
        tenant_id_var.get(""), sku_id=req.sku_id, store_id=req.store_id,
        fnsku=req.fnsku, asin=req.asin, condition_type=req.condition_type,
        low_stock_only=req.low_stock_only, low_stock_threshold=req.low_stock_threshold,
        page=req.page, page_size=req.page_size,
    )
    data = [{"id": i.id, "sku_id": i.sku_id, "fnsku": i.fnsku, "asin": i.asin,
             "qty_available": i.qty_available, "qty_fulfillable": i.qty_fulfillable,
             "qty_inbound": i.qty_inbound, "qty_reserved": i.qty_reserved,
             "store_id": i.store_id} for i in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


@router.post("/fees/search", response_model=None, summary="搜索FBA费用")
async def search_fees(
    req: FbaFeeSearchRequest,
    svc: FBAQueryService = Depends(get_fba_query_service),
):
    """多维度搜索FBA费用: 费用类型/SKU/店铺/日期/金额范围"""
    items, total = await svc.search_fees(
        tenant_id_var.get(""), fee_type=req.fee_type, sku_id=req.sku_id,
        store_id=req.store_id, start_date=req.start_date, end_date=req.end_date,
        min_amount=req.min_amount, max_amount=req.max_amount,
        page=req.page, page_size=req.page_size,
    )
    data = [{"id": f.id, "sku_id": f.sku_id, "fee_type": f.fee_type,
             "fee_amount": f.fee_amount, "currency": f.currency,
             "fee_date": f.fee_date.isoformat() if f.fee_date else ""} for f in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


@router.post("/replenishment-plans/search", response_model=None, summary="搜索补货计划")
async def search_replenishment_plans(
    req: FbaReplenishmentSearchRequest,
    svc: FBAQueryService = Depends(get_fba_query_service),
):
    """多维度搜索补货计划: SKU/店铺/状态/优先级"""
    items, total = await svc.search_replenishment_plans(
        tenant_id_var.get(""), sku_id=req.sku_id, store_id=req.store_id,
        status=req.status, priority=req.priority,
        page=req.page, page_size=req.page_size,
    )
    data = [{"id": p.id, "sku_id": p.sku_id, "store_id": p.store_id,
             "suggested_qty": p.suggested_qty, "approved_qty": p.approved_qty,
             "priority": p.priority, "status": p.status,
             "avg_daily_sales": p.avg_daily_sales, "days_of_supply": p.days_of_supply} for p in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


# ──── FBA 费用 ────


@router.post("/fees", response_model=None)
async def create_fee(req: FeeCreateRequest, svc: FbaFeeService = Depends(get_fee_service)):
    kwargs = req.model_dump()
    if req.fee_date:
        kwargs["fee_date"] = datetime.fromisoformat(req.fee_date)
    else:
        kwargs.pop("fee_date", None)
    fee = await svc.create(tenant_id_var.get(""), **kwargs)
    return Result.ok(data={"id": fee.id, "fee_type": fee.fee_type, "fee_amount": fee.fee_amount},
                     trace_id=trace_id_var.get(""))


@router.get("/fees", response_model=None)
async def list_fees(fee_type: str | None = None, sku_id: str | None = None,
                    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                    svc: FbaFeeService = Depends(get_fee_service)):
    fees = await svc.list_by_tenant(tenant_id_var.get(""), fee_type=fee_type, sku_id=sku_id,
                                     offset=offset, limit=limit)
    items = [{"id": f.id, "sku_id": f.sku_id, "fee_type": f.fee_type, "fee_amount": f.fee_amount,
              "currency": f.currency, "fee_date": f.fee_date.isoformat() if f.fee_date else ""}
             for f in fees]
    return Result.ok(data={"items": items, "total": len(items)}, trace_id=trace_id_var.get(""))


@router.get("/fees/summary", response_model=None)
async def fee_summary(sku_id: str = Query(..., min_length=1), store_id: str = "",
                      svc: FbaFeeService = Depends(get_fee_service)):
    totals = await svc.calculate_total_fees(tenant_id_var.get(""), sku_id, store_id)
    return Result.ok(data=totals, trace_id=trace_id_var.get(""))


# ──── 箱标签 ────


@router.post("/box-labels", response_model=None)
async def create_box_label(req: BoxLabelCreateRequest, svc: FbaBoxLabelService = Depends(get_box_label_service)):
    label = await svc.create(tenant_id_var.get(""), req.shipment_id, req.box_no, req.sku_id, req.quantity,
                             weight=req.weight, dimensions=req.dimensions)
    return Result.ok(data={"id": label.id, "shipment_id": label.shipment_id, "box_no": label.box_no,
                           "sku_id": label.sku_id, "quantity": label.quantity,
                           "weight": label.weight, "status": label.status}, trace_id=trace_id_var.get(""))


@router.get("/box-labels", response_model=None)
async def list_box_labels(shipment_id: str = Query(default=""), svc: FbaBoxLabelService = Depends(get_box_label_service)):
    if not shipment_id:
        return Result.ok(data=[], trace_id=trace_id_var.get(""))
    labels = await svc.list_by_shipment(shipment_id, tenant_id_var.get(""))
    data = [{"id": l.id, "box_no": l.box_no, "sku_id": l.sku_id, "quantity": l.quantity,
             "weight": l.weight, "status": l.status} for l in labels]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.put("/box-labels/{label_id}/print", response_model=None)
async def print_box_label(label_id: str, svc: FbaBoxLabelService = Depends(get_box_label_service)):
    label = await svc.update_status(label_id, tenant_id_var.get(""), "printed")
    return Result.ok(data={"id": label.id, "status": label.status}, trace_id=trace_id_var.get(""))


@router.put("/box-labels/{label_id}/void", response_model=None)
async def void_box_label(label_id: str, svc: FbaBoxLabelService = Depends(get_box_label_service)):
    label = await svc.void_label(label_id, tenant_id_var.get(""))
    return Result.ok(data={"id": label.id, "status": label.status}, trace_id=trace_id_var.get(""))


# ──── 补货计划 ────


@router.post("/replenishment-plans", response_model=None)
async def create_replenishment_plan(req: ReplenishmentPlanCreateRequest, svc: FbaReplenishmentPlanService = Depends(get_replenishment_service)):
    plan = await svc.create(tenant_id_var.get(""), req.sku_id, req.store_id, req.suggested_qty,
                            current_qty=req.current_qty, avg_daily_sales=req.avg_daily_sales,
                            days_of_supply=req.days_of_supply, destination_center=req.destination_center)
    return Result.ok(data={"id": plan.id, "sku_id": plan.sku_id, "store_id": plan.store_id,
                           "suggested_qty": plan.suggested_qty, "current_qty": plan.current_qty,
                           "avg_daily_sales": plan.avg_daily_sales, "days_of_supply": plan.days_of_supply,
                           "priority": plan.priority, "status": plan.status}, trace_id=trace_id_var.get(""))


@router.get("/replenishment-plans", response_model=None)
async def list_replenishment_plans(store_id: str = Query(default=""), status: str = Query(default=""),
                                    priority: str = Query(default=""),
                                    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                                    svc: FbaReplenishmentPlanService = Depends(get_replenishment_service)):
    plans = await svc.list_by_tenant(tenant_id_var.get(""), status=status or None,
                                      store_id=store_id or None, priority=priority or None,
                                      offset=offset, limit=limit)
    data = [{"id": p.id, "sku_id": p.sku_id, "store_id": p.store_id, "suggested_qty": p.suggested_qty,
             "approved_qty": p.approved_qty, "priority": p.priority, "status": p.status,
             "avg_daily_sales": p.avg_daily_sales, "days_of_supply": p.days_of_supply} for p in plans]
    return Result.ok(data={"items": data, "total": len(data)}, trace_id=trace_id_var.get(""))


@router.put("/replenishment-plans/{plan_id}/approve", response_model=None)
async def approve_replenishment_plan(plan_id: str, req: ApproveReplenishmentRequest | None = None,
                                      svc: FbaReplenishmentPlanService = Depends(get_replenishment_service)):
    approved_qty = req.approved_qty if req else None
    plan = await svc.approve(plan_id, tenant_id_var.get(""), approved_qty=approved_qty)
    return Result.ok(data={"id": plan.id, "status": plan.status, "approved_qty": plan.approved_qty},
                     trace_id=trace_id_var.get(""))


@router.put("/replenishment-plans/{plan_id}/reject", response_model=None)
async def reject_replenishment_plan(plan_id: str, svc: FbaReplenishmentPlanService = Depends(get_replenishment_service)):
    plan = await svc.reject(plan_id, tenant_id_var.get(""))
    return Result.ok(data={"id": plan.id, "status": plan.status}, trace_id=trace_id_var.get(""))


@router.post("/replenishment-plans/auto-generate", response_model=None)
async def auto_generate_replenishment(req: AutoGenerateReplenishmentRequest,
                                       svc: FbaReplenishmentPlanService = Depends(get_replenishment_service)):
    plans = await svc.auto_generate(tenant_id_var.get(""), req.store_id, req.avg_daily_sales_map,
                                    req.inventory_map, lead_time_days=req.lead_time_days,
                                    safety_stock_days=req.safety_stock_days, days_of_supply=req.days_of_supply)
    data = [{"id": p.id, "sku_id": p.sku_id, "suggested_qty": p.suggested_qty,
             "priority": p.priority, "status": p.status} for p in plans]
    return Result.ok(data={"generated_count": len(plans), "plans": data}, trace_id=trace_id_var.get(""))


# ──── 入库计划 ────


@router.post("/inbound-plans", response_model=None)
async def create_inbound_plan(
    name: str = Query(..., min_length=1), plan_no: str = Query(..., min_length=1),
    destination_fba_center: str = "", total_units: int = 0,
    svc: FbaInboundPlanService = Depends(get_inbound_plan_service),
):
    plan = await svc.create(tenant_id_var.get(""), name=name, plan_no=plan_no,
                            destination_fba_center=destination_fba_center, total_units=total_units)
    return Result.ok(data={"id": plan.id, "plan_no": plan_no, "status": plan.status},
                     trace_id=trace_id_var.get(""))


@router.get("/inbound-plans", response_model=None)
async def list_inbound_plans(status: str = Query(default=""),
                              offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                              svc: FbaInboundPlanService = Depends(get_inbound_plan_service)):
    plans = await svc.list_by_tenant(tenant_id_var.get(""), status=status or None,
                                      offset=offset, limit=limit)
    data = [{"id": p.id, "plan_no": p.plan_no, "name": p.name, "status": p.status,
             "total_units": p.total_units, "destination_fba_center": p.destination_fba_center}
            for p in plans]
    return Result.ok(data={"items": data, "total": len(data)}, trace_id=trace_id_var.get(""))


@router.put("/inbound-plans/{plan_id}/status", response_model=None)
async def update_inbound_plan_status(plan_id: str, req: ShipmentStatusRequest,
                                      svc: FbaInboundPlanService = Depends(get_inbound_plan_service)):
    plan = await svc.update_status(plan_id, tenant_id_var.get(""), req.status)
    return Result.ok(data={"id": plan.id, "status": plan.status}, trace_id=trace_id_var.get(""))


@router.put("/inbound-plans/{plan_id}/submit", response_model=None)
async def submit_inbound_plan(plan_id: str, svc: FbaInboundPlanService = Depends(get_inbound_plan_service)):
    plan = await svc.submit(plan_id, tenant_id_var.get(""))
    return Result.ok(data={"id": plan.id, "status": plan.status}, trace_id=trace_id_var.get(""))


# ──── PMS 跨域查询 ────


@router.get("/pms/inventory", response_model=None)
async def pms_inventory(store_id: str = Query(default=""), asin: str = Query(default=""),
                        svc: FbaInventoryService = Depends(get_inventory_service)):
    items = await svc.list_by_tenant(tenant_id_var.get(""), store_id=store_id or None, offset=0, limit=100)
    if asin:
        items = [i for i in items if i.asin == asin]
    data = [{"sku_id": i.sku_id, "asin": i.asin, "fnsku": i.fnsku, "qty_available": i.qty_available,
             "qty_fulfillable": i.qty_fulfillable, "qty_inbound": i.qty_inbound, "store_id": i.store_id} for i in items]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/pms/shipments", response_model=None)
async def pms_shipments(status: str = Query(default=""), svc: FbaShipmentService = Depends(get_shipment_service)):
    shipments = await svc.list_by_tenant(tenant_id_var.get(""), status=status or None, offset=0, limit=100)
    data = [{"shipment_id": s.shipment_id, "fba_shipment_id": s.fba_shipment_id, "status": s.status,
             "total_units": s.total_units, "tracking_no": s.tracking_no} for s in shipments]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))
