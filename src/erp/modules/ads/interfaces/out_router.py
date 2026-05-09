from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from erp.shared.context import trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/ads/out/v1", tags=["ADS-Outbound"])


class StrategyUpdateRequest(BaseModel):
    name: str | None = None
    bidding_strategy: str | None = None
    daily_budget: float | None = None
    target_acos: float | None = None
    status: str | None = None


class BudgetAllocateRequest(BaseModel):
    campaign_ids: list[str] = []
    total_budget: float = 0.0
    strategy: str = "proportional"


@router.get("/analytics/performance", response_model=None)
async def get_performance_for_pms(campaign_id: str = Query(default=""),
                                   ad_group_id: str = Query(default=""),
                                   start_date: str = Query(default=""),
                                   end_date: str = Query(default=""),
                                   session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"impressions": 0, "clicks": 0, "ctr": 0.0,
                           "spend": 0.0, "orders": 0, "revenue": 0.0,
                           "acos": 0.0, "roas": 0.0},
                     trace_id=trace_id_var.get(""))


@router.put("/strategies/{strategy_id}", response_model=None)
async def update_strategy(strategy_id: str, req: StrategyUpdateRequest,
                           session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"id": strategy_id, "updated": True}, trace_id=trace_id_var.get(""))


@router.post("/optimization/budget-allocate", response_model=None)
async def allocate_budget(req: BudgetAllocateRequest, session: AsyncSession = Depends(get_db_session)):
    allocations = []
    if req.campaign_ids and req.total_budget > 0:
        per_campaign = req.total_budget / len(req.campaign_ids)
        allocations = [{"campaign_id": cid, "allocated_budget": round(per_campaign, 2)} for cid in req.campaign_ids]
    return Result.ok(data={"allocations": allocations, "total_budget": req.total_budget,
                           "strategy": req.strategy}, trace_id=trace_id_var.get(""))
