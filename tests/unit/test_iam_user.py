from unittest.mock import AsyncMock

import pytest

from erp.modules.iam.application.dtos import PasswordChangeRequest, UserCreateRequest
from erp.modules.iam.application.services import UserService
from erp.modules.iam.domain.auth import hash_password
from erp.modules.iam.domain.models import User
from erp.shared.exceptions import ConflictException, ForbiddenException, NotFoundException


@pytest.fixture
def mock_user_repo():
    return AsyncMock()


@pytest.fixture
def mock_role_repo():
    return AsyncMock()


@pytest.fixture
def mock_audit_repo():
    repo = AsyncMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def user_service(mock_user_repo, mock_role_repo, mock_audit_repo):
    return UserService(mock_user_repo, mock_role_repo, mock_audit_repo)


class TestUserService:
    @pytest.mark.asyncio
    async def test_create_user_success(self, user_service, mock_user_repo):
        req = UserCreateRequest(username="john", password="Secret1234")
        mock_user_repo.get_by_username.return_value = None
        mock_user_repo.create.return_value = User(
            id="u1", tenant_id="t1", username="john", email="", phone="",
            password_hash=hash_password("Secret1234"), display_name="", avatar_url="",
            status="active", user_type="internal", must_change_pwd=False,
        )
        result = await user_service.create("t1", req)
        assert result.username == "john"
        assert result.tenant_id == "t1"

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self, user_service, mock_user_repo):
        req = UserCreateRequest(username="john", password="Secret1234")
        mock_user_repo.get_by_username.return_value = User(
            id="u1", tenant_id="t1", username="john",
        )
        with pytest.raises(ConflictException):
            await user_service.create("t1", req)

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, user_service, mock_user_repo):
        mock_user_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundException):
            await user_service.get("nonexistent", "t1")

    @pytest.mark.asyncio
    async def test_change_password_wrong_old(self, user_service, mock_user_repo):
        mock_user_repo.get_by_id.return_value = User(
            id="u1", tenant_id="t1", username="john",
            password_hash=hash_password("correct_old"),
        )
        req = PasswordChangeRequest(old_password="wrong_old", new_password="newpass1234")
        with pytest.raises(ForbiddenException):
            await user_service.change_password("u1", "t1", req)
