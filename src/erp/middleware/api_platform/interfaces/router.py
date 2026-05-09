from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.api_platform.application.services import ApiPlatformService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/api-platform", tags=["API Platform - API管理平台"])


class RecordCallRequest(BaseModel):
    path: str = Field(min_length=1)
    method: str = Field(min_length=1, max_length=10)
    status_code: int = Field(default=200)
    response_time_ms: int = Field(default=0, ge=0)


class TestEndpointRequest(BaseModel):
    path: str = Field(min_length=1)
    method: str = Field(min_length=1, max_length=10)
    params: dict = Field(default_factory=dict)


@router.get("/endpoints", response_model=None)
async def list_endpoints(service: str = Query(default=""), version: str = Query(default=""),
                          method: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    svc = ApiPlatformService(session)
    result = await svc.list_endpoints(tenant_id_var.get(""), service, version, method)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/calls", response_model=None)
async def record_call(req: RecordCallRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ApiPlatformService(session)
    result = await svc.record_call(tenant_id_var.get(""), req.path, req.method, req.status_code, req.response_time_ms)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/stats", response_model=None)
async def get_stats(service: str = Query(default=""), path: str = Query(default=""),
                     hours: int = Query(default=24, ge=1, le=720),
                     session: AsyncSession = Depends(get_db_session)):
    svc = ApiPlatformService(session)
    result = await svc.get_stats(tenant_id_var.get(""), service, path, hours)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/versions", response_model=None)
async def list_versions(service: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    svc = ApiPlatformService(session)
    result = await svc.list_versions(tenant_id_var.get(""), service)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/test", response_model=None)
async def test_endpoint(req: TestEndpointRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ApiPlatformService(session)
    result = await svc.test_endpoint(tenant_id_var.get(""), req.path, req.method, req.params)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
