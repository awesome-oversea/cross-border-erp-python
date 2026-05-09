from __future__ import annotations

import pytest

from erp.connectors import (
    CONNECTOR_REGISTRY,
    Alibaba1688Connector,
    AlibabaGlobalConnector,
    AlipayConnector,
    AmazonConnector,
    DHLConnector,
    EuVatConnector,
    FBAConnector,
    FedExConnector,
    FourPXConnector,
    PayPalConnector,
    ShipBobConnector,
    ShopifyConnector,
    StripeConnector,
    TikTokShopConnector,
    UPSConnector,
    UsTaxConnector,
    YanwenConnector,
    get_connector,
    list_connectors,
)
from erp.connectors.base import (
    ConnectorConfig,
    ConnectorStatus,
    InventorySyncItem,
    ListingFetchParams,
    ListingUpdateData,
    OrderFetchParams,
    PaymentCreate,
    PaymentRefund,
    RateEstimateParams,
    ShipmentCreate,
    WarehouseInventoryQuery,
    WarehouseReceipt,
)


class TestConnectorRegistry:
    def test_registry_has_all_connectors(self):
        assert len(CONNECTOR_REGISTRY) == 17

    def test_get_connector(self):
        connector = get_connector("amazon")
        assert connector.connector_name == "Amazon"
        assert connector.connector_type == "platform"

    def test_get_connector_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown connector"):
            get_connector("nonexistent")

    def test_list_connectors(self):
        connectors = list_connectors()
        assert len(connectors) == 17
        ids = [c["connector_id"] for c in connectors]
        assert "amazon" in ids
        assert "dhl" in ids
        assert "paypal" in ids

    def test_get_connector_with_config(self):
        config = ConnectorConfig(
            connector_id="amazon",
            connector_name="Amazon",
            connector_type="platform",
            store_id="STORE-001",
        )
        connector = get_connector("amazon", config)
        assert connector.config.store_id == "STORE-001"


class TestAmazonConnector:
    def setup_method(self):
        self.connector = AmazonConnector()

    @pytest.mark.asyncio
    async def test_fetch_orders(self):
        orders, _next_token = await self.connector.fetch_orders(OrderFetchParams(status="Unshipped"))
        assert len(orders) >= 1
        assert orders[0].platform == "amazon"
        assert orders[0].status == "Unshipped"
        assert len(orders[0].items) >= 1

    @pytest.mark.asyncio
    async def test_sync_inventory_success(self):
        items = [
            InventorySyncItem(sku="SKU-001", quantity=10),
            InventorySyncItem(sku="SKU-002", quantity=20),
        ]
        result = await self.connector.sync_inventory(items)
        assert result.success
        assert result.synced_count == 2
        assert result.failed_count == 0

    @pytest.mark.asyncio
    async def test_sync_inventory_failure(self):
        items = [
            InventorySyncItem(sku="SKU-001", quantity=10),
            InventorySyncItem(sku="", quantity=-1),
        ]
        result = await self.connector.sync_inventory(items)
        assert not result.success
        assert result.failed_count == 1

    @pytest.mark.asyncio
    async def test_update_listing(self):
        result = await self.connector.update_listing("LIST-001", ListingUpdateData(price=29.99))
        assert result.success
        assert result.listing_id == "LIST-001"

    @pytest.mark.asyncio
    async def test_update_listing_no_id(self):
        result = await self.connector.update_listing("", ListingUpdateData())
        assert not result.success

    @pytest.mark.asyncio
    async def test_fetch_listings(self):
        listings, _ = await self.connector.fetch_listings(ListingFetchParams())
        assert len(listings) >= 1
        assert listings[0].platform == "amazon"

    @pytest.mark.asyncio
    async def test_health_check(self):
        assert await self.connector.health_check()

    def test_connector_type(self):
        assert self.connector.connector_type == "platform"

    def test_status_management(self):
        assert self.connector.status == ConnectorStatus.ACTIVE
        self.connector.mark_error()
        assert self.connector.status == ConnectorStatus.ERROR
        self.connector.mark_active()
        assert self.connector.status == ConnectorStatus.ACTIVE
        self.connector.mark_rate_limited()
        assert self.connector.status == ConnectorStatus.RATE_LIMITED


