"""
Shopify REST Admin API 连接器 - 真实HTTP对接实现

API版本: 2024-01
对接清单:
  - REST Admin API: 订单查询、商品查询、库存更新
  - GraphQL API: Product查询与变更

认证: Admin API access_token (X-Shopify-Access-Token)
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx

from erp.connectors.base import (
    ConnectorConfig,
    InventorySyncItem,
    ListingFetchParams,
    ListingUpdateData,
    OrderFetchParams,
    OrderItem,
    PlatformConnector,
    PlatformListing,
    PlatformOrder,
    SyncResult,
    UpdateResult,
)
from erp.shared.observability.logging import get_logger

logger = get_logger("erp.connector.shopify")

SHOPIFY_API_VERSION = "2024-01"
ORDER_STATUS_MAP = {
    "open": "confirmed", "pending": "pending", "unfulfilled": "confirmed",
    "partially_fulfilled": "processing", "fulfilled": "shipped",
    "cancelled": "cancelled", "archived": "cancelled",
}


class ShopifyConnector(PlatformConnector):
    """
    Shopify REST Admin API连接器

    通过httpx异步调用Shopify REST Admin API。
    认证: X-Shopify-Access-Token header。
    """

    def __init__(self, config: ConnectorConfig | None = None):
        shop = (config or ConnectorConfig()).extra.get("shop_name", "default")
        super().__init__(config or ConnectorConfig(
            connector_id="shopify", connector_name="Shopify",
            connector_type="platform",
            base_url=f"https://{shop}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}",
        ))
        self._http: httpx.AsyncClient | None = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(30, connect=10),
                headers={"X-Shopify-Access-Token": self.config.access_token,
                         "Content-Type": "application/json"},
            )
        return self._http

    async def close(self):
        if self._http: await self._http.aclose(); self._http = None

    async def fetch_orders(self, params: OrderFetchParams) -> tuple[list[PlatformOrder], str]:
        c = await self._client()
        q = {"limit": 50, "status": "any"}
        if params.status and params.status != "all":
            q["fulfillment_status"] = params.status
        if params.updated_after:
            q["updated_at_min"] = params.updated_after
        try:
            r = await c.get("/orders.json", params=q); r.raise_for_status()
            orders_data = r.json().get("orders", [])
        except Exception as e:
            logger.error("shopify_fetch_orders_failed", error=str(e)[:200])
            return [], str(e)

        orders = []
        for o in orders_data:
            items = []
            for li in o.get("line_items", []):
                items.append(OrderItem(
                    item_id=str(li.get("id")), sku=li.get("sku", ""),
                    title=li.get("title", ""), quantity=int(li.get("quantity", 0)),
                    unit_price=float(li.get("price", 0)), currency="USD"))
            orders.append(PlatformOrder(
                order_id=str(uuid.uuid4()),
                platform_order_id=str(o.get("id", "")),
                platform="shopify", store_id=self.config.store_id,
                status=ORDER_STATUS_MAP.get(o.get("fulfillment_status", "unfulfilled"), "confirmed"),
                order_date=o.get("created_at", ""),
                buyer_name=o.get("customer", {}).get("first_name", ""),
                buyer_email=o.get("email", ""), items=items,
                total_amount=float(o.get("total_price", 0)), currency="USD",
                shipping_cost=float(o.get("total_shipping_price_set", {}).get("shop_money", {}).get("amount", 0))))
        return orders, ""

    async def sync_inventory(self, items: list[InventorySyncItem]) -> SyncResult:
        synced = failed = 0; errors = []
        for item in items:
            if not item.sku: failed += 1; errors.append({"sku": item.sku, "error": "SKU required"}); continue
            try:
                c = await self._client()
                r = await c.get(f"/products.json?sku={item.sku}")
                if r.status_code != 200: failed += 1; errors.append({"sku": item.sku, "error": "Product not found"}); continue
                products = r.json().get("products", [])
                for p in products:
                    for v in p.get("variants", []):
                        if v.get("sku") == item.sku:
                            await c.put(f"/variants/{v['id']}.json", json={"variant": {"id": v["id"], "inventory_quantity": item.quantity}})
                            synced += 1
            except Exception as e:
                failed += 1; errors.append({"sku": item.sku, "error": str(e)[:100]})
        return SyncResult(success=failed == 0, synced_count=synced, failed_count=failed, errors=errors)

    async def update_listing(self, listing_id: str, data: ListingUpdateData) -> UpdateResult:
        c = await self._client()
        patch = {}
        if data.price is not None: patch["price"] = str(data.price)
        if data.quantity is not None: patch["inventory_quantity"] = data.quantity
        if data.status: patch["status"] = data.status
        if not patch: return UpdateResult(success=True, listing_id=listing_id)
        try:
            r = await c.put(f"/variants/{listing_id}.json", json={"variant": patch}); r.raise_for_status()
            return UpdateResult(success=True, listing_id=listing_id)
        except Exception as e:
            return UpdateResult(success=False, listing_id=listing_id, error_message=str(e)[:200])

    async def fetch_listings(self, params: ListingFetchParams) -> tuple[list[PlatformListing], str]:
        c = await self._client()
        try:
            r = await c.get("/products.json", params={"limit": 50, "status": params.status or "active"})
            r.raise_for_status(); products = r.json().get("products", [])
        except Exception as e: return [], str(e)
        listings = []
        for p in products:
            for v in p.get("variants", []):
                listings.append(PlatformListing(
                    listing_id=str(uuid.uuid4()), platform_listing_id=str(v.get("id", "")),
                    platform="shopify", store_id=self.config.store_id,
                    sku=v.get("sku", ""), title=p.get("title", ""),
                    price=float(v.get("price", 0)), currency="USD",
                    quantity=v.get("inventory_quantity", 0), status=p.get("status", "active")))
        return listings, ""
