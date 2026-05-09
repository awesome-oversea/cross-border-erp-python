from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.compliance.domain.engine import ComplianceEngine
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.compliance")


class ComplianceService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = ComplianceEngine()

    async def check(self, tenant_id: str, content: str, platform: str = "",
                     country: str = "", category: str = "") -> dict:
        return self._engine.check_compliance(content, platform, country, category)

    async def get_rules(self, tenant_id: str) -> list[dict]:
        return self._engine.get_rules()

    async def assess_risk(self, tenant_id: str, transaction_amount: float, country: str = "",
                           customer_segment: str = "", platform: str = "") -> dict:
        return self._engine.assess_risk(transaction_amount, country, customer_segment, platform)
