"""
报表性能优化策略 (P6-013)

包含:
  - 预聚合策略: 按时间/维度预计算指标值
  - 缓存策略: 多级缓存(TTL/分层)
  - 分页优化: 游标分页/keyset分页
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass
class PreAggregationConfig:
    """预聚合配置"""
    metric_name: str = ""
    agg_type: str = "sum"  # sum / avg / count / max / min
    time_granularity: str = "hour"  # hour / day / week / month
    dimensions: list[str] = field(default_factory=list)
    retention_days: int = 90
    refresh_interval_s: int = 300


class PreAggregationService:
    """预聚合策略服务"""

    @staticmethod
    def suggest_aggregations(metric: str, time_range_days: int) -> list[PreAggregationConfig]:
        """根据查询时间范围推荐预聚合粒度"""
        configs = []
        if time_range_days <= 1:
            configs.append(PreAggregationConfig(metric_name=metric, agg_type="sum", time_granularity="hour"))
        elif time_range_days <= 30:
            configs.append(PreAggregationConfig(metric_name=metric, agg_type="sum", time_granularity="day"))
        elif time_range_days <= 365:
            configs.append(PreAggregationConfig(metric_name=metric, agg_type="sum", time_granularity="week"))
        else:
            configs.append(PreAggregationConfig(metric_name=metric, agg_type="sum", time_granularity="month"))
        return configs

    @staticmethod
    def best_granularity(days: int) -> str:
        if days <= 1: return "hour"
        if days <= 31: return "day"
        if days <= 90: return "week"
        return "month"


class CacheStrategyService:
    """缓存策略服务"""

    @staticmethod
    def ttl_for_report(report_type: str, time_range_days: int) -> int:
        """根据报表类型和时间范围推荐缓存TTL(秒)"""
        if time_range_days <= 1: return 60
        if time_range_days <= 7: return 300
        if time_range_days <= 30: return 1800
        return 3600

    @staticmethod
    def should_cache(metric: str, time_range_days: int, row_count: int) -> bool:
        """判断是否应该缓存该查询"""
        return row_count > 1000 or time_range_days > 7 or metric in ("dashboard", "kpi")


class PaginationService:
    """分页优化服务"""

    @staticmethod
    def estimate_pages(total: int, page_size: int) -> int:
        return max(1, (total + page_size - 1) // page_size)

    @staticmethod
    def validate_page(page: int, page_size: int) -> list[str]:
        errors = []
        if page < 1: errors.append("页码从1开始")
        if page_size < 1 or page_size > 1000: errors.append("每页数量 1-1000")
        return errors

    @staticmethod
    def keyset_pagination(items: list[dict], sort_key: str, last_value: Any = None, limit: int = 50) -> dict:
        """游标分页(keyset pagination): 适合大数据集"""
        if last_value is not None:
            items = [i for i in items if i.get(sort_key, 0) > last_value]
        page = items[:limit]
        next_value = page[-1].get(sort_key) if len(page) == limit and page else None
        return {"items": page, "next": next_value, "has_more": len(page) == limit}
