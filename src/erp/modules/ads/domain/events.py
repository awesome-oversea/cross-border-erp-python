from __future__ import annotations

from dataclasses import dataclass

from erp.shared.events.domain_event import DomainEvent


@dataclass
class CampaignCreated(DomainEvent):
    campaign_id: str = ""
    campaign_no: str = ""
    platform: str = ""
    campaign_type: str = ""
    daily_budget: float = 0.0

    def __post_init__(self):
        self.event_type = "erp.ads.campaign.created.v1"
        self.domain = "ads"
        self.aggregate_type = "ad_campaign"


@dataclass
class CampaignStatusChanged(DomainEvent):
    campaign_id: str = ""
    campaign_no: str = ""
    from_status: str = ""
    to_status: str = ""

    def __post_init__(self):
        self.event_type = "erp.ads.campaign.status_changed.v1"
        self.domain = "ads"
        self.aggregate_type = "ad_campaign"


@dataclass
class CampaignBudgetUpdated(DomainEvent):
    campaign_id: str = ""
    campaign_no: str = ""
    old_budget: float = 0.0
    new_budget: float = 0.0

    def __post_init__(self):
        self.event_type = "erp.ads.campaign.budget_updated.v1"
        self.domain = "ads"
        self.aggregate_type = "ad_campaign"


@dataclass
class KeywordBidUpdated(DomainEvent):
    keyword_id: str = ""
    campaign_id: str = ""
    old_bid: float = 0.0
    new_bid: float = 0.0

    def __post_init__(self):
        self.event_type = "erp.ads.keyword.bid_updated.v1"
        self.domain = "ads"
        self.aggregate_type = "ad_keyword"
