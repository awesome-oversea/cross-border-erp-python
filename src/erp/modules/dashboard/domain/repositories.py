from abc import ABC, abstractmethod
from collections.abc import Sequence

from erp.modules.dashboard.domain.models import Dashboard, DashboardComponent, DashboardShare, KpiMetric, TodoItem


class DashboardRepository(ABC):
    @abstractmethod
    async def get_by_id(self, dashboard_id: str, tenant_id: str) -> Dashboard | None: ...

    @abstractmethod
    async def get_by_code(self, code: str, tenant_id: str) -> Dashboard | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, owner_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Dashboard], int]: ...

    @abstractmethod
    async def create(self, dashboard: Dashboard) -> Dashboard: ...

    @abstractmethod
    async def update(self, dashboard: Dashboard) -> Dashboard: ...

    @abstractmethod
    async def soft_delete(self, dashboard_id: str, tenant_id: str) -> bool: ...


class DashboardComponentRepository(ABC):
    @abstractmethod
    async def get_by_id(self, component_id: str, tenant_id: str) -> DashboardComponent | None: ...

    @abstractmethod
    async def list_by_dashboard(self, dashboard_id: str, tenant_id: str) -> Sequence[DashboardComponent]: ...

    @abstractmethod
    async def create(self, component: DashboardComponent) -> DashboardComponent: ...

    @abstractmethod
    async def update(self, component: DashboardComponent) -> DashboardComponent: ...

    @abstractmethod
    async def delete(self, component_id: str, tenant_id: str) -> bool: ...


class DashboardShareRepository(ABC):
    @abstractmethod
    async def list_by_dashboard(self, dashboard_id: str, tenant_id: str) -> Sequence[DashboardShare]: ...

    @abstractmethod
    async def create(self, share: DashboardShare) -> DashboardShare: ...

    @abstractmethod
    async def delete(self, share_id: str, tenant_id: str) -> bool: ...


class TodoItemRepository(ABC):
    @abstractmethod
    async def get_by_id(self, todo_id: str, tenant_id: str) -> TodoItem | None: ...

    @abstractmethod
    async def list_by_user(self, tenant_id: str, user_id: str = "", status: str = "",
                           todo_type: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[TodoItem], int]: ...

    @abstractmethod
    async def create(self, todo: TodoItem) -> TodoItem: ...

    @abstractmethod
    async def update(self, todo: TodoItem) -> TodoItem: ...


class KpiMetricRepository(ABC):
    @abstractmethod
    async def get_by_code(self, metric_code: str, tenant_id: str) -> KpiMetric | None: ...

    @abstractmethod
    async def list_by_group(self, tenant_id: str, metric_group: str = "") -> Sequence[KpiMetric]: ...

    @abstractmethod
    async def create(self, metric: KpiMetric) -> KpiMetric: ...

    @abstractmethod
    async def update(self, metric: KpiMetric) -> KpiMetric: ...

    @abstractmethod
    async def upsert_by_code(self, metric: KpiMetric) -> KpiMetric: ...
