from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, select, update

from erp.shared.events.outbox import IdempotencyRecord, OutboxMessage
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from erp.shared.events.domain_event import DomainEvent

logger = get_logger("erp.outbox")


class OutboxRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, event: DomainEvent) -> OutboxMessage:
        payload_str = json.dumps(event.payload, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()[:16]
        msg = OutboxMessage(
            event_id=event.event_id,
            event_type=event.event_type,
            event_version=event.event_version,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            tenant_id=event.tenant_id,
            payload=payload_str,
            payload_hash=payload_hash,
            status="pending",
        )
        self._session.add(msg)
        await self._session.flush()
        return msg

    async def get_pending(self, limit: int = 100) -> list[OutboxMessage]:
        stmt = (
            select(OutboxMessage)
            .where(OutboxMessage.status == "pending", OutboxMessage.retry_count < OutboxMessage.max_retries)
            .order_by(OutboxMessage.created_at)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_published(self, message_id: str) -> None:
        stmt = (
            update(OutboxMessage)
            .where(OutboxMessage.id == message_id)
            .values(status="published", published_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def mark_failed(self, message_id: str) -> None:
        stmt = (
            update(OutboxMessage)
            .where(OutboxMessage.id == message_id)
            .values(retry_count=OutboxMessage.retry_count + 1)
        )
        await self._session.execute(stmt)
        await self._session.flush()


class IdempotencyService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def check_and_record(
        self,
        idempotency_key: str,
        tenant_id: str,
        request_data: dict | None = None,
    ) -> IdempotencyRecord | None:
        stmt = select(IdempotencyRecord).where(
            and_(
                IdempotencyRecord.idempotency_key == idempotency_key,
                IdempotencyRecord.tenant_id == tenant_id,
            )
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        return None

    async def record(
        self,
        idempotency_key: str,
        tenant_id: str,
        request_data: dict | None = None,
        response_data: dict | None = None,
    ) -> IdempotencyRecord:
        request_hash = ""
        if request_data:
            request_hash = hashlib.sha256(json.dumps(request_data, sort_keys=True, default=str).encode()).hexdigest()[:16]
        record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            request_hash=request_hash,
            response_data=json.dumps(response_data or {}, default=str),
            status="completed",
        )
        self._session.add(record)
        await self._session.flush()
        return record
