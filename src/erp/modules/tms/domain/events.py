from __future__ import annotations

from dataclasses import dataclass

from erp.shared.events.domain_event import DomainEvent


@dataclass
class ShipmentCreated(DomainEvent):
    shipment_id: str = ""
    shipment_no: str = ""
    order_id: str = ""
    provider_id: str = ""
    shipping_cost: float = 0.0

    def __post_init__(self):
        self.event_type = "erp.tms.shipment.created.v1"
        self.domain = "tms"
        self.aggregate_type = "shipment"


@dataclass
class ShipmentStatusChanged(DomainEvent):
    shipment_id: str = ""
    shipment_no: str = ""
    from_status: str = ""
    to_status: str = ""

    def __post_init__(self):
        self.event_type = "erp.tms.shipment.status_changed.v1"
        self.domain = "tms"
        self.aggregate_type = "shipment"


@dataclass
class ShipmentTrackingUpdated(DomainEvent):
    shipment_id: str = ""
    shipment_no: str = ""
    tracking_no: str = ""
    carrier: str = ""

    def __post_init__(self):
        self.event_type = "erp.tms.shipment.tracking_updated.v1"
        self.domain = "tms"
        self.aggregate_type = "shipment"


@dataclass
class LogisticsProviderCreated(DomainEvent):
    provider_id: str = ""
    provider_code: str = ""
    provider_type: str = ""

    def __post_init__(self):
        self.event_type = "erp.tms.provider.created.v1"
        self.domain = "tms"
        self.aggregate_type = "logistics_provider"
