from __future__ import annotations

from dataclasses import dataclass

from erp.shared.events.domain_event import DomainEvent


@dataclass
class CustomerCreated(DomainEvent):
    customer_id: str = ""
    customer_no: str = ""
    platform: str = ""

    def __post_init__(self):
        self.event_type = "erp.crm.customer.created.v1"
        self.domain = "crm"
        self.aggregate_type = "customer"


@dataclass
class CustomerSegmentChanged(DomainEvent):
    customer_id: str = ""
    customer_no: str = ""
    from_segment: str = ""
    to_segment: str = ""

    def __post_init__(self):
        self.event_type = "erp.crm.customer.segment_changed.v1"
        self.domain = "crm"
        self.aggregate_type = "customer"


@dataclass
class ReviewCreated(DomainEvent):
    review_id: str = ""
    platform: str = ""
    store_id: str = ""
    rating: int = 0
    is_negative: bool = False

    def __post_init__(self):
        self.event_type = "erp.crm.review.created.v1"
        self.domain = "crm"
        self.aggregate_type = "review"


@dataclass
class NegativeReviewAlert(DomainEvent):
    review_id: str = ""
    platform: str = ""
    rating: int = 0
    sku_id: str = ""

    def __post_init__(self):
        self.event_type = "erp.crm.review.negative_alert.v1"
        self.domain = "crm"
        self.aggregate_type = "review"


@dataclass
class ServiceTicketCreated(DomainEvent):
    ticket_id: str = ""
    ticket_no: str = ""
    customer_id: str = ""
    ticket_type: str = ""
    priority: str = ""

    def __post_init__(self):
        self.event_type = "erp.crm.ticket.created.v1"
        self.domain = "crm"
        self.aggregate_type = "service_ticket"


@dataclass
class ServiceTicketSLABreach(DomainEvent):
    ticket_id: str = ""
    ticket_no: str = ""
    priority: str = ""
    sla_due_at: str = ""

    def __post_init__(self):
        self.event_type = "erp.crm.ticket.sla_breach.v1"
        self.domain = "crm"
        self.aggregate_type = "service_ticket"


@dataclass
class ReturnRefundCreated(DomainEvent):
    rr_id: str = ""
    return_no: str = ""
    order_id: str = ""
    return_type: str = ""
    refund_amount: float = 0.0

    def __post_init__(self):
        self.event_type = "erp.crm.return_refund.created.v1"
        self.domain = "crm"
        self.aggregate_type = "return_refund"


@dataclass
class ReturnRefundStatusChanged(DomainEvent):
    rr_id: str = ""
    return_no: str = ""
    from_status: str = ""
    to_status: str = ""

    def __post_init__(self):
        self.event_type = "erp.crm.return_refund.status_changed.v1"
        self.domain = "crm"
        self.aggregate_type = "return_refund"
