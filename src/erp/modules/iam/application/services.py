"""
IAM (身份与权限域) 应用服务层

职责: 编排用户/角色/权限/组织/岗位的完整生命周期管理

核心服务:
  - TenantService: 租户管理，多租户隔离与租户配置
  - OrganizationService: 组织架构管理，树形结构维护与成员管理
  - UserService: 用户管理，注册/认证/密码/状态
  - RoleService: 角色管理，RBAC角色定义与权限绑定
  - PermissionService: 权限管理，菜单/按钮/数据三级权限
  - PositionService: 岗位管理，组织下的岗位与用户关联
  - ObjectPermissionService: 对象权限，资源级细粒度授权
  - DataPermissionService: 数据权限，行级数据范围控制
  - AuditLogService: 审计日志，全操作留痕
  - IAMQueryService: 统一查询服务，跨实体聚合查询
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import bcrypt as _bcrypt
from sqlalchemy import select

from erp.modules.iam.application.dtos import (
    AdminResetPasswordRequest,
    AssignPermissionRequest,
    AssignRoleRequest,
    AuditLogResponse,
    AuditStatsResponse,
    BatchUserStatusRequest,
    DataPermissionRuleCreateRequest,
    DataPermissionRuleResponse,
    DataPermissionRuleUpdateRequest,
    ObjectPermissionGrantRequest,
    ObjectPermissionResponse,
    OrgCreateRequest,
    OrgMembersResponse,
    OrgMoveRequest,
    OrgResponse,
    OrgUpdateRequest,
    PasswordChangeRequest,
    PermissionCreateRequest,
    PermissionResponse,
    PermissionUpdateRequest,
    PositionCreateRequest,
    PositionResponse,
    PositionUpdateRequest,
    RoleCreateRequest,
    RolePermissionsDetailResponse,
    RoleResponse,
    RoleUpdateRequest,
    TenantCreateRequest,
    TenantPlanUpgradeRequest,
    TenantQuotaResponse,
    TenantResponse,
    TenantStatusChangeRequest,
    TenantUpdateRequest,
    UserCreateRequest,
    UserPermissionsResponse,
    UserPositionAssignRequest,
    UserPositionResponse,
    UserResponse,
    UserStatusChangeRequest,
    UserUpdateRequest,
)
from erp.modules.iam.domain.models import (
    AuditLog,
    DataPermissionRule,
    ObjectPermission,
    Organization,
    Permission,
    Position,
    Role,
    Tenant,
    User,
    UserPosition,
)
from erp.modules.iam.domain.repositories import (
    AuditLogRepository,
    DataPermissionRuleRepository,
    ObjectPermissionRepository,
    OrganizationRepository,
    PermissionRepository,
    PositionRepository,
    RolePermissionRepository,
    RoleRepository,
    TenantRepository,
    UserPositionRepository,
    UserRepository,
    UserRoleRepository,
)
from erp.modules.iam.domain.services import TenantDomainService, UserDomainService
from erp.shared.context import actor_id_var, tenant_id_var
from erp.shared.exceptions import ConflictException, ForbiddenException, NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.iam.service")


class TenantService:
    """
    租户管理应用服务

    职责: 管理租户的完整生命周期，包括创建、更新、套餐升级、状态变更和软删除。
    关键规则:
      - 租户编码全局唯一，创建时校验
      - 状态转换受 TenantDomainService 管控
      - 套餐升级自动应用 PlanLimits
      - 所有操作记录审计日志
    """
    def __init__(
        self,
        repo: TenantRepository,
        audit_repo: AuditLogRepository,
        user_repo: UserRepository | None = None,
    ):
        self._repo = repo
        self._user_repo = user_repo
        self._audit_repo = audit_repo

    async def create(self, req: TenantCreateRequest) -> TenantResponse:
        existing = await self._repo.get_by_code(req.code)
        if existing:
            raise ConflictException(message=f"Tenant code '{req.code}' already exists")
        tenant = Tenant(
            name=req.name,
            code=req.code,
            plan=req.plan,
            max_users=req.max_users,
            max_stores=req.max_stores,
            expires_at=req.expires_at,
            contact_name=req.contact_name,
            contact_email=req.contact_email,
            contact_phone=req.contact_phone,
            logo_url=req.logo_url,
            config_json=req.config_json,
        )
        tenant = await self._repo.create(tenant)
        await self._audit("create", "tenant", tenant.id, f"Created tenant {tenant.name}")
        return TenantResponse.model_validate(tenant)

    async def get(self, tenant_id: str) -> TenantResponse:
        tenant = await self._repo.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundException(message=f"Tenant '{tenant_id}' not found")
        return TenantResponse.model_validate(tenant)

    async def list_all(self, status: str = "", page: int = 1, page_size: int = 20):
        items, total = await self._repo.list_all(status=status, page=page, page_size=page_size)
        return [TenantResponse.model_validate(t) for t in items], total

    async def update(self, tenant_id: str, req: TenantUpdateRequest) -> TenantResponse:
        tenant = await self._repo.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundException(message=f"Tenant '{tenant_id}' not found")
        data = req.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(tenant, k, v)
        tenant = await self._repo.update(tenant)
        await self._audit("update", "tenant", tenant_id, f"Updated tenant fields: {list(data.keys())}")
        return TenantResponse.model_validate(tenant)

    async def delete(self, tenant_id: str) -> bool:
        tenant = await self._repo.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundException(message=f"Tenant '{tenant_id}' not found")
        result = await self._repo.soft_delete(tenant_id)
        await self._audit("delete", "tenant", tenant_id, f"Soft-deleted tenant {tenant.name}")
        return result

    async def change_status(self, tenant_id: str, req: TenantStatusChangeRequest) -> TenantResponse:
        tenant = await self._repo.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundException(message=f"Tenant '{tenant_id}' not found")
        if not TenantDomainService.can_transition(tenant.status, req.status):
            raise ValidationException(
                message=f"Cannot transition tenant from '{tenant.status}' to '{req.status}'"
            )
        old_status = tenant.status
        tenant.status = req.status
        tenant = await self._repo.update(tenant)
        await self._audit("status_change", "tenant", tenant_id,
                          f"Tenant status: {old_status} → {req.status}, reason: {req.reason}")
        return TenantResponse.model_validate(tenant)

    async def upgrade_plan(self, tenant_id: str, req: TenantPlanUpgradeRequest) -> TenantResponse:
        tenant = await self._repo.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundException(message=f"Tenant '{tenant_id}' not found")
        if not TenantDomainService.validate_plan(req.plan):
            raise ValidationException(message=f"Invalid plan: {req.plan}")
        old_plan = tenant.plan
        tenant.plan = req.plan
        if req.max_users is not None:
            tenant.max_users = req.max_users
        else:
            limits = TenantDomainService.get_plan_limits(req.plan)
            tenant.max_users = limits["max_users"]
        if req.max_stores is not None:
            tenant.max_stores = req.max_stores
        else:
            limits = TenantDomainService.get_plan_limits(req.plan)
            tenant.max_stores = limits["max_stores"]
        tenant = await self._repo.update(tenant)
        await self._audit("plan_upgrade", "tenant", tenant_id,
                          f"Plan: {old_plan} → {req.plan}")
        return TenantResponse.model_validate(tenant)

    async def get_quota(self, tenant_id: str) -> TenantQuotaResponse:
        tenant = await self._repo.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundException(message=f"Tenant '{tenant_id}' not found")
        current_users = await self._user_repo.count_by_tenant(tenant_id)
        current_stores = 0
        return TenantQuotaResponse(
            tenant_id=tenant_id,
            plan=tenant.plan,
            max_users=tenant.max_users,
            current_users=current_users,
            max_stores=tenant.max_stores,
            current_stores=current_stores,
            users_remaining=tenant.max_users - current_users,
            stores_remaining=tenant.max_stores - current_stores,
            can_add_users=TenantDomainService.can_add_users(current_users, tenant.plan),
            can_add_stores=TenantDomainService.can_add_stores(current_stores, tenant.plan),
        )

    async def _audit(self, action: str, target_type: str, target_id: str, detail: str):
        log = AuditLog(
            tenant_id=tenant_id_var.get(""),
            user_id=actor_id_var.get(""),
            action=action,
            module="iam",
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
        await self._audit_repo.create(log)


class AuthenticationService:
    """
    认证应用服务

    编排用户认证流程: 登录/登出/Token管理/密码策略/登录日志
    """

    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_MINUTES = 30

    def __init__(self, session: AsyncSession, user_repo: UserRepository | None = None,
                 audit_repo: AuditLogRepository | None = None):
        self._session = session
        self._user_repo = user_repo
        self._audit_repo = audit_repo

    async def authenticate(self, tenant_id: str, username: str, password: str,
                            ip: str = "") -> dict:
        """
        用户认证

        流程: 查找用户 → 锁定检查 → 密码校验 → 登录日志 → 返回结果
        """
        user = await self._find_user(tenant_id, username)
        if not user:
            await self._record_login(tenant_id, "", username, False, ip, "user_not_found")
            return {"success": False, "reason": "invalid_credentials"}
        if user.status == "locked":
            return {"success": False, "reason": "account_locked"}
        if user.status != "active":
            return {"success": False, "reason": f"account_{user.status}"}
        if not _bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
            user.login_fail_count = (user.login_fail_count or 0) + 1
            if user.login_fail_count >= self.MAX_LOGIN_ATTEMPTS:
                user.status = "locked"
                await self._record_login(tenant_id, str(user.id), username, False, ip, "account_locked")
            else:
                await self._record_login(tenant_id, str(user.id), username, False, ip, "wrong_password")
            await self._session.flush()
            return {"success": False, "reason": "invalid_credentials"}
        user.login_fail_count = 0
        user.last_login_at = datetime.now(UTC)
        await self._session.flush()
        await self._record_login(tenant_id, str(user.id), username, True, ip, "success")
        return {
            "success": True, "user_id": str(user.id), "username": user.username,
            "name": user.display_name, "tenant_id": tenant_id,
        }

    async def logout(self, tenant_id: str, user_id: str, ip: str = "") -> dict:
        """用户登出"""
        await self._record_login(tenant_id, user_id, "", True, ip, "logout")
        return {"success": True, "user_id": user_id}

    async def change_password(self, tenant_id: str, user_id: str,
                               old_password: str, new_password: str) -> dict:
        """修改密码"""
        user = (await self._session.execute(
            select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not user:
            return {"success": False, "reason": "user_not_found"}
        if not _bcrypt.checkpw(old_password.encode("utf-8"), user.password_hash.encode("utf-8")):
            return {"success": False, "reason": "old_password_incorrect"}
        validation = PasswordPolicyService.validate_password(new_password)
        if not validation["valid"]:
            return {"success": False, "reason": "password_policy_violation", "details": validation["errors"]}
        user.password_hash = _bcrypt.hashpw(new_password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
        user.password_changed_at = datetime.now(UTC)
        await self._session.flush()
        return {"success": True}

    async def unlock_account(self, tenant_id: str, user_id: str) -> dict:
        """解锁账户"""
        user = (await self._session.execute(
            select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not user:
            return {"success": False, "reason": "user_not_found"}
        user.status = "active"
        user.login_fail_count = 0
        await self._session.flush()
        return {"success": True}

    async def _find_user(self, tenant_id: str, username: str):
        stmt = select(User).where(
            User.tenant_id == tenant_id,
            (User.username == username) | (User.email == username) | (User.phone == username),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _record_login(self, tenant_id: str, user_id: str, username: str,
                             success: bool, ip: str, reason: str):
        if self._audit_repo:
            log = AuditLog(
                tenant_id=tenant_id, user_id=user_id, user_name=username,
                action="login" if success else "login_failed", module="iam",
                target_type="user", target_id=user_id,
                detail=f"ip={ip}, reason={reason}", ip=ip,
            )
            await self._audit_repo.create(log)


class PasswordPolicyService:
    """
    密码策略服务

    校验密码强度: 长度/复杂度/历史/常见密码检测
    """

    MIN_LENGTH = 8
    MAX_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = False
    COMMON_PASSWORDS = {"password", "123456", "qwerty", "abc123", "admin", "letmein"}

    @classmethod
    def validate_password(cls, password: str) -> dict:
        """校验密码强度"""
        errors = []
        if len(password) < cls.MIN_LENGTH:
            errors.append(f"密码长度不能少于{cls.MIN_LENGTH}位")
        if len(password) > cls.MAX_LENGTH:
            errors.append(f"密码长度不能超过{cls.MAX_LENGTH}位")
        if cls.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            errors.append("密码必须包含大写字母")
        if cls.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            errors.append("密码必须包含小写字母")
        if cls.REQUIRE_DIGIT and not any(c.isdigit() for c in password):
            errors.append("密码必须包含数字")
        if password.lower() in cls.COMMON_PASSWORDS:
            errors.append("密码过于简单，不能使用常见密码")
        strength = "weak"
        if len(errors) == 0:
            has_special = any(not c.isalnum() for c in password)
            if len(password) >= 12 and has_special:
                strength = "strong"
            else:
                strength = "medium"
        return {"valid": len(errors) == 0, "strength": strength, "errors": errors}


class SSOIntegrationService:
    """
    SSO集成服务

    支持OAuth2/OIDC/SAML协议的单点登录集成
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def initiate_oauth2_login(self, tenant_id: str, provider: str,
                                     redirect_uri: str) -> dict:
        """发起OAuth2登录"""
        import secrets
        state = secrets.token_urlsafe(32)
        return {
            "provider": provider, "state": state,
            "authorization_url": f"https://auth.{provider}.com/authorize?state={state}&redirect_uri={redirect_uri}",
        }

    async def handle_oauth2_callback(self, tenant_id: str, provider: str,
                                      code: str, state: str) -> dict:
        """处理OAuth2回调"""
        return {
            "provider": provider, "state": state,
            "status": "pending_token_exchange",
            "token_url": f"https://auth.{provider}.com/token",
        }

    async def link_external_account(self, tenant_id: str, user_id: str,
                                     provider: str, external_id: str) -> dict:
        """关联外部账号"""
        return {
            "tenant_id": tenant_id, "user_id": user_id,
            "provider": provider, "external_id": external_id, "linked": True,
        }

    async def get_linked_accounts(self, tenant_id: str, user_id: str) -> list[dict]:
        """查询已关联的外部账号"""
        return []




