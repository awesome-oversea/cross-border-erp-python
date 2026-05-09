from __future__ import annotations

from dataclasses import dataclass

from erp.shared.events.domain_event import DomainEvent


@dataclass
class FbaShipmentCreated(DomainEvent):
    shipment_pk: str = ""
    shipment_id: str = ""
    platform: str = "amazon"
    store_id: str = ""
    total_units: int = 0

    def __post_init__(self):
        self.event_type = "erp.fba.shipment.created.v1"
        self.domain = "fba"
        self.aggregate_type = "fba_shipment"


@dataclass
class FbaShipmentStatusChanged(DomainEvent):
    shipment_pk: str = ""
    shipment_id: str = ""
    from_status: str = ""
    to_status: str = ""

    def __post_init__(self):
        self.event_type = "erp.fba.shipment.status_changed.v1"
        self.domain = "fba"
        self.aggregate_type = "fba_shipment"


@dataclass
class FbaShipmentReceived(DomainEvent):
    shipment_pk: str = ""
    shipment_id: str = ""
    received_units: int = 0
    actual_cost: float = 0.0

    def __post_init__(self):
        self.event_type = "erp.fba.shipment.received.v1"
        self.domain = "fba"
        self.aggregate_type = "fba_shipment"


@dataclass
class FbaInventoryAdjusted(DomainEvent):
    inventory_id: str = ""
    sku_id: str = ""
    store_id: str = ""
    field: str = ""
    delta: int = 0

    def __post_init__(self):
        self.event_type = "erp.fba.inventory.adjusted.v1"
        self.domain = "fba"
        self.aggregate_type = "fba_inventory"


@dataclass
class FbaLowStockAlert(DomainEvent):
    inventory_id: str = ""
    sku_id: str = ""
    store_id: str = ""
    qty_fulfillable: int = 0

    def __post_init__(self):
        self.event_type = "erp.fba.inventory.low_stock_alert.v1"
        self.domain = "fba"
        self.aggregate_type = "fba_inventory"
