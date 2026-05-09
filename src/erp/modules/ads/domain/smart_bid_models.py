from __future__ import annotations

import json
import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class BidStrategy(StrEnum):
    FIXED = "fixed"
    DYNAMIC_DOWN = "dynamic_down"
    DYNAMIC_UP_DOWN = "dynamic_up_down"
    TARGET_ACoS = "target_acos"
    RULE_BASED = "rule_based"


class BidAdjustment(Base):
    __tablename__ = "bid_adjustment"
    __table_args__ = {"schema": "ads"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ad_group_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    keyword_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    strategy: Mapped[str] = mapped_column(String(30), nullable=False, default="target_acos")
    current_bid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    suggested_bid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    applied_bid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    target_acos: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_acos: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    adjustment_reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    is_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    rule_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BidRule(Base):
    __tablename__ = "bid_rule"
    __table_args__ = {"schema": "ads"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    strategy: Mapped[str] = mapped_column(String(30), nullable=False, default="target_acos")
    condition_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    action_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SmartBidService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_bid_rule(self, tenant_id: str, rule_name: str, strategy: str,
                               condition: dict | None = None, action: dict | None = None,
                               priority: int = 0) -> BidRule:
        rule = BidRule(
            tenant_id=tenant_id, rule_name=rule_name, strategy=strategy,
            condition_json=json.dumps(condition or {}, default=str),
            action_json=json.dumps(action or {}, default=str),
            priority=priority, created_by=actor_id_var.get(""),
        )
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def calculate_bid(self, tenant_id: str, campaign_id: str, ad_group_id: str,
                             keyword_id: str = "", current_bid: float = 0.0,
                             actual_acos: float = 0.0, target_acos: float = 0.0,
                             ctr: float = 0.0, cr: float = 0.0,
                             avg_cpc: float = 0.0, strategy: str = "target_acos",
                             rule_params: dict | None = None) -> BidAdjustment:
        suggested_bid = self._calculate(strategy, current_bid, actual_acos, target_acos,
                                        ctr, cr, avg_cpc, rule_params or {})

        reason = self._generate_reason(strategy, current_bid, suggested_bid, actual_acos, target_acos)

        adjustment = BidAdjustment(
            tenant_id=tenant_id, campaign_id=campaign_id,
            ad_group_id=ad_group_id, keyword_id=keyword_id,
            strategy=strategy, current_bid=current_bid,
            suggested_bid=suggested_bid, applied_bid=suggested_bid,
            target_acos=target_acos, actual_acos=actual_acos,
            adjustment_reason=reason,
            rule_json=json.dumps(rule_params or {}, default=str),
            trace_id=trace_id_var.get(""), created_by=actor_id_var.get(""),
        )
        self.session.add(adjustment)
        await self.session.flush()
        return adjustment

    async def apply_bid(self, adjustment_id: str, tenant_id: str) -> BidAdjustment:
        stmt = select(BidAdjustment).where(
            BidAdjustment.id == adjustment_id,
            BidAdjustment.tenant_id == tenant_id,
        )
        adj = (await self.session.execute(stmt)).scalar_one_or_none()
        if not adj:
            raise NotFoundException(message=f"Bid adjustment '{adjustment_id}' not found")
        adj.is_applied = True
        adj.applied_bid = adj.suggested_bid
        await self.session.flush()
        return adj

    async def list_bid_adjustments(self, tenant_id: str, campaign_id: str = "",
                                    is_applied: bool | None = None,
                                    page: int = 1, page_size: int = 20) -> tuple[list[BidAdjustment], int]:
        conditions = [BidAdjustment.tenant_id == tenant_id]
        if campaign_id:
            conditions.append(BidAdjustment.campaign_id == campaign_id)
        if is_applied is not None:
            conditions.append(BidAdjustment.is_applied == is_applied)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(BidAdjustment).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(BidAdjustment).where(*conditions).order_by(
            BidAdjustment.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_bid_rules(self, tenant_id: str, strategy: str = "") -> list[BidRule]:
        conditions = [BidRule.tenant_id == tenant_id]
        if strategy:
            conditions.append(BidRule.strategy == strategy)
        stmt = select(BidRule).where(*conditions).order_by(BidRule.priority.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def _calculate(self, strategy: str, current_bid: float, actual_acos: float,
                    target_acos: float, ctr: float, cr: float,
                    avg_cpc: float, params: dict) -> float:
        max_bid = params.get("max_bid", 10.0)
        min_bid = params.get("min_bid", 0.1)
        max_adjustment_pct = params.get("max_adjustment_pct", 0.5)

        if strategy == "fixed":
            return current_bid

        elif strategy == "target_acos":
            if actual_acos <= 0 or cr <= 0:
                return current_bid
            target_cpc = (cr * target_acos) / 100.0 if target_acos > 0 else current_bid
            suggested = target_cpc
            if actual_acos > target_acos:
                suggested = current_bid * (1 - min(max_adjustment_pct, (actual_acos - target_acos) / actual_acos))
            elif actual_acos < target_acos * 0.8:
                suggested = current_bid * (1 + min(max_adjustment_pct, 0.2))

        elif strategy == "dynamic_down":
            if actual_acos > target_acos:
                reduction = min(max_adjustment_pct, (actual_acos - target_acos) / actual_acos)
                suggested = current_bid * (1 - reduction)
            else:
                suggested = current_bid

        elif strategy == "dynamic_up_down":
            if actual_acos > target_acos:
                reduction = min(max_adjustment_pct, (actual_acos - target_acos) / actual_acos)
                suggested = current_bid * (1 - reduction)
            elif actual_acos < target_acos * 0.7:
                increase = min(max_adjustment_pct, 0.3)
                suggested = current_bid * (1 + increase)
            else:
                suggested = current_bid

        elif strategy == "rule_based":
            rules = params.get("rules", [])
            suggested = current_bid
            for rule in rules:
                if self._match_bid_rule(rule, actual_acos, target_acos, ctr, cr):
                    action = rule.get("action", {})
                    if action.get("type") == "set":
                        suggested = action.get("value", current_bid)
                    elif action.get("type") == "multiply":
                        suggested = current_bid * action.get("factor", 1.0)
                    elif action.get("type") == "adjust_pct":
                        suggested = current_bid * (1 + action.get("pct", 0.0))
                    break
        else:
            suggested = current_bid

        return max(min_bid, min(max_bid, round(suggested, 2)))

    def _match_bid_rule(self, rule: dict, actual_acos: float, target_acos: float,
                         ctr: float, cr: float) -> bool:
        conditions = rule.get("conditions", {})
        for key, value in conditions.items():
            if (key == "acos_gt" and actual_acos <= value) or (key == "acos_lt" and actual_acos >= value) or (key == "ctr_gt" and ctr <= value) or (key == "ctr_lt" and ctr >= value) or (key == "cr_gt" and cr <= value) or (key == "cr_lt" and cr >= value):
                return False
        return True

    def _generate_reason(self, strategy: str, current_bid: float, suggested_bid: float,
                          actual_acos: float, target_acos: float) -> str:
        if abs(suggested_bid - current_bid) < 0.01:
            return f"[{strategy}] 出价维持不变"
        if suggested_bid > current_bid:
            return f"[{strategy}] ACoS {actual_acos:.1%} 低于目标 {target_acos:.1%}，建议提高出价"
        return f"[{strategy}] ACoS {actual_acos:.1%} 高于目标 {target_acos:.1%}，建议降低出价"
