from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from erp.modules.som.domain.models import AlertRecord, AlertRule, Listing, ListingBatchJob, ListingOptimization, OperationMonitor, PriceRule, Store


class StoreRepository(ABC):
    @abstractmethod
    async def get_by_id(self, store_id: str, tenant_id: str) -> Store | None: ...

    @abstractmethod
    async def get_by_code(self, code: str, tenant_id: str) -> Store | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, platform: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[Store], int]: ...

    @abstractmethod
    async def create(self, store: Store) -> Store: ...

    @abstractmethod
    async def update(self, store: Store) -> Store: ...

    @abstractmethod
    async def soft_delete(self, store_id: str, tenant_id: str) -> bool: ...


class ListingRepository(ABC):
    @abstractmethod
    async def get_by_id(self, listing_id: str, tenant_id: str) -> Listing | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, store_id: str = "", status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[Listing], int]: ...

    @abstractmethod
    async def list_by_store(self, store_id: str, tenant_id: str) -> Sequence[Listing]: ...

    @abstractmethod
    async def create(self, listing: Listing) -> Listing: ...

    @abstractmethod
    async def update(self, listing: Listing) -> Listing: ...

    @abstractmethod
    async def soft_delete(self, listing_id: str, tenant_id: str) -> bool: ...


class PriceRuleRepository(ABC):
    @abstractmethod
    async def get_by_id(self, rule_id: str, tenant_id: str) -> PriceRule | None: ...

    @abstractmethod
    async def find_active(self, tenant_id: str, platform: str = "", region: str = "") -> PriceRule | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, platform: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[PriceRule], int]: ...

    @abstractmethod
    async def create(self, rule: PriceRule) -> PriceRule: ...

    @abstractmethod
    async def update(self, rule: PriceRule) -> PriceRule: ...


class ListingBatchJobRepository(ABC):
    @abstractmethod
    async def get_by_id(self, job_id: str, tenant_id: str) -> ListingBatchJob | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[ListingBatchJob], int]: ...

    @abstractmethod
    async def create(self, job: ListingBatchJob) -> ListingBatchJob: ...

    @abstractmethod
    async def update(self, job: ListingBatchJob) -> ListingBatchJob: ...


class OperationMonitorRepository(ABC):
    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, store_id: str = "", metric_type: str = "",
                             start_date: datetime | None = None, end_date: datetime | None = None,
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[OperationMonitor], int]: ...

    @abstractmethod
    async def create(self, monitor: OperationMonitor) -> OperationMonitor: ...


class ListingOptimizationRepository(ABC):
    @abstractmethod
    async def get_by_id(self, optimization_id: str, tenant_id: str) -> ListingOptimization | None: ...

    @abstractmethod
    async def list_by_listing(self, listing_id: str, tenant_id: str) -> Sequence[ListingOptimization]: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, listing_id: str = "", opt_type: str = "",
                             status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[ListingOptimization], int]: ...

    @abstractmethod
    async def create(self, optimization: ListingOptimization) -> ListingOptimization: ...

    @abstractmethod
    async def update(self, optimization: ListingOptimization) -> ListingOptimization: ...


class AlertRuleRepository(ABC):
    @abstractmethod
    async def get_by_id(self, rule_id: str, tenant_id: str) -> AlertRule | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, metric_type: str = "", severity: str = "",
                             status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[AlertRule], int]: ...

    @abstractmethod
    async def find_active_by_metric(self, tenant_id: str, metric_type: str, store_id: str = "") -> Sequence[AlertRule]: ...

    @abstractmethod
    async def create(self, rule: AlertRule) -> AlertRule: ...

    @abstractmethod
    async def update(self, rule: AlertRule) -> AlertRule: ...


class AlertRecordRepository(ABC):
    @abstractmethod
    async def get_by_id(self, record_id: str, tenant_id: str) -> AlertRecord | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, rule_id: str = "", severity: str = "",
                             status: str = "", store_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[AlertRecord], int]: ...

    @abstractmethod
    async def find_recent_by_rule(self, rule_id: str, tenant_id: str, hours: int = 24) -> Sequence[AlertRecord]: ...

    @abstractmethod
    async def create(self, record: AlertRecord) -> AlertRecord: ...

    @abstractmethod
    async def update(self, record: AlertRecord) -> AlertRecord: ...
