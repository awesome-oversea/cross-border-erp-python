from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.sys.domain.ai_switch_models import (
    AIExecutionLogService,
    AISecurityPolicyService,
    AISwitchService,
)
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import NotFoundException, Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/ai-switches", tags=["SYS-AISwitch"])


class AISwitchSetRequest(BaseModel):
    domain: str = Field(..., min_length=1)
    scene: str = Field(default="default")
    is_enabled: bool = Field(default=True)
    auto_execute: bool = Field(default=False)
    auto_execute_threshold: float = Field(default=0)
    require_approval: bool = Field(default=True)
    max_daily_executions: int = Field(default=100)
    gray_rollout_percent: int = Field(default=0, ge=0, le=100)
    description: str = Field(default="")


class AICheckRequest(BaseModel):
    domain: str = Field(..., min_length=1)
    scene: str = Field(default="default")
    confidence: float = Field(default=0)


class AISecurityPolicyRequest(BaseModel):
    policy_name: str = Field(..., min_length=1, max_length=200)
    domain: str = Field(..., min_length=1, max_length=50)
    scene: str = Field(default="default")
    max_single_amount: float = Field(default=0)
    max_daily_amount: float = Field(default=0)
    allowed_operation_types: list[str] = Field(default_factory=list)
    blocked_operation_types: list[str] = Field(default_factory=list)
    require_mfa: bool = Field(default=False)
    require_dual_approval: bool = Field(default=False)
    ip_whitelist: list[str] = Field(default_factory=list)
    time_window_start: str = Field(default="00:00")
    time_window_end: str = Field(default="23:59")


class AISecurityCheckRequest(BaseModel):
    domain: str = Field(..., min_length=1)
    scene: str = Field(default="default")
    operation_type: str = Field(default="")
    amount: float = Field(default=0)
    actor_ip: str = Field(default="")


class AIExecutionLogRequest(BaseModel):
    domain: str = Field(..., min_length=1)
    scene: str = Field(default="default")
    recommendation_id: str = Field(default="")
    execution_type: str = Field(default="auto")
    operation_type: str = Field(default="")
    target_type: str = Field(default="")
    target_id: str = Field(default="")
    result: str = Field(default="pending")
    result_detail: str = Field(default="")
    amount: float = Field(default=0)
    actor_id: str = Field(default="")
    actor_type: str = Field(default="service_account")
    approval_instance_id: str = Field(default="")


class AIRollbackRequest(BaseModel):
    reason: str = Field(..., min_length=1)


@router.post("", response_model=None)
async def set_ai_switch(req: AISwitchSetRequest, session: AsyncSession = Depends(get_db_session)):
    svc = AISwitchService(session)
    switch = await svc.set_switch(
        tenant_id=tenant_id_var.get(""), domain=req.domain, scene=req.scene,
        is_enabled=req.is_enabled, auto_execute=req.auto_execute,
        auto_execute_threshold=req.auto_execute_threshold,
        require_approval=req.require_approval,
        max_daily_executions=req.max_daily_executions,
        gray_rollout_percent=req.gray_rollout_percent,
        description=req.description,
    )
    return Result.ok(
        data={"id": switch.id, "domain": switch.domain, "scene": switch.scene,
              "is_enabled": switch.is_enabled, "auto_execute": switch.auto_execute,
              "require_approval": switch.require_approval},
        trace_id=trace_id_var.get(""),
    )


@router.get("", response_model=None)
async def list_ai_switches(domain: str | None = Query(default=None),
                            session: AsyncSession = Depends(get_db_session)):
    svc = AISwitchService(session)
    switches = await svc.list_switches(tenant_id=tenant_id_var.get(""), domain=domain)
    return Result.ok(
        data=[{"id": s.id, "domain": s.domain, "scene": s.scene,
               "is_enabled": s.is_enabled, "auto_execute": s.auto_execute,
               "auto_execute_threshold": s.auto_execute_threshold,
               "require_approval": s.require_approval,
               "max_daily_executions": s.max_daily_executions,
               "current_daily_count": s.current_daily_count,
               "gray_rollout_percent": s.gray_rollout_percent,
               "description": s.description} for s in switches],
        trace_id=trace_id_var.get(""),
    )


