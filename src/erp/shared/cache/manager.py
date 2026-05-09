from __future__ import annotations

import functools
import hashlib
import json
from typing import TYPE_CHECKING, Any

from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger("erp.cache")

_cache_manager: CacheManager | None = None


def init_cache_manager(redis_client=None, default_ttl: int = 300) -> CacheManager:
    global _cache_manager
    _cache_manager = CacheManager(redis_client=redis_client, default_ttl=default_ttl)
    return _cache_manager


def get_cache_manager() -> CacheManager:
    if _cache_manager is None:
        return init_cache_manager()
    return _cache_manager


DOMAIN_CACHE_TTL: dict[str, int] = {
    "dashboard_kpi": 60,
    "dashboard_trend": 300,
    "dashboard_alert": 30,
    "dashboard_todo": 30,
    "pdm_product": 600,
    "pdm_category": 3600,
    "som_listing": 120,
    "som_store": 600,
    "som_price_rule": 600,
    "oms_order": 30,
    "oms_strategy": 300,
    "wms_inventory": 30,
    "wms_warehouse": 600,
    "tms_logistics": 120,
    "fms_cost": 300,
    "fms_profit": 300,
    "ads_campaign": 60,
    "ads_keyword": 60,
    "crm_customer": 120,
    "crm_ticket": 30,
    "fba_shipment": 60,
    "bi_report": 600,
    "sys_dict": 3600,
    "sys_param": 3600,
    "iam_permission": 1800,
    "iam_role": 1800,
}


def cached(prefix: str, ttl: int | None = None, key_builder: Callable | None = None):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cm = get_cache_manager()
            effective_ttl = ttl or DOMAIN_CACHE_TTL.get(prefix, cm._default_ttl)
            if key_builder:
                cache_params = key_builder(*args, **kwargs)
            else:
                cache_params = {"func": func.__qualname__, "args": _serialize_args(args, kwargs)}
            result = await cm.get(prefix, cache_params)
            if result is not None:
                logger.debug("cache_hit", prefix=prefix, func=func.__qualname__)
                return result
            result = await func(*args, **kwargs)
            if result is not None:
                await cm.set(prefix, cache_params, result, ttl=effective_ttl)
                logger.debug("cache_miss_set", prefix=prefix, func=func.__qualname__, ttl=effective_ttl)
            return result
        return wrapper
    return decorator


def _serialize_args(args: tuple, kwargs: dict) -> list:
    serialized = []
    for arg in args:
        try:
            json.dumps(arg, default=str)
            serialized.append(arg)
        except (TypeError, ValueError):
            serialized.append(str(id(arg)))
    for k, v in sorted(kwargs.items()):
        try:
            json.dumps(v, default=str)
            serialized.append({k: v})
        except (TypeError, ValueError):
            serialized.append({k: str(id(v))})
    return serialized


class CacheManager:
    def __init__(self, redis_client=None, default_ttl: int = 300):
        self._redis = redis_client
        self._default_ttl = default_ttl
        self._local_cache: dict[str, tuple[Any, float]] = {}
        self._local_ttl: int = 10

    def _make_key(self, prefix: str, params: dict) -> str:
        raw = json.dumps(params, sort_keys=True, default=str)
        digest = hashlib.md5(raw.encode()).hexdigest()
        return f"erp:{prefix}:{digest}"

    async def get(self, prefix: str, params: dict) -> Any | None:
        key = self._make_key(prefix, params)
        if key in self._local_cache:
            value, expire_at = self._local_cache[key]
            import time
            if time.monotonic() < expire_at:
                return value
            del self._local_cache[key]
        if self._redis:
            try:
                raw = await self._redis.get(key)
                if raw:
                    value = json.loads(raw)
                    self._set_local(key, value)
                    return value
            except Exception as e:
                logger.warning("cache_get_failed", key=key, error=str(e))
        return None

    async def set(self, prefix: str, params: dict, value: Any, ttl: int | None = None) -> None:
        key = self._make_key(prefix, params)
        effective_ttl = ttl or self._default_ttl
        self._set_local(key, value)
        if self._redis:
            try:
                await self._redis.setex(key, effective_ttl, json.dumps(value, default=str))
            except Exception as e:
                logger.warning("cache_set_failed", key=key, error=str(e))

    async def invalidate(self, prefix: str, params: dict | None = None) -> None:
        if params:
            key = self._make_key(prefix, params)
            self._local_cache.pop(key, None)
            if self._redis:
                try:
                    await self._redis.delete(key)
                except Exception as e:
                    logger.warning("cache_invalidate_failed", key=key, error=str(e))
        else:
            keys_to_remove = [k for k in self._local_cache if k.startswith(f"erp:{prefix}:")]
            for k in keys_to_remove:
                del self._local_cache[k]
            if self._redis:
                try:
                    async for k in self._redis.scan_iter(f"erp:{prefix}:*"):
                        await self._redis.delete(k)
                except Exception as e:
                    logger.warning("cache_bulk_invalidate_failed", prefix=prefix, error=str(e))

    def _set_local(self, key: str, value: Any) -> None:
        import time
        self._local_cache[key] = (value, time.monotonic() + self._local_ttl)


