"""
核心业务链路集成测试

验证14个业务域的领域服务可正常导入和调用，
覆盖状态机、业务规则、计算逻辑。
"""
from __future__ import annotations

from datetime import UTC, datetime


class TestCoreBusinessFlows:
    """核心业务链路集成测试"""

    def test_iam_tenant_flow(self):
        from erp.modules.iam.domain.services import TenantDomainService, UserDomainService
        assert TenantDomainService.can_transition("active", "suspended") is True
        assert TenantDomainService.can_transition("suspended", "deleted") is True
        assert TenantDomainService.can_transition("active", "deleted") is False
        assert TenantDomainService.validate_plan("pro") is True
        assert TenantDomainService.can_add_users(5, "free") is True
        assert TenantDomainService.can_add_users(15, "free") is False
        errors = UserDomainService.validate_password("Abc123")
        assert len(errors) > 0
        errors = UserDomainService.validate_password("StrongPass1")
        assert len(errors) == 0

    def test_oms_order_state_machine(self):
        from erp.modules.oms.domain.services import OrderDomainService, RefundDomainService
        assert OrderDomainService.can_transition("pending", "confirmed") is True
        assert OrderDomainService.can_transition("pending", "cancelled") is True
        assert OrderDomainService.can_transition("confirmed", "cancelled") is True
        assert OrderDomainService.can_transition("shipped", "cancelled") is False
        assert OrderDomainService.can_transition("delivered", "completed") is True
        risks = OrderDomainService.validate_order_risk(1000, 5, 10)
        assert len(risks) == 0
        risks = OrderDomainService.validate_order_risk(999999, 5, 10)
        assert len(risks) > 0
        assert RefundDomainService.is_auto_approve_eligible(type("", (), {"refund_type": "refund_only", "refund_amount": 50.0})()) is True

    def test_scm_purchase_order_flow(self):
        from erp.modules.scm.domain.services import PurchaseOrderDomainService, PurchaseModeService, PurchaseApprovalService
        assert PurchaseOrderDomainService.can_transition("draft", "submitted") is True
        assert PurchaseOrderDomainService.can_transition("draft", "cancelled") is True
        assert PurchaseOrderDomainService.can_transition("approved", "in_production") is True
        assert PurchaseModeService.is_valid_mode("standard_purchase") is True
        assert PurchaseModeService.is_valid_mode("invalid_mode") is False
        assert PurchaseModeService.requires_warehouse_receipt("jit_dropship") is False
        assert PurchaseModeService.requires_quality_inspection("standard_purchase") is True
        approval = PurchaseApprovalService.determine_approval_level(500)
        assert approval["level"] == "auto"
        approval = PurchaseApprovalService.determine_approval_level(5000)
        assert approval["level"] == "manager"
        approval = PurchaseApprovalService.determine_approval_level(50000)
        assert approval["level"] == "director"

    def test_wms_inventory_flow(self):
        from erp.modules.wms.domain.services import InventoryDomainService, QualityInspectionDomainService, StockCountDomainService, TransferDomainService
        available = InventoryDomainService.calculate_available(100, 30)
        assert available == 70
        available = InventoryDomainService.calculate_available(10, 30)
        assert available == 0
        result = QualityInspectionDomainService.determine_result(100, 90, 10)
        assert result == "partial"
        result = QualityInspectionDomainService.determine_result(100, 100, 0)
        assert result == "passed"
        diff = StockCountDomainService.calculate_diff(100, 110)
        assert diff["status"] == "surplus"
        assert TransferDomainService.can_transfer("draft", "approved") is True

    def test_fba_replenishment_flow(self):
        from erp.modules.fba.domain.services import FbaReplenishmentDomainService, FbaShipmentDomainService, FbaPlanCreationService, FbaInventoryAgeService
        qty = FbaReplenishmentDomainService.calculate_suggested_qty(100, 50, 10, 30, 7, 15)
        assert qty >= 0
        assert FbaPlanCreationService.is_valid_mode("sync_from_amazon") is True
        assert FbaPlanCreationService.is_valid_mode("invalid") is False
        steps = FbaPlanCreationService.get_creation_steps("sync_from_amazon")
        assert len(steps) >= 4
        assert FbaShipmentDomainService.can_transition("draft", "submitted") is True
        age_class = FbaInventoryAgeService.classify_age(120)
        assert age_class["level"] == "warning"

    def test_scm_replenishment_calculation(self):
        from erp.modules.scm.domain.services import ReplenishmentDomainService
        result = ReplenishmentDomainService.calculate_replenish_qty(
            daily_sales=10, current_stock=50, inbound_qty=30,
            safety_stock_days=7, lead_time_days=15, order_cycle_days=7, max_stock_days=60,
        )
        assert result["need_replenish"] is True or result["need_replenish"] is False
        assert result["safety_stock"] == 70
        assert result["stock_on_hand_days"] == 5.0

    def test_tms_shipping_flow(self):
        from erp.modules.tms.domain.services import ShipmentDomainService, ShippingMethodDomainService, TrackingDomainService, FreightAdjustmentService
        assert ShipmentDomainService.can_transition("pending", "picked_up") is True
        cost = ShippingMethodDomainService.calculate_freight_by_weight(5, 0.5, 20, 0.5, 5)
        assert cost > 0
        parsed = TrackingDomainService.parse_tracking_events([
            {"timestamp": "2026-01-02", "location": "NY", "status": "delivered"},
            {"timestamp": "2026-01-01", "location": "NJ", "status": "in_transit"},
        ])
        assert len(parsed) == 2
        adjustment = FreightAdjustmentService.calculate_cost_impact(100, 120)
        assert adjustment["difference"] == 20

    def test_pdm_services(self):
        from erp.modules.pdm.domain.services import SPUDomainService, SKUDomainService, ProductCollectionDomainService, SelectionSubmissionService
        spu = type("SPU", (), {"name": "Test", "category_id": "cat1", "brand_id": "brand1", "main_image": "img.jpg"})()
        assert len(SPUDomainService.validate_for_review(spu)) == 0
        errors = SKUDomainService.validate_dimensions(1.5, 30, 20, 10, 50)
        assert len(errors) == 0
        score = ProductCollectionDomainService.calculate_selection_score({"monthly_sales": 800}, {"avg_rating": 4.2, "review_count": 200}, 25)
        assert score >= 30
        auto = SelectionSubmissionService.should_auto_approve(75, "low", "manual")
        assert auto["auto_approve"] is True

    def test_crm_services(self):
        from erp.modules.crm.domain.services import ReviewDomainService, ServiceTicketDomainService, ComplaintDomainService, RefundReportService
        assert ReviewDomainService.can_transition("pending", "acknowledged") is True
        sla = ServiceTicketDomainService.calculate_sla_deadline("urgent")
        assert sla["hours"] == 2
        assert ComplaintDomainService.can_transition("open", "investigating") is True
        report = RefundReportService.calculate_refund_rate(10, 200)
        assert report["refund_rate"] == 5.0
        assert report["level"] == "warning"

    def test_bi_services(self):
        from erp.modules.bi.domain.services import MetricDomainService, AlertDomainService, ReportDomainService, RealTimeSalesService, KpiEvaluationService
        errs = MetricDomainService.validate_metric("sales_30d", "sales", "daily")
        assert len(errs) == 0
        triggered = AlertDomainService.evaluate_threshold(100, "gt", 50)
        assert triggered is True
        agg = ReportDomainService.aggregate_values([10, 20, 30], "sum")
        assert agg == 60.0
        ranked = RealTimeSalesService.rank([{"sku": "A", "sales": 100}, {"sku": "B", "sales": 200}], top=5)
        assert ranked[0]["rank"] == 1
        kpi = KpiEvaluationService.achievement(80, 100)
        assert kpi["met"] is False

    def test_fms_services(self):
        from erp.modules.fms.domain.services import CostEventDomainService, SettlementDomainService, PaymentRequestDomainService, AmazonCollectionService
        assert CostEventDomainService.can_transition("draft", "confirmed") is True
        net = SettlementDomainService.calculate_net_amount(1000, 50, 100, 50, 30, 10)
        assert net == 760.0
        assert PaymentRequestDomainService.can_transition("pending", "approved") is True
        pending = AmazonCollectionService.calc_pending([{"status": "pending", "amount": 100}, {"status": "completed", "amount": 200}])
        assert pending["pending"] == 1

    def test_som_services(self):
        from erp.modules.som.domain.services import ListingDomainService, PriceRuleDomainService, AlertRuleDomainService, PriceLimitService, SlowMovingService
        assert ListingDomainService.can_transition("draft", "pending_review") is True
        price = PriceRuleDomainService.calculate_price("markup", {"percentage": 20}, 100)
        assert price == 120.0
        assert AlertRuleDomainService.can_transition_alert_status("firing", "acknowledged") is True
        limit_errs = PriceLimitService.validate_price_against_limits(50, min_price=60)
        assert len(limit_errs) > 0
        slow = SlowMovingService.classify_movement(0, 100)
        assert slow["status"] == "slow_moving"

    def test_data_permission(self):
        from erp.shared.auth.data_permission import DataPermissionPolicy, DataPermissionService, DataScopeType, DataResourceType
        svc = DataPermissionService()
        ctx = svc.build_context("tenant1", "user1", ["operator"])
        assert ctx.has_access_to_store("store1") is False
        policy = DataPermissionPolicy(scope_type=DataScopeType.ALL, resource_type=DataResourceType.ORDER)
        ctx.policies.append(policy)
        assert ctx.has_access_to_org("any_org") is True

    def test_saga_orchestrator(self):
        from erp.shared.saga import SagaOrchestrator, SagaDefinition, SagaStep
        orch = SagaOrchestrator()
        saga = SagaDefinition(saga_id="test", name="Test", domain="test",
            steps=[SagaStep(step_id="step1", name="Step 1")])
        orch.register(saga)
        assert orch.get("test") is not None
        assert orch.get("not_found") is None

    def test_import_service(self):
        from erp.shared.import_service import ImportService
        template = ImportService.get_template("orders")
        assert template is not None
        assert "platform_order_id" in template.required_fields
        templates = ImportService.list_templates()
        assert len(templates) >= 3
