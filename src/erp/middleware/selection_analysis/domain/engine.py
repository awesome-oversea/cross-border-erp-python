from __future__ import annotations

from erp.middleware.selection.domain.engine import SelectionEngine


class SelectionAnalysisEngine:
    def __init__(self) -> None:
        self._engine = SelectionEngine()

    def analyze(self, tenant_id: str, category_id: str = "", market: str = "", platform: str = "") -> dict:
        from erp.middleware.selection.domain.engine import MarketAnalysisInput
        input_data = MarketAnalysisInput(category=category_id, marketplace=platform or "amazon_us")
        result = self._engine.analyze_market(input_data)
        result["tenant_id"] = tenant_id
        result["market"] = market
        return result

    def get_trends(self, tenant_id: str, category_id: str = "", market: str = "", days: int = 30) -> dict:
        return {
            "tenant_id": tenant_id, "category_id": category_id, "market": market,
            "period_days": days,
            "trends": [
                {"date": f"2026-04-{30 - i:02d}", "search_volume": 5000 + (i % 7) * 200, "sales_volume": 300 + (i % 5) * 50}
                for i in range(days)
            ],
        }

    def get_competitors(self, tenant_id: str, category_id: str = "", market: str = "") -> dict:
        result = self._engine.analyze_competitors(category_id, market or "amazon_us")
        result["tenant_id"] = tenant_id
        return result
