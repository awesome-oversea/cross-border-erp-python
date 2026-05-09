from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from erp.modules.bi.domain.models import BiDashboardWidget, BiMetric, BiMetricValue, BiReport


class BiMetricRepository(ABC):
    @abstractmethod
    async def get_by_id(self, metric_id: str, tenant_id: str) -> BiMetric | None: ...

    @abstractmethod
    async def get_by_code(self, metric_code: str, tenant_id: str) -> BiMetric | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, category: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[BiMetric], int]: ...

    @abstractmethod
    async def create(self, metric: BiMetric) -> BiMetric: ...

    @abstractmethod
    async def update(self, metric: BiMetric) -> BiMetric: ...


class BiMetricValueRepository(ABC):
    @abstractmethod
    async def list_by_metric(self, metric_id: str, tenant_id: str, period_type: str = "",
                             start_date: datetime | None = None, end_date: datetime | None = None) -> Sequence[BiMetricValue]: ...

    @abstractmethod
    async def list_by_metric_code(self, metric_code: str, tenant_id: str, period_type: str = "",
                                  start_date: datetime | None = None, end_date: datetime | None = None,
                                  store_id: str = "", platform: str = "") -> Sequence[BiMetricValue]: ...

    @abstractmethod
    async def create(self, value: BiMetricValue) -> BiMetricValue: ...


class BiReportRepository(ABC):
    @abstractmethod
    async def get_by_id(self, report_id: str, tenant_id: str) -> BiReport | None: ...

    @abstractmethod
    async def get_by_code(self, report_code: str, tenant_id: str) -> BiReport | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, category: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[BiReport], int]: ...

    @abstractmethod
    async def create(self, report: BiReport) -> BiReport: ...

    @abstractmethod
    async def update(self, report: BiReport) -> BiReport: ...


class BiDashboardWidgetRepository(ABC):
    @abstractmethod
    async def list_by_dashboard(self, dashboard_id: str, tenant_id: str) -> Sequence[BiDashboardWidget]: ...

    @abstractmethod
    async def create(self, widget: BiDashboardWidget) -> BiDashboardWidget: ...

    @abstractmethod
    async def update(self, widget: BiDashboardWidget) -> BiDashboardWidget: ...

    @abstractmethod
    async def delete(self, widget_id: str, tenant_id: str) -> bool: ...
