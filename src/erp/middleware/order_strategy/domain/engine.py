"""
订单策略中心 - 基于通用规则引擎实现

职责: 订单审核/分仓/拆合单策略评估
底层: rule_engine (条件匹配+评分排序)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from erp.middleware.rule_engine import RuleEngine, Rule, RuleCondition


@dataclass
class StrategyContext:
    order_amount: float = 0.0
    item_count: int = 0
    platform: str = ""
    country: str = ""
    weight_kg: float = 0.0
    buyer_history: int = 0
    warehouse_stock: dict = field(default_factory=dict)
    profit_rate: float = 0.0


class OrderStrategyEngine:
    """订单策略引擎 - 复用RuleEngine进行审核/分仓/拆合单评估"""

    def __init__(self):
        self._engine = RuleEngine()

    def evaluate_review(self, context: StrategyContext) -> dict:
        rules = [
            Rule("high_value", "高价值需审核", [RuleCondition("order_amount", "gt", 10000)], priority=1),
            Rule("risk_buyer", "退货超3次需审核", [RuleCondition("buyer_history", "gt", 3)], priority=1),
            Rule("low_profit", "利润率<5%需审核", [RuleCondition("profit_rate", "lt", 0.05)], priority=1),
            Rule("auto_pass", "小额自动通过", [RuleCondition("order_amount", "lte", 500)], score=100),
        ]
        data = {"order_amount": context.order_amount, "buyer_history": context.buyer_history,
                "profit_rate": context.profit_rate}
        results = self._engine.evaluate(rules, data, mode="all")
        flags = [r.matched_rule.name for r in results if r.matched and r.matched_rule and r.matched_rule.priority > 0]
        auto = any(r.matched for r in results if r.matched_rule and r.matched_rule.rule_id == "auto_pass")
        return {"auto_pass": auto and not flags, "review": bool(flags), "flags": flags}

    def select_warehouse(self, context: StrategyContext) -> dict:
        if not context.warehouse_stock:
            return {"warehouse": "", "score": 0}
        options = [{"id": w, "qty": q} for w, q in context.warehouse_stock.items()]
        scores = {w: {"stock": min(q/100, 1.0)} for w, q in context.warehouse_stock.items() if q > 0}
        ranked = self._engine.rank_options(options, {"stock": 1.0}, scores)
        return {"warehouse": ranked[0]["id"] if ranked else "", "score": ranked[0].get("total_score", 0) if ranked else 0}
