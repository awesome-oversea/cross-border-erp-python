from __future__ import annotations

PROHIBITED_KEYWORDS: dict[str, list[str]] = {
    "general": ["counterfeit", "fake", "replica", "knockoff", "imitation"],
    "health": ["cure", "treat", "prevent", "diagnose", "prescription"],
    "safety": ["recall", "banned", "hazardous", "toxic", "flammable"],
}

TRADE_EMBARGO_COUNTRIES: list[str] = ["CU", "IR", "KP", "SY"]

IP_CHECK_RULES: list[dict] = [
    {"type": "trademark", "description": "Check for trademark infringement"},
    {"type": "patent", "description": "Check for patent infringement"},
    {"type": "copyright", "description": "Check for copyright infringement"},
]


class ComplianceEngine:
    def check_compliance(self, content: str, platform: str = "", country: str = "",
                          category: str = "") -> dict:
        violations: list[dict] = []
        content_lower = content.lower()

        for rule_type, keywords in PROHIBITED_KEYWORDS.items():
            for kw in keywords:
                if kw in content_lower:
                    violations.append({"type": "prohibited_keyword", "keyword": kw,
                                       "rule_type": rule_type, "severity": "critical"})

        if country in TRADE_EMBARGO_COUNTRIES:
            violations.append({"type": "trade_embargo", "country": country,
                               "severity": "critical", "message": f"Trade embargo: {country}"})

        risk_level = "high" if any(v["severity"] == "critical" for v in violations) else \
                     "medium" if violations else "low"

        return {
            "compliant": len(violations) == 0, "risk_level": risk_level,
            "violations": violations, "platform": platform,
            "country": country, "category": category,
        }

    def assess_risk(self, transaction_amount: float, country: str = "",
                     customer_segment: str = "", platform: str = "") -> dict:
        risk_score = 0
        factors: list[dict] = []

        if transaction_amount > 50000:
            risk_score += 30
            factors.append({"factor": "high_amount", "score": 30})
        if country in TRADE_EMBARGO_COUNTRIES:
            risk_score += 50
            factors.append({"factor": "embargo_country", "score": 50})
        if customer_segment == "new":
            risk_score += 10
            factors.append({"factor": "new_customer", "score": 10})

        risk_level = "high" if risk_score >= 50 else "medium" if risk_score >= 20 else "low"
        return {"risk_score": risk_score, "risk_level": risk_level, "factors": factors}

    def get_rules(self) -> list[dict]:
        return [
            {"rule_id": "prohibited_keywords", "rule_name": "Prohibited Keywords Check", "type": "content"},
            {"rule_id": "trade_embargo", "rule_name": "Trade Embargo Check", "type": "trade"},
            {"rule_id": "ip_check", "rule_name": "IP Infringement Check", "type": "ip"},
        ]


class FraudDetectionService:
    """反欺诈风控(V4 10.9): 订单异常/盗卡/退货滥用/黑名单"""

    @staticmethod
    def detect_order_anomaly(order: dict) -> list[str]:
        flags = []
        if order.get("amount", 0) > 10000 and order.get("is_new_buyer"):
            flags.append("新客大额订单")
        if order.get("shipping_address") != order.get("billing_address"):
            flags.append("地址不一致")
        if order.get("item_count", 0) > 50:
            flags.append("批量采购")
        return flags

    @staticmethod
    def check_blacklist(buyer_id: str, blacklist: list[str]) -> bool:
        return buyer_id in blacklist

    @staticmethod
    def refund_abuse_risk(return_rate: float) -> str:
        if return_rate > 0.3: return "high"
        if return_rate > 0.1: return "medium"
        return "low"


class TradeComplianceService:
    """贸易合规(V4 10.9): 进出口合规/禁运检查"""
    EMBARGOED_COUNTRIES = {"IR", "KP", "SY", "CU", "SD"}
    RESTRICTED_HS_CODES = ["93", "84", "85"]

    @staticmethod
    def check_embargo(country: str) -> bool:
        return country.upper() in TradeComplianceService.EMBARGOED_COUNTRIES

    @staticmethod
    def check_hs_restriction(hs_code: str) -> bool:
        return any(hs_code.startswith(c) for c in TradeComplianceService.RESTRICTED_HS_CODES)
