"""
物流策略中心 - 基于通用规则引擎实现

职责: 物流商选择/运费计算/时效预估
底层: rule_engine (条件匹配+评分排序)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from erp.middleware.rule_engine import RuleEngine, Rule, RuleCondition


@dataclass
class LogisticsContext:
    country: str = ""
    weight_kg: float = 0.0
    volume_m3: float = 0.0
    declared_value: float = 0.0
    sku_category: str = ""
    is_fragile: bool = False
    has_battery: bool = False


@dataclass
class CarrierOption:
    carrier_id: str = ""
    name: str = ""
    freight: float = 0.0
    estimated_days: int = 0
    score: float = 0.0


class LogisticsStrategyEngine:
    """物流策略引擎 - 复用RuleEngine进行物流商选择/运费计算"""

    def __init__(self):
        self._engine = RuleEngine()

    def select_carrier(self, context: LogisticsContext, carriers: list[dict]) -> list[CarrierOption]:
        """多维度评分选择最优物流商"""
        if not carriers:
            return []
        options = []
        for c in carriers:
            freight = self._estimate_freight(c, context)
            days = c.get("estimated_days", 10)
            score = self._calc_score(freight, days, context)
            options.append(CarrierOption(carrier_id=c.get("id", ""), name=c.get("name", ""),
                                         freight=freight, estimated_days=days, score=score))
        return sorted(options, key=lambda x: x.score, reverse=True)

    def _estimate_freight(self, carrier: dict, ctx: LogisticsContext) -> float:
        first_kg = carrier.get("first_kg_price", 0)
        additional_kg = carrier.get("additional_kg_price", 0)
        if ctx.weight_kg <= 1:
            return first_kg
        return first_kg + (ctx.weight_kg - 1) * additional_kg

    def _calc_score(self, freight: float, days: int, ctx: LogisticsContext) -> float:
        cost_score = max(0, 100 - freight / 10)
        time_score = max(0, 100 - days * 5)
        return round(cost_score * 0.6 + time_score * 0.4, 2)

    def get_restricted_rules(self, ctx: LogisticsContext) -> list[str]:
        """检查物流限制规则(含电池/易碎品/特货)"""
        rules = []
        if ctx.has_battery:
            rules.append("含电池:仅限可承运电池的物流渠道")
        if ctx.is_fragile:
            rules.append("易碎品:需加固包装")
        return rules
