from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.auth_center.domain.engine import AuthCenterEngine
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.auth_center")

_engine_instance = AuthCenterEngine()


class AuthCenterService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = _engine_instance

    async def check_permission(self, tenant_id: str, user_id: str, permission_code: str) -> dict:
        return self._engine.check_permission(user_id, permission_code)

    async def get_user_permissions(self, tenant_id: str, user_id: str) -> dict:
        return self._engine.get_user_permissions(user_id)

    async def refresh_cache(self, tenant_id: str, user_id: str, role_codes: list[str],
                             data_scopes: dict | None = None) -> dict:
        return self._engine.refresh_cache(user_id, tenant_id, role_codes, data_scopes)

    async def list_permissions(self, tenant_id: str, module: str = "") -> list[dict]:
        return self._engine.list_permissions(module)

    async def list_roles(self, tenant_id: str) -> list[dict]:
        return self._engine.list_roles()