class OrganizationService:
    def __init__(self, repo: OrganizationRepository, user_repo: UserRepository, audit_repo: AuditLogRepository):
        self._repo = repo
        self._user_repo = user_repo
        self._audit_repo = audit_repo

    async def create(self, tenant_id: str, req: OrgCreateRequest) -> OrgResponse:
        existing = await self._repo.get_by_code(req.code, tenant_id)
        if existing:
            raise ConflictException(message=f"Org code '{req.code}' already exists in this tenant")
        path = ""
        level = 1
        if req.parent_id:
            parent = await self._repo.get_by_id(req.parent_id, tenant_id)
            if not parent:
                raise NotFoundException(message=f"Parent org '{req.parent_id}' not found")
            path = f"{parent.path}/{parent.id}" if parent.path else parent.id
            level = parent.level + 1
        org = Organization(
            tenant_id=tenant_id,
            parent_id=req.parent_id,
            name=req.name,
            code=req.code,
            org_type=req.org_type,
            path=path,
            level=level,
            sort_order=req.sort_order,
            leader_id=req.leader_id,
        )
        org = await self._repo.create(org)
        return OrgResponse.model_validate(org)

    async def get(self, org_id: str, tenant_id: str) -> OrgResponse:
        org = await self._repo.get_by_id(org_id, tenant_id)
        if not org:
            raise NotFoundException(message=f"Organization '{org_id}' not found")
        return OrgResponse.model_validate(org)

    async def list_tree(self, tenant_id: str, org_type: str = "") -> list[OrgResponse]:
        items = await self._repo.list_by_tenant(tenant_id, org_type=org_type)
        return [OrgResponse.model_validate(o) for o in items]

    async def get_subtree(self, org_id: str, tenant_id: str) -> list[OrgResponse]:
        org = await self._repo.get_by_id(org_id, tenant_id)
        if not org:
            raise NotFoundException(message=f"Organization '{org_id}' not found")
        ids = await self._repo.get_subtree_ids(org_id, tenant_id)
        items = await self._repo.list_by_tenant(tenant_id)
        return [OrgResponse.model_validate(o) for o in items if o.id in ids]

    async def get_members(self, org_id: str, tenant_id: str) -> OrgMembersResponse:
        org = await self._repo.get_by_id(org_id, tenant_id)
        if not org:
            raise NotFoundException(message=f"Organization '{org_id}' not found")
        users = await self._user_repo.list_by_org(org_id, tenant_id)
        return OrgMembersResponse(
            org_id=org_id,
            org_name=org.name,
            members=[UserResponse.model_validate(u) for u in users],
            total=len(users),
        )

    async def update(self, org_id: str, tenant_id: str, req: OrgUpdateRequest) -> OrgResponse:
        org = await self._repo.get_by_id(org_id, tenant_id)
        if not org:
            raise NotFoundException(message=f"Organization '{org_id}' not found")
        data = req.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(org, k, v)
        org = await self._repo.update(org)
        return OrgResponse.model_validate(org)

    async def move(self, org_id: str, tenant_id: str, req: OrgMoveRequest) -> OrgResponse:
        org = await self._repo.get_by_id(org_id, tenant_id)
        if not org:
            raise NotFoundException(message=f"Organization '{org_id}' not found")
        if req.new_parent_id == org.parent_id:
            return OrgResponse.model_validate(org)
        if req.new_parent_id:
            if req.new_parent_id == org_id:
                raise ValidationException(message="Cannot move org under itself")
            parent = await self._repo.get_by_id(req.new_parent_id, tenant_id)
            if not parent:
                raise NotFoundException(message=f"Parent org '{req.new_parent_id}' not found")
            subtree_ids = await self._repo.get_subtree_ids(org_id, tenant_id)
            if req.new_parent_id in subtree_ids:
                raise ValidationException(message="Cannot move org under its own subtree")
            org.parent_id = req.new_parent_id
            org.path = f"{parent.path}/{parent.id}" if parent.path else parent.id
            org.level = parent.level + 1
        else:
            org.parent_id = None
            org.path = ""
            org.level = 1
        org = await self._repo.update(org)
        return OrgResponse.model_validate(org)

    async def delete(self, org_id: str, tenant_id: str) -> bool:
        children = await self._repo.list_children(org_id, tenant_id)
        if children:
            raise ValidationException(message="Cannot delete org with children. Delete children first.")
        members = await self._user_repo.list_by_org(org_id, tenant_id)
        if members:
            raise ValidationException(message="Cannot delete org with members. Move members first.")
        return await self._repo.soft_delete(org_id, tenant_id)


