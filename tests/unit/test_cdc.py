from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from erp.modules.sys.domain.cdc_models import (
    CDCEvent,
    CDCOperation,
    CDCStatus,
    DirectCDCHandler,
    KafkaCDCHandler,
)


class TestCDCEvent:
    def test_create_event(self):
        event = CDCEvent(
            source_schema="oms",
            source_table="orders",
            operation=CDCOperation.INSERT.value,
            after_data={"id": "123", "status": "pending"},
            tenant_id="tenant-1",
            timestamp=datetime.now(UTC).isoformat(),
        )
        assert event.source_schema == "oms"
        assert event.operation == "c"

    def test_event_with_before_after(self):
        event = CDCEvent(
            source_schema="wms",
            source_table="inventory",
            operation=CDCOperation.UPDATE.value,
            before_data={"quantity": 100},
            after_data={"quantity": 80},
            changed_columns=["quantity"],
        )
        assert event.operation == "u"
        assert "quantity" in event.changed_columns


class TestKafkaCDCHandler:
    @pytest.mark.asyncio
    async def test_handle_event(self):
        handler = KafkaCDCHandler(topic_name="erp.oms.order.changed.v1")
        event = CDCEvent(
            source_schema="oms",
            source_table="orders",
            operation=CDCOperation.INSERT.value,
            after_data={"id": "123"},
            tenant_id="tenant-1",
            timestamp=datetime.now(UTC).isoformat(),
        )
        result = await handler.handle(event)
        assert result["handler"] == "kafka"
        assert result["topic"] == "erp.oms.order.changed.v1"
        assert result["status"] == "sent_to_kafka"
        assert result["message_size"] > 0


class TestDirectCDCHandler:
    @pytest.mark.asyncio
    async def test_handle_event_without_callback(self):
        handler = DirectCDCHandler()
        event = CDCEvent(
            source_schema="fms",
            source_table="cost_event",
            operation=CDCOperation.INSERT.value,
            after_data={"id": "456"},
        )
        result = await handler.handle(event)
        assert result["handler"] == "direct"
        assert result["status"] == "processed"

    @pytest.mark.asyncio
    async def test_handle_event_with_callback(self):
        callback = AsyncMock()
        handler = DirectCDCHandler(callback=callback)
        event = CDCEvent(
            source_schema="fms",
            source_table="cost_event",
            operation=CDCOperation.DELETE.value,
            before_data={"id": "789"},
        )
        result = await handler.handle(event)
        assert result["status"] == "processed"
        callback.assert_called_once_with(event)


class TestCDCOperationEnum:
    def test_operation_values(self):
        assert CDCOperation.INSERT.value == "c"
        assert CDCOperation.UPDATE.value == "u"
        assert CDCOperation.DELETE.value == "d"
        assert CDCOperation.SNAPSHOT.value == "r"


class TestCDCStatusEnum:
    def test_status_values(self):
        assert CDCStatus.PENDING.value == "pending"
        assert CDCStatus.PROCESSED.value == "processed"
        assert CDCStatus.FAILED.value == "failed"
        assert CDCStatus.SKIPPED.value == "skipped"
        assert CDCStatus.RETRYING.value == "retrying"
