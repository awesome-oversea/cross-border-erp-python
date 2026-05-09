from fastapi import Depends, Header
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.iam.application.services import IAMQueryService
from erp.modules.iam.domain.auth import validate_access_token
from erp.modules.iam.domain.models import User, UserRole
from erp.shared.context import actor_id_var, actor_type_var, tenant_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import ForbiddenException, UnauthorizedException


async def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    if not authorization.startswith("Bearer "):
        raise UnauthorizedException(message="Invalid authorization header")
    token = authorization[7:]
    payload = validate_access_token(token)

    user_id = payload.get("sub", "")
    tenant_id = payload.get("tenant_id", "")

    tenant_id_var.set(tenant_id)
    actor_id_var.set(user_id)
    actor_type_var.set("user")

    stmt = select(User).where(
        and_(User.id == user_id, User.tenant_id == tenant_id, User.deleted_at.is_(None), User.status == "active")
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedException(message="User not found or inactive")

    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "roles": payload.get("roles", []),
        "username": user.username,
    }


async def get_current_user_with_permissions(
    current: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    role_ids_stmt = select(UserRole.role_id).where(
        and_(UserRole.user_id == current["user_id"], UserRole.tenant_id == current["tenant_id"])
    )
    role_result = await session.execute(role_ids_stmt)
    role_ids = [r for r in role_result.scalars().all()]

    permissions: list[str] = []
    if role_ids:
        from erp.modules.iam.domain.models import Permission, RolePermission
        perm_stmt = select(Permission.code).join(
            RolePermission, RolePermission.permission_id == Permission.id
        ).where(RolePermission.role_id.in_(role_ids))
        perm_result = await session.execute(perm_stmt)
        permissions = [p for p in perm_result.scalars().all()]

    current["permissions"] = permissions
    return current


def require_permissions(*required_perms: str):
    async def _check(current: dict = Depends(get_current_user_with_permissions)) -> dict:
        user_perms = set(current.get("permissions", []))
        missing = [p for p in required_perms if p not in user_perms]
        if missing:
            raise ForbiddenException(message=f"Missing permissions: {', '.join(missing)}")
        return current
    return _check


def require_roles(*required_roles: str):
    async def _check(current: dict = Depends(get_current_user)) -> dict:
        user_roles = set(current.get("roles", []))
        missing = [r for r in required_roles if r not in user_roles]
        if missing:
            raise ForbiddenException(message=f"Missing roles: {', '.join(missing)}")
        return current
    return _check


async def get_pms_service_account(
    authorization: str = Header(..., alias="Authorization"),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_actor_type: str = Header(default="service_account", alias="X-Actor-Type"),
    x_source_system: str = Header(default="PMS", alias="X-Source-System"),
    x_idempotency_key: str = Header(default="", alias="X-Idempotency-Key"),
    x_trace_id: str = Header(default="", alias="X-Trace-ID"),
) -> dict:
    if not authorization.startswith("Bearer "):
        raise UnauthorizedException(message="Invalid authorization header")
    token = authorization[7:]
    payload = validate_access_token(token)

    tenant_id_var.set(x_tenant_id)
    actor_id_var.set(payload.get("sub", ""))
    actor_type_var.set(x_actor_type)

    if payload.get("tenant_id") != x_tenant_id:
        raise ForbiddenException(message="Token tenant does not match X-Tenant-ID")

    return {
        "service_account_id": payload.get("sub", ""),
        "tenant_id": x_tenant_id,
        "source_system": x_source_system,
        "idempotency_key": x_idempotency_key,
        "trace_id": x_trace_id,
        "actor_type": x_actor_type,
    }


async def get_iam_query_service(session: AsyncSession = Depends(get_db_session)) -> IAMQueryService:
    return IAMQueryService(session=session)