class TestShopifyConnector:
    def setup_method(self):
        self.connector = ShopifyConnector()

    @pytest.mark.asyncio
    async def test_fetch_orders(self):
        orders, _ = await self.connector.fetch_orders(OrderFetchParams())
        assert len(orders) >= 1
        assert orders[0].platform == "shopify"

    @pytest.mark.asyncio
    async def test_sync_inventory(self):
        result = await self.connector.sync_inventory([InventorySyncItem(sku="SKU-001", quantity=10)])
        assert result.success

    @pytest.mark.asyncio
    async def test_fetch_listings(self):
        listings, _ = await self.connector.fetch_listings(ListingFetchParams())
        assert len(listings) >= 1


class TestTikTokShopConnector:
    def setup_method(self):
        self.connector = TikTokShopConnector()

    @pytest.mark.asyncio
    async def test_fetch_orders(self):
        orders, _ = await self.connector.fetch_orders(OrderFetchParams())
        assert len(orders) >= 1
        assert orders[0].platform == "tiktok_shop"

    @pytest.mark.asyncio
    async def test_fetch_listings(self):
        listings, _ = await self.connector.fetch_listings(ListingFetchParams())
        assert len(listings) >= 1


class TestYanwenConnector:
    def setup_method(self):
        self.connector = YanwenConnector()

    @pytest.mark.asyncio
    async def test_estimate_rate(self):
        rates = await self.connector.estimate_rate(RateEstimateParams(
            origin_country="CN", destination_country="US", weight_kg=1.0,
        ))
        assert len(rates) == 3
        assert rates[0].carrier == "yanwen"
        assert rates[0].cost > 0

    @pytest.mark.asyncio
    async def test_estimate_rate_germany(self):
        rates = await self.connector.estimate_rate(RateEstimateParams(
            origin_country="CN", destination_country="DE", weight_kg=2.0,
        ))
        assert len(rates) == 3
        assert rates[0].currency == "CNY"

    @pytest.mark.asyncio
    async def test_create_shipment(self):
        result = await self.connector.create_shipment(ShipmentCreate(
            order_id="ORD-001", carrier_code="yanwen", service_code="YANWEN_STANDARD",
        ))
        assert result.success
        assert result.tracking_number.startswith("YW")
        assert result.label_url != ""

    @pytest.mark.asyncio
    async def test_get_tracking(self):
        info = await self.connector.get_tracking("YW123456789")
        assert info.tracking_number == "YW123456789"
        assert info.carrier == "yanwen"
        assert len(info.events) >= 1

    @pytest.mark.asyncio
    async def test_cancel_shipment(self):
        assert await self.connector.cancel_shipment("YW123456789")


class TestDHLConnector:
    def setup_method(self):
        self.connector = DHLConnector()

    @pytest.mark.asyncio
    async def test_estimate_rate(self):
        rates = await self.connector.estimate_rate(RateEstimateParams(
            origin_country="CN", destination_country="US", weight_kg=1.0,
        ))
        assert len(rates) == 2
        assert rates[0].currency == "USD"

    @pytest.mark.asyncio
    async def test_create_shipment(self):
        result = await self.connector.create_shipment(ShipmentCreate())
        assert result.success
        assert result.tracking_number.startswith("DHL")


class TestFedExConnector:
    def setup_method(self):
        self.connector = FedExConnector()

    @pytest.mark.asyncio
    async def test_estimate_rate(self):
        rates = await self.connector.estimate_rate(RateEstimateParams(weight_kg=1.0))
        assert len(rates) == 2
        assert rates[0].carrier == "fedex"

    @pytest.mark.asyncio
    async def test_create_shipment(self):
        result = await self.connector.create_shipment(ShipmentCreate())
        assert result.success
        assert result.tracking_number.startswith("FX")


class TestUPSConnector:
    def setup_method(self):
        self.connector = UPSConnector()

    @pytest.mark.asyncio
    async def test_estimate_rate(self):
        rates = await self.connector.estimate_rate(RateEstimateParams(weight_kg=1.0))
        assert len(rates) == 2
        assert rates[0].carrier == "ups"

    @pytest.mark.asyncio
    async def test_create_shipment(self):
        result = await self.connector.create_shipment(ShipmentCreate())
        assert result.success
        assert result.tracking_number.startswith("1Z")


class TestFourPXConnector:
    def setup_method(self):
        self.connector = FourPXConnector()

    @pytest.mark.asyncio
    async def test_estimate_rate(self):
        rates = await self.connector.estimate_rate(RateEstimateParams(weight_kg=1.0))
        assert len(rates) == 2
        assert rates[0].carrier == "4px"

    @pytest.mark.asyncio
    async def test_create_shipment(self):
        result = await self.connector.create_shipment(ShipmentCreate())
        assert result.success
        assert result.tracking_number.startswith("4PX")


