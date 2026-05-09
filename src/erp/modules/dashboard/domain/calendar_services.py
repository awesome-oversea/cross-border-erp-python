"""
电子日历服务 (P3-004)

支持多类型日历事件: 运营日历/任务日历/促销日历/备货日历
所有方法为无状态纯函数，不依赖基础设施层。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta


class CalendarService:
    """电子日历领域服务: 运营日历/任务日历/促销日历/备货日历"""
    """电子日历领域服务"""

    EVENT_TYPES = {"operation", "task", "promotion", "restock", "review"}
    EVENT_STATUSES = {"draft", "confirmed", "completed", "cancelled"}

    @staticmethod
    def validate(event: dict) -> list[str]:
        errors = []
        if not event.get("title"): errors.append("事件标题不能为空")
        if event.get("event_type") not in CalendarService.EVENT_TYPES:
            errors.append(f"事件类型不合法: {event.get('event_type')}")
        if event.get("start_time") and event.get("end_time"):
            if event["start_time"] >= event["end_time"]:
                errors.append("结束时间必须晚于开始时间")
        return errors

    @staticmethod
    def check_conflict(existing: list[dict], start: str, end: str) -> list[dict]:
        conflicts = []
        for e in existing:
            es, ee = e.get("start_time"), e.get("end_time")
            if es and ee and start < ee and end > es:
                conflicts.append(e)
        return conflicts

    @staticmethod
    def generate_recurring_dates(start_date: str, pattern: str, count: int = 10) -> list[str]:
        """生成重复事件日期"""
        try:
            base = datetime.fromisoformat(start_date) if isinstance(start_date, str) else start_date
        except: return [start_date]
        dates = []
        for i in range(count):
            if pattern == "daily": d = base + timedelta(days=i)
            elif pattern == "weekly": d = base + timedelta(weeks=i)
            elif pattern == "biweekly": d = base + timedelta(weeks=i*2)
            elif pattern == "monthly": d = base + timedelta(days=30*i)
            else: d = base + timedelta(days=i)
            dates.append(d.isoformat())
        return dates

    @staticmethod
    def categorize_by_domain(event_type: str) -> str:
        domain_map = {
            "operation": "som", "task": "dashboard",
            "promotion": "oms", "restock": "scm", "review": "crm",
        }
        return domain_map.get(event_type, "dashboard")
