from __future__ import annotations

import pytest

from erp.modules.sys.domain.connector_mock_implementations import (
    AmazonSPMockConnector,
    FedExMockConnector,
    ShopeeMockConnector,
    ShopifyMockConnector,
    StripeMockConnector,
    TikTokShopMockConnector,
    YanwenMockConnector,
)
from erp.modules.sys.domain.connector_spi_models import (
    ConnectorAuthConfig,
    ConnectorRegistry,
)


@pytest.fixture
def auth_config():
    return ConnectorAuthConfig(
        auth_type="oauth2",
        client_id="mock-client-id",
        client_secret="mock-client-secret",
    )


class TestAmazonSPMockConnector:
    @pytest.fixture
    def connector(self, auth_config):
        return AmazonSPMockConnector("conn-1", "tenant-1", auth_config)

    @pytest.mark.asyncio
    async def test_authenticate(self, connector, auth_config):
        result = await connector.authenticate(auth_config)
        assert result.access_token.startswith("mock-amz-token-")
        assert result.token_expiry != ""

    @pytest.mark.asyncio
    async def test_health_check(self, connector):
        assert await connector.health_check() is True

    @pytest.mark.asyncio
    async def test_fetch_orders(self, connector):
        result = await connector.fetch_orders()
        assert result.success is True
        assert "orders" in result.data
        assert result.data["total"] > 0

    @pytest.mark.asyncio
    async def test_fetch_orders_with_time_filter(self, connector):
        result = await connector.fetch_orders(start_time="2020-01-01")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_fetch_listings(self, connector):
        result = await connector.fetch_listings()
        assert result.success is True
        assert "listings" in result.data

    @pytest.mark.asyncio
    async def test_fetch_listings_with_status(self, connector):
        result = await connector.fetch_listings(status="ACTIVE")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_update_listing(self, connector):
        result = await connector.update_listing("MOCK-SKU-0000", {"quantity": 50})
        assert result.success is True
        assert result.data["updated"] is True

    @pytest.mark.asyncio
    async def test_acknowledge_order(self, connector):
        result = await connector.acknowledge_order("111-0000001-1234")
        assert result.success is True
        assert result.data["acknowledged"] is True

    @pytest.mark.asyncio
    async def test_ship_order(self, connector):
        result = await connector.ship_order("111-0000001-1234", "1Z999AA10123456784", "UPS")
        assert result.success is True
        assert result.data["tracking_number"] == "1Z999AA10123456784"

    @pytest.mark.asyncio
    async def test_get_order_detail(self, connector):
        orders = AmazonSPMockConnector.MOCK_ORDERS
        if orders:
            result = await connector.get_order_detail(orders[0]["amazon_order_id"])
            assert result.success is True
            assert result.data["amazon_order_id"] == orders[0]["amazon_order_id"]

    @pytest.mark.asyncio
    async def test_get_inventory_summary(self, connector):
        result = await connector.get_inventory_summary()
        assert result.success is True
        assert "inventory_summaries" in result.data

    @pytest.mark.asyncio
    async def test_refresh_token(self, connector):
        result = await connector.refresh_token()
        assert "mock-amz-token-refresh-" in result.access_token


class TestShopifyMockConnector:
    @pytest.fixture
    def connector(self, auth_config):
        return ShopifyMockConnector("conn-2", "tenant-1", auth_config)

    @pytest.mark.asyncio
    async def test_authenticate(self, connector, auth_config):
        result = await connector.authenticate(auth_config)
        assert result.access_token.startswith("mock-shopify-token-")

    @pytest.mark.asyncio
    async def test_health_check(self, connector):
        assert await connector.health_check() is True

    @pytest.mark.asyncio
    async def test_fetch_orders(self, connector):
        result = await connector.fetch_orders()
        assert result.success is True
        assert "orders" in result.data

    @pytest.mark.asyncio
    async def test_fetch_listings(self, connector):
        result = await connector.fetch_listings()
        assert result.success is True
        assert "products" in result.data

    @pytest.mark.asyncio
    async def test_ship_order(self, connector):
        result = await connector.ship_order("12345", "TRACK123", "USPS")
        assert result.success is True


