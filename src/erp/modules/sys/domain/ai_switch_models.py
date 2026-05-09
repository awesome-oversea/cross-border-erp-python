from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class AISwitch(Base):
    __tablename__ = "ai_switch"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scene: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    auto_execute: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_execute_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    require_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_daily_executions: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    current_daily_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gray_rollout_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AISecurityPolicy(Base):
    __tablename__ = "ai_security_policy"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    policy_name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scene: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    max_single_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    max_daily_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    allowed_operation_types: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    blocked_operation_types: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    require_mfa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    require_dual_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ip_whitelist: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    time_window_start: Mapped[str] = mapped_column(String(10), nullable=False, default="00:00")
    time_window_end: Mapped[str] = mapped_column(String(10), nullable=False, default="23:59")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AIExecutionLog(Base):
    __tablename__ = "ai_execution_log"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scene: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    recommendation_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    execution_type: Mapped[str] = mapped_column(String(50), nullable=False, default="auto")
    operation_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    target_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    result_detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    is_rolled_back: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rollback_reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    rollback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False, default="service_account")
    approval_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AISwitchService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def set_switch(self, tenant_id: str, domain: str, scene: str = "default",
                         is_enabled: bool = True, auto_execute: bool = False,
                         auto_execute_threshold: float = 0, require_approval: bool = True,
                         max_daily_executions: int = 100, gray_rollout_percent: int = 0,
                         description: str = "") -> AISwitch:
        stmt = select(AISwitch).where(
            AISwitch.tenant_id == tenant_id,
            AISwitch.domain == domain,
            AISwitch.scene == scene,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.is_enabled = is_enabled
            existing.auto_execute = auto_execute
            existing.auto_execute_threshold = int(auto_execute_threshold)
            existing.require_approval = require_approval
            existing.max_daily_executions = max_daily_executions
            existing.gray_rollout_percent = gray_rollout_percent
            existing.description = description
            existing.updated_by = actor_id_var.get("")
            await self.session.flush()
            return existing
        switch = AISwitch(
            tenant_id=tenant_id, domain=domain, scene=scene,
            is_enabled=is_enabled, auto_execute=auto_execute,
            auto_execute_threshold=int(auto_execute_threshold),
            require_approval=require_approval,
            max_daily_executions=max_daily_executions,
            gray_rollout_percent=gray_rollout_percent,
            description=description,
            updated_by=actor_id_var.get(""),
        )
        self.session.add(switch)
        await self.session.flush()
        return switch

    async def get_switch(self, tenant_id: str, domain: str,
                         scene: str = "default") -> AISwitch | None:
        stmt = select(AISwitch).where(
            AISwitch.tenant_id == tenant_id,
            AISwitch.domain == domain,
            AISwitch.scene == scene,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_switch_or_raise(self, tenant_id: str, domain: str,
                                   scene: str = "default") -> AISwitch:
        switch = await self.get_switch(tenant_id, domain, scene)
        if not switch:
            raise NotFoundException(message=f"AISwitch '{domain}/{scene}' not found")
        return switch

    async def is_enabled(self, tenant_id: str, domain: str, scene: str = "default") -> bool:
        switch = await self.get_switch(tenant_id, domain, scene)
        if not switch:
            return False
        return switch.is_enabled

    async def can_auto_execute(self, tenant_id: str, domain: str,
                                scene: str = "default", confidence: float = 0) -> bool:
        switch = await self.get_switch(tenant_id, domain, scene)
        if not switch:
            return False
        if not switch.is_enabled:
            return False
        if not switch.auto_execute:
            return False
        if confidence < switch.auto_execute_threshold:
            return False
        return not switch.current_daily_count >= switch.max_daily_executions

    async def record_execution(self, tenant_id: str, domain: str, scene: str = "default"):
        switch = await self.get_switch(tenant_id, domain, scene)
        if switch:
            switch.current_daily_count += 1
            await self.session.flush()

    async def reset_daily_counts(self, tenant_id: str):
        stmt = select(AISwitch).where(AISwitch.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        for switch in result.scalars().all():
            switch.current_daily_count = 0
        await self.session.flush()

    async def list_switches(self, tenant_id: str, domain: str | None = None) -> list[AISwitch]:
        stmt = select(AISwitch).where(AISwitch.tenant_id == tenant_id)
        if domain:
            stmt = stmt.where(AISwitch.domain == domain)
        stmt = stmt.order_by(AISwitch.domain, AISwitch.scene)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def init_defaults(self, tenant_id: str):
        defaults = [
            ("pdm", "product_suggestion", True, False, 0, True, 100, 0, "AI选品建议"),
            ("scm", "replenishment", True, False, 0, True, 100, 0, "AI补货建议"),
            ("ads", "ad_optimization", True, False, 0, True, 50, 0, "AI广告优化建议"),
            ("oms", "risk_control", True, False, 0, True, 200, 0, "AI风控建议"),
            ("fms", "cost_analysis", True, False, 0, True, 50, 0, "AI成本分析建议"),
            ("wms", "inventory_prediction", True, False, 0, True, 50, 0, "AI库存预测"),
            ("crm", "sentiment_analysis", True, False, 0, True, 100, 0, "AI情感分析"),
        ]
        for domain, scene, enabled, auto_exec, threshold, require_appr, max_daily, gray, desc in defaults:
            existing = await self.get_switch(tenant_id, domain, scene)
            if not existing:
                await self.set_switch(tenant_id, domain, scene, enabled, auto_exec,
                                      threshold, require_appr, max_daily, gray, desc)


class AISecurityPolicyService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_policy(self, tenant_id: str, policy_name: str, domain: str,
                            scene: str = "default", max_single_amount: float = 0,
                            max_daily_amount: float = 0,
                            allowed_operation_types: list | None = None,
                            blocked_operation_types: list | None = None,
                            require_mfa: bool = False, require_dual_approval: bool = False,
                            ip_whitelist: list | None = None,
                            time_window_start: str = "00:00",
                            time_window_end: str = "23:59") -> AISecurityPolicy:
        policy = AISecurityPolicy(
            tenant_id=tenant_id, policy_name=policy_name, domain=domain, scene=scene,
            max_single_amount=max_single_amount, max_daily_amount=max_daily_amount,
            allowed_operation_types=json.dumps(allowed_operation_types or []),
            blocked_operation_types=json.dumps(blocked_operation_types or []),
            require_mfa=require_mfa, require_dual_approval=require_dual_approval,
            ip_whitelist=json.dumps(ip_whitelist or []),
            time_window_start=time_window_start, time_window_end=time_window_end,
            created_by=actor_id_var.get(""),
        )
        self.session.add(policy)
        await self.session.flush()
        return policy

    async def get_active_policy(self, tenant_id: str, domain: str,
                                 scene: str = "default") -> AISecurityPolicy | None:
        stmt = select(AISecurityPolicy).where(
            AISecurityPolicy.tenant_id == tenant_id,
            AISecurityPolicy.domain == domain,
            AISecurityPolicy.scene == scene,
            AISecurityPolicy.is_active,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def check_execution_allowed(self, tenant_id: str, domain: str, scene: str = "default",
                                       operation_type: str = "", amount: float = 0,
                                       actor_ip: str = "") -> tuple[bool, str]:
        switch_svc = AISwitchService(self.session)
        if not await switch_svc.is_enabled(tenant_id, domain, scene):
            return False, f"AI功能已关闭: {domain}/{scene}"

        policy = await self.get_active_policy(tenant_id, domain, scene)
        if not policy:
            return True, ""

        if policy.max_single_amount > 0 and amount > float(policy.max_single_amount):
            return False, f"单次执行金额超限: {amount} > {policy.max_single_amount}"

        if policy.max_daily_amount > 0:
            from sqlalchemy import func as sa_func
            today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            stmt = select(sa_func.coalesce(sa_func.sum(AIExecutionLog.amount), 0)).where(
                AIExecutionLog.tenant_id == tenant_id,
                AIExecutionLog.domain == domain,
                AIExecutionLog.scene == scene,
                AIExecutionLog.result.in_(["success", "pending"]),
                not AIExecutionLog.is_rolled_back,
                AIExecutionLog.created_at >= today_start,
            )
            daily_total = float((await self.session.execute(stmt)).scalar() or 0)
            if daily_total + amount > float(policy.max_daily_amount):
                return False, f"日累计金额超限: {daily_total + amount} > {policy.max_daily_amount}"

        if policy.allowed_operation_types and policy.allowed_operation_types != "[]":
            allowed = json.loads(policy.allowed_operation_types)
            if allowed and operation_type not in allowed:
                return False, f"操作类型不在允许列表: {operation_type}"

        if policy.blocked_operation_types and policy.blocked_operation_types != "[]":
            blocked = json.loads(policy.blocked_operation_types)
            if operation_type in blocked:
                return False, f"操作类型被禁止: {operation_type}"

        if policy.ip_whitelist and policy.ip_whitelist != "[]":
            ips = json.loads(policy.ip_whitelist)
            if ips and actor_ip and actor_ip not in ips:
                return False, f"IP不在白名单: {actor_ip}"

        now_time = datetime.now(UTC).strftime("%H:%M")
        if policy.time_window_start and policy.time_window_end and (now_time < policy.time_window_start or now_time > policy.time_window_end):
            return False, f"不在允许时间窗口: {policy.time_window_start}-{policy.time_window_end}"

        return True, ""

    async def list_policies(self, tenant_id: str, domain: str | None = None) -> list[AISecurityPolicy]:
        stmt = select(AISecurityPolicy).where(AISecurityPolicy.tenant_id == tenant_id)
        if domain:
            stmt = stmt.where(AISecurityPolicy.domain == domain)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def deactivate_policy(self, policy_id: str, tenant_id: str) -> AISecurityPolicy:
        stmt = select(AISecurityPolicy).where(
            AISecurityPolicy.id == policy_id, AISecurityPolicy.tenant_id == tenant_id,
        )
        policy = (await self.session.execute(stmt)).scalar_one_or_none()
        if not policy:
            raise NotFoundException(message=f"Policy '{policy_id}' not found")
        policy.is_active = False
        await self.session.flush()
        return policy

    async def init_default_policies(self, tenant_id: str):
        defaults = [
            ("采购AI安全策略", "scm", "replenishment", 50000, 200000,
             ["create_purchase_order"], [], False, True, [], "08:00", "20:00"),
            ("广告AI安全策略", "ads", "ad_optimization", 10000, 50000,
             ["adjust_budget", "adjust_bid"], ["delete_campaign"], False, False, [], "00:00", "23:59"),
            ("风控AI安全策略", "oms", "risk_control", 0, 0,
             ["flag_order", "hold_order"], ["cancel_order"], False, True, [], "00:00", "23:59"),
            ("财务AI安全策略", "fms", "cost_analysis", 0, 0,
             ["adjust_cost"], ["delete_cost_event", "modify_settlement"], True, True, [], "09:00", "18:00"),
        ]
        for name, domain, scene, single_amt, daily_amt, allowed, blocked, mfa, dual, ips, tw_start, tw_end in defaults:
            existing = await self.get_active_policy(tenant_id, domain, scene)
            if not existing:
                await self.create_policy(
                    tenant_id, name, domain, scene, single_amt, daily_amt,
                    allowed, blocked, mfa, dual, ips, tw_start, tw_end,
                )


class AIExecutionLogService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_execution(self, tenant_id: str, domain: str, scene: str = "default",
                             recommendation_id: str = "", execution_type: str = "auto",
                             operation_type: str = "", target_type: str = "",
                             target_id: str = "", result: str = "pending",
                             result_detail: str = "", amount: float = 0,
                             actor_id: str = "", actor_type: str = "service_account",
                             approval_instance_id: str = "") -> AIExecutionLog:
        log = AIExecutionLog(
            tenant_id=tenant_id, domain=domain, scene=scene,
            recommendation_id=recommendation_id, execution_type=execution_type,
            operation_type=operation_type, target_type=target_type,
            target_id=target_id, result=result, result_detail=result_detail,
            amount=amount, actor_id=actor_id or actor_id_var.get(""),
            actor_type=actor_type, approval_instance_id=approval_instance_id,
            trace_id=trace_id_var.get(""),
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def update_result(self, log_id: str, tenant_id: str, result: str,
                             result_detail: str = "") -> AIExecutionLog:
        stmt = select(AIExecutionLog).where(
            AIExecutionLog.id == log_id, AIExecutionLog.tenant_id == tenant_id,
        )
        log = (await self.session.execute(stmt)).scalar_one_or_none()
        if not log:
            raise NotFoundException(message=f"Execution log '{log_id}' not found")
        log.result = result
        if result_detail:
            log.result_detail = result_detail
        await self.session.flush()
        return log

    async def rollback(self, log_id: str, tenant_id: str, reason: str) -> AIExecutionLog:
        stmt = select(AIExecutionLog).where(
            AIExecutionLog.id == log_id, AIExecutionLog.tenant_id == tenant_id,
        )
        log = (await self.session.execute(stmt)).scalar_one_or_none()
        if not log:
            raise NotFoundException(message=f"Execution log '{log_id}' not found")
        log.is_rolled_back = True
        log.rollback_reason = reason
        log.rollback_at = datetime.now(UTC)
        await self.session.flush()
        return log

    async def list_logs(self, tenant_id: str, domain: str = "", scene: str = "",
                         result: str = "", is_rolled_back: bool | None = None,
                         page: int = 1, page_size: int = 20) -> tuple[list[AIExecutionLog], int]:
        conditions = [AIExecutionLog.tenant_id == tenant_id]
        if domain:
            conditions.append(AIExecutionLog.domain == domain)
        if scene:
            conditions.append(AIExecutionLog.scene == scene)
        if result:
            conditions.append(AIExecutionLog.result == result)
        if is_rolled_back is not None:
            conditions.append(AIExecutionLog.is_rolled_back == is_rolled_back)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(AIExecutionLog).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(AIExecutionLog).where(*conditions).order_by(
            AIExecutionLog.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result_set = await self.session.execute(stmt)
        return list(result_set.scalars().all()), total