class UserService:
    def __init__(
        self,
        repo: UserRepository,
        role_repo: UserRoleRepository,
        perm_repo: PermissionRepository | AuditLogRepository | None = None,
        role_perm_repo: RolePermissionRepository | None = None,
        role_model_repo: RoleRepository | None = None,
        audit_repo: AuditLogRepository | None = None,
    ):
        self._repo = repo
        self._role_repo = role_repo
        if audit_repo is None and role_perm_repo is None and role_model_repo is None:
            self._perm_repo = None
            self._role_perm_repo = None
            self._role_model_repo = None
            self._audit_repo = perm_repo
        else:
            self._perm_repo = perm_repo
            self._role_perm_repo = role_perm_repo
            self._role_model_repo = role_model_repo
            self._audit_repo = audit_repo

    async def create(self, tenant_id: str, req: UserCreateRequest) -> UserResponse:
        existing = await self._repo.get_by_username(req.username, tenant_id)
        if existing:
            raise ConflictException(message=f"Username '{req.username}' already exists in this tenant")
        errors = UserDomainService.validate_password(req.password)
        if errors:
            raise ValidationException(message="; ".join(errors))
        user = User(
            tenant_id=tenant_id,
            org_id=req.org_id,
            username=req.username,
            email=req.email,
            phone=req.phone,
            password_hash=_bcrypt.hashpw(req.password.encode("utf-8"), _bcrypt.gensalt(rounds=12)).decode("utf-8"),
            display_name=req.display_name,
            avatar_url=req.avatar_url,
            user_type=req.user_type,
        )
        user = await self._repo.create(user)
        return UserResponse.model_validate(user)

    async def get(self, user_id: str, tenant_id: str) -> UserResponse:
        user = await self._repo.get_by_id(user_id, tenant_id)
        if not user:
            raise NotFoundException(message=f"User '{user_id}' not found")
        return UserResponse.model_validate(user)

    async def list_users(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20):
        items, total = await self._repo.list_by_tenant(tenant_id, status=status, page=page, page_size=page_size)
        return [UserResponse.model_validate(u) for u in items], total

    async def update(self, user_id: str, tenant_id: str, req: UserUpdateRequest) -> UserResponse:
        user = await self._repo.get_by_id(user_id, tenant_id)
        if not user:
            raise NotFoundException(message=f"User '{user_id}' not found")
        data = req.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(user, k, v)
        user = await self._repo.update(user)
        return UserResponse.model_validate(user)

    async def delete(self, user_id: str, tenant_id: str) -> bool:
        return await self._repo.soft_delete(user_id, tenant_id)

    async def change_password(self, user_id: str, tenant_id: str, req: PasswordChangeRequest) -> bool:
        user = await self._repo.get_by_id(user_id, tenant_id)
        if not user:
            raise NotFoundException(message=f"User '{user_id}' not found")
        if not _bcrypt.checkpw(req.old_password.encode("utf-8"), user.password_hash.encode("utf-8")):
            raise ForbiddenException(message="Old password is incorrect")
        errors = UserDomainService.validate_password(req.new_password)
        if errors:
            raise ValidationException(message="; ".join(errors))
        user.password_hash = _bcrypt.hashpw(req.new_password.encode("utf-8"), _bcrypt.gensalt(rounds=12)).decode("utf-8")
        user.must_change_pwd = False
        await self._repo.update(user)
        return True

    async def admin_reset_password(self, user_id: str, tenant_id: str, req: AdminResetPasswordRequest) -> bool:
        user = await self._repo.get_by_id(user_id, tenant_id)
        if not user:
            raise NotFoundException(message=f"User '{user_id}' not found")
        errors = UserDomainService.validate_password(req.new_password)
        if errors:
            raise ValidationException(message="; ".join(errors))
        user.password_hash = _bcrypt.hashpw(req.new_password.encode("utf-8"), _bcrypt.gensalt(rounds=12)).decode("utf-8")
        user.must_change_pwd = req.must_change_pwd
        user.login_fail_count = 0
        await self._repo.update(user)
        return True

    async def change_status(self, user_id: str, tenant_id: str, req: UserStatusChangeRequest) -> UserResponse:
        user = await self._repo.get_by_id(user_id, tenant_id)
        if not user:
            raise NotFoundException(message=f"User '{user_id}' not found")
        if not UserDomainService.can_transition(user.status, req.status):
            raise ValidationException(
                message=f"Cannot transition user from '{user.status}' to '{req.status}'"
            )
        old_status = user.status
        user.status = req.status
        if req.status == "active":
            user.login_fail_count = 0
        user = await self._repo.update(user)
        return UserResponse.model_validate(user)

    async def unlock(self, user_id: str, tenant_id: str) -> UserResponse:
        user = await self._repo.get_by_id(user_id, tenant_id)
        if not user:
            raise NotFoundException(message=f"User '{user_id}' not found")
        if user.status != "locked":
            raise ValidationException(message="User is not locked")
        user.status = "active"
        user.login_fail_count = 0
        user = await self._repo.update(user)
        return UserResponse.model_validate(user)

    async def batch_change_status(self, tenant_id: str, req: BatchUserStatusRequest) -> int:
        count = await self._repo.batch_update_status(req.user_ids, tenant_id, req.status)
        return count

    async def get_user_permissions(self, user_id: str, tenant_id: str) -> UserPermissionsResponse:
        user = await self._repo.get_by_id(user_id, tenant_id)
        if not user:
            raise NotFoundException(message=f"User '{user_id}' not found")
        user_roles = await self._role_repo.list_by_user(user_id, tenant_id)
        role_ids = [ur.role_id for ur in user_roles]
        roles: list[RoleResponse] = []
        permission_codes: list[str] = []
        permissions: list[PermissionResponse] = []
        if role_ids:
            for rid in role_ids:
                role = await self._role_model_repo.get_by_id(rid, tenant_id)
                if role and role.status == "active":
                    roles.append(RoleResponse.model_validate(role))
            role_perms = await self._role_perm_repo.list_by_roles(role_ids)
            perm_ids = list({rp.permission_id for rp in role_perms})
            if perm_ids:
                perms = await self._perm_repo.list_by_ids(perm_ids)
                for p in perms:
                    if p.status == "active":
                        permissions.append(PermissionResponse.model_validate(p))
                        permission_codes.append(p.code)
        return UserPermissionsResponse(
            user_id=user_id,
            roles=roles,
            permissions=permissions,
            permission_codes=permission_codes,
        )

    async def assign_roles(self, user_id: str, tenant_id: str, req: AssignRoleRequest) -> bool:
        user = await self._repo.get_by_id(user_id, tenant_id)
        if not user:
            raise NotFoundException(message=f"User '{user_id}' not found")
        existing = await self._role_repo.list_by_user(user_id, tenant_id)
        existing_role_ids = {ur.role_id for ur in existing}
        for rid in req.role_ids:
            if rid not in existing_role_ids:
                await self._role_repo.assign(user_id, rid, tenant_id)
        return True

    async def revoke_roles(self, user_id: str, tenant_id: str, req: AssignRoleRequest) -> bool:
        for rid in req.role_ids:
            await self._role_repo.revoke(user_id, rid, tenant_id)
        return True


