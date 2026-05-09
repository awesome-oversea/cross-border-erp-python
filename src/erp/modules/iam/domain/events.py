from __future__ import annotations

from dataclasses import dataclass

from erp.shared.events.domain_event import DomainEvent


@dataclass
class UserCreated(DomainEvent):
    user_id: str = ""
    username: str = ""
    email: str = ""

    def __post_init__(self):
        self.event_type = "erp.iam.user.created.v1"
        self.domain = "iam"
        self.aggregate_type = "user"


@dataclass
class UserStatusChanged(DomainEvent):
    user_id: str = ""
    username: str = ""
    from_status: str = ""
    to_status: str = ""

    def __post_init__(self):
        self.event_type = "erp.iam.user.status_changed.v1"
        self.domain = "iam"
        self.aggregate_type = "user"


@dataclass
class RoleCreated(DomainEvent):
    role_id: str = ""
    role_code: str = ""
    role_name: str = ""

    def __post_init__(self):
        self.event_type = "erp.iam.role.created.v1"
        self.domain = "iam"
        self.aggregate_type = "role"


@dataclass
class RolePermissionsChanged(DomainEvent):
    role_id: str = ""
    role_code: str = ""
    added_permissions: list = None
    removed_permissions: list = None

    def __post_init__(self):
        self.event_type = "erp.iam.role.permissions_changed.v1"
        self.domain = "iam"
        self.aggregate_type = "role"
        if self.added_permissions is None:
            self.added_permissions = []
        if self.removed_permissions is None:
            self.removed_permissions = []


@dataclass
class TenantCreated(DomainEvent):
    tenant_id: str = ""
    tenant_code: str = ""
    tenant_name: str = ""

    def __post_init__(self):
        self.event_type = "erp.iam.tenant.created.v1"
        self.domain = "iam"
        self.aggregate_type = "tenant"


@dataclass
class UserRoleAssigned(DomainEvent):
    user_id: str = ""
    role_id: str = ""
    role_code: str = ""

    def __post_init__(self):
        self.event_type = "erp.iam.user.role_assigned.v1"
        self.domain = "iam"
        self.aggregate_type = "user_role"
