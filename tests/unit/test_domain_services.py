from __future__ import annotations

from erp.modules.bi.domain.services import (
    AlertDomainService,
    MetricDomainService,
    ReportDomainService,
)
from erp.modules.dashboard.domain.services import DashboardDomainService
from erp.modules.fms.domain.services import (
    CostEventDomainService,
    SettlementDomainService,
)
from erp.modules.iam.domain.services import (
    RoleDomainService,
    TenantDomainService,
    UserDomainService,
)
from erp.modules.som.domain.services import (
    ListingDomainService,
    PriceRuleDomainService,
    StoreDomainService,
)


class TestCostEventDomainService:
    def test_can_transition_draft_to_confirmed(self):
        assert CostEventDomainService.can_transition("draft", "confirmed") is True

    def test_can_transition_draft_to_cancelled(self):
        assert CostEventDomainService.can_transition("draft", "cancelled") is True

    def test_cannot_transition_confirmed_to_draft(self):
        assert CostEventDomainService.can_transition("confirmed", "draft") is False

    def test_validate_cost_event_valid(self):
        errors = CostEventDomainService.validate_cost_event("purchase_cost", 100.0, "CNY")
        assert len(errors) == 0

    def test_validate_cost_event_invalid_type(self):
        errors = CostEventDomainService.validate_cost_event("invalid", 100.0, "CNY")
        assert len(errors) > 0

    def test_validate_cost_event_negative_amount(self):
        errors = CostEventDomainService.validate_cost_event("purchase_cost", -10.0, "CNY")
        assert len(errors) > 0

    def test_validate_cost_event_invalid_currency(self):
        errors = CostEventDomainService.validate_cost_event("purchase_cost", 100.0, "XYZ")
        assert len(errors) > 0

    def test_calculate_amount_cny_same_currency(self):
        result = CostEventDomainService.calculate_amount_cny(100.0, "CNY", 7.0)
        assert result == 100.0

    def test_calculate_amount_cny_conversion(self):
        result = CostEventDomainService.calculate_amount_cny(100.0, "USD", 7.2)
        assert result == 720.0

    def test_is_deletable_draft(self):
        assert CostEventDomainService.is_deletable("draft") is True

    def test_is_deletable_confirmed(self):
        assert CostEventDomainService.is_deletable("confirmed") is False


class TestSettlementDomainService:
    def test_can_transition_pending_to_confirmed(self):
        assert SettlementDomainService.can_transition("pending", "confirmed") is True

    def test_cannot_transition_settled_to_pending(self):
        assert SettlementDomainService.can_transition("settled", "pending") is False

    def test_calculate_net_amount(self):
        result = SettlementDomainService.calculate_net_amount(
            total_sales=1000.0, total_refund=100.0,
            platform_fee=50.0, advertising_fee=30.0,
            shipping_fee=20.0, other_fee=10.0,
        )
        assert result == 790.0

    def test_validate_settlement_valid(self):
        errors = SettlementDomainService.validate_settlement(1000.0, 100.0, 900.0)
        assert len(errors) == 0

    def test_validate_settlement_refund_exceeds_sales(self):
        errors = SettlementDomainService.validate_settlement(100.0, 200.0, -100.0)
        assert len(errors) > 0


class TestListingDomainService:
    def test_can_transition_draft_to_pending(self):
        assert ListingDomainService.can_transition("draft", "pending_review") is True

    def test_cannot_transition_published_to_draft(self):
        assert ListingDomainService.can_transition("published", "draft") is False

    def test_can_transition_platform_status(self):
        assert ListingDomainService.can_transition_platform_status("not_listed", "active") is True

    def test_validate_listing_price_valid(self):
        errors = ListingDomainService.validate_listing_price(100.0, 80.0, 120.0)
        assert len(errors) == 0

    def test_validate_listing_price_sale_exceeds_regular(self):
        errors = ListingDomainService.validate_listing_price(100.0, 120.0, 0.0)
        assert len(errors) > 0

    def test_validate_listing_price_exceeds_msrp(self):
        errors = ListingDomainService.validate_listing_price(150.0, 0.0, 120.0)
        assert len(errors) > 0

    def test_is_publishable(self):
        assert ListingDomainService.is_publishable("approved", "not_listed") is True
        assert ListingDomainService.is_publishable("draft", "not_listed") is False

    def test_is_editable(self):
        assert ListingDomainService.is_editable("draft") is True
        assert ListingDomainService.is_editable("published") is False


