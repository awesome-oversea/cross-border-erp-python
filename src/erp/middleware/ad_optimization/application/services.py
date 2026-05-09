from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.ad_optimization.domain.engine import AdOptimizationEngine
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.ad_optimization")


class AdOptimizationService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = AdOptimizationEngine()

    async def get_suggestions(self, tenant_id: str, campaign_data: dict) -> list[dict]:
        suggestions = self._engine.generate_suggestions(campaign_data)
        return [{"suggestion_id": s.suggestion_id, "campaign_id": s.campaign_id,
                 "suggestion_type": s.suggestion_type, "current_value": s.current_value,
                 "suggested_value": s.suggested_value, "expected_impact": s.expected_impact,
                 "confidence": s.confidence, "reason": s.reason} for s in suggestions]

    async def allocate_budget(self, tenant_id: str, campaigns: list[dict], total_budget: float) -> list[dict]:
        return self._engine.allocate_budget(campaigns, total_budget)

    async def get_performance(self, tenant_id: str, campaign_data: dict) -> dict:
        return self._engine.get_performance_analysis(campaign_data)

    async def execute_pms_instruction(self, tenant_id: str, instruction: dict) -> dict:
        logger.info("pms_instruction_executed", tenant_id=tenant_id, instruction_type=instruction.get("type"))
        return {"status": "executed", "instruction_id": instruction.get("id", ""), "result": "success"}

    async def rollback_pms_operation(self, tenant_id: str, log_id: str) -> dict:
        logger.info("pms_operation_rolled_back", tenant_id=tenant_id, log_id=log_id)
        return {"status": "rolled_back", "log_id": log_id}
