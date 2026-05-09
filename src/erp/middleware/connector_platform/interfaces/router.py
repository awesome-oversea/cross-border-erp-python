from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.connector_platform.application.services import ConnectorPlatformService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/connector", tags=["Connector Platform - 连接器管理平台"])


class RegisterRequest(BaseModel):
    connector_type: str = Field(min_length=1, max_length=32)
    connector_name: str = Field(min_length=1, max_length=128)
    platform: str = Field(min_length=1, max_length=32)
    version: str = Field(default="1.0.0", max_length=16)
    config: dict = Field(default_factory=dict)


@router.get("/platforms", response_model=None)
async def list_connectors(connector_type: str = Query(default=""), platform: str = Query(default=""),
                           session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorPlatformService(session)
    result = await svc.list_connectors(tenant_id_var.get(""), connector_type, platform)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/platforms/{connector_type}/register", response_model=None)
async def register_connector(connector_type: str, req: RegisterRequest,
                              session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorPlatformService(session)
    result = await svc.register_connector(tenant_id_var.get(""), req.connector_type, req.connector_name,
                                           req.platform, req.version, req.config)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/health", response_model=None)
async def health_check(connector_id: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorPlatformService(session)
    result = await svc.health_check(tenant_id_var.get(""), connector_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/stats", response_model=None)
async def get_stats(connector_id: str = Query(default=""), hours: int = Query(default=24, ge=1, le=720),
                     session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorPlatformService(session)
    result = await svc.get_stats(tenant_id_var.get(""), connector_id, hours)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
