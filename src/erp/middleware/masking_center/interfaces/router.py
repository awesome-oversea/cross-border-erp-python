from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.masking_center.application.services import MaskingCenterService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/masking", tags=["Masking Center - 数据脱敏中心"])


class MaskRequest(BaseModel):
    data: dict
    field_mapping: dict[str, str] | None = None


class RuleCreateRequest(BaseModel):
    rule_code: str = Field(min_length=1, max_length=64)
    rule_name: str = Field(min_length=1, max_length=128)
    field_type: str = Field(min_length=1, max_length=32)
    pattern: str = Field(min_length=1)
    replacement: str = Field(min_length=1)
    description: str = Field(default="")


@router.post("/mask", response_model=None)
async def mask_data(req: MaskRequest, session: AsyncSession = Depends(get_db_session)):
    svc = MaskingCenterService(session)
    result = await svc.mask(tenant_id_var.get(""), req.data, req.field_mapping)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/rules", response_model=None)
async def get_rules(session: AsyncSession = Depends(get_db_session)):
    svc = MaskingCenterService(session)
    result = await svc.get_rules(tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/rules", response_model=None)
async def create_rule(req: RuleCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = MaskingCenterService(session)
    result = await svc.create_rule(tenant_id_var.get(""), req.rule_code, req.rule_name,
                                    req.field_type, req.pattern, req.replacement, req.description)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/audit", response_model=None)
async def get_audit_records(limit: int = Query(default=50, ge=1, le=200),
                              session: AsyncSession = Depends(get_db_session)):
    svc = MaskingCenterService(session)
    result = await svc.get_audit_records(tenant_id_var.get(""), limit)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
