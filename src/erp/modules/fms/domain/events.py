from __future__ import annotations

from dataclasses import dataclass

from erp.shared.events.domain_event import DomainEvent


@dataclass
class CostEventCreated(DomainEvent):
    event_id: str = ""
    event_no: str = ""
    cost_type: str = ""
    amount: float = 0.0
    currency: str = "CNY"
    amount_cny: float = 0.0

    def __post_init__(self):
        self.event_type = "erp.fms.cost_event.created.v1"
        self.domain = "fms"
        self.aggregate_type = "cost_event"


@dataclass
class SettlementCreated(DomainEvent):
    settlement_id: str = ""
    settlement_no: str = ""
    platform: str = ""
    store_id: str = ""
    net_amount: float = 0.0

    def __post_init__(self):
        self.event_type = "erp.fms.settlement.created.v1"
        self.domain = "fms"
        self.aggregate_type = "platform_settlement"


@dataclass
class PaymentCreated(DomainEvent):
    payment_id: str = ""
    payment_no: str = ""
    payment_type: str = ""
    amount: float = 0.0
    currency: str = "CNY"

    def __post_init__(self):
        self.event_type = "erp.fms.payment.created.v1"
        self.domain = "fms"
        self.aggregate_type = "payment_record"


@dataclass
class PaymentStatusChanged(DomainEvent):
    payment_id: str = ""
    payment_no: str = ""
    from_status: str = ""
    to_status: str = ""

    def __post_init__(self):
        self.event_type = "erp.fms.payment.status_changed.v1"
        self.domain = "fms"
        self.aggregate_type = "payment_record"
