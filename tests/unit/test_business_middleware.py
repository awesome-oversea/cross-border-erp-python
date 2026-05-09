from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from erp.middleware.ad_optimization.domain.engine import AdOptimizationEngine
from erp.middleware.billing.domain.engine import BillingEngine, BillingSimulationInput
from erp.middleware.cdp.domain.models import CustomerProfile, RFMCalculator
from erp.middleware.compliance.domain.engine import ComplianceEngine
from erp.middleware.content_review.application.services import ContentReviewService
from erp.middleware.content_review.domain.reviewer import RuleBasedTextReviewer
from erp.middleware.forex.application.services import ForexService
from erp.middleware.forex.domain.providers import MockForexProvider
from erp.middleware.invoice_tax.domain.engine import VAT_RATES, InvoiceTaxEngine, TaxCalculationInput
from erp.middleware.logistics_strategy.domain.engine import LogisticsStrategyEngine, ShipmentEstimateContext
from erp.middleware.order_strategy.domain.engine import (
    DEFAULT_AUTO_APPROVE_RULES,
    DEFAULT_LOGISTICS_RULES,
    DEFAULT_RISK_RULES,
    DEFAULT_WAREHOUSE_RULES,
    OrderStrategyEngine,
    StrategyEvaluationContext,
    StrategyRule,
)
from erp.middleware.payment.domain.adapters import (
    MockPaymentAdapter,
    PaymentChannelRegistry,
    PaymentRequest,
    RefundRequest,
    get_payment_registry,
)
from erp.middleware.selection.domain.engine import MarketAnalysisInput, ProfitSimulationInput, SelectionEngine
from erp.shared.exceptions import NotFoundException, ValidationException


class TestRuleBasedTextReviewer:
    def setup_method(self):
        self.reviewer = RuleBasedTextReviewer()
        self.rules = [
            {"rule_code": "R001", "rule_name": "prohibited_words", "language": "en",
             "keywords": ["counterfeit", "fake"], "is_active": True, "severity": "critical"},
            {"rule_code": "R002", "rule_name": "warning_words", "language": "en",
             "keywords": ["discount"], "is_active": True, "severity": "warning"},
            {"rule_code": "R003", "rule_name": "regex_rule", "language": "*",
             "regex_patterns": [r"\b\d{16}\b"], "is_active": True, "severity": "critical"},
        ]

    @pytest.mark.asyncio
    async def test_review_text_pass(self):
        result = await self.reviewer.review_text("This is a normal product description", "en", self.rules)
        assert result["result"] == "pass"
        assert len(result["violations"]) == 0

    @pytest.mark.asyncio
    async def test_review_text_critical_violation(self):
        result = await self.reviewer.review_text("This is a counterfeit product", "en", self.rules)
        assert result["result"] == "reject"
        assert any(v["severity"] == "critical" for v in result["violations"])

    @pytest.mark.asyncio
    async def test_review_text_warning_violation(self):
        result = await self.reviewer.review_text("Big discount on all items", "en", self.rules)
        assert result["result"] == "warning"
        assert any(v["keyword"] == "discount" for v in result["violations"])

    @pytest.mark.asyncio
    async def test_review_text_language_filter(self):
        result = await self.reviewer.review_text("counterfeit product", "zh", self.rules)
        assert result["result"] == "pass"

    @pytest.mark.asyncio
    async def test_review_text_regex_pattern(self):
        result = await self.reviewer.review_text("Card number 1234567890123456 here", "en", self.rules)
        assert result["result"] == "reject"

    @pytest.mark.asyncio
    async def test_review_text_inactive_rule(self):
        rules = [dict(self.rules[0], is_active=False)]
        result = await self.reviewer.review_text("counterfeit product", "en", rules)
        assert result["result"] == "pass"

    @pytest.mark.asyncio
    async def test_review_image_pass(self):
        result = await self.reviewer.review_image("https://example.com/img.jpg", self.rules)
        assert result["result"] == "pass"

    @pytest.mark.asyncio
    async def test_review_image_critical_violation(self):
        rules = [
            {"rule_code": "IMG001", "rule_name": "image_sensitive", "rule_type": "image",
             "keywords": ["weapon"], "is_active": True, "severity": "critical"},
        ]
        result = await self.reviewer.review_image("https://example.com/assets/weapon-banner.jpg", rules)
        assert result["result"] == "reject"
        assert result["violations"][0]["keyword"] == "weapon"


