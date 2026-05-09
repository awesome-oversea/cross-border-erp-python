"""
IAM域 - 岗位管理路由

提供岗位的CRUD接口、用户岗位分配/撤销、主岗设置等API。
路径前缀: /iam/v1/positions
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.iam.application.dtos import (
    PositionCreateRequest,
    PositionUpdateRequest,
    UserPositionAssignRequest,
)
from erp.modules.iam.application.services import PositionService
from erp.modules.iam.infrastructure.repositories import (
    SqlAuditLogRepository,
    SqlPositionRepository,
    SqlUserPositionRepository,
)
from erp.modules.iam.interfaces.deps import get_current_user
from erp.shared.context import trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

router = APIRouter(prefix="/iam/v1/positions", tags=["IAM-Position"])


def _position_service(session: AsyncSession = Depends(get_db_session)) -> PositionService:
    return PositionService(
        SqlPositionRepository(session),
        SqlUserPositionRepository(session),
        SqlAuditLogRepository(session),
    )


@router.post("", response_model=None, summary="创建岗位")
async def create_position(
    req: PositionCreateRequest,
    current: dict = Depends(get_current_user),
    svc: PositionService = Depends(_position_service),
):
    tid = current["tenant_id"]
    data = await svc.create(tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("", response_model=None, summary="查询岗位列表")
async def list_positions(
    org_id: str = Query(default="", description="按组织ID过滤"),
    status: str = Query(default="", description="按状态过滤"),
    current: dict = Depends(get_current_user),
    svc: PositionService = Depends(_position_service),
):
    tid = current["tenant_id"]
    if org_id:
        items = await svc.list_by_org(org_id, tid)
    else:
        items = await svc.list_by_tenant(tid, status=status)
    return Result.ok(data=[i.model_dump() for i in items], trace_id=trace_id_var.get(""))


@router.get("/{position_id}", response_model=None, summary="查询岗位详情")
async def get_position(
    position_id: str,
    current: dict = Depends(get_current_user),
    svc: PositionService = Depends(_position_service),
):
    tid = current["tenant_id"]
    data = await svc.get(position_id, tid)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.put("/{position_id}", response_model=None, summary="更新岗位")
async def update_position(
    position_id: str,
    req: PositionUpdateRequest,
    current: dict = Depends(get_current_user),
    svc: PositionService = Depends(_position_service),
):
    tid = current["tenant_id"]
    data = await svc.update(position_id, tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.delete("/{position_id}", response_model=None, summary="删除岗位")
async def delete_position(
    position_id: str,
    current: dict = Depends(get_current_user),
    svc: PositionService = Depends(_position_service),
):
    tid = current["tenant_id"]
    await svc.delete(position_id, tid)
    return Result.ok(message="Position deleted", trace_id=trace_id_var.get(""))


@router.post("/{position_id}/assign-user/{user_id}", response_model=None, summary="分配用户到岗位")
async def assign_user_to_position(
    position_id: str,
    user_id: str,
    req: UserPositionAssignRequest,
    current: dict = Depends(get_current_user),
    svc: PositionService = Depends(_position_service),
):
    tid = current["tenant_id"]
    req.position_id = position_id
    data = await svc.assign_user(user_id, tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.delete("/{position_id}/revoke-user/{user_id}", response_model=None, summary="撤销用户岗位")
async def revoke_user_from_position(
    position_id: str,
    user_id: str,
    current: dict = Depends(get_current_user),
    svc: PositionService = Depends(_position_service),
):
    tid = current["tenant_id"]
    await svc.revoke_user(user_id, position_id, tid)
    return Result.ok(message="User position revoked", trace_id=trace_id_var.get(""))


@router.put("/{position_id}/set-primary/{user_id}", response_model=None, summary="设置主岗")
async def set_primary_position(
    position_id: str,
    user_id: str,
    current: dict = Depends(get_current_user),
    svc: PositionService = Depends(_position_service),
):
    tid = current["tenant_id"]
    await svc.set_primary(user_id, position_id, tid)
    return Result.ok(message="Primary position set", trace_id=trace_id_var.get(""))


@router.get("/user/{user_id}/positions", response_model=None, summary="查询用户岗位列表")
async def get_user_positions(
    user_id: str,
    current: dict = Depends(get_current_user),
    svc: PositionService = Depends(_position_service),
):
    tid = current["tenant_id"]
    items = await svc.get_user_positions(user_id, tid)
    return Result.ok(data=[i.model_dump() for i in items], trace_id=trace_id_var.get(""))
