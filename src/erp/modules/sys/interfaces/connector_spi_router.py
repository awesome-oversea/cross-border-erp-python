from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.sys.domain.connector_spi_models import ConnectorRegistry, ConnectorSPIService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/connectors-spi", tags=["SYS-ConnectorSPI"])


class ConnectorCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=100)
    connector_type: str = Field(..., min_length=1, max_length=50)
    provider: str = Field(default="", max_length=100)
    base_url: str = Field(default="", max_length=500)
    auth_config: dict = Field(default_factory=dict)
    rate_limit: int = Field(default=100, ge=1)
    timeout: int = Field(default=30, ge=1, le=300)
    config: dict = Field(default_factory=dict)


class ConnectorUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    base_url: str | None = Field(default=None, max_length=500)
    auth_config: dict | None = Field(default=None)
    rate_limit: int | None = Field(default=None, ge=1)
    timeout: int | None = Field(default=None, ge=1, le=300)
    config: dict | None = Field(default=None)


@router.post("", response_model=None)
async def create_connector(req: ConnectorCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorSPIService(session)
    connector = await svc.create_connector(
        tenant_id=tenant_id_var.get(""), name=req.name, code=req.code,
        connector_type=req.connector_type, provider=req.provider,
        base_url=req.base_url, auth_config=req.auth_config,
        rate_limit=req.rate_limit, timeout=req.timeout, config=req.config,
    )
    return Result.ok(
        data={"id": connector.id, "name": connector.name, "code": connector.code,
              "connector_type": connector.connector_type, "status": connector.status},
        trace_id=trace_id_var.get(""),
    )


@router.get("", response_model=None)
async def list_connectors(
    connector_type: str = Query(default=""),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = ConnectorSPIService(session)
    connectors, total = await svc.list_connectors(
        tenant_id_var.get(""), connector_type=connector_type,
        is_active=is_active, page=page, page_size=page_size,
    )
    data = [{
        "id": c.id, "name": c.name, "code": c.code,
        "connector_type": c.connector_type, "provider": c.provider,
        "base_url": c.base_url, "status": c.status,
        "rate_limit": c.rate_limit, "timeout": c.timeout,
        "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
        "error_count": c.error_count, "is_active": c.is_active,
    } for c in connectors]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/types", response_model=None)
async def list_connector_types():
    types = ConnectorRegistry.list_types()
    return Result.ok(data=types, trace_id=trace_id_var.get(""))


@router.get("/{connector_id}", response_model=None)
async def get_connector(connector_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorSPIService(session)
    connectors, _ = await svc.list_connectors(tenant_id_var.get(""), page=1, page_size=1)
    connector = None
    for c in connectors:
        if c.id == connector_id:
            connector = c
            break
    if not connector:
        return Result.fail(code=404, message="Connector not found", trace_id=trace_id_var.get(""))
    return Result.ok(
        data={"id": connector.id, "name": connector.name, "code": connector.code,
              "connector_type": connector.connector_type, "provider": connector.provider,
              "base_url": connector.base_url, "auth_config": json.loads(connector.auth_config_json),
              "config": json.loads(connector.config_json),
              "status": connector.status, "rate_limit": connector.rate_limit,
              "timeout": connector.timeout, "is_active": connector.is_active},
        trace_id=trace_id_var.get(""),
    )


@router.put("/{connector_id}", response_model=None)
async def update_connector(connector_id: str, req: ConnectorUpdateRequest,
                            session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorSPIService(session)
    kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
    connector = await svc.update_connector(connector_id, tenant_id_var.get(""), **kwargs)
    return Result.ok(
        data={"id": connector.id, "name": connector.name, "code": connector.code},
        trace_id=trace_id_var.get(""),
    )


@router.post("/{connector_id}/activate", response_model=None)
async def activate_connector(connector_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorSPIService(session)
    connector = await svc.activate_connector(connector_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": connector.id, "status": connector.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/{connector_id}/deactivate", response_model=None)
async def deactivate_connector(connector_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorSPIService(session)
    connector = await svc.deactivate_connector(connector_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": connector.id, "status": connector.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/{connector_id}/health-check", response_model=None)
async def health_check_connector(connector_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorSPIService(session)
    result = await svc.health_check(connector_id, tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/call-logs", response_model=None)
async def list_call_logs(
    connector_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = ConnectorSPIService(session)
    logs, total = await svc.list_call_logs(
        tenant_id_var.get(""), connector_id=connector_id,
        page=page, page_size=page_size,
    )
    data = [{
        "id": log.id, "connector_id": log.connector_id, "connector_code": log.connector_code,
        "method": log.method, "path": log.path, "response_status": log.response_status,
        "is_success": log.is_success, "error_message": log.error_message,
        "duration_ms": log.duration_ms, "trace_id": log.trace_id,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    } for log in logs]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))