class TestPayPalConnector:
    def setup_method(self):
        self.connector = PayPalConnector()

    @pytest.mark.asyncio
    async def test_create_payment(self):
        result = await self.connector.create_payment(PaymentCreate(
            order_id="ORD-001", amount=99.99, currency="USD",
        ))
        assert result.success
        assert result.payment_id.startswith("PAYPAL-")
        assert result.redirect_url != ""

    @pytest.mark.asyncio
    async def test_query_payment(self):
        result = await self.connector.query_payment("PAYPAL-123")
        assert result.success
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_query_payment_empty_id(self):
        result = await self.connector.query_payment("")
        assert not result.success

    @pytest.mark.asyncio
    async def test_refund(self):
        result = await self.connector.refund(PaymentRefund(
            payment_id="PAYPAL-123", refund_amount=50.0, currency="USD",
        ))
        assert result.success
        assert result.refund_id.startswith("REFUND-")

    @pytest.mark.asyncio
    async def test_refund_no_payment_id(self):
        result = await self.connector.refund(PaymentRefund(
            payment_id="", refund_amount=50.0,
        ))
        assert not result.success

    @pytest.mark.asyncio
    async def test_refund_negative_amount(self):
        result = await self.connector.refund(PaymentRefund(
            payment_id="PAYPAL-123", refund_amount=-10.0,
        ))
        assert not result.success

    @pytest.mark.asyncio
    async def test_get_balance(self):
        balance = await self.connector.get_balance("USD")
        assert "available_balance" in balance


class TestStripeConnector:
    def setup_method(self):
        self.connector = StripeConnector()

    @pytest.mark.asyncio
    async def test_create_payment(self):
        result = await self.connector.create_payment(PaymentCreate(amount=50.0))
        assert result.success
        assert result.payment_id.startswith("pi_")

    @pytest.mark.asyncio
    async def test_refund(self):
        result = await self.connector.refund(PaymentRefund(
            payment_id="pi_123", refund_amount=25.0,
        ))
        assert result.success
        assert result.refund_id.startswith("re_")


class TestAlipayConnector:
    def setup_method(self):
        self.connector = AlipayConnector()

    @pytest.mark.asyncio
    async def test_create_payment(self):
        result = await self.connector.create_payment(PaymentCreate(amount=100.0, currency="CNY"))
        assert result.success
        assert result.payment_id.startswith("ALI-")
        assert result.status == "WAIT_BUYER_PAY"

    @pytest.mark.asyncio
    async def test_query_payment(self):
        result = await self.connector.query_payment("ALI-123")
        assert result.success
        assert result.status == "TRADE_SUCCESS"

    @pytest.mark.asyncio
    async def test_get_balance(self):
        balance = await self.connector.get_balance("CNY")
        assert "available_amount" in balance


class TestFBAConnector:
    def setup_method(self):
        self.connector = FBAConnector()

    @pytest.mark.asyncio
    async def test_create_receipt(self):
        result = await self.connector.create_receipt(WarehouseReceipt(
            warehouse_id="FBA-US-EAST",
        ))
        assert result.success
        assert result.receipt_id.startswith("FBA-RECV-")

    @pytest.mark.asyncio
    async def test_create_receipt_no_warehouse(self):
        result = await self.connector.create_receipt(WarehouseReceipt())
        assert not result.success

    @pytest.mark.asyncio
    async def test_query_inventory(self):
        items = await self.connector.query_inventory(WarehouseInventoryQuery(
            warehouse_id="FBA-US-EAST", sku="SKU-001",
        ))
        assert len(items) >= 1
        assert items[0].quantity_on_hand > 0

    @pytest.mark.asyncio
    async def test_create_outbound(self):
        result = await self.connector.create_outbound("ORD-001", [{"sku": "SKU-001", "quantity": 1}])
        assert result["success"]
        assert "shipment_id" in result

    @pytest.mark.asyncio
    async def test_create_outbound_no_order(self):
        result = await self.connector.create_outbound("", [])
        assert not result["success"]


