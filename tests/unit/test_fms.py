from unittest.mock import AsyncMock, MagicMock

import pytest

from erp.modules.fms.application.services import (
    PAYMENT_STATUS_TRANSITIONS,
    VALID_COST_TYPES,
    CostEventService,
    PaymentRecordService,
    ProfitCalculationService,
)
from erp.modules.fms.domain.models import PaymentRecord
from erp.shared.exceptions import ValidationException


def _make_session():
    mock = AsyncMock()
    mock.add = MagicMock()
    mock.flush = AsyncMock()
    return mock


class TestCostTypeValidation:
    def test_valid_cost_types_include_product_cost(self):
        assert "product_cost" in VALID_COST_TYPES

    def test_valid_cost_types_include_shipping(self):
        assert "shipping_cost" in VALID_COST_TYPES

    def test_valid_cost_types_include_tax(self):
        assert "tax" in VALID_COST_TYPES


class TestPaymentStatusTransitions:
    def test_pending_can_go_to_processing(self):
        assert "processing" in PAYMENT_STATUS_TRANSITIONS["pending"]

    def test_processing_can_go_to_completed(self):
        assert "completed" in PAYMENT_STATUS_TRANSITIONS["processing"]

    def test_completed_is_terminal(self):
        assert PAYMENT_STATUS_TRANSITIONS["completed"] == []

    def test_failed_can_retry(self):
        assert "pending" in PAYMENT_STATUS_TRANSITIONS["failed"]


class TestCostEventValidation:
    @pytest.mark.asyncio
    async def test_create_invalid_cost_type(self):
        mock_session = _make_session()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        svc = CostEventService(mock_session)
        with pytest.raises(ValidationException, match="Invalid cost type"):
            await svc.create("t1", "E001", cost_type="invalid_type", amount=100.0)

    @pytest.mark.asyncio
    async def test_create_negative_amount(self):
        mock_session = _make_session()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        svc = CostEventService(mock_session)
        with pytest.raises(ValidationException, match="negative"):
            await svc.create("t1", "E001", cost_type="product_cost", amount=-50.0)

    @pytest.mark.asyncio
    async def test_create_zero_exchange_rate(self):
        mock_session = _make_session()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        svc = CostEventService(mock_session)
        with pytest.raises(ValidationException, match="Exchange rate"):
            await svc.create("t1", "E001", cost_type="product_cost", amount=100.0,
                             currency="USD", exchange_rate=0.0)

    @pytest.mark.asyncio
    async def test_create_cny_no_conversion(self):
        mock_session = _make_session()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        svc = CostEventService(mock_session)
        event = await svc.create("t1", "E001", cost_type="product_cost", amount=100.0,
                                 currency="CNY", exchange_rate=7.0)
        assert event.amount_cny == 100.0

    @pytest.mark.asyncio
    async def test_create_foreign_currency_conversion(self):
        mock_session = _make_session()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        svc = CostEventService(mock_session)
        event = await svc.create("t1", "E001", cost_type="product_cost", amount=100.0,
                                 currency="USD", exchange_rate=7.2)
        assert event.amount_cny == 720.0


class TestPaymentStatusValidation:
    @pytest.mark.asyncio
    async def test_update_status_invalid_transition(self):
        mock_session = _make_session()
        payment = PaymentRecord(id="p1", tenant_id="t1", payment_no="PAY001",
                                payment_type="outgoing", amount=100.0, status="pending")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=payment))
        )
        svc = PaymentRecordService(mock_session)
        with pytest.raises(ValidationException, match="Cannot transition"):
            await svc.update_status("p1", "t1", "completed")


class TestProfitCalculation:
    @pytest.mark.asyncio
    async def test_calculate_sku_profit_empty(self):
        mock_session = _make_session()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(all=MagicMock(return_value=[]))
        )
        svc = ProfitCalculationService(mock_session)
        result = await svc.calculate_sku_profit("t1", "sku1")
        assert result["total_cost"] == 0
        assert result["cost_breakdown"] == {}

    @pytest.mark.asyncio
    async def test_calculate_sku_profit_with_costs(self):
        mock_session = _make_session()
        rows = [
            ("product_cost", 50.0),
            ("shipping_cost", 10.0),
            ("platform_fee", 5.0),
        ]
        mock_session.execute = AsyncMock(
            return_value=MagicMock(all=MagicMock(return_value=rows))
        )
        svc = ProfitCalculationService(mock_session)
        result = await svc.calculate_sku_profit("t1", "sku1")
        assert result["total_cost"] == 65.0
        assert result["product_cost"] == 50.0
        assert result["other_costs"] == 15.0
