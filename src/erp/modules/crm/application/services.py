"""
CRM (客户关系管理域) 应用服务层

职责: 编排客户/标签/沟通/评价/工单/退款/投诉的完整业务流程

核心服务:
  - CustomerService: 客户管理，多平台客户统一视图与RFM分群
  - CustomerTagService: 客户标签管理，手动/自动标签
  - CommunicationService: 客户沟通记录管理，多渠道沟通
  - ReviewService: 评价管理，多平台评价监控与回复
  - ServiceTicketService: 客服工单管理，SLA时效与满意度
  - ReturnRefundService: 退货退款管理，关联工单与订单
  - ComplaintService: 投诉管理，严重度分级与升级处理
  - ReviewReplyTemplateService: 评价回复模板管理
  - CRMQueryService: 统一查询服务，跨实体聚合查询
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select

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
from erp.modules.crm.domain.services import ComplaintDomainService, ReviewReplyTemplateDomainService
from erp.shared.context import actor_id_var
from erp.shared.exceptions import DuplicateCodeException, NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.crm")

TICKET_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "open": ["in_progress", "pending_customer", "cancelled"],
    "in_progress": ["pending_customer", "resolved", "escalated", "cancelled"],
    "pending_customer": ["in_progress", "resolved", "cancelled"],
    "escalated": ["in_progress", "resolved", "cancelled"],
    "resolved": ["closed", "reopened"],
    "closed": ["reopened"],
    "reopened": ["in_progress", "cancelled"],
    "cancelled": [],
}

TICKET_TYPES = {"inquiry", "complaint", "return", "refund", "exchange", "technical", "other"}
TICKET_PRIORITIES = {"low", "normal", "high", "urgent"}

REVIEW_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["acknowledged", "ignored"],
    "acknowledged": ["replied", "escalated"],
    "escalated": ["replied"],
    "replied": ["followed_up", "closed"],
    "followed_up": ["closed"],
    "ignored": [],
    "closed": [],
}

RETURN_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "requested": ["approved", "rejected", "cancelled"],
    "approved": ["return_shipping", "cancelled"],
    "return_shipping": ["received", "cancelled"],
    "received": ["inspecting"],
    "inspecting": ["refunding", "rejected_return"],
    "refunding": ["refunded"],
    "refunded": [],
    "rejected": [],
    "rejected_return": [],
    "cancelled": [],
}

SEGMENT_RULES: dict[str, dict] = {
    "vip": {"min_orders": 10, "min_amount": 5000.0},
    "high_value": {"min_orders": 5, "min_amount": 2000.0},
    "regular": {"min_orders": 2, "min_amount": 0.0},
    "new": {"min_orders": 1, "min_amount": 0.0},
    "inactive": {"min_orders": 0, "min_amount": 0.0},
    "normal": {"min_orders": 0, "min_amount": 0.0},
}


class CustomerService:
    """客户应用服务 - 管理客户生命周期、标签和分群"""

    def __init__(self, session: AsyncSession, customer_repo: CustomerRepository | None = None):
        self._session = session
        self._customer_repo = customer_repo

    async def create(self, tenant_id: str, customer_no: str, **kwargs) -> Customer:
        if self._customer_repo:
            existing = await self._customer_repo.get_by_customer_no(customer_no, tenant_id)
        else:
            stmt = select(Customer).where(Customer.customer_no == customer_no, Customer.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Customer no '{customer_no}' already exists")
        customer = Customer(tenant_id=tenant_id, customer_no=customer_no,
                            **{k: v for k, v in kwargs.items() if hasattr(Customer, k)})
        if self._customer_repo:
            return await self._customer_repo.create(customer)
        self._session.add(customer)
        await self._session.flush()
        return customer

    async def get_by_id(self, customer_id: str, tenant_id: str = "") -> Customer | None:
        if self._customer_repo and tenant_id:
            return await self._customer_repo.get_by_id(customer_id, tenant_id)
        stmt = select(Customer).where(Customer.id == customer_id)
        if tenant_id:
            stmt = stmt.where(Customer.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, customer_id: str, tenant_id: str = "") -> Customer:
        customer = await self.get_by_id(customer_id, tenant_id)
        if not customer:
            raise NotFoundException(message=f"Customer '{customer_id}' not found")
        return customer

    async def list_by_tenant(self, tenant_id: str, platform: str | None = None,
                             segment: str | None = None, offset: int = 0, limit: int = 20) -> list[Customer]:
        if self._customer_repo:
            page = (offset // limit) + 1 if limit > 0 else 1
            customers, _ = await self._customer_repo.list_by_tenant(
                tenant_id, segment=segment or "", platform=platform or "", page=page, page_size=limit
            )
            return list(customers)
        stmt = select(Customer).where(Customer.tenant_id == tenant_id)
        if platform:
            stmt = stmt.where(Customer.platform == platform)
        if segment:
            stmt = stmt.where(Customer.segment == segment)
        stmt = stmt.order_by(Customer.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_stats(self, customer_id: str, order_amount: float = 0) -> Customer | None:
        customer = await self.get_by_id(customer_id)
        if not customer:
            return None
        customer.total_orders += 1
        customer.total_amount += order_amount
        customer.avg_order_value = round(customer.total_amount / customer.total_orders, 2)
        if not customer.first_order_at:
            customer.first_order_at = datetime.now(UTC)
        customer.last_order_at = datetime.now(UTC)
        if self._customer_repo:
            return await self._customer_repo.update(customer)
        await self._session.flush()
        return customer

    async def add_tags(self, customer_id: str, tags: list[str]) -> Customer | None:
        customer = await self.get_by_id(customer_id)
        if not customer:
            return None
        existing = json.loads(customer.tags_json) if customer.tags_json else []
        merged = list(set(existing + tags))
        customer.tags_json = json.dumps(merged, ensure_ascii=False)
        if self._customer_repo:
            return await self._customer_repo.update(customer)
        await self._session.flush()
        return customer

    async def auto_classify_segment(self, customer_id: str) -> Customer | None:
        customer = await self.get_by_id(customer_id)
        if not customer:
            return None
        segment = self._calculate_segment(customer.total_orders, customer.total_amount)
        customer.segment = segment
        if self._customer_repo:
            return await self._customer_repo.update(customer)
        await self._session.flush()
        return customer

    async def batch_classify_segments(self, tenant_id: str) -> int:
        stmt = select(Customer).where(Customer.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        customers = result.scalars().all()
        count = 0
        for c in customers:
            new_segment = self._calculate_segment(c.total_orders, c.total_amount)
            if c.segment != new_segment:
                c.segment = new_segment
                count += 1
        await self._session.flush()
        return count

    @staticmethod
    def _calculate_segment(total_orders: int, total_amount: float) -> str:
        for seg_name in ("vip", "high_value", "regular", "new"):
            rule = SEGMENT_RULES[seg_name]
            if total_orders >= rule["min_orders"] and total_amount >= rule["min_amount"]:
                return seg_name
        return "normal"

    async def update(self, customer_id: str, tenant_id: str, **kwargs) -> Customer:
        customer = await self.get_by_id(customer_id, tenant_id)
        if not customer:
            raise NotFoundException(message=f"Customer '{customer_id}' not found")
        for k, v in kwargs.items():
            if v is not None and hasattr(customer, k):
                setattr(customer, k, v)
        if self._customer_repo:
            return await self._customer_repo.update(customer)
        await self._session.flush()
        return customer

    async def soft_delete(self, customer_id: str, tenant_id: str) -> bool:
        customer = await self.get_by_id(customer_id, tenant_id)
        if not customer:
            raise NotFoundException(message=f"Customer '{customer_id}' not found")
        customer.deleted_at = datetime.now(UTC)
        customer.status = "inactive"
        if self._customer_repo:
            await self._customer_repo.update(customer)
        else:
            await self._session.flush()
        return True


class CustomerTagService:
    """客户标签应用服务 - 管理客户标签的创建和查询"""

    def __init__(self, session: AsyncSession, customer_tag_repo: CustomerTagRepository | None = None):
        self._session = session
        self._customer_tag_repo = customer_tag_repo

    async def create(self, tenant_id: str, name: str, **kwargs) -> CustomerTag:
        tag = CustomerTag(tenant_id=tenant_id, name=name,
                          **{k: v for k, v in kwargs.items() if hasattr(CustomerTag, k)})
        if self._customer_tag_repo:
            return await self._customer_tag_repo.create(tag)
        self._session.add(tag)
        await self._session.flush()
        return tag

    async def list_by_tenant(self, tenant_id: str) -> list[CustomerTag]:
        if self._customer_tag_repo:
            return list(await self._customer_tag_repo.list_by_tenant(tenant_id))
        stmt = select(CustomerTag).where(CustomerTag.tenant_id == tenant_id).order_by(CustomerTag.created_at)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class CommunicationService:
    """客户沟通应用服务 - 管理客户沟通记录"""

    def __init__(self, session: AsyncSession, communication_repo: CustomerCommunicationRepository | None = None):
        self._session = session
        self._communication_repo = communication_repo

    async def get_by_id(self, comm_id: str) -> CustomerCommunication | None:
        stmt = select(CustomerCommunication).where(CustomerCommunication.id == comm_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create(self, tenant_id: str, customer_id: str, channel: str = "email",
                     direction: str = "outbound", **kwargs) -> CustomerCommunication:
        comm = CustomerCommunication(tenant_id=tenant_id, customer_id=customer_id,
                                     channel=channel, direction=direction,
                                     **{k: v for k, v in kwargs.items() if hasattr(CustomerCommunication, k)})
        if self._communication_repo:
            return await self._communication_repo.create(comm)
        self._session.add(comm)
        await self._session.flush()
        return comm

    async def list_by_customer(self, customer_id: str) -> list[CustomerCommunication]:
        if self._communication_repo:
            return list(await self._communication_repo.list_by_customer(customer_id, ""))
        stmt = select(CustomerCommunication).where(
            CustomerCommunication.customer_id == customer_id
        ).order_by(CustomerCommunication.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ReviewService:
    """评价应用服务 - 管理商品评价、回复和状态流转"""

    def __init__(self, session: AsyncSession, review_repo: ReviewRepository | None = None):
        self._session = session
        self._review_repo = review_repo

    async def create(self, tenant_id: str, platform: str, store_id: str,
                     rating: int, **kwargs) -> Review:
        if not (1 <= rating <= 5):
            raise ValidationException(message="Rating must be between 1 and 5")
        is_negative = rating <= 2
        review = Review(
            tenant_id=tenant_id, platform=platform, store_id=store_id,
            rating=rating, is_negative=is_negative,
            **{k: v for k, v in kwargs.items() if hasattr(Review, k)},
        )
        if self._review_repo:
            return await self._review_repo.create(review)
        self._session.add(review)
        await self._session.flush()
        return review

    async def get_by_id(self, review_id: str, tenant_id: str = "") -> Review | None:
        if self._review_repo and tenant_id:
            return await self._review_repo.get_by_id(review_id, tenant_id)
        stmt = select(Review).where(Review.id == review_id)
        if tenant_id:
            stmt = stmt.where(Review.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, review_id: str, tenant_id: str = "") -> Review:
        review = await self.get_by_id(review_id, tenant_id)
        if not review:
            raise NotFoundException(message=f"Review '{review_id}' not found")
        return review

    async def list_by_tenant(self, tenant_id: str, platform: str | None = None,
                             status: str | None = None, is_negative: bool | None = None,
                             offset: int = 0, limit: int = 20) -> list[Review]:
        stmt = select(Review).where(Review.tenant_id == tenant_id)
        if platform:
            stmt = stmt.where(Review.platform == platform)
        if status:
            stmt = stmt.where(Review.status == status)
        if is_negative is not None:
            stmt = stmt.where(Review.is_negative == is_negative)
        stmt = stmt.order_by(Review.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, review_id: str, tenant_id: str, new_status: str) -> Review:
        review = await self.get_by_id(review_id, tenant_id)
        if not review:
            raise NotFoundException(message=f"Review '{review_id}' not found")
        allowed = REVIEW_STATUS_TRANSITIONS.get(review.status, [])
        if new_status not in allowed:
            raise ValidationException(
                message=f"Cannot transition review from '{review.status}' to '{new_status}'"
            )
        review.status = new_status
        if self._review_repo:
            return await self._review_repo.update(review)
        await self._session.flush()
        return review

    async def reply(self, review_id: str, tenant_id: str, reply_text: str, replied_by: str) -> Review:
        review = await self.get_by_id(review_id, tenant_id)
        if not review:
            raise NotFoundException(message=f"Review '{review_id}' not found")
        if review.status not in ("pending", "acknowledged", "escalated"):
            raise ValidationException(message=f"Cannot reply to review in '{review.status}' status")
        review.reply = reply_text
        review.replied_by = replied_by
        review.replied_at = datetime.now(UTC)
        review.status = "replied"
        if self._review_repo:
            return await self._review_repo.update(review)
        await self._session.flush()
        return review

    async def get_negative_unreplied(self, tenant_id: str, limit: int = 50) -> list[Review]:
        stmt = select(Review).where(
            Review.tenant_id == tenant_id,
            Review.is_negative,
            Review.status.in_(["pending", "acknowledged"]),
        ).order_by(Review.created_at.asc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ServiceTicketService:
    """服务工单应用服务 - 管理工单创建、状态流转、分配和解决"""

    def __init__(self, session: AsyncSession, ticket_repo: ServiceTicketRepository | None = None):
        self._session = session
        self._ticket_repo = ticket_repo

    async def create(self, tenant_id: str, ticket_no: str, customer_id: str,
                     ticket_type: str = "inquiry", priority: str = "normal",
                     subject: str = "", **kwargs) -> ServiceTicket:
        if ticket_type not in TICKET_TYPES:
            raise ValidationException(
                message=f"Invalid ticket type '{ticket_type}', allowed: {', '.join(sorted(TICKET_TYPES))}"
            )
        if priority not in TICKET_PRIORITIES:
            raise ValidationException(
                message=f"Invalid priority '{priority}', allowed: {', '.join(sorted(TICKET_PRIORITIES))}"
            )
        if self._ticket_repo:
            existing = await self._ticket_repo.get_by_ticket_no(ticket_no, tenant_id)
        else:
            stmt = select(ServiceTicket).where(
                ServiceTicket.ticket_no == ticket_no, ServiceTicket.tenant_id == tenant_id
            )
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Ticket no '{ticket_no}' already exists")
        ticket = ServiceTicket(
            tenant_id=tenant_id, ticket_no=ticket_no, customer_id=customer_id,
            ticket_type=ticket_type, priority=priority, subject=subject,
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(ServiceTicket, k)},
        )
        if priority == "urgent":
            ticket.sla_due_at = datetime.now(UTC) + timedelta(hours=2)
        elif priority == "high":
            ticket.sla_due_at = datetime.now(UTC) + timedelta(hours=4)
        if self._ticket_repo:
            return await self._ticket_repo.create(ticket)
        self._session.add(ticket)
        await self._session.flush()
        return ticket

    async def get_by_id(self, ticket_id: str, tenant_id: str = "") -> ServiceTicket | None:
        if self._ticket_repo and tenant_id:
            return await self._ticket_repo.get_by_id(ticket_id, tenant_id)
        stmt = select(ServiceTicket).where(ServiceTicket.id == ticket_id)
        if tenant_id:
            stmt = stmt.where(ServiceTicket.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str | None = None,
                             ticket_type: str | None = None, priority: str | None = None,
                             assigned_to: str | None = None,
                             offset: int = 0, limit: int = 20) -> list[ServiceTicket]:
        stmt = select(ServiceTicket).where(ServiceTicket.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(ServiceTicket.status == status)
        if ticket_type:
            stmt = stmt.where(ServiceTicket.ticket_type == ticket_type)
        if priority:
            stmt = stmt.where(ServiceTicket.priority == priority)
        if assigned_to:
            stmt = stmt.where(ServiceTicket.assigned_to == assigned_to)
        stmt = stmt.order_by(ServiceTicket.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, ticket_id: str, tenant_id: str, new_status: str) -> ServiceTicket:
        ticket = await self.get_by_id(ticket_id, tenant_id)
        if not ticket:
            raise NotFoundException(message=f"Ticket '{ticket_id}' not found")
        allowed = TICKET_STATUS_TRANSITIONS.get(ticket.status, [])
        if new_status not in allowed:
            raise ValidationException(
                message=f"Cannot transition ticket from '{ticket.status}' to '{new_status}'"
            )
        ticket.status = new_status
        if new_status == "in_progress" and not ticket.first_response_at:
            ticket.first_response_at = datetime.now(UTC)
        elif new_status == "resolved":
            ticket.resolved_at = datetime.now(UTC)
        elif new_status == "closed":
            ticket.closed_at = datetime.now(UTC)
        if self._ticket_repo:
            return await self._ticket_repo.update(ticket)
        await self._session.flush()
        return ticket

    async def assign(self, ticket_id: str, tenant_id: str, assigned_to: str,
                     assigned_group: str = "") -> ServiceTicket:
        ticket = await self.get_by_id(ticket_id, tenant_id)
        if not ticket:
            raise NotFoundException(message=f"Ticket '{ticket_id}' not found")
        if ticket.status not in ("open", "escalated"):
            raise ValidationException(message="Can only assign tickets in 'open' or 'escalated' status")
        ticket.assigned_to = assigned_to
        if assigned_group:
            ticket.assigned_group = assigned_group
        ticket.status = "in_progress"
        if not ticket.first_response_at:
            ticket.first_response_at = datetime.now(UTC)
        if self._ticket_repo:
            return await self._ticket_repo.update(ticket)
        await self._session.flush()
        return ticket

    async def resolve(self, ticket_id: str, tenant_id: str, resolution: str,
                      satisfaction_score: int = 0) -> ServiceTicket:
        ticket = await self.get_by_id(ticket_id, tenant_id)
        if not ticket:
            raise NotFoundException(message=f"Ticket '{ticket_id}' not found")
        if ticket.status not in ("in_progress", "pending_customer", "escalated"):
            raise ValidationException(message="Can only resolve tickets in 'in_progress', 'pending_customer' or 'escalated' status")
        if satisfaction_score < 0 or satisfaction_score > 5:
            raise ValidationException(message="Satisfaction score must be between 0 and 5")
        ticket.resolution = resolution
        ticket.satisfaction_score = satisfaction_score
        ticket.resolved_at = datetime.now(UTC)
        ticket.status = "resolved"
        if self._ticket_repo:
            return await self._ticket_repo.update(ticket)
        await self._session.flush()
        return ticket

    async def get_overdue_tickets(self, tenant_id: str) -> list[ServiceTicket]:
        now = datetime.now(UTC)
        stmt = select(ServiceTicket).where(
            ServiceTicket.tenant_id == tenant_id,
            ServiceTicket.sla_due_at < now,
            ServiceTicket.status.in_(["open", "in_progress", "pending_customer", "escalated"]),
        ).order_by(ServiceTicket.sla_due_at.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ReturnRefundService:
    """退货退款应用服务 - 管理退货退款单据创建和状态流转"""

    def __init__(self, session: AsyncSession, return_refund_repo: ReturnRefundRepository | None = None):
        self._session = session
        self._return_refund_repo = return_refund_repo

    async def create(self, tenant_id: str, return_no: str, order_id: str,
                     customer_id: str, sku_id: str, return_type: str = "return",
                     quantity: int = 1, refund_amount: float = 0.0, **kwargs) -> ReturnRefund:
        if return_type not in ("return", "refund_only", "exchange"):
            raise ValidationException(message=f"Invalid return type '{return_type}'")
        if quantity <= 0:
            raise ValidationException(message="Quantity must be positive")
        if refund_amount < 0:
            raise ValidationException(message="Refund amount cannot be negative")
        if self._return_refund_repo:
            existing = await self._return_refund_repo.get_by_return_no(return_no, tenant_id)
        else:
            stmt = select(ReturnRefund).where(
                ReturnRefund.return_no == return_no, ReturnRefund.tenant_id == tenant_id
            )
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Return no '{return_no}' already exists")
        rr = ReturnRefund(
            tenant_id=tenant_id, return_no=return_no, order_id=order_id,
            customer_id=customer_id, sku_id=sku_id, return_type=return_type,
            quantity=quantity, refund_amount=refund_amount,
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(ReturnRefund, k)},
        )
        if self._return_refund_repo:
            return await self._return_refund_repo.create(rr)
        self._session.add(rr)
        await self._session.flush()
        return rr

    async def get_by_id(self, rr_id: str, tenant_id: str = "") -> ReturnRefund | None:
        if self._return_refund_repo and tenant_id:
            return await self._return_refund_repo.get_by_id(rr_id, tenant_id)
        stmt = select(ReturnRefund).where(ReturnRefund.id == rr_id)
        if tenant_id:
            stmt = stmt.where(ReturnRefund.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str | None = None,
                             order_id: str | None = None,
                             offset: int = 0, limit: int = 20) -> list[ReturnRefund]:
        stmt = select(ReturnRefund).where(ReturnRefund.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(ReturnRefund.status == status)
        if order_id:
            stmt = stmt.where(ReturnRefund.order_id == order_id)
        stmt = stmt.order_by(ReturnRefund.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_customer(self, customer_id: str, tenant_id: str) -> list[ReturnRefund]:
        stmt = select(ReturnRefund).where(
            ReturnRefund.customer_id == customer_id,
            ReturnRefund.tenant_id == tenant_id,
        ).order_by(ReturnRefund.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, rr_id: str, tenant_id: str, new_status: str) -> ReturnRefund:
        rr = await self.get_by_id(rr_id, tenant_id)
        if not rr:
            raise NotFoundException(message=f"Return/refund '{rr_id}' not found")
        allowed = RETURN_STATUS_TRANSITIONS.get(rr.status, [])
        if new_status not in allowed:
            raise ValidationException(
                message=f"Cannot transition return/refund from '{rr.status}' to '{new_status}'"
            )
        rr.status = new_status
        if new_status == "received":
            rr.received_at = datetime.now(UTC)
        elif new_status == "refunded":
            rr.refunded_at = datetime.now(UTC)
        if self._return_refund_repo:
            return await self._return_refund_repo.update(rr)
        await self._session.flush()
        return rr


class ComplaintService:
    """投诉应用服务 - 管理投诉创建、状态流转、升级和解决"""

    def __init__(self, session: AsyncSession, complaint_repo: ComplaintRepository | None = None):
        self._session = session
        self._complaint_repo = complaint_repo

    async def create(self, tenant_id: str, complaint_no: str, customer_id: str,
                     complaint_type: str, severity: str = "medium",
                     subject: str = "", **kwargs) -> Complaint:
        errors = ComplaintDomainService.validate_complaint(complaint_type, severity)
        if errors:
            raise ValidationException(message="; ".join(errors))
        if self._complaint_repo:
            existing = await self._complaint_repo.get_by_complaint_no(complaint_no, tenant_id)
        else:
            stmt = select(Complaint).where(
                Complaint.complaint_no == complaint_no, Complaint.tenant_id == tenant_id
            )
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Complaint '{complaint_no}' already exists")
        complaint = Complaint(
            tenant_id=tenant_id, complaint_no=complaint_no, customer_id=customer_id,
            complaint_type=complaint_type, severity=severity, subject=subject,
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(Complaint, k)},
        )
        if ComplaintDomainService.requires_escalation(severity, complaint_type):
            complaint.status = "escalated"
        if self._complaint_repo:
            return await self._complaint_repo.create(complaint)
        self._session.add(complaint)
        await self._session.flush()
        return complaint

    async def get_by_id(self, complaint_id: str, tenant_id: str) -> Complaint | None:
        if self._complaint_repo:
            return await self._complaint_repo.get_by_id(complaint_id, tenant_id)
        stmt = select(Complaint).where(Complaint.id == complaint_id, Complaint.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_all(self, tenant_id: str, status: str = "", severity: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[Complaint], int]:
        if self._complaint_repo:
            return await self._complaint_repo.list_by_tenant(tenant_id, status=status, severity=severity,
                                                              page=page, page_size=page_size)
        conditions = [Complaint.tenant_id == tenant_id]
        if status:
            conditions.append(Complaint.status == status)
        if severity:
            conditions.append(Complaint.severity == severity)
        total = (await self._session.execute(select(func.count()).select_from(Complaint).where(*conditions))).scalar() or 0
        stmt = select(Complaint).where(*conditions).order_by(Complaint.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def update_status(self, complaint_id: str, tenant_id: str, new_status: str) -> Complaint:
        complaint = await self.get_by_id(complaint_id, tenant_id)
        if not complaint:
            raise NotFoundException(message=f"Complaint '{complaint_id}' not found")
        if not ComplaintDomainService.can_transition(complaint.status, new_status):
            raise ValidationException(
                message=f"Cannot transition complaint from '{complaint.status}' to '{new_status}'"
            )
        complaint.status = new_status
        if new_status == "resolved":
            complaint.resolved_at = datetime.now(UTC)
        elif new_status == "closed":
            complaint.closed_at = datetime.now(UTC)
        if self._complaint_repo:
            return await self._complaint_repo.update(complaint)
        await self._session.flush()
        return complaint

    async def resolve(self, complaint_id: str, tenant_id: str, resolution: str,
                      resolution_type: str, satisfaction_score: int = 0) -> Complaint:
        complaint = await self.get_by_id(complaint_id, tenant_id)
        if not complaint:
            raise NotFoundException(message=f"Complaint '{complaint_id}' not found")
        if complaint.status not in ("investigating", "escalated"):
            raise ValidationException(message="Complaint must be in 'investigating' or 'escalated' status to resolve")
        if resolution_type not in ("refund", "replacement", "apology", "credit", "other"):
            raise ValidationException(message=f"Invalid resolution type '{resolution_type}'")
        complaint.resolution = resolution
        complaint.resolution_type = resolution_type
        complaint.satisfaction_score = satisfaction_score
        complaint.resolved_at = datetime.now(UTC)
        complaint.status = "resolved"
        if self._complaint_repo:
            return await self._complaint_repo.update(complaint)
        await self._session.flush()
        return complaint

    async def escalate(self, complaint_id: str, tenant_id: str, escalated_to: str) -> Complaint:
        complaint = await self.get_by_id(complaint_id, tenant_id)
        if not complaint:
            raise NotFoundException(message=f"Complaint '{complaint_id}' not found")
        if complaint.status not in ("investigating", "submitted"):
            raise ValidationException(message="Complaint must be in 'investigating' or 'submitted' status to escalate")
        complaint.escalated_to = escalated_to
        complaint.status = "escalated"
        if self._complaint_repo:
            return await self._complaint_repo.update(complaint)
        await self._session.flush()
        return complaint


class ReviewReplyTemplateService:
    """评价回复模板应用服务 - 管理回复模板的创建、渲染和推荐"""

    def __init__(self, session: AsyncSession, template_repo: ReviewReplyTemplateRepository | None = None):
        self._session = session
        self._template_repo = template_repo

    async def create(self, tenant_id: str, name: str, category: str,
                     content_template: str, **kwargs) -> ReviewReplyTemplate:
        if category not in ("general", "positive", "negative", "neutral", "complaint"):
            raise ValidationException(message=f"Invalid template category '{category}'")
        errors = ReviewReplyTemplateDomainService.validate_template(content_template)
        if errors:
            raise ValidationException(message="; ".join(errors))
        template = ReviewReplyTemplate(
            tenant_id=tenant_id, name=name, category=category,
            content_template=content_template,
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(ReviewReplyTemplate, k)},
        )
        if self._template_repo:
            return await self._template_repo.create(template)
        self._session.add(template)
        await self._session.flush()
        return template

    async def get_by_id(self, template_id: str, tenant_id: str) -> ReviewReplyTemplate | None:
        if self._template_repo:
            return await self._template_repo.get_by_id(template_id, tenant_id)
        stmt = select(ReviewReplyTemplate).where(
            ReviewReplyTemplate.id == template_id, ReviewReplyTemplate.tenant_id == tenant_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_all(self, tenant_id: str, category: str = "", language: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[ReviewReplyTemplate], int]:
        if self._template_repo:
            return await self._template_repo.list_by_tenant(tenant_id, category=category,
                                                             language=language, page=page, page_size=page_size)
        conditions = [ReviewReplyTemplate.tenant_id == tenant_id, ReviewReplyTemplate.status == "active"]
        if category:
            conditions.append(ReviewReplyTemplate.category == category)
        if language:
            conditions.append(ReviewReplyTemplate.language == language)
        total = (await self._session.execute(select(func.count()).select_from(ReviewReplyTemplate).where(*conditions))).scalar() or 0
        stmt = select(ReviewReplyTemplate).where(*conditions).order_by(ReviewReplyTemplate.name).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def render(self, template_id: str, tenant_id: str, variables: dict[str, str]) -> str:
        template = await self.get_by_id(template_id, tenant_id)
        if not template:
            raise NotFoundException(message=f"Template '{template_id}' not found")
        template.usage_count += 1
        if self._template_repo:
            await self._template_repo.update(template)
        else:
            await self._session.flush()
        return ReviewReplyTemplateDomainService.render_template(template.content_template, variables)

    async def suggest_template(self, tenant_id: str, rating: int,
                                language: str = "en", platform: str = "") -> list[ReviewReplyTemplate]:
        category = ReviewReplyTemplateDomainService.match_template_category(rating)
        conditions = [
            ReviewReplyTemplate.tenant_id == tenant_id,
            ReviewReplyTemplate.status == "active",
        ]
        category_filter = [ReviewReplyTemplate.category == category, ReviewReplyTemplate.category == "general"]
        conditions.append(category_filter[0] | category_filter[1])
        if language:
            conditions.append(ReviewReplyTemplate.language == language)
        if platform:
            conditions.append((ReviewReplyTemplate.platform == platform) | (ReviewReplyTemplate.platform == ""))
        stmt = select(ReviewReplyTemplate).where(*conditions).order_by(
            ReviewReplyTemplate.is_default.desc(), ReviewReplyTemplate.usage_count.desc()
        ).limit(5)
        return list((await self._session.execute(stmt)).scalars().all())


class CRMQueryService:
    """
    CRM 统计查询服务

    提供CRM模块的运营统计概览、各子域统计数据聚合。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_statistics(self, tenant_id: str) -> dict:
        """获取CRM运营统计概览"""
        total_customers = (await self._session.execute(
            select(func.count()).select_from(Customer).where(Customer.tenant_id == tenant_id)
        )).scalar() or 0

        active_customers = (await self._session.execute(
            select(func.count()).select_from(Customer)
            .where(Customer.tenant_id == tenant_id, Customer.status == "active")
        )).scalar() or 0

        by_platform_rows = (await self._session.execute(
            select(Customer.platform, func.count())
            .where(Customer.tenant_id == tenant_id)
            .group_by(Customer.platform)
        )).all()
        customers_by_platform = {r[0] or "unknown": r[1] for r in by_platform_rows}

        by_segment_rows = (await self._session.execute(
            select(Customer.segment, func.count())
            .where(Customer.tenant_id == tenant_id)
            .group_by(Customer.segment)
        )).all()
        customers_by_segment = {r[0] or "unknown": r[1] for r in by_segment_rows}

        total_tickets = (await self._session.execute(
            select(func.count()).select_from(ServiceTicket).where(ServiceTicket.tenant_id == tenant_id)
        )).scalar() or 0

        open_tickets = (await self._session.execute(
            select(func.count()).select_from(ServiceTicket)
            .where(ServiceTicket.tenant_id == tenant_id,
                   ServiceTicket.status.in_(["open", "in_progress", "pending_customer", "escalated"]))
        )).scalar() or 0

        overdue_tickets = (await self._session.execute(
            select(func.count()).select_from(ServiceTicket)
            .where(ServiceTicket.tenant_id == tenant_id,
                   ServiceTicket.sla_due_at < datetime.now(UTC),
                   ServiceTicket.status.notin_(["resolved", "closed", "cancelled"]))
        )).scalar() or 0

        total_returns = (await self._session.execute(
            select(func.count()).select_from(ReturnRefund).where(ReturnRefund.tenant_id == tenant_id)
        )).scalar() or 0

        pending_returns = (await self._session.execute(
            select(func.count()).select_from(ReturnRefund)
            .where(ReturnRefund.tenant_id == tenant_id, ReturnRefund.status.in_(["requested", "approved"]))
        )).scalar() or 0

        total_refund_amount = (await self._session.execute(
            select(func.coalesce(func.sum(ReturnRefund.refund_amount), 0))
            .where(ReturnRefund.tenant_id == tenant_id, ReturnRefund.status.in_(["refunded", "completed"]))
        )).scalar() or 0

        total_reviews = (await self._session.execute(
            select(func.count()).select_from(Review).where(Review.tenant_id == tenant_id)
        )).scalar() or 0

        negative_reviews = (await self._session.execute(
            select(func.count()).select_from(Review)
            .where(Review.tenant_id == tenant_id, Review.is_negative == True)
        )).scalar() or 0

        unreplied_reviews = (await self._session.execute(
            select(func.count()).select_from(Review)
            .where(Review.tenant_id == tenant_id, Review.reply == "", Review.status == "pending")
        )).scalar() or 0

        total_complaints = (await self._session.execute(
            select(func.count()).select_from(Complaint).where(Complaint.tenant_id == tenant_id)
        )).scalar() or 0

        open_complaints = (await self._session.execute(
            select(func.count()).select_from(Complaint)
            .where(Complaint.tenant_id == tenant_id, Complaint.status.in_(["open", "investigating", "escalated"]))
        )).scalar() or 0

        return {
            "total_customers": total_customers,
            "active_customers": active_customers,
            "customers_by_platform": customers_by_platform,
            "customers_by_segment": customers_by_segment,
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "overdue_tickets": overdue_tickets,
            "total_returns": total_returns,
            "pending_returns": pending_returns,
            "total_refund_amount": float(total_refund_amount),
            "total_reviews": total_reviews,
            "negative_reviews": negative_reviews,
            "unreplied_reviews": unreplied_reviews,
            "total_complaints": total_complaints,
            "open_complaints": open_complaints,
        }

    async def search_customers(self, tenant_id: str, keyword: str = "", platform: str = "",
                                segment: str = "", status: str = "", country: str = "",
                                page: int = 1, page_size: int = 20) -> tuple[list[Customer], int]:
        """多维度搜索客户"""
        conditions = [Customer.tenant_id == tenant_id]
        if keyword:
            conditions.append(
                (Customer.customer_no.contains(keyword) | Customer.name.contains(keyword) | Customer.email.contains(keyword))
            )
        if platform:
            conditions.append(Customer.platform == platform)
        if segment:
            conditions.append(Customer.segment == segment)
        if status:
            conditions.append(Customer.status == status)
        if country:
            conditions.append(Customer.country == country)
        total = (await self._session.execute(
            select(func.count()).select_from(Customer).where(*conditions)
        )).scalar() or 0
        stmt = select(Customer).where(*conditions).order_by(
            Customer.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total


class CustomerProfileService:
    """
    客户画像服务

    构建客户360度画像: 基础信息/消费行为/偏好标签/互动历史/价值评分
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_customer_360(self, tenant_id: str, customer_id: str) -> dict:
        """获取客户360度画像"""
        customer = (await self._session.execute(
            select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not customer:
            raise NotFoundException(message=f"Customer '{customer_id}' not found")
        communications = (await self._session.execute(
            select(Communication).where(
                Communication.tenant_id == tenant_id, Communication.customer_id == customer_id
            ).order_by(Communication.created_at.desc()).limit(10)
        )).scalars().all()
        tickets = (await self._session.execute(
            select(ServiceTicket).where(
                ServiceTicket.tenant_id == tenant_id, ServiceTicket.customer_id == customer_id
            ).order_by(ServiceTicket.created_at.desc()).limit(10)
        )).scalars().all()
        reviews = (await self._session.execute(
            select(Review).where(
                Review.tenant_id == tenant_id, Review.customer_id == customer_id
            ).order_by(Review.created_at.desc()).limit(10)
        )).scalars().all()
        return {
            "basic_info": {
                "customer_id": str(customer.id), "customer_no": customer.customer_no,
                "name": customer.name, "email": customer.email, "phone": customer.phone,
                "segment": customer.segment, "status": customer.status,
                "source": customer.source, "platform": customer.platform,
            },
            "purchase_behavior": {
                "total_orders": customer.total_orders, "total_amount": round(customer.total_amount, 2),
                "avg_order_value": round(customer.avg_order_value, 2) if customer.avg_order_value else 0,
                "first_order_at": customer.first_order_at.isoformat() if customer.first_order_at else None,
                "last_order_at": customer.last_order_at.isoformat() if customer.last_order_at else None,
            },
            "recent_communications": len(communications),
            "open_tickets": sum(1 for t in tickets if t.status in ("open", "in_progress")),
            "review_count": len(reviews),
            "avg_review_rating": round(sum(r.rating for r in reviews if r.rating) / len(reviews), 1) if reviews else 0,
        }

    async def batch_build_profiles(self, tenant_id: str, segment: str = "") -> dict:
        """批量构建客户画像"""
        conditions = [Customer.tenant_id == tenant_id, Customer.status == "active"]
        if segment:
            conditions.append(Customer.segment == segment)
        customers = (await self._session.execute(
            select(Customer).where(*conditions)
        )).scalars().all()
        segment_dist: dict[str, int] = {}
        for c in customers:
            seg = c.segment or "unsegmented"
            segment_dist[seg] = segment_dist.get(seg, 0) + 1
        return {
            "total_customers": len(customers), "segment_distribution": segment_dist,
        }


class ChurnPredictionService:
    """
    客户流失预警服务

    基于行为特征预测客户流失概率: 活跃度衰减/购买间隔延长/投诉增加 → 流失评分
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def predict_churn_risk(self, tenant_id: str, customer_id: str) -> dict:
        """预测客户流失风险"""
        from datetime import UTC, datetime, timedelta
        customer = (await self._session.execute(
            select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not customer:
            raise NotFoundException(message=f"Customer '{customer_id}' not found")
        churn_score = 0
        risk_factors = []
        now = datetime.now(UTC)
        if customer.last_order_at:
            days_since_last = (now - customer.last_order_at).days
            if days_since_last > 180:
                churn_score += 40
                risk_factors.append({"factor": "long_inactive", "days": days_since_last, "weight": 40})
            elif days_since_last > 90:
                churn_score += 25
                risk_factors.append({"factor": "declining_activity", "days": days_since_last, "weight": 25})
            elif days_since_last > 60:
                churn_score += 10
                risk_factors.append({"factor": "slight_decline", "days": days_since_last, "weight": 10})
        recent_tickets = (await self._session.execute(
            select(func.count()).select_from(ServiceTicket).where(
                ServiceTicket.tenant_id == tenant_id, ServiceTicket.customer_id == customer_id,
                ServiceTicket.status.in_(["open", "in_progress"]),
                ServiceTicket.created_at >= now - timedelta(days=30),
            )
        )).scalar() or 0
        if recent_tickets >= 3:
            churn_score += 20
            risk_factors.append({"factor": "high_complaints", "count": recent_tickets, "weight": 20})
        elif recent_tickets >= 1:
            churn_score += 5
            risk_factors.append({"factor": "recent_complaint", "count": recent_tickets, "weight": 5})
        if customer.total_orders and customer.total_orders <= 1:
            churn_score += 15
            risk_factors.append({"factor": "low_retention", "orders": customer.total_orders, "weight": 15})
        churn_score = min(churn_score, 100)
        risk_level = "critical" if churn_score >= 70 else "high" if churn_score >= 50 else "medium" if churn_score >= 30 else "low"
        return {
            "customer_id": customer_id, "churn_score": churn_score,
            "risk_level": risk_level, "risk_factors": risk_factors,
            "recommendation": self._get_retention_action(risk_level),
        }

    async def scan_high_risk_customers(self, tenant_id: str, threshold: int = 50) -> list[dict]:
        """扫描高流失风险客户"""
        customers = (await self._session.execute(
            select(Customer).where(Customer.tenant_id == tenant_id, Customer.status == "active")
        )).scalars().all()
        high_risk = []
        for c in customers:
            prediction = await self.predict_churn_risk(tenant_id, str(c.id))
            if prediction["churn_score"] >= threshold:
                high_risk.append(prediction)
        high_risk.sort(key=lambda x: x["churn_score"], reverse=True)
        return high_risk

    def _get_retention_action(self, risk_level: str) -> str:
        actions = {
            "critical": "立即人工关怀触达，提供专属优惠",
            "high": "发送挽回邮件+优惠券",
            "medium": "定期推送个性化推荐",
            "low": "维持正常运营节奏",
        }
        return actions.get(risk_level, "")


class RFMAnalysisService:
    """
    RFM分析应用服务

    基于Recency(最近购买)、Frequency(购买频率)、Monetary(消费金额)三维模型
    对客户进行价值分群，支持自定义分群阈值和自动化分群。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def calculate_rfm_scores(self, tenant_id: str, customer_id: str) -> dict:
        """
        计算单个客户的RFM得分

        R(Recency): 距离最近一次购买的天数，越短得分越高
        F(Frequency): 累计订单数，越多得分越高
        M(Monetary): 累计消费金额，越高得分越高
        """
        from datetime import UTC, datetime
        stmt = select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        customer = (await self._session.execute(stmt)).scalar_one_or_none()
        if not customer:
            raise NotFoundException(message=f"Customer '{customer_id}' not found")
        now = datetime.now(UTC)
        if customer.last_order_at:
            recency_days = (now - customer.last_order_at).days
        else:
            recency_days = 999
        r_score = 5
        if recency_days > 180:
            r_score = 1
        elif recency_days > 90:
            r_score = 2
        elif recency_days > 60:
            r_score = 3
        elif recency_days > 30:
            r_score = 4
        frequency = customer.total_orders
        f_score = 1
        if frequency >= 20:
            f_score = 5
        elif frequency >= 10:
            f_score = 4
        elif frequency >= 5:
            f_score = 3
        elif frequency >= 2:
            f_score = 2
        monetary = customer.total_amount
        m_score = 1
        if monetary >= 10000:
            m_score = 5
        elif monetary >= 5000:
            m_score = 4
        elif monetary >= 1000:
            m_score = 3
        elif monetary >= 200:
            m_score = 2
        rfm_score = r_score * 100 + f_score * 10 + m_score
        segment = self._classify_segment(r_score, f_score, m_score)
        return {
            "customer_id": customer_id, "customer_no": customer.customer_no,
            "recency_days": recency_days, "frequency": frequency,
            "monetary": round(monetary, 2),
            "r_score": r_score, "f_score": f_score, "m_score": m_score,
            "rfm_score": rfm_score, "segment": segment,
        }

    async def batch_analyze(self, tenant_id: str, page: int = 1,
                            page_size: int = 100) -> dict:
        """批量RFM分析"""
        stmt = select(Customer).where(
            Customer.tenant_id == tenant_id, Customer.status == "active",
        ).offset((page - 1) * page_size).limit(page_size)
        customers = list((await self._session.execute(stmt)).scalars().all())
        results = []
        segment_counts: dict[str, int] = {}
        for c in customers:
            rfm = await self.calculate_rfm_scores(tenant_id, str(c.id))
            results.append(rfm)
            seg = rfm["segment"]
            segment_counts[seg] = segment_counts.get(seg, 0) + 1
            c.segment = seg
        if results:
            await self._session.flush()
        return {
            "total_analyzed": len(results),
            "segment_distribution": segment_counts,
            "results": results,
        }

    async def get_segment_overview(self, tenant_id: str) -> dict:
        """获取客户分群概览"""
        from sqlalchemy import func as sa_func
        stmt = select(Customer.segment, sa_func.count()).where(
            Customer.tenant_id == tenant_id, Customer.status == "active",
        ).group_by(Customer.segment)
        rows = list((await self._session.execute(stmt)).all())
        distribution = {row[0]: row[1] for row in rows}
        total = sum(distribution.values())
        return {
            "total_customers": total,
            "segment_distribution": distribution,
            "segment_percentages": {k: round(v / total * 100, 1) for k, v in distribution.items()} if total > 0 else {},
        }

    def _classify_segment(self, r: int, f: int, m: int) -> str:
        """根据RFM得分分类客户"""
        if r >= 4 and f >= 4 and m >= 4:
            return "vip"
        elif r >= 3 and f >= 3 and m >= 3:
            return "high_value"
        elif r >= 3 and f < 3:
            return "new_potential"
        elif r < 3 and f >= 3:
            return "at_risk"
        elif r < 2 and f < 2:
            return "churned"
        else:
            return "normal"


class CustomerLifecycleService:
    """
    客户生命周期管理应用服务

    编排客户从获客→激活→留存→流失的完整生命周期管理:
    - 自动识别生命周期阶段
    - 触发阶段转换事件
    - 生成客户挽留策略
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def identify_lifecycle_stage(self, tenant_id: str, customer_id: str) -> dict:
        """识别客户生命周期阶段"""
        from datetime import UTC, datetime, timedelta
        stmt = select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        customer = (await self._session.execute(stmt)).scalar_one_or_none()
        if not customer:
            raise NotFoundException(message=f"Customer '{customer_id}' not found")
        now = datetime.now(UTC)
        if not customer.first_order_at:
            stage = "prospect"
        elif customer.total_orders == 1:
            days_since_first = (now - customer.first_order_at).days
            if days_since_first <= 30:
                stage = "new"
            else:
                stage = "one_time"
        elif customer.last_order_at:
            days_since_last = (now - customer.last_order_at).days
            if days_since_last <= 30:
                stage = "active"
            elif days_since_last <= 90:
                stage = "declining"
            elif days_since_last <= 180:
                stage = "at_risk"
            else:
                stage = "churned"
        else:
            stage = "inactive"
        return {
            "customer_id": customer_id, "customer_no": customer.customer_no,
            "lifecycle_stage": stage,
            "total_orders": customer.total_orders,
            "total_amount": round(customer.total_amount, 2),
            "days_since_last_order": (now - customer.last_order_at).days if customer.last_order_at else None,
            "segment": customer.segment,
        }

    async def get_lifecycle_distribution(self, tenant_id: str) -> dict:
        """获取客户生命周期分布"""
        from datetime import UTC, datetime, timedelta
        now = datetime.now(UTC)
        stmt = select(Customer).where(Customer.tenant_id == tenant_id, Customer.status == "active")
        customers = list((await self._session.execute(stmt)).scalars().all())
        distribution: dict[str, int] = {
            "prospect": 0, "new": 0, "active": 0,
            "declining": 0, "at_risk": 0, "churned": 0,
            "one_time": 0, "inactive": 0,
        }
        for c in customers:
            if not c.first_order_at:
                distribution["prospect"] += 1
            elif c.total_orders == 1:
                days = (now - c.first_order_at).days
                if days <= 30:
                    distribution["new"] += 1
                else:
                    distribution["one_time"] += 1
            elif c.last_order_at:
                days = (now - c.last_order_at).days
                if days <= 30:
                    distribution["active"] += 1
                elif days <= 90:
                    distribution["declining"] += 1
                elif days <= 180:
                    distribution["at_risk"] += 1
                else:
                    distribution["churned"] += 1
            else:
                distribution["inactive"] += 1
        total = sum(distribution.values())
        return {
            "total_customers": total,
            "distribution": distribution,
            "percentages": {k: round(v / total * 100, 1) for k, v in distribution.items()} if total > 0 else {},
        }

    async def generate_retention_strategies(self, tenant_id: str, stage: str) -> list[dict]:
        """根据生命周期阶段生成挽留策略"""
        strategies = {
            "prospect": [
                {"strategy": "first_purchase_discount", "description": "首单优惠吸引转化", "priority": "high"},
                {"strategy": "welcome_series", "description": "欢迎邮件系列", "priority": "medium"},
            ],
            "new": [
                {"strategy": "second_purchase_incentive", "description": "复购激励", "priority": "high"},
                {"strategy": "product_recommendation", "description": "个性化产品推荐", "priority": "medium"},
            ],
            "declining": [
                {"strategy": "win_back_campaign", "description": "挽回营销活动", "priority": "high"},
                {"strategy": "exclusive_offer", "description": "专属优惠", "priority": "high"},
            ],
            "at_risk": [
                {"strategy": "personal_outreach", "description": "人工关怀触达", "priority": "critical"},
                {"strategy": "loyalty_reward", "description": "忠诚度奖励", "priority": "high"},
            ],
            "churned": [
                {"strategy": "reactivation_campaign", "description": "重新激活营销", "priority": "medium"},
                {"strategy": "survey_feedback", "description": "流失原因调研", "priority": "low"},
            ],
        }
        return strategies.get(stage, [])

    async def search_tickets(self, tenant_id: str, keyword: str = "", status: str = "",
                              ticket_type: str = "", priority: str = "", assigned_to: str = "",
                              page: int = 1, page_size: int = 20) -> tuple[list[ServiceTicket], int]:
        """多维度搜索工单"""
        conditions = [ServiceTicket.tenant_id == tenant_id]
        if keyword:
            conditions.append(
                (ServiceTicket.ticket_no.contains(keyword) | ServiceTicket.subject.contains(keyword))
            )
        if status:
            conditions.append(ServiceTicket.status == status)
        if ticket_type:
            conditions.append(ServiceTicket.ticket_type == ticket_type)
        if priority:
            conditions.append(ServiceTicket.priority == priority)
        if assigned_to:
            conditions.append(ServiceTicket.assigned_to == assigned_to)
        total = (await self._session.execute(
            select(func.count()).select_from(ServiceTicket).where(*conditions)
        )).scalar() or 0
        stmt = select(ServiceTicket).where(*conditions).order_by(
            ServiceTicket.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total
