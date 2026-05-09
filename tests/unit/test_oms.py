from unittest.mock import AsyncMock, MagicMock

import pytest

from erp.modules.oms.application.services import (
    ORDER_STATUS_TRANSITIONS,
    REFUND_STATUS_TRANSITIONS,
    RefundOrderService,
    SalesOrderService,
)
from erp.modules.oms.domain.models import RefundOrder, SalesOrder
from erp.shared.exceptions import ValidationException


class TestOrderStatusTransitions:
    def test_pending_can_go_to_confirmed(self):
        assert "confirmed" in ORDER_STATUS_TRANSITIONS["pending"]

    def test_confirmed_can_go_to_processing(self):
        assert "processing" in ORDER_STATUS_TRANSITIONS["confirmed"]

    def test_processing_can_go_to_shipped(self):
        assert "shipped" in ORDER_STATUS_TRANSITIONS["processing"]

    def test_completed_is_terminal(self):
        assert ORDER_STATUS_TRANSITIONS["completed"] == []

    def test_cancelled_is_terminal(self):
        assert ORDER_STATUS_TRANSITIONS["cancelled"] == []

    def test_refunded_is_terminal(self):
        assert ORDER_STATUS_TRANSITIONS["refunded"] == []


class TestRefundStatusTransitions:
    def test_pending_can_go_to_approved(self):
        assert "approved" in REFUND_STATUS_TRANSITIONS["pending"]

    def test_pending_can_go_to_rejected(self):
        assert "rejected" in REFUND_STATUS_TRANSITIONS["pending"]

    def test_processing_can_go_to_completed(self):
        assert "completed" in REFUND_STATUS_TRANSITIONS["processing"]

    def test_completed_is_terminal(self):
        assert REFUND_STATUS_TRANSITIONS["completed"] == []

    def test_failed_can_retry(self):
        assert "processing" in REFUND_STATUS_TRANSITIONS["failed"]


class TestOrderRiskValidation:
    @pytest.mark.asyncio
    async def test_create_order_exceeds_max_amount(self):
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        svc = SalesOrderService(mock_session)
        with pytest.raises(ValidationException, match="exceeds maximum"):
            await svc.create("t1", "ORD001", "amazon", "store1",
                             total_amount=600000.0)

    @pytest.mark.asyncio
    async def test_add_item_negative_quantity(self):
        mock_session = AsyncMock()
        svc = SalesOrderService(mock_session)
        with pytest.raises(ValidationException, match="positive"):
            await svc.add_item("t1", "ord1", "sku1", quantity=-5, unit_price=10.0)

    @pytest.mark.asyncio
    async def test_add_item_quantity_exceeds_max(self):
        mock_session = AsyncMock()
        svc = SalesOrderService(mock_session)
        with pytest.raises(ValidationException, match="exceeds maximum"):
            await svc.add_item("t1", "ord1", "sku1", quantity=20000, unit_price=10.0)

    @pytest.mark.asyncio
    async def test_add_item_negative_price(self):
        mock_session = AsyncMock()
        svc = SalesOrderService(mock_session)
        with pytest.raises(ValidationException, match="negative"):
            await svc.add_item("t1", "ord1", "sku1", quantity=5, unit_price=-10.0)

    @pytest.mark.asyncio
    async def test_add_item_to_shipped_order_fails(self):
        mock_session = AsyncMock()
        order = SalesOrder(id="ord1", tenant_id="t1", order_no="ORD001",
                           platform="amazon", store_id="store1", status="shipped",
                           total_amount=100.0)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=order))
        )
        svc = SalesOrderService(mock_session)
        with pytest.raises(ValidationException, match="Cannot add items"):
            await svc.add_item("t1", "ord1", "sku1", quantity=5, unit_price=10.0)


class TestRefundStatusValidation:
    @pytest.mark.asyncio
    async def test_update_refund_status_invalid_transition(self):
        mock_session = AsyncMock()
        refund = RefundOrder(id="r1", tenant_id="t1", refund_no="REF001",
                             original_order_id="ord1", refund_type="return",
                             refund_amount=100.0, status="pending")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=refund))
        )
        svc = RefundOrderService(mock_session)
        with pytest.raises(ValidationException, match="Cannot transition refund"):
            await svc.update_status("r1", "t1", "completed")