class TestMockForexProvider:
    def setup_method(self):
        self.provider = MockForexProvider()

    @pytest.mark.asyncio
    async def test_get_rate_same_currency(self):
        rate = await self.provider.get_rate("USD", "USD")
        assert rate == 1.0

    @pytest.mark.asyncio
    async def test_get_rate_usd_cny(self):
        rate = await self.provider.get_rate("USD", "CNY")
        assert rate == 7.25

    @pytest.mark.asyncio
    async def test_get_rate_cny_usd(self):
        rate = await self.provider.get_rate("CNY", "USD")
        assert rate == 0.138

    @pytest.mark.asyncio
    async def test_get_rate_unknown_pair(self):
        rate = await self.provider.get_rate("XXX", "YYY")
        assert rate is None

    @pytest.mark.asyncio
    async def test_get_rates_batch(self):
        pairs = [("USD", "CNY"), ("EUR", "USD")]
        result = await self.provider.get_rates_batch(pairs)
        assert result[("USD", "CNY")] == 7.25
        assert result[("EUR", "USD")] == 1.083

    @pytest.mark.asyncio
    async def test_get_rates_batch_partial(self):
        pairs = [("USD", "CNY"), ("XXX", "YYY")]
        result = await self.provider.get_rates_batch(pairs)
        assert ("USD", "CNY") in result
        assert ("XXX", "YYY") not in result

    @pytest.mark.asyncio
    async def test_get_rate_usd_cad(self):
        rate = await self.provider.get_rate("USD", "CAD")
        assert rate == 1.37


class TestContentReviewService:
    @pytest.mark.asyncio
    async def test_init_default_rules_skips_existing_rule(self, monkeypatch):
        service = ContentReviewService(AsyncMock())
        created_codes: list[str] = []

        async def fake_create_rule(**kwargs):
            created_codes.append(kwargs["rule_code"])
            if kwargs["rule_code"] == "text_contact_privacy":
                raise ValidationException(message="exists")
            return SimpleNamespace(rule_code=kwargs["rule_code"])

        monkeypatch.setattr(service, "create_rule", fake_create_rule)

        created = await service.init_default_rules("tenant-1")

        assert created_codes == [
            "text_prohibited_keywords",
            "text_contact_privacy",
            "text_marketing_warning",
            "image_sensitive_keywords",
        ]
        assert [item.rule_code for item in created] == [
            "text_prohibited_keywords",
            "text_marketing_warning",
            "image_sensitive_keywords",
        ]


class TestForexService:
    @pytest.mark.asyncio
    async def test_list_rates_normalizes_codes_and_reports_missing_targets(self, monkeypatch):
        service = ForexService(AsyncMock())
        requested_pairs: list[tuple[str, str]] = []

        async def fake_get_rate(tenant_id: str, from_currency: str, to_currency: str, rate_date=None):
            requested_pairs.append((from_currency, to_currency))
            if to_currency == "CNY":
                return {"rate": 7.25}
            if to_currency == "CAD":
                return {"rate": 1.37}
            raise NotFoundException(message="missing")

        monkeypatch.setattr(service, "get_rate", fake_get_rate)

        result = await service.list_rates(
            "tenant-1",
            base_currency=" usd ",
            target_currencies=["cny", "usd", "cad", "mxn", "cad"],
        )

        assert requested_pairs == [("USD", "CNY"), ("USD", "CAD"), ("USD", "MXN")]
        assert result["base"] == "USD"
        assert result["rates"] == {"CNY": 7.25, "CAD": 1.37}
        assert result["missing_targets"] == ["MXN"]

    @pytest.mark.asyncio
    async def test_create_alert_rule_normalizes_currency_pair(self, monkeypatch):
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        service = ForexService(session)

        monkeypatch.setattr(service, "_get_alert_rule", AsyncMock(return_value=None))

        rule = await service.create_alert_rule(
            tenant_id="tenant-1",
            from_currency=" usd ",
            to_currency=" cny ",
            threshold_pct=1.5,
            direction=" BOTH ",
        )

        assert rule.from_currency == "USD"
        assert rule.to_currency == "CNY"
        assert rule.direction == "both"
        session.add.assert_called_once()


