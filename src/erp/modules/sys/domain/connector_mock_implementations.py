from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta

from erp.modules.sys.domain.connector_spi_models import (
    BaseConnector,
    ConnectorAuthConfig,
    ConnectorCallResult,
    ConnectorRegistry,
)
from erp.shared.context import trace_id_var


class AmazonSPMockConnector(BaseConnector):
    MOCK_ORDERS: list[dict] = []
    MOCK_LISTINGS: list[dict] = []

    def __init__(self, connector_id: str, tenant_id: str, auth_config: ConnectorAuthConfig,
                 base_url: str = "https://mock-sellingpartnerapi.amazon.com",
                 rate_limit: int = 30, timeout: int = 30):
        super().__init__(connector_id, tenant_id, auth_config, base_url, rate_limit, timeout)
        self._init_mock_data()

    def _init_mock_data(self):
        if not AmazonSPMockConnector.MOCK_ORDERS:
            now = datetime.now(UTC)
            for i in range(20):
                order_date = now - timedelta(days=random.randint(1, 30))
                AmazonSPMockConnector.MOCK_ORDERS.append({
                    "amazon_order_id": f"111-{i:07d}-{random.randint(1000, 9999)}",
                    "order_status": random.choice(["Pending", "Unshipped", "Shipped", "Delivered"]),
                    "purchase_date": order_date.isoformat(),
                    "order_total": {"amount": str(round(random.uniform(10, 500), 2)), "currency_code": "USD"},
                    "number_of_items_shipped": random.randint(0, 3),
                    "number_of_items_unshipped": random.randint(0, 2),
                    "marketplace_id": "ATVPDKIKX0DER",
                    "sales_channel": "Amazon.com",
                    "ship_to_country_code": "US",
                    "order_type": random.choice(["StandardOrder", "Preorder"]),
                    "fulfillment_channel": random.choice(["MFN", "AFN"]),
                    "last_update_date": order_date.isoformat(),
                })
        if not AmazonSPMockConnector.MOCK_LISTINGS:
            for i in range(10):
                AmazonSPMockConnector.MOCK_LISTINGS.append({
                    "sku": f"MOCK-SKU-{i:04d}",
                    "asin": f"B0{random.randint(1000000, 9999999)}",
                    "product_name": f"Mock Product {i + 1}",
                    "price": {"amount": str(round(random.uniform(5, 200), 2)), "currency_code": "USD"},
                    "quantity": random.randint(0, 100),
                    "status": random.choice(["ACTIVE", "INACTIVE"]),
                    "fulfillment_channel": random.choice(["MFN", "AFN"]),
                })

    async def authenticate(self, config: ConnectorAuthConfig) -> ConnectorAuthConfig:
        config.access_token = f"mock-amz-token-{uuid.uuid4().hex[:16]}"
        config.token_expiry = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        self.auth_config = config
        return config

    async def call(self, method: str, path: str, params: dict | None = None,
                   body: dict | None = None, headers: dict | None = None) -> ConnectorCallResult:
        self._call_count += 1
        return ConnectorCallResult(
            success=True,
            data={"message": "Amazon SP-API mock call", "method": method, "path": path},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def health_check(self) -> bool:
        return True

    async def refresh_token(self) -> ConnectorAuthConfig:
        self.auth_config.access_token = f"mock-amz-token-refresh-{uuid.uuid4().hex[:16]}"
        self.auth_config.token_expiry = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        return self.auth_config

    async def fetch_orders(self, start_time: str = "", end_time: str = "",
                           page_size: int = 50) -> ConnectorCallResult:
        orders = AmazonSPMockConnector.MOCK_ORDERS[:page_size]
        if start_time:
            orders = [o for o in orders if o["purchase_date"] >= start_time]
        if end_time:
            orders = [o for o in orders if o["purchase_date"] <= end_time]
        return ConnectorCallResult(
            success=True,
            data={"orders": orders, "total": len(orders), "next_token": ""},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def fetch_listings(self, status: str = "") -> ConnectorCallResult:
        listings = AmazonSPMockConnector.MOCK_LISTINGS
        if status:
            listings = [item for item in listings if item["status"] == status]
        return ConnectorCallResult(
            success=True,
            data={"listings": listings, "total": len(listings)},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def update_listing(self, listing_id: str, data: dict) -> ConnectorCallResult:
        for listing in AmazonSPMockConnector.MOCK_LISTINGS:
            if listing["sku"] == listing_id:
                listing.update(data)
                break
        return ConnectorCallResult(
            success=True,
            data={"listing_id": listing_id, "updated": True},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def acknowledge_order(self, order_id: str) -> ConnectorCallResult:
        return ConnectorCallResult(
            success=True,
            data={"order_id": order_id, "acknowledged": True},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def ship_order(self, order_id: str, tracking_number: str,
                         carrier: str = "") -> ConnectorCallResult:
        for order in AmazonSPMockConnector.MOCK_ORDERS:
            if order["amazon_order_id"] == order_id:
                order["order_status"] = "Shipped"
                order["last_update_date"] = datetime.now(UTC).isoformat()
                break
        return ConnectorCallResult(
            success=True,
            data={"order_id": order_id, "tracking_number": tracking_number, "carrier": carrier},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def get_order_detail(self, order_id: str) -> ConnectorCallResult:
        for order in AmazonSPMockConnector.MOCK_ORDERS:
            if order["amazon_order_id"] == order_id:
                return ConnectorCallResult(
                    success=True, data=order, status_code=200,
                    trace_id=trace_id_var.get(""),
                )
        return ConnectorCallResult(
            success=False, data=None, error=f"Order {order_id} not found",
            status_code=404, trace_id=trace_id_var.get(""),
        )

    async def get_inventory_summary(self) -> ConnectorCallResult:
        summaries = []
        for listing in AmazonSPMockConnector.MOCK_LISTINGS:
            summaries.append({
                "sku": listing["sku"],
                "asin": listing["asin"],
                "total_quantity": listing["quantity"],
                "fulfillable_quantity": max(0, listing["quantity"] - random.randint(0, 5)),
                "reserved_quantity": random.randint(0, 3),
            })
        return ConnectorCallResult(
            success=True, data={"inventory_summaries": summaries},
            status_code=200, trace_id=trace_id_var.get(""),
        )


class ShopifyMockConnector(BaseConnector):
    MOCK_ORDERS: list[dict] = []
    MOCK_PRODUCTS: list[dict] = []

    def __init__(self, connector_id: str, tenant_id: str, auth_config: ConnectorAuthConfig,
                 base_url: str = "https://mock-shop.myshopify.com/admin/api/2024-01",
                 rate_limit: int = 40, timeout: int = 30):
        super().__init__(connector_id, tenant_id, auth_config, base_url, rate_limit, timeout)
        self._init_mock_data()

    def _init_mock_data(self):
        if not ShopifyMockConnector.MOCK_ORDERS:
            now = datetime.now(UTC)
            for i in range(15):
                order_date = now - timedelta(days=random.randint(1, 30))
                ShopifyMockConnector.MOCK_ORDERS.append({
                    "id": random.randint(1000000000, 9999999999),
                    "order_number": 1000 + i,
                    "email": f"customer{i}@example.com",
                    "created_at": order_date.isoformat(),
                    "updated_at": order_date.isoformat(),
                    "total_price": str(round(random.uniform(10, 300), 2)),
                    "currency": "USD",
                    "financial_status": random.choice(["pending", "paid", "refunded"]),
                    "fulfillment_status": random.choice(["fulfilled", "partial", "unfulfilled", None]),
                    "shipping_address": {
                        "country_code": "US",
                        "city": "New York",
                        "zip": "10001",
                    },
                    "line_items": [
                        {"title": f"Product {random.randint(1, 10)}", "quantity": random.randint(1, 3),
                         "price": str(round(random.uniform(5, 100), 2))}
                    ],
                })
        if not ShopifyMockConnector.MOCK_PRODUCTS:
            for i in range(8):
                ShopifyMockConnector.MOCK_PRODUCTS.append({
                    "id": random.randint(1000000000, 9999999999),
                    "title": f"Mock Shopify Product {i + 1}",
                    "handle": f"mock-shopify-product-{i + 1}",
                    "status": random.choice(["active", "draft", "archived"]),
                    "variants": [
                        {"id": random.randint(1000000000, 9999999999),
                         "sku": f"SHOPIFY-SKU-{i:04d}",
                         "price": str(round(random.uniform(5, 200), 2)),
                         "inventory_quantity": random.randint(0, 100)}
                    ],
                })

    async def authenticate(self, config: ConnectorAuthConfig) -> ConnectorAuthConfig:
        config.access_token = f"mock-shopify-token-{uuid.uuid4().hex[:16]}"
        self.auth_config = config
        return config

    async def call(self, method: str, path: str, params: dict | None = None,
                   body: dict | None = None, headers: dict | None = None) -> ConnectorCallResult:
        self._call_count += 1
        return ConnectorCallResult(
            success=True,
            data={"message": "Shopify API mock call", "method": method, "path": path},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def health_check(self) -> bool:
        return True

    async def refresh_token(self) -> ConnectorAuthConfig:
        return self.auth_config

    async def fetch_orders(self, start_time: str = "", end_time: str = "",
                           page_size: int = 50) -> ConnectorCallResult:
        orders = ShopifyMockConnector.MOCK_ORDERS[:page_size]
        if start_time:
            orders = [o for o in orders if o["created_at"] >= start_time]
        return ConnectorCallResult(
            success=True,
            data={"orders": orders, "total": len(orders)},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def fetch_listings(self, status: str = "") -> ConnectorCallResult:
        products = ShopifyMockConnector.MOCK_PRODUCTS
        if status:
            products = [p for p in products if p["status"] == status]
        return ConnectorCallResult(
            success=True,
            data={"products": products, "total": len(products)},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def update_listing(self, listing_id: str, data: dict) -> ConnectorCallResult:
        return ConnectorCallResult(
            success=True,
            data={"product_id": listing_id, "updated": True},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def acknowledge_order(self, order_id: str) -> ConnectorCallResult:
        return ConnectorCallResult(
            success=True,
            data={"order_id": order_id, "acknowledged": True},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def ship_order(self, order_id: str, tracking_number: str,
                         carrier: str = "") -> ConnectorCallResult:
        return ConnectorCallResult(
            success=True,
            data={"order_id": order_id, "tracking_number": tracking_number, "carrier": carrier},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )


class ShopeeMockConnector(BaseConnector):
    MOCK_ORDERS: list[dict] = []

    def __init__(self, connector_id: str, tenant_id: str, auth_config: ConnectorAuthConfig,
                 base_url: str = "https://mock-api.shopee.com/api/v2",
                 rate_limit: int = 20, timeout: int = 30):
        super().__init__(connector_id, tenant_id, auth_config, base_url, rate_limit, timeout)
        self._init_mock_data()

    def _init_mock_data(self):
        if not ShopeeMockConnector.MOCK_ORDERS:
            now = datetime.now(UTC)
            for _i in range(12):
                order_date = now - timedelta(days=random.randint(1, 30))
                ShopeeMockConnector.MOCK_ORDERS.append({
                    "order_sn": f"SHOPEE{random.randint(100000000, 999999999)}",
                    "order_status": random.choice(["UNPAID", "READY_TO_SHIP", "SHIPPED", "COMPLETED", "CANCELLED"]),
                    "create_time": int(order_date.timestamp()),
                    "update_time": int(order_date.timestamp()),
                    "total_amount": str(round(random.uniform(5, 200), 2)),
                    "currency": "CNY",
                    "item_count": random.randint(1, 5),
                    "region": "CN",
                })

    async def authenticate(self, config: ConnectorAuthConfig) -> ConnectorAuthConfig:
        config.access_token = f"mock-shopee-token-{uuid.uuid4().hex[:16]}"
        self.auth_config = config
        return config

    async def call(self, method: str, path: str, params: dict | None = None,
                   body: dict | None = None, headers: dict | None = None) -> ConnectorCallResult:
        self._call_count += 1
        return ConnectorCallResult(
            success=True,
            data={"message": "Shopee API mock call", "method": method, "path": path},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def health_check(self) -> bool:
        return True

    async def refresh_token(self) -> ConnectorAuthConfig:
        return self.auth_config

    async def fetch_orders(self, start_time: str = "", end_time: str = "",
                           page_size: int = 50) -> ConnectorCallResult:
        orders = ShopeeMockConnector.MOCK_ORDERS[:page_size]
        return ConnectorCallResult(
            success=True,
            data={"orders": orders, "total": len(orders), "more": False},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def fetch_listings(self, status: str = "") -> ConnectorCallResult:
        return ConnectorCallResult(
            success=True,
            data={"items": [], "total": 0},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )


class TikTokShopMockConnector(BaseConnector):
    MOCK_ORDERS: list[dict] = []

    def __init__(self, connector_id: str, tenant_id: str, auth_config: ConnectorAuthConfig,
                 base_url: str = "https://mock-api.tiktokshop.com/api/v1",
                 rate_limit: int = 20, timeout: int = 30):
        super().__init__(connector_id, tenant_id, auth_config, base_url, rate_limit, timeout)
        self._init_mock_data()

    def _init_mock_data(self):
        if not TikTokShopMockConnector.MOCK_ORDERS:
            now = datetime.now(UTC)
            for _i in range(10):
                order_date = now - timedelta(days=random.randint(1, 30))
                TikTokShopMockConnector.MOCK_ORDERS.append({
                    "order_id": f"TT{random.randint(100000000, 999999999)}",
                    "order_status": random.choice(["UNPAID", "AWAITING_SHIPMENT", "SHIPPED", "DELIVERED", "CANCELLED"]),
                    "create_time": order_date.isoformat(),
                    "total_amount": str(round(random.uniform(5, 150), 2)),
                    "currency": "USD",
                    "item_count": random.randint(1, 4),
                })

    async def authenticate(self, config: ConnectorAuthConfig) -> ConnectorAuthConfig:
        config.access_token = f"mock-tiktok-token-{uuid.uuid4().hex[:16]}"
        self.auth_config = config
        return config

    async def call(self, method: str, path: str, params: dict | None = None,
                   body: dict | None = None, headers: dict | None = None) -> ConnectorCallResult:
        self._call_count += 1
        return ConnectorCallResult(
            success=True,
            data={"message": "TikTok Shop API mock call", "method": method, "path": path},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def health_check(self) -> bool:
        return True

    async def refresh_token(self) -> ConnectorAuthConfig:
        return self.auth_config

    async def fetch_orders(self, start_time: str = "", end_time: str = "",
                           page_size: int = 50) -> ConnectorCallResult:
        orders = TikTokShopMockConnector.MOCK_ORDERS[:page_size]
        return ConnectorCallResult(
            success=True,
            data={"orders": orders, "total": len(orders)},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )


class FedExMockConnector(BaseConnector):
    async def authenticate(self, config: ConnectorAuthConfig) -> ConnectorAuthConfig:
        config.access_token = f"mock-fedex-token-{uuid.uuid4().hex[:16]}"
        self.auth_config = config
        return config

    async def call(self, method: str, path: str, params: dict | None = None,
                   body: dict | None = None, headers: dict | None = None) -> ConnectorCallResult:
        self._call_count += 1
        return ConnectorCallResult(success=True, data={}, status_code=200, trace_id=trace_id_var.get(""))

    async def health_check(self) -> bool:
        return True

    async def refresh_token(self) -> ConnectorAuthConfig:
        return self.auth_config

    async def create_shipment(self, shipment_data: dict) -> ConnectorCallResult:
        return ConnectorCallResult(
            success=True,
            data={
                "shipment_id": f"FX{uuid.uuid4().hex[:12].upper()}",
                "tracking_number": f"7489{random.randint(100000000, 999999999)}",
                "label_url": "https://mock-fedex.com/label/mock.pdf",
                "estimated_delivery": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
            },
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def get_tracking(self, tracking_number: str) -> ConnectorCallResult:
        events = []
        now = datetime.now(UTC)
        for i in range(random.randint(2, 5)):
            event_time = now - timedelta(days=random.randint(0, 5), hours=random.randint(0, 23))
            events.append({
                "timestamp": event_time.isoformat(),
                "status": random.choice(["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"]),
                "location": random.choice(["Memphis, TN", "Indianapolis, IN", "Los Angeles, CA"]),
                "description": f"Package status update {i + 1}",
            })
        return ConnectorCallResult(
            success=True,
            data={"tracking_number": tracking_number, "status": events[0]["status"] if events else "UNKNOWN",
                  "events": events},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def estimate_shipping_cost(self, params: dict) -> ConnectorCallResult:
        weight = params.get("weight_kg", 1)
        base_cost = 15 + weight * 8
        return ConnectorCallResult(
            success=True,
            data={
                "cost": round(base_cost, 2),
                "currency": "USD",
                "estimated_days": random.randint(2, 5),
                "service": "FEDEX_GROUND",
            },
            status_code=200,
            trace_id=trace_id_var.get(""),
        )


class YanwenMockConnector(BaseConnector):
    async def authenticate(self, config: ConnectorAuthConfig) -> ConnectorAuthConfig:
        config.api_key = f"mock-yanwen-key-{uuid.uuid4().hex[:16]}"
        self.auth_config = config
        return config

    async def call(self, method: str, path: str, params: dict | None = None,
                   body: dict | None = None, headers: dict | None = None) -> ConnectorCallResult:
        self._call_count += 1
        return ConnectorCallResult(success=True, data={}, status_code=200, trace_id=trace_id_var.get(""))

    async def health_check(self) -> bool:
        return True

    async def refresh_token(self) -> ConnectorAuthConfig:
        return self.auth_config

    async def create_shipment(self, shipment_data: dict) -> ConnectorCallResult:
        return ConnectorCallResult(
            success=True,
            data={
                "shipment_id": f"YW{uuid.uuid4().hex[:12].upper()}",
                "tracking_number": f"YW{random.randint(100000000, 999999999)}",
                "label_url": "https://mock-yanwen.com/label/mock.pdf",
            },
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def get_tracking(self, tracking_number: str) -> ConnectorCallResult:
        return ConnectorCallResult(
            success=True,
            data={"tracking_number": tracking_number, "status": "IN_TRANSIT",
                  "events": [{"timestamp": datetime.now(UTC).isoformat(), "status": "ACCEPTED",
                              "location": "Shenzhen, CN", "description": "Package accepted"}]},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def estimate_shipping_cost(self, params: dict) -> ConnectorCallResult:
        weight = params.get("weight_kg", 1)
        dest = params.get("destination_country", "US")
        base = 35 if dest in ("US", "GB", "DE") else 45
        return ConnectorCallResult(
            success=True,
            data={"cost": round(base + weight * 12, 2), "currency": "CNY",
                  "estimated_days": random.randint(7, 15), "service": "YANWEN_ECONOMY"},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )


class StripeMockConnector(BaseConnector):
    async def authenticate(self, config: ConnectorAuthConfig) -> ConnectorAuthConfig:
        config.api_key = f"sk_mock_{uuid.uuid4().hex[:24]}"
        self.auth_config = config
        return config

    async def call(self, method: str, path: str, params: dict | None = None,
                   body: dict | None = None, headers: dict | None = None) -> ConnectorCallResult:
        self._call_count += 1
        return ConnectorCallResult(success=True, data={}, status_code=200, trace_id=trace_id_var.get(""))

    async def health_check(self) -> bool:
        return True

    async def refresh_token(self) -> ConnectorAuthConfig:
        return self.auth_config

    async def get_balance(self) -> ConnectorCallResult:
        return ConnectorCallResult(
            success=True,
            data={"balance": round(random.uniform(1000, 50000), 2), "currency": "USD",
                  "pending": round(random.uniform(100, 5000), 2)},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def get_transactions(self, start_date: str = "", end_date: str = "") -> ConnectorCallResult:
        transactions = []
        for i in range(5):
            transactions.append({
                "id": f"txn_{uuid.uuid4().hex[:24]}",
                "amount": round(random.uniform(10, 500), 2),
                "currency": "usd",
                "type": random.choice(["charge", "payment", "refund"]),
                "status": random.choice(["succeeded", "pending"]),
                "created": (datetime.now(UTC) - timedelta(days=i)).isoformat(),
            })
        return ConnectorCallResult(
            success=True,
            data={"transactions": transactions, "has_more": False},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )

    async def initiate_payout(self, amount: float, currency: str = "USD") -> ConnectorCallResult:
        return ConnectorCallResult(
            success=True,
            data={"payout_id": f"po_{uuid.uuid4().hex[:24]}", "amount": amount,
                  "currency": currency.lower(), "status": "pending",
                  "arrival_date": (datetime.now(UTC) + timedelta(days=2)).isoformat()},
            status_code=200,
            trace_id=trace_id_var.get(""),
        )


ConnectorRegistry.register("amazon_sp", AmazonSPMockConnector)
ConnectorRegistry.register("shopify", ShopifyMockConnector)
ConnectorRegistry.register("shopee", ShopeeMockConnector)
ConnectorRegistry.register("tiktok_shop", TikTokShopMockConnector)
ConnectorRegistry.register("fedex", FedExMockConnector)
ConnectorRegistry.register("yanwen", YanwenMockConnector)
ConnectorRegistry.register("stripe", StripeMockConnector)
