from __future__ import annotations

import re


class DataMasker:
    PATTERNS = {
        "phone": (re.compile(r"(\d{3})\d{4}(\d{4})"), r"\1****\2"),
        "email": (re.compile(r"(.{2}).*(@.*)"), r"\1***\2"),
        "id_card": (re.compile(r"(\d{4})\d{10}(\d{4})"), r"\1**********\2"),
        "bank_card": (re.compile(r"(\d{4})\d{8,12}(\d{4})"), r"\1********\2"),
        "name": (re.compile(r"(.).+"), r"\1**"),
        "address": (re.compile(r"(.{6}).+"), r"\1***"),
        "api_key": (re.compile(r"(.{4}).+(.{4})"), r"\1****\2"),
        "token": (re.compile(r"(.{8}).+"), r"\1****"),
    }

    @classmethod
    def mask(cls, value: str, field_type: str = "default") -> str:
        if not value or len(value) < 3:
            return value
        if field_type in cls.PATTERNS:
            pattern, replacement = cls.PATTERNS[field_type]
            return pattern.sub(replacement, value)
        if len(value) <= 8:
            return value[:2] + "*" * (len(value) - 2)
        return value[:4] + "****" + value[-4:]

    @classmethod
    def mask_dict(cls, data: dict, sensitive_fields: dict[str, str] | None = None) -> dict:
        if not sensitive_fields:
            sensitive_fields = {
                "phone": "phone",
                "email": "email",
                "id_card": "id_card",
                "bank_card": "bank_card",
                "address": "address",
                "api_key": "api_key",
                "access_token": "token",
                "secret_key": "api_key",
                "password": "token",
                "password_hash": "token",
            }
        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = cls.mask_dict(value, sensitive_fields)
            elif isinstance(value, list):
                result[key] = [
                    cls.mask_dict(item, sensitive_fields) if isinstance(item, dict) else item
                    for item in value
                ]
            elif isinstance(value, str) and key in sensitive_fields:
                result[key] = cls.mask(value, sensitive_fields[key])
            else:
                result[key] = value
        return result


class DataEncryption:
    @staticmethod
    def encrypt_field(value: str, key: str = "") -> str:
        import base64
        return base64.b64encode(value.encode("utf-8")).decode("utf-8")

    @staticmethod
    def decrypt_field(value: str, key: str = "") -> str:
        import base64
        return base64.b64decode(value.encode("utf-8")).decode("utf-8")


class ExportAuditor:
    _exports: list[dict] = []

    @classmethod
    def log_export(
        cls,
        tenant_id: str,
        user_id: str,
        export_type: str,
        record_count: int,
        fields: list[str],
        trace_id: str = "",
    ) -> dict:
        entry = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "export_type": export_type,
            "record_count": record_count,
            "fields": fields,
            "trace_id": trace_id,
        }
        cls._exports.append(entry)
        return entry

    @classmethod
    def get_exports(cls, tenant_id: str = "") -> list[dict]:
        if tenant_id:
            return [e for e in cls._exports if e["tenant_id"] == tenant_id]
        return cls._exports