class TestStoreDomainService:
    def test_can_transition_auth(self):
        assert StoreDomainService.can_transition_auth("unauthorized", "authorizing") is True

    def test_validate_platform_valid(self):
        assert StoreDomainService.validate_platform("amazon") is True

    def test_validate_platform_invalid(self):
        assert StoreDomainService.validate_platform("invalid_platform") is False

    def test_is_operational(self):
        assert StoreDomainService.is_operational("active", "authorized") is True
        assert StoreDomainService.is_operational("active", "unauthorized") is False


class TestPriceRuleDomainService:
    def test_validate_rule_valid_markup(self):
        errors = PriceRuleDomainService.validate_rule("markup", {"percentage": 20}, 0, 0)
        assert len(errors) == 0

    def test_validate_rule_invalid_type(self):
        errors = PriceRuleDomainService.validate_rule("invalid", {}, 0, 0)
        assert len(errors) > 0

    def test_validate_rule_missing_percentage(self):
        errors = PriceRuleDomainService.validate_rule("markup", {}, 0, 0)
        assert len(errors) > 0

    def test_calculate_price_markup(self):
        result = PriceRuleDomainService.calculate_price("markup", {"percentage": 20}, 100.0)
        assert result == 120.0

    def test_calculate_price_markdown(self):
        result = PriceRuleDomainService.calculate_price("markdown", {"percentage": 10}, 100.0)
        assert result == 90.0

    def test_calculate_price_fixed(self):
        result = PriceRuleDomainService.calculate_price("fixed", {"amount": 50.0}, 100.0)
        assert result == 50.0

    def test_calculate_price_with_min(self):
        result = PriceRuleDomainService.calculate_price("markdown", {"percentage": 50}, 100.0, min_price=60.0)
        assert result == 60.0

    def test_calculate_price_with_max(self):
        result = PriceRuleDomainService.calculate_price("markup", {"percentage": 100}, 100.0, max_price=150.0)
        assert result == 150.0


class TestMetricDomainService:
    def test_validate_metric_valid(self):
        errors = MetricDomainService.validate_metric("revenue", "sales", "daily")
        assert len(errors) == 0

    def test_validate_metric_invalid_category(self):
        errors = MetricDomainService.validate_metric("test", "invalid", "daily")
        assert len(errors) > 0

    def test_calculate_change_rate_positive(self):
        result = MetricDomainService.calculate_change_rate(120.0, 100.0)
        assert result == 20.0

    def test_calculate_change_rate_negative(self):
        result = MetricDomainService.calculate_change_rate(80.0, 100.0)
        assert result == -20.0

    def test_calculate_change_rate_zero_previous(self):
        result = MetricDomainService.calculate_change_rate(100.0, 0.0)
        assert result == 100.0

    def test_calculate_moving_average(self):
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = MetricDomainService.calculate_moving_average(values, window=3)
        assert len(result) == 5
        assert result[0] == 10.0
        assert result[2] == 20.0

    def test_calculate_moving_average_empty(self):
        result = MetricDomainService.calculate_moving_average([], window=3)
        assert result == []


class TestAlertDomainService:
    def test_evaluate_threshold_gt(self):
        assert AlertDomainService.evaluate_threshold(10.0, "gt", 5.0) is True
        assert AlertDomainService.evaluate_threshold(3.0, "gt", 5.0) is False

    def test_evaluate_threshold_lt(self):
        assert AlertDomainService.evaluate_threshold(3.0, "lt", 5.0) is True

    def test_evaluate_threshold_gte(self):
        assert AlertDomainService.evaluate_threshold(5.0, "gte", 5.0) is True

    def test_validate_alert_rule_valid(self):
        errors = AlertDomainService.validate_alert_rule("gt", 100.0)
        assert len(errors) == 0

    def test_validate_alert_rule_invalid_operator(self):
        errors = AlertDomainService.validate_alert_rule("invalid", 100.0)
        assert len(errors) > 0