class TestShipBobConnector:
    def setup_method(self):
        self.connector = ShipBobConnector()

    @pytest.mark.asyncio
    async def test_create_receipt(self):
        result = await self.connector.create_receipt(WarehouseReceipt(warehouse_id="SB-US-01"))
        assert result.success
        assert result.receipt_id.startswith("SB-RECV-")

    @pytest.mark.asyncio
    async def test_query_inventory(self):
        items = await self.connector.query_inventory(WarehouseInventoryQuery(sku="SKU-001"))
        assert len(items) >= 1


class TestAlibaba1688Connector:
    def setup_method(self):
        self.connector = Alibaba1688Connector()

    @pytest.mark.asyncio
    async def test_search_products(self):
        result = await self.connector.search_products("手机壳", page_size=3)
        assert result["total"] > 0
        assert len(result["items"]) > 0
        assert result["items"][0]["currency"] == "CNY"

    @pytest.mark.asyncio
    async def test_search_products_empty_keyword(self):
        result = await self.connector.search_products("")
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_get_product_detail(self):
        result = await self.connector.get_product_detail("1688-PROD-001")
        assert result["success"]
        assert "specifications" in result

    @pytest.mark.asyncio
    async def test_get_product_detail_no_id(self):
        result = await self.connector.get_product_detail("")
        assert not result["success"]

    @pytest.mark.asyncio
    async def test_place_order(self):
        result = await self.connector.place_order(
            [{"sku": "SKU-001", "quantity": 10, "unit_price": 25.0}],
            {"city": "Shenzhen"},
        )
        assert result["success"]
        assert result["currency"] == "CNY"

    @pytest.mark.asyncio
    async def test_place_order_no_items(self):
        result = await self.connector.place_order([], {})
        assert not result["success"]


class TestAlibabaGlobalConnector:
    def setup_method(self):
        self.connector = AlibabaGlobalConnector()

    @pytest.mark.asyncio
    async def test_search_products(self):
        result = await self.connector.search_products("phone case")
        assert result["total"] > 0
        assert result["items"][0]["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_place_order(self):
        result = await self.connector.place_order(
            [{"sku": "SKU-001", "quantity": 50, "unit_price": 45.0}],
            {"city": "Los Angeles"},
        )
        assert result["success"]
        assert result["currency"] == "USD"


class TestEuVatConnector:
    def setup_method(self):
        self.connector = EuVatConnector()

    @pytest.mark.asyncio
    async def test_calculate_tax_germany(self):
        result = await self.connector.calculate_tax(100.0, "DE")
        assert result["success"]
        assert result["tax_rate"] == 0.19
        assert result["tax_amount"] == 19.0
        assert result["total_amount"] == 119.0

    @pytest.mark.asyncio
    async def test_calculate_tax_france(self):
        result = await self.connector.calculate_tax(100.0, "FR")
        assert result["success"]
        assert result["tax_rate"] == 0.20
        assert result["tax_amount"] == 20.0

    @pytest.mark.asyncio
    async def test_calculate_tax_unknown_country(self):
        result = await self.connector.calculate_tax(100.0, "XX")
        assert result["success"]
        assert result["tax_rate"] == 0.0
        assert result["tax_amount"] == 0.0

    @pytest.mark.asyncio
    async def test_validate_vat_valid(self):
        result = await self.connector.validate_vat("DE123456789", "DE")
        assert result["success"]
        assert result["is_valid"]

    @pytest.mark.asyncio
    async def test_validate_vat_invalid(self):
        result = await self.connector.validate_vat("INVALID", "DE")
        assert result["success"]
        assert not result["is_valid"]


class TestUsTaxConnector:
    def setup_method(self):
        self.connector = UsTaxConnector()

    @pytest.mark.asyncio
    async def test_calculate_tax_california(self):
        result = await self.connector.calculate_tax(100.0, "US", "CA")
        assert result["success"]
        assert result["tax_rate"] == 0.0825
        assert result["tax_amount"] == 8.25

    @pytest.mark.asyncio
    async def test_calculate_tax_new_york(self):
        result = await self.connector.calculate_tax(100.0, "US", "NY")
        assert result["success"]
        assert result["tax_rate"] == 0.08

    @pytest.mark.asyncio
    async def test_calculate_tax_non_us(self):
        result = await self.connector.calculate_tax(100.0, "DE")
        assert not result["success"]

    @pytest.mark.asyncio
    async def test_validate_vat(self):
        result = await self.connector.validate_vat("12345", "US")
        assert result["success"]
        assert not result["is_valid"]