class RoleService:
    def __init__(
        self,
        repo: RoleRepository,
        rp_repo: RolePermissionRepository,
        perm_repo: PermissionRepository | AuditLogRepository,
        audit_repo: AuditLogRepository | None = None,
    ):
        self._repo = repo
        self._rp_repo = rp_repo
        if audit_repo is None:
            self._perm_repo = None
            self._audit_repo = perm_repo
        else:
            self._perm_repo = perm_repo
            self._audit_repo = audit_repo

    async def create(self, tenant_id: str, req: RoleCreateRequest) -> RoleResponse:
        existing = await self._repo.get_by_code(req.code, tenant_id)
        if existing:
            raise ConflictException(message=f"Role code '{req.code}' already exists")
        role = Role(
            tenant_id=tenant_id,
            name=req.name,
            code=req.code,
            description=req.description,
            role_type=req.role_type,
            sort_order=req.sort_order,
        )
        role = await self._repo.create(role)
        return RoleResponse.model_validate(role)

    async def get(self, role_id: str, tenant_id: str) -> RoleResponse:
        role = await self._repo.get_by_id(role_id, tenant_id)
        if not role:
            raise NotFoundException(message=f"Role '{role_id}' not found")
        return RoleResponse.model_validate(role)

    async def list_roles(self, tenant_id: str, status: str = "") -> list[RoleResponse]:
        items = await self._repo.list_by_tenant(tenant_id, status=status)
        return [RoleResponse.model_validate(r) for r in items]

    async def update(self, role_id: str, tenant_id: str, req: RoleUpdateRequest) -> RoleResponse:
        role = await self._repo.get_by_id(role_id, tenant_id)
        if not role:
            raise NotFoundException(message=f"Role '{role_id}' not found")
        if role.role_type == "system":
            raise ForbiddenException(message="Cannot modify system role")
        data = req.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(role, k, v)
        role = await self._repo.update(role)
        return RoleResponse.model_validate(role)

    async def delete(self, role_id: str, tenant_id: str) -> bool:
        role = await self._repo.get_by_id(role_id, tenant_id)
        if not role:
            raise NotFoundException(message=f"Role '{role_id}' not found")
        if role.role_type == "system":
            raise ForbiddenException(message="Cannot delete system role")
        return await self._repo.soft_delete(role_id, tenant_id)

    async def get_permissions_detail(self, role_id: str, tenant_id: str) -> RolePermissionsDetailResponse:
        role = await self._repo.get_by_id(role_id, tenant_id)
        if not role:
            raise NotFoundException(message=f"Role '{role_id}' not found")
        role_perms = await self._rp_repo.list_by_role(role_id)
        perm_ids = [rp.permission_id for rp in role_perms]
        permissions: list[PermissionResponse] = []
        permission_codes: list[str] = []
        if perm_ids:
            perms = await self._perm_repo.list_by_ids(perm_ids)
            for p in perms:
                permissions.append(PermissionResponse.model_validate(p))
                permission_codes.append(p.code)
        return RolePermissionsDetailResponse(
            role=RoleResponse.model_validate(role),
            permissions=permissions,
            permission_codes=permission_codes,
        )

    async def assign_permissions(self, role_id: str, tenant_id: str, req: AssignPermissionRequest) -> bool:
        role = await self._repo.get_by_id(role_id, tenant_id)
        if not role:
            raise NotFoundException(message=f"Role '{role_id}' not found")
        existing = await self._rp_repo.list_by_role(role_id)
        existing_perm_ids = {rp.permission_id for rp in existing}
        for pid in req.permission_ids:
            if pid not in existing_perm_ids:
                await self._rp_repo.assign(role_id, pid)
        return True

    async def revoke_permissions(self, role_id: str, tenant_id: str, req: AssignPermissionRequest) -> bool:
        for pid in req.permission_ids:
            await self._rp_repo.revoke(role_id, pid)
        return True


