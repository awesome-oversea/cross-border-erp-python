from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from erp.middleware.logistics_strategy.application.services import LogisticsStrategyService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/tms/v1/strategy", tags=["Logistics Strategy - 物流策略中心"])


class ProviderSelectRequest(BaseModel):
    origin_country: str = Field(default="CN", max_length=10)
    destination_country: str = Field(default="US", max_length=10)
    weight_kg: float = Field(gt=0)
    declared_value: float = Field(default=0, ge=0)
    currency: str = Field(default="USD", max_length=10)
    service_level: str = Field(default="standard")
    priority: str = Field(default="balanced", pattern="^(cost|speed|balanced)$")


class RateCalculateRequest(BaseModel):
    origin_country: str = Field(default="CN", max_length=10)
    destination_country: str = Field(default="US", max_length=10)
    weight_kg: float = Field(gt=0)
    provider_id: str = Field(min_length=1)
    currency: str = Field(default="USD", max_length=10)


@router.post("/select", response_model=None)
async def select_provider(req: ProviderSelectRequest, session: AsyncSession = Depends(get_db_session)):
    svc = LogisticsStrategyService(session)
    result = await svc.select_provider(
        tenant_id_var.get(""), origin_country=req.origin_country,
        destination_country=req.destination_country, weight_kg=req.weight_kg,
        declared_value=req.declared_value, currency=req.currency,
        service_level=req.service_level, priority=req.priority,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/calculate", response_model=None)
async def calculate_rate(req: RateCalculateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = LogisticsStrategyService(session)
    result = await svc.calculate_rate(
        tenant_id_var.get(""), origin_country=req.origin_country,
        destination_country=req.destination_country, weight_kg=req.weight_kg,
        provider_id=req.provider_id, currency=req.currency,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/rules", response_model=None)
async def get_rules(session: AsyncSession = Depends(get_db_session)):
    svc = LogisticsStrategyService(session)
    rules = await svc.get_rules(tenant_id_var.get(""))
    return Result.ok(data=rules, trace_id=trace_id_var.get(""))
