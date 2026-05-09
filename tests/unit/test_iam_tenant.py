from unittest.mock import AsyncMock

import pytest

from erp.modules.iam.application.dtos import TenantCreateRequest, TenantUpdateRequest
from erp.modules.iam.application.services import TenantService
from erp.modules.iam.domain.models import Tenant
from erp.shared.exceptions import ConflictException, NotFoundException


@pytest.fixture
def mock_tenant_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_audit_repo():
    repo = AsyncMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def tenant_service(mock_tenant_repo, mock_audit_repo):
    return TenantService(mock_tenant_repo, mock_audit_repo)


class TestTenantService:
    @pytest.mark.asyncio
    async def test_create_tenant_success(self, tenant_service, mock_tenant_repo):
        req = TenantCreateRequest(name="Test Corp", code="test_corp")
        mock_tenant_repo.get_by_code.return_value = None
        mock_tenant_repo.create.return_value = Tenant(
            id="t1", name="Test Corp", code="test_corp", status="active", plan="free",
            max_users=10, max_stores=5, contact_name="", contact_email="",
            contact_phone="", logo_url="", config_json="{}",
        )
        result = await tenant_service.create(req)
        assert result.name == "Test Corp"
        assert result.code == "test_corp"
        mock_tenant_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_tenant_duplicate_code(self, tenant_service, mock_tenant_repo):
        req = TenantCreateRequest(name="Test Corp", code="test_corp")
        mock_tenant_repo.get_by_code.return_value = Tenant(
            id="t1", name="Existing", code="test_corp", status="active", plan="free",
            max_users=10, max_stores=5, contact_name="", contact_email="",
            contact_phone="", logo_url="", config_json="{}",
        )
        with pytest.raises(ConflictException):
            await tenant_service.create(req)

    @pytest.mark.asyncio
    async def test_get_tenant_success(self, tenant_service, mock_tenant_repo):
        mock_tenant_repo.get_by_id.return_value = Tenant(
            id="t1", name="Test Corp", code="test_corp", status="active", plan="free",
            max_users=10, max_stores=5, contact_name="", contact_email="",
            contact_phone="", logo_url="", config_json="{}",
        )
        result = await tenant_service.get("t1")
        assert result.id == "t1"
        assert result.name == "Test Corp"

    @pytest.mark.asyncio
    async def test_get_tenant_not_found(self, tenant_service, mock_tenant_repo):
        mock_tenant_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundException):
            await tenant_service.get("nonexistent")

    @pytest.mark.asyncio
    async def test_update_tenant_success(self, tenant_service, mock_tenant_repo):
        existing = Tenant(
            id="t1", name="Old Name", code="test_corp", status="active", plan="free",
            max_users=10, max_stores=5, contact_name="", contact_email="",
            contact_phone="", logo_url="", config_json="{}",
        )
        mock_tenant_repo.get_by_id.return_value = existing
        mock_tenant_repo.update.return_value = existing
        req = TenantUpdateRequest(name="New Name")
        result = await tenant_service.update("t1", req)
        assert result.name == "New Name"

    @pytest.mark.asyncio
    async def test_delete_tenant_success(self, tenant_service, mock_tenant_repo):
        mock_tenant_repo.get_by_id.return_value = Tenant(
            id="t1", name="Test Corp", code="test_corp", status="active", plan="free",
            max_users=10, max_stores=5, contact_name="", contact_email="",
            contact_phone="", logo_url="", config_json="{}",
        )
        mock_tenant_repo.soft_delete.return_value = True
        result = await tenant_service.delete("t1")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_tenant_not_found(self, tenant_service, mock_tenant_repo):
        mock_tenant_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundException):
            await tenant_service.delete("nonexistent")
