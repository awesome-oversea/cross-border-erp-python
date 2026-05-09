from __future__ import annotations

import pytest

from erp.middleware.api_platform.domain.engine import ApiPlatformEngine
from erp.middleware.audit_center.domain.engine import AuditCenterEngine
from erp.middleware.auth_center.domain.engine import AuthCenterEngine
from erp.middleware.connector_platform.domain.engine import ConnectorPlatformEngine
from erp.middleware.cost_engine.domain.engine import CostAggregationEngine
from erp.middleware.file_processor.domain.engine import FileProcessorEngine
from erp.middleware.inventory_voucher.domain.engine import InventoryVoucherEngine
from erp.middleware.masking_center.domain.engine import MaskingCenterEngine
from erp.middleware.notification_center.domain.engine import NotificationEngine
from erp.middleware.profit_engine.domain.engine import ProfitCalculationInput, ProfitEngine
from erp.middleware.task_scheduler.domain.engine import TaskSchedulerEngine
from erp.middleware.translation_center.domain.engine import TranslationCenterEngine
from erp.middleware.workflow_engine.domain.engine import WorkflowEngine


class TestNotificationEngine:
    def setup_method(self):
        self.engine = NotificationEngine()

    def test_register_template(self):
        template = self.engine.register_template("test.code", "测试标题 {{name}}", "测试内容 {{value}}", "email")
        assert template.code == "test.code"
        assert template.channel == "email"

    def test_render_template(self):
        self.engine.register_template("greet", "Hello {{name}}", "Welcome {{name}}!")
        result = self.engine.render_template("greet", {"name": "World"})
        assert result["title"] == "Hello World"
        assert result["body"] == "Welcome World!"

    def test_render_template_not_found(self):
        result = self.engine.render_template("nonexistent", {})
        assert result is None

    def test_send_notification(self):
        self.engine.register_template("order.test", "订单 {{no}}", "金额 {{amount}}")
        msg = self.engine.send("t1", "order.test", "user1", {"no": "ORD001", "amount": "100"})
        assert msg.status == "sent"
        assert "ORD001" in msg.title

    def test_send_notification_template_not_found(self):
        msg = self.engine.send("t1", "nonexistent", "user1")
        assert msg.status == "failed"

    def test_get_history(self):
        self.engine.register_template("h.test", "Test", "Body")
        self.engine.send("t1", "h.test", "u1")
        self.engine.send("t1", "h.test", "u2")
        history = self.engine.get_history("t1")
        assert len(history) == 2

    def test_mark_read(self):
        self.engine.register_template("mr.test", "Test", "Body")
        msg = self.engine.send("t1", "mr.test", "u1")
        result = self.engine.mark_read(msg.id)
        assert result.status == "read"
        assert result.read_at != ""

    def test_default_templates_exist(self):
        templates = self.engine.get_templates()
        codes = [t.code for t in templates]
        assert "order.created" in codes
        assert "inventory.low_stock" in codes


class TestFileProcessorEngine:
    def setup_method(self):
        self.engine = FileProcessorEngine()

    def test_upload_file(self):
        meta = self.engine.upload("t1", "test.jpg", b"fake image data", "pdm")
        assert meta.extension == "jpg"
        assert meta.is_image is True
        assert meta.status == "uploaded"

    def test_upload_invalid_extension(self):
        with pytest.raises(ValueError, match="not allowed"):
            self.engine.upload("t1", "test.exe", b"data")

    def test_upload_too_large(self):
        with pytest.raises(ValueError, match="exceeds"):
            self.engine.upload("t1", "test.jpg", b"x" * (51 * 1024 * 1024))

    def test_get_file(self):
        meta = self.engine.upload("t1", "doc.pdf", b"pdf content")
        result = self.engine.get_file(meta.file_id)
        assert result.filename == "doc.pdf"
        assert result.is_document is True

    def test_delete_file(self):
        meta = self.engine.upload("t1", "del.txt", b"delete me")
        result = self.engine.delete_file(meta.file_id)
        assert result["success"] is True
        assert self.engine.get_file(meta.file_id) is None

    def test_generate_preview_image(self):
        meta = self.engine.upload("t1", "img.png", b"image data")
        result = self.engine.generate_preview(meta.file_id)
        assert result["success"] is True
        assert result["type"] == "image"

    def test_generate_preview_unsupported(self):
        meta = self.engine.upload("t1", "data.csv", b"csv data")
        result = self.engine.generate_preview(meta.file_id)
        assert result["success"] is False

    def test_list_files(self):
        self.engine.upload("t1", "a.jpg", b"a")
        self.engine.upload("t1", "b.png", b"b")
        files = self.engine.list_files("t1")
        assert len(files) == 2


