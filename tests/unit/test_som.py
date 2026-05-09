from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from erp.modules.som.application.services import (
    LISTING_STATUS_ON_PLATFORM,
    LISTING_STATUS_TRANSITIONS,
    STORE_AUTH_STATUS_TRANSITIONS,
    ListingService,
    PriceRuleService,
    StoreService,
    _apply_price_formula,
    _validate_formula,
)
from erp.modules.som.domain.models import PriceRule, Store
from erp.shared.exceptions import DuplicateCodeException, ValidationException


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def store_service(mock_session):
    return StoreService(mock_session)


@pytest.fixture
def listing_service(mock_session):
    return ListingService(mock_session)


@pytest.fixture
def price_rule_service(mock_session):
    return PriceRuleService(mock_session)


class TestListingStatusTransitions:
    def test_draft_can_transition_to_pending_review(self):
        assert "pending_review" in LISTING_STATUS_TRANSITIONS["draft"]

    def test_draft_can_transition_to_cancelled(self):
        assert "cancelled" in LISTING_STATUS_TRANSITIONS["draft"]

    def test_active_can_transition_to_inactive(self):
        assert "inactive" in LISTING_STATUS_TRANSITIONS["active"]

    def test_active_can_transition_to_out_of_stock(self):
        assert "out_of_stock" in LISTING_STATUS_TRANSITIONS["active"]

    def test_cancelled_is_terminal(self):
        assert LISTING_STATUS_TRANSITIONS["cancelled"] == []

    def test_discontinued_is_terminal(self):
        assert LISTING_STATUS_TRANSITIONS["discontinued"] == []

    def test_publish_failed_can_go_back_to_approved(self):
        assert "approved" in LISTING_STATUS_TRANSITIONS["publish_failed"]


class TestListingPlatformStatusTransitions:
    def test_not_listed_can_go_to_listing(self):
        assert "listing" in LISTING_STATUS_ON_PLATFORM["not_listed"]

    def test_listed_can_go_to_delisting(self):
        assert "delisting" in LISTING_STATUS_ON_PLATFORM["listed"]

    def test_delisted_can_go_to_listing(self):
        assert "listing" in LISTING_STATUS_ON_PLATFORM["delisted"]


class TestStoreAuthStatusTransitions:
    def test_unauthorized_can_go_to_authorizing(self):
        assert "authorizing" in STORE_AUTH_STATUS_TRANSITIONS["unauthorized"]

    def test_authorized_can_go_to_expiring(self):
        assert "expiring" in STORE_AUTH_STATUS_TRANSITIONS["authorized"]

    def test_authorized_can_go_to_revoked(self):
        assert "revoked" in STORE_AUTH_STATUS_TRANSITIONS["authorized"]

    def test_revoked_can_go_to_authorizing(self):
        assert "authorizing" in STORE_AUTH_STATUS_TRANSITIONS["revoked"]


class TestPriceFormulaValidation:
    def test_markup_requires_markup_percent(self):
        with pytest.raises(ValidationException, match="markup_percent"):
            _validate_formula("markup", {})

    def test_markup_rejects_negative_percent(self):
        with pytest.raises(ValidationException, match="negative"):
            _validate_formula("markup", {"markup_percent": -10})

    def test_markup_valid(self):
        _validate_formula("markup", {"markup_percent": 30})

    def test_markdown_requires_markdown_percent(self):
        with pytest.raises(ValidationException, match="markdown_percent"):
            _validate_formula("markdown", {})

    def test_markdown_rejects_over_100(self):
        with pytest.raises(ValidationException, match="between 0 and 100"):
            _validate_formula("markdown", {"markdown_percent": 150})

    def test_markdown_valid(self):
        _validate_formula("markdown", {"markdown_percent": 20})

    def test_fixed_requires_fixed_price(self):
        with pytest.raises(ValidationException, match="fixed_price"):
            _validate_formula("fixed", {})

    def test_fixed_rejects_negative(self):
        with pytest.raises(ValidationException, match="negative"):
            _validate_formula("fixed", {"fixed_price": -5})

    def test_competitive_requires_base_percent(self):
        with pytest.raises(ValidationException, match="base_percent"):
            _validate_formula("competitive", {"competitor_offset": 0})

    def test_competitive_requires_competitor_offset(self):
        with pytest.raises(ValidationException, match="competitor_offset"):
            _validate_formula("competitive", {"base_percent": 100})

    def test_competitive_valid(self):
        _validate_formula("competitive", {"base_percent": 100, "competitor_offset": 0})


