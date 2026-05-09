from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.selection.application.services import SelectionService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/pdm/v1/selection", tags=["Selection - 选品分析中台"])


class ProfitSimulationRequest(BaseModel):
    sale_price: float = Field(gt=0)
    cost_price: float = Field(ge=0)
    shipping_cost: float = Field(default=0, ge=0)
    commission_rate: float = Field(default=0.15, ge=0, le=1)
    vat_rate: float = Field(default=0, ge=0, le=1)
    advertising_cost: float = Field(default=0, ge=0)
    other_costs: float = Field(default=0, ge=0)
    currency: str = Field(default="USD", max_length=10)
    monthly_sales_estimate: int = Field(default=100, ge=1)


@router.get("/market-analysis", response_model=None)
async def market_analysis(category: str = Query(...), marketplace: str = Query(default="amazon_us"),
                           session: AsyncSession = Depends(get_db_session)):
    svc = SelectionService(session)
    result = await svc.market_analysis(tenant_id_var.get(""), category, marketplace)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/competitor-analysis", response_model=None)
async def competitor_analysis(category: str = Query(...), marketplace: str = Query(default="amazon_us"),
                               session: AsyncSession = Depends(get_db_session)):
    svc = SelectionService(session)
    result = await svc.competitor_analysis(tenant_id_var.get(""), category, marketplace)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/profit-simulation", response_model=None)
async def profit_simulation(req: ProfitSimulationRequest, session: AsyncSession = Depends(get_db_session)):
    svc = SelectionService(session)
    result = await svc.profit_simulation(
        tenant_id_var.get(""), sale_price=req.sale_price, cost_price=req.cost_price,
        shipping_cost=req.shipping_cost, commission_rate=req.commission_rate,
        vat_rate=req.vat_rate, advertising_cost=req.advertising_cost,
        other_costs=req.other_costs, currency=req.currency,
        monthly_sales_estimate=req.monthly_sales_estimate,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