class TestWorkflowEngine:
    def setup_method(self):
        self.engine = WorkflowEngine()

    def test_create_definition(self):
        nodes = [{"node_id": "n1", "node_name": "审批", "node_type": "approval",
                  "assignee_ids": ["admin1"]}]
        defn = self.engine.create_definition("po-approval", "采购审批", "scm", "purchase_order", nodes)
        assert defn.flow_code == "po-approval"
        assert len(defn.nodes) == 1

    def test_create_definition_duplicate_code(self):
        nodes = [{"node_id": "n1", "node_name": "审批", "assignee_ids": ["a1"]}]
        self.engine.create_definition("dup-code", "Test", "sys", "test", nodes)
        with pytest.raises(ValueError, match="already exists"):
            self.engine.create_definition("dup-code", "Test2", "sys", "test", nodes)

    def test_start_instance(self):
        nodes = [{"node_id": "n1", "node_name": "审批", "node_type": "approval",
                  "assignee_ids": ["mgr1"]}]
        self.engine.create_definition("test-flow", "Test", "sys", "test", nodes)
        instance = self.engine.start_instance("test-flow", "t1", "BIZ001", "order", "user1")
        assert instance.status == "running"
        assert instance.current_node_id == "n1"

    def test_complete_task_approved(self):
        nodes = [
            {"node_id": "n1", "node_name": "一级审批", "node_type": "approval", "assignee_ids": ["mgr1"]},
            {"node_id": "n2", "node_name": "二级审批", "node_type": "approval", "assignee_ids": ["mgr2"]},
        ]
        self.engine.create_definition("two-step", "两级审批", "scm", "po", nodes)
        instance = self.engine.start_instance("two-step", "t1", "PO001", "po", "user1")
        tasks = self.engine.get_instance_tasks(instance.instance_id)
        result = self.engine.complete_task(tasks[0].task_id, "approved", "同意")
        assert result["success"] is True
        assert result["instance_status"] == "running"

    def test_complete_task_rejected(self):
        nodes = [{"node_id": "n1", "node_name": "审批", "assignee_ids": ["mgr1"]}]
        self.engine.create_definition("reject-flow", "Reject", "sys", "test", nodes)
        instance = self.engine.start_instance("reject-flow", "t1", "X1", "test", "u1")
        tasks = self.engine.get_instance_tasks(instance.instance_id)
        result = self.engine.complete_task(tasks[0].task_id, "rejected", "拒绝")
        assert result["instance_status"] == "rejected"


class TestTaskSchedulerEngine:
    def setup_method(self):
        self.engine = TaskSchedulerEngine()

    def test_create_job(self):
        job = self.engine.create_job("t1", "sync_inventory", "inventory", "0 */5 * * *",
                                      "InventorySyncHandler")
        assert job.job_name == "sync_inventory"
        assert job.status == "active"

    def test_pause_resume_job(self):
        job = self.engine.create_job("t1", "test_job", "test", "0 0 * * *", "TestHandler")
        result = self.engine.pause_job(job.job_id)
        assert result["status"] == "paused"
        result = self.engine.resume_job(job.job_id)
        assert result["status"] == "active"

    def test_execute_job(self):
        job = self.engine.create_job("t1", "exec_test", "test", "0 0 * * *", "ExecHandler")
        log = self.engine.execute_job(job.job_id)
        assert log.status == "success"

    def test_delete_job(self):
        job = self.engine.create_job("t1", "del_test", "test", "0 0 * * *", "DelHandler")
        result = self.engine.delete_job(job.job_id)
        assert result["success"] is True

    def test_get_job_logs(self):
        job = self.engine.create_job("t1", "log_test", "test", "0 0 * * *", "LogHandler")
        self.engine.execute_job(job.job_id)
        logs = self.engine.get_job_logs(job.job_id)
        assert len(logs) == 1


