from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.sys.domain.pms_integration_models import (
    GrayRolloutService,
    PMSEventSubscriptionService,
    PMSFeedbackService,
)
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/api/out/v1/pms", tags=["SYS-PMS-Integration"])


class FeedbackSubmitRequest(BaseModel):
    recommendation_id: str = Field(..., min_length=1)
    erp_reference_id: str = Field(default="")
    domain: str = Field(..., min_length=1)
    feedback_type: str = Field(..., pattern=r"^(accepted|rejected|approved|executed|failed|rolled_back|effect_measured)$")
    feedback_reason: str = Field(default="")
    feedback_detail: dict = Field(default_factory=dict)
    effect_metrics: dict = Field(default_factory=dict)
    operator_id: str = Field(default="")
    operator_type: str = Field(default="user")


class SubscriptionCreateRequest(BaseModel):
    subscriber_name: str = Field(..., min_length=1, max_length=200)
    subscriber_type: str = Field(default="pms", pattern=r"^(pms|external_system|webhook)$")
    event_types: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    callback_url: str = Field(default="")
    secret_key: str = Field(default="")
    retry_policy: dict = Field(default_factory=dict)


class SubscriptionUpdateRequest(BaseModel):
    subscriber_name: str | None = Field(default=None, max_length=200)
    event_types: list[str] | None = None
    domains: list[str] | None = None
    callback_url: str | None = None
    retry_policy: dict | None = None


class SubscriptionReplayRequest(BaseModel):
    event_type: str = Field(default="")
    domain: str = Field(default="")


class GrayRolloutCreateRequest(BaseModel):
    domain: str = Field(..., min_length=1)
    scene: str = Field(default="default")
    rollout_percent: int = Field(default=0, ge=0, le=100)
    rollout_strategy: str = Field(default="random", pattern=r"^(random|user_list|org_list)$")
    target_user_list: list[str] = Field(default_factory=list)
    target_org_list: list[str] = Field(default_factory=list)
    auto_rollback_on_error_rate: float = Field(default=0.5, ge=0, le=1)
    auto_rollback_window_minutes: int = Field(default=30)
    monitoring_window_minutes: int = Field(default=60)
    min_sample_size: int = Field(default=10)


class GrayRolloutUpdatePercentRequest(BaseModel):
    rollout_percent: int = Field(..., ge=0, le=100)


class GrayRolloutRecordResultRequest(BaseModel):
    is_error: bool = Field(default=False)


class GrayRolloutManualRollbackRequest(BaseModel):
    reason: str = Field(default="")


class GrayRolloutCheckRequest(BaseModel):
    domain: str = Field(..., min_length=1)
    scene: str = Field(default="default")
    user_id: str = Field(default="")
    org_id: str = Field(default="")


# ── Feedback ──

@router.post("/feedback", response_model=None)
async def submit_feedback(req: FeedbackSubmitRequest, session: AsyncSession = Depends(get_db_session)):
    svc = PMSFeedbackService(session)
    record = await svc.submit_feedback(
        tenant_id=tenant_id_var.get(""), recommendation_id=req.recommendation_id,
        erp_reference_id=req.erp_reference_id, domain=req.domain,
        feedback_type=req.feedback_type, feedback_reason=req.feedback_reason,
        feedback_detail=req.feedback_detail, effect_metrics=req.effect_metrics,
        operator_id=req.operator_id, operator_type=req.operator_type,
    )
    return Result.ok(
        data={"id": record.id, "recommendation_id": record.recommendation_id,
              "feedback_type": record.feedback_type, "domain": record.domain,
              "trace_id": record.trace_id},
        trace_id=trace_id_var.get(""),
    )


