from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from erp.modules.fms.domain.models import CostEvent, ExchangeRate, PaymentRecord, PlatformSettlement


class CostEventRepository(ABC):
    @abstractmethod
    async def get_by_id(self, event_id: str, tenant_id: str) -> CostEvent | None: ...

    @abstractmethod
    async def get_by_event_no(self, event_no: str, tenant_id: str) -> CostEvent | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, cost_type: str = "", sku_id: str = "",
                             start_date: datetime | None = None, end_date: datetime | None = None,
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[CostEvent], int]: ...

    @abstractmethod
    async def create(self, event: CostEvent) -> CostEvent: ...

    @abstractmethod
    async def update(self, event: CostEvent) -> CostEvent: ...


class PlatformSettlementRepository(ABC):
    @abstractmethod
    async def get_by_id(self, settlement_id: str, tenant_id: str) -> PlatformSettlement | None: ...

    @abstractmethod
    async def get_by_settlement_no(self, settlement_no: str, tenant_id: str) -> PlatformSettlement | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, platform: str = "", store_id: str = "",
                             status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[PlatformSettlement], int]: ...

    @abstractmethod
    async def create(self, settlement: PlatformSettlement) -> PlatformSettlement: ...

    @abstractmethod
    async def update(self, settlement: PlatformSettlement) -> PlatformSettlement: ...


class PaymentRecordRepository(ABC):
    @abstractmethod
    async def get_by_id(self, payment_id: str, tenant_id: str) -> PaymentRecord | None: ...

    @abstractmethod
    async def get_by_payment_no(self, payment_no: str, tenant_id: str) -> PaymentRecord | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, payment_type: str = "", status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[PaymentRecord], int]: ...

    @abstractmethod
    async def create(self, payment: PaymentRecord) -> PaymentRecord: ...

    @abstractmethod
    async def update(self, payment: PaymentRecord) -> PaymentRecord: ...


class ExchangeRateRepository(ABC):
    @abstractmethod
    async def get_latest(self, from_currency: str, to_currency: str, tenant_id: str) -> ExchangeRate | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, rate_date: datetime | None = None) -> Sequence[ExchangeRate]: ...

    @abstractmethod
    async def create(self, rate: ExchangeRate) -> ExchangeRate: ...
