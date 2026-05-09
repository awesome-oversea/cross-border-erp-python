from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from erp.middleware.profit_engine.application.services import ProfitEngineService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/fms/v1/profit-engine", tags=["Profit Engine - 利润核算中台"])


class CalculateRequest(BaseModel):
    revenue: float = Field(gt=0)
    purchase_cost: float = Field(default=0, ge=0)
    head_freight: float = Field(default=0, ge=0)
    warehouse_fee: float = Field(default=0, ge=0)
    platform_commission: float = Field(default=0, ge=0)
    advertising_cost: float = Field(default=0, ge=0)
    payment_fee: float = Field(default=0, ge=0)
    last_mile_cost: float = Field(default=0, ge=0)
    other_costs: float = Field(default=0, ge=0)
    vat_amount: float = Field(default=0, ge=0)
    currency: str = Field(default="USD", max_length=10)
    quantity: int = Field(default=1, ge=1)


class SettlementRequest(BaseModel):
    order_amount: float = Field(gt=0)
    platform: str = Field(default="amazon", max_length=32)
    cost_price: float = Field(default=0, ge=0)
    shipping_fee: float = Field(default=0, ge=0)
    commission_rate: float = Field(default=0.15, ge=0, le=1)
    vat_rate: float = Field(default=0, ge=0, le=1)
    advertising_share: float = Field(default=0, ge=0)


class AggregateRequest(BaseModel):
    records: list[dict]
    period_key: str = Field(default="month")


@router.post("/calculate", response_model=None)
async def calculate_profit(req: CalculateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ProfitEngineService(session)
    result = await svc.calculate(
        tenant_id_var.get(""), revenue=req.revenue, purchase_cost=req.purchase_cost,
        head_freight=req.head_freight, warehouse_fee=req.warehouse_fee,
        platform_commission=req.platform_commission, advertising_cost=req.advertising_cost,
        payment_fee=req.payment_fee, last_mile_cost=req.last_mile_cost,
        other_costs=req.other_costs, vat_amount=req.vat_amount,
        currency=req.currency, quantity=req.quantity,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/settlement", response_model=None)
async def calculate_settlement(req: SettlementRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ProfitEngineService(session)
    result = await svc.calculate_settlement(
        tenant_id_var.get(""), order_amount=req.order_amount, platform=req.platform,
        cost_price=req.cost_price, shipping_fee=req.shipping_fee,
        commission_rate=req.commission_rate, vat_rate=req.vat_rate,
        advertising_share=req.advertising_share,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/aggregate", response_model=None)
async def aggregate_by_period(req: AggregateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ProfitEngineService(session)
    result = await svc.aggregate_by_period(tenant_id_var.get(""), req.records, req.period_key)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
