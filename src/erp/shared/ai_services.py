"""
AI预测服务 (P7-012/P7-014)

包含:
  - AI仓储预测WMS: 库存预测、库位优化、异常预警
  - AI成本归集FMS: 成本异常检测、归集建议

所有方法为无状态纯函数,可通过PMS集成接口调用。
"""
from __future__ import annotations

from statistics import mean, stdev


class WarehousePredictionService:
    """AI仓储预测: 基于历史销量预测库存需求,检测异常波动"""
    """AI仓储预测 (P7-012): 库存预测/库位优化/异常预警"""

    @staticmethod
    def predict_stock(daily_sales: list[float], lead_time_days: int, periods: int = 7) -> dict:
        """基于历史销量预测未来库存需求"""
        if len(daily_sales) < 7:
            return {"error": "至少需要7天数据", "predictions": []}
        recent = daily_sales[-30:] if len(daily_sales) >= 30 else daily_sales
        avg = mean(recent)
        predictions = [round(avg * lead_time_days * 1.1, 1) for _ in range(periods)]
        return {"predictions": predictions, "avg_daily": round(avg, 2),
                "total_forecast": round(sum(predictions), 1)}

    @staticmethod
    def suggest_location(current_usage: dict, total_capacity: dict) -> list[dict]:
        """基于使用率建议库位优化"""
        suggestions = []
        for zone, used in current_usage.items():
            cap = total_capacity.get(zone, 1)
            rate = used / cap
            if rate > 0.85:
                suggestions.append({"zone": zone, "rate": round(rate * 100, 1),
                                    "action": "建议扩容或调整商品分布", "priority": "high"})
            elif rate < 0.2:
                suggestions.append({"zone": zone, "rate": round(rate * 100, 1),
                                    "action": "利用率过低，考虑合并库位", "priority": "low"})
        return sorted(suggestions, key=lambda x: x.get("rate", 0), reverse=True)

    @staticmethod
    def detect_anomaly(sales_history: list[float], threshold: float = 2.0) -> list[dict]:
        """基于标准差检测销量异常"""
        if len(sales_history) < 14:
            return []
        mu, sigma = mean(sales_history), stdev(sales_history)
        if sigma == 0: return []
        anomalies = []
        for i, val in enumerate(sales_history):
            z = (val - mu) / sigma
            if abs(z) > threshold:
                anomalies.append({"index": i, "value": val, "z_score": round(z, 2),
                                  "type": "spike" if val > mu else "drop"})
        return anomalies


class CostAnomalyService:
    """AI成本归集: 检测成本异常偏离,建议分摊方案"""
    """AI成本归集 (P7-014): 成本异常检测、归集建议"""

    @staticmethod
    def detect_cost_anomaly(cost_events: list[dict]) -> list[dict]:
        """检测成本异常: 偏离平均成本超过30%"""
        if not cost_events:
            return []
        amounts = [e.get("amount", 0) for e in cost_events if e.get("amount", 0) > 0]
        if not amounts:
            return []
        avg_cost = mean(amounts)
        anomalies = []
        for event in cost_events:
            amt = event.get("amount", 0)
            if amt > 0 and abs(amt - avg_cost) / avg_cost > 0.3:
                anomalies.append({"event_id": event.get("id"), "cost_type": event.get("cost_type"),
                                  "amount": amt, "avg_cost": round(avg_cost, 2),
                                  "deviation": round((amt - avg_cost) / avg_cost * 100, 1)})
        return anomalies

    @staticmethod
    def suggest_allocation(cost_event: dict, skus: list[str]) -> dict:
        """建议成本分摊方案"""
        if not skus:
            return {"method": "no_sku", "allocations": {}}
        amount = cost_event.get("amount", 0)
        equal = round(amount / len(skus), 2)
        return {"method": "equal_split", "total": amount,
                "allocations": {s: equal for s in skus}, "per_sku": equal}
