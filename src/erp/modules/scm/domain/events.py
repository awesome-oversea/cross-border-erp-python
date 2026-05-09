from __future__ import annotations

from dataclasses import dataclass

from erp.shared.events.domain_event import DomainEvent


@dataclass
class PurchaseOrderCreated(DomainEvent):
    po_id: str = ""
    po_no: str = ""
    supplier_id: str = ""
    warehouse_id: str = ""
    total_amount: float = 0.0

    def __post_init__(self):
        self.event_type = "erp.scm.purchase_order.created.v1"
        self.domain = "scm"
        self.aggregate_type = "purchase_order"


@dataclass
class PurchaseOrderStatusChanged(DomainEvent):
    po_id: str = ""
    po_no: str = ""
    from_status: str = ""
    to_status: str = ""

    def __post_init__(self):
        self.event_type = "erp.scm.purchase_order.status_changed.v1"
        self.domain = "scm"
        self.aggregate_type = "purchase_order"


@dataclass
class SupplierCreated(DomainEvent):
    supplier_id: str = ""
    supplier_code: str = ""
    supplier_type: str = ""

    def __post_init__(self):
        self.event_type = "erp.scm.supplier.created.v1"
        self.domain = "scm"
        self.aggregate_type = "supplier"


@dataclass
class SupplierRatingUpdated(DomainEvent):
    supplier_id: str = ""
    supplier_code: str = ""
    old_rating: float = 0.0
    new_rating: float = 0.0

    def __post_init__(self):
        self.event_type = "erp.scm.supplier.rating_updated.v1"
        self.domain = "scm"
        self.aggregate_type = "supplier"


@dataclass
class ReplenishmentPlanCreated(DomainEvent):
    plan_id: str = ""
    plan_no: str = ""
    warehouse_id: str = ""
    plan_type: str = ""

    def __post_init__(self):
        self.event_type = "erp.scm.replenishment_plan.created.v1"
        self.domain = "scm"
        self.aggregate_type = "replenishment_plan"
