"""
IAM域 - 对象级权限与数据权限路由

提供对象级权限(ObjectPermission)的授予/撤销/查询接口，
以及数据权限规则(DataPermissionRule)的CRUD接口。
路径前缀: /iam/v1
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.iam.application.dtos import (
    DataPermissionRuleCreateRequest,
    DataPermissionRuleUpdateRequest,
    ObjectPermissionGrantRequest,
)
from erp.modules.iam.application.services import DataPermissionService, ObjectPermissionService
from erp.modules.iam.infrastructure.repositories import (
    SqlAuditLogRepository,
    SqlDataPermissionRuleRepository,
    SqlObjectPermissionRepository,
)
from erp.modules.iam.interfaces.deps import get_current_user
from erp.shared.context import trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

router = APIRouter(tags=["IAM-PermissionExt"])


def _object_perm_service(session: AsyncSession = Depends(get_db_session)) -> ObjectPermissionService:
    return ObjectPermissionService(SqlObjectPermissionRepository(session), SqlAuditLogRepository(session))


def _data_perm_service(session: AsyncSession = Depends(get_db_session)) -> DataPermissionService:
    return DataPermissionService(SqlDataPermissionRuleRepository(session), SqlAuditLogRepository(session))


@router.post("/iam/v1/object-permissions", response_model=None, summary="授予对象级权限")
async def grant_object_permission(
    req: ObjectPermissionGrantRequest,
    current: dict = Depends(get_current_user),
    svc: ObjectPermissionService = Depends(_object_perm_service),
):
    tid = current["tenant_id"]
    data = await svc.grant(tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.delete("/iam/v1/object-permissions/{perm_id}", response_model=None, summary="撤销对象级权限")
async def revoke_object_permission(
    perm_id: str,
    current: dict = Depends(get_current_user),
    svc: ObjectPermissionService = Depends(_object_perm_service),
):
    tid = current["tenant_id"]
    await svc.revoke(perm_id, tid)
    return Result.ok(message="Object permission revoked", trace_id=trace_id_var.get(""))


@router.get("/iam/v1/object-permissions/by-subject", response_model=None, summary="按主体查询对象权限")
async def list_object_perms_by_subject(
    subject_type: str = Query(..., description="主体类型: user/role/position/org"),
    subject_id: str = Query(..., description="主体ID"),
    current: dict = Depends(get_current_user),
    svc: ObjectPermissionService = Depends(_object_perm_service),
):
    tid = current["tenant_id"]
    items = await svc.list_by_subject(subject_type, subject_id, tid)
    return Result.ok(data=[i.model_dump() for i in items], trace_id=trace_id_var.get(""))


@router.get("/iam/v1/object-permissions/by-resource", response_model=None, summary="按资源查询对象权限")
async def list_object_perms_by_resource(
    resource_type: str = Query(..., description="资源类型"),
    resource_id: str = Query(..., description="资源实例ID"),
    current: dict = Depends(get_current_user),
    svc: ObjectPermissionService = Depends(_object_perm_service),
):
    tid = current["tenant_id"]
    items = await svc.list_by_resource(resource_type, resource_id, tid)
    return Result.ok(data=[i.model_dump() for i in items], trace_id=trace_id_var.get(""))


@router.get("/iam/v1/object-permissions/check", response_model=None, summary="检查对象权限")
async def check_object_permission(
    subject_type: str = Query(..., description="主体类型"),
    subject_id: str = Query(..., description="主体ID"),
    resource_type: str = Query(..., description="资源类型"),
    resource_id: str = Query(..., description="资源实例ID"),
    action: str = Query(default="read", description="操作类型"),
    current: dict = Depends(get_current_user),
    svc: ObjectPermissionService = Depends(_object_perm_service),
):
    tid = current["tenant_id"]
    data = await svc.check_permission(subject_type, subject_id, resource_type, resource_id, action, tid)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/iam/v1/data-permission-rules", response_model=None, summary="创建数据权限规则")
async def create_data_permission_rule(
    req: DataPermissionRuleCreateRequest,
    current: dict = Depends(get_current_user),
    svc: DataPermissionService = Depends(_data_perm_service),
):
    tid = current["tenant_id"]
    data = await svc.create(tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.put("/iam/v1/data-permission-rules/{rule_id}", response_model=None, summary="更新数据权限规则")
async def update_data_permission_rule(
    rule_id: str,
    req: DataPermissionRuleUpdateRequest,
    current: dict = Depends(get_current_user),
    svc: DataPermissionService = Depends(_data_perm_service),
):
    tid = current["tenant_id"]
    data = await svc.update(rule_id, tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.delete("/iam/v1/data-permission-rules/{rule_id}", response_model=None, summary="删除数据权限规则")
async def delete_data_permission_rule(
    rule_id: str,
    current: dict = Depends(get_current_user),
    svc: DataPermissionService = Depends(_data_perm_service),
):
    tid = current["tenant_id"]
    await svc.delete(rule_id, tid)
    return Result.ok(message="Data permission rule deleted", trace_id=trace_id_var.get(""))


@router.get("/iam/v1/data-permission-rules/by-role", response_model=None, summary="按角色查询数据权限规则")
async def list_data_perm_rules_by_role(
    role_id: str = Query(..., description="角色ID"),
    current: dict = Depends(get_current_user),
    svc: DataPermissionService = Depends(_data_perm_service),
):
    tid = current["tenant_id"]
    items = await svc.list_by_role(role_id, tid)
    return Result.ok(data=[i.model_dump() for i in items], trace_id=trace_id_var.get(""))


@router.get("/iam/v1/data-permission-rules/by-user", response_model=None, summary="按用户查询数据权限规则")
async def list_data_perm_rules_by_user(
    user_id: str = Query(..., description="用户ID"),
    current: dict = Depends(get_current_user),
    svc: DataPermissionService = Depends(_data_perm_service),
):
    tid = current["tenant_id"]
    items = await svc.list_by_user(user_id, tid)
    return Result.ok(data=[i.model_dump() for i in items], trace_id=trace_id_var.get(""))


@router.get("/iam/v1/data-permission-rules/by-dimension", response_model=None, summary="按维度查询数据权限规则")
async def list_data_perm_rules_by_dimension(
    dimension: str = Query(..., description="维度: tenant/org/department/store/marketplace/channel/warehouse/supplier/category/data_level"),
    current: dict = Depends(get_current_user),
    svc: DataPermissionService = Depends(_data_perm_service),
):
    tid = current["tenant_id"]
    items = await svc.list_by_dimension(dimension, tid)
    return Result.ok(data=[i.model_dump() for i in items], trace_id=trace_id_var.get(""))
