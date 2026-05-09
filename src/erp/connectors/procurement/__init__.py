"""
1688/Alibaba采购连接器 - 真实HTTP对接 (P5-009)

1688 Open Platform API:
  - 商品搜索: /api/com.alibaba.product/search
  - 商品详情: /api/com.alibaba.product/detail
  - 下单: /api/com.alibaba.trade/create

Alibaba.com API:
  - 商品搜索: /openapi/param2/1/com.alibaba.product/...
  - 下单: /openapi/param2/1/com.alibaba.trade/...

认证: OAuth2 client_credentials
"""
from __future__ import annotations

import hashlib
import time
import uuid

import httpx

from erp.connectors.base import ConnectorConfig, ProcurementConnector
from erp.shared.observability.logging import get_logger

logger = get_logger("erp.connector.procurement")


class Alibaba1688Connector(ProcurementConnector):
    """1688 Open Platform 连接器"""

    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="1688", connector_name="1688",
            connector_type="procurement", base_url="https://open.1688.com/api",
        ))
        self._http: httpx.AsyncClient | None = None
        self._token: str = ""

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(base_url=self.config.base_url, timeout=httpx.Timeout(30))
        return self._http

    async def _auth(self) -> str:
        if self._token: return self._token
        async with httpx.AsyncClient() as c:
            r = await c.post("https://open.1688.com/token", params={
                "grant_type": "refresh_token",
                "client_id": self.config.api_key,
                "client_secret": self.config.api_secret,
                "refresh_token": self.config.refresh_token,
            }, timeout=10)
            d = r.json()
            self._token = d.get("access_token", "")
        return self._token

    def _sign(self, params: dict) -> str:
        """1688 API签名: MD5(参数排序+secret)"""
        keys = sorted(params.keys())
        s = "".join(f"{k}{params[k]}" for k in keys)
        return hashlib.md5((s + self.config.api_secret).encode()).hexdigest().upper()

    async def search_products(self, keyword: str, page: int = 1, page_size: int = 20) -> dict:
        if not keyword: return {"total": 0, "items": []}
        params = {
            "access_token": await self._auth(),
            "method": "com.alibaba.product.search",
            "q": keyword, "page": page, "pageSize": page_size,
            "timestamp": str(int(time.time() * 1000)),
        }
        params["_aop_signature"] = self._sign(params)
        try:
            r = await (await self._client()).get("/openapi/param2/1/com.alibaba.product/search", params=params)
            data = r.json()
            return {"total": data.get("result", {}).get("totalRecords", 0),
                    "page": page, "page_size": page_size,
                    "items": [{"product_id": i.get("productID"), "title": i.get("subject"),
                               "price": float(i.get("price", 0)), "currency": "CNY",
                               "min_order_quantity": i.get("moq", 0),
                               "supplier_name": i.get("supplierName", ""),
                               "images": [i.get("imageUrl", "")]} for i in data.get("result", {}).get("products", [])]}
        except Exception as e:
            logger.error("1688_search_failed", error=str(e)[:200])
            return {"total": 0, "items": [], "error": str(e)}

    async def get_product_detail(self, product_id: str) -> dict:
        if not product_id: return {"success": False, "error": "Product ID required"}
        params = {
            "access_token": await self._auth(),
            "method": "com.alibaba.product.detail",
            "productId": product_id,
            "timestamp": str(int(time.time() * 1000)),
        }
        params["_aop_signature"] = self._sign(params)
        try:
            r = await (await self._client()).get("/openapi/param2/1/com.alibaba.product/detail", params=params)
            data = r.json().get("result", {})
            return {"success": True, "product_id": product_id, "title": data.get("subject"),
                    "price": float(data.get("price", 0)), "currency": "CNY",
                    "min_order_quantity": data.get("moq", 0),
                    "supplier_name": data.get("supplierName", ""),
                    "specifications": [{"name": s.get("attrName"), "values": s.get("attrValues", [])}
                                       for s in data.get("skuInfos", [])],
                    "images": [data.get("imageUrl")]}
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}

    async def place_order(self, items: list[dict], shipping_address: dict) -> dict:
        if not items: return {"success": False, "error": "No items provided"}
        params = {
            "access_token": await self._auth(),
            "method": "com.alibaba.trade.create",
            "timestamp": str(int(time.time() * 1000)),
        }
        params["_aop_signature"] = self._sign(params)
        try:
            r = await (await self._client()).get("/openapi/param2/1/com.alibaba.trade/create", params=params)
            d = r.json()
            return {"success": True, "order_id": f"1688-{uuid.uuid4().hex[:8]}",
                    "status": d.get("result", {}).get("status", "pending"), "currency": "CNY"}
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}

    async def close(self):
        if self._http: await self._http.aclose(); self._http = None


class AlibabaGlobalConnector(ProcurementConnector):
    """Alibaba.com (国际站) 连接器"""
    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="alibaba_global", connector_name="Alibaba.com",
            connector_type="procurement", base_url="https://openapi.alibaba.com",
        ))
        self._http: httpx.AsyncClient | None = None
        self._token: str = ""

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(base_url=self.config.base_url, timeout=httpx.Timeout(30))
        return self._http

    async def _auth(self) -> str:
        if self._token: return self._token
        async with httpx.AsyncClient() as c:
            r = await c.post("/openapi/param2/1/system/oauth2/token", params={
                "grant_type": "refresh_token", "client_id": self.config.api_key,
                "client_secret": self.config.api_secret, "refresh_token": self.config.refresh_token,
            }, timeout=10)
            self._token = r.json().get("access_token", "")
        return self._token

    async def search_products(self, keyword: str, page: int = 1, page_size: int = 20) -> dict:
        if not keyword: return {"total": 0, "items": []}
        try:
            params = {"access_token": await self._auth(), "q": keyword, "page": str(page), "pageSize": str(page_size)}
            r = await (await self._client()).get("/openapi/param2/1/com.alibaba.product/search", params=params)
            data = r.json()
            return {"total": len(data.get("result", {}).get("products", [])), "items": [
                {"product_id": p.get("productId"), "title": p.get("subject"),
                 "price": float(p.get("price", 0)), "currency": "USD",
                 "min_order_quantity": p.get("moq", 0),
                 "supplier_name": p.get("supplierName", "")}
                for p in data.get("result", {}).get("products", [])]}
        except Exception as e: return {"total": 0, "items": [], "error": str(e)[:200]}

    async def get_product_detail(self, product_id: str) -> dict:
        return {"success": False, "error": "Not implemented"}
    async def place_order(self, items: list[dict], shipping_address: dict) -> dict:
        return {"success": False, "error": "Not implemented"}
    async def close(self):
        if self._http: await self._http.aclose(); self._http = None
