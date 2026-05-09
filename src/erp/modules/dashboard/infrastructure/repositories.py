from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.dashboard.domain.models import Dashboard, DashboardComponent, DashboardShare, KpiMetric, TodoItem
from erp.modules.dashboard.domain.repositories import (
    DashboardComponentRepository,
    DashboardRepository,
    DashboardShareRepository,
    KpiMetricRepository,
    TodoItemRepository,
)


class SqlDashboardRepository(DashboardRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, dashboard_id: str, tenant_id: str) -> Dashboard | None:
        stmt = select(Dashboard).where(Dashboard.id == dashboard_id, Dashboard.tenant_id == tenant_id, Dashboard.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, code: str, tenant_id: str) -> Dashboard | None:
        stmt = select(Dashboard).where(Dashboard.code == code, Dashboard.tenant_id == tenant_id, Dashboard.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, owner_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Dashboard], int]:
        conditions = [Dashboard.tenant_id == tenant_id, Dashboard.deleted_at.is_(None)]
        if owner_id:
            conditions.append(Dashboard.owner_id == owner_id)
        total = (await self._session.execute(select(func.count()).select_from(Dashboard).where(*conditions))).scalar() or 0
        stmt = select(Dashboard).where(*conditions).order_by(Dashboard.sort_order, Dashboard.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, dashboard: Dashboard) -> Dashboard:
        self._session.add(dashboard)
        await self._session.flush()
        return dashboard

    async def update(self, dashboard: Dashboard) -> Dashboard:
        await self._session.flush()
        return dashboard

    async def soft_delete(self, dashboard_id: str, tenant_id: str) -> bool:
        stmt = update(Dashboard).where(Dashboard.id == dashboard_id, Dashboard.tenant_id == tenant_id).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlDashboardComponentRepository(DashboardComponentRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, component_id: str, tenant_id: str) -> DashboardComponent | None:
        stmt = select(DashboardComponent).where(DashboardComponent.id == component_id, DashboardComponent.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_dashboard(self, dashboard_id: str, tenant_id: str) -> Sequence[DashboardComponent]:
        stmt = select(DashboardComponent).where(DashboardComponent.dashboard_id == dashboard_id, DashboardComponent.tenant_id == tenant_id).order_by(DashboardComponent.sort_order)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, component: DashboardComponent) -> DashboardComponent:
        self._session.add(component)
        await self._session.flush()
        return component

    async def update(self, component: DashboardComponent) -> DashboardComponent:
        await self._session.flush()
        return component

    async def delete(self, component_id: str, tenant_id: str) -> bool:
        stmt = sa_delete(DashboardComponent).where(DashboardComponent.id == component_id, DashboardComponent.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlDashboardShareRepository(DashboardShareRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_dashboard(self, dashboard_id: str, tenant_id: str) -> Sequence[DashboardShare]:
        stmt = select(DashboardShare).where(DashboardShare.dashboard_id == dashboard_id, DashboardShare.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, share: DashboardShare) -> DashboardShare:
        self._session.add(share)
        await self._session.flush()
        return share

    async def delete(self, share_id: str, tenant_id: str) -> bool:
        stmt = sa_delete(DashboardShare).where(DashboardShare.id == share_id, DashboardShare.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlTodoItemRepository(TodoItemRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, todo_id: str, tenant_id: str) -> TodoItem | None:
        stmt = select(TodoItem).where(TodoItem.id == todo_id, TodoItem.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_user(self, tenant_id: str, user_id: str = "", status: str = "",
                           todo_type: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[TodoItem], int]:
        conditions = [TodoItem.tenant_id == tenant_id]
        if user_id:
            conditions.append(TodoItem.user_id == user_id)
        if status:
            conditions.append(TodoItem.status == status)
        if todo_type:
            conditions.append(TodoItem.todo_type == todo_type)
        total = (await self._session.execute(select(func.count()).select_from(TodoItem).where(*conditions))).scalar() or 0
        stmt = select(TodoItem).where(*conditions).order_by(TodoItem.priority_score.desc(), TodoItem.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, todo: TodoItem) -> TodoItem:
        self._session.add(todo)
        await self._session.flush()
        return todo

    async def update(self, todo: TodoItem) -> TodoItem:
        await self._session.flush()
        return todo


class SqlKpiMetricRepository(KpiMetricRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_code(self, metric_code: str, tenant_id: str) -> KpiMetric | None:
        stmt = select(KpiMetric).where(KpiMetric.metric_code == metric_code, KpiMetric.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_group(self, tenant_id: str, metric_group: str = "") -> Sequence[KpiMetric]:
        conditions = [KpiMetric.tenant_id == tenant_id, KpiMetric.status == "active"]
        if metric_group:
            conditions.append(KpiMetric.metric_group == metric_group)
        stmt = select(KpiMetric).where(*conditions).order_by(KpiMetric.metric_group, KpiMetric.metric_code)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, metric: KpiMetric) -> KpiMetric:
        self._session.add(metric)
        await self._session.flush()
        return metric

    async def update(self, metric: KpiMetric) -> KpiMetric:
        await self._session.flush()
        return metric

    async def upsert_by_code(self, metric: KpiMetric) -> KpiMetric:
        existing = await self.get_by_code(metric.metric_code, metric.tenant_id)
        if existing:
            existing.previous_value = existing.current_value
            existing.current_value = metric.current_value
            existing.change_rate = metric.change_rate
            existing.direction = metric.direction
            existing.last_refreshed_at = datetime.now(UTC)
            await self._session.flush()
            return existing
        return await self.create(metric)
