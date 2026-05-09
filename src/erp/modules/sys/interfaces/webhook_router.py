from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.sys.domain.webhook_models import WebhookService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/webhooks", tags=["SYS-Webhook"])


class WebhookCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    event_types: list[str] = Field(..., min_length=1)
    callback_url: str = Field(..., min_length=1, max_length=500)
    secret: str = Field(default="", max_length=200)
    http_method: str = Field(default="POST", pattern=r"^(POST|PUT|PATCH)$")
    headers: dict = Field(default_factory=dict)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_interval_seconds: int = Field(default=60, ge=10, le=3600)
    timeout_seconds: int = Field(default=30, ge=5, le=120)


class WebhookUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    event_types: list[str] | None = Field(default=None)
    callback_url: str | None = Field(default=None, max_length=500)
    secret: str | None = Field(default=None, max_length=200)
    headers: dict | None = Field(default=None)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    retry_interval_seconds: int | None = Field(default=None, ge=10, le=3600)
    timeout_seconds: int | None = Field(default=None, ge=5, le=120)
    status: str | None = Field(default=None, pattern=r"^(active|inactive)$")


class WebhookTriggerRequest(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=200)
    payload: dict = Field(default_factory=dict)


@router.post("/subscriptions", response_model=None)
async def create_subscription(req: WebhookCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = WebhookService(session)
    sub = await svc.create_subscription(
        tenant_id=tenant_id_var.get(""), name=req.name, event_types=req.event_types,
        callback_url=req.callback_url, secret=req.secret,
        http_method=req.http_method, headers=req.headers,
        max_retries=req.max_retries, retry_interval_seconds=req.retry_interval_seconds,
        timeout_seconds=req.timeout_seconds,
    )
    return Result.ok(
        data={"id": sub.id, "name": sub.name, "callback_url": sub.callback_url,
              "event_types": json.loads(sub.event_types), "status": sub.status},
        trace_id=trace_id_var.get(""),
    )


@router.get("/subscriptions", response_model=None)
async def list_subscriptions(status: str = Query(default=""),
                              session: AsyncSession = Depends(get_db_session)):
    svc = WebhookService(session)
    subs = await svc.list_subscriptions(tenant_id_var.get(""), status=status)
    data = [{
        "id": s.id, "name": s.name, "callback_url": s.callback_url,
        "event_types": json.loads(s.event_types), "http_method": s.http_method,
        "status": s.status, "max_retries": s.max_retries,
        "consecutive_failures": s.consecutive_failures,
        "last_triggered_at": s.last_triggered_at.isoformat() if s.last_triggered_at else None,
        "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None,
        "last_error": s.last_error,
    } for s in subs]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.put("/subscriptions/{subscription_id}", response_model=None)
async def update_subscription(subscription_id: str, req: WebhookUpdateRequest,
                               session: AsyncSession = Depends(get_db_session)):
    svc = WebhookService(session)
    kwargs = {}
    for k, v in req.model_dump().items():
        if v is not None:
            kwargs[k] = v
    sub = await svc.update_subscription(subscription_id, tenant_id_var.get(""), **kwargs)
    return Result.ok(
        data={"id": sub.id, "name": sub.name, "status": sub.status},
        trace_id=trace_id_var.get(""),
    )


@router.delete("/subscriptions/{subscription_id}", response_model=None)
async def delete_subscription(subscription_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = WebhookService(session)
    await svc.delete_subscription(subscription_id, tenant_id_var.get(""))
    return Result.ok(data=None, trace_id=trace_id_var.get(""))


@router.post("/trigger", response_model=None)
async def trigger_event(req: WebhookTriggerRequest, session: AsyncSession = Depends(get_db_session)):
    svc = WebhookService(session)
    deliveries = await svc.trigger_event(
        tenant_id=tenant_id_var.get(""), event_type=req.event_type, payload=req.payload,
    )
    return Result.ok(
        data={"deliveries_created": len(deliveries),
              "delivery_ids": [d.id for d in deliveries]},
        trace_id=trace_id_var.get(""),
    )


@router.get("/deliveries", response_model=None)
async def list_deliveries(
    subscription_id: str = Query(default=""),
    event_type: str = Query(default=""),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = WebhookService(session)
    deliveries, total = await svc.list_deliveries(
        tenant_id_var.get(""), subscription_id=subscription_id,
        event_type=event_type, status=status,
        page=page, page_size=page_size,
    )
    data = [{
        "id": d.id, "subscription_id": d.subscription_id,
        "event_type": d.event_type, "status": d.status,
        "attempt_count": d.attempt_count, "max_attempts": d.max_attempts,
        "last_response_status": d.last_response_status,
        "last_error": d.last_error,
        "next_retry_at": d.next_retry_at.isoformat() if d.next_retry_at else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    } for d in deliveries]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/deliveries/{delivery_id}/retry", response_model=None)
async def retry_delivery(delivery_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = WebhookService(session)
    delivery = await svc.retry_delivery(delivery_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": delivery.id, "status": delivery.status,
              "attempt_count": delivery.attempt_count},
        trace_id=trace_id_var.get(""),
    )


@router.post("/deliveries/{delivery_id}/success", response_model=None)
async def mark_delivery_success(delivery_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = WebhookService(session)
    delivery = await svc.mark_delivery_success(delivery_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": delivery.id, "status": delivery.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/deliveries/{delivery_id}/fail", response_model=None)
async def mark_delivery_failed(delivery_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = WebhookService(session)
    delivery = await svc.mark_delivery_failed(delivery_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": delivery.id, "status": delivery.status,
              "attempt_count": delivery.attempt_count},
        trace_id=trace_id_var.get(""),
    )


@router.get("/pending-retries", response_model=None)
async def get_pending_retries(session: AsyncSession = Depends(get_db_session)):
    svc = WebhookService(session)
    deliveries = await svc.get_pending_retries(tenant_id_var.get(""))
    data = [{
        "id": d.id, "subscription_id": d.subscription_id,
        "event_type": d.event_type, "attempt_count": d.attempt_count,
        "next_retry_at": d.next_retry_at.isoformat() if d.next_retry_at else None,
    } for d in deliveries]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))
