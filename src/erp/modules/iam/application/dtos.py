from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PageRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    keyword: str = Field(default="")


class TenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Tenant name")
    code: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z][a-z0-9_]*$", description="Tenant code")
    plan: str = Field(default="free", pattern=r"^(free|pro|enterprise)$")
    max_users: int = Field(default=10, ge=1, le=10000)
    max_stores: int = Field(default=5, ge=1, le=1000)
    expires_at: datetime | None = None
    contact_name: str = Field(default="", max_length=100)
    contact_email: str = Field(default="", max_length=200)
    contact_phone: str = Field(default="", max_length=30)
    logo_url: str = Field(default="", max_length=500)
    config_json: str = Field(default="{}")


class TenantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    plan: str | None = Field(default=None, pattern=r"^(free|pro|enterprise)$")
    max_users: int | None = Field(default=None, ge=1, le=10000)
    max_stores: int | None = Field(default=None, ge=1, le=1000)
    expires_at: datetime | None = None
    contact_name: str | None = Field(default=None, max_length=100)
    contact_email: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=30)
    logo_url: str | None = Field(default=None, max_length=500)
    config_json: str | None = None
    status: str | None = Field(default=None, pattern=r"^(active|suspended)$")


class TenantResponse(BaseModel):
    id: str
    name: str
    code: str
    status: str
    plan: str
    max_users: int
    max_stores: int
    expires_at: datetime | None = None
    contact_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    logo_url: str = ""
    config_json: str = "{}"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TenantStatusChangeRequest(BaseModel):
    status: str = Field(..., pattern=r"^(active|suspended)$")
    reason: str = Field(default="", max_length=500)


class TenantPlanUpgradeRequest(BaseModel):
    plan: str = Field(..., pattern=r"^(free|pro|enterprise)$")
    max_users: int | None = Field(default=None, ge=1, le=10000)
    max_stores: int | None = Field(default=None, ge=1, le=1000)


class TenantQuotaResponse(BaseModel):
    tenant_id: str
    plan: str
    max_users: int
    current_users: int
    max_stores: int
    current_stores: int
    users_remaining: int
    stores_remaining: int
    can_add_users: bool
    can_add_stores: bool


class OrgCreateRequest(BaseModel):
    parent_id: str | None = None
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=50)
    org_type: str = Field(default="company", pattern=r"^(company|department|team)$")
    sort_order: int = Field(default=0, ge=0)
    leader_id: str | None = None


class OrgUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    org_type: str | None = Field(default=None, pattern=r"^(company|department|team)$")
    sort_order: int | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")
    leader_id: str | None = None


class OrgMoveRequest(BaseModel):
    new_parent_id: str | None = None


class OrgResponse(BaseModel):
    id: str
    tenant_id: str
    parent_id: str | None = None
    name: str
    code: str
    org_type: str
    path: str = ""
    level: int = 0
    sort_order: int = 0
    status: str = "active"
    leader_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class OrgMembersResponse(BaseModel):
    org_id: str
    org_name: str
    members: list[UserResponse] = []
    total: int = 0


class UserCreateRequest(BaseModel):
    org_id: str | None = None
    username: str = Field(..., min_length=3, max_length=80, pattern=r"^[a-zA-Z][a-zA-Z0-9_.]*$")
    email: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=30)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=100)
    avatar_url: str = Field(default="", max_length=500)
    user_type: str = Field(default="internal", pattern=r"^(internal|external)$")


class UserUpdateRequest(BaseModel):
    org_id: str | None = None
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    display_name: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, pattern=r"^(active|disabled|locked)$")


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    org_id: str | None = None
    username: str
    email: str = ""
    phone: str = ""
    display_name: str = ""
    avatar_url: str = ""
    status: str = "active"
    user_type: str = "internal"
    last_login_at: datetime | None = None
    must_change_pwd: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)
    must_change_pwd: bool = Field(default=True)


class UserStatusChangeRequest(BaseModel):
    status: str = Field(..., pattern=r"^(active|disabled|locked)$")
    reason: str = Field(default="", max_length=500)


class BatchUserStatusRequest(BaseModel):
    user_ids: list[str] = Field(..., min_length=1, max_length=100)
    status: str = Field(..., pattern=r"^(active|disabled)$")


class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    code: str = Field(..., min_length=1, max_length=80, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    description: str = Field(default="", max_length=500)
    role_type: str = Field(default="custom", pattern=r"^(system|custom)$")
    sort_order: int = Field(default=0, ge=0)


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")
    sort_order: int | None = Field(default=None, ge=0)


class RoleResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    code: str
    description: str = ""
    role_type: str = "custom"
    status: str = "active"
    sort_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PermissionCreateRequest(BaseModel):
    parent_id: str | None = None
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z][a-zA-Z0-9_:]*$")
    perm_type: str = Field(default="menu", pattern=r"^(menu|button|api|data)$")
    resource: str = Field(default="", max_length=200)
    action: str = Field(default="", max_length=50, pattern=r"^(read|write|delete|approve|)$")
    icon: str = Field(default="", max_length=100)
    sort_order: int = Field(default=0, ge=0)


class PermissionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    perm_type: str | None = Field(default=None, pattern=r"^(menu|button|api|data)$")
    resource: str | None = Field(default=None, max_length=200)
    action: str | None = Field(default=None, max_length=50)
    icon: str | None = Field(default=None, max_length=100)
    sort_order: int | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class PermissionResponse(BaseModel):
    id: str
    parent_id: str | None = None
    name: str
    code: str
    perm_type: str = "menu"
    resource: str = ""
    action: str = ""


class UserPermissionsResponse(BaseModel):
    user_id: str
    roles: list[RoleResponse] = []
    permissions: list[PermissionResponse] = []
    permission_codes: list[str] = []


class RolePermissionsDetailResponse(BaseModel):
    role: RoleResponse
    permissions: list[PermissionResponse] = []
    permission_codes: list[str] = []


class AssignRoleRequest(BaseModel):
    role_ids: list[str] = Field(..., min_length=1)


class AssignPermissionRequest(BaseModel):
    permission_ids: list[str] = Field(..., min_length=1)


class AuditLogResponse(BaseModel):
    id: str
    tenant_id: str
    actor_id: str
    actor_type: str = "user"
    action: str
    resource_type: str = ""
    resource_id: str = ""
    detail: str = ""
    ip_address: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AuditStatsResponse(BaseModel):
    total: int = 0
    by_action: dict[str, int] = {}
    by_module: dict[str, int] = {}
    by_date: dict[str, int] = {}


class PositionCreateRequest(BaseModel):
    org_id: str = Field(..., min_length=1, description="所属组织ID")
    name: str = Field(..., min_length=1, max_length=100, description="岗位名称")
    code: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$", description="岗位编码")
    level: int = Field(default=1, ge=1, le=20, description="岗位层级，数字越大级别越高")
    sort_order: int = Field(default=0, ge=0, description="排序序号")


class PositionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100, description="岗位名称")
    level: int | None = Field(default=None, ge=1, le=20, description="岗位层级")
    sort_order: int | None = Field(default=None, ge=0, description="排序序号")
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$", description="状态")


class PositionResponse(BaseModel):
    id: str
    tenant_id: str
    org_id: str
    name: str
    code: str
    level: int = 1
    sort_order: int = 0
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserPositionAssignRequest(BaseModel):
    position_id: str = Field(..., min_length=1, description="岗位ID")
    is_primary: bool = Field(default=False, description="是否设为主岗")


class UserPositionResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    position_id: str
    is_primary: bool = False
    position_name: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ObjectPermissionGrantRequest(BaseModel):
    subject_type: str = Field(..., pattern=r"^(user|role|position|org)$", description="主体类型")
    subject_id: str = Field(..., min_length=1, description="主体ID")
    resource_type: str = Field(..., min_length=1, max_length=50, description="资源类型")
    resource_id: str = Field(..., min_length=1, description="资源实例ID")
    action: str = Field(default="read", pattern=r"^(read|write|delete|approve)$", description="操作类型")
    effect: str = Field(default="allow", pattern=r"^(allow|deny)$", description="效果: allow/deny")
    conditions_json: str = Field(default="{}", description="附加条件JSON")


class ObjectPermissionResponse(BaseModel):
    id: str
    tenant_id: str
    subject_type: str
    subject_id: str
    resource_type: str
    resource_id: str
    action: str = "read"
    effect: str = "allow"
    conditions_json: str = "{}"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class DataPermissionRuleCreateRequest(BaseModel):
    role_id: str | None = Field(default=None, description="角色ID，与user_id二选一")
    user_id: str | None = Field(default=None, description="用户ID，与role_id二选一")
    dimension: str = Field(
        ..., pattern=r"^(tenant|org|department|store|marketplace|channel|warehouse|supplier|category|data_level)$",
        description="数据权限维度"
    )
    allowed_values_json: str = Field(default="[]", description="允许的值列表JSON")
    priority: int = Field(default=0, ge=0, description="优先级，数字越大优先级越高")


class DataPermissionRuleUpdateRequest(BaseModel):
    allowed_values_json: str | None = Field(default=None, description="允许的值列表JSON")
    priority: int | None = Field(default=None, ge=0, description="优先级")
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$", description="状态")


class DataPermissionRuleResponse(BaseModel):
    id: str
    tenant_id: str
    role_id: str | None = None
    user_id: str | None = None
    dimension: str
    allowed_values_json: str = "[]"
    priority: int = 0
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
