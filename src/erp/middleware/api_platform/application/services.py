from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.api_platform.domain.engine import ApiPlatformEngine
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.api_platform")

_engine_instance = ApiPlatformEngine()


class ApiPlatformService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = _engine_instance

    async def list_endpoints(self, tenant_id: str, service: str = "", version: str = "",
                              method: str = "") -> list[dict]:
        return self._engine.list_endpoints(service, version, method)

    async def record_call(self, tenant_id: str, path: str, method: str,
                           status_code: int = 200, response_time_ms: int = 0) -> dict:
        return self._engine.record_call(tenant_id, path, method, status_code, response_time_ms)

    async def get_stats(self, tenant_id: str, service: str = "", path: str = "",
                         hours: int = 24) -> dict:
        return self._engine.get_stats(tenant_id, service, path, hours)

    async def list_versions(self, tenant_id: str, service: str = "") -> list[dict]:
        return self._engine.list_versions(service)

    async def test_endpoint(self, tenant_id: str, path: str, method: str,
                             params: dict | None = None) -> dict:
        return self._engine.test_endpoint(path, method, params)
