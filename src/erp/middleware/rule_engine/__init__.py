"""
通用规则引擎 - 合并 order_strategy + logistics_strategy

提供统一的"条件评估→评分排序→选择最优"策略执行框架。
被order_strategy/logistics_strategy/billing等策略中台作为底层引擎复用。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuleCondition:
    field: str = ""
    operator: str = "eq"  # eq/gt/gte/lt/lte/in/between
    value: Any = None


@dataclass
class RuleAction:
    action_type: str = ""
    params: dict = field(default_factory=dict)


@dataclass
class Rule:
    rule_id: str = ""
    name: str = ""
    conditions: list[RuleCondition] = field(default_factory=list)
    score: float = 0.0
    priority: int = 0
    action: RuleAction | None = None
    is_active: bool = True


@dataclass
class EvaluationResult:
    matched: bool = False
    score: float = 0.0
    matched_rule: Rule | None = None
    all_scores: list[tuple[str, float]] = field(default_factory=list)


class RuleEngine:
    """通用规则引擎 - 条件评估+评分排序"""

    @staticmethod
    def evaluate_condition(condition: RuleCondition, data: dict) -> bool:
        actual = data.get(condition.field)
        val = condition.value
        op = condition.operator
        if op == "eq": return actual == val
        if op == "gt": return actual is not None and actual > val
        if op == "gte": return actual is not None and actual >= val
        if op == "lt": return actual is not None and actual < val
        if op == "lte": return actual is not None and actual <= val
        if op == "in": return actual in (val or [])
        if op == "between" and isinstance(val, (list, tuple)) and len(val) == 2:
            return actual is not None and val[0] <= actual <= val[1]
        return False

    @staticmethod
    def match_all(conditions: list[RuleCondition], data: dict) -> bool:
        """所有条件同时满足(AND)"""
        return all(RuleEngine.evaluate_condition(c, data) for c in conditions)

    @staticmethod
    def match_any(conditions: list[RuleCondition], data: dict) -> bool:
        """任一条件满足(OR)"""
        return any(RuleEngine.evaluate_condition(c, data) for c in conditions)

    @staticmethod
    def evaluate(rules: list[Rule], data: dict, mode: str = "best") -> list[EvaluationResult]:
        """
        执行多条规则评估

        参数:
            rules: 规则列表
            data:  评估上下文数据
            mode:  best(返回最优) / all(返回全部) / first(返回首个匹配)

        返回:
            EvaluationResult 列表,按score降序排列
        """
        results = []
        for rule in rules:
            if not rule.is_active:
                continue
            matched = RuleEngine.match_all(rule.conditions, data)
            results.append(EvaluationResult(
                matched=matched, score=rule.score if matched else 0,
                matched_rule=rule if matched else None,
            ))

        results.sort(key=lambda r: (r.score, r.matched_rule.priority if r.matched_rule else 0), reverse=True)

        if mode == "best":
            return [results[0]] if results else [EvaluationResult()]
        if mode == "first":
            matched = [r for r in results if r.matched]
            return [matched[0]] if matched else [EvaluationResult()]
        return results

    @staticmethod
    def rank_options(options: list[dict], weights: dict[str, float], scores: dict[str, dict]) -> list[dict]:
        """
        多维度加权评分排序

        参数:
            options: 待排序选项列表
            weights: 权重配置 {"维度名": 权重}
            scores:  评分数据 {"选项key": {"维度名": 分值}}

        返回:
            按综合评分降序排列的选项(每项附加 total_score)
        """
        ranked = []
        for opt in options:
            key = opt.get("id", str(id(opt)))
            dims = scores.get(key, {})
            total = sum(dims.get(dim, 0) * weights.get(dim, 0) for dim in weights)
            ranked.append({**opt, "total_score": round(total, 2)})
        return sorted(ranked, key=lambda x: x["total_score"], reverse=True)