class TestPaymentAdapters:
    def setup_method(self):
        self.adapter = MockPaymentAdapter()

    @pytest.mark.asyncio
    async def test_pay(self):
        request = PaymentRequest(tenant_id="t1", channel="mock", amount=100.0, currency="USD")
        result = await self.adapter.pay(request)
        assert result.success is True
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_refund(self):
        request = RefundRequest(tenant_id="t1", channel="mock", original_transaction_id="TX001", refund_amount=50.0)
        result = await self.adapter.refund(request)
        assert result.success is True
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_get_balance(self):
        balance = await self.adapter.get_balance("t1", "USD")
        assert balance.available == 100000.0
        assert balance.currency == "USD"

    def test_get_channel_name(self):
        assert self.adapter.get_channel_name() == "mock"


class TestPaymentChannelRegistry:
    def test_register_and_get(self):
        registry = PaymentChannelRegistry()
        adapter = MockPaymentAdapter()
        registry.register("test_channel", adapter)
        assert registry.get("test_channel") is adapter

    def test_get_nonexistent(self):
        registry = PaymentChannelRegistry()
        assert registry.get("nonexistent") is None

    def test_list_channels(self):
        registry = get_payment_registry()
        channels = registry.list_channels()
        assert "mock" in channels
        assert "paypal" in channels
        assert "stripe" in channels


class TestOrderStrategyEngine:
    def setup_method(self):
        self.engine = OrderStrategyEngine()

    def test_evaluate_risk_high_amount(self):
        ctx = StrategyEvaluationContext(tenant_id="t1", order_amount=60000)
        result = self.engine.evaluate(ctx, DEFAULT_RISK_RULES)
        assert result.risk_level in ("high", "medium")
        assert len(result.matched_rules) > 0

    def test_evaluate_risk_new_customer(self):
        ctx = StrategyEvaluationContext(tenant_id="t1", order_amount=6000, customer_segment="new")
        result = self.engine.evaluate(ctx, DEFAULT_RISK_RULES)
        assert result.risk_level in ("medium", "high")

    def test_evaluate_risk_low(self):
        ctx = StrategyEvaluationContext(tenant_id="t1", order_amount=100, customer_segment="vip")
        result = self.engine.evaluate(ctx, DEFAULT_RISK_RULES)
        assert result.risk_level in ("low", "medium")

    def test_evaluate_warehouse_allocation(self):
        ctx = StrategyEvaluationContext(tenant_id="t1")
        result = self.engine.evaluate(ctx, DEFAULT_WAREHOUSE_RULES)
        assert result.recommended_warehouse_id == "default"

    def test_evaluate_logistics_selection(self):
        ctx = StrategyEvaluationContext(tenant_id="t1")
        result = self.engine.evaluate(ctx, DEFAULT_LOGISTICS_RULES)
        assert result.recommended_logistics_id == "default"

    def test_evaluate_auto_approve(self):
        ctx = StrategyEvaluationContext(tenant_id="t1", order_amount=500, customer_segment="vip")
        result = self.engine.evaluate(ctx, DEFAULT_AUTO_APPROVE_RULES)
        assert result.auto_approve is True

    def test_evaluate_auto_approve_new_customer(self):
        ctx = StrategyEvaluationContext(tenant_id="t1", order_amount=500, customer_segment="new")
        result = self.engine.evaluate(ctx, DEFAULT_AUTO_APPROVE_RULES)
        assert result.auto_approve is False

    def test_evaluate_large_quantity(self):
        ctx = StrategyEvaluationContext(tenant_id="t1", items=[{"quantity": 2000}])
        result = self.engine.evaluate(ctx, DEFAULT_RISK_RULES)
        assert result.risk_level in ("medium", "low", "high")

    def test_evaluate_inactive_rule_skipped(self):
        inactive_rule = StrategyRule(
            rule_id="x1", rule_name="inactive", strategy_type="risk_control",
            priority=100, conditions={"min_amount": 1}, is_active=False,
            actions={"risk_level": "high"},
        )
        ctx = StrategyEvaluationContext(tenant_id="t1", order_amount=100)
        result = self.engine.evaluate(ctx, [inactive_rule])
        assert result.risk_level == "low"


