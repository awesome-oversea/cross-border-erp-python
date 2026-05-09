from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.bi.domain.models import BiDashboardWidget, BiMetric, BiMetricValue, BiReport
from erp.modules.bi.domain.repositories import (
    BiDashboardWidgetRepository,
    BiMetricRepository,
    BiMetricValueRepository,
    BiReportRepository,
)


class SqlBiMetricRepository(BiMetricRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, metric_id: str, tenant_id: str) -> BiMetric | None:
        stmt = select(BiMetric).where(BiMetric.id == metric_id, BiMetric.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, metric_code: str, tenant_id: str) -> BiMetric | None:
        stmt = select(BiMetric).where(BiMetric.metric_code == metric_code, BiMetric.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, category: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[BiMetric], int]:
        conditions = [BiMetric.tenant_id == tenant_id]
        if category:
            conditions.append(BiMetric.metric_category == category)
        total = (await self._session.execute(select(func.count()).select_from(BiMetric).where(*conditions))).scalar() or 0
        stmt = select(BiMetric).where(*conditions).order_by(BiMetric.metric_code).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, metric: BiMetric) -> BiMetric:
        self._session.add(metric)
        await self._session.flush()
        return metric

    async def update(self, metric: BiMetric) -> BiMetric:
        await self._session.flush()
        return metric


class SqlBiMetricValueRepository(BiMetricValueRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_metric(self, metric_id: str, tenant_id: str, period_type: str = "",
                             start_date: datetime | None = None, end_date: datetime | None = None) -> Sequence[BiMetricValue]:
        conditions = [BiMetricValue.metric_id == metric_id, BiMetricValue.tenant_id == tenant_id]
        if period_type:
            conditions.append(BiMetricValue.period_type == period_type)
        if start_date:
            conditions.append(BiMetricValue.period_date >= start_date)
        if end_date:
            conditions.append(BiMetricValue.period_date <= end_date)
        stmt = select(BiMetricValue).where(*conditions).order_by(BiMetricValue.period_date)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_metric_code(self, metric_code: str, tenant_id: str, period_type: str = "",
                                  start_date: datetime | None = None, end_date: datetime | None = None,
                                  store_id: str = "", platform: str = "") -> Sequence[BiMetricValue]:
        conditions = [BiMetricValue.metric_code == metric_code, BiMetricValue.tenant_id == tenant_id]
        if period_type:
            conditions.append(BiMetricValue.period_type == period_type)
        if start_date:
            conditions.append(BiMetricValue.period_date >= start_date)
        if end_date:
            conditions.append(BiMetricValue.period_date <= end_date)
        if store_id:
            conditions.append(BiMetricValue.store_id == store_id)
        if platform:
            conditions.append(BiMetricValue.platform == platform)
        stmt = select(BiMetricValue).where(*conditions).order_by(BiMetricValue.period_date)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, value: BiMetricValue) -> BiMetricValue:
        self._session.add(value)
        await self._session.flush()
        return value


class SqlBiReportRepository(BiReportRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, report_id: str, tenant_id: str) -> BiReport | None:
        stmt = select(BiReport).where(BiReport.id == report_id, BiReport.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, report_code: str, tenant_id: str) -> BiReport | None:
        stmt = select(BiReport).where(BiReport.report_code == report_code, BiReport.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, category: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[BiReport], int]:
        conditions = [BiReport.tenant_id == tenant_id]
        if category:
            conditions.append(BiReport.category == category)
        total = (await self._session.execute(select(func.count()).select_from(BiReport).where(*conditions))).scalar() or 0
        stmt = select(BiReport).where(*conditions).order_by(BiReport.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, report: BiReport) -> BiReport:
        self._session.add(report)
        await self._session.flush()
        return report

    async def update(self, report: BiReport) -> BiReport:
        await self._session.flush()
        return report


class SqlBiDashboardWidgetRepository(BiDashboardWidgetRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_dashboard(self, dashboard_id: str, tenant_id: str) -> Sequence[BiDashboardWidget]:
        stmt = select(BiDashboardWidget).where(BiDashboardWidget.dashboard_id == dashboard_id, BiDashboardWidget.tenant_id == tenant_id).order_by(BiDashboardWidget.sort_order)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, widget: BiDashboardWidget) -> BiDashboardWidget:
        self._session.add(widget)
        await self._session.flush()
        return widget

    async def update(self, widget: BiDashboardWidget) -> BiDashboardWidget:
        await self._session.flush()
        return widget

    async def delete(self, widget_id: str, tenant_id: str) -> bool:
        stmt = sa_delete(BiDashboardWidget).where(BiDashboardWidget.id == widget_id, BiDashboardWidget.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0