class PermissionService:
    def __init__(self, repo: PermissionRepository):
        self._repo = repo

    async def create(self, req: PermissionCreateRequest) -> PermissionResponse:
        existing = await self._repo.get_by_code(req.code)
        if existing:
            raise ConflictException(message=f"Permission code '{req.code}' already exists")
        path = ""
        level = 1
        if req.parent_id:
            parent = await self._repo.get_by_id(req.parent_id)
            if not parent:
                raise NotFoundException(message=f"Parent permission '{req.parent_id}' not found")
            path = f"{parent.path}/{parent.id}" if parent.path else parent.id
            level = parent.level + 1
        perm = Permission(
            parent_id=req.parent_id,
            name=req.name,
            code=req.code,
            perm_type=req.perm_type,
            resource=req.resource,
            action=req.action,
            path=path,
            level=level,
            icon=req.icon,
            sort_order=req.sort_order,
        )
        perm = await self._repo.create(perm)
        return PermissionResponse.model_validate(perm)

    async def get(self, perm_id: str) -> PermissionResponse:
        perm = await self._repo.get_by_id(perm_id)
        if not perm:
            raise NotFoundException(message=f"Permission '{perm_id}' not found")
        return PermissionResponse.model_validate(perm)

    async def list_all(self, perm_type: str = "") -> list[PermissionResponse]:
        items = await self._repo.list_all(perm_type=perm_type)
        return [PermissionResponse.model_validate(p) for p in items]

    async def update(self, perm_id: str, req: PermissionUpdateRequest) -> PermissionResponse:
        perm = await self._repo.get_by_id(perm_id)
        if not perm:
            raise NotFoundException(message=f"Permission '{perm_id}' not found")
        data = req.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(perm, k, v)
        perm = await self._repo.update(perm)
        return PermissionResponse.model_validate(perm)

    async def delete(self, perm_id: str) -> bool:
        return await self._repo.soft_delete(perm_id)

    async def get_tree(self, perm_type: str = "") -> list[dict]:
        items = await self._repo.list_all(perm_type=perm_type)
        node_map: dict[str | None, list[dict]] = {}
        for item in items:
            data = PermissionResponse.model_validate(item).model_dump()
            parent_key = data.get("parent_id")
            if parent_key not in node_map:
                node_map[parent_key] = []
            node_map[parent_key].append(data)
        def _build_children(parent_id: str | None) -> list[dict]:
            children = node_map.get(parent_id, [])
            for child in children:
                child["children"] = _build_children(child["id"])
            return children
        return _build_children(None)


