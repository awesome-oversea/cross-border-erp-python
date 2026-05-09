"""
Dashboard 模块依赖注入工厂 - 提供所有应用服务的 FastAPI Depends 工厂函数

本模块将仓储接口的创建与服务的组装集中管理，
路由层通过 Depends(get_xxx_service) 获取已注入仓储的服务实例，
实现控制反转（IoC）和依赖倒置（DIP）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends

from erp.modules.dashboard.application.services import (
    BusinessAggregationService,
    DashboardComponentService,
    DashboardQueryService,
    DashboardService,
    DashboardShareService,
    KpiMetricService,
    TodoItemService,
)
from erp.modules.dashboard.domain.repositories import (
    DashboardComponentRepository,
    DashboardRepository,
    DashboardShareRepository,
    KpiMetricRepository,
    TodoItemRepository,
)
from erp.modules.dashboard.infrastructure.repositories import (
    SqlDashboardComponentRepository,
    SqlDashboardRepository,
    SqlDashboardShareRepository,
    SqlKpiMetricRepository,
    SqlTodoItemRepository,
)
from erp.shared.db.session import get_db_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _get_dashboard_repo(session: AsyncSession) -> DashboardRepository:
    return SqlDashboardRepository(session)


def _get_component_repo(session: AsyncSession) -> DashboardComponentRepository:
    return SqlDashboardComponentRepository(session)


def _get_share_repo(session: AsyncSession) -> DashboardShareRepository:
    return SqlDashboardShareRepository(session)


def _get_todo_repo(session: AsyncSession) -> TodoItemRepository:
    return SqlTodoItemRepository(session)


def _get_kpi_repo(session: AsyncSession) -> KpiMetricRepository:
    return SqlKpiMetricRepository(session)


async def get_dashboard_service(session: AsyncSession = Depends(get_db_session)) -> DashboardService:
    return DashboardService(session=session, dashboard_repo=_get_dashboard_repo(session))


async def get_component_service(session: AsyncSession = Depends(get_db_session)) -> DashboardComponentService:
    return DashboardComponentService(session=session, component_repo=_get_component_repo(session))


async def get_share_service(session: AsyncSession = Depends(get_db_session)) -> DashboardShareService:
    return DashboardShareService(session=session, share_repo=_get_share_repo(session))


async def get_business_service(session: AsyncSession = Depends(get_db_session)) -> BusinessAggregationService:
    return BusinessAggregationService(session=session, dashboard_repo=_get_dashboard_repo(session))


async def get_todo_service(session: AsyncSession = Depends(get_db_session)) -> TodoItemService:
    return TodoItemService(session=session, todo_repo=_get_todo_repo(session))


async def get_kpi_service(session: AsyncSession = Depends(get_db_session)) -> KpiMetricService:
    return KpiMetricService(session=session, kpi_repo=_get_kpi_repo(session))


async def get_dashboard_query_service(session: AsyncSession = Depends(get_db_session)) -> DashboardQueryService:
    return DashboardQueryService(session=session)
