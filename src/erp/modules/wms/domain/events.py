from __future__ import annotations

from dataclasses import dataclass

from erp.shared.events.domain_event import DomainEvent


@dataclass
class InventoryAdjusted(DomainEvent):
    inventory_id: str = ""
    warehouse_id: str = ""
    sku_id: str = ""
    movement_type: str = ""
    qty_change: int = 0
    qty_after: int = 0

    def __post_init__(self):
        self.event_type = "erp.wms.inventory.adjusted.v1"
        self.domain = "wms"
        self.aggregate_type = "inventory"


@dataclass
class LowStockAlert(DomainEvent):
    inventory_id: str = ""
    warehouse_id: str = ""
    sku_id: str = ""
    available_qty: int = 0
    safety_qty: int = 0

    def __post_init__(self):
        self.event_type = "erp.wms.inventory.low_stock_alert.v1"
        self.domain = "wms"
        self.aggregate_type = "inventory"


@dataclass
class InboundReceived(DomainEvent):
    inbound_id: str = ""
    inbound_no: str = ""
    warehouse_id: str = ""
    inbound_type: str = ""

    def __post_init__(self):
        self.event_type = "erp.wms.inbound.received.v1"
        self.domain = "wms"
        self.aggregate_type = "inbound_order"


@dataclass
class OutboundShipped(DomainEvent):
    outbound_id: str = ""
    outbound_no: str = ""
    warehouse_id: str = ""
    outbound_type: str = ""
    tracking_no: str = ""

    def __post_init__(self):
        self.event_type = "erp.wms.outbound.shipped.v1"
        self.domain = "wms"
        self.aggregate_type = "outbound_order"
