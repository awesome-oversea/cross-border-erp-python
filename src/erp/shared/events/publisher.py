from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from erp.shared.events.domain_event import DomainEvent

logger = get_logger("erp.events")


class EventPublisher:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}
        self._outbox: list[dict[str, Any]] = []

    def subscribe(self, event_type: str, handler: Callable) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        if event_type in self._handlers:
            self._handlers[event_type] = [h for h in self._handlers[event_type] if h != handler]

    async def publish(self, event: DomainEvent) -> None:
        event.published_at = event.published_at or __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        if not event.payload_hash and event.payload:
            event.payload_hash = hashlib.sha256(json.dumps(event.payload, sort_keys=True, default=str).encode()).hexdigest()[:16]

        event_dict = event.to_dict()
        self._outbox.append(event_dict)

        handlers = self._handlers.get(event.event_type, [])
        handlers += self._handlers.get("*", [])

        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    "event_handler_failed",
                    event_type=event.event_type,
                    handler=handler.__name__,
                    error=str(e),
                )

        logger.info(
            "event_published",
            event_type=event.event_type,
            event_id=event.event_id,
            domain=event.domain,
            aggregate_id=event.aggregate_id,
        )

    async def publish_many(self, events: list[DomainEvent]) -> None:
        for event in events:
            await self.publish(event)

    async def replay_event(self, event_dict: dict[str, Any]) -> None:
        event = __import__("erp.shared.events.domain_event", fromlist=["DomainEvent"]).DomainEvent.from_dict(event_dict)
        handlers = self._handlers.get(event.event_type, [])
        handlers += self._handlers.get("*", [])

        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    "event_replay_handler_failed",
                    event_type=event.event_type,
                    handler=handler.__name__,
                    error=str(e),
                )

        logger.info(
            "event_replayed",
            event_type=event.event_type,
            event_id=event.event_id,
            domain=event.domain,
            aggregate_id=event.aggregate_id,
        )

    def peek_outbox_entries(self) -> list[dict[str, Any]]:
        return self._outbox.copy()

    def get_outbox_entries(self) -> list[dict[str, Any]]:
        entries = self._outbox.copy()
        self._outbox.clear()
        return entries

    def clear_outbox(self) -> None:
        self._outbox.clear()


_event_publisher: EventPublisher | None = None


def get_event_publisher() -> EventPublisher:
    global _event_publisher
    if _event_publisher is None:
        _event_publisher = EventPublisher()
    return _event_publisher
