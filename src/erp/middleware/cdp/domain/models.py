from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class CustomerProfile:
    customer_id: str = ""
    customer_no: str = ""
    name: str = ""
    email: str = ""
    phone: str = ""
    platforms: list[str] = field(default_factory=list)
    segment: str = "normal"
    rfm_score: dict = field(default_factory=dict)
    total_orders: int = 0
    total_amount: float = 0.0
    avg_order_amount: float = 0.0
    first_order_date: str = ""
    last_order_date: str = ""
    tags: list[str] = field(default_factory=list)
    lifetime_value: float = 0.0


@dataclass
class CustomerSegment:
    segment_id: str = ""
    segment_name: str = ""
    segment_type: str = "auto"
    criteria: dict = field(default_factory=dict)
    customer_count: int = 0
    description: str = ""


class RFMCalculator:
    def calculate(self, orders: list[dict], reference_date: datetime | None = None) -> dict:
        if not orders:
            return {"recency_days": 999, "frequency": 0, "monetary": 0.0,
                    "r_score": 1, "f_score": 1, "m_score": 1, "segment": "inactive"}

        ref = reference_date or datetime.now(UTC)
        dates = [o.get("order_date", ref) for o in orders]
        recency_days = min((ref - d).days if hasattr((ref - d), "days") else 999 for d in dates)
        frequency = len(orders)
        monetary = sum(o.get("amount", 0) for o in orders)

        r_score = 5 if recency_days <= 30 else 4 if recency_days <= 90 else 3 if recency_days <= 180 else 2 if recency_days <= 365 else 1
        f_score = 5 if frequency >= 20 else 4 if frequency >= 10 else 3 if frequency >= 5 else 2 if frequency >= 2 else 1
        m_score = 5 if monetary >= 5000 else 4 if monetary >= 2000 else 3 if monetary >= 500 else 2 if monetary >= 100 else 1

        avg_score = (r_score + f_score + m_score) / 3
        if avg_score >= 4:
            segment = "champions"
        elif r_score >= 4 and f_score < 4:
            segment = "recent_customers"
        elif f_score >= 4 and r_score < 4:
            segment = "loyal_customers"
        elif avg_score >= 3:
            segment = "potential"
        elif r_score >= 3:
            segment = "promising"
        else:
            segment = "at_risk"

        return {
            "recency_days": recency_days, "frequency": frequency, "monetary": monetary,
            "r_score": r_score, "f_score": f_score, "m_score": m_score, "segment": segment,
        }
