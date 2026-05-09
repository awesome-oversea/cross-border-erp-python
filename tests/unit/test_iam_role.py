from unittest.mock import AsyncMock

import pytest

from erp.modules.iam.application.dtos import RoleCreateRequest, RoleUpdateRequest
from erp.modules.iam.application.services import RoleService
from erp.modules.iam.domain.models import Role
from erp.shared.exceptions import ConflictException, ForbiddenException, NotFoundException


@pytest.fixture
def mock_role_repo():
    return AsyncMock()


@pytest.fixture
def mock_rp_repo():
    return AsyncMock()


@pytest.fixture
def mock_audit_repo():
    repo = AsyncMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def role_service(mock_role_repo, mock_rp_repo, mock_audit_repo):
    return RoleService(mock_role_repo, mock_rp_repo, mock_audit_repo)


class TestRoleService:
    @pytest.mark.asyncio
    async def test_create_role_success(self, role_service, mock_role_repo):
        req = RoleCreateRequest(name="Admin", code="admin")
        mock_role_repo.get_by_code.return_value = None
        mock_role_repo.create.return_value = Role(
            id="r1", tenant_id="t1", name="Admin", code="admin",
            description="", role_type="custom", status="active", sort_order=0,
        )
        result = await role_service.create("t1", req)
        assert result.name == "Admin"
        assert result.code == "admin"

    @pytest.mark.asyncio
    async def test_create_role_duplicate_code(self, role_service, mock_role_repo):
        req = RoleCreateRequest(name="Admin", code="admin")
        mock_role_repo.get_by_code.return_value = Role(id="r1", code="admin")
        with pytest.raises(ConflictException):
            await role_service.create("t1", req)

    @pytest.mark.asyncio
    async def test_update_system_role_forbidden(self, role_service, mock_role_repo):
        mock_role_repo.get_by_id.return_value = Role(
            id="r1", tenant_id="t1", name="System", code="system",
            role_type="system", description="", status="active", sort_order=0,
        )
        req = RoleUpdateRequest(name="New Name")
        with pytest.raises(ForbiddenException):
            await role_service.update("r1", "t1", req)

    @pytest.mark.asyncio
    async def test_delete_system_role_forbidden(self, role_service, mock_role_repo):
        mock_role_repo.get_by_id.return_value = Role(
            id="r1", tenant_id="t1", name="System", code="system",
            role_type="system", description="", status="active", sort_order=0,
        )
        with pytest.raises(ForbiddenException):
            await role_service.delete("r1", "t1")

    @pytest.mark.asyncio
    async def test_get_role_not_found(self, role_service, mock_role_repo):
        mock_role_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundException):
            await role_service.get("nonexistent", "t1")
