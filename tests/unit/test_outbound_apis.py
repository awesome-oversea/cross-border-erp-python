from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from erp.shared.db.session import get_db_session

HEADERS = {"X-Tenant-ID": "t1", "X-Actor-ID": "u1", "X-Actor-Type": "pms"}


@pytest.fixture(autouse=True)
def _override_db(app):
    mock_session = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session
    yield
    app.dependency_overrides.pop(get_db_session, None)


class TestFmsOutbound:
    @pytest.mark.asyncio
    async def test_get_cost_for_pms(self, client):
        resp = await client.get("/fms/api/out/v1/pms/cost/B001", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["asin"] == "B001"

    @pytest.mark.asyncio
    async def test_get_profit_for_pms(self, client):
        resp = await client.get("/fms/api/out/v1/pms/profit/B001", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "profit" in body["data"]

    @pytest.mark.asyncio
    async def test_get_profit_margin(self, client):
        resp = await client.get("/fms/api/out/v1/pms/profit/margin", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0

    @pytest.mark.asyncio
    async def test_export_journal_entries(self, client):
        resp = await client.post("/fms/api/out/v1/journal-entries/export",
                                  json={"period_start": "2025-01-01", "period_end": "2025-01-31"},
                                  headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0

    @pytest.mark.asyncio
    async def test_push_kingdee(self, client):
        resp = await client.post("/fms/api/out/v1/inventory-cost/push-kingdee",
                                  json={"period": "2025-01"}, headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["target"] == "kingdee"

    @pytest.mark.asyncio
    async def test_push_voucher_kingdee(self, client):
        resp = await client.post("/fms/api/out/v1/voucher-engine/push-kingdee?voucher_id=v1",
                                  headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["target"] == "kingdee"

    @pytest.mark.asyncio
    async def test_push_voucher_yonyou(self, client):
        resp = await client.post("/fms/api/out/v1/voucher-engine/push-yonyou?voucher_id=v1",
                                  headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["target"] == "yonyou"


class TestAdsOutbound:
    @pytest.mark.asyncio
    async def test_get_performance(self, client):
        resp = await client.get("/ads/api/out/v1/analytics/performance", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0

    @pytest.mark.asyncio
    async def test_update_strategy(self, client):
        resp = await client.put("/ads/api/out/v1/strategies/s1",
                                 json={"daily_budget": 100.0}, headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["updated"] is True

    @pytest.mark.asyncio
    async def test_allocate_budget(self, client):
        resp = await client.post("/ads/api/out/v1/optimization/budget-allocate",
                                  json={"campaign_ids": ["c1", "c2"], "total_budget": 200.0},
                                  headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]["allocations"]) == 2


class TestPdmOutbound:
    @pytest.mark.asyncio
    async def test_create_suggestion(self, client):
        resp = await client.post("/pdm/api/out/v1/suggestions",
                                  json={"title": "New product idea", "market": "US"},
                                  headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["source"] == "pms"

    @pytest.mark.asyncio
    async def test_update_product(self, client):
        resp = await client.put("/pdm/api/out/v1/products/p1",
                                 json={"name": "Updated"}, headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["updated"] is True


class TestSomOutbound:
    @pytest.mark.asyncio
    async def test_optimize_listing(self, client):
        resp = await client.put("/som/api/out/v1/listings/l1",
                                 json={"title": "Optimized title"}, headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["optimized"] is True

    @pytest.mark.asyncio
    async def test_adjust_price(self, client):
        resp = await client.put("/som/api/out/v1/listings/l1/price",
                                 json={"price": 29.99}, headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["price"] == 29.99


class TestSysOutbound:
    @pytest.mark.asyncio
    async def test_send_notification(self, client):
        resp = await client.post("/sys/api/out/v1/notification/send",
                                  json={"channel": "email", "recipients": ["a@b.com"],
                                        "subject": "Alert", "content": "Low stock"},
                                  headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] == "sent"


class TestOmsOutbound:
    @pytest.mark.asyncio
    async def test_get_risk_alerts(self, client):
        resp = await client.get("/oms/api/out/v1/risk-alerts", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0

    @pytest.mark.asyncio
    async def test_mark_order_risk(self, client):
        resp = await client.put("/oms/api/out/v1/orders/o1/risk-mark",
                                 json={"risk_level": "high", "risk_flags": ["fraud"]},
                                 headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["risk_level"] == "high"


class TestScmOutbound:
    @pytest.mark.asyncio
    async def test_create_replenishment_advice(self, client):
        resp = await client.post("/scm/api/out/v1/replenishment-advice",
                                  json={"warehouse_id": "wh1", "sku_ids": ["sku1"],
                                        "suggested_qty": 100},
                                  headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["source"] == "pms"

    @pytest.mark.asyncio
    async def test_mark_supplier_risk(self, client):
        resp = await client.put("/scm/api/out/v1/suppliers/s1/risk-mark",
                                 json={"risk_level": "high", "risk_type": "delivery"},
                                 headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["risk_level"] == "high"