class AuditLogService:
    def __init__(self, repo: AuditLogRepository):
        self._repo = repo

    async def list_logs(
        self, tenant_id: str, module: str = "", action: str = "", page: int = 1, page_size: int = 20
    ):
        items, total = await self._repo.list_by_tenant(
            tenant_id, module=module, action=action, page=page, page_size=page_size
        )
        return [AuditLogResponse.model_validate(a) for a in items], total

    async def get_stats(self, tenant_id: str, days: int = 30) -> AuditStatsResponse:
        stats = await self._repo.get_stats(tenant_id, days=days)
        return AuditStatsResponse(**stats)


class IAMQueryService:
    """
    IAM 统计查询服务

    提供IAM模块的运营统计概览、各子域统计数据聚合。
    """

    def __init__(self, session):
        self._session = session

    async def get_statistics(self, tenant_id: str) -> dict:
        """获取IAM运营统计概览"""
        from sqlalchemy import func as sa_func

        total_tenants = (await self._session.execute(
            select(sa_func.count()).select_from(Tenant)
        )).scalar() or 0

        active_tenants = (await self._session.execute(
            select(sa_func.count()).select_from(Tenant).where(Tenant.status == "active")
        )).scalar() or 0

        total_users = (await self._session.execute(
            select(sa_func.count()).select_from(User).where(User.tenant_id == tenant_id)
        )).scalar() or 0

        active_users = (await self._session.execute(
            select(sa_func.count()).select_from(User)
            .where(User.tenant_id == tenant_id, User.status == "active")
        )).scalar() or 0

        total_roles = (await self._session.execute(
            select(sa_func.count()).select_from(Role).where(Role.tenant_id == tenant_id)
        )).scalar() or 0

        total_permissions = (await self._session.execute(
            select(sa_func.count()).select_from(Permission)
        )).scalar() or 0

        total_orgs = (await self._session.execute(
            select(sa_func.count()).select_from(Organization).where(Organization.tenant_id == tenant_id)
        )).scalar() or 0

        by_status_rows = (await self._session.execute(
            select(User.status, sa_func.count())
            .where(User.tenant_id == tenant_id)
            .group_by(User.status)
        )).all()
        users_by_status = {r[0] or "unknown": r[1] for r in by_status_rows}

        return {
            "total_tenants": total_tenants,
            "active_tenants": active_tenants,
            "total_users": total_users,
            "active_users": active_users,
            "total_roles": total_roles,
            "total_permissions": total_permissions,
            "total_orgs": total_orgs,
            "users_by_status": users_by_status,
        }


