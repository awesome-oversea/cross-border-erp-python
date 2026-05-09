from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.iam.application.dtos import (
    AdminResetPasswordRequest,
    AssignRoleRequest,
    BatchUserStatusRequest,
    PasswordChangeRequest,
    UserCreateRequest,
    UserPermissionsResponse,
    UserStatusChangeRequest,
    UserUpdateRequest,
)
from erp.modules.iam.application.services import UserService
from erp.modules.iam.infrastructure.repositories import (
    SqlAuditLogRepository,
    SqlPermissionRepository,
    SqlRolePermissionRepository,
    SqlRoleRepository,
    SqlUserRepository,
    SqlUserRoleRepository,
)
from erp.modules.iam.interfaces.deps import get_current_user
from erp.shared.context import trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

router = APIRouter(prefix="/iam/v1/users", tags=["IAM-User"])


def _user_service(session: AsyncSession = Depends(get_db_session)) -> UserService:
    return UserService(
        SqlUserRepository(session),
        SqlUserRoleRepository(session),
        SqlPermissionRepository(session),
        SqlRolePermissionRepository(session),
        SqlRoleRepository(session),
        SqlAuditLogRepository(session),
    )


@router.post("", response_model=None)
async def create_user(
    req: UserCreateRequest,
    current: dict = Depends(get_current_user),
    svc: UserService = Depends(_user_service),
):
    tid = current["tenant_id"]
    data = await svc.create(tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("", response_model=None)
async def list_users(
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current: dict = Depends(get_current_user),
    svc: UserService = Depends(_user_service),
):
    tid = current["tenant_id"]
    items, total = await svc.list_users(tid, status=status, page=page, page_size=page_size)
    return Result.paginate(
        items=[i.model_dump() for i in items], total=total, page=page, page_size=page_size, trace_id=trace_id_var.get("")
    )


@router.get("/me", response_model=None)
async def get_current_user_info(
    current: dict = Depends(get_current_user),
    svc: UserService = Depends(_user_service),
):
    tid = current["tenant_id"]
    data = await svc.get(current["user_id"], tid)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/{user_id}", response_model=None)
async def get_user(
    user_id: str,
    current: dict = Depends(get_current_user),
    svc: UserService = Depends(_user_service),
):
    tid = current["tenant_id"]
    data = await svc.get(user_id, tid)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.put("/{user_id}", response_model=None)
async def update_user(
    user_id: str,
    req: UserUpdateRequest,
    current: dict = Depends(get_current_user),
    svc: UserService = Depends(_user_service),
):
    tid = current["tenant_id"]
    data = await svc.update(user_id, tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.delete("/{user_id}", response_model=None)
async def delete_user(
    user_id: str,
    current: dict = Depends(get_current_user),
    svc: UserService = Depends(_user_service),
):
    tid = current["tenant_id"]
    await svc.delete(user_id, tid)
    return Result.ok(message="User deleted", trace_id=trace_id_var.get(""))


@router.put("/{user_id}/password", response_model=None)
async def change_password(
    user_id: str,
    req: PasswordChangeRequest,
    current: dict = Depends(get_current_user),
    svc: UserService = Depends(_user_service),
):
    tid = current["tenant_id"]
    await svc.change_password(user_id, tid, req)
    return Result.ok(message="Password changed", trace_id=trace_id_var.get(""))


@router.put("/{user_id}/admin-reset-password", response_model=None)
async def admin_reset_password(
    user_id: str,
    req: AdminResetPasswordRequest,
    current: dict = Depends(get_current_user),
    svc: UserService = Depends(_user_service),
):
    tid = current["tenant_id"]
    await svc.admin_reset_password(user_id, tid, req)
    return Result.ok(message="Password reset by admin", trace_id=trace_id_var.get(""))


@router.put("/{user_id}/status", response_model=None)
async def change_user_status(
    user_id: str,
    req: UserStatusChangeRequest,
    current: dict = Depends(get_current_user),
    svc: UserService = Depends(_user_service),
):
    tid = current["tenant_id"]
    data = await svc.change_status(user_id, tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.put("/{user_id}/unlock", response_model=None)
async def unlock_user(
    user_id: str,
    current: dict = Depends(get_current_user),
    svc: UserService = Depends(_user_service),
):
    tid = current["tenant_id"]
    data = await svc.unlock(user_id, tid)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/batch/status", response_model=None)
async def batch_change_status(
    req: BatchUserStatusRequest,
    current: dict = Depends(get_current_user),
    svc: UserService = Depends(_user_service),
):
    tid = current["tenant_id"]
    count = await svc.batch_change_status(tid, req)
    return Result.ok(data={"updated_count": count}, trace_id=trace_id_var.get(""))


@router.get("/{user_id}/permissions", response_model=None)
async def get_user_permissions(
    user_id: str,
    current: dict = Depends(get_current_user),
    svc: UserService = Depends(_user_service),
):
    tid = current["tenant_id"]
    data = await svc.get_user_permissions(user_id, tid)
    return Result.ok(data=data.model_dump(), trace_id=trace_id_var.get(""))


@router.post("/{user_id}/roles", response_model=None)
async def assign_roles(
    user_id: str,
    req: AssignRoleRequest,
    current: dict = Depends(get_current_user),
    svc: UserService = Depends(_user_service),
):
    tid = current["tenant_id"]
    await svc.assign_roles(user_id, tid, req)
    return Result.ok(message="Roles assigned", trace_id=trace_id_var.get(""))


@router.delete("/{user_id}/roles", response_model=None)
async def revoke_roles(
    user_id: str,
    req: AssignRoleRequest,
    current: dict = Depends(get_current_user),
    svc: UserService = Depends(_user_service),
):
    tid = current["tenant_id"]
    await svc.revoke_roles(user_id, tid, req)
    return Result.ok(message="Roles revoked", trace_id=trace_id_var.get(""))
