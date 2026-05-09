from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.fba.application.services import (
    FbaInventoryService,
    FbaReplenishmentPlanService,
    FbaShipmentService,
)
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import NotFoundException, Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/fba/out/v1", tags=["FBA-Outbound"])


class FbaInventorySyncRequest(BaseModel):
    store_id: str = Field(..., min_length=1)
    sku_id: str = ""
    asin: str = ""
    qty_fulfillable: int = Field(default=0, ge=0)
    qty_inbound: int = Field(default=0, ge=0)
    qty_reserved: int = Field(default=0, ge=0)
    fnsku: str = ""
    fulfillment_center_id: str = ""


class FbaShipmentStatusSyncRequest(BaseModel):
    fba_shipment_id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    tracking_no: str = ""
    carrier: str = ""
    received_units: int = Field(default=0, ge=0)


class ReplenishmentAdviceRequest(BaseModel):
    sku_id: str = Field(..., min_length=1)
    store_id: str = Field(..., min_length=1)
    suggested_qty: int = Field(..., ge=1)
    avg_daily_sales: float = Field(default=0.0, ge=0)
    days_of_supply: int = Field(default=30, ge=1)
    source: str = "wms"


class FbaFeeSyncRequest(BaseModel):
    sku_id: str = Field(..., min_length=1)
    store_id: str = Field(..., min_length=1)
    fee_type: str = Field(..., min_length=1)
    fee_amount: float = Field(default=0.0, ge=0)
    currency: str = "USD"
    quantity: int = Field(default=0, ge=0)
    per_unit_fee: float = Field(default=0.0, ge=0)


@router.post("/inventory-sync", response_model=None)
async def sync_fba_inventory(req: FbaInventorySyncRequest, session: AsyncSession = Depends(get_db_session)):
    svc = FbaInventoryService(session)
    existing = await svc.find_by_sku_store(req.sku_id, req.store_id, tenant_id_var.get(""))
    if existing:
        existing.qty_fulfillable = req.qty_fulfillable
        existing.qty_inbound = req.qty_inbound
        existing.qty_reserved = req.qty_reserved
        if req.fnsku:
            existing.fnsku = req.fnsku
        await session.flush()
        return Result.ok(data={"id": existing.id, "sku_id": existing.sku_id, "action": "updated"},
                         trace_id=trace_id_var.get(""))
    inv = await svc.create(tenant_id_var.get(""), req.sku_id, req.store_id,
                           fnsku=req.fnsku, asin=req.asin, qty_fulfillable=req.qty_fulfillable,
                           qty_inbound=req.qty_inbound, qty_reserved=req.qty_reserved,
                           fulfillment_center_id=req.fulfillment_center_id)
    return Result.ok(data={"id": inv.id, "sku_id": inv.sku_id, "action": "created"},
                     trace_id=trace_id_var.get(""))


@router.post("/shipment-status-sync", response_model=None)
async def sync_shipment_status(req: FbaShipmentStatusSyncRequest, session: AsyncSession = Depends(get_db_session)):
    svc = FbaShipmentService(session)
    shipment = await svc.get_by_shipment_id_or_raise(req.fba_shipment_id, tenant_id_var.get(""))
    if req.tracking_no:
        shipment.tracking_no = req.tracking_no
    if req.carrier:
        shipment.carrier = req.carrier
    if req.received_units > 0:
        shipment.received_units = (shipment.received_units or 0) + req.received_units
    shipment.status = req.status
    await session.flush()
    return Result.ok(data={"id": shipment.id, "fba_shipment_id": shipment.fba_shipment_id,
                           "status": shipment.status}, trace_id=trace_id_var.get(""))


@router.post("/replenishment-advice", response_model=None)
async def receive_replenishment_advice(req: ReplenishmentAdviceRequest,
                                        session: AsyncSession = Depends(get_db_session)):
    svc = FbaReplenishmentPlanService(session)
    plan = await svc.create(tenant_id_var.get(""), req.sku_id, req.store_id, req.suggested_qty,
                            avg_daily_sales=req.avg_daily_sales, days_of_supply=req.days_of_supply)
    return Result.ok(data={"id": plan.id, "sku_id": plan.sku_id, "suggested_qty": plan.suggested_qty,
                           "source": req.source, "status": plan.status}, trace_id=trace_id_var.get(""))


@router.post("/fee-sync", response_model=None)
async def sync_fba_fee(req: FbaFeeSyncRequest, session: AsyncSession = Depends(get_db_session)):
    from erp.modules.fba.application.services import FbaFeeService
    svc = FbaFeeService(session)
    fee = await svc.create(tenant_id_var.get(""), req.sku_id, req.store_id, req.fee_type,
                           req.fee_amount, currency=req.currency, quantity=req.quantity,
                           per_unit_fee=req.per_unit_fee)
    return Result.ok(data={"id": fee.id, "sku_id": fee.sku_id, "fee_type": fee.fee_type,
                           "fee_amount": fee.fee_amount}, trace_id=trace_id_var.get(""))


@router.get("/inventory-summary", response_model=None)
async def get_inventory_summary(store_id: str = Query(default=""), sku_id: str = Query(default=""),
                                 session: AsyncSession = Depends(get_db_session)):
    svc = FbaInventoryService(session)
    items = await svc.list_by_tenant(tenant_id_var.get(""), store_id=store_id or None, offset=0, limit=500)
    if sku_id:
        items = [i for i in items if i.sku_id == sku_id]
    total_fulfillable = sum(i.qty_fulfillable for i in items)
    total_inbound = sum(i.qty_inbound for i in items)
    total_reserved = sum(i.qty_reserved for i in items)
    return Result.ok(data={"total_skus": len(items), "total_fulfillable": total_fulfillable,
                           "total_inbound": total_inbound, "total_reserved": total_reserved},
                     trace_id=trace_id_var.get(""))
