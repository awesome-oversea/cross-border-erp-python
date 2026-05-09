from abc import ABC, abstractmethod
from collections.abc import Sequence

from erp.modules.oms.domain.models import OrderAuditLog, OrderSplitRule, Promotion, RefundOrder, SalesOrder, SalesOrderItem


class SalesOrderRepository(ABC):
    @abstractmethod
    async def get_by_id(self, order_id: str, tenant_id: str) -> SalesOrder | None: ...

    @abstractmethod
    async def get_by_order_no(self, order_no: str, tenant_id: str) -> SalesOrder | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", platform: str = "", store_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[SalesOrder], int]: ...

    @abstractmethod
    async def create(self, order: SalesOrder) -> SalesOrder: ...

    @abstractmethod
    async def update(self, order: SalesOrder) -> SalesOrder: ...

    @abstractmethod
    async def soft_delete(self, order_id: str, tenant_id: str) -> bool: ...


class SalesOrderItemRepository(ABC):
    @abstractmethod
    async def list_by_order(self, order_id: str, tenant_id: str) -> Sequence[SalesOrderItem]: ...

    @abstractmethod
    async def create(self, item: SalesOrderItem) -> SalesOrderItem: ...

    @abstractmethod
    async def update(self, item: SalesOrderItem) -> SalesOrderItem: ...


class RefundOrderRepository(ABC):
    @abstractmethod
    async def get_by_id(self, refund_id: str, tenant_id: str) -> RefundOrder | None: ...

    @abstractmethod
    async def get_by_refund_no(self, refund_no: str, tenant_id: str) -> RefundOrder | None: ...

    @abstractmethod
    async def list_by_original_order(self, original_order_id: str, tenant_id: str) -> Sequence[RefundOrder]: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[RefundOrder], int]: ...

    @abstractmethod
    async def create(self, refund: RefundOrder) -> RefundOrder: ...

    @abstractmethod
    async def update(self, refund: RefundOrder) -> RefundOrder: ...


class OrderSplitRuleRepository(ABC):
    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "") -> Sequence[OrderSplitRule]: ...

    @abstractmethod
    async def create(self, rule: OrderSplitRule) -> OrderSplitRule: ...

    @abstractmethod
    async def update(self, rule: OrderSplitRule) -> OrderSplitRule: ...


class OrderAuditLogRepository(ABC):
    @abstractmethod
    async def create(self, log: OrderAuditLog) -> OrderAuditLog: ...

    @abstractmethod
    async def list_by_order(self, order_id: str, tenant_id: str) -> Sequence[OrderAuditLog]: ...


class PromotionRepository(ABC):
    @abstractmethod
    async def get_by_id(self, promo_id: str, tenant_id: str) -> Promotion | None: ...

    @abstractmethod
    async def get_by_promo_no(self, promo_no: str, tenant_id: str) -> Promotion | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", promo_type: str = "",
                             platform: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[Promotion], int]: ...

    @abstractmethod
    async def list_active_for_discount(self, tenant_id: str, order_amount: float,
                                       platform: str = "", store_id: str = "") -> Sequence[Promotion]: ...

    @abstractmethod
    async def create(self, promo: Promotion) -> Promotion: ...

    @abstractmethod
    async def update(self, promo: Promotion) -> Promotion: ...

    @abstractmethod
    async def soft_delete(self, promo_id: str, tenant_id: str) -> bool: ...
