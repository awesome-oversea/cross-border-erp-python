from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.sys.domain.master_data_governance_models import MasterDataGovernanceService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/master-data-governance", tags=["SYS-MasterDataGovernance"])


class CreateRuleRequest(BaseModel):
    rule_name: str = Field(..., min_length=1, max_length=200)
    rule_code: str = Field(..., min_length=1, max_length=100)
    master_data_type: str = Field(..., min_length=1, max_length=50)
    rule_type: str = Field(..., min_length=1, max_length=50)
    field_name: str = Field(default="", max_length=100)
    condition: dict = Field(default_factory=dict)
    description: str = Field(default="", max_length=500)
    severity: str = Field(default="warning", max_length=20)


class ValidateRecordRequest(BaseModel):
    master_data_type: str = Field(..., min_length=1, max_length=50)
    record: dict = Field(...)


class ResolveIssueRequest(BaseModel):
    resolution_note: str = Field(default="", max_length=500)


@router.post("/rules", response_model=None)
async def create_rule(req: CreateRuleRequest, session: AsyncSession = Depends(get_db_session)):
    svc = MasterDataGovernanceService(session)
    rule = await svc.create_rule(
        tenant_id=tenant_id_var.get(""), rule_name=req.rule_name, rule_code=req.rule_code,
        master_data_type=req.master_data_type, rule_type=req.rule_type,
        field_name=req.field_name, condition=req.condition,
        description=req.description, severity=req.severity,
    )
    return Result.ok(
        data={"id": rule.id, "rule_code": rule.rule_code, "rule_name": rule.rule_name,
              "master_data_type": rule.master_data_type, "rule_type": rule.rule_type,
              "severity": rule.severity, "is_active": rule.is_active},
        trace_id=trace_id_var.get(""),
    )


@router.get("/rules", response_model=None)
async def list_rules(
    master_data_type: str = Query(default=""),
    rule_type: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = MasterDataGovernanceService(session)
    rules = await svc.list_rules(
        tenant_id_var.get(""), master_data_type=master_data_type,
    )
    if rule_type:
        rules = [r for r in rules if r.rule_type == rule_type]
    total = len(rules)
    offset = (page - 1) * page_size
    paged = rules[offset:offset + page_size]
    items = [
        {"id": r.id, "rule_code": r.rule_code, "rule_name": r.rule_name,
         "master_data_type": r.master_data_type, "rule_type": r.rule_type,
         "field_name": r.field_name, "condition": r.condition_json,
         "severity": r.severity, "is_active": r.is_active,
         "description": r.description}
        for r in paged
    ]
    return Result.paginate(items=items, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/validate", response_model=None)
async def validate_record(req: ValidateRecordRequest, session: AsyncSession = Depends(get_db_session)):
    svc = MasterDataGovernanceService(session)
    issues = await svc.validate_record(
        tenant_id=tenant_id_var.get(""), master_data_type=req.master_data_type, record=req.record,
    )
    return Result.ok(
        data={"issue_count": len(issues), "issues": [
            {"id": i.id, "rule_id": i.rule_id, "issue_type": i.issue_type,
             "field_name": i.field_name, "severity": i.severity,
             "message": i.message, "current_value": i.current_value,
             "expected_value": i.expected_value}
            for i in issues
        ]},
        trace_id=trace_id_var.get(""),
    )


@router.get("/issues", response_model=None)
async def list_issues(
    master_data_type: str = Query(default=""),
    status: str = Query(default=""),
    severity: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = MasterDataGovernanceService(session)
    issues, total = await svc.list_issues(
        tenant_id_var.get(""), master_data_type=master_data_type,
        status=status, severity=severity, page=page, page_size=page_size,
    )
    items = [
        {"id": i.id, "rule_id": i.rule_id, "master_data_type": i.master_data_type,
         "record_id": i.record_id, "field_name": i.field_name,
         "issue_type": i.issue_type, "severity": i.severity,
         "message": i.message, "status": i.status,
         "current_value": i.current_value, "expected_value": i.expected_value}
        for i in issues
    ]
    return Result.paginate(items=items, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/issues/{issue_id}/resolve", response_model=None)
async def resolve_issue(issue_id: str, req: ResolveIssueRequest, session: AsyncSession = Depends(get_db_session)):
    svc = MasterDataGovernanceService(session)
    issue = await svc.resolve_issue(issue_id, tenant_id_var.get(""), resolution_note=req.resolution_note)
    return Result.ok(
        data={"id": issue.id, "status": issue.status, "resolved_by": issue.resolved_by},
        trace_id=trace_id_var.get(""),
    )


@router.post("/init-defaults", response_model=None)
async def init_defaults(session: AsyncSession = Depends(get_db_session)):
    svc = MasterDataGovernanceService(session)
    rules = await svc.init_default_rules(tenant_id_var.get(""))
    return Result.ok(
        data={"initialized_count": len(rules)},
        trace_id=trace_id_var.get(""),
    )
