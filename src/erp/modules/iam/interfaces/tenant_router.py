from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.iam.application.dtos import (
    TenantCreateRequest,
    TenantPlanUpgradeRequest,
    TenantStatusChangeRequest,
    TenantUpdateRequest,
)
from erp.modules.iam.application.services import TenantService
from erp.modules.iam.infrastructure.repositories import SqlAuditLogRepository, SqlTenantRepository, SqlUserRepository
from erp.shared.context import trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

router = APIRouter(prefix="/iam/v1/tenants", tags=["IAM-Tenant"])


def _tenant_service(session: AsyncSession = Depends(get_db_session)) -> TenantService:
    return TenantService(SqlTenantRepository(session), SqlUserRepository(session), SqlAuditLogRepository(session))


@router.post("", response_model=None)
async def create_tenant(
    req: TenantCreateRequest,
    svc: TenantService = Depends(_tenant_service),
):
    data = await svc.create(req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/{tenant_id}", response_model=None)
async def get_tenant(
    tenant_id: str,
    svc: TenantService = Depends(_tenant_service),
):
    data = await svc.get(tenant_id)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("", response_model=None)
async def list_tenants(
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: TenantService = Depends(_tenant_service),
):
    items, total = await svc.list_all(status=status, page=page, page_size=page_size)
    return Result.paginate(items=[i.model_dump() for i in items], total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.put("/{tenant_id}", response_model=None)
async def update_tenant(
    tenant_id: str,
    req: TenantUpdateRequest,
    svc: TenantService = Depends(_tenant_service),
):
    data = await svc.update(tenant_id, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.delete("/{tenant_id}", response_model=None)
async def delete_tenant(
    tenant_id: str,
    svc: TenantService = Depends(_tenant_service),
):
    await svc.delete(tenant_id)
    return Result.ok(message="Tenant deleted", trace_id=trace_id_var.get(""))


@router.put("/{tenant_id}/status", response_model=None)
async def change_tenant_status(
    tenant_id: str,
    req: TenantStatusChangeRequest,
    svc: TenantService = Depends(_tenant_service),
):
    data = await svc.change_status(tenant_id, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.put("/{tenant_id}/plan", response_model=None)
async def upgrade_tenant_plan(
    tenant_id: str,
    req: TenantPlanUpgradeRequest,
    svc: TenantService = Depends(_tenant_service),
):
    data = await svc.upgrade_plan(tenant_id, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/{tenant_id}/quota", response_model=None)
async def get_tenant_quota(
    tenant_id: str,
    svc: TenantService = Depends(_tenant_service),
):
    data = await svc.get_quota(tenant_id)
    return Result.ok(data=data.model_dump(), trace_id=trace_id_var.get(""))
