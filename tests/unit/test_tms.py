from unittest.mock import AsyncMock, MagicMock

import pytest

from erp.modules.tms.application.services import (
    SHIPMENT_STATUS_TRANSITIONS,
    ShipmentService,
)
from erp.modules.tms.domain.models import Shipment
from erp.shared.exceptions import ValidationException


def _make_session():
    mock = AsyncMock()
    mock.add = MagicMock()
    mock.flush = AsyncMock()
    return mock


class TestShipmentStatusTransitions:
    def test_pending_can_go_to_picked_up(self):
        assert "picked_up" in SHIPMENT_STATUS_TRANSITIONS["pending"]

    def test_in_transit_can_go_to_out_for_delivery(self):
        assert "out_for_delivery" in SHIPMENT_STATUS_TRANSITIONS["in_transit"]

    def test_exception_can_go_back_to_in_transit(self):
        assert "in_transit" in SHIPMENT_STATUS_TRANSITIONS["exception"]

    def test_completed_is_terminal(self):
        assert SHIPMENT_STATUS_TRANSITIONS["completed"] == []

    def test_cancelled_is_terminal(self):
        assert SHIPMENT_STATUS_TRANSITIONS["cancelled"] == []

    def test_delivered_can_go_to_completed(self):
        assert "completed" in SHIPMENT_STATUS_TRANSITIONS["delivered"]


class TestShipmentCostValidation:
    @pytest.mark.asyncio
    async def test_create_shipment_negative_cost(self):
        mock_session = _make_session()
        svc = ShipmentService(mock_session)
        with pytest.raises(ValidationException, match="negative"):
            await svc.create("t1", "SHP001", "ord1", "wh1", "prov1", "sm1",
                             shipping_cost=-50.0)

    @pytest.mark.asyncio
    async def test_create_shipment_cost_exceeds_max(self):
        mock_session = _make_session()
        svc = ShipmentService(mock_session)
        with pytest.raises(ValidationException, match="exceeds maximum"):
            await svc.create("t1", "SHP001", "ord1", "wh1", "prov1", "sm1",
                             shipping_cost=200000.0)

    @pytest.mark.asyncio
    async def test_create_shipment_negative_weight(self):
        mock_session = _make_session()
        svc = ShipmentService(mock_session)
        with pytest.raises(ValidationException, match="negative"):
            await svc.create("t1", "SHP001", "ord1", "wh1", "prov1", "sm1",
                             weight=-5.0)

    @pytest.mark.asyncio
    async def test_create_shipment_weight_exceeds_max(self):
        mock_session = _make_session()
        svc = ShipmentService(mock_session)
        with pytest.raises(ValidationException, match="exceeds maximum"):
            await svc.create("t1", "SHP001", "ord1", "wh1", "prov1", "sm1",
                             weight=2000.0)

    @pytest.mark.asyncio
    async def test_create_shipment_valid(self):
        mock_session = _make_session()
        svc = ShipmentService(mock_session)
        result = await svc.create("t1", "SHP001", "ord1", "wh1", "prov1", "sm1",
                                  shipping_cost=50.0, weight=10.0)
        assert result is not None


class TestShipmentStatusValidation:
    @pytest.mark.asyncio
    async def test_update_status_invalid_transition(self):
        mock_session = _make_session()
        shipment = Shipment(id="s1", tenant_id="t1", shipment_no="SHP001",
                            order_id="ord1", warehouse_id="wh1",
                            provider_id="prov1", shipping_method_id="sm1",
                            status="pending")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=shipment))
        )
        svc = ShipmentService(mock_session)
        with pytest.raises(ValidationException, match="Cannot transition shipment"):
            await svc.update_status("s1", "t1", "delivered")

    @pytest.mark.asyncio
    async def test_update_status_valid_transition(self):
        mock_session = _make_session()
        shipment = Shipment(id="s1", tenant_id="t1", shipment_no="SHP001",
                            order_id="ord1", warehouse_id="wh1",
                            provider_id="prov1", shipping_method_id="sm1",
                            status="pending")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=shipment))
        )
        svc = ShipmentService(mock_session)
        result = await svc.update_status("s1", "t1", "picked_up")
        assert result.status == "picked_up"
