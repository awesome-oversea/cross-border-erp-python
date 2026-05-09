from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.audit_center.domain.engine import AuditCenterEngine
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.audit_center")

_engine_instance = AuditCenterEngine()


class AuditCenterService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = _engine_instance

    async def log(self, tenant_id: str, action: str, resource_type: str, resource_id: str = "",
                   resource_name: str = "", domain: str = "", actor_id: str = "",
                   actor_type: str = "user", actor_name: str = "",
                   before: dict | None = None, after: dict | None = None,
                   ip_address: str = "", user_agent: str = "",
                   request_path: str = "", request_method: str = "",
                   status: str = "success", error_message: str = "",
                   trace_id: str = "") -> dict:
        record = self._engine.log(tenant_id, action, resource_type, resource_id, resource_name,
                                   domain, actor_id, actor_type, actor_name, before, after,
                                   ip_address, user_agent, request_path, request_method,
                                   status, error_message, trace_id)
        return {"id": record.id, "action": record.action, "status": record.status, "created_at": record.created_at}

    async def query(self, tenant_id: str, domain: str = "", action: str = "",
                     actor_id: str = "", resource_type: str = "", resource_id: str = "",
                     start_date: str = "", end_date: str = "", status: str = "",
                     limit: int = 50, offset: int = 0) -> list[dict]:
        records = self._engine.query(tenant_id, domain, action, actor_id, resource_type,
                                      resource_id, start_date, end_date, status, limit, offset)
        return [self._engine._record_to_dict(r) for r in records]

    async def export(self, tenant_id: str, domain: str = "", start_date: str = "",
                      end_date: str = "", output_format: str = "json") -> list[dict]:
        return self._engine.export(tenant_id, domain, start_date, end_date, output_format)