class TestAuthCenterEngine:
    def setup_method(self):
        self.engine = AuthCenterEngine()

    def test_refresh_cache_and_check(self):
        self.engine.refresh_cache("u1", "t1", ["admin"])
        result = self.engine.check_permission("u1", "iam:user:write")
        assert result["has_permission"] is True

    def test_check_permission_no_cache(self):
        result = self.engine.check_permission("unknown", "iam:user:read")
        assert result["has_permission"] is False

    def test_viewer_role(self):
        self.engine.refresh_cache("u2", "t1", ["viewer"])
        result = self.engine.check_permission("u2", "iam:user:write")
        assert result["has_permission"] is False
        result = self.engine.check_permission("u2", "iam:user:read")
        assert result["has_permission"] is True

    def test_list_permissions(self):
        perms = self.engine.list_permissions("iam")
        assert len(perms) > 0
        assert all(p["module"] == "iam" for p in perms)

    def test_list_roles(self):
        roles = self.engine.list_roles()
        codes = [r["role_code"] for r in roles]
        assert "admin" in codes
        assert "viewer" in codes


class TestAuditCenterEngine:
    def setup_method(self):
        self.engine = AuditCenterEngine()

    def test_log_and_query(self):
        self.engine.log("t1", "CREATE", "user", "u1", "Test User", "iam", actor_id="admin")
        results = self.engine.query("t1", domain="iam")
        assert len(results) == 1
        assert results[0].action == "CREATE"

    def test_query_with_filters(self):
        self.engine.log("t1", "CREATE", "user", "u1", domain="iam", actor_id="a1")
        self.engine.log("t1", "DELETE", "user", "u2", domain="iam", actor_id="a2")
        results = self.engine.query("t1", action="DELETE")
        assert len(results) == 1
        assert results[0].action == "DELETE"

    def test_diff_calculation(self):
        self.engine.log("t1", "UPDATE", "user", "u1", before={"name": "Old"}, after={"name": "New"})
        results = self.engine.query("t1")
        assert results[0].diff == {"name": {"before": "Old", "after": "New"}}

    def test_export(self):
        self.engine.log("t1", "CREATE", "order", "o1", domain="oms")
        exported = self.engine.export("t1")
        assert len(exported) == 1


class TestTranslationCenterEngine:
    def setup_method(self):
        self.engine = TranslationCenterEngine()

    def test_translate_same_language(self):
        result = self.engine.translate("产品", "zh", "zh")
        assert result == "产品"

    def test_translate_with_glossary(self):
        result = self.engine.translate("spu", "zh", "en", "pdm")
        assert result == "Standard Product Unit"

    def test_translate_passthrough(self):
        result = self.engine.translate("unknown term", "en", "ja")
        assert result == "unknown term"

    def test_batch_translate(self):
        results = self.engine.batch_translate(["spu", "sku"], "zh", "en", "pdm")
        assert results[0] == "Standard Product Unit"
        assert results[1] == "Stock Keeping Unit"

    def test_get_languages(self):
        langs = self.engine.get_languages()
        codes = [lang["code"] for lang in langs]
        assert "zh" in codes
        assert "en" in codes
        assert "ja" in codes

    def test_add_glossary(self):
        result = self.engine.add_glossary("custom", "hello", {"en": "Hello", "ja": "こんにちは"})
        assert result["entry_id"] == "custom.hello"
        translated = self.engine.translate("hello", "zh", "ja", "custom")
        assert translated == "こんにちは"


