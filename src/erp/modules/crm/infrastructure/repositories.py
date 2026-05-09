from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
from erp.modules.crm.domain.repositories import (
    ComplaintRepository,
    CustomerCommunicationRepository,
    CustomerRepository,
    CustomerTagRepository,
    ReturnRefundRepository,
    ReviewReplyTemplateRepository,
    ReviewRepository,
    ServiceTicketRepository,
)


class SqlCustomerRepository(CustomerRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, customer_id: str, tenant_id: str) -> Customer | None:
        stmt = select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_customer_no(self, customer_no: str, tenant_id: str) -> Customer | None:
        stmt = select(Customer).where(Customer.customer_no == customer_no, Customer.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, segment: str = "", platform: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Customer], int]:
        conditions = [Customer.tenant_id == tenant_id]
        if segment:
            conditions.append(Customer.segment == segment)
        if platform:
            conditions.append(Customer.platform == platform)
        total = (await self._session.execute(select(func.count()).select_from(Customer).where(*conditions))).scalar() or 0
        stmt = select(Customer).where(*conditions).order_by(Customer.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, customer: Customer) -> Customer:
        self._session.add(customer)
        await self._session.flush()
        return customer

    async def update(self, customer: Customer) -> Customer:
        await self._session.flush()
        return customer


class SqlCustomerTagRepository(CustomerTagRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_tenant(self, tenant_id: str) -> Sequence[CustomerTag]:
        stmt = select(CustomerTag).where(CustomerTag.tenant_id == tenant_id, CustomerTag.status == "active")
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, tag: CustomerTag) -> CustomerTag:
        self._session.add(tag)
        await self._session.flush()
        return tag

    async def update(self, tag: CustomerTag) -> CustomerTag:
        await self._session.flush()
        return tag


class SqlCustomerCommunicationRepository(CustomerCommunicationRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_customer(self, customer_id: str, tenant_id: str) -> Sequence[CustomerCommunication]:
        stmt = select(CustomerCommunication).where(CustomerCommunication.customer_id == customer_id, CustomerCommunication.tenant_id == tenant_id).order_by(CustomerCommunication.created_at.desc())
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, comm: CustomerCommunication) -> CustomerCommunication:
        self._session.add(comm)
        await self._session.flush()
        return comm


class SqlReviewRepository(ReviewRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, review_id: str, tenant_id: str) -> Review | None:
        stmt = select(Review).where(Review.id == review_id, Review.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "", store_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Review], int]:
        conditions = [Review.tenant_id == tenant_id]
        if status:
            conditions.append(Review.status == status)
        if store_id:
            conditions.append(Review.store_id == store_id)
        total = (await self._session.execute(select(func.count()).select_from(Review).where(*conditions))).scalar() or 0
        stmt = select(Review).where(*conditions).order_by(Review.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, review: Review) -> Review:
        self._session.add(review)
        await self._session.flush()
        return review

    async def update(self, review: Review) -> Review:
        await self._session.flush()
        return review


class SqlServiceTicketRepository(ServiceTicketRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, ticket_id: str, tenant_id: str) -> ServiceTicket | None:
        stmt = select(ServiceTicket).where(ServiceTicket.id == ticket_id, ServiceTicket.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_ticket_no(self, ticket_no: str, tenant_id: str) -> ServiceTicket | None:
        stmt = select(ServiceTicket).where(ServiceTicket.ticket_no == ticket_no, ServiceTicket.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "", ticket_type: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[ServiceTicket], int]:
        conditions = [ServiceTicket.tenant_id == tenant_id]
        if status:
            conditions.append(ServiceTicket.status == status)
        if ticket_type:
            conditions.append(ServiceTicket.ticket_type == ticket_type)
        total = (await self._session.execute(select(func.count()).select_from(ServiceTicket).where(*conditions))).scalar() or 0
        stmt = select(ServiceTicket).where(*conditions).order_by(ServiceTicket.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, ticket: ServiceTicket) -> ServiceTicket:
        self._session.add(ticket)
        await self._session.flush()
        return ticket

    async def update(self, ticket: ServiceTicket) -> ServiceTicket:
        await self._session.flush()
        return ticket


class SqlReturnRefundRepository(ReturnRefundRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, return_id: str, tenant_id: str) -> ReturnRefund | None:
        stmt = select(ReturnRefund).where(ReturnRefund.id == return_id, ReturnRefund.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_return_no(self, return_no: str, tenant_id: str) -> ReturnRefund | None:
        stmt = select(ReturnRefund).where(ReturnRefund.return_no == return_no, ReturnRefund.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[ReturnRefund], int]:
        conditions = [ReturnRefund.tenant_id == tenant_id]
        if status:
            conditions.append(ReturnRefund.status == status)
        total = (await self._session.execute(select(func.count()).select_from(ReturnRefund).where(*conditions))).scalar() or 0
        stmt = select(ReturnRefund).where(*conditions).order_by(ReturnRefund.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, return_refund: ReturnRefund) -> ReturnRefund:
        self._session.add(return_refund)
        await self._session.flush()
        return return_refund

    async def update(self, return_refund: ReturnRefund) -> ReturnRefund:
        await self._session.flush()
        return return_refund


class SqlComplaintRepository(ComplaintRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, complaint_id: str, tenant_id: str) -> Complaint | None:
        stmt = select(Complaint).where(Complaint.id == complaint_id, Complaint.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_complaint_no(self, complaint_no: str, tenant_id: str) -> Complaint | None:
        stmt = select(Complaint).where(Complaint.complaint_no == complaint_no, Complaint.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "", severity: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Complaint], int]:
        conditions = [Complaint.tenant_id == tenant_id]
        if status:
            conditions.append(Complaint.status == status)
        if severity:
            conditions.append(Complaint.severity == severity)
        total = (await self._session.execute(select(func.count()).select_from(Complaint).where(*conditions))).scalar() or 0
        stmt = select(Complaint).where(*conditions).order_by(Complaint.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, complaint: Complaint) -> Complaint:
        self._session.add(complaint)
        await self._session.flush()
        return complaint

    async def update(self, complaint: Complaint) -> Complaint:
        await self._session.flush()
        return complaint


class SqlReviewReplyTemplateRepository(ReviewReplyTemplateRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, template_id: str, tenant_id: str) -> ReviewReplyTemplate | None:
        stmt = select(ReviewReplyTemplate).where(
            ReviewReplyTemplate.id == template_id, ReviewReplyTemplate.tenant_id == tenant_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, category: str = "", language: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[ReviewReplyTemplate], int]:
        conditions = [ReviewReplyTemplate.tenant_id == tenant_id, ReviewReplyTemplate.status == "active"]
        if category:
            conditions.append(ReviewReplyTemplate.category == category)
        if language:
            conditions.append(ReviewReplyTemplate.language == language)
        total = (await self._session.execute(select(func.count()).select_from(ReviewReplyTemplate).where(*conditions))).scalar() or 0
        stmt = select(ReviewReplyTemplate).where(*conditions).order_by(ReviewReplyTemplate.name).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, template: ReviewReplyTemplate) -> ReviewReplyTemplate:
        self._session.add(template)
        await self._session.flush()
        return template

    async def update(self, template: ReviewReplyTemplate) -> ReviewReplyTemplate:
        await self._session.flush()
        return template
