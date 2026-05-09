"""
FBA/海外仓/3PL 连接器 (P5-006)

Amazon FBA: Fulfillment Inbound/Outbound APIs
ShipBob: ShipBob 3PL API
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx

from erp.connectors.base import ConnectorConfig, WarehouseConnector, WarehouseInventory, WarehouseInventoryQuery, WarehouseReceipt, WarehouseReceiptResult
from erp.shared.observability.logging import get_logger

logger = get_logger("erp.connector.warehouse")

SP_API_ENDPOINTS = {
    "NA": "https://sellingpartnerapi-na.amazon.com",
    "EU": "https://sellingpartnerapi-eu.amazon.com",
    "FE": "https://sellingpartnerapi-fe.amazon.com",
}


class FBAConnector(WarehouseConnector):
    """Amazon FBA 连接器 (SP-API Fulfillment APIs)"""

    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="fba", connector_name="Amazon FBA",
            connector_type="warehouse", base_url=SP_API_ENDPOINTS["NA"],
        ))
        self._http: httpx.AsyncClient | None = None
        self._token: str = ""
        self._token_expires: float = 0

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            m = self.config.marketplace_id or ""
            ep = SP_API_ENDPOINTS["EU"] if m.startswith(("A2Q", "A2E")) else \
                 SP_API_ENDPOINTS["FE"] if m.startswith(("A1V", "A2I")) else SP_API_ENDPOINTS["NA"]
            self._http = httpx.AsyncClient(base_url=ep, timeout=httpx.Timeout(30))
        return self._http

    async def _auth(self) -> str:
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

    async def _h(self) -> dict:
        return {"x-amz-access-token": await self._auth(), "Content-Type": "application/json"}

    async def query_inventory(self, query: WarehouseInventoryQuery) -> list[WarehouseInventory]:
        c, h = await self._client(), await self._h()
        try:
            r = await c.get("/fba/inventory/v1/summaries", params={
                "marketplaceIds": self.config.marketplace_id,
                "granularityType": "Marketplace",
                "sku": query.sku or "",
            }, headers=h)
            data = r.json()
            result = []
            for inv in data.get("payload", {}).get("inventorySummaries", []):
                d = inv.get("inventoryDetails", {})
                result.append(WarehouseInventory(
                    sku=inv.get("sellerSku", ""), warehouse_id="FBA",
                    quantity_on_hand=d.get("fulfillableQuantity", 0) + d.get("inboundWorkingQuantity", 0) + d.get("inboundShippedQuantity", 0),
                    quantity_reserved=d.get("reservedQuantity", 0),
                    quantity_available=d.get("fulfillableQuantity", 0),
                    location="Amazon FBA",
                ))
            return result
        except Exception as e:
            logger.error("fba_inventory_query_failed", error=str(e)[:200])
            return []

    async def create_receipt(self, receipt: WarehouseReceipt) -> WarehouseReceiptResult:
        try:
            c, h = await self._client(), await self._h()
            payload = {
                "marketplaceId": self.config.marketplace_id,
                "shipFromAddress": {"name": receipt.warehouse_id or "Default", "addressLine1": "Default"},
                "inboundShipmentPlanRequestItems": [
                    {"sellerSku": receipt.sku or "", "quantity": receipt.expected_qty or 0}
                ],
            }
            r = await c.post("/fba/inbound/v0/plans", json=payload, headers=h)
            data = r.json()
            plan = (data.get("payload", {}).get("inboundShipmentPlans") or [{}])[0]
            return WarehouseReceiptResult(
                success=r.status_code == 200, receipt_id=plan.get("shipmentId", str(uuid.uuid4())),
                status="CREATED" if r.status_code == 200 else "FAILED",
            )
        except Exception as e:
            return WarehouseReceiptResult(success=False, receipt_id="", status="FAILED", error_message=str(e)[:200])

    async def create_outbound(self, order_id: str, items: list[dict]) -> dict:
        c, h = await self._client(), await self._h()
        try:
            r = await c.post("/fba/outbound/v0/fulfillmentOrders", headers=h, json={
                "sellerFulfillmentOrderId": order_id,
                "marketplaceId": self.config.marketplace_id,
                "displayableOrderId": order_id,
                "displayableOrderDate": datetime.now(UTC).isoformat(),
                "items": [{"sellerSku": i.get("sku"), "quantity": i.get("qty", 1),
                           "sellerFulfillmentOrderItemId": i.get("id", str(uuid.uuid4()))} for i in items],
            })
            data = r.json()
            return {"success": r.status_code == 200, "order_id": order_id,
                    "status": data.get("payload", {}).get("status", "COMPLETED") if r.status_code == 200 else "FAILED",
                    "shipment_id": data.get("payload", {}).get("fulfillmentOrderStatus", {}).get("fulfillmentShipmentId", "")}
        except Exception as e:
            return {"success": False, "order_id": order_id, "error": str(e)[:200]}

    async def close(self):
        if self._http: await self._http.aclose(); self._http = None


class ShipBobConnector(WarehouseConnector):
    """ShipBob 3PL 连接器"""
    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="shipbob", connector_name="ShipBob",
            connector_type="warehouse", base_url="https://api.shipbob.com/1.0"))
        self._http: httpx.AsyncClient | None = None

    async def _c(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(base_url=self.config.base_url, timeout=httpx.Timeout(30),
                headers={"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"})
        return self._http

    async def query_inventory(self, query: WarehouseInventoryQuery) -> list[WarehouseInventory]:
        try:
            r = await (await self._c()).get("/inventory", params={"sku": query.sku, "location_id": query.warehouse_id})
            data = r.json()
            return [WarehouseInventory(sku=i.get("sku"), warehouse_id=i.get("location_id"),
                    quantity_on_hand=i.get("on_hand", 0), quantity_reserved=i.get("reserved", 0),
                    quantity_available=i.get("available", 0), location=i.get("location_name", ""))
                    for i in (data if isinstance(data, list) else data.get("data", []))]
        except Exception as e: return []

    async def create_receipt(self, receipt: WarehouseReceipt) -> WarehouseReceiptResult:
        try:
            r = await (await self._c()).post("/receipts", json={"sku": receipt.sku, "quantity": receipt.expected_qty})
            d = r.json()
            return WarehouseReceiptResult(success=r.status_code in (200, 201), receipt_id=d.get("id", ""), status="pending")
        except Exception as e:
            return WarehouseReceiptResult(success=False, receipt_id="", status="failed", error_message=str(e)[:200])

    async def create_outbound(self, order_id: str, items: list[dict]) -> dict:
        return {"success": False, "error": "Not implemented"}

    async def close(self):
        if self._http: await self._http.aclose(); self._http = None
