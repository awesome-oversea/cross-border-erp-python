from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from erp.middleware.ad_optimization.application.services import AdOptimizationService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/ads/v1/optimization", tags=["Ad Optimization - 广告优化中台"])


class SuggestionRequest(BaseModel):
    campaign_id: str = ""
    spend: float = 0
    sales: float = 0
    clicks: int = 0
    impressions: int = 0
    acos: float = 0
    daily_budget: float = 0


class BudgetAllocateRequest(BaseModel):
    campaigns: list[dict]
    total_budget: float = Field(gt=0)


class PmsInstructionRequest(BaseModel):
    id: str = ""
    type: str = ""
    data: dict = Field(default_factory=dict)


@router.get("/suggestions", response_model=None)
async def get_suggestions(campaign_id: str = "", spend: float = 0, sales: float = 0,
                           clicks: int = 0, impressions: int = 0, acos: float = 0,
                           daily_budget: float = 0, session: AsyncSession = Depends(get_db_session)):
    svc = AdOptimizationService(session)
    campaign_data = {"campaign_id": campaign_id, "spend": spend, "sales": sales,
                     "clicks": clicks, "impressions": impressions, "acos": acos, "daily_budget": daily_budget}
    suggestions = await svc.get_suggestions(tenant_id_var.get(""), campaign_data)
    return Result.ok(data=suggestions, trace_id=trace_id_var.get(""))


@router.post("/budget-allocate", response_model=None)
async def allocate_budget(req: BudgetAllocateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = AdOptimizationService(session)
    result = await svc.allocate_budget(tenant_id_var.get(""), req.campaigns, req.total_budget)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/performance", response_model=None)
async def get_performance(campaign_id: str = "", spend: float = 0, sales: float = 0,
                           clicks: int = 0, impressions: int = 0,
                           session: AsyncSession = Depends(get_db_session)):
    svc = AdOptimizationService(session)
    campaign_data = {"campaign_id": campaign_id, "spend": spend, "sales": sales,
                     "clicks": clicks, "impressions": impressions}
    result = await svc.get_performance(tenant_id_var.get(""), campaign_data)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/pms/execute", response_model=None)
async def execute_pms_instruction(req: PmsInstructionRequest, session: AsyncSession = Depends(get_db_session)):
    svc = AdOptimizationService(session)
    result = await svc.execute_pms_instruction(tenant_id_var.get(""), req.model_dump())
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/pms/{log_id}/rollback", response_model=None)
async def rollback_pms_operation(log_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = AdOptimizationService(session)
    result = await svc.rollback_pms_operation(tenant_id_var.get(""), log_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
