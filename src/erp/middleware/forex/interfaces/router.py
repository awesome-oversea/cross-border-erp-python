from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.forex.application.services import ForexService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/fms/v1/forex", tags=["Forex - 货币汇率中心"])


class ConvertItem(BaseModel):
    amount: float = Field(gt=0)
    from_currency: str = Field(min_length=3, max_length=10)
    to_currency: str = Field(min_length=3, max_length=10)
    rate_date: str = Field(default="")


class ConvertRequest(BaseModel):
    items: list[ConvertItem]


class GainLossRequest(BaseModel):
    original_amount: float = Field(gt=0)
    original_currency: str = Field(min_length=3, max_length=10)
    original_rate: float = Field(gt=0)
    current_rate: float = Field(gt=0)
    target_currency: str = Field(default="CNY", max_length=10)


class AlertRuleCreateRequest(BaseModel):
    from_currency: str = Field(min_length=3, max_length=10)
    to_currency: str = Field(min_length=3, max_length=10)
    threshold_pct: float = Field(default=5.0, gt=0)
    direction: str = Field(default="both", pattern="^(up|down|both)$")
    is_active: bool = Field(default=True)


@router.get("/rates", response_model=None)
async def list_rates(base_currency: str = Query(default="USD"),
                     target_currencies: str = Query(default=""),
                     rate_date: str = Query(default=""),
                     session: AsyncSession = Depends(get_db_session)):
    svc = ForexService(session)
    targets = [item.strip().upper() for item in target_currencies.split(",") if item.strip()] or None
    target_date = date.fromisoformat(rate_date) if rate_date else None
    result = await svc.list_rates(tenant_id_var.get(""), base_currency.upper(), targets, target_date)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/rates/{from_currency}/{to_currency}", response_model=None)
async def get_rate(from_currency: str, to_currency: str, rate_date: str = Query(default=""),
                   session: AsyncSession = Depends(get_db_session)):
    svc = ForexService(session)
    target_date = date.fromisoformat(rate_date) if rate_date else None
    result = await svc.get_rate(tenant_id_var.get(""), from_currency.upper(), to_currency.upper(), target_date)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/rates/{from_currency}/{to_currency}/snapshot", response_model=None)
async def get_snapshot(from_currency: str, to_currency: str, snapshot_date: str = Query(...),
                       session: AsyncSession = Depends(get_db_session)):
    svc = ForexService(session)
    result = await svc.get_snapshot(
        tenant_id_var.get(""),
        from_currency.upper(),
        to_currency.upper(),
        date.fromisoformat(snapshot_date),
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/history", response_model=None)
async def get_history(from_currency: str = Query(...), to_currency: str = Query(...),
                      start_date: str = Query(...), end_date: str = Query(...),
                      session: AsyncSession = Depends(get_db_session)):
    svc = ForexService(session)
    records = await svc.get_history(
        tenant_id_var.get(""),
        from_currency.upper(),
        to_currency.upper(),
        date.fromisoformat(start_date),
        date.fromisoformat(end_date),
    )
    items = [{"rate_date": str(r.rate_date), "rate": r.rate, "source": r.source} for r in records]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.post("/convert", response_model=None)
async def convert(req: ConvertRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ForexService(session)
    items = [i.model_dump() for i in req.items]
    results = await svc.convert(tenant_id_var.get(""), items)
    return Result.ok(data=results, trace_id=trace_id_var.get(""))


@router.post("/gain-loss/calculate", response_model=None)
async def calculate_gain_loss(req: GainLossRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ForexService(session)
    result = await svc.calculate_gain_loss(
        tenant_id_var.get(""), req.original_amount, req.original_currency,
        req.original_rate, req.current_rate, req.target_currency,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/risk-alert", response_model=None)
async def get_risk_alerts(session: AsyncSession = Depends(get_db_session)):
    svc = ForexService(session)
    alerts = await svc.get_risk_alerts(tenant_id_var.get(""))
    return Result.ok(data=alerts, trace_id=trace_id_var.get(""))


@router.get("/alert-rules", response_model=None)
async def list_alert_rules(is_active: bool | None = Query(default=None),
                           session: AsyncSession = Depends(get_db_session)):
    svc = ForexService(session)
    rules = await svc.list_alert_rules(tenant_id_var.get(""), is_active=is_active)
    items = [{
        "id": rule.id,
        "from_currency": rule.from_currency,
        "to_currency": rule.to_currency,
        "threshold_pct": rule.threshold_pct,
        "direction": rule.direction,
        "is_active": rule.is_active,
        "last_alerted_at": rule.last_alerted_at.isoformat() if rule.last_alerted_at else None,
    } for rule in rules]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.post("/alert-rules", response_model=None)
async def create_alert_rule(req: AlertRuleCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ForexService(session)
    rule = await svc.create_alert_rule(
        tenant_id=tenant_id_var.get(""),
        from_currency=req.from_currency,
        to_currency=req.to_currency,
        threshold_pct=req.threshold_pct,
        direction=req.direction,
        is_active=req.is_active,
    )
    return Result.ok(data={
        "id": rule.id,
        "from_currency": rule.from_currency,
        "to_currency": rule.to_currency,
        "threshold_pct": rule.threshold_pct,
        "direction": rule.direction,
        "is_active": rule.is_active,
    }, trace_id=trace_id_var.get(""))


@router.post("/alert-rules/init-defaults", response_model=None)
async def init_default_alert_rules(session: AsyncSession = Depends(get_db_session)):
    svc = ForexService(session)
    rules = await svc.init_default_alert_rules(tenant_id_var.get(""))
    return Result.ok(data={"created_count": len(rules)}, trace_id=trace_id_var.get(""))


@router.post("/rates/sync", response_model=None)
async def sync_rates(session: AsyncSession = Depends(get_db_session)):
    svc = ForexService(session)
    result = await svc.sync_rates(tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