class TestLogisticsStrategyEngine:
    def setup_method(self):
        self.engine = LogisticsStrategyEngine()

    def test_select_provider_us(self):
        ctx = ShipmentEstimateContext(origin_country="CN", destination_country="US", weight_kg=1.0)
        options = self.engine.select_provider(ctx)
        assert len(options) > 0
        assert all(o.provider_id for o in options)

    def test_select_provider_sorted_by_score(self):
        ctx = ShipmentEstimateContext(origin_country="CN", destination_country="US", weight_kg=1.0)
        options = self.engine.select_provider(ctx, priority="cost")
        for i in range(len(options) - 1):
            assert options[i].score >= options[i + 1].score

    def test_select_provider_speed_priority(self):
        ctx = ShipmentEstimateContext(origin_country="CN", destination_country="US", weight_kg=1.0)
        options = self.engine.select_provider(ctx, priority="speed")
        assert len(options) > 0

    def test_select_provider_unsupported_country(self):
        ctx = ShipmentEstimateContext(origin_country="CN", destination_country="XX", weight_kg=1.0)
        options = self.engine.select_provider(ctx)
        assert len(options) == 0

    def test_calculate_rate(self):
        ctx = ShipmentEstimateContext(origin_country="CN", destination_country="US", weight_kg=2.0)
        result = self.engine.calculate_rate(ctx, "yanwen")
        assert result is not None
        assert result.cost > 0

    def test_calculate_rate_unknown_provider(self):
        ctx = ShipmentEstimateContext(origin_country="CN", destination_country="US", weight_kg=1.0)
        result = self.engine.calculate_rate(ctx, "unknown")
        assert result is None


