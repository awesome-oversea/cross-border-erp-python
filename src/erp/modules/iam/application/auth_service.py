from __future__ import annotations

from datetime import UTC, datetime

from erp.modules.iam.domain.auth import create_access_token, create_refresh_token, verify_password
from erp.modules.iam.domain.models import AuditLog
from erp.modules.iam.domain.repositories import AuditLogRepository, UserRepository, UserRoleRepository
from erp.shared.context import actor_id_var, tenant_id_var, trace_id_var
from erp.shared.exceptions import UnauthorizedException
from erp.shared.observability.logging import get_logger

logger = get_logger("erp.iam.auth_service")

LOGIN_FAIL_LOCK_THRESHOLD = 5


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        user_role_repo: UserRoleRepository,
        audit_repo: AuditLogRepository,
    ):
        self._user_repo = user_repo
        self._user_role_repo = user_role_repo
        self._audit_repo = audit_repo

    async def login(self, username: str, password: str, tenant_id: str, ip: str = "") -> dict:
        user = await self._user_repo.get_by_username(username, tenant_id)
        if not user or not verify_password(password, user.password_hash):
            await self._write_audit(
                tenant_id=tenant_id, user_id="", user_name=username,
                action="login_failed", target_type="user", target_id="",
                detail=f"Login failed for username={username}", ip=ip,
            )
            if user and user.status == "active":
                user.login_fail_count = (user.login_fail_count or 0) + 1
                if user.login_fail_count >= LOGIN_FAIL_LOCK_THRESHOLD:
                    user.status = "locked"
                await self._user_repo.update(user)
            raise UnauthorizedException(message="Invalid username or password")

        if user.status == "locked":
            raise UnauthorizedException(message="Account is locked due to too many failed login attempts")

        if user.status != "active":
            raise UnauthorizedException(message=f"Account is {user.status}")

        role_codes = await self._get_user_role_codes(user.id, tenant_id)

        access_token = create_access_token(subject=user.id, tenant_id=user.tenant_id, roles=role_codes)
        refresh_token = create_refresh_token(subject=user.id, tenant_id=user.tenant_id)

        user.last_login_at = datetime.now(UTC)
        user.last_login_ip = ip
        user.login_fail_count = 0
        await self._user_repo.update(user)

        await self._write_audit(
            tenant_id=user.tenant_id, user_id=user.id, user_name=user.username,
            action="login", target_type="user", target_id=user.id,
            detail="Login successful", ip=ip,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": user.id,
            "tenant_id": user.tenant_id,
            "display_name": user.display_name or user.username,
            "roles": role_codes,
        }

    async def refresh(self, user_id: str, tenant_id: str) -> dict:
        user = await self._user_repo.get_by_id(user_id, tenant_id)
        if not user:
            raise UnauthorizedException(message="User not found or inactive")
        if user.status != "active":
            raise UnauthorizedException(message=f"Account is {user.status}")

        role_codes = await self._get_user_role_codes(user.id, tenant_id)

        access_token = create_access_token(subject=user.id, tenant_id=user.tenant_id, roles=role_codes)
        refresh_token = create_refresh_token(subject=user.id, tenant_id=user.tenant_id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": user.id,
            "tenant_id": user.tenant_id,
            "display_name": user.display_name or user.username,
            "roles": role_codes,
        }

    async def refresh_by_token(self, refresh_token: str) -> dict:
        from erp.modules.iam.domain.auth import validate_refresh_token

        payload = validate_refresh_token(refresh_token)
        user_id = payload.get("sub", "")
        tenant_id = payload.get("tenant_id", "")
        return await self.refresh(user_id=user_id, tenant_id=tenant_id)

    async def _get_user_role_codes(self, user_id: str, tenant_id: str) -> list[str]:
        from sqlalchemy import and_, select

        from erp.modules.iam.domain.models import Role

        user_roles = await self._user_role_repo.list_by_user(user_id, tenant_id)
        if not user_roles:
            return []
        role_ids = [ur.role_id for ur in user_roles]
        session = self._user_repo._session
        role_stmt = select(Role.code).where(
            and_(Role.id.in_(role_ids), Role.tenant_id == tenant_id, Role.status == "active")
        )
        result = await session.execute(role_stmt)
        return [r for r in result.scalars().all()]

    async def _write_audit(
        self, tenant_id: str, user_id: str, user_name: str,
        action: str, target_type: str, target_id: str,
        detail: str, ip: str = "",
    ):
        log = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            user_name=user_name,
            action=action,
            module="iam",
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip=ip,
            trace_id=trace_id_var.get(""),
        )
        await self._audit_repo.create(log)
