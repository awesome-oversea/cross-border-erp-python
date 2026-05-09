from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from erp.modules.iam.interfaces.deps import get_current_user
from erp.shared.db.session import get_db_session


def _make_db_mock():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_scalars.first.return_value = None
    mock_scalars.one_or_none.return_value = None
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalar.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.delete = AsyncMock()
    mock_session.refresh = AsyncMock()
    return mock_session


@pytest.fixture(autouse=True)
def _override_db(app):
    mock_session = _make_db_mock()
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "user-00000000-0000-0000-0000-000000000001",
        "tenant_id": "tenant-00000000-0000-0000-0000-000000000001",
        "roles": ["admin"],
        "username": "integration-user",
    }
    yield
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_current_user, None)


class TestHealthEndpoint:
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_health_returns_200(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_ping_returns_200(self, client):
        resp = await client.get("/api/admin/v1/ping")
        assert resp.status_code == 200


class TestIAMEndpoints:
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_tenants_requires_tenant_header(self, client):
        resp = await client.get("/api/iam/v1/tenants", headers={"X-Actor-ID": "user-1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 422
        assert body["message"] == "X-Tenant-ID header is required"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_tenants_requires_actor_header(self, client):
        resp = await client.get("/api/iam/v1/tenants", headers={"X-Tenant-ID": "tenant-1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 422
        assert body["message"] == "X-Actor-ID header is required"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_tenants(self, client, tenant_headers):
        resp = await client.get("/api/iam/v1/tenants", headers=tenant_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_users(self, client, tenant_headers):
        resp = await client.get("/api/iam/v1/users", headers=tenant_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_roles(self, client, tenant_headers):
        resp = await client.get("/api/iam/v1/roles", headers=tenant_headers)
        assert resp.status_code == 200


class TestPDMEndpoints:
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_spus(self, client, tenant_headers):
        resp = await client.get("/api/pdm/v1/spus", headers=tenant_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_skus(self, client, tenant_headers):
        resp = await client.get("/api/pdm/v1/skus", headers=tenant_headers)
        assert resp.status_code == 200


class TestOMSEndpoints:
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_orders(self, client, tenant_headers):
        resp = await client.get("/api/oms/v1/orders", headers=tenant_headers)
        assert resp.status_code == 200


class TestWMSEndpoints:
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_warehouses(self, client, tenant_headers):
        resp = await client.get("/api/wms/v1/warehouses", headers=tenant_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_inventory(self, client, tenant_headers):
        resp = await client.get("/api/wms/v1/inventory", headers=tenant_headers)
        assert resp.status_code == 200


class TestFMSEndpoints:
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_cost_events(self, client, tenant_headers):
        resp = await client.get("/api/fms/v1/cost-events", headers=tenant_headers)
        assert resp.status_code == 200


class TestSYSEndpoints:
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_params(self, client, tenant_headers):
        resp = await client.get("/api/sys/v1/params", headers=tenant_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_connectors(self, client, tenant_headers):
        resp = await client.get("/api/sys/v1/connectors", headers=tenant_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_ai_switches(self, client, tenant_headers):
        resp = await client.get("/api/sys/v1/ai-switches", headers=tenant_headers)
        assert resp.status_code == 200