class TestBillingEngine:
    def setup_method(self):
        self.engine = BillingEngine()

    def test_calculate_platform_commission_amazon(self):
        result = self.engine.calculate_platform_commission("amazon", 100.0, 2)
        assert result["rate"] == 0.15
        assert result["commission"] == 30.0

    def test_calculate_platform_commission_category(self):
        result = self.engine.calculate_platform_commission("amazon", 100.0, 1, "electronics")
        assert result["rate"] == 0.08
        assert result["commission"] == 8.0

    def test_calculate_platform_commission_shopify(self):
        result = self.engine.calculate_platform_commission("shopify", 100.0, 1)
        assert result["commission"] == 0.0

    def test_calculate_warehouse_fee_fba(self):
        result = self.engine.calculate_warehouse_fee("fba", quantity=10, cubic_feet=5.0, storage_months=1)
        assert result["storage_fee"] == 12.0
        assert result["fulfillment_fee"] == 32.2

    def test_calculate_warehouse_fee_overseas(self):
        result = self.engine.calculate_warehouse_fee("overseas", quantity=100, storage_months=2)
        assert result["storage_fee"] == 100.0
        assert result["inbound_fee"] == 30.0
        assert result["outbound_fee"] == 50.0

    def test_simulate(self):
        input_data = BillingSimulationInput(
            platform="amazon", sale_price=50.0, quantity=2,
            cost_price=20.0, shipping_cost=5.0, warehouse_type="fba",
        )
        result = self.engine.simulate(input_data)
        assert result["revenue"] == 100.0
        assert result["cost"] == 40.0
        assert result["profit"] < result["revenue"]

    def test_calculate_freight_allocate_by_weight(self):
        items = [{"sku_id": "sku1", "weight_kg": 3.0}, {"sku_id": "sku2", "weight_kg": 1.0}]
        result = self.engine.calculate_freight_allocate(100.0, items)
        assert result[0]["allocated_freight"] == 75.0
        assert result[1]["allocated_freight"] == 25.0

    def test_calculate_freight_allocate_equal(self):
        items = [{"sku_id": "sku1", "weight_kg": 0}, {"sku_id": "sku2", "weight_kg": 0}]
        result = self.engine.calculate_freight_allocate(100.0, items)
        assert result[0]["allocated_freight"] == 50.0

    def test_calculate_fba_head_cost(self):
        result = self.engine.calculate_fba_head_cost(1000.0, 500, damaged_units=5, lost_units=2)
        assert result["per_unit_cost"] == 2.0
        assert result["damage_cost"] == 10.0
        assert result["lost_cost"] == 4.0


class TestRFMCalculator:
    def setup_method(self):
        self.calculator = RFMCalculator()

    def test_calculate_champions(self):
        now = datetime.now(UTC)
        orders = [{"order_date": now - timedelta(days=10), "amount": 300} for _ in range(25)]
        result = self.calculator.calculate(orders)
        assert result["r_score"] == 5
        assert result["f_score"] == 5
        assert result["segment"] == "champions"

    def test_calculate_inactive(self):
        result = self.calculator.calculate([])
        assert result["segment"] == "inactive"
        assert result["frequency"] == 0

    def test_calculate_recent_customers(self):
        now = datetime.now(UTC)
        orders = [{"order_date": now - timedelta(days=15), "amount": 100}]
        result = self.calculator.calculate(orders)
        assert result["r_score"] == 5
        assert result["segment"] in ("recent_customers", "champions")

    def test_calculate_loyal_customers(self):
        now = datetime.now(UTC)
        orders = [{"order_date": now - timedelta(days=200), "amount": 300} for _ in range(20)]
        result = self.calculator.calculate(orders)
        assert result["f_score"] == 5

    def test_calculate_at_risk(self):
        now = datetime.now(UTC)
        orders = [{"order_date": now - timedelta(days=400), "amount": 50}]
        result = self.calculator.calculate(orders)
        assert result["r_score"] == 1


class TestCustomerProfile:
    def test_default_values(self):
        profile = CustomerProfile(customer_id="c1")
        assert profile.segment == "normal"
        assert profile.total_orders == 0
        assert profile.platforms == []

    def test_custom_values(self):
        profile = CustomerProfile(
            customer_id="c1", name="Test", email="test@example.com",
            segment="vip", total_orders=10, total_amount=5000.0,
        )
        assert profile.segment == "vip"
        assert profile.total_orders == 10