@router.get("/{domain}/{scene}", response_model=None)
async def get_ai_switch(domain: str, scene: str = "default",
                         session: AsyncSession = Depends(get_db_session)):
    svc = AISwitchService(session)
    switch = await svc.get_switch_or_raise(tenant_id_var.get(""), domain=domain, scene=scene)
    return Result.ok(
        data={"id": switch.id, "domain": switch.domain, "scene": switch.scene,
              "is_enabled": switch.is_enabled, "auto_execute": switch.auto_execute,
              "auto_execute_threshold": switch.auto_execute_threshold,
              "require_approval": switch.require_approval,
              "max_daily_executions": switch.max_daily_executions,
              "current_daily_count": switch.current_daily_count,
              "gray_rollout_percent": switch.gray_rollout_percent},
        trace_id=trace_id_var.get(""),
    )


@router.post("/check", response_model=None)
async def check_ai_execution(req: AICheckRequest, session: AsyncSession = Depends(get_db_session)):
    svc = AISwitchService(session)
    enabled = await svc.is_enabled(tenant_id_var.get(""), req.domain, req.scene)
    can_auto = await svc.can_auto_execute(
        tenant_id_var.get(""), req.domain, req.scene, req.confidence
    )
    return Result.ok(
        data={"domain": req.domain, "scene": req.scene,
              "is_enabled": enabled, "can_auto_execute": can_auto},
        trace_id=trace_id_var.get(""),
    )


@router.post("/security-check", response_model=None)
async def security_check(req: AISecurityCheckRequest, session: AsyncSession = Depends(get_db_session)):
    svc = AISecurityPolicyService(session)
    allowed, reason = await svc.check_execution_allowed(
        tenant_id_var.get(""), req.domain, req.scene,
        operation_type=req.operation_type, amount=req.amount,
        actor_ip=req.actor_ip,
    )
    return Result.ok(
        data={"domain": req.domain, "scene": req.scene,
              "allowed": allowed, "reason": reason},
        trace_id=trace_id_var.get(""),
    )


@router.post("/security-policies", response_model=None)
async def create_security_policy(req: AISecurityPolicyRequest, session: AsyncSession = Depends(get_db_session)):
    svc = AISecurityPolicyService(session)
    policy = await svc.create_policy(
        tenant_id=tenant_id_var.get(""), policy_name=req.policy_name,
        domain=req.domain, scene=req.scene,
        max_single_amount=req.max_single_amount, max_daily_amount=req.max_daily_amount,
        allowed_operation_types=req.allowed_operation_types,
        blocked_operation_types=req.blocked_operation_types,
        require_mfa=req.require_mfa, require_dual_approval=req.require_dual_approval,
        ip_whitelist=req.ip_whitelist,
        time_window_start=req.time_window_start, time_window_end=req.time_window_end,
    )
    return Result.ok(
        data={"id": policy.id, "policy_name": policy.policy_name,
              "domain": policy.domain, "scene": policy.scene,
              "max_single_amount": float(policy.max_single_amount),
              "max_daily_amount": float(policy.max_daily_amount),
              "require_mfa": policy.require_mfa,
              "require_dual_approval": policy.require_dual_approval,
              "is_active": policy.is_active},
        trace_id=trace_id_var.get(""),
    )


