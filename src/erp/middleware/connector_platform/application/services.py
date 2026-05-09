from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.connector_platform.domain.engine import ConnectorPlatformEngine

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ConnectorPlatformService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = ConnectorPlatformEngine()

    async def list_connectors(self, tenant_id: str, connector_type: str = "", platform: str = "") -> list[dict]:
        connectors = self._engine.list_connectors(connector_type=connector_type, platform=platform)
        return [self._to_dict(c) for c in connectors]

    async def register_connector(self, tenant_id: str, connector_type: str, connector_name: str,
                                  platform: str, version: str = "1.0.0", config: dict | None = None) -> dict:
        result = self._engine.register_connector(connector_type, connector_name, platform, version, config or {})
        return result

    async def health_check(self, connector_id: str = "") -> dict:
        if connector_id:
            return self._engine.health_check(connector_id)
        return self._engine.health_check()

    async def record_call(self, tenant_id: str, connector_id: str, success: bool, response_time_ms: int) -> dict:
        return self._engine.record_call(tenant_id, connector_id, success, response_time_ms)

    async def get_stats(self, tenant_id: str, connector_id: str, hours: int = 24) -> dict:
        return self._engine.get_stats(tenant_id, connector_id, hours)

    @staticmethod
    def _to_dict(connector) -> dict:
        return {
            "connector_id": connector.connector_id,
            "connector_type": connector.connector_type,
            "connector_name": connector.connector_name,
            "platform": connector.platform,
            "version": connector.version,
            "is_active": connector.is_active,
            "health_status": connector.health_status,
            "last_health_check": connector.last_health_check,
            "registered_at": connector.registered_at,
        }
