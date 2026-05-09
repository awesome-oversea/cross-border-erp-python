from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.fms.domain.billing_strategy_models import BillingStrategyService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/fms/v1/billing-strategies", tags=["FMS-BillingStrategy"])


class StrategyCreateRequest(BaseModel):
    strategy_code: str = Field(..., min_length=1, max_length=100)
    strategy_name: str = Field(..., min_length=1, max_length=200)
    fee_type: str = Field(..., pattern=r"^(platform_fee|logistics_fee|warehouse_fee|service_fee|other_fee)$")
    description: str = Field(default="")
    calculation_method: str = Field(default="percentage", pattern=r"^(percentage|fixed|tiered|formula)$")
    condition: dict = Field(default_factory=dict)
    rate: dict = Field(default_factory=dict)
    tiers: list = Field(default_factory=list)
    formula: dict = Field(default_factory=dict)
    currency: str = Field(default="CNY")
    min_fee: float = Field(default=0)
    max_fee: float = Field(default=0)
    priority: int = Field(default=0)
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class StrategyUpdateRequest(BaseModel):
    strategy_name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    calculation_method: str | None = None
    condition: dict | None = None
    rate: dict | None = None
    tiers: list | None = None
    formula: dict | None = None
    min_fee: float | None = None
    max_fee: float | None = None


class FeeCalculateRequest(BaseModel):
    fee_type: str = Field(..., pattern=r"^(platform_fee|logistics_fee|warehouse_fee|service_fee|other_fee)$")
    base_amount: float = Field(..., ge=0)
    context: dict = Field(default_factory=dict)
    source_type: str = Field(default="")
    source_id: str = Field(default="")
    order_id: str = Field(default="")


@router.post("", response_model=None)
async def create_strategy(req: StrategyCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = BillingStrategyService(session)
    strategy = await svc.create_strategy(
        tenant_id=tenant_id_var.get(""), strategy_code=req.strategy_code,
        strategy_name=req.strategy_name, fee_type=req.fee_type,
        description=req.description, calculation_method=req.calculation_method,
        condition=req.condition, rate=req.rate, tiers=req.tiers,
        formula=req.formula, currency=req.currency,
        min_fee=req.min_fee, max_fee=req.max_fee, priority=req.priority,
        effective_from=req.effective_from, effective_to=req.effective_to,
    )
    return Result.ok(
        data={"id": strategy.id, "strategy_code": strategy.strategy_code,
              "strategy_name": strategy.strategy_name, "fee_type": strategy.fee_type,
              "calculation_method": strategy.calculation_method,
              "currency": strategy.currency, "version": strategy.version},
        trace_id=trace_id_var.get(""),
    )


@router.get("", response_model=None)
async def list_strategies(
    fee_type: str = Query(default=""),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = BillingStrategyService(session)
    strategies, total = await svc.list_strategies(
        tenant_id_var.get(""), fee_type=fee_type,
        is_active=is_active, page=page, page_size=page_size,
    )
    data = [{
        "id": s.id, "strategy_code": s.strategy_code, "strategy_name": s.strategy_name,
        "fee_type": s.fee_type, "calculation_method": s.calculation_method,
        "description": s.description, "currency": s.currency,
        "min_fee": float(s.min_fee), "max_fee": float(s.max_fee),
        "priority": s.priority, "is_active": s.is_active, "version": s.version,
        "effective_from": s.effective_from.isoformat() if s.effective_from else None,
        "effective_to": s.effective_to.isoformat() if s.effective_to else None,
    } for s in strategies]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.put("/{strategy_id}", response_model=None)
async def update_strategy(strategy_id: str, req: StrategyUpdateRequest,
                           session: AsyncSession = Depends(get_db_session)):
    svc = BillingStrategyService(session)
    strategy = await svc.update_strategy(
        strategy_id, tenant_id_var.get(""),
        strategy_name=req.strategy_name, description=req.description,
        calculation_method=req.calculation_method, condition=req.condition,
        rate=req.rate, tiers=req.tiers, formula=req.formula,
        min_fee=req.min_fee, max_fee=req.max_fee,
    )
    return Result.ok(data={"id": strategy.id, "version": strategy.version}, trace_id=trace_id_var.get(""))


@router.put("/{strategy_id}/deactivate", response_model=None)
async def deactivate_strategy(strategy_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = BillingStrategyService(session)
    strategy = await svc.deactivate_strategy(strategy_id, tenant_id_var.get(""))
    return Result.ok(data={"id": strategy.id, "is_active": strategy.is_active}, trace_id=trace_id_var.get(""))


@router.post("/calculate", response_model=None)
async def calculate_fee(req: FeeCalculateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = BillingStrategyService(session)
    log = await svc.calculate_fee(
        tenant_id_var.get(""), fee_type=req.fee_type,
        base_amount=Decimal(str(req.base_amount)), context=req.context,
        source_type=req.source_type, source_id=req.source_id,
        order_id=req.order_id,
    )
    return Result.ok(
        data={"id": log.id, "strategy_code": log.strategy_code,
              "fee_type": log.fee_type, "base_amount": float(log.base_amount),
              "calculated_fee": float(log.calculated_fee),
              "currency": log.currency,
              "calculation_detail": json.loads(log.calculation_detail)},
        trace_id=trace_id_var.get(""),
    )


@router.get("/calculation-logs", response_model=None)
async def list_calculation_logs(
    fee_type: str = Query(default=""),
    order_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = BillingStrategyService(session)
    logs, total = await svc.list_calculation_logs(
        tenant_id_var.get(""), fee_type=fee_type,
        order_id=order_id, page=page, page_size=page_size,
    )
    data = [{
        "id": log.id, "strategy_code": log.strategy_code, "fee_type": log.fee_type,
        "source_type": log.source_type, "source_id": log.source_id,
        "order_id": log.order_id, "base_amount": float(log.base_amount),
        "calculated_fee": float(log.calculated_fee), "currency": log.currency,
        "calculation_detail": json.loads(log.calculation_detail),
        "trace_id": log.trace_id,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    } for log in logs]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/init-defaults", response_model=None)
async def init_default_strategies(session: AsyncSession = Depends(get_db_session)):
    svc = BillingStrategyService(session)
    await svc.init_defaults(tenant_id_var.get(""))
    return Result.ok(data={"message": "Default billing strategies initialized"}, trace_id=trace_id_var.get(""))
