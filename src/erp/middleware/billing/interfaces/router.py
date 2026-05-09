from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.billing.application.services import BillingService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/fms/v1/billing", tags=["Billing - 计费策略中心"])


class SimulateRequest(BaseModel):
    platform: str = Field(default="amazon", max_length=32)
    sale_price: float = Field(gt=0)
    quantity: int = Field(default=1, ge=1)
    category: str = Field(default="")
    currency: str = Field(default="USD", max_length=10)
    weight_kg: float = Field(default=0, ge=0)
    warehouse_type: str = Field(default="fba")
    shipping_cost: float = Field(default=0, ge=0)
    cost_price: float = Field(default=0, ge=0)
    packaging_type: str = Field(default="medium_box")


class FreightAllocateRequest(BaseModel):
    total_freight: float = Field(gt=0)
    items: list[dict]


class FbaHeadCostRequest(BaseModel):
    shipment_cost: float = Field(gt=0)
    total_units: int = Field(gt=0)
    damaged_units: int = Field(default=0, ge=0)
    lost_units: int = Field(default=0, ge=0)


@router.get("/platform-fees", response_model=None)
async def get_platform_fees(platform: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    svc = BillingService(session)
    fees = await svc.get_platform_fees(platform)
    return Result.ok(data=fees, trace_id=trace_id_var.get(""))


@router.post("/simulate", response_model=None)
async def simulate(req: SimulateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = BillingService(session)
    result = await svc.simulate(
        tenant_id_var.get(""), platform=req.platform, sale_price=req.sale_price,
        quantity=req.quantity, category=req.category, currency=req.currency,
        weight_kg=req.weight_kg, warehouse_type=req.warehouse_type,
        shipping_cost=req.shipping_cost, cost_price=req.cost_price, packaging_type=req.packaging_type,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/warehouse-fees", response_model=None)
async def get_warehouse_fees(warehouse_type: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    svc = BillingService(session)
    fees = await svc.get_warehouse_fees(warehouse_type)
    return Result.ok(data=fees, trace_id=trace_id_var.get(""))


@router.get("/freight-pool", response_model=None)
async def get_freight_pool(session: AsyncSession = Depends(get_db_session)):
    svc = BillingService(session)
    pool = await svc.get_freight_pool(tenant_id_var.get(""))
    return Result.ok(data=pool, trace_id=trace_id_var.get(""))


@router.post("/freight-allocate", response_model=None)
async def allocate_freight(req: FreightAllocateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = BillingService(session)
    result = await svc.allocate_freight(tenant_id_var.get(""), req.total_freight, req.items)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/packaging-costs", response_model=None)
async def get_packaging_costs(session: AsyncSession = Depends(get_db_session)):
    svc = BillingService(session)
    costs = await svc.get_packaging_costs()
    return Result.ok(data=costs, trace_id=trace_id_var.get(""))


@router.post("/fba-head-cost", response_model=None)
async def calculate_fba_head_cost(req: FbaHeadCostRequest, session: AsyncSession = Depends(get_db_session)):
    svc = BillingService(session)
    result = await svc.calculate_fba_head_cost(
        tenant_id_var.get(""), req.shipment_cost, req.total_units,
        req.damaged_units, req.lost_units,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
