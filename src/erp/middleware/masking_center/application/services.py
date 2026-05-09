from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.masking_center.domain.engine import MaskingCenterEngine
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.masking_center")

_engine_instance = MaskingCenterEngine()


class MaskingCenterService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = _engine_instance

    async def mask(self, tenant_id: str, data: dict, field_mapping: dict[str, str] | None = None,
                    operator_id: str = "") -> dict:
        return self._engine.mask_dict(data, field_mapping, tenant_id, operator_id)

    async def get_rules(self, tenant_id: str) -> list[dict]:
        return self._engine.get_rules()

    async def create_rule(self, tenant_id: str, rule_code: str, rule_name: str, field_type: str,
                           pattern: str, replacement: str, description: str = "") -> dict:
        return self._engine.create_rule(rule_code, rule_name, field_type, pattern, replacement, description)

    async def get_audit_records(self, tenant_id: str, limit: int = 50) -> list[dict]:
        return self._engine.get_audit_records(tenant_id, limit)
