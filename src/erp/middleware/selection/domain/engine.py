from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MarketAnalysisInput:
    category: str = ""
    marketplace: str = "amazon_us"
    keywords: list[str] = field(default_factory=list)


@dataclass
class ProfitSimulationInput:
    sale_price: float = 0.0
    cost_price: float = 0.0
    shipping_cost: float = 0.0
    commission_rate: float = 0.15
    vat_rate: float = 0.0
    advertising_cost: float = 0.0
    other_costs: float = 0.0
    currency: str = "USD"
    monthly_sales_estimate: int = 100


class SelectionEngine:
    def analyze_market(self, input_data: MarketAnalysisInput) -> dict:
        return {
            "category": input_data.category, "marketplace": input_data.marketplace,
            "market_size_estimate": 5000000, "growth_rate_pct": 12.5,
            "competition_level": "medium", "avg_price": 25.99,
            "avg_reviews": 350, "seasonal": False,
            "top_keywords": input_data.keywords[:5] if input_data.keywords else ["generic"],
            "opportunity_score": 72,
        }

    def analyze_competitors(self, category: str, marketplace: str = "amazon_us") -> dict:
        return {
            "category": category, "marketplace": marketplace,
            "top_competitors": [
                {"rank": 1, "name": "Competitor A", "price": 24.99, "reviews": 1200, "rating": 4.3},
                {"rank": 2, "name": "Competitor B", "price": 29.99, "reviews": 800, "rating": 4.1},
                {"rank": 3, "name": "Competitor C", "price": 22.99, "reviews": 600, "rating": 4.5},
            ],
            "avg_price": 25.99, "avg_rating": 4.3, "market_concentration": "moderate",
        }

    def simulate_profit(self, input_data: ProfitSimulationInput) -> dict:
        commission = round(input_data.sale_price * input_data.commission_rate, 2)
        vat = round(input_data.sale_price * input_data.vat_rate, 2)
        total_cost = round(input_data.cost_price + input_data.shipping_cost + commission +
                           vat + input_data.advertising_cost + input_data.other_costs, 2)
        profit_per_unit = round(input_data.sale_price - total_cost, 2)
        margin_pct = round(profit_per_unit / input_data.sale_price * 100, 2) if input_data.sale_price > 0 else 0
        monthly_profit = round(profit_per_unit * input_data.monthly_sales_estimate, 2)

        return {
            "sale_price": input_data.sale_price, "total_cost": total_cost,
            "profit_per_unit": profit_per_unit, "margin_pct": margin_pct,
            "monthly_profit": monthly_profit, "currency": input_data.currency,
            "breakdown": {
                "cost_price": input_data.cost_price, "shipping": input_data.shipping_cost,
                "commission": commission, "vat": vat,
                "advertising": input_data.advertising_cost, "other": input_data.other_costs,
            },
        }


class TrendAnalysisService:
    """趋势分析(V4 10.10): 关键词趋势+品类趋势"""

    @staticmethod
    def keyword_trend(keyword: str, history: list[dict]) -> dict:
        if not history: return {"keyword": keyword, "trend": "unknown", "scores": []}
        recent = [h.get("score", 0) for h in history[-90:]]
        avg = sum(recent) / max(len(recent), 1)
        trend = "up" if len(recent) > 1 and recent[-1] > recent[0] else ("down" if len(recent) > 1 else "stable")
        return {"keyword": keyword, "trend": trend, "avg_score": round(avg, 2), "samples": len(history)}

    @staticmethod
    def category_trend(category_id: str, sales_history: list[dict]) -> dict:
        if not sales_history: return {"category": category_id, "trend": "unknown"}
        recent = sales_history[-90:]
        growth = sum(s.get("sales", 0) for s in recent[-30:]) / max(sum(s.get("sales", 0) for s in recent[:30]), 1) - 1 if len(recent) >= 60 else 0
        seasonality = "high" if max(s.get("sales", 0) for s in recent) > 2 * sum(s.get("sales", 0) for s in recent) / max(len(recent), 1) else "normal"
        return {"category": category_id, "growth": round(growth, 2), "seasonality": seasonality}
