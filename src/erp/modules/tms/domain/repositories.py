"""
TMS 领域仓储接口

定义运输管理模块所有聚合根的持久化抽象，
包括物流商、配送方式、发货单、运费模板、
物流策略、物流连接器及其关联实体。
"""
from abc import ABC, abstractmethod
from collections.abc import Sequence

from erp.modules.tms.domain.logistics_connector_models import (
    DispatchRecord,
    FreightQuote,
    LogisticsConnector,
    ShipmentLabel,
    TrackingRecord,
)
from erp.modules.tms.domain.models import FreightTemplate, LogisticsProvider, Shipment, ShippingBatch, ShippingMethod
from erp.modules.tms.domain.strategy_models import LogisticsStrategy, LogisticsStrategyExecutionLog


class LogisticsProviderRepository(ABC):
    """物流商仓储接口"""

    @abstractmethod
    async def get_by_id(self, provider_id: str, tenant_id: str) -> LogisticsProvider | None: ...

    @abstractmethod
    async def get_by_code(self, code: str, tenant_id: str) -> LogisticsProvider | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", provider_type: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[LogisticsProvider], int]: ...

    @abstractmethod
    async def create(self, provider: LogisticsProvider) -> LogisticsProvider: ...

    @abstractmethod
    async def update(self, provider: LogisticsProvider) -> LogisticsProvider: ...

    @abstractmethod
    async def soft_delete(self, provider_id: str, tenant_id: str) -> bool: ...


class ShippingMethodRepository(ABC):
    """配送方式仓储接口"""

    @abstractmethod
    async def get_by_id(self, method_id: str, tenant_id: str) -> ShippingMethod | None: ...

    @abstractmethod
    async def get_by_code(self, code: str, tenant_id: str) -> ShippingMethod | None: ...

    @abstractmethod
    async def list_by_provider(self, provider_id: str, tenant_id: str) -> Sequence[ShippingMethod]: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[ShippingMethod], int]: ...

    @abstractmethod
    async def create(self, method: ShippingMethod) -> ShippingMethod: ...

    @abstractmethod
    async def update(self, method: ShippingMethod) -> ShippingMethod: ...


class ShipmentRepository(ABC):
    """发货单仓储接口"""

    @abstractmethod
    async def get_by_id(self, shipment_id: str, tenant_id: str) -> Shipment | None: ...

    @abstractmethod
    async def get_by_shipment_no(self, shipment_no: str, tenant_id: str) -> Shipment | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", order_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Shipment], int]: ...

    @abstractmethod
    async def list_by_status(self, tenant_id: str, status: str,
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Shipment], int]: ...

    @abstractmethod
    async def create(self, shipment: Shipment) -> Shipment: ...

    @abstractmethod
    async def update(self, shipment: Shipment) -> Shipment: ...


class FreightTemplateRepository(ABC):
    """运费模板仓储接口"""

    @abstractmethod
    async def get_by_id(self, template_id: str, tenant_id: str) -> FreightTemplate | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[FreightTemplate], int]: ...

    @abstractmethod
    async def create(self, template: FreightTemplate) -> FreightTemplate: ...

    @abstractmethod
    async def update(self, template: FreightTemplate) -> FreightTemplate: ...


class ShippingBatchRepository(ABC):
    """发货批次仓储接口"""

    @abstractmethod
    async def get_by_id(self, batch_id: str, tenant_id: str) -> ShippingBatch | None: ...

    @abstractmethod
    async def get_by_batch_no(self, batch_no: str, tenant_id: str) -> ShippingBatch | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", carrier_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[ShippingBatch], int]: ...

    @abstractmethod
    async def create(self, batch: ShippingBatch) -> ShippingBatch: ...

    @abstractmethod
    async def update(self, batch: ShippingBatch) -> ShippingBatch: ...


class LogisticsStrategyRepository(ABC):
    """物流策略仓储接口"""

    @abstractmethod
    async def get_by_id(self, strategy_id: str, tenant_id: str) -> LogisticsStrategy | None: ...

    @abstractmethod
    async def get_by_code(self, tenant_id: str, strategy_code: str) -> LogisticsStrategy | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, strategy_type: str = "",
                             is_active: bool | None = None,
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[LogisticsStrategy], int]: ...

    @abstractmethod
    async def create(self, strategy: LogisticsStrategy) -> LogisticsStrategy: ...

    @abstractmethod
    async def update(self, strategy: LogisticsStrategy) -> LogisticsStrategy: ...


class LogisticsStrategyExecutionLogRepository(ABC):
    """物流策略执行日志仓储接口"""

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, strategy_type: str = "",
                             order_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[LogisticsStrategyExecutionLog], int]: ...

    @abstractmethod
    async def create(self, log: LogisticsStrategyExecutionLog) -> LogisticsStrategyExecutionLog: ...


class LogisticsConnectorRepository(ABC):
    """物流连接器仓储接口"""

    @abstractmethod
    async def get_by_id(self, connector_id: str, tenant_id: str) -> LogisticsConnector | None: ...

    @abstractmethod
    async def get_by_code(self, tenant_id: str, code: str) -> LogisticsConnector | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, connector_type: str = "",
                             carrier_code: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[LogisticsConnector], int]: ...

    @abstractmethod
    async def create(self, connector: LogisticsConnector) -> LogisticsConnector: ...

    @abstractmethod
    async def update(self, connector: LogisticsConnector) -> LogisticsConnector: ...


class ShipmentLabelRepository(ABC):
    """面单仓储接口"""

    @abstractmethod
    async def create(self, label: ShipmentLabel) -> ShipmentLabel: ...


class TrackingRecordRepository(ABC):
    """物流轨迹仓储接口"""

    @abstractmethod
    async def get_by_tracking_number(self, tenant_id: str, tracking_number: str) -> TrackingRecord | None: ...

    @abstractmethod
    async def create(self, record: TrackingRecord) -> TrackingRecord: ...

    @abstractmethod
    async def update(self, record: TrackingRecord) -> TrackingRecord: ...


class FreightQuoteRepository(ABC):
    """运费报价仓储接口"""

    @abstractmethod
    async def create(self, quote: FreightQuote) -> FreightQuote: ...


class DispatchRecordRepository(ABC):
    """发货调度仓储接口"""

    @abstractmethod
    async def get_by_id(self, dispatch_id: str, tenant_id: str) -> DispatchRecord | None: ...

    @abstractmethod
    async def create(self, dispatch: DispatchRecord) -> DispatchRecord: ...

    @abstractmethod
    async def update(self, dispatch: DispatchRecord) -> DispatchRecord: ...
