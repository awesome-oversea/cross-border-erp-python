from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.notification_center.application.services import NotificationCenterService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/notification", tags=["Notification Center - 消息通知中心"])


class SendRequest(BaseModel):
    template_code: str = Field(min_length=1)
    recipient_id: str = Field(min_length=1)
    variables: dict = Field(default_factory=dict)
    channel: str = Field(default="", max_length=20)
    recipient_address: str = Field(default="")


class TemplateCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    title_template: str = Field(min_length=1)
    body_template: str = Field(min_length=1)
    channel: str = Field(default="in_app", max_length=20)


@router.post("/send", response_model=None)
async def send_notification(req: SendRequest, session: AsyncSession = Depends(get_db_session)):
    svc = NotificationCenterService(session)
    result = await svc.send(tenant_id_var.get(""), req.template_code, req.recipient_id,
                             req.variables, req.channel, req.recipient_address)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/templates", response_model=None)
async def get_templates(session: AsyncSession = Depends(get_db_session)):
    svc = NotificationCenterService(session)
    result = await svc.get_templates(tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/templates", response_model=None)
async def create_template(req: TemplateCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = NotificationCenterService(session)
    result = await svc.create_template(tenant_id_var.get(""), req.code, req.title_template, req.body_template, req.channel)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/history", response_model=None)
async def get_history(recipient_id: str = Query(default=""), channel: str = Query(default=""),
                       status: str = Query(default=""), limit: int = Query(default=50, ge=1, le=200),
                       session: AsyncSession = Depends(get_db_session)):
    svc = NotificationCenterService(session)
    result = await svc.get_history(tenant_id_var.get(""), recipient_id, channel, status, limit)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.put("/{message_id}/read", response_model=None)
async def mark_read(message_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = NotificationCenterService(session)
    result = await svc.mark_read(tenant_id_var.get(""), message_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
