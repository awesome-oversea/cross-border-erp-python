from __future__ import annotations

from dataclasses import dataclass

from erp.shared.events.domain_event import DomainEvent


@dataclass
class ListingCreated(DomainEvent):
    listing_id: str = ""
    store_id: str = ""
    sku_id: str = ""
    price: float = 0.0
    currency: str = "USD"

    def __post_init__(self):
        self.event_type = "erp.som.listing.created.v1"
        self.domain = "som"
        self.aggregate_type = "listing"


@dataclass
class ListingStatusChanged(DomainEvent):
    listing_id: str = ""
    from_status: str = ""
    to_status: str = ""

    def __post_init__(self):
        self.event_type = "erp.som.listing.status_changed.v1"
        self.domain = "som"
        self.aggregate_type = "listing"


@dataclass
class ListingPriceUpdated(DomainEvent):
    listing_id: str = ""
    old_price: float = 0.0
    new_price: float = 0.0
    currency: str = "USD"

    def __post_init__(self):
        self.event_type = "erp.som.listing.price_updated.v1"
        self.domain = "som"
        self.aggregate_type = "listing"


@dataclass
class StoreCreated(DomainEvent):
    store_id: str = ""
    store_code: str = ""
    platform: str = ""
    region: str = ""

    def __post_init__(self):
        self.event_type = "erp.som.store.created.v1"
        self.domain = "som"
        self.aggregate_type = "store"


@dataclass
class StoreAuthStatusChanged(DomainEvent):
    store_id: str = ""
    store_code: str = ""
    from_status: str = ""
    to_status: str = ""

    def __post_init__(self):
        self.event_type = "erp.som.store.auth_status_changed.v1"
        self.domain = "som"
        self.aggregate_type = "store"


@dataclass
class ListingOptimizationCreated(DomainEvent):
    optimization_id: str = ""
    listing_id: str = ""
    opt_type: str = ""

    def __post_init__(self):
        self.event_type = "erp.som.listing_optimization.created.v1"
        self.domain = "som"
        self.aggregate_type = "listing_optimization"


@dataclass
class ListingOptimizationApplied(DomainEvent):
    optimization_id: str = ""
    listing_id: str = ""
    opt_type: str = ""
    score_before: float = 0.0
    score_after: float = 0.0

    def __post_init__(self):
        self.event_type = "erp.som.listing_optimization.applied.v1"
        self.domain = "som"
        self.aggregate_type = "listing_optimization"


@dataclass
class AlertTriggered(DomainEvent):
    alert_id: str = ""
    rule_id: str = ""
    rule_name: str = ""
    metric_type: str = ""
    severity: str = "warning"

    def __post_init__(self):
        self.event_type = "erp.som.alert.triggered.v1"
        self.domain = "som"
        self.aggregate_type = "alert_record"


@dataclass
class AlertResolved(DomainEvent):
    alert_id: str = ""
    rule_id: str = ""
    rule_name: str = ""

    def __post_init__(self):
        self.event_type = "erp.som.alert.resolved.v1"
        self.domain = "som"
        self.aggregate_type = "alert_record"