class TestShopeeMockConnector:
    @pytest.fixture
    def connector(self, auth_config):
        return ShopeeMockConnector("conn-3", "tenant-1", auth_config)

    @pytest.mark.asyncio
    async def test_authenticate(self, connector, auth_config):
        result = await connector.authenticate(auth_config)
        assert result.access_token.startswith("mock-shopee-token-")

    @pytest.mark.asyncio
    async def test_fetch_orders(self, connector):
        result = await connector.fetch_orders()
        assert result.success is True
        assert "orders" in result.data


class TestTikTokShopMockConnector:
    @pytest.fixture
    def connector(self, auth_config):
        return TikTokShopMockConnector("conn-4", "tenant-1", auth_config)

    @pytest.mark.asyncio
    async def test_authenticate(self, connector, auth_config):
        result = await connector.authenticate(auth_config)
        assert result.access_token.startswith("mock-tiktok-token-")

    @pytest.mark.asyncio
    async def test_fetch_orders(self, connector):
        result = await connector.fetch_orders()
        assert result.success is True


class TestFedExMockConnector:
    @pytest.fixture
    def connector(self, auth_config):
        return FedExMockConnector("conn-5", "tenant-1", auth_config)

    @pytest.mark.asyncio
    async def test_health_check(self, connector):
        assert await connector.health_check() is True

    @pytest.mark.asyncio
    async def test_create_shipment(self, connector):
        result = await connector.create_shipment({"origin": "US", "destination": "CN"})
        assert result.success is True
        assert "tracking_number" in result.data
        assert "label_url" in result.data

    @pytest.mark.asyncio
    async def test_get_tracking(self, connector):
        result = await connector.get_tracking("748999999999")
        assert result.success is True
        assert "status" in result.data
        assert "events" in result.data

    @pytest.mark.asyncio
    async def test_estimate_shipping_cost(self, connector):
        result = await connector.estimate_shipping_cost({"weight_kg": 2.5, "destination_country": "US"})
        assert result.success is True
        assert "cost" in result.data
        assert result.data["cost"] > 0


class TestYanwenMockConnector:
    @pytest.fixture
    def connector(self, auth_config):
        return YanwenMockConnector("conn-6", "tenant-1", auth_config)

    @pytest.mark.asyncio
    async def test_create_shipment(self, connector):
        result = await connector.create_shipment({"origin": "CN", "destination": "US"})
        assert result.success is True
        assert "tracking_number" in result.data

    @pytest.mark.asyncio
    async def test_estimate_shipping_cost(self, connector):
        result = await connector.estimate_shipping_cost({"weight_kg": 1, "destination_country": "US"})
        assert result.success is True
        assert result.data["cost"] > 0


class TestStripeMockConnector:
    @pytest.fixture
    def connector(self, auth_config):
        return StripeMockConnector("conn-7", "tenant-1", auth_config)

    @pytest.mark.asyncio
    async def test_get_balance(self, connector):
        result = await connector.get_balance()
        assert result.success is True
        assert "balance" in result.data
        assert result.data["balance"] > 0

    @pytest.mark.asyncio
    async def test_get_transactions(self, connector):
        result = await connector.get_transactions()
        assert result.success is True
        assert "transactions" in result.data

    @pytest.mark.asyncio
    async def test_initiate_payout(self, connector):
        result = await connector.initiate_payout(100.0, "USD")
        assert result.success is True
        assert "payout_id" in result.data
        assert result.data["status"] == "pending"


class TestConnectorRegistry:
    def test_registry_has_all_mock_connectors(self):
        expected_types = ["amazon_sp", "shopify", "shopee", "tiktok_shop",
                          "fedex", "yanwen", "stripe"]
        for t in expected_types:
            assert ConnectorRegistry.get(t) is not None, f"Connector type '{t}' not registered"

    def test_list_types_includes_mocks(self):
        types = ConnectorRegistry.list_types()
        assert "amazon_sp" in types
        assert "shopify" in types
        assert "fedex" in types
        assert "stripe" in types

    @pytest.mark.asyncio
    async def test_instantiate_via_registry(self, auth_config):
        cls = ConnectorRegistry.get("amazon_sp")
        instance = cls("test-conn", "test-tenant", auth_config)
        assert isinstance(instance, AmazonSPMockConnector)
        assert await instance.health_check() is True
