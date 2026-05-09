from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.cdp.domain.models import CustomerProfile, CustomerSegment, RFMCalculator
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.cdp")


class CDPService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._rfm = RFMCalculator()

    async def get_customer_profile(self, tenant_id: str, customer_id: str) -> dict:
        profile = CustomerProfile(customer_id=customer_id, segment="normal")
        return {
            "customer_id": profile.customer_id, "segment": profile.segment,
            "rfm_score": profile.rfm_score, "total_orders": profile.total_orders,
            "total_amount": profile.total_amount, "tags": profile.tags,
        }

    async def calculate_rfm(self, tenant_id: str, customer_id: str, orders: list[dict]) -> dict:
        result = self._rfm.calculate(orders)
        return {"customer_id": customer_id, "rfm": result}

    async def get_segments(self, tenant_id: str) -> list[dict]:
        default_segments = [
            CustomerSegment(segment_id="champions", segment_name="Champions", segment_type="auto",
                            criteria={"min_avg_score": 4}, description="Best customers"),
            CustomerSegment(segment_id="loyal_customers", segment_name="Loyal Customers", segment_type="auto",
                            criteria={"min_f_score": 4}, description="Frequent buyers"),
            CustomerSegment(segment_id="recent_customers", segment_name="Recent Customers", segment_type="auto",
                            criteria={"min_r_score": 4}, description="Recently active"),
            CustomerSegment(segment_id="at_risk", segment_name="At Risk", segment_type="auto",
                            criteria={"max_avg_score": 2}, description="Need attention"),
        ]
        return [{"segment_id": s.segment_id, "segment_name": s.segment_name,
                 "segment_type": s.segment_type, "description": s.description} for s in default_segments]

    async def create_segment(self, tenant_id: str, segment_name: str, criteria: dict,
                              segment_type: str = "custom", description: str = "") -> dict:
        segment = CustomerSegment(
            segment_id=f"custom_{segment_name.lower().replace(' ', '_')}",
            segment_name=segment_name, segment_type=segment_type,
            criteria=criteria, description=description,
        )
        logger.info("segment_created", segment_name=segment_name, tenant_id=tenant_id)
        return {"segment_id": segment.segment_id, "segment_name": segment.segment_name,
                "segment_type": segment.segment_type, "description": segment.description}
