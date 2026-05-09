from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class WebhookStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    ABANDONED = "abandoned"


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscription"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    event_types: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    callback_url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    http_method: Mapped[str] = mapped_column(String(10), nullable=False, default="POST")
    headers_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class WebhookDelivery(Base):
    __tablename__ = "webhook_delivery"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    subscription_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_response_status: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_response_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_error: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class WebhookService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_subscription(self, tenant_id: str, name: str, event_types: list[str],
                                   callback_url: str, secret: str = "",
                                   http_method: str = "POST", headers: dict | None = None,
                                   max_retries: int = 3, retry_interval_seconds: int = 60,
                                   timeout_seconds: int = 30) -> WebhookSubscription:
        sub = WebhookSubscription(
            tenant_id=tenant_id, name=name,
            event_types=json.dumps(event_types, default=str),
            callback_url=callback_url, secret=secret,
            http_method=http_method,
            headers_json=json.dumps(headers or {}, default=str),
            max_retries=max_retries,
            retry_interval_seconds=retry_interval_seconds,
            timeout_seconds=timeout_seconds,
            created_by=actor_id_var.get(""),
        )
        self.session.add(sub)
        await self.session.flush()
        return sub

    async def update_subscription(self, subscription_id: str, tenant_id: str, **kwargs) -> WebhookSubscription:
        sub = await self._get_subscription(subscription_id, tenant_id)
        if not sub:
            raise NotFoundException(message=f"Webhook subscription '{subscription_id}' not found")
        for k, v in kwargs.items():
            if hasattr(sub, k) and k not in ("id", "tenant_id"):
                if k == "event_types" and isinstance(v, list):
                    v = json.dumps(v, default=str)
                elif k == "headers" and isinstance(v, dict):
                    sub.headers_json = json.dumps(v, default=str)
                    continue
                setattr(sub, k, v)
        await self.session.flush()
        return sub

    async def delete_subscription(self, subscription_id: str, tenant_id: str):
        sub = await self._get_subscription(subscription_id, tenant_id)
        if not sub:
            raise NotFoundException(message=f"Webhook subscription '{subscription_id}' not found")
        await self.session.delete(sub)
        await self.session.flush()

    async def trigger_event(self, tenant_id: str, event_type: str,
                             payload: dict | None = None) -> list[WebhookDelivery]:
        stmt = select(WebhookSubscription).where(
            WebhookSubscription.tenant_id == tenant_id,
            WebhookSubscription.status == "active",
        )
        result = await self.session.execute(stmt)
        subscriptions = list(result.scalars().all())

        deliveries = []
        for sub in subscriptions:
            event_types = json.loads(sub.event_types)
            if event_types and event_type not in event_types:
                continue

            delivery = WebhookDelivery(
                tenant_id=tenant_id, subscription_id=sub.id,
                event_type=event_type,
                payload_json=json.dumps(payload or {}, default=str),
                max_attempts=sub.max_retries,
                next_retry_at=datetime.now(UTC),
                trace_id=trace_id_var.get(""),
            )
            self.session.add(delivery)
            deliveries.append(delivery)

            sub.last_triggered_at = datetime.now(UTC)

        if deliveries:
            await self.session.flush()
        return deliveries

    async def retry_delivery(self, delivery_id: str, tenant_id: str) -> WebhookDelivery:
        delivery = await self._get_delivery(delivery_id, tenant_id)
        if not delivery:
            raise NotFoundException(message=f"Webhook delivery '{delivery_id}' not found")

        if delivery.status in ("success", "abandoned"):
            raise ValidationException(message=f"Cannot retry delivery in status '{delivery.status}'")

        delivery.attempt_count += 1
        if delivery.attempt_count >= delivery.max_attempts:
            delivery.status = "abandoned"
        else:
            delivery.status = "retrying"
            sub = await self._get_subscription(delivery.subscription_id, tenant_id)
            interval = sub.retry_interval_seconds if sub else 60
            delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=interval * delivery.attempt_count)

        await self.session.flush()
        return delivery

    async def mark_delivery_success(self, delivery_id: str, tenant_id: str,
                                     response_status: int = 200,
                                     response_body: str = "") -> WebhookDelivery:
        delivery = await self._get_delivery(delivery_id, tenant_id)
        if not delivery:
            raise NotFoundException(message=f"Webhook delivery '{delivery_id}' not found")
        delivery.status = "success"
        delivery.last_response_status = response_status
        delivery.last_response_body = response_body[:5000]
        delivery.attempt_count += 1

        sub = await self._get_subscription(delivery.subscription_id, tenant_id)
        if sub:
            sub.last_success_at = datetime.now(UTC)
            sub.consecutive_failures = 0
            sub.last_error = ""

        await self.session.flush()
        return delivery

    async def mark_delivery_failed(self, delivery_id: str, tenant_id: str,
                                    error: str = "", response_status: int = 0) -> WebhookDelivery:
        delivery = await self._get_delivery(delivery_id, tenant_id)
        if not delivery:
            raise NotFoundException(message=f"Webhook delivery '{delivery_id}' not found")

        delivery.last_error = error[:500]
        delivery.last_response_status = response_status
        delivery.attempt_count += 1

        sub = await self._get_subscription(delivery.subscription_id, tenant_id)
        if sub:
            sub.consecutive_failures += 1
            sub.last_error = error[:500]
            if sub.consecutive_failures >= 10:
                sub.status = "error"

        if delivery.attempt_count >= delivery.max_attempts:
            delivery.status = "abandoned"
        else:
            delivery.status = "retrying"
            interval = sub.retry_interval_seconds if sub else 60
            delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=interval * delivery.attempt_count)

        await self.session.flush()
        return delivery

    async def list_subscriptions(self, tenant_id: str, status: str = "") -> list[WebhookSubscription]:
        conditions = [WebhookSubscription.tenant_id == tenant_id]
        if status:
            conditions.append(WebhookSubscription.status == status)
        stmt = select(WebhookSubscription).where(*conditions).order_by(WebhookSubscription.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_deliveries(self, tenant_id: str, subscription_id: str = "",
                               event_type: str = "", status: str = "",
                               page: int = 1, page_size: int = 20) -> tuple[list[WebhookDelivery], int]:
        conditions = [WebhookDelivery.tenant_id == tenant_id]
        if subscription_id:
            conditions.append(WebhookDelivery.subscription_id == subscription_id)
        if event_type:
            conditions.append(WebhookDelivery.event_type == event_type)
        if status:
            conditions.append(WebhookDelivery.status == status)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(WebhookDelivery).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(WebhookDelivery).where(*conditions).order_by(
            WebhookDelivery.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_pending_retries(self, tenant_id: str) -> list[WebhookDelivery]:
        now = datetime.now(UTC)
        stmt = select(WebhookDelivery).where(
            WebhookDelivery.tenant_id == tenant_id,
            WebhookDelivery.status.in_(["pending", "retrying"]),
            WebhookDelivery.next_retry_at <= now,
        ).order_by(WebhookDelivery.next_retry_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_subscription(self, subscription_id: str, tenant_id: str) -> WebhookSubscription | None:
        stmt = select(WebhookSubscription).where(
            WebhookSubscription.id == subscription_id,
            WebhookSubscription.tenant_id == tenant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _get_delivery(self, delivery_id: str, tenant_id: str) -> WebhookDelivery | None:
        stmt = select(WebhookDelivery).where(
            WebhookDelivery.id == delivery_id,
            WebhookDelivery.tenant_id == tenant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
