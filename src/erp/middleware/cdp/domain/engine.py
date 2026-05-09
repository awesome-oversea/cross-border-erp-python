"""
CDP (Customer Data Platform) 客户数据中台引擎

职责:
  - 客户画像: 基于订单/售后/浏览等多维度数据构建客户画像
  - 客户分群: 按RFM/行为/属性等维度自动分群
  - 标签管理: 客户标签的自动生成与匹配
  - LTV计算: 客户生命周期价值预测

被调用方: CRM(客服域), SOM(销售域), ADS(广告域)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class CustomerSegment(StrEnum):
    VIP = "vip"
    HIGH_VALUE = "high_value"
    REGULAR = "regular"
    NEW = "new"
    INACTIVE = "inactive"
    NORMAL = "normal"


@dataclass
class CustomerProfile:
    customer_id: str = ""
    name: str = ""
    email: str = ""
    platform: str = ""
    total_orders: int = 0
    total_spent: float = 0.0
    avg_order_value: float = 0.0
    last_order_date: str = ""
    first_order_date: str = ""
    tags: list[str] = field(default_factory=list)
    segment: str = "normal"
    predicted_ltv: float = 0.0


class CdpEngine:
    """
    客户数据平台引擎

    提供客户画像、分群、标签、LTV预测等能力。
    被CRM/SOM/ADS等业务域复用。
    """

    @staticmethod
    def segment_customer(profile: CustomerProfile) -> CustomerSegment:
        """
        基于RFM模型自动分群

        规则:
          - VIP: 订单>=10 且 消费>=5000
          - HIGH_VALUE: 订单>=5 且 消费>=2000
          - REGULAR: 订单>=2
          - NEW: 订单=1
          - INACTIVE: 最近订单>180天
          - NORMAL: 其他
        """
        days_since_last = CdpEngine._days_since(profile.last_order_date)
        if days_since_last > 180:
            return CustomerSegment.INACTIVE
        if profile.total_orders >= 10 and profile.total_spent >= 5000:
            return CustomerSegment.VIP
        if profile.total_orders >= 5 and profile.total_spent >= 2000:
            return CustomerSegment.HIGH_VALUE
        if profile.total_orders >= 2:
            return CustomerSegment.REGULAR
        if profile.total_orders == 1:
            return CustomerSegment.NEW
        return CustomerSegment.NORMAL

    @staticmethod
    def calculate_ltv(profile: CustomerProfile) -> float:
        """
        预估客户生命周期价值(LTV)

        公式: LTV = 平均客单价 x 年均购买频次 x 预估留存年数
        """
        if profile.total_orders == 0:
            return 0.0
        avg_order = profile.total_spent / profile.total_orders
        days_active = max(1, CdpEngine._days_since(profile.first_order_date))
        freq_per_year = profile.total_orders / (days_active / 365)
        retention_years = CdpEngine._estimate_retention(profile.segment)
        return round(avg_order * freq_per_year * retention_years, 2)

    @staticmethod
    def generate_tags(profile: CustomerProfile) -> list[str]:
        """根据客户行为自动生成标签"""
        tags = []
        if profile.total_orders >= 5:
            tags.append("高频客户")
        if profile.total_spent >= 10000:
            tags.append("高消费")
        if profile.avg_order_value >= 100:
            tags.append("高客单")
        days_since = CdpEngine._days_since(profile.last_order_date)
        if days_since <= 30:
            tags.append("近期活跃")
        elif days_since >= 180:
            tags.append("流失风险")
        return tags

    @staticmethod
    def _days_since(date_str: str) -> int:
        if not date_str:
            return 999
        try:
            d = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return max(0, (datetime.now(UTC) - d).days)
        except (ValueError, TypeError):
            return 999

    @staticmethod
    def _estimate_retention(segment: str) -> float:
        """按客户分群预估留存年数"""
        retention = {
            "vip": 5.0, "high_value": 3.0, "regular": 2.0,
            "new": 1.5, "normal": 1.0, "inactive": 0.5,
        }
        return retention.get(segment, 1.0)
