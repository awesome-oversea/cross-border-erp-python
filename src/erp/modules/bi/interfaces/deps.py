"""
BI 模块依赖注入工厂 - 提供所有应用服务的 FastAPI Depends 工厂函数

本模块将仓储接口的创建与服务的组装集中管理，
路由层通过 Depends(get_xxx_service) 获取已注入仓储的服务实例，
实现控制反转（IoC）和依赖倒置（DIP）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends

from erp.modules.bi.application.services import (
    BIQueryService,
    BiDashboardWidgetService,
    BiMetricService,
    BiMetricValueService,
    BiReportService,
    KpiAggregationService,
)
from erp.modules.bi.domain.repositories import (
    BiDashboardWidgetRepository,
    BiMetricRepository,
    BiMetricValueRepository,
    BiReportRepository,
)
from erp.modules.bi.infrastructure.repositories import (
    SqlBiDashboardWidgetRepository,
    SqlBiMetricRepository,
    SqlBiMetricValueRepository,
    SqlBiReportRepository,
)
from erp.shared.db.session import get_db_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _get_metric_repo(session: AsyncSession) -> BiMetricRepository:
    return SqlBiMetricRepository(session)


def _get_metric_value_repo(session: AsyncSession) -> BiMetricValueRepository:
    return SqlBiMetricValueRepository(session)


def _get_report_repo(session: AsyncSession) -> BiReportRepository:
    return SqlBiReportRepository(session)


def _get_widget_repo(session: AsyncSession) -> BiDashboardWidgetRepository:
    return SqlBiDashboardWidgetRepository(session)


async def get_metric_service(session: AsyncSession = Depends(get_db_session)) -> BiMetricService:
    return BiMetricService(session=session, metric_repo=_get_metric_repo(session))


async def get_metric_value_service(session: AsyncSession = Depends(get_db_session)) -> BiMetricValueService:
    return BiMetricValueService(session=session, metric_value_repo=_get_metric_value_repo(session))


async def get_report_service(session: AsyncSession = Depends(get_db_session)) -> BiReportService:
    return BiReportService(session=session, report_repo=_get_report_repo(session))


async def get_widget_service(session: AsyncSession = Depends(get_db_session)) -> BiDashboardWidgetService:
    return BiDashboardWidgetService(session=session, widget_repo=_get_widget_repo(session))


async def get_kpi_service(session: AsyncSession = Depends(get_db_session)) -> KpiAggregationService:
    return KpiAggregationService(session=session, metric_value_repo=_get_metric_value_repo(session))


async def get_bi_query_service(session: AsyncSession = Depends(get_db_session)) -> BIQueryService:
    return BIQueryService(session=session)
