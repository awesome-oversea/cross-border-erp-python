from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from erp.modules.fba.domain.models import FbaBoxLabel, FbaFee, FbaInboundPlan, FbaInventory, FbaReplenishmentPlan, FbaShipment


class FbaShipmentRepository(ABC):
    @abstractmethod
    async def get_by_id(self, shipment_id: str, tenant_id: str) -> FbaShipment | None: ...

    @abstractmethod
    async def get_by_shipment_id(self, shipment_id_field: str, tenant_id: str) -> FbaShipment | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", store_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[FbaShipment], int]: ...

    @abstractmethod
    async def create(self, shipment: FbaShipment) -> FbaShipment: ...

    @abstractmethod
    async def update(self, shipment: FbaShipment) -> FbaShipment: ...

    @abstractmethod
    async def soft_delete(self, shipment_id: str, tenant_id: str) -> bool: ...


class FbaInventoryRepository(ABC):
    @abstractmethod
    async def get_by_id(self, inventory_id: str, tenant_id: str) -> FbaInventory | None: ...

    @abstractmethod
    async def find_by_sku_store(self, sku_id: str, store_id: str, tenant_id: str) -> FbaInventory | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, store_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[FbaInventory], int]: ...

    @abstractmethod
    async def create(self, inventory: FbaInventory) -> FbaInventory: ...

    @abstractmethod
    async def update(self, inventory: FbaInventory) -> FbaInventory: ...


class FbaFeeRepository(ABC):
    @abstractmethod
    async def list_by_sku(self, sku_id: str, tenant_id: str, fee_type: str = "",
                          start_date: datetime | None = None, end_date: datetime | None = None) -> Sequence[FbaFee]: ...

    @abstractmethod
    async def list_by_store(self, store_id: str, tenant_id: str, fee_type: str = "",
                            start_date: datetime | None = None, end_date: datetime | None = None) -> Sequence[FbaFee]: ...

    @abstractmethod
    async def create(self, fee: FbaFee) -> FbaFee: ...


class FbaBoxLabelRepository(ABC):
    @abstractmethod
    async def get_by_id(self, label_id: str, tenant_id: str) -> FbaBoxLabel | None: ...

    @abstractmethod
    async def list_by_shipment(self, shipment_id: str, tenant_id: str) -> Sequence[FbaBoxLabel]: ...

    @abstractmethod
    async def create(self, label: FbaBoxLabel) -> FbaBoxLabel: ...

    @abstractmethod
    async def update(self, label: FbaBoxLabel) -> FbaBoxLabel: ...


class FbaReplenishmentPlanRepository(ABC):
    @abstractmethod
    async def get_by_id(self, plan_id: str, tenant_id: str) -> FbaReplenishmentPlan | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", store_id: str = "",
                             priority: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[FbaReplenishmentPlan], int]: ...

    @abstractmethod
    async def create(self, plan: FbaReplenishmentPlan) -> FbaReplenishmentPlan: ...

    @abstractmethod
    async def update(self, plan: FbaReplenishmentPlan) -> FbaReplenishmentPlan: ...


class FbaInboundPlanRepository(ABC):
    @abstractmethod
    async def get_by_id(self, plan_id: str, tenant_id: str) -> FbaInboundPlan | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[FbaInboundPlan], int]: ...

    @abstractmethod
    async def create(self, plan: FbaInboundPlan) -> FbaInboundPlan: ...

    @abstractmethod
    async def update(self, plan: FbaInboundPlan) -> FbaInboundPlan: ...
