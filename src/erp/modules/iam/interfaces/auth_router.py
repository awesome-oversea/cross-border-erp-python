from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.iam.application.auth_service import AuthService
from erp.modules.iam.infrastructure.repositories import SqlAuditLogRepository, SqlUserRoleRepository, SqlUserRepository
from erp.shared.context import trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result, UnauthorizedException
from erp.shared.observability.logging import get_logger

logger = get_logger("erp.iam.auth_router")

router = APIRouter(prefix="/iam/v1/auth", tags=["IAM-Auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=80)
    password: str = Field(..., min_length=8, max_length=128)
    tenant_id: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user_id: str
    tenant_id: str
    display_name: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


def _auth_service(session: AsyncSession = Depends(get_db_session)) -> AuthService:
    return AuthService(
        user_repo=SqlUserRepository(session),
        user_role_repo=SqlUserRoleRepository(session),
        audit_repo=SqlAuditLogRepository(session),
    )


def _build_token_response(result: dict) -> dict:
    from erp.bootstrap.config import get_settings
    settings = get_settings()
    data = TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        expires_in=settings.access_token_expire_minutes * 60,
        user_id=result["user_id"],
        tenant_id=result["tenant_id"],
        display_name=result["display_name"],
    )
    return data.model_dump()


@router.post("/login", response_model=None)
async def login(
    req: LoginRequest,
    request: Request,
    svc: AuthService = Depends(_auth_service),
):
    ip = request.client.host if request.client else ""
    result = await svc.login(
        username=req.username, password=req.password,
        tenant_id=req.tenant_id, ip=ip,
    )
    return Result.ok(data=_build_token_response(result), trace_id=trace_id_var.get(""))


@router.post("/refresh", response_model=None)
async def refresh_token(
    req: RefreshRequest,
    svc: AuthService = Depends(_auth_service),
):
    result = await svc.refresh_by_token(refresh_token=req.refresh_token)
    return Result.ok(data=_build_token_response(result), trace_id=trace_id_var.get(""))


@router.post("/logout", response_model=None)
async def logout(req: LogoutRequest):
    return Result.ok(message="Logged out successfully", trace_id=trace_id_var.get(""))
