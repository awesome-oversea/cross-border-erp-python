from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.sys.domain.pms_data_query_models import PMSDataQueryService
from erp.shared.context import actor_type_var, tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/pms-data-query", tags=["SYS-PMSDataQuery"])


class CreatePolicyRequest(BaseModel):
    policy_name: str = Field(..., min_length=1, max_length=200)
    domain: str = Field(..., min_length=1, max_length=50)
    allowed_scopes: list[str] = Field(default_factory=list)
    allowed_fields: list[str] = Field(default_factory=list)
    masked_fields: list[str] = Field(default_factory=list)
    denied_fields: list[str] = Field(default_factory=list)
    row_filter: dict = Field(default_factory=dict)
    max_rows_per_query: int = Field(default=1000, ge=1, le=10000)


class QueryDataRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=50)
    query_scope: str = Field(..., min_length=1, max_length=50)
    query_type: str = Field(default="list", max_length=50)
    filters: dict | None = Field(default=None)
    requested_fields: list[str] | None = Field(default=None)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


@router.post("/policies", response_model=None)
async def create_policy(req: CreatePolicyRequest, session: AsyncSession = Depends(get_db_session)):
    svc = PMSDataQueryService(session)
    policy = await svc.create_policy(
        tenant_id=tenant_id_var.get(""), policy_name=req.policy_name, domain=req.domain,
        allowed_scopes=req.allowed_scopes, allowed_fields=req.allowed_fields,
        masked_fields=req.masked_fields, denied_fields=req.denied_fields,
        row_filter=req.row_filter, max_rows_per_query=req.max_rows_per_query,
    )
    return Result.ok(
        data={"id": policy.id, "policy_name": policy.policy_name, "domain": policy.domain,
              "allowed_scopes": policy.allowed_scopes, "is_active": policy.is_active},
        trace_id=trace_id_var.get(""),
    )


@router.get("/policies", response_model=None)
async def list_policies(
    domain: str = Query(default=""),
    session: AsyncSession = Depends(get_db_session),
):
    svc = PMSDataQueryService(session)
    policies = await svc.list_policies(tenant_id_var.get(""), domain=domain)
    items = [
        {"id": p.id, "policy_name": p.policy_name, "domain": p.domain,
         "allowed_scopes": p.allowed_scopes, "allowed_fields": p.allowed_fields,
         "masked_fields": p.masked_fields, "denied_fields": p.denied_fields,
         "max_rows_per_query": p.max_rows_per_query, "is_active": p.is_active}
        for p in policies
    ]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.post("/query", response_model=None)
async def query_data(req: QueryDataRequest, session: AsyncSession = Depends(get_db_session)):
    pms_client_id = actor_type_var.get("pms_anonymous")
    svc = PMSDataQueryService(session)
    result = await svc.query_data(
        tenant_id=tenant_id_var.get(""), pms_client_id=pms_client_id,
        domain=req.domain, query_scope=req.query_scope,
        query_type=req.query_type, filters=req.filters,
        requested_fields=req.requested_fields,
        page=req.page, page_size=req.page_size,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/query-logs", response_model=None)
async def list_query_logs(
    domain: str = Query(default=""),
    pms_client_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = PMSDataQueryService(session)
    logs, total = await svc.list_query_logs(
        tenant_id_var.get(""), domain=domain, pms_client_id=pms_client_id,
        page=page, page_size=page_size,
    )
    items = [
        {"id": log.id, "pms_client_id": log.pms_client_id, "query_domain": log.query_domain,
         "query_scope": log.query_scope, "query_type": log.query_type,
         "row_count": log.row_count, "is_success": log.is_success,
         "duration_ms": log.duration_ms, "created_at": log.created_at.isoformat() if log.created_at else None}
        for log in logs
    ]
    return Result.paginate(items=items, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/init-defaults", response_model=None)
async def init_defaults(session: AsyncSession = Depends(get_db_session)):
    svc = PMSDataQueryService(session)
    policies = await svc.init_default_policies(tenant_id_var.get(""))
    return Result.ok(
        data={"initialized_count": len(policies)},
        trace_id=trace_id_var.get(""),
    )
