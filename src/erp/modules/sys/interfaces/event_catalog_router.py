from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.sys.domain.event_catalog_models import BusinessEventCatalogService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/event-catalog", tags=["SYS-EventCatalog"])


class EventRegisterRequest(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=200)
    event_name: str = Field(..., min_length=1, max_length=200)
    domain: str = Field(..., min_length=1, max_length=50)
    aggregate_type: str = Field(..., min_length=1, max_length=100)
    aggregate_action: str = Field(default="created")
    event_version: str = Field(default="v1")
    description: str = Field(default="")
    payload_schema: dict = Field(default_factory=dict)
    consumer_domains: list[str] = Field(default_factory=list)


class EventSubscribeRequest(BaseModel):
    event_type: str = Field(..., min_length=1)
    subscriber_domain: str = Field(..., min_length=1)
    subscriber_name: str = Field(..., min_length=1)
    callback_type: str = Field(default="async", pattern=r"^(sync|async|webhook)$")
    callback_endpoint: str = Field(default="")


@router.post("/events", response_model=None)
async def register_event(req: EventRegisterRequest, session: AsyncSession = Depends(get_db_session)):
    svc = BusinessEventCatalogService(session)
    catalog = await svc.register_event(
        event_type=req.event_type, event_name=req.event_name,
        domain=req.domain, aggregate_type=req.aggregate_type,
        aggregate_action=req.aggregate_action, event_version=req.event_version,
        description=req.description, payload_schema=req.payload_schema,
        consumer_domains=req.consumer_domains,
    )
    return Result.ok(
        data={"id": catalog.id, "event_type": catalog.event_type,
              "event_name": catalog.event_name, "domain": catalog.domain,
              "aggregate_type": catalog.aggregate_type},
        trace_id=trace_id_var.get(""),
    )


@router.get("/events", response_model=None)
async def list_events(domain: str = Query(default=""),
                       is_active: bool | None = Query(default=None),
                       session: AsyncSession = Depends(get_db_session)):
    svc = BusinessEventCatalogService(session)
    events = await svc.list_events(domain=domain, is_active=is_active)
    data = [{
        "id": e.id, "event_type": e.event_type, "event_name": e.event_name,
        "domain": e.domain, "aggregate_type": e.aggregate_type,
        "aggregate_action": e.aggregate_action, "event_version": e.event_version,
        "description": e.description,
        "payload_schema": json.loads(e.payload_schema_json),
        "consumer_domains": json.loads(e.consumer_domains),
        "is_active": e.is_active,
    } for e in events]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/subscriptions", response_model=None)
async def subscribe_event(req: EventSubscribeRequest, session: AsyncSession = Depends(get_db_session)):
    svc = BusinessEventCatalogService(session)
    sub = await svc.subscribe_event(
        tenant_id=tenant_id_var.get(""), event_type=req.event_type,
        subscriber_domain=req.subscriber_domain, subscriber_name=req.subscriber_name,
        callback_type=req.callback_type, callback_endpoint=req.callback_endpoint,
    )
    return Result.ok(
        data={"id": sub.id, "event_type": sub.event_type,
              "subscriber_domain": sub.subscriber_domain,
              "subscriber_name": sub.subscriber_name},
        trace_id=trace_id_var.get(""),
    )


@router.get("/subscriptions", response_model=None)
async def list_subscriptions(event_type: str = Query(default=""),
                              subscriber_domain: str = Query(default=""),
                              session: AsyncSession = Depends(get_db_session)):
    svc = BusinessEventCatalogService(session)
    subs = await svc.list_subscriptions(
        tenant_id_var.get(""), event_type=event_type,
        subscriber_domain=subscriber_domain,
    )
    data = [{
        "id": s.id, "event_type": s.event_type,
        "subscriber_domain": s.subscriber_domain,
        "subscriber_name": s.subscriber_name,
        "callback_type": s.callback_type,
        "callback_endpoint": s.callback_endpoint,
        "is_active": s.is_active,
    } for s in subs]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/init-defaults", response_model=None)
async def init_default_events(session: AsyncSession = Depends(get_db_session)):
    svc = BusinessEventCatalogService(session)
    await svc.init_defaults()
    return Result.ok(data={"message": "Default business event catalog initialized"}, trace_id=trace_id_var.get(""))
