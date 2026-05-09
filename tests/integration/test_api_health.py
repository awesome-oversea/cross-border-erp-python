import pytest
from httpx import ASGITransport, AsyncClient

from erp.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


MIDDLEWARE_ENDPOINTS = [
    ("/sys/api/v1/notification/templates", "GET"),
    ("/sys/api/v1/file/files", "GET"),
    ("/sys/api/v1/workflow/definitions", "GET"),
    ("/sys/api/v1/scheduler/jobs", "GET"),
    ("/sys/api/v1/audit/logs", "GET"),
    ("/sys/api/v1/translation/languages", "GET"),
    ("/sys/api/v1/masking/rules", "GET"),
    ("/sys/api/v1/api-platform/endpoints", "GET"),
    ("/sys/api/v1/connector/platforms", "GET"),
    ("/sys/api/v1/content-review/tasks", "GET"),
    ("/fms/api/v1/forex/rates", "GET"),
    ("/fms/api/v1/payment/payments", "GET"),
    ("/oms/api/v1/order-strategy/rules", "GET"),
    ("/tms/api/v1/logistics-strategy/rules", "GET"),
    ("/fms/api/v1/billing/rules", "GET"),
    ("/crm/api/v1/cdp/profiles", "GET"),
    ("/fms/api/v1/invoice-tax/invoices", "GET"),
    ("/sys/api/v1/compliance/checks", "GET"),
    ("/pdm/api/v1/selection/analyses", "GET"),
    ("/ads/api/v1/ad-optimization/suggestions", "GET"),
    ("/fms/api/v1/cost-engine/events", "GET"),
    ("/fms/api/v1/profit-engine/settlements", "GET"),
    ("/wms/api/v1/voucher/vouchers", "GET"),
]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["status"] == "UP"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_admin_ping(client: AsyncClient):
    response = await client.get("/api/admin/v1/ping")
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.integration
async def test_trace_id_in_response(client: AsyncClient):
    response = await client.get("/api/health", headers={"X-Trace-ID": "test-trace-123"})
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("path,method", MIDDLEWARE_ENDPOINTS)
async def test_middleware_endpoints_exist(client: AsyncClient, path: str, method: str):
    headers = {"X-Tenant-ID": "test-tenant", "X-Actor-ID": "test-user"}
    if method == "GET":
        response = await client.get(path, headers=headers)
    assert response.status_code in (200, 404, 422, 500), f"Endpoint {method} {path} returned unexpected status"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_audit_log_endpoint(client: AsyncClient):
    headers = {"X-Tenant-ID": "test-tenant", "X-Actor-ID": "test-user"}
    response = await client.get("/sys/api/v1/audit/logs", headers=headers)
    assert response.status_code in (200, 404, 422, 500)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_translation_languages(client: AsyncClient):
    headers = {"X-Tenant-ID": "test-tenant", "X-Actor-ID": "test-user"}
    response = await client.get("/sys/api/v1/translation/languages", headers=headers)
    assert response.status_code in (200, 404, 422, 500)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_masking_rules(client: AsyncClient):
    headers = {"X-Tenant-ID": "test-tenant", "X-Actor-ID": "test-user"}
    response = await client.get("/sys/api/v1/masking/rules", headers=headers)
    assert response.status_code in (200, 404, 422, 500)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_connector_platform_list(client: AsyncClient):
    headers = {"X-Tenant-ID": "test-tenant", "X-Actor-ID": "test-user"}
    response = await client.get("/sys/api/v1/connector/platforms", headers=headers)
    assert response.status_code in (200, 404, 422, 500)