class TestPriceFormulaApplication:
    def test_markup_calculation(self):
        rule = PriceRule(
            tenant_id="t1", name="test", rule_type="markup",
            formula_json='{"markup_percent": 50, "fixed_addition": 10}',
        )
        result = _apply_price_formula(rule, 100.0)
        assert result == 160.0

    def test_markdown_calculation(self):
        rule = PriceRule(
            tenant_id="t1", name="test", rule_type="markdown",
            formula_json='{"markdown_percent": 20, "fixed_subtraction": 5}',
        )
        result = _apply_price_formula(rule, 100.0)
        assert result == 75.0

    def test_fixed_calculation(self):
        rule = PriceRule(
            tenant_id="t1", name="test", rule_type="fixed",
            formula_json='{"fixed_price": 199.99}',
        )
        result = _apply_price_formula(rule, 100.0)
        assert result == 199.99

    def test_competitive_calculation(self):
        rule = PriceRule(
            tenant_id="t1", name="test", rule_type="competitive",
            formula_json='{"base_percent": 110, "competitor_offset": -2}',
        )
        result = _apply_price_formula(rule, 100.0)
        assert abs(result - 108.0) < 0.01


class TestStoreService:
    @pytest.mark.asyncio
    async def test_create_store_success(self, store_service, mock_session):
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        store = await store_service.create("t1", "My Store", "STR001", "amazon")
        assert store.name == "My Store"
        assert store.code == "STR001"

    @pytest.mark.asyncio
    async def test_create_store_duplicate_code(self, store_service, mock_session):
        existing = Store(id="s1", tenant_id="t1", name="Existing", code="STR001", platform="amazon")
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing)))
        with pytest.raises(DuplicateCodeException):
            await store_service.create("t1", "New Store", "STR001", "amazon")


class TestListingService:
    @pytest.mark.asyncio
    async def test_create_listing_validates_price(self, listing_service, mock_session):
        store = Store(id="s1", tenant_id="t1", name="Store", code="S1", platform="amazon")
        with patch.object(StoreService, "get_by_id", return_value=store), \
             pytest.raises(ValidationException, match="Sale price must be less than regular price"):
            await listing_service.create("t1", "s1", "sku1", price=10.0, sale_price=10.0)

    @pytest.mark.asyncio
    async def test_create_listing_price_exceeds_max(self, listing_service, mock_session):
        store = Store(id="s1", tenant_id="t1", name="Store", code="S1", platform="amazon")
        with patch.object(StoreService, "get_by_id", return_value=store), \
             pytest.raises(ValidationException, match="cannot exceed"):
            await listing_service.create("t1", "s1", "sku1", price=9999999.0)


class TestPriceRuleService:
    @pytest.mark.asyncio
    async def test_create_rule_invalid_type(self, price_rule_service, mock_session):
        with pytest.raises(ValidationException, match="Invalid rule_type"):
            await price_rule_service.create("t1", "Bad Rule", "invalid_type")

    @pytest.mark.asyncio
    async def test_create_rule_valid_markup(self, price_rule_service, mock_session):
        rule = await price_rule_service.create("t1", "Markup 50%", "markup",
                                                formula_json='{"markup_percent": 50}')
        assert rule.rule_type == "markup"

    @pytest.mark.asyncio
    async def test_calculate_price_negative_cost(self, price_rule_service, mock_session):
        with pytest.raises(ValidationException, match="cannot be negative"):
            await price_rule_service.calculate_price("t1", cost_price=-10.0)
