from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from erp.modules.wms.application.dtos import LocationCreateRequest
from erp.modules.wms.application.services import InventoryService, LocationService
from erp.modules.wms.domain.models import Inventory, Warehouse
from erp.modules.wms.interfaces.deps import get_inventory_alert_service
from erp.shared.exceptions import ValidationException


def _make_session():
    mock = AsyncMock()
    mock.add = MagicMock()
    mock.flush = AsyncMock()
    return mock


class TestLocationValidation:
    @pytest.mark.asyncio
    async def test_create_location_invalid_type(self):
        mock_session = _make_session()
        wh = Warehouse(id="wh1", tenant_id="t1", name="Test", code="WH001")
        mock_session.get = AsyncMock(return_value=wh)
        svc = LocationService(mock_session)
        with pytest.raises(ValidationException, match="Invalid location type"):
            await svc.create("t1", "wh1", "LOC001", location_type="invalid_type")

    @pytest.mark.asyncio
    async def test_create_location_valid_type(self):
        mock_session = _make_session()
        wh = Warehouse(id="wh1", tenant_id="t1", name="Test", code="WH001")
        mock_session.get = AsyncMock(return_value=wh)
        svc = LocationService(mock_session)
        result = await svc.create("t1", "wh1", "LOC001", location_type="picking")
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_location_warehouse_not_found(self):
        mock_session = _make_session()
        mock_session.get = AsyncMock(return_value=None)
        svc = LocationService(mock_session)
        with pytest.raises(Exception, match="not found"):
            await svc.create("t1", "wh1", "LOC001")


class TestInventoryAdjustment:
    @pytest.mark.asyncio
    async def test_adjust_stock_zero_change(self):
        mock_session = _make_session()
        svc = InventoryService(mock_session)
        with pytest.raises(ValidationException, match="cannot be zero"):
            await svc.adjust_stock("t1", "wh1", "sku1", qty_change=0, movement_type="adjust")

    @pytest.mark.asyncio
    async def test_adjust_stock_insufficient_stock(self):
        mock_session = _make_session()
        inv = Inventory(
            id="inv1", tenant_id="t1", warehouse_id="wh1", sku_id="sku1",
            qty_on_hand=5, qty_reserved=0, qty_available=5, safety_qty=10,
        )
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=inv))
        )
        svc = InventoryService(mock_session)
        with pytest.raises(ValidationException, match="Insufficient stock"):
            await svc.adjust_stock("t1", "wh1", "sku1", qty_change=-10, movement_type="outbound")

    @pytest.mark.asyncio
    async def test_adjust_stock_reserved_exceeds_available(self):
        mock_session = _make_session()
        inv = Inventory(
            id="inv1", tenant_id="t1", warehouse_id="wh1", sku_id="sku1",
            qty_on_hand=10, qty_reserved=8, qty_available=2, safety_qty=5,
        )
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=inv))
        )
        svc = InventoryService(mock_session)
        with pytest.raises(ValidationException, match="Insufficient available stock"):
            await svc.adjust_stock("t1", "wh1", "sku1", qty_change=-5, movement_type="outbound")


class TestLowStockCheck:
    @pytest.mark.asyncio
    async def test_check_low_stock_returns_shortage(self):
        mock_session = _make_session()
        inv = Inventory(
            id="inv1", tenant_id="t1", warehouse_id="wh1", sku_id="sku1",
            qty_on_hand=3, qty_reserved=0, qty_available=3, safety_qty=10,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [inv]
        mock_session.execute = AsyncMock(return_value=mock_result)
        svc = InventoryService(mock_session)
        result = await svc.check_low_stock("t1")
        assert len(result) == 1
        assert result[0]["shortage"] == 7
        assert result[0]["sku_id"] == "sku1"


class TestInventoryQuery:
    @pytest.mark.asyncio
    async def test_query_stock_by_sku_without_inventory_repo_uses_session_lookup(self):
        mock_session = _make_session()
        inv = Inventory(
            id="inv1", tenant_id="t1", warehouse_id="wh1", sku_id="sku1",
            qty_on_hand=8, qty_reserved=3, qty_available=5, safety_qty=2,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [inv]
        mock_session.execute = AsyncMock(return_value=mock_result)
        svc = InventoryService(mock_session)

        items, total = await svc.query_stock("t1", sku_id="sku1", page=1, page_size=20)

        assert total == 1
        assert len(items) == 1
        assert items[0].sku_id == "sku1"


class TestWmsRouterContracts:
    @pytest.mark.asyncio
    async def test_resolve_alert_accepts_request_body_contract(self, app, tenant_headers):
        alert = SimpleNamespace(id="alert-1", status="resolved")
        service = SimpleNamespace(resolve_alert=AsyncMock(return_value=alert))
        app.dependency_overrides[get_inventory_alert_service] = lambda: service
        transport = ASGITransport(app=app)

        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/wms/v1/alerts/alert-1/resolve",
                    headers=tenant_headers,
                    json={"resolution_note": "fixed shortage"},
                )
        finally:
            app.dependency_overrides.pop(get_inventory_alert_service, None)

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 0
        assert body["data"] == {"id": "alert-1", "status": "resolved"}
        service.resolve_alert.assert_awaited_once()
        call_args = service.resolve_alert.call_args
        assert call_args[0][0] == "alert-1"
        assert call_args[0][1] == tenant_headers["X-Tenant-ID"]


class TestLocationRequestContract:
    def test_location_create_request_accepts_all_service_supported_location_types(self):
        req = LocationCreateRequest(
            warehouse_id="wh1",
            code="LOC-001",
            location_type="returns",
        )

        assert req.location_type == "returns"
