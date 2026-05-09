from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OptimizationSuggestion:
    suggestion_id: str = ""
    campaign_id: str = ""
    suggestion_type: str = ""
    current_value: float = 0.0
    suggested_value: float = 0.0
    expected_impact: dict = field(default_factory=dict)
    confidence: float = 0.0
    reason: str = ""


class AdOptimizationEngine:
    def generate_suggestions(self, campaign_data: dict) -> list[OptimizationSuggestion]:
        suggestions: list[OptimizationSuggestion] = []
        acos = campaign_data.get("acos", 0)
        spend = campaign_data.get("spend", 0)
        sales = campaign_data.get("sales", 0)
        clicks = campaign_data.get("clicks", 0)
        impressions = campaign_data.get("impressions", 0)
        daily_budget = campaign_data.get("daily_budget", 0)
        campaign_id = campaign_data.get("campaign_id", "")

        if acos > 30 and spend > 0:
            suggested_budget = round(daily_budget * 0.8, 2)
            suggestions.append(OptimizationSuggestion(
                suggestion_id=f"opt_{campaign_id}_budget",
                campaign_id=campaign_id, suggestion_type="budget_reduction",
                current_value=daily_budget, suggested_value=suggested_budget,
                expected_impact={"acos_reduction": round((acos - 25) * 0.3, 2)},
                confidence=0.75, reason=f"ACOS {acos}% is above 30% target, reduce budget",
            ))

        if impressions > 0 and clicks > 0:
            ctr = clicks / impressions * 100
            if ctr < 0.5:
                suggestions.append(OptimizationSuggestion(
                    suggestion_id=f"opt_{campaign_id}_keywords",
                    campaign_id=campaign_id, suggestion_type="keyword_optimization",
                    current_value=ctr, suggested_value=1.0,
                    expected_impact={"ctr_improvement": round(1.0 - ctr, 2)},
                    confidence=0.6, reason=f"CTR {ctr:.2f}% is below 0.5%, optimize keywords",
                ))

        if acos > 0 and sales > 0:
            target_acos = 25.0
            suggested_bid_ratio = target_acos / acos if acos > 0 else 1.0
            suggestions.append(OptimizationSuggestion(
                suggestion_id=f"opt_{campaign_id}_bid",
                campaign_id=campaign_id, suggestion_type="bid_adjustment",
                current_value=1.0, suggested_value=round(suggested_bid_ratio, 2),
                expected_impact={"target_acos": target_acos},
                confidence=0.7, reason=f"Adjust bids to target ACOS {target_acos}%",
            ))

        return suggestions

    def allocate_budget(self, campaigns: list[dict], total_budget: float) -> list[dict]:
        if not campaigns:
            return []
        total_roas = sum(max(c.get("roas", 0), 0.01) for c in campaigns)
        allocations = []
        for c in campaigns:
            roas = max(c.get("roas", 0), 0.01)
            share = roas / total_roas
            allocated = round(total_budget * share, 2)
            allocations.append({
                "campaign_id": c.get("campaign_id", ""),
                "campaign_name": c.get("campaign_name", ""),
                "roas": roas, "share_pct": round(share * 100, 2),
                "allocated_budget": allocated,
            })
        return allocations

    def get_performance_analysis(self, campaign_data: dict) -> dict:
        spend = campaign_data.get("spend", 0)
        sales = campaign_data.get("sales", 0)
        clicks = campaign_data.get("clicks", 0)
        impressions = campaign_data.get("impressions", 0)
        acos = round(spend / sales * 100, 2) if sales > 0 else 999.99
        roas = round(sales / spend, 2) if spend > 0 else 0
        ctr = round(clicks / impressions * 100, 4) if impressions > 0 else 0
        cpc = round(spend / clicks, 2) if clicks > 0 else 0

        return {
            "campaign_id": campaign_data.get("campaign_id", ""),
            "spend": spend, "sales": sales, "acos": acos, "roas": roas,
            "ctr": ctr, "cpc": cpc, "impressions": impressions, "clicks": clicks,
            "performance_rating": "good" if acos <= 25 else "average" if acos <= 40 else "poor",
        }
