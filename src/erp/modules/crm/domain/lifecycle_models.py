from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class LifecycleStage(StrEnum):
    PROSPECT = "prospect"
    NEW = "new"
    ACTIVE = "active"
    LOYAL = "loyal"
    AT_RISK = "at_risk"
    CHURNED = "churned"
    REACTIVATED = "reactivated"


class CustomerSegment(Base):
    __tablename__ = "customer_segment"
    __table_args__ = {"schema": "crm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    segment_name: Mapped[str] = mapped_column(String(200), nullable=False)
    segment_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    segment_type: Mapped[str] = mapped_column(String(50), nullable=False, default="lifecycle",
                                                comment="lifecycle/rfm/value/custom")
    criteria_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    lifecycle_stage: Mapped[str] = mapped_column(String(30), nullable=False, default="", index=True)
    customer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_order_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_order_frequency: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_auto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CustomerSegmentMember(Base):
    __tablename__ = "customer_segment_member"
    __table_args__ = {"schema": "crm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    segment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lifecycle_stage: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    rfm_score_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CustomerLifecycleService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_segment(self, tenant_id: str, segment_name: str, segment_code: str,
                              segment_type: str = "lifecycle", description: str = "",
                              criteria: dict | None = None, lifecycle_stage: str = "",
                              is_auto: bool = False) -> CustomerSegment:
        existing = await self._get_by_code(tenant_id, segment_code)
        if existing:
            raise ValidationException(message=f"Segment code '{segment_code}' already exists")

        segment = CustomerSegment(
            tenant_id=tenant_id, segment_name=segment_name,
            segment_code=segment_code, description=description,
            segment_type=segment_type,
            criteria_json=json.dumps(criteria or {}, default=str),
            lifecycle_stage=lifecycle_stage, is_auto=is_auto,
            created_by=actor_id_var.get(""),
        )
        self.session.add(segment)
        await self.session.flush()
        return segment

    async def assign_customer(self, tenant_id: str, segment_id: str, customer_id: str,
                               lifecycle_stage: str = "", rfm_score: dict | None = None) -> CustomerSegmentMember:
        existing = await self._get_member(tenant_id, segment_id, customer_id)
        if existing:
            existing.lifecycle_stage = lifecycle_stage
            existing.rfm_score_json = json.dumps(rfm_score or {}, default=str)
            await self.session.flush()
            return existing

        member = CustomerSegmentMember(
            tenant_id=tenant_id, segment_id=segment_id,
            customer_id=customer_id, lifecycle_stage=lifecycle_stage,
            rfm_score_json=json.dumps(rfm_score or {}, default=str),
        )
        self.session.add(member)
        await self.session.flush()
        return member

    async def evaluate_lifecycle(self, tenant_id: str, customer_id: str,
                                  total_orders: int = 0, total_revenue: float = 0.0,
                                  first_order_date: str = "", last_order_date: str = "",
                                  avg_days_between_orders: float = 0.0) -> dict:
        now = datetime.now(UTC)
        days_since_last = 999
        if last_order_date:
            try:
                last_dt = datetime.fromisoformat(last_order_date.replace("Z", "+00:00"))
                days_since_last = (now - last_dt).days
            except (ValueError, TypeError):
                pass

        days_since_first = 999
        if first_order_date:
            try:
                first_dt = datetime.fromisoformat(first_order_date.replace("Z", "+00:00"))
                days_since_first = (now - first_dt).days
            except (ValueError, TypeError):
                pass

        if total_orders == 0:
            stage = LifecycleStage.PROSPECT
        elif total_orders == 1 and days_since_first <= 30:
            stage = LifecycleStage.NEW
        elif total_orders >= 1 and days_since_last <= 90 and avg_days_between_orders <= 30:
            stage = LifecycleStage.LOYAL
        elif total_orders >= 2 and days_since_last <= 90:
            stage = LifecycleStage.ACTIVE
        elif total_orders >= 2 and 90 < days_since_last <= 180:
            stage = LifecycleStage.AT_RISK
        elif total_orders >= 1 and days_since_last > 180:
            stage = LifecycleStage.CHURNED
        else:
            stage = LifecycleStage.NEW

        rfm = self._calculate_rfm(total_orders, total_revenue, days_since_last, avg_days_between_orders)

        return {
            "customer_id": customer_id,
            "lifecycle_stage": stage.value,
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "days_since_last_order": days_since_last,
            "rfm_score": rfm,
            "recommendation": self._get_recommendation(stage, rfm),
        }

    async def batch_assign_lifecycle(self, tenant_id: str, customers: list[dict]) -> dict:
        results = {"assigned": 0, "errors": 0, "details": []}
        for cust in customers:
            try:
                evaluation = await self.evaluate_lifecycle(
                    tenant_id=tenant_id, customer_id=cust.get("customer_id", ""),
                    total_orders=cust.get("total_orders", 0),
                    total_revenue=cust.get("total_revenue", 0.0),
                    first_order_date=cust.get("first_order_date", ""),
                    last_order_date=cust.get("last_order_date", ""),
                    avg_days_between_orders=cust.get("avg_days_between_orders", 0.0),
                )

                stage = evaluation["lifecycle_stage"]
                stmt = select(CustomerSegment).where(
                    CustomerSegment.tenant_id == tenant_id,
                    CustomerSegment.lifecycle_stage == stage,
                    CustomerSegment.is_auto,
                )
                segment = (await self.session.execute(stmt)).scalar_one_or_none()

                if segment:
                    await self.assign_customer(
                        tenant_id=tenant_id, segment_id=segment.id,
                        customer_id=cust.get("customer_id", ""),
                        lifecycle_stage=stage,
                        rfm_score=evaluation["rfm_score"],
                    )
                    results["assigned"] += 1
                    results["details"].append({
                        "customer_id": cust.get("customer_id"),
                        "stage": stage, "segment_id": segment.id,
                    })
                else:
                    results["errors"] += 1
                    results["details"].append({
                        "customer_id": cust.get("customer_id"),
                        "error": f"No auto segment for stage '{stage}'",
                    })
            except Exception as e:
                results["errors"] += 1
                results["details"].append({
                    "customer_id": cust.get("customer_id", ""),
                    "error": str(e),
                })
        return results

    async def list_segments(self, tenant_id: str, segment_type: str = "",
                             lifecycle_stage: str = "") -> list[CustomerSegment]:
        conditions = [CustomerSegment.tenant_id == tenant_id]
        if segment_type:
            conditions.append(CustomerSegment.segment_type == segment_type)
        if lifecycle_stage:
            conditions.append(CustomerSegment.lifecycle_stage == lifecycle_stage)
        stmt = select(CustomerSegment).where(*conditions).order_by(CustomerSegment.segment_type, CustomerSegment.segment_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_segment_members(self, tenant_id: str, segment_id: str,
                                    page: int = 1, page_size: int = 20) -> tuple[list[CustomerSegmentMember], int]:
        conditions = [
            CustomerSegmentMember.tenant_id == tenant_id,
            CustomerSegmentMember.segment_id == segment_id,
        ]
        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(CustomerSegmentMember).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(CustomerSegmentMember).where(*conditions).order_by(
            CustomerSegmentMember.assigned_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def init_default_segments(self, tenant_id: str) -> list[CustomerSegment]:
        defaults = [
            ("潜在客户", "prospect", "lifecycle", LifecycleStage.PROSPECT.value,
             {"total_orders_eq": 0}),
            ("新客户", "new", "lifecycle", LifecycleStage.NEW.value,
             {"total_orders_eq": 1, "days_since_first_lte": 30}),
            ("活跃客户", "active", "lifecycle", LifecycleStage.ACTIVE.value,
             {"total_orders_gte": 2, "days_since_last_lte": 90}),
            ("忠诚客户", "loyal", "lifecycle", LifecycleStage.LOYAL.value,
             {"total_orders_gte": 5, "days_since_last_lte": 60, "avg_days_between_lte": 30}),
            ("流失风险客户", "at_risk", "lifecycle", LifecycleStage.AT_RISK.value,
             {"total_orders_gte": 2, "days_since_last_gt": 90, "days_since_last_lte": 180}),
            ("已流失客户", "churned", "lifecycle", LifecycleStage.CHURNED.value,
             {"days_since_last_gt": 180}),
            ("高价值客户", "high_value", "value", "",
             {"total_revenue_gte": 10000, "total_orders_gte": 5}),
            ("VIP客户", "vip", "rfm", "",
             {"rfm_r_gte": 4, "rfm_f_gte": 4, "rfm_m_gte": 4}),
        ]
        segments = []
        for name, code, seg_type, stage, criteria in defaults:
            try:
                seg = await self.create_segment(
                    tenant_id=tenant_id, segment_name=name, segment_code=code,
                    segment_type=seg_type, lifecycle_stage=stage,
                    criteria=criteria, is_auto=True,
                )
                segments.append(seg)
            except ValidationException:
                pass
        return segments

    def _calculate_rfm(self, total_orders: int, total_revenue: float,
                        days_since_last: int, avg_days_between: float) -> dict:
        r_score = 1
        if days_since_last <= 30:
            r_score = 5
        elif days_since_last <= 60:
            r_score = 4
        elif days_since_last <= 90:
            r_score = 3
        elif days_since_last <= 180:
            r_score = 2

        f_score = 1
        if total_orders >= 10:
            f_score = 5
        elif total_orders >= 5:
            f_score = 4
        elif total_orders >= 3:
            f_score = 3
        elif total_orders >= 2:
            f_score = 2

        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
        m_score = 1
        if avg_order_value >= 500:
            m_score = 5
        elif avg_order_value >= 200:
            m_score = 4
        elif avg_order_value >= 100:
            m_score = 3
        elif avg_order_value >= 50:
            m_score = 2

        return {
            "recency_score": r_score,
            "frequency_score": f_score,
            "monetary_score": m_score,
            "rfm_combined": f"{r_score}{f_score}{m_score}",
            "days_since_last": days_since_last,
            "total_orders": total_orders,
            "avg_order_value": round(avg_order_value, 2),
        }

    def _get_recommendation(self, stage: LifecycleStage, rfm: dict) -> str:
        recommendations = {
            LifecycleStage.PROSPECT: "首单优惠、新客礼包",
            LifecycleStage.NEW: "复购激励、关联推荐",
            LifecycleStage.ACTIVE: "会员升级、交叉销售",
            LifecycleStage.LOYAL: "VIP专属权益、新品优先",
            LifecycleStage.AT_RISK: "挽回优惠券、个性化推荐",
            LifecycleStage.CHURNED: "重激活活动、特别折扣",
            LifecycleStage.REACTIVATED: "回归奖励、忠诚度提升",
        }
        return recommendations.get(stage, "")

    async def _get_by_code(self, tenant_id: str, code: str) -> CustomerSegment | None:
        stmt = select(CustomerSegment).where(
            CustomerSegment.tenant_id == tenant_id,
            CustomerSegment.segment_code == code,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _get_member(self, tenant_id: str, segment_id: str,
                           customer_id: str) -> CustomerSegmentMember | None:
        stmt = select(CustomerSegmentMember).where(
            CustomerSegmentMember.tenant_id == tenant_id,
            CustomerSegmentMember.segment_id == segment_id,
            CustomerSegmentMember.customer_id == customer_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
