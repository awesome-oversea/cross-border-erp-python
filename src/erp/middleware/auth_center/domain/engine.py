from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Permission:
    code: str = ""
    name: str = ""
    module: str = ""
    action: str = ""
    description: str = ""


@dataclass
class Role:
    role_id: str = ""
    role_code: str = ""
    role_name: str = ""
    description: str = ""
    permissions: list[str] = field(default_factory=list)
    is_active: bool = True


@dataclass
class UserPermissionCache:
    user_id: str = ""
    tenant_id: str = ""
    role_codes: list[str] = field(default_factory=list)
    permission_codes: list[str] = field(default_factory=list)
    data_scopes: dict = field(default_factory=dict)
    cached_at: str = ""


class AuthCenterEngine:
    def __init__(self):
        self._permissions: dict[str, Permission] = {}
        self._roles: dict[str, Role] = {}
        self._user_caches: dict[str, UserPermissionCache] = {}
        self._register_default_permissions()
        self._register_default_roles()

    def _register_default_permissions(self):
        defaults = [
            ("iam:user:read", "查看用户", "iam", "read"),
            ("iam:user:write", "编辑用户", "iam", "write"),
            ("iam:role:read", "查看角色", "iam", "read"),
            ("iam:role:write", "编辑角色", "iam", "write"),
            ("pdm:product:read", "查看产品", "pdm", "read"),
            ("pdm:product:write", "编辑产品", "pdm", "write"),
            ("oms:order:read", "查看订单", "oms", "read"),
            ("oms:order:write", "编辑订单", "oms", "write"),
            ("wms:inventory:read", "查看库存", "wms", "read"),
            ("wms:inventory:write", "编辑库存", "wms", "write"),
            ("fms:finance:read", "查看财务", "fms", "read"),
            ("fms:finance:write", "编辑财务", "fms", "write"),
            ("scm:purchase:read", "查看采购", "scm", "read"),
            ("scm:purchase:write", "编辑采购", "scm", "write"),
            ("sys:config:read", "查看配置", "sys", "read"),
            ("sys:config:write", "编辑配置", "sys", "write"),
        ]
        for code, name, module, action in defaults:
            self._permissions[code] = Permission(code=code, name=name, module=module, action=action)

    def _register_default_roles(self):
        self._roles["admin"] = Role(role_id=str(uuid.uuid4()), role_code="admin", role_name="管理员",
                                     permissions=list(self._permissions.keys()))
        self._roles["operator"] = Role(role_id=str(uuid.uuid4()), role_code="operator", role_name="运营人员",
                                        permissions=["pdm:product:read", "oms:order:read", "oms:order:write",
                                                     "wms:inventory:read", "scm:purchase:read"])
        self._roles["viewer"] = Role(role_id=str(uuid.uuid4()), role_code="viewer", role_name="只读用户",
                                      permissions=[p for p in self._permissions if p.endswith(":read")])

    def check_permission(self, user_id: str, permission_code: str) -> dict:
        cache = self._user_caches.get(user_id)
        if not cache:
            return {"has_permission": False, "reason": "User cache not found"}
        has = permission_code in cache.permission_codes
        return {"has_permission": has, "user_id": user_id, "permission_code": permission_code}

    def get_user_permissions(self, user_id: str) -> dict:
        cache = self._user_caches.get(user_id)
        if not cache:
            return {"user_id": user_id, "roles": [], "permissions": [], "data_scopes": {}}
        return {"user_id": user_id, "roles": cache.role_codes,
                "permissions": cache.permission_codes, "data_scopes": cache.data_scopes}

    def refresh_cache(self, user_id: str, tenant_id: str, role_codes: list[str],
                       data_scopes: dict | None = None) -> dict:
        all_permissions: list[str] = []
        for rc in role_codes:
            role = self._roles.get(rc)
            if role:
                all_permissions.extend(role.permissions)
        unique_permissions = list(set(all_permissions))
        cache = UserPermissionCache(
            user_id=user_id, tenant_id=tenant_id, role_codes=role_codes,
            permission_codes=unique_permissions, data_scopes=data_scopes or {},
            cached_at=datetime.now(UTC).isoformat(),
        )
        self._user_caches[user_id] = cache
        return {"user_id": user_id, "roles": role_codes, "permission_count": len(unique_permissions)}

    def list_permissions(self, module: str = "") -> list[dict]:
        results = list(self._permissions.values())
        if module:
            results = [p for p in results if p.module == module]
        return [{"code": p.code, "name": p.name, "module": p.module, "action": p.action} for p in results]

    def list_roles(self) -> list[dict]:
        return [{"role_id": r.role_id, "role_code": r.role_code, "role_name": r.role_name,
                 "permission_count": len(r.permissions), "is_active": r.is_active} for r in self._roles.values()]
