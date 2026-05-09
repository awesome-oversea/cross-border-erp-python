from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.auth_center.application.services import AuthCenterService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/iam/v1/auth", tags=["Auth Center - 权限管理中心"])


class RefreshCacheRequest(BaseModel):
    user_id: str = Field(min_length=1)
    role_codes: list[str]
    data_scopes: dict = Field(default_factory=dict)


@router.get("/check", response_model=None)
async def check_permission(user_id: str = Query(...), permission_code: str = Query(...),
                            session: AsyncSession = Depends(get_db_session)):
    svc = AuthCenterService(session)
    result = await svc.check_permission(tenant_id_var.get(""), user_id, permission_code)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/permissions/{user_id}", response_model=None)
async def get_user_permissions(user_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = AuthCenterService(session)
    result = await svc.get_user_permissions(tenant_id_var.get(""), user_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/refresh", response_model=None)
async def refresh_cache(req: RefreshCacheRequest, session: AsyncSession = Depends(get_db_session)):
    svc = AuthCenterService(session)
    result = await svc.refresh_cache(tenant_id_var.get(""), req.user_id, req.role_codes, req.data_scopes)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/permissions", response_model=None)
async def list_permissions(module: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    svc = AuthCenterService(session)
    result = await svc.list_permissions(tenant_id_var.get(""), module)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/roles", response_model=None)
async def list_roles(session: AsyncSession = Depends(get_db_session)):
    svc = AuthCenterService(session)
    result = await svc.list_roles(tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