class QueryOptimizer:
    COMMON_INDEXES = [
        ("pdm", "sku", ["tenant_id", "spu_id", "status"]),
        ("pdm", "spu", ["tenant_id", "category_id", "status"]),
        ("oms", "sales_order", ["tenant_id", "store_id", "status", "created_at"]),
        ("oms", "order_item", ["tenant_id", "order_id", "sku_id"]),
        ("wms", "inventory_account", ["tenant_id", "sku_id", "warehouse_id"]),
        ("fms", "cost_event", ["tenant_id", "domain", "event_type", "created_at"]),
        ("iam", "user", ["tenant_id", "status"]),
        ("iam", "user_role", ["user_id", "role_id"]),
    ]

    @classmethod
    def generate_index_ddl(cls) -> list[str]:
        statements = []
        for schema, table, columns in cls.COMMON_INDEXES:
            idx_name = f"idx_{table}_{'_'.join(columns)}"
            col_list = ", ".join(columns)
            statements.append(
                f"CREATE INDEX IF NOT EXISTS {idx_name} ON {schema}.{table} ({col_list});"
            )
        return statements

    @classmethod
    def suggest_partition(cls, table: str, schema: str = "oms") -> list[str]:
        partition_suggestions = {
            "sales_order": f"ALTER TABLE {schema}.sales_order PARTITION BY RANGE (TO_DAYS(created_at)) (PARTITION p_2025_q1 VALUES LESS THAN (TO_DAYS('2025-04-01')), PARTITION p_2025_q2 VALUES LESS THAN (TO_DAYS('2025-07-01')), PARTITION p_2025_q3 VALUES LESS THAN (TO_DAYS('2025-10-01')), PARTITION p_2025_q4 VALUES LESS THAN (TO_DAYS('2026-01-01')), PARTITION p_future VALUES LESS THAN MAXVALUE);",
            "order_item": f"ALTER TABLE {schema}.order_item PARTITION BY RANGE (TO_DAYS(created_at)) (PARTITION p_2025_q1 VALUES LESS THAN (TO_DAYS('2025-04-01')), PARTITION p_future VALUES LESS THAN MAXVALUE);",
            "cost_event": "ALTER TABLE fms.cost_event PARTITION BY RANGE (TO_DAYS(created_at)) (PARTITION p_2025_q1 VALUES LESS THAN (TO_DAYS('2025-04-01')), PARTITION p_future VALUES LESS THAN MAXVALUE);",
            "inventory_transaction": "ALTER TABLE wms.inventory_transaction PARTITION BY RANGE (TO_DAYS(created_at)) (PARTITION p_2025_q1 VALUES LESS THAN (TO_DAYS('2025-04-01')), PARTITION p_future VALUES LESS THAN MAXVALUE);",
        }
        return [partition_suggestions.get(table, f"-- No partition suggestion for {table}")]
