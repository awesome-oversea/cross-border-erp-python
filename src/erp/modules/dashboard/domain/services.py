"""
Dashboard 领域服务 - 工作台核心业务规则的纯函数实现

本模块包含 Dashboard 域的纯业务逻辑，不依赖任何基础设施（数据库、缓存等），
所有方法均为无副作用的静态方法，适合单元测试。

主要职责：
1. KPI 趋势计算 - 根据当前值与历史值计算变化率和方向
2. 待办优先级排序 - 按优先级等级对待办事项排序
3. 告警严重度过滤 - 按最低严重度等级筛选告警
4. 时间区间生成 - 生成日/周/月维度的统计区间标签
"""
from __future__ import annotations

from datetime import UTC, datetime


class DashboardDomainService:
    """Dashboard 领域服务 - 提供工作台相关的纯业务规则计算"""

    @staticmethod
    def calculate_kpi_trend(current: float, previous: float) -> dict:
        """
        计算 KPI 趋势指标

        根据当前值与上一周期值计算变化率和趋势方向：
        - change_rate: 变化百分比，保留两位小数
        - direction: 趋势方向，变化率 >5% 为 up，<-5% 为 down，其余为 stable
        - 当 previous 为 0 时：current 也为 0 则变化率为 0%，否则视为 100% 增长

        Args:
            current: 当前周期值
            previous: 上一周期值

        Returns:
            包含 current、previous、change_rate、direction 的字典
        """
        if previous == 0:
            change_rate = 0.0 if current == 0 else 100.0
        else:
            change_rate = round((current - previous) / abs(previous) * 100, 2)

        if change_rate > 5:
            direction = "up"
        elif change_rate < -5:
            direction = "down"
        else:
            direction = "stable"

        return {
            "current": current,
            "previous": previous,
            "change_rate": change_rate,
            "direction": direction,
        }

    @staticmethod
    def prioritize_todos(todos: list[dict]) -> list[dict]:
        """
        按优先级对待办事项排序

        优先级等级从高到低：critical > high > medium > low，
        未识别的优先级默认视为 medium（等级值 2）。

        Args:
            todos: 待办事项列表，每项需包含 "priority" 字段

        Returns:
            按优先级从高到低排序后的列表
        """
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return sorted(todos, key=lambda t: priority_order.get(t.get("priority", "medium"), 2))

    @staticmethod
    def filter_alerts_by_severity(alerts: list[dict], min_severity: str = "medium") -> list[dict]:
        """
        按最低严重度等级过滤告警

        严重度等级从高到低：critical > high > medium > low > info，
        仅保留严重度不低于 min_severity 的告警。

        Args:
            alerts: 告警列表，每项需包含 "severity" 字段
            min_severity: 最低严重度阈值，默认 "medium"

        Returns:
            过滤后的告警列表
        """
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        min_level = severity_order.get(min_severity, 2)
        return [a for a in alerts if severity_order.get(a.get("severity", "info"), 4) <= min_level]

    @staticmethod
    def generate_period_ranges(period_type: str, count: int = 7) -> list[str]:
        """
        生成时间区间标签列表

        根据周期类型生成指定数量的时间标签，从过去到当前排列：
        - daily: 生成 "YYYY-MM-DD" 格式的日期标签
        - weekly: 生成 "YYYY-WWW" 格式的周标签
        - monthly: 生成 "YYYY-MM" 格式的月标签

        Args:
            period_type: 周期类型，支持 "daily"、"weekly"、"monthly"
            count: 生成的区间数量，默认 7

        Returns:
            时间区间标签列表，从最早到最近排列
        """
        now = datetime.now(UTC)
        ranges = []
        for i in range(count - 1, -1, -1):
            if period_type == "daily":
                d = datetime(now.year, now.month, now.day) - __import__("datetime").timedelta(days=i)
                ranges.append(d.strftime("%Y-%m-%d"))
            elif period_type == "weekly":
                d = now - __import__("datetime").timedelta(weeks=i)
                ranges.append(d.strftime("%Y-W%W"))
            elif period_type == "monthly":
                month = now.month - i
                year = now.year
                while month <= 0:
                    month += 12
                    year -= 1
                ranges.append(f"{year}-{month:02d}")
        return ranges
