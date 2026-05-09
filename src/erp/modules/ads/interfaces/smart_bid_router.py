from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.ads.domain.smart_bid_models import SmartBidService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/ads/v1/smart-bid", tags=["ADS-SmartBid"])


class BidRuleCreateRequest(BaseModel):
    rule_name: str = Field(..., min_length=1, max_length=200)
    strategy: str = Field(default="target_acos", pattern=r"^(fixed|dynamic_down|dynamic_up_down|target_acos|rule_based)$")
    condition: dict = Field(default_factory=dict)
    action: dict = Field(default_factory=dict)
    priority: int = Field(default=0)


class BidCalculateRequest(BaseModel):
    campaign_id: str = Field(..., min_length=1)
    ad_group_id: str = Field(..., min_length=1)
    keyword_id: str = Field(default="")
    current_bid: float = Field(default=0.0, ge=0)
    actual_acos: float = Field(default=0.0, ge=0)
    target_acos: float = Field(default=0.0, ge=0)
    ctr: float = Field(default=0.0, ge=0)
    cr: float = Field(default=0.0, ge=0)
    avg_cpc: float = Field(default=0.0, ge=0)
    strategy: str = Field(default="target_acos")
    rule_params: dict = Field(default_factory=dict)


@router.post("/rules", response_model=None)
async def create_bid_rule(req: BidRuleCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = SmartBidService(session)
    rule = await svc.create_bid_rule(
        tenant_id=tenant_id_var.get(""), rule_name=req.rule_name,
        strategy=req.strategy, condition=req.condition,
        action=req.action, priority=req.priority,
    )
    return Result.ok(
        data={"id": rule.id, "rule_name": rule.rule_name, "strategy": rule.strategy},
        trace_id=trace_id_var.get(""),
    )


@router.get("/rules", response_model=None)
async def list_bid_rules(strategy: str = Query(default=""),
                          session: AsyncSession = Depends(get_db_session)):
    svc = SmartBidService(session)
    rules = await svc.list_bid_rules(tenant_id_var.get(""), strategy=strategy)
    data = [{
        "id": r.id, "rule_name": r.rule_name, "strategy": r.strategy,
        "condition": json.loads(r.condition_json), "action": json.loads(r.action_json),
        "priority": r.priority, "is_active": r.is_active,
    } for r in rules]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/calculate", response_model=None)
async def calculate_bid(req: BidCalculateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = SmartBidService(session)
    adj = await svc.calculate_bid(
        tenant_id=tenant_id_var.get(""), campaign_id=req.campaign_id,
        ad_group_id=req.ad_group_id, keyword_id=req.keyword_id,
        current_bid=req.current_bid, actual_acos=req.actual_acos,
        target_acos=req.target_acos, ctr=req.ctr, cr=req.cr,
        avg_cpc=req.avg_cpc, strategy=req.strategy,
        rule_params=req.rule_params,
    )
    return Result.ok(
        data={"id": adj.id, "current_bid": adj.current_bid,
              "suggested_bid": adj.suggested_bid, "strategy": adj.strategy,
              "adjustment_reason": adj.adjustment_reason, "is_applied": adj.is_applied},
        trace_id=trace_id_var.get(""),
    )


@router.post("/adjustments/{adjustment_id}/apply", response_model=None)
async def apply_bid(adjustment_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = SmartBidService(session)
    adj = await svc.apply_bid(adjustment_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": adj.id, "applied_bid": adj.applied_bid, "is_applied": adj.is_applied},
        trace_id=trace_id_var.get(""),
    )


@router.get("/adjustments", response_model=None)
async def list_bid_adjustments(
    campaign_id: str = Query(default=""),
    is_applied: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = SmartBidService(session)
    adjustments, total = await svc.list_bid_adjustments(
        tenant_id_var.get(""), campaign_id=campaign_id,
        is_applied=is_applied, page=page, page_size=page_size,
    )
    data = [{
        "id": a.id, "campaign_id": a.campaign_id, "ad_group_id": a.ad_group_id,
        "keyword_id": a.keyword_id, "strategy": a.strategy,
        "current_bid": a.current_bid, "suggested_bid": a.suggested_bid,
        "applied_bid": a.applied_bid, "target_acos": a.target_acos,
        "actual_acos": a.actual_acos, "adjustment_reason": a.adjustment_reason,
        "is_applied": a.is_applied,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in adjustments]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))
