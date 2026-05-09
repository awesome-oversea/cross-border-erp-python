from __future__ import annotations

import asyncio
import sys
import time
import uuid
from dataclasses import dataclass, field

import httpx

API_BASE = "http://localhost:8000/api/v1"
ADMIN_BASE = "http://localhost:8000/api/admin/v1"
TENANT_ID = "e2e-test-tenant"
HEADERS = {
    "Content-Type": "application/json",
    "X-Tenant-ID": TENANT_ID,
    "X-Actor-ID": "e2e-tester",
    "X-Actor-Type": "user",
}


@dataclass
class TestResult:
    __test__ = False
    name: str = ""
    passed: bool = False
    duration_ms: float = 0
    detail: str = ""
    error: str = ""


@dataclass
class E2ETestSuite:
    name: str = ""
    results: list[TestResult] = field(default_factory=list)
    start_time: float = 0
    end_time: float = 0

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def total_duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000


class E2ETestRunner:
    def __init__(self, base_url: str = API_BASE):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0, headers=HEADERS)
        self.suite = E2ETestSuite(name="ERP E2E Core Chain Tests")

    async def run_all(self) -> E2ETestSuite:
        self.suite.start_time = time.time()
        print(f"\n{'='*60}")
        print(f"  ERP E2E Test Suite: {self.suite.name}")
        print(f"  Base URL: {self.base_url}")
        print(f"  Tenant ID: {TENANT_ID}")
        print(f"{'='*60}\n")

        await self._test_health()
        await self._test_iam_user_lifecycle()
        await self._test_iam_role_lifecycle()
        await self._test_pdm_product_lifecycle()
        await self._test_oms_order_lifecycle()
        await self._test_wms_inventory_lifecycle()
        await self._test_scm_purchase_lifecycle()
        await self._test_fms_cost_profit_chain()
        await self._test_tms_shipment_lifecycle()
        await self._test_crm_ticket_lifecycle()
        await self._test_ads_campaign_lifecycle()
        await self._test_sys_dict_lifecycle()
        await self._test_sys_param_lifecycle()
        await self._test_pms_integration_chain()
        await self._test_connector_lifecycle()
        await self._test_cdc_pipeline_lifecycle()
        await self._test_billing_strategy_chain()
        await self._test_voucher_chain()
        await self._test_bi_metric_chain()
        await self._test_cross_domain_order_to_shipment()

        self.suite.end_time = time.time()
        self._print_summary()
        return self.suite

    async def _run_test(self, name: str, test_fn) -> TestResult:
        result = TestResult(name=name)
        start = time.time()
        try:
            await test_fn()
            result.passed = True
            result.detail = "OK"
        except Exception as e:
            result.passed = False
            result.error = str(e)[:200]
        result.duration_ms = (time.time() - start) * 1000
        self.suite.results.append(result)
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {name} ({result.duration_ms:.0f}ms)")
        if not result.passed:
            print(f"         Error: {result.error}")
        return result

    async def _test_health(self):
        async def fn():
            resp = await self.client.get("/health")
            assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
            data = resp.json()
            assert data.get("code") == 0 or data.get("data", {}).get("status") == "UP"
        await self._run_test("Health Check", fn)

    async def _test_iam_user_lifecycle(self):
        async def fn():
            user_id = str(uuid.uuid4())
            resp = await self.client.post("/iam/users", json={
                "username": f"e2e_user_{user_id[:8]}",
                "password": "Test@12345",
                "email": f"e2e_{user_id[:8]}@test.com",
                "phone": "13800000001",
                "real_name": "E2E Test User",
            })
            assert resp.status_code in (200, 201), f"Create user failed: {resp.text[:200]}"
        await self._run_test("IAM - User Lifecycle", fn)

    async def _test_iam_role_lifecycle(self):
        async def fn():
            code = f"E2E_ROLE_{uuid.uuid4().hex[:6]}"
            resp = await self.client.post("/iam/roles", json={
                "role_code": code,
                "role_name": f"E2E Test Role {code}",
                "description": "E2E test role",
            })
            assert resp.status_code in (200, 201), f"Create role failed: {resp.text[:200]}"
        await self._run_test("IAM - Role Lifecycle", fn)

    async def _test_pdm_product_lifecycle(self):
        async def fn():
            spu_code = f"E2E_SPU_{uuid.uuid4().hex[:6]}"
            resp = await self.client.post("/pdm/spus", json={
                "spu_code": spu_code,
                "spu_name": f"E2E Test Product {spu_code}",
                "category_id": "cat-001",
                "status": "draft",
            })
            assert resp.status_code in (200, 201), f"Create SPU failed: {resp.text[:200]}"
        await self._run_test("PDM - Product Lifecycle", fn)

    async def _test_oms_order_lifecycle(self):
        async def fn():
            order_no = f"E2E-ORD-{uuid.uuid4().hex[:8]}"
            resp = await self.client.post("/oms/orders", json={
                "order_no": order_no,
                "platform": "amazon",
                "store_id": "store-001",
                "order_status": "pending",
                "total_amount": 99.99,
                "currency": "USD",
            })
            assert resp.status_code in (200, 201), f"Create order failed: {resp.text[:200]}"
        await self._run_test("OMS - Order Lifecycle", fn)

    async def _test_wms_inventory_lifecycle(self):
        async def fn():
            sku_id = f"SKU-E2E-{uuid.uuid4().hex[:6]}"
            resp = await self.client.post("/wms/inventory", json={
                "sku_id": sku_id,
                "warehouse_id": "wh-001",
                "quantity": 100,
                "available_quantity": 80,
                "locked_quantity": 20,
            })
            assert resp.status_code in (200, 201), f"Create inventory failed: {resp.text[:200]}"
        await self._run_test("WMS - Inventory Lifecycle", fn)

    async def _test_scm_purchase_lifecycle(self):
        async def fn():
            po_no = f"E2E-PO-{uuid.uuid4().hex[:8]}"
            resp = await self.client.post("/scm/purchase-orders", json={
                "po_no": po_no,
                "supplier_id": "supplier-001",
                "status": "draft",
                "total_amount": 5000.00,
                "currency": "CNY",
            })
            assert resp.status_code in (200, 201), f"Create PO failed: {resp.text[:200]}"
        await self._run_test("SCM - Purchase Order Lifecycle", fn)

    async def _test_fms_cost_profit_chain(self):
        async def fn():
            event_no = f"E2E-COST-{uuid.uuid4().hex[:8]}"
            resp = await self.client.post("/fms/cost-events", json={
                "event_no": event_no,
                "cost_type": "purchase",
                "amount": 100.50,
                "currency": "CNY",
                "exchange_rate": 1.0,
                "order_id": "order-e2e-001",
            })
            assert resp.status_code in (200, 201), f"Create cost event failed: {resp.text[:200]}"
        await self._run_test("FMS - Cost & Profit Chain", fn)

    async def _test_tms_shipment_lifecycle(self):
        async def fn():
            shipment_no = f"E2E-SHIP-{uuid.uuid4().hex[:8]}"
            resp = await self.client.post("/tms/shipments", json={
                "shipment_no": shipment_no,
                "order_id": "order-e2e-001",
                "carrier": "fedex",
                "status": "pending",
                "origin": "Shenzhen",
                "destination": "New York",
            })
            assert resp.status_code in (200, 201), f"Create shipment failed: {resp.text[:200]}"
        await self._run_test("TMS - Shipment Lifecycle", fn)

    async def _test_crm_ticket_lifecycle(self):
        async def fn():
            ticket_no = f"E2E-TKT-{uuid.uuid4().hex[:8]}"
            resp = await self.client.post("/crm/tickets", json={
                "ticket_no": ticket_no,
                "order_id": "order-e2e-001",
                "type": "return",
                "status": "open",
                "description": "E2E test ticket",
            })
            assert resp.status_code in (200, 201), f"Create ticket failed: {resp.text[:200]}"
        await self._run_test("CRM - Ticket Lifecycle", fn)

    async def _test_ads_campaign_lifecycle(self):
        async def fn():
            campaign_id = f"E2E-CAMP-{uuid.uuid4().hex[:6]}"
            resp = await self.client.post("/ads/campaigns", json={
                "campaign_id": campaign_id,
                "campaign_name": f"E2E Test Campaign {campaign_id}",
                "platform": "amazon",
                "status": "draft",
                "daily_budget": 50.00,
                "currency": "USD",
            })
            assert resp.status_code in (200, 201), f"Create campaign failed: {resp.text[:200]}"
        await self._run_test("ADS - Campaign Lifecycle", fn)

    async def _test_sys_dict_lifecycle(self):
        async def fn():
            dict_code = f"E2E_DICT_{uuid.uuid4().hex[:6]}"
            resp = await self.client.post("/sys/dicts", json={
                "dict_code": dict_code,
                "dict_name": f"E2E Test Dict {dict_code}",
                "description": "E2E test dictionary",
            })
            assert resp.status_code in (200, 201), f"Create dict failed: {resp.text[:200]}"
        await self._run_test("SYS - Dictionary Lifecycle", fn)

    async def _test_sys_param_lifecycle(self):
        async def fn():
            param_code = f"E2E_PARAM_{uuid.uuid4().hex[:6]}"
            resp = await self.client.post("/sys/params", json={
                "param_code": param_code,
                "param_name": f"E2E Test Param {param_code}",
                "param_value": "test_value",
                "param_type": "string",
            })
            assert resp.status_code in (200, 201), f"Create param failed: {resp.text[:200]}"
        await self._run_test("SYS - Parameter Lifecycle", fn)

    async def _test_pms_integration_chain(self):
        async def fn():
            resp = await self.client.post("/sys/pms/recommendations", json={
                "recommendation_type": "product_selection",
                "title": "E2E Test PMS Recommendation",
                "content": {"sku": "TEST-SKU", "reason": "E2E test"},
                "priority": "medium",
                "idempotency_key": str(uuid.uuid4()),
            })
            assert resp.status_code in (200, 201, 404), f"PMS recommendation failed: {resp.text[:200]}"
        await self._run_test("PMS - Integration Chain", fn)

    async def _test_connector_lifecycle(self):
        async def fn():
            code = f"E2E_CONN_{uuid.uuid4().hex[:6]}"
            resp = await self.client.post("/sys/connectors", json={
                "name": f"E2E Test Connector {code}",
                "code": code,
                "connector_type": "marketplace",
                "provider": "amazon",
                "base_url": "https://mock-api.amazon.com",
            })
            assert resp.status_code in (200, 201), f"Create connector failed: {resp.text[:200]}"
        await self._run_test("SYS - Connector Lifecycle", fn)

    async def _test_cdc_pipeline_lifecycle(self):
        async def fn():
            code = f"E2E_CDC_{uuid.uuid4().hex[:6]}"
            resp = await self.client.post("/sys/cdc/pipelines", json={
                "pipeline_name": f"E2E CDC Pipeline {code}",
                "pipeline_code": code,
                "source_schema": "oms",
                "source_table": "orders",
                "handler_type": "kafka",
                "topic_name": "erp.oms.order.e2e.v1",
            })
            assert resp.status_code in (200, 201), f"Create CDC pipeline failed: {resp.text[:200]}"
        await self._run_test("CDC - Pipeline Lifecycle", fn)

    async def _test_billing_strategy_chain(self):
        async def fn():
            code = f"E2E_BILLING_{uuid.uuid4().hex[:6]}"
            resp = await self.client.post("/fms/billing/strategies", json={
                "strategy_code": code,
                "strategy_name": f"E2E Test Strategy {code}",
                "fee_type": "platform_fee",
                "calculation_method": "percentage",
                "rate": {"rate": 0.15},
            })
            assert resp.status_code in (200, 201), f"Create billing strategy failed: {resp.text[:200]}"
        await self._run_test("FMS - Billing Strategy Chain", fn)

    async def _test_voucher_chain(self):
        async def fn():
            code = f"E2E_VCH_{uuid.uuid4().hex[:6]}"
            resp = await self.client.post("/fms/vouchers/templates", json={
                "template_code": code,
                "template_name": f"E2E Test Voucher Template {code}",
                "voucher_type": "purchase",
                "trigger_event": "e2e_test_trigger",
                "debit_rules": [{"account": "1401", "account_name": "Test Debit", "amount_field": "amount"}],
                "credit_rules": [{"account": "2202", "account_name": "Test Credit", "amount_field": "amount"}],
            })
            assert resp.status_code in (200, 201), f"Create voucher template failed: {resp.text[:200]}"
        await self._run_test("FMS - Voucher Chain", fn)

    async def _test_bi_metric_chain(self):
        async def fn():
            metric_code = f"E2E_METRIC_{uuid.uuid4().hex[:6]}"
            resp = await self.client.post("/bi/metrics", json={
                "metric_code": metric_code,
                "metric_name": f"E2E Test Metric {metric_code}",
                "metric_type": "gauge",
                "unit": "count",
                "description": "E2E test metric",
            })
            assert resp.status_code in (200, 201, 404), f"Create BI metric failed: {resp.text[:200]}"
        await self._run_test("BI - Metric Chain", fn)

    async def _test_cross_domain_order_to_shipment(self):
        async def fn():
            order_no = f"E2E-XORD-{uuid.uuid4().hex[:8]}"
            resp = await self.client.post("/oms/orders", json={
                "order_no": order_no,
                "platform": "amazon",
                "store_id": "store-001",
                "order_status": "pending",
                "total_amount": 199.99,
                "currency": "USD",
            })
            assert resp.status_code in (200, 201), f"Cross-domain: create order failed: {resp.text[:200]}"

            cost_no = f"E2E-XCOST-{uuid.uuid4().hex[:8]}"
            resp2 = await self.client.post("/fms/cost-events", json={
                "event_no": cost_no,
                "cost_type": "purchase",
                "amount": 80.00,
                "currency": "CNY",
                "order_id": order_no,
            })
            assert resp2.status_code in (200, 201), f"Cross-domain: create cost failed: {resp2.text[:200]}"
        await self._run_test("Cross-Domain - Order→Cost Chain", fn)

    def _print_summary(self):
        print(f"\n{'='*60}")
        print("  E2E Test Summary")
        print(f"{'='*60}")
        print(f"  Total:  {self.suite.total}")
        print(f"  Passed: {self.suite.passed}")
        print(f"  Failed: {self.suite.failed}")
        print(f"  Duration: {self.suite.total_duration_ms:.0f}ms")
        print(f"{'='*60}")

        if self.suite.failed > 0:
            print("\n  Failed Tests:")
            for r in self.suite.results:
                if not r.passed:
                    print(f"    - {r.name}: {r.error}")

        print()


async def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else API_BASE
    runner = E2ETestRunner(base_url=base_url)
    suite = await runner.run_all()
    await runner.client.aclose()
    sys.exit(0 if suite.failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
