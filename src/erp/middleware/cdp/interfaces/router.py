from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from erp.middleware.cdp.application.services import CDPService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/crm/v1/cdp", tags=["CDP - 客户数据平台"])


class SegmentCreateRequest(BaseModel):
    segment_name: str = Field(min_length=1, max_length=128)
    criteria: dict = Field(default_factory=dict)
    segment_type: str = Field(default="custom")
    description: str = Field(default="")


@router.get("/customers/{customer_id}/profile", response_model=None)
async def get_customer_profile(customer_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = CDPService(session)
    profile = await svc.get_customer_profile(tenant_id_var.get(""), customer_id)
    return Result.ok(data=profile, trace_id=trace_id_var.get(""))


@router.get("/segments", response_model=None)
async def get_segments(session: AsyncSession = Depends(get_db_session)):
    svc = CDPService(session)
    segments = await svc.get_segments(tenant_id_var.get(""))
    return Result.ok(data=segments, trace_id=trace_id_var.get(""))


@router.post("/segments", response_model=None)
async def create_segment(req: SegmentCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = CDPService(session)
    segment = await svc.create_segment(
        tenant_id_var.get(""), segment_name=req.segment_name, criteria=req.criteria,
        segment_type=req.segment_type, description=req.description,
    )
    return Result.ok(data=segment, trace_id=trace_id_var.get(""))
