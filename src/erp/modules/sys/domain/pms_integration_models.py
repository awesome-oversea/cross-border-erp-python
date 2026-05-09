from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.events.domain_event import (
    RecommendationAccepted,
    RecommendationApproved,
    RecommendationEffectMeasured,
    RecommendationExecuted,
    RecommendationFailed,
    RecommendationRejected,
    RecommendationRolledBack,
)
from erp.shared.events.publisher import get_event_publisher
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FeedbackRecord(Base):
    __tablename__ = "pms_feedback_record"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    erp_reference_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    feedback_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True,
                                                comment="accepted/rejected/executed/failed/rolled_back/effect_measured")
    feedback_reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    feedback_detail: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    effect_metrics: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    operator_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    operator_type: Mapped[str] = mapped_column(String(50), nullable=False, default="user")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EventSubscription(Base):
    __tablename__ = "pms_event_subscription"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    subscriber_name: Mapped[str] = mapped_column(String(200), nullable=False)
    subscriber_type: Mapped[str] = mapped_column(String(50), nullable=False, default="pms",
                                                  comment="pms/external_system/webhook")
    event_types: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    domains: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    callback_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    secret_key: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    retry_policy: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class GrayRolloutConfig(Base):
    __tablename__ = "pms_gray_rollout_config"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scene: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    rollout_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="0-100")
    rollout_strategy: Mapped[str] = mapped_column(String(50), nullable=False, default="random",
                                                   comment="random/user_list/org_list")
    target_user_list: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    target_org_list: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    auto_rollback_on_error_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.50")
    )
    auto_rollback_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    monitoring_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    min_sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    current_error_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0"))
    current_sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rollback_reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PMSFeedbackService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def submit_feedback(self, tenant_id: str, recommendation_id: str,
                               erp_reference_id: str, domain: str,
                               feedback_type: str, feedback_reason: str = "",
                               feedback_detail: dict | None = None,
                               effect_metrics: dict | None = None,
                               operator_id: str = "", operator_type: str = "user") -> FeedbackRecord:
        record = FeedbackRecord(
            tenant_id=tenant_id, recommendation_id=recommendation_id,
            erp_reference_id=erp_reference_id, domain=domain,
            feedback_type=feedback_type, feedback_reason=feedback_reason,
            feedback_detail=json.dumps(feedback_detail or {}, default=str),
            effect_metrics=json.dumps(effect_metrics or {}, default=str),
            operator_id=operator_id or actor_id_var.get(""),
            operator_type=operator_type,
            trace_id=trace_id_var.get(""),
        )
        self.session.add(record)
        await self.session.flush()

        await self._publish_feedback_event(tenant_id, recommendation_id, erp_reference_id,
                                            domain, feedback_type, feedback_reason,
                                            feedback_detail, effect_metrics)

        return record

    async def _publish_feedback_event(self, tenant_id: str, recommendation_id: str,
                                       erp_reference_id: str, domain: str,
                                       feedback_type: str, feedback_reason: str,
                                       feedback_detail: dict | None,
                                       effect_metrics: dict | None):
        publisher = get_event_publisher()
        detail = feedback_detail or {}

        event_map = {
            "accepted": RecommendationAccepted,
            "rejected": RecommendationRejected,
            "approved": RecommendationApproved,
            "executed": RecommendationExecuted,
            "failed": RecommendationFailed,
            "rolled_back": RecommendationRolledBack,
        }

        event_cls = event_map.get(feedback_type)
        if event_cls:
            kwargs = {
                "tenant_id": tenant_id, "domain": domain,
                "aggregate_id": recommendation_id,
                "trace_id": trace_id_var.get(""),
                "actor": actor_id_var.get(""),
                "recommendation_id": recommendation_id,
                "erp_reference_id": erp_reference_id,
            }
            if feedback_type == "rejected":
                kwargs["rejection_reason"] = feedback_reason
            elif feedback_type == "executed":
                kwargs["execution_result"] = detail
            elif feedback_type == "failed":
                kwargs["failure_reason"] = feedback_reason
            elif feedback_type == "rolled_back":
                kwargs["rollback_reason"] = feedback_reason

            event = event_cls(**kwargs)
            await publisher.publish(event)

        if feedback_type == "effect_measured":
            event = RecommendationEffectMeasured(
                tenant_id=tenant_id, domain="bi",
                aggregate_id=recommendation_id,
                trace_id=trace_id_var.get(""),
                actor=actor_id_var.get(""),
                recommendation_id=recommendation_id,
                erp_reference_id=erp_reference_id,
                measured_result=effect_metrics or {},
            )
            await publisher.publish(event)

    async def replay_feedback(self, feedback_id: str, tenant_id: str) -> FeedbackRecord:
        stmt = select(FeedbackRecord).where(
            FeedbackRecord.id == feedback_id,
            FeedbackRecord.tenant_id == tenant_id,
        )
        record = (await self.session.execute(stmt)).scalar_one_or_none()
        if not record:
            raise NotFoundException(message=f"Feedback '{feedback_id}' not found")

        await self._publish_feedback_event(
            tenant_id=record.tenant_id,
            recommendation_id=record.recommendation_id,
            erp_reference_id=record.erp_reference_id,
            domain=record.domain,
            feedback_type=record.feedback_type,
            feedback_reason=record.feedback_reason,
            feedback_detail=json.loads(record.feedback_detail) if record.feedback_detail else {},
            effect_metrics=json.loads(record.effect_metrics) if record.effect_metrics else {},
        )
        return record

    async def list_feedback(self, tenant_id: str, recommendation_id: str = "",
                             domain: str = "", feedback_type: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[list[FeedbackRecord], int]:
        conditions = [FeedbackRecord.tenant_id == tenant_id]
        if recommendation_id:
            conditions.append(FeedbackRecord.recommendation_id == recommendation_id)
        if domain:
            conditions.append(FeedbackRecord.domain == domain)
        if feedback_type:
            conditions.append(FeedbackRecord.feedback_type == feedback_type)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(FeedbackRecord).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(FeedbackRecord).where(*conditions).order_by(
            FeedbackRecord.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total


class PMSEventSubscriptionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_subscription(self, tenant_id: str, subscriber_name: str,
                                   subscriber_type: str = "pms",
                                   event_types: list | None = None,
                                   domains: list | None = None,
                                   callback_url: str = "",
                                   secret_key: str = "",
                                   retry_policy: dict | None = None) -> EventSubscription:
        sub = EventSubscription(
            tenant_id=tenant_id, subscriber_name=subscriber_name,
            subscriber_type=subscriber_type,
            event_types=json.dumps(event_types or [], default=str),
            domains=json.dumps(domains or [], default=str),
            callback_url=callback_url, secret_key=secret_key,
            retry_policy=json.dumps(retry_policy or {"max_retries": 3, "backoff_seconds": [5, 30, 120]}, default=str),
            created_by=actor_id_var.get(""),
        )
        self.session.add(sub)
        await self.session.flush()
        return sub

    async def update_subscription(self, subscription_id: str, tenant_id: str,
                                   subscriber_name: str | None = None,
                                   event_types: list | None = None,
                                   domains: list | None = None,
                                   callback_url: str | None = None,
                                   retry_policy: dict | None = None) -> EventSubscription:
        sub = await self._get_by_id(subscription_id, tenant_id)
        if not sub:
            raise NotFoundException(message=f"Subscription '{subscription_id}' not found")
        if subscriber_name is not None:
            sub.subscriber_name = subscriber_name
        if event_types is not None:
            sub.event_types = json.dumps(event_types, default=str)
        if domains is not None:
            sub.domains = json.dumps(domains, default=str)
        if callback_url is not None:
            sub.callback_url = callback_url
        if retry_policy is not None:
            sub.retry_policy = json.dumps(retry_policy, default=str)
        await self.session.flush()
        return sub

    async def deactivate_subscription(self, subscription_id: str, tenant_id: str) -> EventSubscription:
        sub = await self._get_by_id(subscription_id, tenant_id)
        if not sub:
            raise NotFoundException(message=f"Subscription '{subscription_id}' not found")
        sub.is_active = False
        await self.session.flush()
        return sub

    async def list_subscriptions(self, tenant_id: str, subscriber_type: str = "",
                                  is_active: bool | None = None) -> list[EventSubscription]:
        conditions = [EventSubscription.tenant_id == tenant_id]
        if subscriber_type:
            conditions.append(EventSubscription.subscriber_type == subscriber_type)
        if is_active is not None:
            conditions.append(EventSubscription.is_active == is_active)
        stmt = select(EventSubscription).where(*conditions).order_by(EventSubscription.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_subscribers_for_event(self, tenant_id: str, event_type: str,
                                                domain: str = "") -> list[EventSubscription]:
        stmt = select(EventSubscription).where(
            EventSubscription.tenant_id == tenant_id,
            EventSubscription.is_active,
        )
        result = await self.session.execute(stmt)
        all_subs = list(result.scalars().all())

        matched = []
        for sub in all_subs:
            sub_events = json.loads(sub.event_types)
            sub_domains = json.loads(sub.domains)
            event_match = not sub_events or event_type in sub_events or any(
                event_type.startswith(e.replace("*", "")) for e in sub_events if "*" in e
            )
            domain_match = not sub_domains or domain in sub_domains
            if event_match and domain_match:
                matched.append(sub)
        return matched

    async def replay_events(self, tenant_id: str, subscription_id: str, event_type: str = "", domain: str = "") -> list[dict]:
        sub = await self._get_by_id(subscription_id, tenant_id)
        if not sub:
            raise NotFoundException(message=f"Subscription '{subscription_id}' not found")

        publisher = get_event_publisher()
        entries = publisher.peek_outbox_entries()
        matched = []
        for entry in entries:
            if entry.get("tenant_id") != tenant_id:
                continue
            if event_type and entry.get("event_type") != event_type:
                continue
            if domain and entry.get("domain") != domain:
                continue
            sub_events = json.loads(sub.event_types)
            sub_domains = json.loads(sub.domains)
            event_match = not sub_events or entry.get("event_type") in sub_events or any(
                str(entry.get("event_type", "")).startswith(e.replace("*", "")) for e in sub_events if "*" in e
            )
            domain_match = not sub_domains or entry.get("domain") in sub_domains
            if event_match and domain_match:
                await publisher.replay_event(entry)
                matched.append(entry)

        return matched

    async def _get_by_id(self, subscription_id: str, tenant_id: str) -> EventSubscription | None:
        stmt = select(EventSubscription).where(
            EventSubscription.id == subscription_id,
            EventSubscription.tenant_id == tenant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class GrayRolloutService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_config(self, tenant_id: str, domain: str, scene: str = "default",
                             rollout_percent: int = 0, rollout_strategy: str = "random",
                             target_user_list: list | None = None,
                             target_org_list: list | None = None,
                             auto_rollback_on_error_rate: float = 0.5,
                             auto_rollback_window_minutes: int = 30,
                             monitoring_window_minutes: int = 60,
                             min_sample_size: int = 10) -> GrayRolloutConfig:
        existing = await self._get_by_domain_scene(tenant_id, domain, scene)
        if existing:
            raise ValidationException(message=f"Gray rollout config for {domain}/{scene} already exists")

        config = GrayRolloutConfig(
            tenant_id=tenant_id, domain=domain, scene=scene,
            rollout_percent=min(max(rollout_percent, 0), 100),
            rollout_strategy=rollout_strategy,
            target_user_list=json.dumps(target_user_list or [], default=str),
            target_org_list=json.dumps(target_org_list or [], default=str),
            auto_rollback_on_error_rate=Decimal(str(auto_rollback_on_error_rate)),
            auto_rollback_window_minutes=auto_rollback_window_minutes,
            monitoring_window_minutes=monitoring_window_minutes,
            min_sample_size=min_sample_size,
            created_by=actor_id_var.get(""),
        )
        self.session.add(config)
        await self.session.flush()
        return config

    async def update_rollout_percent(self, config_id: str, tenant_id: str,
                                      rollout_percent: int) -> GrayRolloutConfig:
        config = await self._get_by_id(config_id, tenant_id)
        if not config:
            raise NotFoundException(message=f"Gray rollout config '{config_id}' not found")
        config.rollout_percent = min(max(rollout_percent, 0), 100)
        config.rolled_back_at = None
        config.rollback_reason = ""
        await self.session.flush()
        return config

    async def check_should_execute(self, tenant_id: str, domain: str,
                                     scene: str = "default",
                                     user_id: str = "", org_id: str = "") -> bool:
        config = await self._get_by_domain_scene(tenant_id, domain, scene)
        if not config or not config.is_active:
            return False

        if config.rolled_back_at:
            return False

        if config.rollout_strategy == "user_list":
            target_users = json.loads(config.target_user_list)
            return bool(user_id and user_id in target_users)
        elif config.rollout_strategy == "org_list":
            target_orgs = json.loads(config.target_org_list)
            return bool(org_id and org_id in target_orgs)
        else:
            import random
            return random.randint(1, 100) <= config.rollout_percent

    async def record_execution_result(self, config_id: str, tenant_id: str,
                                       is_error: bool) -> GrayRolloutConfig:
        config = await self._get_by_id(config_id, tenant_id)
        if not config:
            raise NotFoundException(message=f"Gray rollout config '{config_id}' not found")

        config.current_sample_count += 1
        if is_error:
            error_count = int(float(config.current_error_rate) * (config.current_sample_count - 1) / 100) + 1
            config.current_error_rate = Decimal(str(round(error_count / config.current_sample_count * 100, 2)))
        else:
            error_count = int(float(config.current_error_rate) * (config.current_sample_count - 1) / 100)
            config.current_error_rate = Decimal(str(round(error_count / config.current_sample_count * 100, 2)))

        config.last_checked_at = datetime.now(UTC)

        if (config.current_sample_count >= config.min_sample_size and
                float(config.current_error_rate) >= float(config.auto_rollback_on_error_rate)):
            config.rollout_percent = 0
            config.rolled_back_at = datetime.now(UTC)
            config.rollback_reason = f"Auto-rollback: error rate {config.current_error_rate}% >= threshold {config.auto_rollback_on_error_rate}%"

        await self.session.flush()
        return config

    async def manual_rollback(self, config_id: str, tenant_id: str,
                               reason: str = "") -> GrayRolloutConfig:
        config = await self._get_by_id(config_id, tenant_id)
        if not config:
            raise NotFoundException(message=f"Gray rollout config '{config_id}' not found")
        config.rollout_percent = 0
        config.rolled_back_at = datetime.now(UTC)
        config.rollback_reason = reason or "Manual rollback"
        await self.session.flush()
        return config

    async def list_configs(self, tenant_id: str, domain: str = "") -> list[GrayRolloutConfig]:
        conditions = [GrayRolloutConfig.tenant_id == tenant_id]
        if domain:
            conditions.append(GrayRolloutConfig.domain == domain)
        stmt = select(GrayRolloutConfig).where(*conditions).order_by(GrayRolloutConfig.domain, GrayRolloutConfig.scene)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_by_domain_scene(self, tenant_id: str, domain: str, scene: str) -> GrayRolloutConfig | None:
        stmt = select(GrayRolloutConfig).where(
            GrayRolloutConfig.tenant_id == tenant_id,
            GrayRolloutConfig.domain == domain,
            GrayRolloutConfig.scene == scene,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _get_by_id(self, config_id: str, tenant_id: str) -> GrayRolloutConfig | None:
        stmt = select(GrayRolloutConfig).where(
            GrayRolloutConfig.id == config_id,
            GrayRolloutConfig.tenant_id == tenant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
