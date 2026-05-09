from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class BizRule(Base):
    __tablename__ = "biz_rule"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    domain: Mapped[str] = mapped_column(String(50), nullable=False, default="", index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    condition_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    action_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BizRuleService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_rule(self, tenant_id: str, rule_type: str, rule_code: str,
                          rule_name: str, domain: str = "", priority: int = 0,
                          condition_json: str = "{}", action_json: str = "{}",
                          description: str = "", effective_from: datetime | None = None,
                          effective_to: datetime | None = None) -> BizRule:
        stmt = select(BizRule).where(
            BizRule.tenant_id == tenant_id,
            BizRule.rule_code == rule_code,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise ValidationException(f"Rule code already exists: {rule_code}")
        rule = BizRule(
            tenant_id=tenant_id, rule_type=rule_type, rule_code=rule_code,
            rule_name=rule_name, domain=domain, priority=priority,
            condition_json=condition_json, action_json=action_json,
            description=description, effective_from=effective_from,
            effective_to=effective_to, created_by="",
        )
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def update_rule(self, rule_id: str, **kwargs) -> BizRule:
        rule = await self.session.get(BizRule, rule_id)
        if not rule:
            raise NotFoundException(f"Rule not found: {rule_id}")
        for k, v in kwargs.items():
            if hasattr(rule, k) and k != "id":
                setattr(rule, k, v)
        rule.version += 1
        await self.session.flush()
        return rule

    async def get_by_id(self, rule_id: str) -> BizRule | None:
        return await self.session.get(BizRule, rule_id)

    async def get_or_raise(self, rule_id: str) -> BizRule:
        rule = await self.get_by_id(rule_id)
        if not rule:
            raise NotFoundException(message=f"BizRule '{rule_id}' not found")
        return rule

    async def list_rules(self, tenant_id: str, rule_type: str | None = None,
                         domain: str | None = None, is_active: bool | None = None) -> list[BizRule]:
        stmt = select(BizRule).where(BizRule.tenant_id == tenant_id)
        if rule_type:
            stmt = stmt.where(BizRule.rule_type == rule_type)
        if domain:
            stmt = stmt.where(BizRule.domain == domain)
        if is_active is not None:
            stmt = stmt.where(BizRule.is_active == is_active)
        stmt = stmt.order_by(BizRule.priority.desc(), BizRule.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def evaluate(self, tenant_id: str, rule_type: str, context: dict) -> list[dict]:
        now = datetime.now()
        stmt = select(BizRule).where(
            BizRule.tenant_id == tenant_id,
            BizRule.rule_type == rule_type,
            BizRule.is_active,
        ).order_by(BizRule.priority.desc())
        result = await self.session.execute(stmt)
        rules = list(result.scalars().all())

        matched = []
        for rule in rules:
            if rule.effective_from and now < rule.effective_from:
                continue
            if rule.effective_to and now > rule.effective_to:
                continue
            try:
                condition = json.loads(rule.condition_json)
                if self._match_condition(condition, context):
                    action = json.loads(rule.action_json)
                    matched.append({
                        "rule_id": rule.id,
                        "rule_code": rule.rule_code,
                        "rule_name": rule.rule_name,
                        "action": action,
                        "priority": rule.priority,
                    })
            except (json.JSONDecodeError, Exception):
                continue
        return matched

    def _match_condition(self, condition: dict, context: dict) -> bool:
        for key, expected in condition.items():
            actual = context.get(key)
            if isinstance(expected, dict):
                op = expected.get("op", "eq")
                val = expected.get("value")
                if (op == "eq" and actual != val) or (op == "ne" and actual == val) or (op == "gt" and (actual is None or actual <= val)) or (op == "gte" and (actual is None or actual < val)) or (op == "lt" and (actual is None or actual >= val)) or (op == "lte" and (actual is None or actual > val)) or (op == "in" and actual not in val) or (op == "contains" and (actual is None or val not in str(actual))):
                    return False
            else:
                if actual != expected:
                    return False
        return True

    async def delete_rule(self, rule_id: str):
        rule = await self.session.get(BizRule, rule_id)
        if not rule:
            raise NotFoundException(f"Rule not found: {rule_id}")
        await self.session.delete(rule)
        await self.session.flush()


class BizRuleVersion(Base):
    __tablename__ = "biz_rule_version"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    condition_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    action_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    change_reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    changed_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BizRuleExecutionLog(Base):
    __tablename__ = "biz_rule_execution_log"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    context_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    action_taken: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BizRuleVersionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_version(self, rule: BizRule, change_reason: str = "") -> BizRuleVersion:
        version = BizRuleVersion(
            tenant_id=rule.tenant_id, rule_id=rule.id,
            rule_code=rule.rule_code, version=rule.version,
            rule_name=rule.rule_name, description=rule.description,
            condition_json=rule.condition_json, action_json=rule.action_json,
            priority=rule.priority, effective_from=rule.effective_from,
            effective_to=rule.effective_to, change_reason=change_reason,
            changed_by=actor_id_var.get(""),
        )
        self.session.add(version)
        await self.session.flush()
        return version

    async def list_versions(self, tenant_id: str, rule_id: str) -> list[BizRuleVersion]:
        stmt = select(BizRuleVersion).where(
            BizRuleVersion.tenant_id == tenant_id,
            BizRuleVersion.rule_id == rule_id,
        ).order_by(BizRuleVersion.version.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def rollback_to_version(self, rule_id: str, version: int,
                                   tenant_id: str) -> BizRule:
        rule = await self.session.get(BizRule, rule_id)
        if not rule or rule.tenant_id != tenant_id:
            raise NotFoundException(f"Rule not found: {rule_id}")

        stmt = select(BizRuleVersion).where(
            BizRuleVersion.tenant_id == tenant_id,
            BizRuleVersion.rule_id == rule_id,
            BizRuleVersion.version == version,
        )
        ver = (await self.session.execute(stmt)).scalar_one_or_none()
        if not ver:
            raise NotFoundException(f"Version {version} not found for rule {rule_id}")

        await self.save_version(rule, change_reason=f"Rollback to version {version}")

        rule.rule_name = ver.rule_name
        rule.description = ver.description
        rule.condition_json = ver.condition_json
        rule.action_json = ver.action_json
        rule.priority = ver.priority
        rule.effective_from = ver.effective_from
        rule.effective_to = ver.effective_to
        rule.version += 1
        await self.session.flush()
        return rule


class BizRuleExecutionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_execution(self, tenant_id: str, rule_id: str, rule_code: str,
                             rule_type: str, rule_version: int,
                             context: dict, matched: bool,
                             action_taken: dict | None = None,
                             explanation: str = "") -> BizRuleExecutionLog:
        log = BizRuleExecutionLog(
            tenant_id=tenant_id, rule_id=rule_id, rule_code=rule_code,
            rule_type=rule_type, rule_version=rule_version,
            context_json=json.dumps(context, default=str),
            matched=matched,
            action_taken=json.dumps(action_taken or {}, default=str),
            explanation=explanation,
            trace_id=trace_id_var.get(""),
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def list_execution_logs(self, tenant_id: str, rule_type: str = "",
                                   rule_code: str = "",
                                   page: int = 1, page_size: int = 20) -> tuple[list[BizRuleExecutionLog], int]:
        conditions = [BizRuleExecutionLog.tenant_id == tenant_id]
        if rule_type:
            conditions.append(BizRuleExecutionLog.rule_type == rule_type)
        if rule_code:
            conditions.append(BizRuleExecutionLog.rule_code == rule_code)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(BizRuleExecutionLog).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(BizRuleExecutionLog).where(*conditions).order_by(
            BizRuleExecutionLog.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total


class BizRuleSimulationService:
    @staticmethod
    def simulate(rule: dict, cases: list[dict]) -> dict:
        cond = rule.get("condition_json", {})
        matched, results = 0, []
        for c in cases:
            is_match = BizRuleSimulationService._eval(cond, c.get("data", {}))
            if is_match: matched += 1
            results.append({"id": c.get("id", ""), "matched": is_match})
        return {"code": rule.get("rule_code", ""), "total": len(cases),
                "matched": matched, "rate": round(matched/max(len(cases),1)*100, 2)}

    @staticmethod
    def _eval(cond: dict, data: dict) -> bool:
        actual = data.get(cond.get("field", ""))
        op, val = cond.get("operator", "eq"), cond.get("value")
        if op == "eq": return actual == val
        if op == "gt": return actual is not None and actual > val
        if op == "gte": return actual is not None and actual >= val
        if op == "lt": return actual is not None and actual < val
        if op == "lte": return actual is not None and actual <= val
        if op == "in": return actual in (val or [])
        if op == "between" and isinstance(val, list) and len(val) == 2:
            return actual is not None and val[0] <= actual <= val[1]
        return False
