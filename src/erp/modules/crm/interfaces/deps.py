from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import Depends

from erp.modules.crm.application.services import (
    CRMQueryService,
    CommunicationService,
    ComplaintService,
    CustomerService,
    CustomerTagService,
    ReturnRefundService,
    ReviewReplyTemplateService,
    ReviewService,
    ServiceTicketService,
)
from erp.modules.crm.domain.lifecycle_models import CustomerLifecycleService
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
from erp.modules.crm.infrastructure.repositories import (
    SqlComplaintRepository,
    SqlCustomerCommunicationRepository,
    SqlCustomerRepository,
    SqlCustomerTagRepository,
    SqlReturnRefundRepository,
    SqlReviewReplyTemplateRepository,
    SqlReviewRepository,
    SqlServiceTicketRepository,
)
from erp.shared.db.session import get_db_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _get_customer_repo(session: AsyncSession) -> CustomerRepository:
    return SqlCustomerRepository(session)


def _get_customer_tag_repo(session: AsyncSession) -> CustomerTagRepository:
    return SqlCustomerTagRepository(session)


def _get_communication_repo(session: AsyncSession) -> CustomerCommunicationRepository:
    return SqlCustomerCommunicationRepository(session)


def _get_review_repo(session: AsyncSession) -> ReviewRepository:
    return SqlReviewRepository(session)


def _get_ticket_repo(session: AsyncSession) -> ServiceTicketRepository:
    return SqlServiceTicketRepository(session)


def _get_return_refund_repo(session: AsyncSession) -> ReturnRefundRepository:
    return SqlReturnRefundRepository(session)


def _get_complaint_repo(session: AsyncSession) -> ComplaintRepository:
    return SqlComplaintRepository(session)


def _get_review_reply_template_repo(session: AsyncSession) -> ReviewReplyTemplateRepository:
    return SqlReviewReplyTemplateRepository(session)


async def get_customer_service(session: AsyncSession = Depends(get_db_session)) -> CustomerService:
    return CustomerService(
        session=session,
        customer_repo=_get_customer_repo(session),
    )


async def get_customer_tag_service(session: AsyncSession = Depends(get_db_session)) -> CustomerTagService:
    return CustomerTagService(
        session=session,
        customer_tag_repo=_get_customer_tag_repo(session),
    )


async def get_communication_service(session: AsyncSession = Depends(get_db_session)) -> CommunicationService:
    return CommunicationService(
        session=session,
        communication_repo=_get_communication_repo(session),
    )


async def get_review_service(session: AsyncSession = Depends(get_db_session)) -> ReviewService:
    return ReviewService(
        session=session,
        review_repo=_get_review_repo(session),
    )


async def get_ticket_service(session: AsyncSession = Depends(get_db_session)) -> ServiceTicketService:
    return ServiceTicketService(
        session=session,
        ticket_repo=_get_ticket_repo(session),
    )


async def get_return_refund_service(session: AsyncSession = Depends(get_db_session)) -> ReturnRefundService:
    return ReturnRefundService(
        session=session,
        return_refund_repo=_get_return_refund_repo(session),
    )


async def get_complaint_service(session: AsyncSession = Depends(get_db_session)) -> ComplaintService:
    return ComplaintService(
        session=session,
        complaint_repo=_get_complaint_repo(session),
    )


async def get_review_reply_template_service(session: AsyncSession = Depends(get_db_session)) -> ReviewReplyTemplateService:
    return ReviewReplyTemplateService(
        session=session,
        template_repo=_get_review_reply_template_repo(session),
    )


async def get_lifecycle_service(session: AsyncSession = Depends(get_db_session)) -> CustomerLifecycleService:
    return CustomerLifecycleService(session=session)


async def get_crm_query_service(session: AsyncSession = Depends(get_db_session)) -> CRMQueryService:
    return CRMQueryService(session=session)