@router.get("/feedback", response_model=None)
async def list_feedback(
    recommendation_id: str = Query(default=""),
    domain: str = Query(default=""),
    feedback_type: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = PMSFeedbackService(session)
    records, total = await svc.list_feedback(
        tenant_id_var.get(""), recommendation_id=recommendation_id,
        domain=domain, feedback_type=feedback_type,
        page=page, page_size=page_size,
    )
    data = [{
        "id": r.id, "recommendation_id": r.recommendation_id,
        "erp_reference_id": r.erp_reference_id, "domain": r.domain,
        "feedback_type": r.feedback_type, "feedback_reason": r.feedback_reason,
        "feedback_detail": json.loads(r.feedback_detail),
        "effect_metrics": json.loads(r.effect_metrics),
        "operator_id": r.operator_id, "operator_type": r.operator_type,
        "trace_id": r.trace_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in records]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/feedback/{feedback_id}/replay", response_model=None)
async def replay_feedback(feedback_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = PMSFeedbackService(session)
    record = await svc.replay_feedback(feedback_id, tenant_id_var.get(""))
    return Result.ok(
        data={
            "id": record.id,
            "recommendation_id": record.recommendation_id,
            "erp_reference_id": record.erp_reference_id,
            "feedback_type": record.feedback_type,
            "domain": record.domain,
            "replayed": True,
            "trace_id": trace_id_var.get(""),
        },
        trace_id=trace_id_var.get(""),
    )


# ── Event Subscriptions ──

@router.post("/subscriptions", response_model=None)
async def create_subscription(req: SubscriptionCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = PMSEventSubscriptionService(session)
    sub = await svc.create_subscription(
        tenant_id=tenant_id_var.get(""), subscriber_name=req.subscriber_name,
        subscriber_type=req.subscriber_type, event_types=req.event_types,
        domains=req.domains, callback_url=req.callback_url,
        secret_key=req.secret_key, retry_policy=req.retry_policy,
    )
    return Result.ok(
        data={"id": sub.id, "subscriber_name": sub.subscriber_name,
              "subscriber_type": sub.subscriber_type,
              "event_types": json.loads(sub.event_types),
              "domains": json.loads(sub.domains),
              "callback_url": sub.callback_url, "is_active": sub.is_active},
        trace_id=trace_id_var.get(""),
    )


@router.get("/subscriptions", response_model=None)
async def list_subscriptions(
    subscriber_type: str = Query(default=""),
    is_active: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    svc = PMSEventSubscriptionService(session)
    subs = await svc.list_subscriptions(
        tenant_id_var.get(""), subscriber_type=subscriber_type, is_active=is_active,
    )
    data = [{
        "id": s.id, "subscriber_name": s.subscriber_name,
        "subscriber_type": s.subscriber_type,
        "event_types": json.loads(s.event_types),
        "domains": json.loads(s.domains),
        "callback_url": s.callback_url, "is_active": s.is_active,
        "failure_count": s.failure_count,
        "last_event_at": s.last_event_at.isoformat() if s.last_event_at else None,
    } for s in subs]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.put("/subscriptions/{subscription_id}", response_model=None)
async def update_subscription(subscription_id: str, req: SubscriptionUpdateRequest,
                               session: AsyncSession = Depends(get_db_session)):
    svc = PMSEventSubscriptionService(session)
    sub = await svc.update_subscription(
        subscription_id, tenant_id_var.get(""),
        subscriber_name=req.subscriber_name, event_types=req.event_types,
        domains=req.domains, callback_url=req.callback_url,
        retry_policy=req.retry_policy,
    )
    return Result.ok(data={"id": sub.id, "subscriber_name": sub.subscriber_name}, trace_id=trace_id_var.get(""))


@router.put("/subscriptions/{subscription_id}/deactivate", response_model=None)
async def deactivate_subscription(subscription_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = PMSEventSubscriptionService(session)
    sub = await svc.deactivate_subscription(subscription_id, tenant_id_var.get(""))
    return Result.ok(data={"id": sub.id, "is_active": sub.is_active}, trace_id=trace_id_var.get(""))


@router.post("/subscriptions/{subscription_id}/replay", response_model=None)
async def replay_subscription_events(subscription_id: str, req: SubscriptionReplayRequest,
                                     session: AsyncSession = Depends(get_db_session)):
    svc = PMSEventSubscriptionService(session)
    events = await svc.replay_events(
        tenant_id_var.get(""), subscription_id,
        event_type=req.event_type, domain=req.domain,
    )
    return Result.ok(
        data={
            "subscription_id": subscription_id,
            "replayed_count": len(events),
            "events": [
                {
                    "event_id": e.get("event_id", ""),
                    "event_type": e.get("event_type", ""),
                    "domain": e.get("domain", ""),
                    "aggregate_id": e.get("aggregate_id", ""),
                }
                for e in events
            ],
        },
        trace_id=trace_id_var.get(""),
    )


# ── Gray Rollout ──

@router.post("/gray-rollout", response_model=None)
async def create_gray_rollout(req: GrayRolloutCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = GrayRolloutService(session)
    config = await svc.create_config(
        tenant_id=tenant_id_var.get(""), domain=req.domain, scene=req.scene,
        rollout_percent=req.rollout_percent, rollout_strategy=req.rollout_strategy,
        target_user_list=req.target_user_list, target_org_list=req.target_org_list,
        auto_rollback_on_error_rate=req.auto_rollback_on_error_rate,
        auto_rollback_window_minutes=req.auto_rollback_window_minutes,
        monitoring_window_minutes=req.monitoring_window_minutes,
        min_sample_size=req.min_sample_size,
    )
    return Result.ok(
        data={"id": config.id, "domain": config.domain, "scene": config.scene,
              "rollout_percent": config.rollout_percent,
              "rollout_strategy": config.rollout_strategy,
              "auto_rollback_on_error_rate": float(config.auto_rollback_on_error_rate)},
        trace_id=trace_id_var.get(""),
    )


@router.get("/gray-rollout", response_model=None)
async def list_gray_rollouts(domain: str = Query(default=""),
                              session: AsyncSession = Depends(get_db_session)):
    svc = GrayRolloutService(session)
    configs = await svc.list_configs(tenant_id_var.get(""), domain=domain)
    data = [{
        "id": c.id, "domain": c.domain, "scene": c.scene,
        "rollout_percent": c.rollout_percent, "rollout_strategy": c.rollout_strategy,
        "target_user_list": json.loads(c.target_user_list),
        "target_org_list": json.loads(c.target_org_list),
        "is_active": c.is_active,
        "auto_rollback_on_error_rate": float(c.auto_rollback_on_error_rate),
        "current_error_rate": float(c.current_error_rate),
        "current_sample_count": c.current_sample_count,
        "rolled_back_at": c.rolled_back_at.isoformat() if c.rolled_back_at else None,
        "rollback_reason": c.rollback_reason,
    } for c in configs]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.put("/gray-rollout/{config_id}/percent", response_model=None)
async def update_rollout_percent(config_id: str, req: GrayRolloutUpdatePercentRequest,
                                  session: AsyncSession = Depends(get_db_session)):
    svc = GrayRolloutService(session)
    config = await svc.update_rollout_percent(config_id, tenant_id_var.get(""), req.rollout_percent)
    return Result.ok(
        data={"id": config.id, "rollout_percent": config.rollout_percent},
        trace_id=trace_id_var.get(""),
    )


@router.post("/gray-rollout/check", response_model=None)
async def check_gray_rollout(req: GrayRolloutCheckRequest, session: AsyncSession = Depends(get_db_session)):
    svc = GrayRolloutService(session)
    should_execute = await svc.check_should_execute(
        tenant_id_var.get(""), req.domain, req.scene,
        user_id=req.user_id, org_id=req.org_id,
    )
    return Result.ok(
        data={"domain": req.domain, "scene": req.scene, "should_execute": should_execute},
        trace_id=trace_id_var.get(""),
    )


@router.post("/gray-rollout/{config_id}/record-result", response_model=None)
async def record_execution_result(config_id: str, req: GrayRolloutRecordResultRequest,
                                   session: AsyncSession = Depends(get_db_session)):
    svc = GrayRolloutService(session)
    config = await svc.record_execution_result(config_id, tenant_id_var.get(""), is_error=req.is_error)
    return Result.ok(
        data={"id": config.id, "current_error_rate": float(config.current_error_rate),
              "current_sample_count": config.current_sample_count,
              "rolled_back_at": config.rolled_back_at.isoformat() if config.rolled_back_at else None,
              "rollback_reason": config.rollback_reason},
        trace_id=trace_id_var.get(""),
    )


@router.post("/gray-rollout/{config_id}/rollback", response_model=None)
async def manual_rollback(config_id: str, req: GrayRolloutManualRollbackRequest,
                           session: AsyncSession = Depends(get_db_session)):
    svc = GrayRolloutService(session)
    config = await svc.manual_rollback(config_id, tenant_id_var.get(""), reason=req.reason)
    return Result.ok(
        data={"id": config.id, "rollout_percent": config.rollout_percent,
              "rolled_back_at": config.rolled_back_at.isoformat() if config.rolled_back_at else None,
              "rollback_reason": config.rollback_reason},
        trace_id=trace_id_var.get(""),
    )
