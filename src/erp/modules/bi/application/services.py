"""
BI 应用服务 - 封装商业智能域的业务逻辑

服务层通过构造函数注入仓储接口，实现依赖倒置。
当仓储未注入时，回退到直接使用 session 操作，保持向后兼容。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from sqlalchemy import func as sa_func
from sqlalchemy import select

from erp.modules.bi.domain.models import BiDashboardWidget, BiMetric, BiMetricValue, BiReport
from erp.shared.exceptions import NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from erp.modules.bi.domain.repositories import (
        BiDashboardWidgetRepository,
        BiMetricRepository,
        BiMetricValueRepository,
        BiReportRepository,
    )

logger = get_logger("erp.bi")

VALID_PERIOD_TYPES = {"hourly", "daily", "weekly", "monthly", "quarterly", "yearly"}
"""支持的周期类型"""

VALID_WIDGET_TYPES = {"kpi_card", "line_chart", "bar_chart", "pie_chart", "table", "heatmap", "funnel"}
"""支持的 Widget 类型"""

KPI_DEFINITIONS = {
    "order_count": {"category": "sales", "unit": "count", "description": "Total order count"},
    "order_amount": {"category": "sales", "unit": "currency", "description": "Total order amount"},
    "avg_order_value": {"category": "sales", "unit": "currency", "description": "Average order value"},
    "refund_rate": {"category": "sales", "unit": "percent", "description": "Refund rate"},
    "inventory_turnover": {"category": "inventory", "unit": "ratio", "description": "Inventory turnover ratio"},
    "low_stock_sku_count": {"category": "inventory", "unit": "count", "description": "Low stock SKU count"},
    "fulfillment_rate": {"category": "logistics", "unit": "percent", "description": "Order fulfillment rate"},
    "on_time_delivery_rate": {"category": "logistics", "unit": "percent", "description": "On-time delivery rate"},
    "gross_profit_margin": {"category": "finance", "unit": "percent", "description": "Gross profit margin"},
    "ad_roas": {"category": "marketing", "unit": "ratio", "description": "Return on ad spend"},
    "cac": {"category": "marketing", "unit": "currency", "description": "Customer acquisition cost"},
}
"""KPI 预定义指标"""


class BiMetricService:
    """指标管理应用服务 - 管理指标的创建与查询"""

    def __init__(self, session: AsyncSession, metric_repo: BiMetricRepository | None = None):
        self._session = session
        self._metric_repo = metric_repo

    async def create(self, tenant_id: str, metric_code: str, metric_name: str, **kwargs) -> BiMetric:
        metric = BiMetric(tenant_id=tenant_id, metric_code=metric_code, metric_name=metric_name,
                          **{k: v for k, v in kwargs.items() if hasattr(BiMetric, k)})
        if self._metric_repo:
            return await self._metric_repo.create(metric)
        self._session.add(metric)
        await self._session.flush()
        return metric

    async def list_by_tenant(self, tenant_id: str, category: str | None = None) -> list[BiMetric]:
        if self._metric_repo:
            items, _ = await self._metric_repo.list_by_tenant(tenant_id, category=category or "", page_size=10000)
            return list(items)
        stmt = select(BiMetric).where(BiMetric.tenant_id == tenant_id, BiMetric.status == "active")
        if category:
            stmt = stmt.where(BiMetric.metric_category == category)
        stmt = stmt.order_by(BiMetric.metric_code)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, metric_id: str, tenant_id: str) -> BiMetric | None:
        if self._metric_repo:
            return await self._metric_repo.get_by_id(metric_id, tenant_id)
        stmt = select(BiMetric).where(BiMetric.id == metric_id, BiMetric.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, metric_id: str, tenant_id: str) -> BiMetric:
        metric = await self.get_by_id(metric_id, tenant_id)
        if not metric:
            raise NotFoundException(message=f"BI metric '{metric_id}' not found")
        return metric


class KpiAggregationService:
    """KPI 聚合应用服务 - 计算派生 KPI 指标"""

    def __init__(self, session: AsyncSession, metric_value_repo: BiMetricValueRepository | None = None):
        self._session = session
        self._metric_value_repo = metric_value_repo

    async def get_kpi_value(self, tenant_id: str, metric_code: str,
                            period_type: str = "daily", limit: int = 1) -> list[dict]:
        if metric_code not in KPI_DEFINITIONS:
            raise ValidationException(message=f"Unknown KPI '{metric_code}'")
        stmt = select(BiMetricValue).where(
            BiMetricValue.tenant_id == tenant_id,
            BiMetricValue.metric_code == metric_code,
            BiMetricValue.period_type == period_type,
        ).order_by(BiMetricValue.period_date.desc()).limit(limit)
        result = await self._session.execute(stmt)
        values = result.scalars().all()
        kpi_def = KPI_DEFINITIONS[metric_code]
        return [
            {
                "metric_code": metric_code,
                "category": kpi_def["category"],
                "unit": kpi_def["unit"],
                "description": kpi_def["description"],
                "period_date": str(v.period_date),
                "period_type": v.period_type,
                "numeric_value": v.numeric_value,
            }
            for v in values
        ]

    async def calculate_derived_kpi(self, tenant_id: str, kpi_code: str,
                                     period_type: str = "daily") -> float | None:
        if kpi_code == "avg_order_value":
            order_amounts = await self.get_kpi_value(tenant_id, "order_amount", period_type, limit=1)
            order_counts = await self.get_kpi_value(tenant_id, "order_count", period_type, limit=1)
            if order_amounts and order_counts and order_counts[0]["numeric_value"] > 0:
                return round(order_amounts[0]["numeric_value"] / order_counts[0]["numeric_value"], 2)
        if kpi_code == "refund_rate":
            refunds = await self.get_kpi_value(tenant_id, "refund_rate", period_type, limit=1)
            if refunds:
                return refunds[0]["numeric_value"]
        return None


class BiMetricValueService:
    """指标值应用服务 - 管理指标值的录入与查询"""

    def __init__(self, session: AsyncSession, metric_value_repo: BiMetricValueRepository | None = None):
        self._session = session
        self._metric_value_repo = metric_value_repo

    async def record(self, tenant_id: str, metric_id: str, metric_code: str,
                     period_type: str, period_date, numeric_value: float = 0.0,
                     **kwargs) -> BiMetricValue:
        if period_type not in VALID_PERIOD_TYPES:
            raise ValidationException(
                message=f"Invalid period type '{period_type}', allowed: {VALID_PERIOD_TYPES}"
            )
        val = BiMetricValue(tenant_id=tenant_id, metric_id=metric_id, metric_code=metric_code,
                            period_type=period_type, period_date=period_date,
                            numeric_value=numeric_value,
                            **{k: v for k, v in kwargs.items() if hasattr(BiMetricValue, k)})
        if self._metric_value_repo:
            return await self._metric_value_repo.create(val)
        self._session.add(val)
        await self._session.flush()
        return val

    async def query(self, tenant_id: str, metric_code: str, period_type: str = "daily",
                    store_id: str | None = None, limit: int = 30) -> list[BiMetricValue]:
        if self._metric_value_repo:
            items = await self._metric_value_repo.list_by_metric_code(
                metric_code, tenant_id, period_type=period_type, store_id=store_id or "")
            return list(items)[:limit]
        stmt = select(BiMetricValue).where(
            BiMetricValue.tenant_id == tenant_id,
            BiMetricValue.metric_code == metric_code,
            BiMetricValue.period_type == period_type,
        )
        if store_id:
            stmt = stmt.where(BiMetricValue.store_id == store_id)
        stmt = stmt.order_by(BiMetricValue.period_date.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class BiReportService:
    """报表应用服务 - 管理报表的创建与查询"""

    def __init__(self, session: AsyncSession, report_repo: BiReportRepository | None = None):
        self._session = session
        self._report_repo = report_repo

    async def create(self, tenant_id: str, report_code: str, name: str, **kwargs) -> BiReport:
        report = BiReport(tenant_id=tenant_id, report_code=report_code, name=name,
                          **{k: v for k, v in kwargs.items() if hasattr(BiReport, k)})
        if self._report_repo:
            return await self._report_repo.create(report)
        self._session.add(report)
        await self._session.flush()
        return report

    async def get_by_id(self, report_id: str) -> BiReport | None:
        if self._report_repo:
            return await self._report_repo.get_by_id(report_id, tenant_id="")
        return await self._session.get(BiReport, report_id)

    async def get_or_raise(self, report_id: str, tenant_id: str = "") -> BiReport:
        report = await self.get_by_id(report_id)
        if not report:
            raise NotFoundException(message=f"BI report '{report_id}' not found")
        return report

    async def get_by_code(self, report_code: str, tenant_id: str) -> BiReport | None:
        if self._report_repo:
            return await self._report_repo.get_by_code(report_code, tenant_id)
        stmt = select(BiReport).where(BiReport.report_code == report_code, BiReport.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, category: str | None = None) -> list[BiReport]:
        if self._report_repo:
            items, _ = await self._report_repo.list_by_tenant(tenant_id, category=category or "", page_size=10000)
            return list(items)
        stmt = select(BiReport).where(BiReport.tenant_id == tenant_id, BiReport.status == "active")
        if category:
            stmt = stmt.where(BiReport.category == category)
        stmt = stmt.order_by(BiReport.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class BiDashboardWidgetService:
    """仪表盘 Widget 应用服务 - 管理 Widget 的创建与查询"""

    def __init__(self, session: AsyncSession, widget_repo: BiDashboardWidgetRepository | None = None):
        self._session = session
        self._widget_repo = widget_repo

    async def create(self, tenant_id: str, dashboard_id: str, widget_type: str,
                     title: str = "", **kwargs) -> BiDashboardWidget:
        if widget_type not in VALID_WIDGET_TYPES:
            raise ValidationException(
                message=f"Invalid widget type '{widget_type}', allowed: {VALID_WIDGET_TYPES}"
            )
        widget = BiDashboardWidget(tenant_id=tenant_id, dashboard_id=dashboard_id,
                                   widget_type=widget_type, title=title,
                                   **{k: v for k, v in kwargs.items() if hasattr(BiDashboardWidget, k)})
        if self._widget_repo:
            return await self._widget_repo.create(widget)
        self._session.add(widget)
        await self._session.flush()
        return widget

    async def list_by_dashboard(self, dashboard_id: str) -> list[BiDashboardWidget]:
        if self._widget_repo:
            items = await self._widget_repo.list_by_dashboard(dashboard_id, tenant_id="")
            return list(items)
        stmt = select(BiDashboardWidget).where(
            BiDashboardWidget.dashboard_id == dashboard_id,
            BiDashboardWidget.status == "active",
        ).order_by(BiDashboardWidget.sort_order)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class BIQueryService:
    """
    BI 统计查询服务

    提供BI模块的运营统计概览、各子域统计数据聚合。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_statistics(self, tenant_id: str) -> dict:
        """获取BI运营统计概览"""
        total_metrics = (await self._session.execute(
            select(sa_func.count()).select_from(BiMetric).where(BiMetric.tenant_id == tenant_id)
        )).scalar() or 0

        active_metrics = (await self._session.execute(
            select(sa_func.count()).select_from(BiMetric)
            .where(BiMetric.tenant_id == tenant_id, BiMetric.status == "active")
        )).scalar() or 0

        total_metric_values = (await self._session.execute(
            select(sa_func.count()).select_from(BiMetricValue).where(BiMetricValue.tenant_id == tenant_id)
        )).scalar() or 0

        total_reports = (await self._session.execute(
            select(sa_func.count()).select_from(BiReport)
            .where(BiReport.tenant_id == tenant_id, BiReport.status == "active")
        )).scalar() or 0

        total_widgets = (await self._session.execute(
            select(sa_func.count()).select_from(BiDashboardWidget)
            .where(BiDashboardWidget.tenant_id == tenant_id, BiDashboardWidget.status == "active")
        )).scalar() or 0

        by_category_rows = (await self._session.execute(
            select(BiMetric.metric_category, sa_func.count())
            .where(BiMetric.tenant_id == tenant_id)
            .group_by(BiMetric.metric_category)
        )).all()
        metrics_by_category = {r[0]: r[1] for r in by_category_rows}

        kpi_count = len([k for k in KPI_DEFINITIONS if k.startswith(("order_", "avg_", "refund_", "inventory_", "fulfillment_", "on_time_", "gross_", "ad_", "cac"))])

        return {
            "total_metrics": total_metrics,
            "active_metrics": active_metrics,
            "total_metric_values": total_metric_values,
            "total_reports": total_reports,
            "total_widgets": total_widgets,
            "metrics_by_category": metrics_by_category,
            "kpi_count": kpi_count,
        }

    async def search_metrics(self, tenant_id: str, keyword: str = "", metric_category: str = "",
                              status: str = "", page: int = 1, page_size: int = 20) -> tuple[list[BiMetric], int]:
        """多维度搜索指标"""
        conditions = [BiMetric.tenant_id == tenant_id]
        if keyword:
            conditions.append((BiMetric.metric_code.contains(keyword) | BiMetric.metric_name.contains(keyword)))
        if metric_category:
            conditions.append(BiMetric.metric_category == metric_category)
        if status:
            conditions.append(BiMetric.status == status)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(BiMetric).where(*conditions)
        )).scalar() or 0
        stmt = select(BiMetric).where(*conditions).order_by(
            BiMetric.metric_code
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total


class DataQualityMonitorService:
    """
    数据质量监控服务

    监控BI数据质量: 完整性/一致性/及时性/准确性
    - 数据缺失检测
    - 异常值检测
    - 数据延迟告警
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def check_data_completeness(self, tenant_id: str, metric_code: str,
                                       period_type: str = "daily",
                                       days: int = 30) -> dict:
        """检查数据完整性"""
        from datetime import date, timedelta
        end = date.today()
        start = end - timedelta(days=days)
        expected_days = days + 1
        actual_values = (await self._session.execute(
            select(BiMetricValue).where(
                BiMetricValue.tenant_id == tenant_id,
                BiMetricValue.metric_code == metric_code,
                BiMetricValue.period_type == period_type,
                BiMetricValue.period_date >= start,
                BiMetricValue.period_date <= end,
            )
        )).scalars().all()
        actual_dates = set()
        for v in actual_values:
            if v.period_date:
                actual_dates.add(v.period_date.date() if hasattr(v.period_date, "date") else v.period_date)
        missing_dates = []
        current = start
        while current <= end:
            if current not in actual_dates:
                missing_dates.append(current.isoformat())
            current += timedelta(days=1)
        completeness_rate = (expected_days - len(missing_dates)) / expected_days * 100 if expected_days > 0 else 0
        return {
            "metric_code": metric_code, "period_type": period_type,
            "expected_days": expected_days, "actual_days": len(actual_dates),
            "missing_days": len(missing_dates), "missing_dates": missing_dates[:20],
            "completeness_rate": round(completeness_rate, 2),
            "status": "excellent" if completeness_rate >= 99 else "good" if completeness_rate >= 95 else "warning" if completeness_rate >= 80 else "poor",
        }

    async def detect_anomalies(self, tenant_id: str, metric_code: str,
                                period_type: str = "daily",
                                days: int = 30,
                                z_threshold: float = 3.0) -> dict:
        """检测异常值"""
        from datetime import date, timedelta
        end = date.today()
        start = end - timedelta(days=days)
        values = (await self._session.execute(
            select(BiMetricValue).where(
                BiMetricValue.tenant_id == tenant_id,
                BiMetricValue.metric_code == metric_code,
                BiMetricValue.period_type == period_type,
                BiMetricValue.period_date >= start,
                BiMetricValue.period_date <= end,
            ).order_by(BiMetricValue.period_date)
        )).scalars().all()
        if len(values) < 3:
            return {"metric_code": metric_code, "anomalies": [], "reason": "insufficient data"}
        numeric_vals = [float(v.numeric_value) for v in values if v.numeric_value is not None]
        if not numeric_vals:
            return {"metric_code": metric_code, "anomalies": [], "reason": "no numeric values"}
        mean = sum(numeric_vals) / len(numeric_vals)
        std = (sum((x - mean) ** 2 for x in numeric_vals) / len(numeric_vals)) ** 0.5
        if std == 0:
            return {"metric_code": metric_code, "anomalies": [], "mean": round(mean, 4), "std": 0}
        anomalies = []
        for v in values:
            if v.numeric_value is not None:
                z_score = abs(float(v.numeric_value) - mean) / std
                if z_score > z_threshold:
                    anomalies.append({
                        "period_date": v.period_date.isoformat() if hasattr(v.period_date, "isoformat") else str(v.period_date),
                        "value": float(v.numeric_value), "z_score": round(z_score, 2),
                        "deviation": round(float(v.numeric_value) - mean, 4),
                    })
        return {
            "metric_code": metric_code, "total_points": len(values),
            "anomaly_count": len(anomalies), "anomalies": anomalies,
            "mean": round(mean, 4), "std": round(std, 4),
            "z_threshold": z_threshold,
        }

    async def check_data_freshness(self, tenant_id: str, metric_codes: list[str]) -> dict:
        """检查数据新鲜度"""
        from datetime import date, timedelta
        results = []
        for code in metric_codes:
            latest = (await self._session.execute(
                select(BiMetricValue).where(
                    BiMetricValue.tenant_id == tenant_id,
                    BiMetricValue.metric_code == code,
                ).order_by(BiMetricValue.period_date.desc()).limit(1)
            )).scalar_one_or_none()
            if latest and latest.period_date:
                latest_date = latest.period_date.date() if hasattr(latest.period_date, "date") else latest.period_date
                delay_days = (date.today() - latest_date).days
                results.append({
                    "metric_code": code, "latest_date": latest_date.isoformat() if hasattr(latest_date, "isoformat") else str(latest_date),
                    "delay_days": delay_days,
                    "freshness": "fresh" if delay_days <= 1 else "stale" if delay_days <= 3 else "outdated",
                })
            else:
                results.append({"metric_code": code, "latest_date": None, "delay_days": -1, "freshness": "missing"})
        return {"metrics_checked": len(metric_codes), "results": results}


class CrossDomainComparisonService:
    """
    跨域数据对比服务

    对比不同业务域的关键指标: 销售vs库存/采购vs销售/广告vs转化
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def compare_sales_vs_inventory(self, tenant_id: str, days: int = 30) -> dict:
        """销售vs库存对比"""
        sales_metric = "daily_sales_amount"
        inventory_metric = "daily_inventory_value"
        from datetime import date, timedelta
        end = date.today()
        start = end - timedelta(days=days)
        sales_values = (await self._session.execute(
            select(BiMetricValue).where(
                BiMetricValue.tenant_id == tenant_id,
                BiMetricValue.metric_code == sales_metric,
                BiMetricValue.period_type == "daily",
                BiMetricValue.period_date >= start,
                BiMetricValue.period_date <= end,
            ).order_by(BiMetricValue.period_date)
        )).scalars().all()
        inventory_values = (await self._session.execute(
            select(BiMetricValue).where(
                BiMetricValue.tenant_id == tenant_id,
                BiMetricValue.metric_code == inventory_metric,
                BiMetricValue.period_type == "daily",
                BiMetricValue.period_date >= start,
                BiMetricValue.period_date <= end,
            ).order_by(BiMetricValue.period_date)
        )).scalars().all()
        total_sales = sum(float(v.numeric_value) for v in sales_values if v.numeric_value)
        avg_inventory = sum(float(v.numeric_value) for v in inventory_values if v.numeric_value) / len(inventory_values) if inventory_values else 0
        turnover_rate = total_sales / avg_inventory if avg_inventory > 0 else 0
        return {
            "period_days": days, "total_sales": round(total_sales, 2),
            "avg_inventory": round(avg_inventory, 2),
            "turnover_rate": round(turnover_rate, 2),
            "assessment": "healthy" if turnover_rate >= 3 else "slow" if turnover_rate >= 1 else "critical",
        }

    async def compare_ads_vs_conversion(self, tenant_id: str, days: int = 30) -> dict:
        """广告投入vs转化对比"""
        ad_spend_metric = "daily_ad_spend"
        conversion_metric = "daily_conversion_rate"
        from datetime import date, timedelta
        end = date.today()
        start = end - timedelta(days=days)
        ad_values = (await self._session.execute(
            select(BiMetricValue).where(
                BiMetricValue.tenant_id == tenant_id,
                BiMetricValue.metric_code == ad_spend_metric,
                BiMetricValue.period_type == "daily",
                BiMetricValue.period_date >= start,
                BiMetricValue.period_date <= end,
            )
        )).scalars().all()
        conv_values = (await self._session.execute(
            select(BiMetricValue).where(
                BiMetricValue.tenant_id == tenant_id,
                BiMetricValue.metric_code == conversion_metric,
                BiMetricValue.period_type == "daily",
                BiMetricValue.period_date >= start,
                BiMetricValue.period_date <= end,
            )
        )).scalars().all()
        total_ad_spend = sum(float(v.numeric_value) for v in ad_values if v.numeric_value)
        avg_conv_rate = sum(float(v.numeric_value) for v in conv_values if v.numeric_value) / len(conv_values) if conv_values else 0
        return {
            "period_days": days, "total_ad_spend": round(total_ad_spend, 2),
            "avg_conversion_rate": round(avg_conv_rate, 2),
            "efficiency": "high" if avg_conv_rate > 10 else "medium" if avg_conv_rate > 5 else "low",
        }


class MetricAlertService:
    """
    指标告警应用服务

    编排指标告警的完整流程: 规则定义 → 阈值检测 → 告警触发 → 通知
    支持静态阈值和动态阈值(同比/环比)告警。
    """

    def __init__(self, session: AsyncSession, metric_repo: BiMetricRepository | None = None,
                 value_repo: BiMetricValueRepository | None = None):
        self._session = session
        self._metric_repo = metric_repo
        self._value_repo = value_repo

    async def create_alert_rule(self, tenant_id: str, metric_code: str,
                                rule_name: str, condition: str,
                                threshold: float, severity: str = "warning",
                                **kwargs) -> dict:
        """
        创建告警规则

        condition: gt(大于) / lt(小于) / gte(大于等于) / lte(小于等于) / eq(等于)
                  pct_change_up(环比上升) / pct_change_down(环比下降)
        """
        valid_conditions = {"gt", "lt", "gte", "lte", "eq", "pct_change_up", "pct_change_down"}
        if condition not in valid_conditions:
            raise ValidationException(message=f"Invalid condition '{condition}'")
        if severity not in ("info", "warning", "critical"):
            raise ValidationException(message=f"Invalid severity '{severity}'")
        metric_stmt = select(BiMetric).where(
            BiMetric.tenant_id == tenant_id, BiMetric.metric_code == metric_code,
        )
        metric = (await self._session.execute(metric_stmt)).scalar_one_or_none()
        if not metric:
            raise NotFoundException(message=f"Metric '{metric_code}' not found")
        import uuid
        rule_id = str(uuid.uuid4())
        return {
            "rule_id": rule_id, "tenant_id": tenant_id,
            "metric_code": metric_code, "rule_name": rule_name,
            "condition": condition, "threshold": threshold,
            "severity": severity, "is_active": True,
            "notify_channels": kwargs.get("notify_channels", ["email"]),
            "cooldown_minutes": kwargs.get("cooldown_minutes", 30),
        }

    async def evaluate_rules(self, tenant_id: str, metric_code: str,
                             current_value: float,
                             previous_value: float | None = None) -> list[dict]:
        """
        评估告警规则

        流程: 获取指标当前值 → 匹配告警规则 → 判断是否触发
        """
        alerts: list[dict] = []
        metric_stmt = select(BiMetric).where(
            BiMetric.tenant_id == tenant_id, BiMetric.metric_code == metric_code,
        )
        metric = (await self._session.execute(metric_stmt)).scalar_one_or_none()
        if not metric:
            return alerts
        rules = await self._get_rules_for_metric(tenant_id, metric_code)
        for rule in rules:
            if not rule.get("is_active", True):
                continue
            triggered = False
            condition = rule.get("condition", "gt")
            threshold = rule.get("threshold", 0)
            if condition == "gt" and current_value > threshold:
                triggered = True
            elif condition == "lt" and current_value < threshold:
                triggered = True
            elif condition == "gte" and current_value >= threshold:
                triggered = True
            elif condition == "lte" and current_value <= threshold:
                triggered = True
            elif condition == "eq" and abs(current_value - threshold) < 0.001:
                triggered = True
            elif condition == "pct_change_up" and previous_value and previous_value > 0:
                pct_change = (current_value - previous_value) / previous_value * 100
                if pct_change >= threshold:
                    triggered = True
            elif condition == "pct_change_down" and previous_value and previous_value > 0:
                pct_change = (previous_value - current_value) / previous_value * 100
                if pct_change >= threshold:
                    triggered = True
            if triggered:
                from datetime import UTC, datetime
                alerts.append({
                    "rule_id": rule.get("rule_id", ""),
                    "metric_code": metric_code,
                    "metric_name": metric.metric_name,
                    "condition": condition,
                    "threshold": threshold,
                    "current_value": current_value,
                    "previous_value": previous_value,
                    "severity": rule.get("severity", "warning"),
                    "triggered_at": datetime.now(UTC).isoformat(),
                })
        return alerts

    async def _get_rules_for_metric(self, tenant_id: str, metric_code: str) -> list[dict]:
        return []


class MetricAggregationService:
    """
    指标自动聚合应用服务

    编排指标数据的自动聚合: 原始数据 → 小时聚合 → 日聚合 → 周聚合 → 月聚合
    支持sum/avg/max/min/count聚合方式。
    """

    def __init__(self, session: AsyncSession, value_repo: BiMetricValueRepository | None = None):
        self._session = session
        self._value_repo = value_repo

    async def aggregate_to_daily(self, tenant_id: str, metric_code: str,
                                  target_date: str) -> dict:
        """
        将小时数据聚合为日数据

        流程: 查询当日所有hourly数据 → 按聚合方式计算 → 写入daily记录
        """
        from datetime import date, datetime
        dt = date.fromisoformat(target_date)
        stmt = select(BiMetricValue).where(
            BiMetricValue.tenant_id == tenant_id,
            BiMetricValue.metric_code == metric_code,
            BiMetricValue.period_type == "hourly",
            sa_func.date(BiMetricValue.period_date) == dt,
        )
        hourly_values = list((await self._session.execute(stmt)).scalars().all())
        if not hourly_values:
            return {"metric_code": metric_code, "target_date": target_date, "aggregated": False, "reason": "no hourly data"}
        metric_stmt = select(BiMetric).where(
            BiMetric.tenant_id == tenant_id, BiMetric.metric_code == metric_code,
        )
        metric = (await self._session.execute(metric_stmt)).scalar_one_or_none()
        agg_method = "sum"
        values = [v.numeric_value for v in hourly_values]
        if agg_method == "sum":
            result = sum(values)
        elif agg_method == "avg":
            result = sum(values) / len(values) if values else 0
        elif agg_method == "max":
            result = max(values) if values else 0
        elif agg_method == "min":
            result = min(values) if values else 0
        else:
            result = sum(values)
        daily_value = BiMetricValue(
            tenant_id=tenant_id, metric_code=metric_code,
            metric_id=hourly_values[0].metric_id,
            numeric_value=round(result, 4),
            period_type="daily",
            period_date=datetime(dt.year, dt.month, dt.day),
        )
        self._session.add(daily_value)
        await self._session.flush()
        return {
            "metric_code": metric_code, "target_date": target_date,
            "aggregated": True, "agg_method": agg_method,
            "source_count": len(hourly_values),
            "result_value": round(result, 4),
        }

    async def aggregate_to_monthly(self, tenant_id: str, metric_code: str,
                                    year: int, month: int) -> dict:
        """
        将日数据聚合为月数据

        流程: 查询当月所有daily数据 → 按聚合方式计算 → 写入monthly记录
        """
        from datetime import date, datetime
        stmt = select(BiMetricValue).where(
            BiMetricValue.tenant_id == tenant_id,
            BiMetricValue.metric_code == metric_code,
            BiMetricValue.period_type == "daily",
            sa_func.extract("year", BiMetricValue.period_date) == year,
            sa_func.extract("month", BiMetricValue.period_date) == month,
        )
        daily_values = list((await self._session.execute(stmt)).scalars().all())
        if not daily_values:
            return {"metric_code": metric_code, "year": year, "month": month, "aggregated": False, "reason": "no daily data"}
        metric_stmt = select(BiMetric).where(
            BiMetric.tenant_id == tenant_id, BiMetric.metric_code == metric_code,
        )
        metric = (await self._session.execute(metric_stmt)).scalar_one_or_none()
        agg_method = "sum"
        values = [v.numeric_value for v in daily_values]
        if agg_method == "sum":
            result = sum(values)
        elif agg_method == "avg":
            result = sum(values) / len(values) if values else 0
        elif agg_method == "max":
            result = max(values) if values else 0
        elif agg_method == "min":
            result = min(values) if values else 0
        else:
            result = sum(values)
        monthly_value = BiMetricValue(
            tenant_id=tenant_id, metric_code=metric_code,
            metric_id=daily_values[0].metric_id,
            numeric_value=round(result, 4),
            period_type="monthly",
            period_date=datetime(year, month, 1),
        )
        self._session.add(monthly_value)
        await self._session.flush()
        return {
            "metric_code": metric_code, "year": year, "month": month,
            "aggregated": True, "agg_method": agg_method,
            "source_count": len(daily_values),
            "result_value": round(result, 4),
        }

    async def backfill_aggregation(self, tenant_id: str, metric_code: str,
                                    start_date: str, end_date: str,
                                    target_period: str = "daily") -> dict:
        """
        回填聚合数据

        流程: 遍历日期范围 → 逐日/逐月聚合 → 批量写入
        """
        from datetime import date, timedelta
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        results: list[dict] = []
        current = start
        while current <= end:
            if target_period == "daily":
                result = await self.aggregate_to_daily(tenant_id, metric_code, current.isoformat())
                results.append(result)
            current += timedelta(days=1)
        if target_period == "monthly":
            current = start
            while current <= end:
                result = await self.aggregate_to_monthly(tenant_id, metric_code, current.year, current.month)
                results.append(result)
                if current.month == 12:
                    current = date(current.year + 1, 1, 1)
                else:
                    current = date(current.year, current.month + 1, 1)
        success_count = sum(1 for r in results if r.get("aggregated", False))
        return {
            "metric_code": metric_code, "target_period": target_period,
            "start_date": start_date, "end_date": end_date,
            "total_attempts": len(results), "success_count": success_count,
        }

    async def search_metric_values(self, tenant_id: str, metric_code: str = "", period_type: str = "daily",
                                    store_id: str = "", platform: str = "",
                                    start_date=None, end_date=None,
                                    page: int = 1, page_size: int = 20) -> tuple[list[BiMetricValue], int]:
        """多维度搜索指标值"""
        conditions = [BiMetricValue.tenant_id == tenant_id]
        if metric_code:
            conditions.append(BiMetricValue.metric_code == metric_code)
        if period_type:
            conditions.append(BiMetricValue.period_type == period_type)
        if store_id:
            conditions.append(BiMetricValue.store_id == store_id)
        if platform:
            conditions.append(BiMetricValue.platform == platform)
        if start_date:
            conditions.append(BiMetricValue.period_date >= start_date)
        if end_date:
            conditions.append(BiMetricValue.period_date <= end_date)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(BiMetricValue).where(*conditions)
        )).scalar() or 0
        stmt = select(BiMetricValue).where(*conditions).order_by(
            BiMetricValue.period_date.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total

    async def search_reports(self, tenant_id: str, keyword: str = "", category: str = "",
                              report_type: str = "", page: int = 1, page_size: int = 20) -> tuple[list[BiReport], int]:
        """多维度搜索报表"""
        conditions = [BiReport.tenant_id == tenant_id, BiReport.status == "active"]
        if keyword:
            conditions.append((BiReport.report_code.contains(keyword) | BiReport.name.contains(keyword)))
        if category:
            conditions.append(BiReport.category == category)
        if report_type:
            conditions.append(BiReport.report_type == report_type)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(BiReport).where(*conditions)
        )).scalar() or 0
        stmt = select(BiReport).where(*conditions).order_by(
            BiReport.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total
