from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.sys.domain.rule_models import BizRuleExecutionService, BizRuleService, BizRuleVersionService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import NotFoundException, Result

router = APIRouter(prefix="/sys/v1/rules", tags=["SYS-BizRule"])


class RuleCreateRequest(BaseModel):
    rule_type: str = Field(..., min_length=1)
    rule_code: str = Field(..., min_length=1)
    rule_name: str = Field(..., min_length=1)
    domain: str = Field(default="")
    priority: int = Field(default=0)
    condition_json: str = Field(default="{}")
    action_json: str = Field(default="{}")
    description: str = Field(default="")
    effective_from: datetime | None = Field(default=None)
    effective_to: datetime | None = Field(default=None)


class RuleUpdateRequest(BaseModel):
    rule_name: str | None = Field(default=None)
    priority: int | None = Field(default=None)
    condition_json: str | None = Field(default=None)
    action_json: str | None = Field(default=None)
    is_active: bool | None = Field(default=None)
    description: str | None = Field(default=None)
    effective_from: datetime | None = Field(default=None)
    effective_to: datetime | None = Field(default=None)


class RuleEvaluateRequest(BaseModel):
    rule_type: str = Field(..., min_length=1)
    context: dict = Field(default_factory=dict)


@router.post("", response_model=None)
async def create_rule(req: RuleCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = BizRuleService(session)
    rule = await svc.create_rule(
        tenant_id=tenant_id_var.get(""), rule_type=req.rule_type, rule_code=req.rule_code,
        rule_name=req.rule_name, domain=req.domain, priority=req.priority,
        condition_json=req.condition_json, action_json=req.action_json,
        description=req.description, effective_from=req.effective_from,
        effective_to=req.effective_to,
    )
    return Result.ok(
        data={"id": rule.id, "rule_type": rule.rule_type, "rule_code": rule.rule_code,
              "rule_name": rule.rule_name, "version": rule.version},
        trace_id=trace_id_var.get(""),
    )


@router.get("", response_model=None)
async def list_rules(rule_type: str | None = Query(default=None),
                     domain: str | None = Query(default=None),
                     is_active: bool | None = Query(default=None),
                     session: AsyncSession = Depends(get_db_session)):
    svc = BizRuleService(session)
    rules = await svc.list_rules(
        tenant_id=tenant_id_var.get(""), rule_type=rule_type,
        domain=domain, is_active=is_active,
    )
    return Result.ok(
        data=[{"id": r.id, "rule_type": r.rule_type, "rule_code": r.rule_code,
               "rule_name": r.rule_name, "domain": r.domain, "priority": r.priority,
               "is_active": r.is_active, "version": r.version} for r in rules],
        trace_id=trace_id_var.get(""),
    )


@router.get("/{rule_id}", response_model=None)
async def get_rule(rule_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = BizRuleService(session)
    rule = await svc.get_or_raise(rule_id)
    return Result.ok(
        data={"id": rule.id, "rule_type": rule.rule_type, "rule_code": rule.rule_code,
              "rule_name": rule.rule_name, "domain": rule.domain, "priority": rule.priority,
              "condition_json": rule.condition_json, "action_json": rule.action_json,
              "is_active": rule.is_active, "version": rule.version,
              "description": rule.description},
        trace_id=trace_id_var.get(""),
    )


@router.put("/{rule_id}", response_model=None)
async def update_rule(rule_id: str, req: RuleUpdateRequest,
                       session: AsyncSession = Depends(get_db_session)):
    svc = BizRuleService(session)
    kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
    rule = await svc.update_rule(rule_id, **kwargs)
    return Result.ok(
        data={"id": rule.id, "rule_code": rule.rule_code, "version": rule.version},
        trace_id=trace_id_var.get(""),
    )


@router.delete("/{rule_id}", response_model=None)
async def delete_rule(rule_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = BizRuleService(session)
    await svc.delete_rule(rule_id)
    return Result.ok(data=None, trace_id=trace_id_var.get(""))


@router.post("/evaluate", response_model=None)
async def evaluate_rules(req: RuleEvaluateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = BizRuleService(session)
    matched = await svc.evaluate(
        tenant_id=tenant_id_var.get(""), rule_type=req.rule_type, context=req.context,
    )
    return Result.ok(data=matched, trace_id=trace_id_var.get(""))


class RuleRollbackRequest(BaseModel):
    version: int = Field(..., ge=1)


# ── Version Management ──

@router.get("/{rule_id}/versions", response_model=None)
async def list_rule_versions(rule_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = BizRuleVersionService(session)
    versions = await svc.list_versions(tenant_id_var.get(""), rule_id)
    data = [{
        "id": v.id, "rule_id": v.rule_id, "rule_code": v.rule_code,
        "version": v.version, "rule_name": v.rule_name,
        "description": v.description, "priority": v.priority,
        "condition_json": v.condition_json, "action_json": v.action_json,
        "effective_from": v.effective_from.isoformat() if v.effective_from else None,
        "effective_to": v.effective_to.isoformat() if v.effective_to else None,
        "change_reason": v.change_reason, "changed_by": v.changed_by,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    } for v in versions]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/{rule_id}/rollback", response_model=None)
async def rollback_rule(rule_id: str, req: RuleRollbackRequest,
                         session: AsyncSession = Depends(get_db_session)):
    ver_svc = BizRuleVersionService(session)
    rule = await ver_svc.rollback_to_version(rule_id, req.version, tenant_id_var.get(""))
    return Result.ok(
        data={"id": rule.id, "rule_code": rule.rule_code,
              "version": rule.version, "rollback_to": req.version},
        trace_id=trace_id_var.get(""),
    )


# ── Execution Logs ──

@router.get("/execution-logs", response_model=None)
async def list_execution_logs(
    rule_type: str = Query(default=""),
    rule_code: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    import json
    svc = BizRuleExecutionService(session)
    logs, total = await svc.list_execution_logs(
        tenant_id_var.get(""), rule_type=rule_type,
        rule_code=rule_code, page=page, page_size=page_size,
    )
    data = [{
        "id": log.id, "rule_id": log.rule_id, "rule_code": log.rule_code,
        "rule_type": log.rule_type, "rule_version": log.rule_version,
        "context": json.loads(log.context_json),
        "matched": log.matched,
        "action_taken": json.loads(log.action_taken),
        "explanation": log.explanation, "trace_id": log.trace_id,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    } for log in logs]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))