class TestInvoiceTaxEngine:
    def setup_method(self):
        self.engine = InvoiceTaxEngine()

    def test_calculate_tax_de(self):
        result = self.engine.calculate_tax(TaxCalculationInput(amount=100.0, country_code="DE"))
        assert result["tax_rate"] == 0.19
        assert result["tax_amount"] == 19.0
        assert result["gross_amount"] == 119.0

    def test_calculate_tax_b2b(self):
        result = self.engine.calculate_tax(TaxCalculationInput(amount=100.0, country_code="DE", is_b2b=True))
        assert result["tax_rate"] == 0.0
        assert result["tax_amount"] == 0.0

    def test_calculate_tax_inclusive(self):
        result = self.engine.calculate_tax(TaxCalculationInput(amount=119.0, country_code="DE", tax_inclusive=True))
        assert result["net_amount"] == 100.0
        assert result["tax_amount"] == 19.0

    def test_calculate_tax_us(self):
        result = self.engine.calculate_tax(TaxCalculationInput(amount=100.0, country_code="US"))
        assert result["tax_rate"] == 0.0
        assert result["tax_amount"] == 0.0

    def test_generate_invoice(self):
        items = [{"name": "Product A", "amount": 50.0, "quantity": 2}]
        counterparty = {"name": "Buyer Corp", "country": "DE"}
        result = self.engine.generate_invoice("t1", "sales", items, counterparty, "DE")
        assert result["invoice_type"] == "sales"
        assert result["status"] == "draft"
        assert result["subtotal"] == 100.0

    def test_get_tax_rates_single(self):
        result = self.engine.get_tax_rates("DE")
        assert len(result) == 1
        assert result[0]["vat_rate"] == 0.19

    def test_get_tax_rates_all(self):
        result = self.engine.get_tax_rates()
        assert len(result) == len(VAT_RATES)

    def test_get_filing_data(self):
        result = self.engine.get_filing_data("t1", "2024-01-01", "2024-03-31", "DE")
        assert result["vat_rate"] == 0.19
        assert result["status"] == "draft"


class TestComplianceEngine:
    def setup_method(self):
        self.engine = ComplianceEngine()

    def test_check_compliance_clean(self):
        result = self.engine.check_compliance("This is a safe product listing")
        assert result["compliant"] is True
        assert result["risk_level"] == "low"

    def test_check_compliance_prohibited_keyword(self):
        result = self.engine.check_compliance("This is a counterfeit watch")
        assert result["compliant"] is False
        assert result["risk_level"] == "high"
        assert any(v["type"] == "prohibited_keyword" for v in result["violations"])

    def test_check_compliance_embargo_country(self):
        result = self.engine.check_compliance("Normal product", country="IR")
        assert result["compliant"] is False
        assert any(v["type"] == "trade_embargo" for v in result["violations"])

    def test_check_compliance_health_keyword(self):
        result = self.engine.check_compliance("This product can cure diseases")
        assert result["compliant"] is False
        assert any(v["rule_type"] == "health" for v in result["violations"])

    def test_assess_risk_low(self):
        result = self.engine.assess_risk(transaction_amount=100, country="US", customer_segment="vip")
        assert result["risk_level"] == "low"
        assert result["risk_score"] == 0

    def test_assess_risk_high_amount(self):
        result = self.engine.assess_risk(transaction_amount=60000)
        assert result["risk_score"] >= 30
        assert any(f["factor"] == "high_amount" for f in result["factors"])

    def test_assess_risk_embargo(self):
        result = self.engine.assess_risk(transaction_amount=100, country="KP")
        assert result["risk_level"] == "high"
        assert result["risk_score"] >= 50

    def test_assess_risk_new_customer(self):
        result = self.engine.assess_risk(transaction_amount=100, customer_segment="new")
        assert result["risk_score"] >= 10

    def test_get_rules(self):
        rules = self.engine.get_rules()
        assert len(rules) >= 3
        rule_ids = [r["rule_id"] for r in rules]
        assert "prohibited_keywords" in rule_ids


