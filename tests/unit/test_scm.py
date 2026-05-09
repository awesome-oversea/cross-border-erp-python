from unittest.mock import AsyncMock, MagicMock

import pytest

from erp.modules.scm.application.services import (
    PO_STATUS_TRANSITIONS,
    PurchaseOrderService,
    SupplierService,
)
from erp.modules.scm.domain.models import PurchaseOrder, Supplier
from erp.shared.exceptions import ValidationException


class TestPOStatusTransitions:
    def test_draft_can_go_to_pending_approval(self):
        assert "pending_approval" in PO_STATUS_TRANSITIONS["draft"]

    def test_approved_can_go_to_ordered(self):
        assert "ordered" in PO_STATUS_TRANSITIONS["approved"]

    def test_ordered_can_go_to_partial_received(self):
        assert "partial_received" in PO_STATUS_TRANSITIONS["ordered"]

    def test_completed_is_terminal(self):
        assert PO_STATUS_TRANSITIONS["completed"] == []

    def test_cancelled_is_terminal(self):
        assert PO_STATUS_TRANSITIONS["cancelled"] == []

    def test_rejected_is_terminal(self):
        assert PO_STATUS_TRANSITIONS["rejected"] == []


class TestSupplierRating:
    def test_calculate_overall_rating(self):
        result = SupplierService.calculate_overall_rating(
            quality_score=90, delivery_score=80, price_score=85, service_score=75
        )
        expected = round(
            90 * 0.4 + 80 * 0.3 + 85 * 0.2 + 75 * 0.1, 2
        )
        assert result == expected

    def test_suggest_cooperation_level_strategic(self):
        assert SupplierService.suggest_cooperation_level(95) == "strategic"

    def test_suggest_cooperation_level_normal(self):
        assert SupplierService.suggest_cooperation_level(75) == "normal"

    def test_suggest_cooperation_level_trial(self):
        assert SupplierService.suggest_cooperation_level(50) == "trial"

    def test_suggest_cooperation_level_boundary_90(self):
        assert SupplierService.suggest_cooperation_level(90) == "strategic"

    def test_suggest_cooperation_level_boundary_70(self):
        assert SupplierService.suggest_cooperation_level(70) == "normal"

    def test_suggest_cooperation_level_below_70(self):
        assert SupplierService.suggest_cooperation_level(69) == "trial"


class TestSupplierCooperationLevel:
    @pytest.mark.asyncio
    async def test_update_cooperation_level_invalid(self):
        mock_session = AsyncMock()
        supplier = Supplier(id="sup1", tenant_id="t1", name="Test", code="SUP001")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=supplier))
        )
        svc = SupplierService(mock_session)
        with pytest.raises(ValidationException, match="Invalid cooperation level"):
            await svc.update_cooperation_level("sup1", "t1", "premium")


class TestPOValidation:
    @pytest.mark.asyncio
    async def test_create_po_inactive_supplier(self):
        mock_session = AsyncMock()
        supplier = Supplier(id="sup1", tenant_id="t1", name="Test", code="SUP001", status="inactive")
        mock_session.get = AsyncMock(return_value=supplier)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        svc = PurchaseOrderService(mock_session)
        with pytest.raises(ValidationException, match="inactive supplier"):
            await svc.create("t1", "PO001", "sup1", "wh1")

    @pytest.mark.asyncio
    async def test_add_item_negative_quantity(self):
        mock_session = AsyncMock()
        po = PurchaseOrder(id="po1", tenant_id="t1", po_no="PO001",
                           supplier_id="sup1", warehouse_id="wh1", status="draft", total_amount=0)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=po))
        )
        svc = PurchaseOrderService(mock_session)
        with pytest.raises(ValidationException, match="positive"):
            await svc.add_item("t1", "po1", "sku1", quantity=-5, unit_price=10.0)

    @pytest.mark.asyncio
    async def test_add_item_negative_price(self):
        mock_session = AsyncMock()
        po = PurchaseOrder(id="po1", tenant_id="t1", po_no="PO001",
                           supplier_id="sup1", warehouse_id="wh1", status="draft", total_amount=0)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=po))
        )
        svc = PurchaseOrderService(mock_session)
        with pytest.raises(ValidationException, match="negative"):
            await svc.add_item("t1", "po1", "sku1", quantity=5, unit_price=-10.0)

    @pytest.mark.asyncio
    async def test_add_item_to_approved_po_fails(self):
        mock_session = AsyncMock()
        po = PurchaseOrder(id="po1", tenant_id="t1", po_no="PO001",
                           supplier_id="sup1", warehouse_id="wh1", status="approved", total_amount=0)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=po))
        )
        svc = PurchaseOrderService(mock_session)
        with pytest.raises(ValidationException, match="Cannot add items"):
            await svc.add_item("t1", "po1", "sku1", quantity=5, unit_price=10.0)
