from abc import ABC, abstractmethod
from collections.abc import Sequence

from erp.modules.wms.domain.models import (
    InboundOrder,
    Inventory,
    Location,
    OutboundOrder,
    QualityInspection,
    StockCount,
    StockMovement,
    Warehouse,
)
from erp.modules.wms.domain.inventory_alert_models import (
    InventoryAlert,
    InventoryAlertRule,
    InventorySnapshot,
)
from erp.modules.wms.domain.transfer_replenishment_models import (
    FBAReplenishmentPlan,
    StockTransferOrder,
)


class WarehouseRepository(ABC):
    @abstractmethod
    async def get_by_id(self, warehouse_id: str, tenant_id: str) -> Warehouse | None: ...

    @abstractmethod
    async def get_by_code(self, code: str, tenant_id: str) -> Warehouse | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, warehouse_type: str = "", status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Warehouse], int]: ...

    @abstractmethod
    async def create(self, warehouse: Warehouse) -> Warehouse: ...

    @abstractmethod
    async def update(self, warehouse: Warehouse) -> Warehouse: ...

    @abstractmethod
    async def soft_delete(self, warehouse_id: str, tenant_id: str) -> bool: ...


class LocationRepository(ABC):
    @abstractmethod
    async def get_by_id(self, location_id: str, tenant_id: str) -> Location | None: ...

    @abstractmethod
    async def list_by_warehouse(self, warehouse_id: str, tenant_id: str, location_type: str = "") -> Sequence[Location]: ...

    @abstractmethod
    async def create(self, location: Location) -> Location: ...

    @abstractmethod
    async def update(self, location: Location) -> Location: ...


class InventoryRepository(ABC):
    @abstractmethod
    async def get_by_id(self, inventory_id: str, tenant_id: str) -> Inventory | None: ...

    @abstractmethod
    async def find_by_warehouse_sku(self, warehouse_id: str, sku_id: str, tenant_id: str) -> Inventory | None: ...

    @abstractmethod
    async def list_by_warehouse(self, warehouse_id: str, tenant_id: str, page: int = 1, page_size: int = 20) -> tuple[Sequence[Inventory], int]: ...

    @abstractmethod
    async def list_by_sku(self, sku_id: str, tenant_id: str) -> Sequence[Inventory]: ...

    @abstractmethod
    async def find_low_stock(self, tenant_id: str) -> Sequence[Inventory]: ...

    @abstractmethod
    async def create(self, inventory: Inventory) -> Inventory: ...

    @abstractmethod
    async def update(self, inventory: Inventory) -> Inventory: ...


class InboundOrderRepository(ABC):
    @abstractmethod
    async def get_by_id(self, inbound_id: str, tenant_id: str) -> InboundOrder | None: ...

    @abstractmethod
    async def get_by_inbound_no(self, inbound_no: str, tenant_id: str) -> InboundOrder | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", warehouse_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[InboundOrder], int]: ...

    @abstractmethod
    async def create(self, order: InboundOrder) -> InboundOrder: ...

    @abstractmethod
    async def update(self, order: InboundOrder) -> InboundOrder: ...


class OutboundOrderRepository(ABC):
    @abstractmethod
    async def get_by_id(self, outbound_id: str, tenant_id: str) -> OutboundOrder | None: ...

    @abstractmethod
    async def get_by_outbound_no(self, outbound_no: str, tenant_id: str) -> OutboundOrder | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", warehouse_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[OutboundOrder], int]: ...

    @abstractmethod
    async def create(self, order: OutboundOrder) -> OutboundOrder: ...

    @abstractmethod
    async def update(self, order: OutboundOrder) -> OutboundOrder: ...


class StockMovementRepository(ABC):
    @abstractmethod
    async def create(self, movement: StockMovement) -> StockMovement: ...

    @abstractmethod
    async def list_by_sku(self, sku_id: str, tenant_id: str, limit: int = 50) -> Sequence[StockMovement]: ...

    @abstractmethod
    async def list_by_reference(self, reference_type: str, reference_id: str, tenant_id: str) -> Sequence[StockMovement]: ...


