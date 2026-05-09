from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.order_strategy.application.services import OrderStrategyService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/oms/v1/strategies", tags=["Order Strategy - 订单策略中心"])


class StrategyEvaluateRequest(BaseModel):
    order_id: str = Field(default="")
    order_amount: float = Field(default=0, ge=0)
    currency: str = Field(default="USD", max_length=10)
    platform: str = Field(default="", max_length=32)
    store_id: str = Field(default="")
    items: list[dict] = Field(default_factory=list)
    shipping_address: dict = Field(default_factory=dict)
    customer_id: str = Field(default="")
    customer_segment: str = Field(default="")
    strategy_types: list[str] = Field(default_factory=list)


@router.get("", response_model=None)
async def list_strategies(strategy_type: str = Query(default=""),
                          session: AsyncSession = Depends(get_db_session)):
    svc = OrderStrategyService(session)
    strategies = await svc.list_strategies(tenant_id_var.get(""), strategy_type=strategy_type)
    return Result.ok(data=strategies, trace_id=trace_id_var.get(""))


@router.post("", response_model=None)
async def create_strategy(session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"message": "Strategy creation via config - not yet implemented"}, trace_id=trace_id_var.get(""))


@router.post("/evaluate", response_model=None)
async def evaluate_strategy(req: StrategyEvaluateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = OrderStrategyService(session)
    result = await svc.evaluate(
        tenant_id_var.get(""), order_id=req.order_id, order_amount=req.order_amount,
        currency=req.currency, platform=req.platform, store_id=req.store_id,
        items=req.items, shipping_address=req.shipping_address,
        customer_id=req.customer_id, customer_segment=req.customer_segment,
        strategy_types=req.strategy_types or None,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
