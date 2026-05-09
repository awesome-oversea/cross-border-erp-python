from __future__ import annotations

from dataclasses import dataclass

from erp.shared.events.domain_event import DomainEvent


@dataclass
class OrderCreated(DomainEvent):
    order_id: str = ""
    order_no: str = ""
    platform: str = ""
    store_id: str = ""
    total_amount: float = 0.0
    currency: str = "USD"

    def __post_init__(self):
        self.event_type = "erp.oms.order.created.v1"
        self.domain = "oms"
        self.aggregate_type = "sales_order"


@dataclass
class OrderStatusChanged(DomainEvent):
    order_id: str = ""
    order_no: str = ""
    from_status: str = ""
    to_status: str = ""
    remark: str = ""

    def __post_init__(self):
        self.event_type = "erp.oms.order.status_changed.v1"
        self.domain = "oms"
        self.aggregate_type = "sales_order"


@dataclass
class OrderItemAdded(DomainEvent):
    order_id: str = ""
    order_no: str = ""
    sku_id: str = ""
    quantity: int = 0
    unit_price: float = 0.0

    def __post_init__(self):
        self.event_type = "erp.oms.order.item_added.v1"
        self.domain = "oms"
        self.aggregate_type = "sales_order"


@dataclass
class OrderCancelled(DomainEvent):
    order_id: str = ""
    order_no: str = ""
    cancel_reason: str = ""

    def __post_init__(self):
        self.event_type = "erp.oms.order.cancelled.v1"
        self.domain = "oms"
        self.aggregate_type = "sales_order"


@dataclass
class RefundCreated(DomainEvent):
    refund_id: str = ""
    refund_no: str = ""
    original_order_id: str = ""
    refund_type: str = ""
    refund_amount: float = 0.0
    currency: str = "USD"

    def __post_init__(self):
        self.event_type = "erp.oms.refund.created.v1"
        self.domain = "oms"
        self.aggregate_type = "refund_order"


@dataclass
class RefundStatusChanged(DomainEvent):
    refund_id: str = ""
    refund_no: str = ""
    from_status: str = ""
    to_status: str = ""

    def __post_init__(self):
        self.event_type = "erp.oms.refund.status_changed.v1"
        self.domain = "oms"
        self.aggregate_type = "refund_order"


@dataclass
class OrderRiskDetected(DomainEvent):
    order_id: str = ""
    order_no: str = ""
    risk_type: str = ""
    risk_level: str = ""
    risk_detail: str = ""

    def __post_init__(self):
        self.event_type = "erp.oms.order.risk_detected.v1"
        self.domain = "oms"
        self.aggregate_type = "sales_order"
