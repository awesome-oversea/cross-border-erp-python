from __future__ import annotations

from dataclasses import dataclass

from erp.shared.events.domain_event import DomainEvent


@dataclass
class DashboardCreated(DomainEvent):
    dashboard_id: str = ""
    dashboard_code: str = ""
    name: str = ""

    def __post_init__(self):
        self.event_type = "erp.dashboard.dashboard.created.v1"
        self.domain = "dashboard"
        self.aggregate_type = "dashboard"


@dataclass
class DashboardShared(DomainEvent):
    dashboard_id: str = ""
    share_type: str = ""
    target_id: str = ""
    permission: str = ""

    def __post_init__(self):
        self.event_type = "erp.dashboard.dashboard.shared.v1"
        self.domain = "dashboard"
        self.aggregate_type = "dashboard_share"