class StockCountRepository(ABC):
    @abstractmethod
    async def get_by_id(self, count_id: str, tenant_id: str) -> StockCount | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[StockCount], int]: ...

    @abstractmethod
    async def create(self, count: StockCount) -> StockCount: ...

    @abstractmethod
    async def update(self, count: StockCount) -> StockCount: ...


class QualityInspectionRepository(ABC):
    @abstractmethod
    async def get_by_id(self, inspection_id: str, tenant_id: str) -> QualityInspection | None: ...

    @abstractmethod
    async def list_by_warehouse(self, tenant_id: str, warehouse_id: str,
                                 result: str = "", offset: int = 0, limit: int = 20) -> Sequence[QualityInspection]: ...

    @abstractmethod
    async def create(self, inspection: QualityInspection) -> QualityInspection: ...

    @abstractmethod
    async def update(self, inspection: QualityInspection) -> QualityInspection: ...


class StockTransferOrderRepository(ABC):
    @abstractmethod
    async def get_by_id(self, transfer_id: str, tenant_id: str) -> StockTransferOrder | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "",
                              from_warehouse_id: str = "", to_warehouse_id: str = "",
                              page: int = 1, page_size: int = 20) -> tuple[Sequence[StockTransferOrder], int]: ...

    @abstractmethod
    async def create(self, transfer: StockTransferOrder) -> StockTransferOrder: ...

    @abstractmethod
    async def update(self, transfer: StockTransferOrder) -> StockTransferOrder: ...


class FBAReplenishmentPlanRepository(ABC):
    @abstractmethod
    async def get_by_id(self, plan_id: str, tenant_id: str) -> FBAReplenishmentPlan | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, sku_id: str = "", status: str = "",
                              page: int = 1, page_size: int = 20) -> tuple[Sequence[FBAReplenishmentPlan], int]: ...

    @abstractmethod
    async def create(self, plan: FBAReplenishmentPlan) -> FBAReplenishmentPlan: ...

    @abstractmethod
    async def update(self, plan: FBAReplenishmentPlan) -> FBAReplenishmentPlan: ...


class InventorySnapshotRepository(ABC):
    @abstractmethod
    async def get_by_key(self, tenant_id: str, snapshot_date: str,
                          warehouse_id: str, sku_id: str) -> InventorySnapshot | None: ...

    @abstractmethod
    async def list_by_date(self, tenant_id: str, snapshot_date: str,
                            warehouse_id: str = "", sku_id: str = "") -> Sequence[InventorySnapshot]: ...

    @abstractmethod
    async def create(self, snapshot: InventorySnapshot) -> InventorySnapshot: ...

    @abstractmethod
    async def update(self, snapshot: InventorySnapshot) -> InventorySnapshot: ...


class InventoryAlertRuleRepository(ABC):
    @abstractmethod
    async def get_by_id(self, rule_id: str, tenant_id: str) -> InventoryAlertRule | None: ...

    @abstractmethod
    async def list_active(self, tenant_id: str) -> Sequence[InventoryAlertRule]: ...

    @abstractmethod
    async def create(self, rule: InventoryAlertRule) -> InventoryAlertRule: ...

    @abstractmethod
    async def update(self, rule: InventoryAlertRule) -> InventoryAlertRule: ...


class InventoryAlertRepository(ABC):
    @abstractmethod
    async def get_by_id(self, alert_id: str, tenant_id: str) -> InventoryAlert | None: ...

    @abstractmethod
    async def find_active_in_cooldown(self, tenant_id: str, rule_id: str, alert_type: str,
                                       warehouse_id: str, sku_id: str,
                                       cutoff_time) -> InventoryAlert | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, alert_type: str = "",
                              severity: str = "", status: str = "",
                              warehouse_id: str = "", sku_id: str = "",
                              page: int = 1, page_size: int = 20) -> tuple[Sequence[InventoryAlert], int]: ...

    @abstractmethod
    async def create(self, alert: InventoryAlert) -> InventoryAlert: ...

    @abstractmethod
    async def update(self, alert: InventoryAlert) -> InventoryAlert: ...