class TestMaskingCenterEngine:
    def setup_method(self):
        self.engine = MaskingCenterEngine()

    def test_mask_phone(self):
        result = self.engine.mask_value("13812345678", "phone")
        assert result == "138****5678"

    def test_mask_email(self):
        result = self.engine.mask_value("test@example.com", "email")
        assert "****" in result or "***" in result

    def test_mask_id_card(self):
        result = self.engine.mask_value("110101199001011234", "id_card")
        assert "**********" in result

    def test_mask_dict(self):
        data = {"phone": "13812345678", "email": "test@example.com", "name": "正常字段"}
        result = self.engine.mask_dict(data, tenant_id="t1")
        assert result["phone"] != "13812345678"
        assert result["name"] == "正常字段"

    def test_get_rules(self):
        rules = self.engine.get_rules()
        codes = [r["rule_code"] for r in rules]
        assert "phone" in codes
        assert "email" in codes

    def test_create_rule(self):
        result = self.engine.create_rule("custom_field", "自定义脱敏", "custom",
                                          r"(.{2}).+", r"\1**")
        assert result["rule_code"] == "custom_field"

    def test_mask_short_value(self):
        result = self.engine.mask_value("ab", "phone")
        assert result == "ab"

    def test_mask_default(self):
        result = self.engine.mask_value("abcdefghijk", "unknown_type")
        assert "****" in result


class TestApiPlatformEngine:
    def setup_method(self):
        self.engine = ApiPlatformEngine()

    def test_list_endpoints(self):
        endpoints = self.engine.list_endpoints()
        assert len(endpoints) > 0

    def test_list_endpoints_filter_service(self):
        endpoints = self.engine.list_endpoints(service="iam")
        assert all(e["service"] == "iam" for e in endpoints)

    def test_record_call(self):
        result = self.engine.record_call("t1", "/api/v1/orders", "GET", 200, 150)
        assert result["recorded"] is True

    def test_get_stats(self):
        self.engine.record_call("t1", "/api/v1/orders", "GET", 200, 100)
        self.engine.record_call("t1", "/api/v1/orders", "GET", 500, 200)
        stats = self.engine.get_stats("t1")
        assert stats["total_calls"] == 2
        assert stats["error_calls"] == 1

    def test_test_endpoint(self):
        result = self.engine.test_endpoint("/api/v1/test", "GET", {"key": "value"})
        assert result["status"] == "mock_success"


class TestConnectorPlatformEngine:
    def setup_method(self):
        self.engine = ConnectorPlatformEngine()

    def test_list_connectors(self):
        connectors = self.engine.list_connectors()
        assert len(connectors) > 0

    def test_list_connectors_filter_type(self):
        connectors = self.engine.list_connectors(connector_type="marketplace")
        assert all(c["connector_type"] == "marketplace" for c in connectors)

    def test_register_connector(self):
        result = self.engine.register_connector("marketplace", "Walmart API", "walmart")
        assert result["status"] == "registered"

    def test_health_check_all(self):
        result = self.engine.health_check()
        assert result["total"] > 0
        assert result["healthy"] == result["total"]

    def test_health_check_single(self):
        result = self.engine.health_check("amazon-sp")
        assert result["health_status"] == "healthy"

    def test_get_stats(self):
        self.engine.record_call("t1", "amazon-sp", True, 200)
        self.engine.record_call("t1", "amazon-sp", False, 500)
        stats = self.engine.get_stats("t1", "amazon-sp")
        assert stats["total_calls"] == 2
        assert stats["success_calls"] == 1


