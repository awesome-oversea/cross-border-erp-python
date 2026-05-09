from __future__ import annotations

import json

import httpx

from erp.shared.observability.logging import get_logger

logger = get_logger("erp.search")


class SearchService:
    def __init__(self, es_url: str = "http://localhost:9200"):
        self._es_url = es_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def create_index(self, index_name: str, mapping: dict) -> bool:
        url = f"{self._es_url}/{index_name}"
        resp = await self._client.put(url, json=mapping)
        if resp.status_code in (200, 201):
            logger.info("es_index_created", index=index_name)
            return True
        logger.warning("es_index_create_failed", index=index_name, status=resp.status_code)
        return False

    async def index_document(self, index_name: str, doc_id: str, document: dict) -> bool:
        url = f"{self._es_url}/{index_name}/_doc/{doc_id}"
        resp = await self._client.put(url, json=document)
        return resp.status_code in (200, 201)

    async def bulk_index(self, index_name: str, documents: list[dict]) -> int:
        if not documents:
            return 0
        lines = []
        for doc in documents:
            action = {"index": {"_id": doc.pop("_id", None)}}
            lines.append(json.dumps(action))
            lines.append(json.dumps(doc, default=str))
        url = f"{self._es_url}/{index_name}/_bulk"
        resp = await self._client.post(url, content="\n".join(lines) + "\n", headers={"Content-Type": "application/x-ndjson"})
        if resp.status_code == 200:
            result = resp.json()
            return result.get("items", []).__len__()
        return 0

    async def search(self, index_name: str, query: dict, page: int = 1, page_size: int = 20) -> dict:
        from_val = (page - 1) * page_size
        body = {
            **query,
            "from": from_val,
            "size": page_size,
        }
        url = f"{self._es_url}/{index_name}/_search"
        resp = await self._client.post(url, json=body)
        if resp.status_code == 200:
            result = resp.json()
            hits = result.get("hits", {})
            return {
                "total": hits.get("total", {}).get("value", 0),
                "items": [h["_source"] | {"_score": h.get("_score")} for h in hits.get("hits", [])],
                "page": page,
                "page_size": page_size,
            }
        return {"total": 0, "items": [], "page": page, "page_size": page_size}

    async def delete_document(self, index_name: str, doc_id: str) -> bool:
        url = f"{self._es_url}/{index_name}/_doc/{doc_id}"
        resp = await self._client.delete(url)
        return resp.status_code in (200, 404)

    async def delete_index(self, index_name: str) -> bool:
        url = f"{self._es_url}/{index_name}"
        resp = await self._client.delete(url)
        return resp.status_code in (200, 404)

    async def close(self) -> None:
        await self._client.aclose()


PRODUCT_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "tenant_id": {"type": "keyword"},
            "spu_id": {"type": "keyword"},
            "sku_id": {"type": "keyword"},
            "spu_name": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_smart"},
            "sku_name": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_smart"},
            "category_name": {"type": "keyword"},
            "brand_name": {"type": "keyword"},
            "status": {"type": "keyword"},
            "created_at": {"type": "date"},
        }
    }
}

ORDER_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "tenant_id": {"type": "keyword"},
            "order_id": {"type": "keyword"},
            "order_no": {"type": "keyword"},
            "platform": {"type": "keyword"},
            "store_id": {"type": "keyword"},
            "status": {"type": "keyword"},
            "buyer_name": {"type": "text", "analyzer": "ik_max_word"},
            "created_at": {"type": "date"},
        }
    }
}