@router.get("/security-policies", response_model=None)
async def list_security_policies(domain: str | None = Query(default=None),
                                  session: AsyncSession = Depends(get_db_session)):
    svc = AISecurityPolicyService(session)
    policies = await svc.list_policies(tenant_id_var.get(""), domain=domain)
    return Result.ok(
        data=[{"id": p.id, "policy_name": p.policy_name, "domain": p.domain,
               "scene": p.scene, "max_single_amount": float(p.max_single_amount),
               "max_daily_amount": float(p.max_daily_amount),
               "allowed_operation_types": json.loads(p.allowed_operation_types),
               "blocked_operation_types": json.loads(p.blocked_operation_types),
               "require_mfa": p.require_mfa, "require_dual_approval": p.require_dual_approval,
               "ip_whitelist": json.loads(p.ip_whitelist),
               "time_window_start": p.time_window_start, "time_window_end": p.time_window_end,
               "is_active": p.is_active} for p in policies],
        trace_id=trace_id_var.get(""),
    )


@router.put("/security-policies/{policy_id}/deactivate", response_model=None)
async def deactivate_security_policy(policy_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = AISecurityPolicyService(session)
    policy = await svc.deactivate_policy(policy_id, tenant_id_var.get(""))
    return Result.ok(data={"id": policy.id, "is_active": policy.is_active}, trace_id=trace_id_var.get(""))


@router.post("/execution-logs", response_model=None)
async def log_execution(req: AIExecutionLogRequest, session: AsyncSession = Depends(get_db_session)):
    svc = AIExecutionLogService(session)
    log = await svc.log_execution(
        tenant_id=tenant_id_var.get(""), domain=req.domain, scene=req.scene,
        recommendation_id=req.recommendation_id, execution_type=req.execution_type,
        operation_type=req.operation_type, target_type=req.target_type,
        target_id=req.target_id, result=req.result, result_detail=req.result_detail,
        amount=req.amount, actor_id=req.actor_id, actor_type=req.actor_type,
        approval_instance_id=req.approval_instance_id,
    )
    return Result.ok(
        data={"id": log.id, "domain": log.domain, "scene": log.scene,
              "recommendation_id": log.recommendation_id, "result": log.result},
        trace_id=trace_id_var.get(""),
    )


@router.get("/execution-logs", response_model=None)
async def list_execution_logs(
    domain: str = Query(default=""),
    scene: str = Query(default=""),
    result: str = Query(default=""),
    is_rolled_back: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = AIExecutionLogService(session)
    logs, total = await svc.list_logs(
        tenant_id_var.get(""), domain=domain, scene=scene,
        result=result, is_rolled_back=is_rolled_back,
        page=page, page_size=page_size,
    )
    data = [{
        "id": log.id, "domain": log.domain, "scene": log.scene,
        "recommendation_id": log.recommendation_id,
        "execution_type": log.execution_type, "operation_type": log.operation_type,
        "target_type": log.target_type, "target_id": log.target_id,
        "result": log.result, "amount": float(log.amount),
        "is_rolled_back": log.is_rolled_back, "rollback_reason": log.rollback_reason,
        "actor_id": log.actor_id, "actor_type": log.actor_type,
        "trace_id": log.trace_id,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    } for log in logs]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.put("/execution-logs/{log_id}/rollback", response_model=None)
async def rollback_execution(log_id: str, req: AIRollbackRequest, session: AsyncSession = Depends(get_db_session)):
    svc = AIExecutionLogService(session)
    log = await svc.rollback(log_id, tenant_id_var.get(""), reason=req.reason)
    return Result.ok(
        data={"id": log.id, "is_rolled_back": log.is_rolled_back,
              "rollback_reason": log.rollback_reason},
        trace_id=trace_id_var.get(""),
    )


@router.post("/init-defaults", response_model=None)
async def init_ai_switch_defaults(session: AsyncSession = Depends(get_db_session)):
    tenant_id = tenant_id_var.get("")
    switch_svc = AISwitchService(session)
    policy_svc = AISecurityPolicyService(session)
    await switch_svc.init_defaults(tenant_id)
    await policy_svc.init_default_policies(tenant_id)
    return Result.ok(data={"message": "AI switches and security policies initialized"}, trace_id=trace_id_var.get(""))