class TestReportDomainService:
    def test_validate_report_config_valid(self):
        errors = ReportDomainService.validate_report_config("daily", ["store_id"])
        assert len(errors) == 0

    def test_validate_report_config_invalid_period(self):
        errors = ReportDomainService.validate_report_config("invalid", ["store_id"])
        assert len(errors) > 0

    def test_validate_report_config_no_dimensions(self):
        errors = ReportDomainService.validate_report_config("daily", [])
        assert len(errors) > 0

    def test_aggregate_values_sum(self):
        result = ReportDomainService.aggregate_values([10.0, 20.0, 30.0], "sum")
        assert result == 60.0

    def test_aggregate_values_avg(self):
        result = ReportDomainService.aggregate_values([10.0, 20.0, 30.0], "avg")
        assert result == 20.0

    def test_aggregate_values_max(self):
        result = ReportDomainService.aggregate_values([10.0, 20.0, 30.0], "max")
        assert result == 30.0

    def test_aggregate_values_empty(self):
        result = ReportDomainService.aggregate_values([], "sum")
        assert result == 0.0


class TestDashboardDomainService:
    def test_calculate_kpi_trend_up(self):
        result = DashboardDomainService.calculate_kpi_trend(120.0, 100.0)
        assert result["direction"] == "up"
        assert result["change_rate"] == 20.0

    def test_calculate_kpi_trend_down(self):
        result = DashboardDomainService.calculate_kpi_trend(80.0, 100.0)
        assert result["direction"] == "down"

    def test_calculate_kpi_trend_stable(self):
        result = DashboardDomainService.calculate_kpi_trend(102.0, 100.0)
        assert result["direction"] == "stable"

    def test_prioritize_todos(self):
        todos = [
            {"title": "low", "priority": "low"},
            {"title": "critical", "priority": "critical"},
            {"title": "medium", "priority": "medium"},
        ]
        result = DashboardDomainService.prioritize_todos(todos)
        assert result[0]["priority"] == "critical"

    def test_filter_alerts_by_severity(self):
        alerts = [
            {"severity": "info"},
            {"severity": "medium"},
            {"severity": "critical"},
        ]
        result = DashboardDomainService.filter_alerts_by_severity(alerts, "medium")
        assert len(result) == 2

    def test_generate_period_ranges_daily(self):
        result = DashboardDomainService.generate_period_ranges("daily", count=3)
        assert len(result) == 3

    def test_generate_period_ranges_monthly(self):
        result = DashboardDomainService.generate_period_ranges("monthly", count=3)
        assert len(result) == 3


class TestTenantDomainService:
    def test_can_transition_active_to_suspended(self):
        assert TenantDomainService.can_transition("active", "suspended") is True

    def test_cannot_transition_deleted_to_active(self):
        assert TenantDomainService.can_transition("deleted", "active") is False

    def test_validate_plan(self):
        assert TenantDomainService.validate_plan("pro") is True
        assert TenantDomainService.validate_plan("invalid") is False

    def test_get_plan_limits(self):
        limits = TenantDomainService.get_plan_limits("free")
        assert limits["max_users"] == 10

    def test_can_add_users(self):
        assert TenantDomainService.can_add_users(5, "free") is True
        assert TenantDomainService.can_add_users(10, "free") is False

    def test_can_add_stores(self):
        assert TenantDomainService.can_add_stores(3, "free") is True
        assert TenantDomainService.can_add_stores(5, "free") is False


class TestUserDomainService:
    def test_can_transition_active_to_disabled(self):
        assert UserDomainService.can_transition("active", "disabled") is True

    def test_cannot_transition_disabled_to_locked(self):
        assert UserDomainService.can_transition("disabled", "locked") is False

    def test_validate_password_valid(self):
        errors = UserDomainService.validate_password("Test1234")
        assert len(errors) == 0

    def test_validate_password_too_short(self):
        errors = UserDomainService.validate_password("Te1")
        assert len(errors) > 0

    def test_validate_password_no_digit(self):
        errors = UserDomainService.validate_password("TestTest")
        assert len(errors) > 0

    def test_validate_email_valid(self):
        assert UserDomainService.validate_email("test@example.com") is True

    def test_validate_email_invalid(self):
        assert UserDomainService.validate_email("invalid") is False

    def test_is_active(self):
        assert UserDomainService.is_active("active") is True
        assert UserDomainService.is_active("disabled") is False


class TestRoleDomainService:
    def test_validate_permission_code_valid(self):
        assert RoleDomainService.validate_permission_code("iam:user:write") is True

    def test_validate_permission_code_invalid(self):
        assert RoleDomainService.validate_permission_code("invalid") is False

    def test_is_admin_role(self):
        assert RoleDomainService.is_admin_role("super_admin") is True
        assert RoleDomainService.is_admin_role("viewer") is False