class TestCostEngine:
    def setup_method(self):
        self.engine = CostAggregationEngine()

    def test_collect_events(self):
        from erp.middleware.cost_engine.domain.engine import CostEvent
        events = [CostEvent(sku_id="sku1", cost_type="purchase", amount=100, currency="USD")]
        result = self.engine.collect_events(events)
        assert result["event_count"] == 1
        assert result["total"] == 100

    def test_generate_breakdown(self):
        from erp.middleware.cost_engine.domain.engine import CostEvent
        events = [CostEvent(sku_id="sku1", cost_type="purchase", amount=100),
                  CostEvent(sku_id="sku1", cost_type="shipping", amount=20)]
        result = self.engine.generate_breakdown("sku1", events)
        assert "purchase" in result.costs
        assert "shipping" in result.costs

    def test_allocate_shared_costs(self):
        weights = {"sku1": 60.0, "sku2": 40.0}
        result = self.engine.allocate_shared_costs(1000.0, weights)
        assert result["sku1"] == 600.0
        assert result["sku2"] == 400.0

    def test_calculate_fifo(self):
        layers = [{"quantity": 100, "unit_cost": 10.0, "date": "2024-01-01"},
                  {"quantity": 50, "unit_cost": 12.0, "date": "2024-01-15"}]
        result = self.engine.calculate_fifo_cost(layers, 120)
        assert result["quantity"] == 120
        assert result["total_cost"] == 1240.0


class TestProfitEngine:
    def setup_method(self):
        self.engine = ProfitEngine()

    def test_calculate_profit(self):
        result = self.engine.calculate(ProfitCalculationInput(
            revenue=1000, purchase_cost=400, head_freight=100,
            platform_commission=150, advertising_cost=50, payment_fee=30,
        ))
        assert result.gross_profit == 500
        assert result.gross_margin_pct == 50.0
        assert result.operating_profit == 270

    def test_calculate_settlement(self):
        result = self.engine.calculate_settlement(100, "amazon", cost_price=40, commission_rate=0.15)
        assert result["commission"] == 15.0
        assert result["profit"] == 45.0

    def test_aggregate_by_period(self):
        records = [
            {"month": "2024-01", "revenue": 1000, "cost": 600, "profit": 400},
            {"month": "2024-01", "revenue": 500, "cost": 300, "profit": 200},
            {"month": "2024-02", "revenue": 800, "cost": 500, "profit": 300},
        ]
        result = self.engine.aggregate_by_period(records, "month")
        assert result["2024-01"]["revenue"] == 1500
        assert result["2024-02"]["profit"] == 300


class TestInventoryVoucherEngine:
    def setup_method(self):
        self.engine = InventoryVoucherEngine()

    def test_create_voucher(self):
        lines = [{"sku_id": "sku1", "quantity": 10, "unit_cost": 50}]
        voucher = self.engine.create_voucher("purchase_in", "wh1", lines)
        assert voucher.voucher_type == "purchase_in"
        assert voucher.direction == "in"
        assert voucher.total_quantity == 10
        assert voucher.total_amount == 500.0

    def test_post_voucher(self):
        lines = [{"sku_id": "sku1", "quantity": 5, "unit_cost": 20}]
        voucher = self.engine.create_voucher("sales_out", "wh1", lines)
        result = self.engine.post_voucher(voucher)
        assert result["success"] is True
        assert result["status"] == "posted"

    def test_cancel_voucher(self):
        lines = [{"sku_id": "sku1", "quantity": 1, "unit_cost": 10}]
        voucher = self.engine.create_voucher("adjustment_in", "wh1", lines)
        result = self.engine.cancel_voucher(voucher, "error")
        assert result["success"] is True

    def test_generate_from_purchase(self):
        po = {"id": "PO001", "warehouse_id": "wh1", "operator_id": "u1",
              "items": [{"sku_id": "sku1", "sku_name": "Product A", "quantity": 20, "unit_cost": 30}]}
        voucher = self.engine.generate_from_purchase(po)
        assert voucher.voucher_type == "purchase_in"
        assert voucher.reference_type == "purchase_order"
        assert voucher.total_quantity == 20

    def test_generate_from_sales(self):
        so = {"id": "SO001", "warehouse_id": "wh1", "operator_id": "u2",
              "items": [{"sku_id": "sku1", "sku_name": "Product A", "quantity": 5, "unit_cost": 30}]}
        voucher = self.engine.generate_from_sales(so)
        assert voucher.voucher_type == "sales_out"
        assert voucher.direction == "out"
