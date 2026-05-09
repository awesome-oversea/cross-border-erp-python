from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MasterDataType(StrEnum):
    SKU = "sku"
    STORE = "store"
    CHANNEL = "channel"
    WAREHOUSE = "warehouse"
    SUPPLIER = "supplier"
    PRODUCT = "product"
    CUSTOMER = "customer"
    LOGISTICS_PROVIDER = "logistics_provider"


class GovernanceRuleType(StrEnum):
    UNIQUENESS = "uniqueness"
    COMPLETENESS = "completeness"
    FORMAT = "format"
    RANGE = "range"
    CONSISTENCY = "consistency"
    DUPLICATE_DETECTION = "duplicate_detection"
    CROSS_REFERENCE = "cross_reference"


class MasterDataRule(Base):
    __tablename__ = "master_data_rule"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    master_data_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    field_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    condition_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MasterDataIssue(Base):
    __tablename__ = "master_data_issue"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    master_data_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    current_value: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    expected_value: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    resolved_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MasterDataGovernanceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_rule(self, tenant_id: str, rule_name: str, rule_code: str,
                           master_data_type: str, rule_type: str,
                           field_name: str = "", condition: dict | None = None,
                           description: str = "", severity: str = "warning") -> MasterDataRule:
        existing = await self._get_by_code(tenant_id, rule_code)
        if existing:
            raise ValidationException(message=f"Rule code '{rule_code}' already exists")

        rule = MasterDataRule(
            tenant_id=tenant_id, rule_name=rule_name, rule_code=rule_code,
            master_data_type=master_data_type, rule_type=rule_type,
            field_name=field_name, condition_json=json.dumps(condition or {}, default=str),
            description=description, severity=severity,
            created_by=actor_id_var.get(""),
        )
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def init_default_rules(self, tenant_id: str) -> list[MasterDataRule]:
        defaults = [
            ("SKU编码唯一", "sku_code_unique", MasterDataType.SKU.value,
             GovernanceRuleType.UNIQUENESS.value, "code", {"unique_fields": ["code"]}, "error"),
            ("SKU必填字段完整性", "sku_required_fields", MasterDataType.SKU.value,
             GovernanceRuleType.COMPLETENESS.value, "", {"required_fields": ["code", "name", "category_id"]}, "error"),
            ("店铺编码唯一", "store_code_unique", MasterDataType.STORE.value,
             GovernanceRuleType.UNIQUENESS.value, "code", {"unique_fields": ["code"]}, "error"),
            ("店铺授权状态检查", "store_auth_check", MasterDataType.STORE.value,
             GovernanceRuleType.CONSISTENCY.value, "auth_status", {"valid_statuses": ["authorized"]}, "warning"),
            ("渠道编码唯一", "channel_code_unique", MasterDataType.CHANNEL.value,
             GovernanceRuleType.UNIQUENESS.value, "code", {"unique_fields": ["code"]}, "error"),
            ("仓库编码唯一", "warehouse_code_unique", MasterDataType.WAREHOUSE.value,
             GovernanceRuleType.UNIQUENESS.value, "code", {"unique_fields": ["code"]}, "error"),
            ("仓库类型有效性", "warehouse_type_valid", MasterDataType.WAREHOUSE.value,
             GovernanceRuleType.RANGE.value, "warehouse_type",
             {"valid_values": ["self_owned", "fba", "third_party", "overseas"]}, "warning"),
            ("供应商编码唯一", "supplier_code_unique", MasterDataType.SUPPLIER.value,
             GovernanceRuleType.UNIQUENESS.value, "code", {"unique_fields": ["code"]}, "error"),
            ("供应商资质有效期", "supplier_qualification_valid", MasterDataType.SUPPLIER.value,
             GovernanceRuleType.RANGE.value, "qualification_expiry",
             {"check_expiry": True, "warning_days": 30}, "warning"),
            ("SKU与店铺交叉引用", "sku_store_cross_ref", MasterDataType.SKU.value,
             GovernanceRuleType.CROSS_REFERENCE.value, "store_id",
             {"reference_type": "store", "must_exist": True}, "warning"),
        ]
        rules = []
        for name, code, mdt, rt, fn, cond, sev in defaults:
            existing = await self._get_by_code(tenant_id, code)
            if not existing:
                rule = await self.create_rule(
                    tenant_id=tenant_id, rule_name=name, rule_code=code,
                    master_data_type=mdt, rule_type=rt,
                    field_name=fn, condition=cond, severity=sev,
                )
                rules.append(rule)
        return rules

    async def validate_record(self, tenant_id: str, master_data_type: str,
                               record: dict) -> list[MasterDataIssue]:
        stmt = select(MasterDataRule).where(
            MasterDataRule.tenant_id == tenant_id,
            MasterDataRule.master_data_type == master_data_type,
            MasterDataRule.is_active,
        )
        result = await self.session.execute(stmt)
        rules = list(result.scalars().all())

        issues = []
        for rule in rules:
            condition = json.loads(rule.condition_json)
            issue = self._evaluate_rule(rule, condition, record)
            if issue:
                issues.append(issue)

        if issues:
            self.session.add_all(issues)
            await self.session.flush()
        return issues

    async def resolve_issue(self, issue_id: str, tenant_id: str,
                             resolution_note: str = "") -> MasterDataIssue:
        stmt = select(MasterDataIssue).where(
            MasterDataIssue.id == issue_id, MasterDataIssue.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        issue = result.scalar_one_or_none()
        if not issue:
            raise NotFoundException(message=f"Issue '{issue_id}' not found")

        issue.status = "resolved"
        issue.resolved_by = actor_id_var.get("")
        issue.resolved_at = datetime.now(UTC)
        issue.resolution_note = resolution_note
        await self.session.flush()
        return issue

    async def list_issues(self, tenant_id: str, master_data_type: str = "",
                           status: str = "", severity: str = "",
                           page: int = 1, page_size: int = 20) -> tuple[list[MasterDataIssue], int]:
        conditions = [MasterDataIssue.tenant_id == tenant_id]
        if master_data_type:
            conditions.append(MasterDataIssue.master_data_type == master_data_type)
        if status:
            conditions.append(MasterDataIssue.status == status)
        if severity:
            conditions.append(MasterDataIssue.severity == severity)

        stmt = select(MasterDataIssue).where(*conditions).order_by(MasterDataIssue.created_at.desc())
        total_result = await self.session.execute(
            select(func.count()).select_from(MasterDataIssue).where(*conditions)
        )
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(stmt.offset(offset).limit(page_size))
        return list(result.scalars().all()), total

    async def list_rules(self, tenant_id: str, master_data_type: str = "") -> list[MasterDataRule]:
        conditions = [MasterDataRule.tenant_id == tenant_id]
        if master_data_type:
            conditions.append(MasterDataRule.master_data_type == master_data_type)
        stmt = select(MasterDataRule).where(*conditions).order_by(MasterDataRule.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def _evaluate_rule(self, rule: MasterDataRule, condition: dict,
                        record: dict) -> MasterDataIssue | None:
        record_id = record.get("id", str(uuid.uuid4()))

        if rule.rule_type == GovernanceRuleType.COMPLETENESS.value:
            required = condition.get("required_fields", [])
            for field in required:
                val = record.get(field)
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    return MasterDataIssue(
                        tenant_id=rule.tenant_id, rule_id=rule.id,
                        master_data_type=rule.master_data_type, record_id=record_id,
                        field_name=field, issue_type="missing_required",
                        severity=rule.severity,
                        message=f"Required field '{field}' is missing",
                        current_value="", expected_value="non-empty",
                        trace_id=trace_id_var.get(""),
                    )

        elif rule.rule_type == GovernanceRuleType.RANGE.value:
            field = rule.field_name
            val = record.get(field)
            valid_values = condition.get("valid_values", [])
            if valid_values and val and val not in valid_values:
                return MasterDataIssue(
                    tenant_id=rule.tenant_id, rule_id=rule.id,
                    master_data_type=rule.master_data_type, record_id=record_id,
                    field_name=field, issue_type="invalid_value",
                    severity=rule.severity,
                    message=f"Field '{field}' value '{val}' not in valid range",
                    current_value=str(val), expected_value=str(valid_values),
                    trace_id=trace_id_var.get(""),
                )

        elif rule.rule_type == GovernanceRuleType.FORMAT.value:
            field = rule.field_name
            val = record.get(field, "")
            pattern = condition.get("pattern", "")
            if pattern and val:
                import re
                if not re.match(pattern, str(val)):
                    return MasterDataIssue(
                        tenant_id=rule.tenant_id, rule_id=rule.id,
                        master_data_type=rule.master_data_type, record_id=record_id,
                        field_name=field, issue_type="format_mismatch",
                        severity=rule.severity,
                        message=f"Field '{field}' format mismatch",
                        current_value=str(val), expected_value=f"pattern: {pattern}",
                        trace_id=trace_id_var.get(""),
                    )
        return None

    async def _get_by_code(self, tenant_id: str, rule_code: str) -> MasterDataRule | None:
        stmt = select(MasterDataRule).where(
            MasterDataRule.tenant_id == tenant_id, MasterDataRule.rule_code == rule_code,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
