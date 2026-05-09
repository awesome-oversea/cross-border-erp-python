from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.iam.application.dtos import (
    AssignPermissionRequest,
    PermissionCreateRequest,
    PermissionUpdateRequest,
    RoleCreateRequest,
    RoleUpdateRequest,
)
from erp.modules.iam.application.services import PermissionService, RoleService
from erp.modules.iam.infrastructure.repositories import (
    SqlAuditLogRepository,
    SqlPermissionRepository,
    SqlRolePermissionRepository,
    SqlRoleRepository,
)
from erp.modules.iam.interfaces.deps import get_current_user
from erp.shared.context import trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

router = APIRouter(prefix="/iam/v1/roles", tags=["IAM-Role"])


def _role_service(session: AsyncSession = Depends(get_db_session)) -> RoleService:
    return RoleService(
        SqlRoleRepository(session), SqlRolePermissionRepository(session),
        SqlPermissionRepository(session), SqlAuditLogRepository(session),
    )


def _perm_service(session: AsyncSession = Depends(get_db_session)) -> PermissionService:
    return PermissionService(SqlPermissionRepository(session))


@router.post("", response_model=None)
async def create_role(
    req: RoleCreateRequest,
    current: dict = Depends(get_current_user),
    svc: RoleService = Depends(_role_service),
):
    tid = current["tenant_id"]
    data = await svc.create(tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("", response_model=None)
async def list_roles(
    status: str = Query(default=""),
    current: dict = Depends(get_current_user),
    svc: RoleService = Depends(_role_service),
):
    tid = current["tenant_id"]
    items = await svc.list_roles(tid, status=status)
    return Result.ok(data=[i.model_dump() for i in items], trace_id=trace_id_var.get(""))


@router.get("/{role_id}", response_model=None)
async def get_role(
    role_id: str,
    current: dict = Depends(get_current_user),
    svc: RoleService = Depends(_role_service),
):
    tid = current["tenant_id"]
    data = await svc.get(role_id, tid)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/{role_id}/permissions", response_model=None)
async def get_role_permissions(
    role_id: str,
    current: dict = Depends(get_current_user),
    svc: RoleService = Depends(_role_service),
):
    tid = current["tenant_id"]
    data = await svc.get_permissions_detail(role_id, tid)
    return Result.ok(data=data.model_dump(), trace_id=trace_id_var.get(""))


@router.put("/{role_id}", response_model=None)
async def update_role(
    role_id: str,
    req: RoleUpdateRequest,
    current: dict = Depends(get_current_user),
    svc: RoleService = Depends(_role_service),
):
    tid = current["tenant_id"]
    data = await svc.update(role_id, tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.delete("/{role_id}", response_model=None)
async def delete_role(
    role_id: str,
    current: dict = Depends(get_current_user),
    svc: RoleService = Depends(_role_service),
):
    tid = current["tenant_id"]
    await svc.delete(role_id, tid)
    return Result.ok(message="Role deleted", trace_id=trace_id_var.get(""))


@router.post("/{role_id}/permissions", response_model=None)
async def assign_permissions(
    role_id: str,
    req: AssignPermissionRequest,
    current: dict = Depends(get_current_user),
    svc: RoleService = Depends(_role_service),
):
    tid = current["tenant_id"]
    await svc.assign_permissions(role_id, tid, req)
    return Result.ok(message="Permissions assigned", trace_id=trace_id_var.get(""))


@router.delete("/{role_id}/permissions", response_model=None)
async def revoke_permissions(
    role_id: str,
    req: AssignPermissionRequest,
    current: dict = Depends(get_current_user),
    svc: RoleService = Depends(_role_service),
):
    tid = current["tenant_id"]
    await svc.revoke_permissions(role_id, tid, req)
    return Result.ok(message="Permissions revoked", trace_id=trace_id_var.get(""))


@router.post("/permissions", response_model=None)
async def create_permission(
    req: PermissionCreateRequest,
    current: dict = Depends(get_current_user),
    svc: PermissionService = Depends(_perm_service),
):
    data = await svc.create(req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/permissions/all", response_model=None)
async def list_permissions(
    perm_type: str = Query(default=""),
    current: dict = Depends(get_current_user),
    svc: PermissionService = Depends(_perm_service),
):
    items = await svc.list_all(perm_type=perm_type)
    return Result.ok(data=[i.model_dump() for i in items], trace_id=trace_id_var.get(""))


@router.get("/permissions/tree", response_model=None)
async def get_permissions_tree(
    perm_type: str = Query(default=""),
    current: dict = Depends(get_current_user),
    svc: PermissionService = Depends(_perm_service),
):
    tree = await svc.get_tree(perm_type=perm_type)
    return Result.ok(data=tree, trace_id=trace_id_var.get(""))


@router.put("/permissions/{perm_id}", response_model=None)
async def update_permission(
    perm_id: str,
    req: PermissionUpdateRequest,
    current: dict = Depends(get_current_user),
    svc: PermissionService = Depends(_perm_service),
):
    data = await svc.update(perm_id, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.delete("/permissions/{perm_id}", response_model=None)
async def delete_permission(
    perm_id: str,
    current: dict = Depends(get_current_user),
    svc: PermissionService = Depends(_perm_service),
):
    await svc.delete(perm_id)
    return Result.ok(message="Permission deleted", trace_id=trace_id_var.get(""))
