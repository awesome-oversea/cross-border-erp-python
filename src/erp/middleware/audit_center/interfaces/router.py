from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.audit_center.application.services import AuditCenterService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/audit", tags=["Audit Center - 日志审计中心"])


class AuditLogRequest(BaseModel):
    action: str = Field(min_length=1, max_length=100)
    resource_type: str = Field(min_length=1, max_length=100)
    resource_id: str = Field(default="")
    resource_name: str = Field(default="")
    domain: str = Field(default="")
    actor_id: str = Field(default="")
    actor_type: str = Field(default="user")
    actor_name: str = Field(default="")
    before: dict = Field(default_factory=dict)
    after: dict = Field(default_factory=dict)
    ip_address: str = Field(default="")
    user_agent: str = Field(default="")
    request_path: str = Field(default="")
    request_method: str = Field(default="")
    status: str = Field(default="success")
    error_message: str = Field(default="")


@router.post("/log", response_model=None)
async def log_audit(req: AuditLogRequest, session: AsyncSession = Depends(get_db_session)):
    svc = AuditCenterService(session)
    result = await svc.log(tenant_id_var.get(""), req.action, req.resource_type, req.resource_id,
                            req.resource_name, req.domain, req.actor_id, req.actor_type, req.actor_name,
                            req.before, req.after, req.ip_address, req.user_agent,
                            req.request_path, req.request_method, req.status, req.error_message,
                            trace_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/logs", response_model=None)
async def query_logs(domain: str = Query(default=""), action: str = Query(default=""),
                      actor_id: str = Query(default=""), resource_type: str = Query(default=""),
                      resource_id: str = Query(default=""), start_date: str = Query(default=""),
                      end_date: str = Query(default=""), status: str = Query(default=""),
                      limit: int = Query(default=50, ge=1, le=200),
                      offset: int = Query(default=0, ge=0),
                      session: AsyncSession = Depends(get_db_session)):
    svc = AuditCenterService(session)
    result = await svc.query(tenant_id_var.get(""), domain, action, actor_id, resource_type,
                              resource_id, start_date, end_date, status, limit, offset)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/export", response_model=None)
async def export_logs(domain: str = Query(default=""), start_date: str = Query(default=""),
                       end_date: str = Query(default=""), output_format: str = Query(default="json"),
                       session: AsyncSession = Depends(get_db_session)):
    svc = AuditCenterService(session)
    result = await svc.export(tenant_id_var.get(""), domain, start_date, end_date, output_format)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
