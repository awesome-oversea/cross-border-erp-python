from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.order_strategy.domain.engine import (
    DEFAULT_AUTO_APPROVE_RULES,
    DEFAULT_LOGISTICS_RULES,
    DEFAULT_RISK_RULES,
    DEFAULT_WAREHOUSE_RULES,
    OrderStrategyEngine,
    StrategyEvaluationContext,
    StrategyRule,
)
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.order_strategy")


class OrderStrategyService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = OrderStrategyEngine()

    async def evaluate(self, tenant_id: str, order_id: str = "", order_amount: float = 0.0,
                       currency: str = "USD", platform: str = "", store_id: str = "",
                       items: list | None = None, shipping_address: dict | None = None,
                       customer_id: str = "", customer_segment: str = "",
                       strategy_types: list[str] | None = None) -> dict:
        context = StrategyEvaluationContext(
            tenant_id=tenant_id, order_id=order_id, order_amount=order_amount,
            currency=currency, platform=platform, store_id=store_id,
            items=items or [], shipping_address=shipping_address or {},
            customer_id=customer_id, customer_segment=customer_segment,
        )

        types = strategy_types or ["risk_control", "warehouse_allocation", "logistics_selection", "auto_approve"]
        all_rules: list[StrategyRule] = []
        if "risk_control" in types:
            all_rules.extend(DEFAULT_RISK_RULES)
        if "warehouse_allocation" in types:
            all_rules.extend(DEFAULT_WAREHOUSE_RULES)
        if "logistics_selection" in types:
            all_rules.extend(DEFAULT_LOGISTICS_RULES)
        if "auto_approve" in types:
            all_rules.extend(DEFAULT_AUTO_APPROVE_RULES)

        result = self._engine.evaluate(context, all_rules)
        logger.info("order_strategy_evaluated", order_id=order_id, risk_level=result.risk_level,
                     auto_approve=result.auto_approve)

        return {
            "order_id": order_id, "risk_level": result.risk_level,
            "recommended_warehouse_id": result.recommended_warehouse_id,
            "recommended_logistics_id": result.recommended_logistics_id,
            "auto_approve": result.auto_approve,
            "matched_rules": result.matched_rules,
        }

    async def list_strategies(self, tenant_id: str, strategy_type: str = "") -> list[dict]:
        rules_map = {
            "risk_control": DEFAULT_RISK_RULES,
            "warehouse_allocation": DEFAULT_WAREHOUSE_RULES,
            "logistics_selection": DEFAULT_LOGISTICS_RULES,
            "auto_approve": DEFAULT_AUTO_APPROVE_RULES,
        }
        if strategy_type:
            rules = rules_map.get(strategy_type, [])
        else:
            rules = DEFAULT_RISK_RULES + DEFAULT_WAREHOUSE_RULES + DEFAULT_LOGISTICS_RULES + DEFAULT_AUTO_APPROVE_RULES
        return [{"rule_id": r.rule_id, "rule_name": r.rule_name, "strategy_type": r.strategy_type,
                 "priority": r.priority, "is_active": r.is_active} for r in rules]