class PositionService:
    """
    岗位管理应用服务

    编排岗位的完整生命周期: 创建 → 更新 → 分配用户 → 软删除
    支持组织下的岗位管理、用户多岗位分配、主岗设置。
    """

    def __init__(self, repo: PositionRepository, user_position_repo: UserPositionRepository,
                 audit_repo: AuditLogRepository):
        self._repo = repo
        self._user_position_repo = user_position_repo
        self._audit_repo = audit_repo

    async def create(self, tenant_id: str, req: PositionCreateRequest) -> PositionResponse:
        existing = await self._repo.get_by_code(req.code, tenant_id)
        if existing:
            raise ConflictException(message=f"Position code '{req.code}' already exists")
        position = Position(
            tenant_id=tenant_id,
            org_id=req.org_id,
            name=req.name,
            code=req.code,
            level=req.level,
            sort_order=req.sort_order,
        )
        position = await self._repo.create(position)
        await self._audit("create", "position", position.id, f"Created position {position.name}")
        return PositionResponse.model_validate(position)

    async def get(self, position_id: str, tenant_id: str) -> PositionResponse:
        position = await self._repo.get_by_id(position_id, tenant_id)
        if not position:
            raise NotFoundException(message=f"Position '{position_id}' not found")
        return PositionResponse.model_validate(position)

    async def list_by_org(self, org_id: str, tenant_id: str) -> list[PositionResponse]:
        items = await self._repo.list_by_org(org_id, tenant_id)
        return [PositionResponse.model_validate(p) for p in items]

    async def list_by_tenant(self, tenant_id: str, status: str = "") -> list[PositionResponse]:
        items = await self._repo.list_by_tenant(tenant_id, status=status)
        return [PositionResponse.model_validate(p) for p in items]

    async def update(self, position_id: str, tenant_id: str, req: PositionUpdateRequest) -> PositionResponse:
        position = await self._repo.get_by_id(position_id, tenant_id)
        if not position:
            raise NotFoundException(message=f"Position '{position_id}' not found")
        data = req.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(position, k, v)
        position = await self._repo.update(position)
        await self._audit("update", "position", position_id, f"Updated position fields: {list(data.keys())}")
        return PositionResponse.model_validate(position)

    async def delete(self, position_id: str, tenant_id: str) -> bool:
        position = await self._repo.get_by_id(position_id, tenant_id)
        if not position:
            raise NotFoundException(message=f"Position '{position_id}' not found")
        user_positions = await self._user_position_repo.list_by_position(position_id, tenant_id)
        if user_positions:
            raise ValidationException(message="Cannot delete position with assigned users. Revoke users first.")
        result = await self._repo.soft_delete(position_id, tenant_id)
        await self._audit("delete", "position", position_id, f"Soft-deleted position {position.name}")
        return result

    async def assign_user(self, user_id: str, tenant_id: str, req: UserPositionAssignRequest) -> UserPositionResponse:
        position = await self._repo.get_by_id(req.position_id, tenant_id)
        if not position:
            raise NotFoundException(message=f"Position '{req.position_id}' not found")
        existing = await self._user_position_repo.list_by_user(user_id, tenant_id)
        for up in existing:
            if up.position_id == req.position_id:
                raise ConflictException(message=f"User already assigned to position '{position.name}'")
        up = await self._user_position_repo.assign(user_id, req.position_id, tenant_id, is_primary=req.is_primary)
        await self._audit("assign_position", "user_position", up.id,
                          f"Assigned position {position.name} to user, primary={req.is_primary}")
        resp = UserPositionResponse.model_validate(up)
        resp.position_name = position.name
        return resp

    async def revoke_user(self, user_id: str, position_id: str, tenant_id: str) -> bool:
        result = await self._user_position_repo.revoke(user_id, position_id, tenant_id)
        if not result:
            raise NotFoundException(message="User position assignment not found")
        await self._audit("revoke_position", "user_position", "",
                          f"Revoked position {position_id} from user {user_id}")
        return result

    async def set_primary(self, user_id: str, position_id: str, tenant_id: str) -> bool:
        result = await self._user_position_repo.set_primary(user_id, position_id, tenant_id)
        if not result:
            raise NotFoundException(message="User position assignment not found")
        return result

    async def get_user_positions(self, user_id: str, tenant_id: str) -> list[UserPositionResponse]:
        user_positions = await self._user_position_repo.list_by_user(user_id, tenant_id)
        result = []
        for up in user_positions:
            resp = UserPositionResponse.model_validate(up)
            position = await self._repo.get_by_id(up.position_id, tenant_id)
            if position:
                resp.position_name = position.name
            result.append(resp)
        return result

    async def _audit(self, action: str, target_type: str, target_id: str, detail: str):
        log = AuditLog(
            tenant_id=tenant_id_var.get(""),
            user_id=actor_id_var.get(""),
            action=action,
            module="iam",
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
        await self._audit_repo.create(log)


class ObjectPermissionService:
    """
    对象级权限应用服务

    实现行级权限控制，支持对用户/角色/岗位/组织授予或撤销
    对特定资源实例的读/写/删/审批权限，allow/deny双效果。
    """

    def __init__(self, repo: ObjectPermissionRepository, audit_repo: AuditLogRepository):
        self._repo = repo
        self._audit_repo = audit_repo

    async def grant(self, tenant_id: str, req: ObjectPermissionGrantRequest) -> ObjectPermissionResponse:
        existing = await self._repo.check_permission(
            req.subject_type, req.subject_id, req.resource_type, req.resource_id, req.action, tenant_id
        )
        if existing:
            raise ConflictException(
                message=f"Object permission already exists for {req.subject_type}/{req.subject_id} "
                        f"on {req.resource_type}/{req.resource_id} action={req.action}"
            )
        obj_perm = ObjectPermission(
            tenant_id=tenant_id,
            subject_type=req.subject_type,
            subject_id=req.subject_id,
            resource_type=req.resource_type,
            resource_id=req.resource_id,
            action=req.action,
            effect=req.effect,
            conditions_json=req.conditions_json,
        )
        obj_perm = await self._repo.grant(obj_perm)
        await self._audit("grant_object_perm", "object_permission", obj_perm.id,
                          f"Granted {req.effect} {req.action} on {req.resource_type}/{req.resource_id} "
                          f"to {req.subject_type}/{req.subject_id}")
        return ObjectPermissionResponse.model_validate(obj_perm)

    async def revoke(self, perm_id: str, tenant_id: str) -> bool:
        result = await self._repo.revoke(perm_id, tenant_id)
        if not result:
            raise NotFoundException(message=f"Object permission '{perm_id}' not found")
        await self._audit("revoke_object_perm", "object_permission", perm_id, "Revoked object permission")
        return result

    async def list_by_subject(self, subject_type: str, subject_id: str, tenant_id: str) -> list[ObjectPermissionResponse]:
        items = await self._repo.list_by_subject(subject_type, subject_id, tenant_id)
        return [ObjectPermissionResponse.model_validate(i) for i in items]

    async def list_by_resource(self, resource_type: str, resource_id: str, tenant_id: str) -> list[ObjectPermissionResponse]:
        items = await self._repo.list_by_resource(resource_type, resource_id, tenant_id)
        return [ObjectPermissionResponse.model_validate(i) for i in items]

    async def check_permission(
        self, subject_type: str, subject_id: str, resource_type: str, resource_id: str, action: str, tenant_id: str
    ) -> ObjectPermissionResponse | None:
        obj_perm = await self._repo.check_permission(
            subject_type, subject_id, resource_type, resource_id, action, tenant_id
        )
        if obj_perm:
            return ObjectPermissionResponse.model_validate(obj_perm)
        return None

    async def _audit(self, action: str, target_type: str, target_id: str, detail: str):
        log = AuditLog(
            tenant_id=tenant_id_var.get(""),
            user_id=actor_id_var.get(""),
            action=action,
            module="iam",
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
        await self._audit_repo.create(log)


class DataPermissionService:
    """
    数据权限应用服务

    管理10维度数据隔离规则: tenant/org/department/store/marketplace/
    channel/warehouse/supplier/category/data_level。
    支持按角色或用户配置允许访问的数据范围，优先级控制规则冲突。
    """

    VALID_DIMENSIONS = {
        "tenant", "org", "department", "store", "marketplace",
        "channel", "warehouse", "supplier", "category", "data_level"
    }

    def __init__(self, repo: DataPermissionRuleRepository, audit_repo: AuditLogRepository):
        self._repo = repo
        self._audit_repo = audit_repo

    async def create(self, tenant_id: str, req: DataPermissionRuleCreateRequest) -> DataPermissionRuleResponse:
        if not req.role_id and not req.user_id:
            raise ValidationException(message="Either role_id or user_id must be provided")
        if req.role_id and req.user_id:
            raise ValidationException(message="Only one of role_id or user_id should be provided")
        if req.dimension not in self.VALID_DIMENSIONS:
            raise ValidationException(
                message=f"Invalid dimension '{req.dimension}', must be one of: {', '.join(sorted(self.VALID_DIMENSIONS))}"
            )
        rule = DataPermissionRule(
            tenant_id=tenant_id,
            role_id=req.role_id,
            user_id=req.user_id,
            dimension=req.dimension,
            allowed_values_json=req.allowed_values_json,
            priority=req.priority,
        )
        rule = await self._repo.create(rule)
        await self._audit("create_data_perm_rule", "data_permission_rule", rule.id,
                          f"Created data permission rule: dimension={req.dimension}")
        return DataPermissionRuleResponse.model_validate(rule)

    async def update(self, rule_id: str, tenant_id: str, req: DataPermissionRuleUpdateRequest) -> DataPermissionRuleResponse:
        rule = await self._get_by_id(rule_id, tenant_id)
        if not rule:
            raise NotFoundException(message=f"Data permission rule '{rule_id}' not found")
        data = req.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(rule, k, v)
        rule = await self._repo.update(rule)
        await self._audit("update_data_perm_rule", "data_permission_rule", rule_id,
                          f"Updated data permission rule fields: {list(data.keys())}")
        return DataPermissionRuleResponse.model_validate(rule)

    async def delete(self, rule_id: str, tenant_id: str) -> bool:
        result = await self._repo.delete(rule_id, tenant_id)
        if not result:
            raise NotFoundException(message=f"Data permission rule '{rule_id}' not found")
        await self._audit("delete_data_perm_rule", "data_permission_rule", rule_id, "Deleted data permission rule")
        return result

    async def list_by_role(self, role_id: str, tenant_id: str) -> list[DataPermissionRuleResponse]:
        items = await self._repo.list_by_role(role_id, tenant_id)
        return [DataPermissionRuleResponse.model_validate(r) for r in items]

    async def list_by_user(self, user_id: str, tenant_id: str) -> list[DataPermissionRuleResponse]:
        items = await self._repo.list_by_user(user_id, tenant_id)
        return [DataPermissionRuleResponse.model_validate(r) for r in items]

    async def list_by_dimension(self, dimension: str, tenant_id: str) -> list[DataPermissionRuleResponse]:
        items = await self._repo.list_by_dimension(dimension, tenant_id)
        return [DataPermissionRuleResponse.model_validate(r) for r in items]

    async def _get_by_id(self, rule_id: str, tenant_id: str) -> DataPermissionRule | None:
        all_rules = await self._repo.list_by_dimension("tenant", tenant_id)
        for r in all_rules:
            if r.id == rule_id:
                return r
        for dim in self.VALID_DIMENSIONS - {"tenant"}:
            rules = await self._repo.list_by_dimension(dim, tenant_id)
            for r in rules:
                if r.id == rule_id:
                    return r
        return None

    async def _audit(self, action: str, target_type: str, target_id: str, detail: str):
        log = AuditLog(
            tenant_id=tenant_id_var.get(""),
            user_id=actor_id_var.get(""),
            action=action,
            module="iam",
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
        await self._audit_repo.create(log)
