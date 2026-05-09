from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def app():
    from erp.main import create_app
    return create_app()


@pytest.fixture(scope="session")
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def tenant_headers():
    return {
        "X-Tenant-ID": "tenant-00000000-0000-0000-0000-000000000001",
        "X-Actor-ID": "user-00000000-0000-0000-0000-000000000001",
        "X-Actor-Type": "user",
    }


@pytest.fixture
def pms_headers():
    return {
        "X-Tenant-ID": "tenant-00000000-0000-0000-0000-000000000001",
        "X-Actor-ID": "pms-client-001",
        "X-Actor-Type": "pms",
    }
