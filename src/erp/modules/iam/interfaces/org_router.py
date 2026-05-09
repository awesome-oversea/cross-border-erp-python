from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.iam.application.dtos import OrgCreateRequest, OrgMoveRequest, OrgUpdateRequest
from erp.modules.iam.application.services import OrganizationService
from erp.modules.iam.infrastructure.repositories import (
    SqlAuditLogRepository,
    SqlOrganizationRepository,
    SqlUserRepository,
)
from erp.modules.iam.interfaces.deps import get_current_user
from erp.shared.context import trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

router = APIRouter(prefix="/iam/v1/orgs", tags=["IAM-Organization"])


def _org_service(session: AsyncSession = Depends(get_db_session)) -> OrganizationService:
    return OrganizationService(SqlOrganizationRepository(session), SqlUserRepository(session), SqlAuditLogRepository(session))


@router.post("", response_model=None)
async def create_org(
    req: OrgCreateRequest,
    current: dict = Depends(get_current_user),
    svc: OrganizationService = Depends(_org_service),
):
    tid = current["tenant_id"]
    data = await svc.create(tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/tree", response_model=None)
async def list_org_tree(
    org_type: str = Query(default=""),
    current: dict = Depends(get_current_user),
    svc: OrganizationService = Depends(_org_service),
):
    tid = current["tenant_id"]
    items = await svc.list_tree(tid, org_type=org_type)
    return Result.ok(data=[i.model_dump() for i in items], trace_id=trace_id_var.get(""))


@router.get("/{org_id}", response_model=None)
async def get_org(
    org_id: str,
    current: dict = Depends(get_current_user),
    svc: OrganizationService = Depends(_org_service),
):
    tid = current["tenant_id"]
    data = await svc.get(org_id, tid)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/{org_id}/subtree", response_model=None)
async def get_org_subtree(
    org_id: str,
    current: dict = Depends(get_current_user),
    svc: OrganizationService = Depends(_org_service),
):
    tid = current["tenant_id"]
    items = await svc.get_subtree(org_id, tid)
    return Result.ok(data=[i.model_dump() for i in items], trace_id=trace_id_var.get(""))


@router.get("/{org_id}/members", response_model=None)
async def get_org_members(
    org_id: str,
    current: dict = Depends(get_current_user),
    svc: OrganizationService = Depends(_org_service),
):
    tid = current["tenant_id"]
    data = await svc.get_members(org_id, tid)
    return Result.ok(data=data.model_dump(), trace_id=trace_id_var.get(""))


@router.put("/{org_id}", response_model=None)
async def update_org(
    org_id: str,
    req: OrgUpdateRequest,
    current: dict = Depends(get_current_user),
    svc: OrganizationService = Depends(_org_service),
):
    tid = current["tenant_id"]
    data = await svc.update(org_id, tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.put("/{org_id}/move", response_model=None)
async def move_org(
    org_id: str,
    req: OrgMoveRequest,
    current: dict = Depends(get_current_user),
    svc: OrganizationService = Depends(_org_service),
):
    tid = current["tenant_id"]
    data = await svc.move(org_id, tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.delete("/{org_id}", response_model=None)
async def delete_org(
    org_id: str,
    current: dict = Depends(get_current_user),
    svc: OrganizationService = Depends(_org_service),
):
    tid = current["tenant_id"]
    await svc.delete(org_id, tid)
    return Result.ok(message="Organization deleted", trace_id=trace_id_var.get(""))
