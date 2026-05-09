from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from erp.middleware.compliance.application.services import ComplianceService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/fms/v1", tags=["Compliance - 合规风控中台"])


class ComplianceCheckRequest(BaseModel):
    content: str = Field(min_length=1)
    platform: str = Field(default="", max_length=32)
    country: str = Field(default="", max_length=10)
    category: str = Field(default="")


class RiskAssessRequest(BaseModel):
    transaction_amount: float = Field(gt=0)
    country: str = Field(default="", max_length=10)
    customer_segment: str = Field(default="")
    platform: str = Field(default="", max_length=32)


@router.post("/compliance/check", response_model=None)
async def check_compliance(req: ComplianceCheckRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ComplianceService(session)
    result = await svc.check(tenant_id_var.get(""), req.content, req.platform, req.country, req.category)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/compliance/rules", response_model=None)
async def get_compliance_rules(session: AsyncSession = Depends(get_db_session)):
    svc = ComplianceService(session)
    rules = await svc.get_rules(tenant_id_var.get(""))
    return Result.ok(data=rules, trace_id=trace_id_var.get(""))


@router.post("/risk/assess", response_model=None)
async def assess_risk(req: RiskAssessRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ComplianceService(session)
    result = await svc.assess_risk(tenant_id_var.get(""), req.transaction_amount, req.country, req.customer_segment, req.platform)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
