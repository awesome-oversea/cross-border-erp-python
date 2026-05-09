from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CostType(StrEnum):
    PURCHASE = "purchase"
    HEAD_FREIGHT = "head_freight"
    WAREHOUSE = "warehouse"
    PLATFORM_COMMISSION = "platform_commission"
    ADVERTISING = "advertising"
    PAYMENT_FEE = "payment_fee"
    LAST_MILE = "last_mile"
    OTHER = "other"


COST_TYPE_NAMES = {
    "purchase": "采购成本", "head_freight": "头程运费", "warehouse": "仓储费",
    "platform_commission": "平台佣金", "advertising": "广告费",
    "payment_fee": "支付手续费", "last_mile": "尾程运费", "other": "其他",
}


@dataclass
class CostEvent:
    event_id: str = ""
    cost_type: str = ""
    amount: float = 0.0
    currency: str = "CNY"
    sku_id: str = ""
    order_id: str = ""
    reference_type: str = ""
    reference_id: str = ""
    occurred_date: str = ""


@dataclass
class CostBreakdown:
    sku_id: str = ""
    period: str = ""
    costs: dict[str, float] = field(default_factory=dict)
    total: float = 0.0
    currency: str = "CNY"


class CostAggregationEngine:
    def collect_events(self, events: list[CostEvent]) -> dict:
        by_type: dict[str, float] = {}
        by_sku: dict[str, dict[str, float]] = {}
        total = 0.0

        for event in events:
            by_type[event.cost_type] = by_type.get(event.cost_type, 0) + event.amount
            total += event.amount

            if event.sku_id:
                if event.sku_id not in by_sku:
                    by_sku[event.sku_id] = {}
                by_sku[event.sku_id][event.cost_type] = by_sku[event.sku_id].get(event.cost_type, 0) + event.amount

        return {
            "total": round(total, 2), "by_type": {k: round(v, 2) for k, v in by_type.items()},
            "by_sku": {sku: {k: round(v, 2) for k, v in costs.items()} for sku, costs in by_sku.items()},
            "event_count": len(events),
        }

    def generate_breakdown(self, sku_id: str, events: list[CostEvent], period: str = "") -> CostBreakdown:
        costs: dict[str, float] = {}
        total = 0.0
        for event in events:
            if event.sku_id == sku_id:
                costs[event.cost_type] = costs.get(event.cost_type, 0) + event.amount
                total += event.amount
        return CostBreakdown(sku_id=sku_id, period=period, costs={k: round(v, 2) for k, v in costs.items()},
                              total=round(total, 2))

    def allocate_shared_costs(self, shared_cost: float, sku_weights: dict[str, float]) -> dict[str, float]:
        total_weight = sum(sku_weights.values())
        if total_weight <= 0:
            count = len(sku_weights)
            return {sku: round(shared_cost / count, 2) for sku in sku_weights} if count > 0 else {}
        return {sku: round(shared_cost * (weight / total_weight), 2) for sku, weight in sku_weights.items()}

    def calculate_fifo_cost(self, layers: list[dict], quantity: int) -> dict:
        remaining = quantity
        total_cost = 0.0
        consumed_layers: list[dict] = []

        for layer in sorted(layers, key=lambda x: x.get("date", "")):
            if remaining <= 0:
                break
            available = layer.get("quantity", 0)
            unit_cost = layer.get("unit_cost", 0)
            consumed = min(remaining, available)
            cost = round(consumed * unit_cost, 2)
            total_cost += cost
            consumed_layers.append({"date": layer.get("date", ""), "quantity": consumed,
                                     "unit_cost": unit_cost, "cost": cost})
            remaining -= consumed

        avg_cost = round(total_cost / quantity, 4) if quantity > 0 else 0
        return {"quantity": quantity, "total_cost": round(total_cost, 2),
                "avg_unit_cost": avg_cost, "consumed_layers": consumed_layers}

    def detect_anomaly(self, events: list[CostEvent], threshold_pct: float = 50.0) -> list[dict]:
        if not events:
            return []
        by_type: dict[str, list[float]] = {}
        for event in events:
            by_type.setdefault(event.cost_type, []).append(event.amount)

        anomalies: list[dict] = []
        for cost_type, amounts in by_type.items():
            if len(amounts) < 2:
                continue
            avg = sum(amounts) / len(amounts)
            for amt in amounts:
                if avg > 0 and abs(amt - avg) / avg * 100 > threshold_pct:
                    anomalies.append({"cost_type": cost_type, "amount": amt,
                                      "average": round(avg, 2), "deviation_pct": round(abs(amt - avg) / avg * 100, 2)})
        return anomalies


class AiCostService:
    """AI成本归集(V4 10.12): 智能识别遗漏/异常成本"""

    @staticmethod
    def detect_missing_events(order: dict) -> list[dict]:
        suggestions = []
        platforms = ["amazon", "ebay", "shopify"]
        if order.get("platform") in platforms:
            commission = round(order.get("total_amount", 0) * 0.15, 2)
            suggestions.append({"type": "platform_commission", "suggested_amount": commission, "reason": f"{order.get("platform")}平台佣金"})
        if order.get("has_fba"):
            suggestions.append({"type": "fba_fulfillment", "suggested_amount": order.get("item_count", 0) * 3.5, "reason": "FBA配送费"})
        if order.get("has_advertising"):
            suggestions.append({"type": "advertising_cost", "reason": "广告费用待关联"})
        return suggestions

    @staticmethod
    def auto_categorize(description: str) -> str:
        desc_lower = description.lower()
        if any(w in desc_lower for w in ["采购","购买","supplier"]): return "purchase"
        if any(w in desc_lower for w in ["运","物流","freight","shipping"]): return "logistics"
        if any(w in desc_lower for w in ["仓","storage","warehouse"]): return "warehouse"
        if any(w in desc_lower for w in ["佣金","commission","platform"]): return "platform_fee"
        if any(w in desc_lower for w in ["广告","ad","promotion"]): return "advertising"
        return "other"
