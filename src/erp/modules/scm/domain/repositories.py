from abc import ABC, abstractmethod
from collections.abc import Sequence

from erp.modules.scm.domain.models import (
    Inquiry,
    InquiryQuote,
    PurchaseOrder,
    PurchaseOrderItem,
    ReplenishmentPlan,
    Supplier,
    SupplierEvaluation,
)


class SupplierRepository(ABC):
    @abstractmethod
    async def get_by_id(self, supplier_id: str, tenant_id: str) -> Supplier | None: ...

    @abstractmethod
    async def get_by_code(self, code: str, tenant_id: str) -> Supplier | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", supplier_type: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Supplier], int]: ...

    @abstractmethod
    async def create(self, supplier: Supplier) -> Supplier: ...

    @abstractmethod
    async def update(self, supplier: Supplier) -> Supplier: ...

    @abstractmethod
    async def soft_delete(self, supplier_id: str, tenant_id: str) -> bool: ...


class PurchaseOrderRepository(ABC):
    @abstractmethod
    async def get_by_id(self, po_id: str, tenant_id: str) -> PurchaseOrder | None: ...

    @abstractmethod
    async def get_by_po_no(self, po_no: str, tenant_id: str) -> PurchaseOrder | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", supplier_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[PurchaseOrder], int]: ...

    @abstractmethod
    async def create(self, po: PurchaseOrder) -> PurchaseOrder: ...

    @abstractmethod
    async def update(self, po: PurchaseOrder) -> PurchaseOrder: ...

    @abstractmethod
    async def soft_delete(self, po_id: str, tenant_id: str) -> bool: ...


class PurchaseOrderItemRepository(ABC):
    @abstractmethod
    async def list_by_po(self, po_id: str, tenant_id: str) -> Sequence[PurchaseOrderItem]: ...

    @abstractmethod
    async def create(self, item: PurchaseOrderItem) -> PurchaseOrderItem: ...

    @abstractmethod
    async def update(self, item: PurchaseOrderItem) -> PurchaseOrderItem: ...


class ReplenishmentPlanRepository(ABC):
    @abstractmethod
    async def get_by_id(self, plan_id: str, tenant_id: str) -> ReplenishmentPlan | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[ReplenishmentPlan], int]: ...

    @abstractmethod
    async def create(self, plan: ReplenishmentPlan) -> ReplenishmentPlan: ...

    @abstractmethod
    async def update(self, plan: ReplenishmentPlan) -> ReplenishmentPlan: ...


class SupplierEvaluationRepository(ABC):
    @abstractmethod
    async def list_by_supplier(self, supplier_id: str, tenant_id: str) -> Sequence[SupplierEvaluation]: ...

    @abstractmethod
    async def get_by_supplier_period(self, supplier_id: str, period: str, tenant_id: str) -> SupplierEvaluation | None: ...

    @abstractmethod
    async def create(self, evaluation: SupplierEvaluation) -> SupplierEvaluation: ...


class InquiryRepository(ABC):
    @abstractmethod
    async def get_by_id(self, inquiry_id: str, tenant_id: str) -> Inquiry | None: ...

    @abstractmethod
    async def get_by_inquiry_no(self, inquiry_no: str, tenant_id: str) -> Inquiry | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Inquiry], int]: ...

    @abstractmethod
    async def create(self, inquiry: Inquiry) -> Inquiry: ...

    @abstractmethod
    async def update(self, inquiry: Inquiry) -> Inquiry: ...


class InquiryQuoteRepository(ABC):
    @abstractmethod
    async def list_by_inquiry(self, inquiry_id: str, tenant_id: str) -> Sequence[InquiryQuote]: ...

    @abstractmethod
    async def get_by_id(self, quote_id: str, tenant_id: str) -> InquiryQuote | None: ...

    @abstractmethod
    async def create(self, quote: InquiryQuote) -> InquiryQuote: ...

    @abstractmethod
    async def update(self, quote: InquiryQuote) -> InquiryQuote: ...