class TestSelectionEngine:
    def setup_method(self):
        self.engine = SelectionEngine()

    def test_analyze_market(self):
        input_data = MarketAnalysisInput(
            category="electronics", marketplace="amazon_us", keywords=["bluetooth speaker"],
        )
        result = self.engine.analyze_market(input_data)
        assert result["category"] == "electronics"
        assert result["marketplace"] == "amazon_us"
        assert "market_size_estimate" in result
        assert "opportunity_score" in result

    def test_analyze_competitors(self):
        result = self.engine.analyze_competitors("electronics", "amazon_us")
        assert "top_competitors" in result
        assert len(result["top_competitors"]) > 0
        assert result["avg_price"] > 0

    def test_simulate_profit_positive(self):
        input_data = ProfitSimulationInput(
            sale_price=30.0, cost_price=10.0, shipping_cost=3.0,
            commission_rate=0.15, advertising_cost=2.0, monthly_sales_estimate=200,
        )
        result = self.engine.simulate_profit(input_data)
        assert result["profit_per_unit"] > 0
        assert result["margin_pct"] > 0
        assert result["monthly_profit"] > 0

    def test_simulate_profit_negative(self):
        input_data = ProfitSimulationInput(
            sale_price=10.0, cost_price=15.0, shipping_cost=3.0, commission_rate=0.15,
        )
        result = self.engine.simulate_profit(input_data)
        assert result["profit_per_unit"] < 0

    def test_simulate_profit_breakdown(self):
        input_data = ProfitSimulationInput(sale_price=100.0, cost_price=40.0, commission_rate=0.15)
        result = self.engine.simulate_profit(input_data)
        assert "breakdown" in result
        assert result["breakdown"]["commission"] == 15.0


class TestAdOptimizationEngine:
    def setup_method(self):
        self.engine = AdOptimizationEngine()

    def test_generate_suggestions_high_acos(self):
        campaign_data = {
            "campaign_id": "c1", "acos": 45, "spend": 100, "sales": 222,
            "clicks": 50, "impressions": 5000, "daily_budget": 50,
        }
        suggestions = self.engine.generate_suggestions(campaign_data)
        assert len(suggestions) > 0
        types = [s.suggestion_type for s in suggestions]
        assert "budget_reduction" in types

    def test_generate_suggestions_low_ctr(self):
        campaign_data = {
            "campaign_id": "c2", "acos": 20, "spend": 50, "sales": 250,
            "clicks": 10, "impressions": 10000, "daily_budget": 30,
        }
        suggestions = self.engine.generate_suggestions(campaign_data)
        types = [s.suggestion_type for s in suggestions]
        assert "keyword_optimization" in types

    def test_generate_suggestions_bid_adjustment(self):
        campaign_data = {
            "campaign_id": "c3", "acos": 35, "spend": 100, "sales": 285,
            "clicks": 50, "impressions": 5000, "daily_budget": 50,
        }
        suggestions = self.engine.generate_suggestions(campaign_data)
        types = [s.suggestion_type for s in suggestions]
        assert "bid_adjustment" in types

    def test_allocate_budget(self):
        campaigns = [
            {"campaign_id": "c1", "campaign_name": "Camp 1", "roas": 3.0},
            {"campaign_id": "c2", "campaign_name": "Camp 2", "roas": 2.0},
        ]
        result = self.engine.allocate_budget(campaigns, 1000.0)
        assert len(result) == 2
        total = sum(r["allocated_budget"] for r in result)
        assert total > 0

    def test_allocate_budget_empty(self):
        result = self.engine.allocate_budget([], 1000.0)
        assert result == []

    def test_get_performance_analysis_good(self):
        data = {"campaign_id": "c1", "spend": 100, "sales": 500, "clicks": 200, "impressions": 10000}
        result = self.engine.get_performance_analysis(data)
        assert result["acos"] == 20.0
        assert result["roas"] == 5.0
        assert result["performance_rating"] == "good"

    def test_get_performance_analysis_poor(self):
        data = {"campaign_id": "c2", "spend": 500, "sales": 1000, "clicks": 200, "impressions": 10000}
        result = self.engine.get_performance_analysis(data)
        assert result["acos"] == 50.0
        assert result["performance_rating"] == "poor"
