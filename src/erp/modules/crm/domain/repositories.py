from abc import ABC, abstractmethod
from collections.abc import Sequence

from erp.modules.crm.domain.models import (
    Complaint,
    Customer,
    CustomerCommunication,
    CustomerTag,
    ReturnRefund,
    Review,
    ReviewReplyTemplate,
    ServiceTicket,
)


class CustomerRepository(ABC):
    @abstractmethod
    async def get_by_id(self, customer_id: str, tenant_id: str) -> Customer | None: ...

    @abstractmethod
    async def get_by_customer_no(self, customer_no: str, tenant_id: str) -> Customer | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, segment: str = "", platform: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Customer], int]: ...

    @abstractmethod
    async def create(self, customer: Customer) -> Customer: ...

    @abstractmethod
    async def update(self, customer: Customer) -> Customer: ...


class CustomerTagRepository(ABC):
    @abstractmethod
    async def list_by_tenant(self, tenant_id: str) -> Sequence[CustomerTag]: ...

    @abstractmethod
    async def create(self, tag: CustomerTag) -> CustomerTag: ...

    @abstractmethod
    async def update(self, tag: CustomerTag) -> CustomerTag: ...


class CustomerCommunicationRepository(ABC):
    @abstractmethod
    async def list_by_customer(self, customer_id: str, tenant_id: str) -> Sequence[CustomerCommunication]: ...

    @abstractmethod
    async def create(self, comm: CustomerCommunication) -> CustomerCommunication: ...


class ReviewRepository(ABC):
    @abstractmethod
    async def get_by_id(self, review_id: str, tenant_id: str) -> Review | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", store_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Review], int]: ...

    @abstractmethod
    async def create(self, review: Review) -> Review: ...

    @abstractmethod
    async def update(self, review: Review) -> Review: ...


class ServiceTicketRepository(ABC):
    @abstractmethod
    async def get_by_id(self, ticket_id: str, tenant_id: str) -> ServiceTicket | None: ...

    @abstractmethod
    async def get_by_ticket_no(self, ticket_no: str, tenant_id: str) -> ServiceTicket | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", ticket_type: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[ServiceTicket], int]: ...

    @abstractmethod
    async def create(self, ticket: ServiceTicket) -> ServiceTicket: ...

    @abstractmethod
    async def update(self, ticket: ServiceTicket) -> ServiceTicket: ...


class ReturnRefundRepository(ABC):
    @abstractmethod
    async def get_by_id(self, return_id: str, tenant_id: str) -> ReturnRefund | None: ...

    @abstractmethod
    async def get_by_return_no(self, return_no: str, tenant_id: str) -> ReturnRefund | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[ReturnRefund], int]: ...

    @abstractmethod
    async def create(self, return_refund: ReturnRefund) -> ReturnRefund: ...

    @abstractmethod
    async def update(self, return_refund: ReturnRefund) -> ReturnRefund: ...


class ComplaintRepository(ABC):
    @abstractmethod
    async def get_by_id(self, complaint_id: str, tenant_id: str) -> Complaint | None: ...

    @abstractmethod
    async def get_by_complaint_no(self, complaint_no: str, tenant_id: str) -> Complaint | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", severity: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Complaint], int]: ...

    @abstractmethod
    async def create(self, complaint: Complaint) -> Complaint: ...

    @abstractmethod
    async def update(self, complaint: Complaint) -> Complaint: ...


class ReviewReplyTemplateRepository(ABC):
    @abstractmethod
    async def get_by_id(self, template_id: str, tenant_id: str) -> ReviewReplyTemplate | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, category: str = "", language: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[ReviewReplyTemplate], int]: ...

    @abstractmethod
    async def create(self, template: ReviewReplyTemplate) -> ReviewReplyTemplate: ...

    @abstractmethod
    async def update(self, template: ReviewReplyTemplate) -> ReviewReplyTemplate: ...
