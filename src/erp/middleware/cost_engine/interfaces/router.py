from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.cost_engine.application.services import CostEngineService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/fms/v1/cost-engine", tags=["Cost Engine - 成本归集中台"])


class CollectRequest(BaseModel):
    events: list[dict]


class BreakdownRequest(BaseModel):
    sku_id: str = Field(min_length=1)
    events: list[dict]
    period: str = Field(default="")


class AllocateRequest(BaseModel):
    shared_cost: float = Field(gt=0)
    sku_weights: dict[str, float]


class FifoRequest(BaseModel):
    layers: list[dict]
    quantity: int = Field(gt=0)


class AnomalyRequest(BaseModel):
    events: list[dict]
    threshold_pct: float = Field(default=50.0, gt=0)


@router.post("/collect", response_model=None)
async def collect_events(req: CollectRequest, session: AsyncSession = Depends(get_db_session)):
    svc = CostEngineService(session)
    result = await svc.collect_events(tenant_id_var.get(""), req.events)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/events", response_model=None)
async def query_events(sku_id: str = Query(default=""), cost_type: str = Query(default=""),
                        start_date: str = Query(default=""), end_date: str = Query(default=""),
                        session: AsyncSession = Depends(get_db_session)):
    svc = CostEngineService(session)
    events = await svc.query_events(tenant_id_var.get(""), sku_id, cost_type, start_date, end_date)
    return Result.ok(data=events, trace_id=trace_id_var.get(""))


@router.post("/breakdown", response_model=None)
async def generate_breakdown(req: BreakdownRequest, session: AsyncSession = Depends(get_db_session)):
    svc = CostEngineService(session)
    result = await svc.generate_breakdown(tenant_id_var.get(""), req.sku_id, req.events, req.period)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/allocate", response_model=None)
async def allocate_shared_costs(req: AllocateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = CostEngineService(session)
    result = await svc.allocate(tenant_id_var.get(""), req.shared_cost, req.sku_weights)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/fifo", response_model=None)
async def calculate_fifo(req: FifoRequest, session: AsyncSession = Depends(get_db_session)):
    svc = CostEngineService(session)
    result = await svc.calculate_fifo(tenant_id_var.get(""), req.layers, req.quantity)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/trend", response_model=None)
async def get_trend(sku_id: str = Query(default=""), period_type: str = Query(default="monthly"),
                     months: int = Query(default=6), session: AsyncSession = Depends(get_db_session)):
    svc = CostEngineService(session)
    result = await svc.get_trend(tenant_id_var.get(""), sku_id, period_type, months)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/anomaly", response_model=None)
async def detect_anomaly(req: AnomalyRequest, session: AsyncSession = Depends(get_db_session)):
    svc = CostEngineService(session)
    result = await svc.detect_anomaly(tenant_id_var.get(""), req.events, req.threshold_pct)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
