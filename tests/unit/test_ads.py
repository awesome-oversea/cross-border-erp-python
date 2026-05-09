from unittest.mock import AsyncMock, MagicMock

import pytest

from erp.modules.ads.application.services import (
    CAMPAIGN_STATUS_TRANSITIONS,
    MAX_KEYWORD_BID,
    MIN_DAILY_BUDGET,
    MIN_KEYWORD_BID,
    AdCampaignService,
    AdKeywordService,
)
from erp.modules.ads.domain.models import AdCampaign, AdKeyword
from erp.shared.exceptions import NotFoundException, ValidationException


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


class TestCampaignStatusTransitions:
    def test_draft_can_go_to_pending(self):
        assert "pending" in CAMPAIGN_STATUS_TRANSITIONS["draft"]

    def test_pending_can_go_to_active(self):
        assert "active" in CAMPAIGN_STATUS_TRANSITIONS["pending"]

    def test_active_can_go_to_paused(self):
        assert "paused" in CAMPAIGN_STATUS_TRANSITIONS["active"]

    def test_completed_is_terminal(self):
        assert CAMPAIGN_STATUS_TRANSITIONS["completed"] == []

    def test_cancelled_is_terminal(self):
        assert CAMPAIGN_STATUS_TRANSITIONS["cancelled"] == []

    def test_rejected_can_go_to_draft(self):
        assert "draft" in CAMPAIGN_STATUS_TRANSITIONS["rejected"]


class TestCampaignBudgetValidation:
    def test_min_daily_budget_value(self):
        assert MIN_DAILY_BUDGET == 1.0

    def test_min_keyword_bid_value(self):
        assert MIN_KEYWORD_BID == 0.02

    def test_max_keyword_bid_value(self):
        assert MAX_KEYWORD_BID == 1000.0


class TestAdCampaignService:
    @pytest.mark.asyncio
    async def test_create_campaign(self, mock_session):
        svc = AdCampaignService(mock_session)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        campaign = await svc.create("t1", "CMP001", "Test Campaign", "amazon", "s1",
                                     campaign_type="sponsored_products",
                                     daily_budget=50.0, target_acos=25.0)
        assert campaign.name == "Test Campaign"
        assert campaign.daily_budget == 50.0

    @pytest.mark.asyncio
    async def test_update_status_invalid_transition(self, mock_session):
        svc = AdCampaignService(mock_session)
        campaign = AdCampaign(id="c1", tenant_id="t1", name="Test", campaign_type="sp",
                              daily_budget=50.0, status="draft")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
        )
        with pytest.raises(ValidationException, match="Cannot transition"):
            await svc.update_status("c1", "t1", "active")

    @pytest.mark.asyncio
    async def test_activate_campaign_low_budget(self, mock_session):
        svc = AdCampaignService(mock_session)
        campaign = AdCampaign(id="c1", tenant_id="t1", name="Test", campaign_type="sp",
                              daily_budget=0.5, status="pending")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
        )
        with pytest.raises(ValidationException, match="daily_budget must be at least"):
            await svc.update_status("c1", "t1", "active")


class TestAdKeywordService:
    @pytest.mark.asyncio
    async def test_update_bid_below_minimum(self, mock_session):
        svc = AdKeywordService(mock_session)
        mock_session.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundException):
            await svc.update_bid("kw1", 0.001)

    @pytest.mark.asyncio
    async def test_update_bid_above_maximum(self, mock_session):
        svc = AdKeywordService(mock_session)
        kw = AdKeyword(id="kw1", tenant_id="t1", campaign_id="c1", ad_group_id="g1", keyword_text="test", match_type="broad", bid=1.0)
        mock_session.get = AsyncMock(return_value=kw)
        with pytest.raises(ValidationException, match="cannot exceed"):
            await svc.update_bid("kw1", 5000.0)

    @pytest.mark.asyncio
    async def test_update_bid_valid(self, mock_session):
        svc = AdKeywordService(mock_session)
        kw = AdKeyword(id="kw1", tenant_id="t1", campaign_id="c1", ad_group_id="g1", keyword_text="test", match_type="broad", bid=1.0)
        mock_session.get = AsyncMock(return_value=kw)
        result = await svc.update_bid("kw1", 2.5)
        assert result.bid == 2.5
