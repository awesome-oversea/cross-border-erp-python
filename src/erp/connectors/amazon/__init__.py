"""
Amazon SP-API 连接器 - 真实HTTP对接实现

Orders API v0: 订单同步、订单明细、发货确认
Listings Items 2021-08-01: Listing查询与更新
FBA Inventory v1: 库存同步

认证: OAuth2 refresh_token -> access_token
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

logger = get_logger("erp.connector.amazon")

SP_API_ENDPOINTS = {
    "NA": "https://sellingpartnerapi-na.amazon.com",
    "EU": "https://sellingpartnerapi-eu.amazon.com",
    "FE": "https://sellingpartnerapi-fe.amazon.com",
}

ORDER_STATUS_MAP = {
    "PendingAvailability": "pending", "Pending": "pending", "Unshipped": "confirmed",
    "PartiallyShipped": "processing", "Shipped": "shipped",
    "InvoiceUnconfirmed": "shipped", "Cancelled": "cancelled", "Unfulfillable": "cancelled",
}


class AmazonConnector(PlatformConnector):
    """Amazon SP-API连接器: httpx异步OAuth2+HTTP对接"""

    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="amazon", connector_name="Amazon",
            connector_type="platform", base_url="https://sellingpartnerapi-na.amazon.com",
        ))
        self._http: httpx.AsyncClient | None = None
        self._token: str = ""
        self._token_expires: float = 0

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self._endpoint(), timeout=httpx.Timeout(30, connect=10))
        return self._http

    def _endpoint(self) -> str:
        m = self.config.marketplace_id or ""
        if m.startswith(("A2Q", "A2E")): return SP_API_ENDPOINTS["EU"]
        if m.startswith(("A1V", "A2I")): return SP_API_ENDPOINTS["FE"]
        return SP_API_ENDPOINTS["NA"]

    async def _get_token(self) -> str:
        if self._token and self._token_expires > datetime.now(UTC).timestamp():
            return self._token
        async with httpx.AsyncClient() as c:
            r = await c.post("https://api.amazon.com/auth/o2/token", json={
                "grant_type": "refresh_token", "refresh_token": self.config.refresh_token,
                "client_id": self.config.api_key, "client_secret": self.config.api_secret,
            }, timeout=10)
            d = r.json()
            self._token = d.get("access_token", "")
            self._token_expires = datetime.now(UTC).timestamp() + d.get("expires_in", 3600) - 60
        return self._token

    async def _headers(self) -> dict:
        return {"x-amz-access-token": await self._get_token(), "Content-Type": "application/json"}

    async def fetch_orders(self, params: OrderFetchParams) -> tuple[list[PlatformOrder], str]:
        c, h = await self._client(), await self._headers()
        q = {"MarketplaceIds": self.config.marketplace_id, "MaxResultsPerPage": 50}
        if params.status and params.status != "all":
            s = ",".join(k for k, v in ORDER_STATUS_MAP.items() if v == params.status)
            if s: q["OrderStatuses"] = s
        if params.updated_after: q["LastUpdatedAfter"] = params.updated_after
        try:
            r = await c.get("/orders/v0/orders", params=q, headers=h); r.raise_for_status()
            orders_data = r.json().get("payload", {}).get("Orders", [])
        except Exception as e:
            logger.error("fetch_orders_failed", error=str(e)[:200])
            return [], str(e)
        orders = []
        for o in orders_data:
            items = await self._order_items(o.get("AmazonOrderId", ""))
            orders.append(PlatformOrder(order_id=str(uuid.uuid4()),
                platform_order_id=o.get("AmazonOrderId", ""), platform="amazon",
                store_id=self.config.store_id,
                status=ORDER_STATUS_MAP.get(o.get("OrderStatus", ""), "pending"),
                order_date=o.get("PurchaseDate", ""), buyer_name=o.get("BuyerName", ""),
                items=items,
                total_amount=float(o.get("OrderTotal", {}).get("Amount", 0)),
                currency=o.get("OrderTotal", {}).get("CurrencyCode", "USD"), shipping_cost=0.0))
        return orders, ""

    async def _order_items(self, amz_id: str) -> list:
        try:
            r = await (await self._client()).get(
                f"/orders/v0/orders/{amz_id}/orderItems", headers=await self._headers())
            if r.status_code != 200: return []
            items = r.json().get("payload", {}).get("OrderItems", [])
            return [{"item_id": i.get("OrderItemId"), "sku": i.get("SellerSKU", ""),
                     "title": i.get("Title", ""), "quantity": int(i.get("QuantityOrdered", 0)),
                     "unit_price": float(i.get("ItemPrice", {}).get("Amount", 0)),
                     "currency": i.get("ItemPrice", {}).get("CurrencyCode", "USD")} for i in items]
        except: return []

    async def sync_inventory(self, items: list[InventorySyncItem]) -> SyncResult:
        synced = failed = 0; errors = []
        for item in items:
            if not item.sku:
                failed += 1; errors.append({"sku": item.sku, "error": "SKU required"}); continue
            try:
                c, h = await self._client(), await self._headers()
                await c.post("/fba/inventory/v1/supply", json=[{
                    "sellerSku": item.sku, "quantity": item.quantity,
                    "marketplaceId": self.config.marketplace_id}], headers=h)
                synced += 1
            except Exception as e:
                failed += 1; errors.append({"sku": item.sku, "error": str(e)[:100]})
        return SyncResult(success=failed == 0, synced_count=synced, failed_count=failed, errors=errors)

    async def update_listing(self, listing_id: str, data: ListingUpdateData) -> UpdateResult:
        c, h = await self._client(), await self._headers()
        patches = {}
        if data.price is not None: patches["price"] = {"value": data.price, "currency": data.currency or "USD"}
        if data.quantity is not None: patches["quantity"] = data.quantity
        if data.status: patches["status"] = data.status
        if not patches: return UpdateResult(success=True, listing_id=listing_id)
        try:
            r = await c.patch(f"/listings/2021-08-01/items/{self.config.seller_id}/{listing_id}",
                json={"patches": [{"op": "replace", "path": f"/{k}", "value": v} for k, v in patches.items()]},
                headers=h); r.raise_for_status()
            return UpdateResult(success=True, listing_id=listing_id)
        except Exception as e:
            return UpdateResult(success=False, listing_id=listing_id, error_message=str(e)[:200])

    async def fetch_listings(self, params: ListingFetchParams) -> tuple[list[PlatformListing], str]:
        c, h = await self._client(), await self._headers()
        q = {"marketplaceIds": self.config.marketplace_id}
        if params.status: q["itemStatus"] = params.status
        try:
            r = await c.get(f"/listings/2021-08-01/items/{self.config.seller_id}", params=q, headers=h)
            r.raise_for_status(); items = r.json().get("items", [])
        except Exception as e: return [], str(e)
        listings = []
        for item in items:
            s = (item.get("summaries") or [{}])[0]
            listings.append(PlatformListing(listing_id=str(uuid.uuid4()),
                platform_listing_id=item.get("sku", ""), platform="amazon",
                store_id=self.config.store_id, sku=item.get("sku", ""),
                title=s.get("itemName", ""), price=0.0, currency="USD",
                quantity=0, status=s.get("status", "active")))
        return listings, ""

    async def confirm_shipment(self, order_id: str, tracking_no: str, carrier: str = "") -> UpdateResult:
        try:
            r = await (await self._client()).post(f"/orders/v0/orders/{order_id}/shipment",
                headers=await self._headers(),
                json={"payload": {"fulfillmentDate": datetime.now(UTC).isoformat(),
                      "fulfillmentData": [{"trackingNumber": tracking_no, "carrierCode": carrier or "Other"}]}})
            r.raise_for_status()
            return UpdateResult(success=True, listing_id=order_id)
        except Exception as e:
            return UpdateResult(success=False, listing_id=order_id, error_message=str(e)[:200])

    async def close(self):
        if self._http: await self._http.aclose(); self._http = None
