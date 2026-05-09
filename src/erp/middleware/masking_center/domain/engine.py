from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class MaskingRule:
    rule_id: str = ""
    rule_code: str = ""
    rule_name: str = ""
    field_type: str = ""
    pattern: str = ""
    replacement: str = ""
    is_active: bool = True
    description: str = ""


@dataclass
class MaskingAuditRecord:
    id: str = ""
    tenant_id: str = ""
    rule_code: str = ""
    field_name: str = ""
    original_length: int = 0
    masked_length: int = 0
    operator_id: str = ""
    created_at: str = ""


class MaskingCenterEngine:
    def __init__(self):
        self._rules: dict[str, MaskingRule] = {}
        self._audit_records: list[MaskingAuditRecord] = []
        self._register_default_rules()

    def _register_default_rules(self):
        defaults = [
            ("phone", "手机号脱敏", "phone", r"(\d{3})\d{4}(\d{4})", r"\1****\2"),
            ("email", "邮箱脱敏", "email", r"(.{2}).*(@.*)", r"\1***\2"),
            ("id_card", "身份证脱敏", "id_card", r"(\d{4})\d{10}(\d{4})", r"\1**********\2"),
            ("bank_card", "银行卡脱敏", "bank_card", r"(\d{4})\d{8,12}(\d{4})", r"\1********\2"),
            ("name", "姓名脱敏", "name", r"(.).+", r"\1**"),
            ("address", "地址脱敏", "address", r"(.{6}).+", r"\1***"),
            ("api_key", "API密钥脱敏", "api_key", r"(.{4}).+(.{4})", r"\1****\2"),
            ("token", "令牌脱敏", "token", r"(.{8}).+", r"\1****"),
        ]
        for code, name, field_type, pattern, replacement in defaults:
            self._rules[code] = MaskingRule(
                rule_id=str(uuid.uuid4()), rule_code=code, rule_name=name,
                field_type=field_type, pattern=pattern, replacement=replacement,
            )

    def mask_value(self, value: str, field_type: str = "default") -> str:
        if not value or len(value) < 3:
            return value
        rule = self._rules.get(field_type)
        if rule and rule.is_active:
            try:
                return re.sub(rule.pattern, rule.replacement, value)
            except re.error:
                pass
        if len(value) <= 8:
            return value[:2] + "*" * (len(value) - 2)
        return value[:4] + "****" + value[-4:]

    def mask_dict(self, data: dict, field_mapping: dict[str, str] | None = None,
                   tenant_id: str = "", operator_id: str = "") -> dict:
        if not field_mapping:
            field_mapping = {
                "phone": "phone", "email": "email", "id_card": "id_card",
                "bank_card": "bank_card", "address": "address",
                "api_key": "api_key", "access_token": "token",
                "secret_key": "api_key", "password": "token",
            }
        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = self.mask_dict(value, field_mapping, tenant_id, operator_id)
            elif isinstance(value, list):
                result[key] = [self.mask_dict(item, field_mapping, tenant_id, operator_id)
                               if isinstance(item, dict) else item for item in value]
            elif isinstance(value, str) and key in field_mapping:
                masked = self.mask_value(value, field_mapping[key])
                result[key] = masked
                if tenant_id and masked != value:
                    self._audit_records.append(MaskingAuditRecord(
                        id=str(uuid.uuid4()), tenant_id=tenant_id,
                        rule_code=field_mapping[key], field_name=key,
                        original_length=len(value), masked_length=len(masked),
                        operator_id=operator_id,
                        created_at=datetime.now(UTC).isoformat(),
                    ))
            else:
                result[key] = value
        return result

    def get_rules(self) -> list[dict]:
        return [{"rule_id": r.rule_id, "rule_code": r.rule_code, "rule_name": r.rule_name,
                 "field_type": r.field_type, "is_active": r.is_active, "description": r.description}
                for r in self._rules.values()]

    def create_rule(self, rule_code: str, rule_name: str, field_type: str,
                     pattern: str, replacement: str, description: str = "") -> dict:
        rule = MaskingRule(
            rule_id=str(uuid.uuid4()), rule_code=rule_code, rule_name=rule_name,
            field_type=field_type, pattern=pattern, replacement=replacement,
            description=description,
        )
        self._rules[rule_code] = rule
        return {"rule_id": rule.rule_id, "rule_code": rule.rule_code, "rule_name": rule.rule_name}

    def get_audit_records(self, tenant_id: str, limit: int = 50) -> list[dict]:
        records = [r for r in self._audit_records if r.tenant_id == tenant_id]
        return [{"id": r.id, "rule_code": r.rule_code, "field_name": r.field_name,
                 "original_length": r.original_length, "masked_length": r.masked_length,
                 "operator_id": r.operator_id, "created_at": r.created_at}
                for r in records[-limit:]]
