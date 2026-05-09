from __future__ import annotations

from dataclasses import dataclass

from erp.shared.events.domain_event import DomainEvent


@dataclass
class SPUCreated(DomainEvent):
    spu_id: str = ""
    spu_code: str = ""
    name: str = ""
    category_id: str = ""

    def __post_init__(self):
        self.event_type = "erp.pdm.spu.created.v1"
        self.domain = "pdm"
        self.aggregate_type = "spu"


@dataclass
class SPUStatusChanged(DomainEvent):
    spu_id: str = ""
    spu_code: str = ""
    from_status: str = ""
    to_status: str = ""

    def __post_init__(self):
        self.event_type = "erp.pdm.spu.status_changed.v1"
        self.domain = "pdm"
        self.aggregate_type = "spu"


@dataclass
class SKUCreated(DomainEvent):
    sku_id: str = ""
    sku_code: str = ""
    spu_id: str = ""
    cost_price: float = 0.0

    def __post_init__(self):
        self.event_type = "erp.pdm.sku.created.v1"
        self.domain = "pdm"
        self.aggregate_type = "sku"


@dataclass
class ProductProjectStageChanged(DomainEvent):
    project_id: str = ""
    project_code: str = ""
    from_stage: str = ""
    to_stage: str = ""

    def __post_init__(self):
        self.event_type = "erp.pdm.project.stage_changed.v1"
        self.domain = "pdm"
        self.aggregate_type = "product_project"
