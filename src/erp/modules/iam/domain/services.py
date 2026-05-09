from __future__ import annotations

import re

TENANT_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "active": ["suspended"],
    "suspended": ["active", "deleted"],
    "deleted": [],
}

USER_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "active": ["disabled", "locked"],
    "disabled": ["active"],
    "locked": ["active"],
    "pending": ["active", "disabled"],
}

VALID_PLANS = {"free", "pro", "enterprise"}
PLAN_LIMITS: dict[str, dict] = {
    "free": {"max_users": 10, "max_stores": 5},
    "pro": {"max_users": 50, "max_stores": 20},
    "enterprise": {"max_users": 999999, "max_stores": 999999},
}

PASSWORD_MIN_LENGTH = 8
PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$")


class TenantDomainService:
    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        return target_status in TENANT_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_plan(plan: str) -> bool:
        return plan in VALID_PLANS

    @staticmethod
    def get_plan_limits(plan: str) -> dict:
        return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])

    @staticmethod
    def can_add_users(current_count: int, plan: str) -> bool:
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
        return current_count < limits["max_users"]

    @staticmethod
    def can_add_stores(current_count: int, plan: str) -> bool:
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
        return current_count < limits["max_stores"]


class UserDomainService:
    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        return target_status in USER_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_password(password: str) -> list[str]:
        errors: list[str] = []
        if len(password) < PASSWORD_MIN_LENGTH:
            errors.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
        if not PASSWORD_PATTERN.match(password):
            errors.append("Password must contain uppercase, lowercase, and digit")
        return errors

    @staticmethod
    def validate_email(email: str) -> bool:
        pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
        return bool(pattern.match(email))

    @staticmethod
    def is_active(status: str) -> bool:
        return status == "active"


class RoleDomainService:
    @staticmethod
    def validate_permission_code(code: str) -> bool:
        parts = code.split(":")
        if len(parts) < 2:
            return False
        return all(len(p) > 0 for p in parts)

    @staticmethod
    def is_admin_role(role_code: str) -> bool:
        return role_code in ("super_admin", "admin", "tenant_admin")
