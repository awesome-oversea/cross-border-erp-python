from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.sys.domain.store_auth_models import StoreAuthorizationService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/store-authorizations", tags=["SYS-StoreAuth"])


class AuthorizeStoreRequest(BaseModel):
    store_id: str = Field(..., min_length=1, max_length=36)
    store_name: str = Field(..., min_length=1, max_length=200)
    platform: str = Field(..., min_length=1, max_length=50)
    marketplace_id: str = Field(default="", max_length=100)
    seller_id: str = Field(default="", max_length=100)
    region: str = Field(default="", max_length=20)
    auth_type: str = Field(default="oauth2", max_length=30)
    access_token: str = Field(default="")
    refresh_token: str = Field(default="")
    token_expiry: datetime | None = None
    token_scope: str = Field(default="")
    auth_meta: dict = Field(default_factory=dict)


class RefreshTokenRequest(BaseModel):
    new_access_token: str = Field(default="")
    new_refresh_token: str = Field(default="")
    new_token_expiry: datetime | None = None
    refresh_type: str = Field(default="manual", pattern=r"^(auto|manual)$")


class RevokeRequest(BaseModel):
    reason: str = Field(default="", max_length=500)


@router.post("", response_model=None)
async def authorize_store(req: AuthorizeStoreRequest, session: AsyncSession = Depends(get_db_session)):
    svc = StoreAuthorizationService(session)
    auth = await svc.authorize_store(
        tenant_id=tenant_id_var.get(""), store_id=req.store_id,
        store_name=req.store_name, platform=req.platform,
        marketplace_id=req.marketplace_id, seller_id=req.seller_id,
        region=req.region, auth_type=req.auth_type,
        access_token=req.access_token, refresh_token=req.refresh_token,
        token_expiry=req.token_expiry, token_scope=req.token_scope,
        auth_meta=req.auth_meta,
    )
    return Result.ok(
        data={"id": auth.id, "store_id": auth.store_id, "store_name": auth.store_name,
              "platform": auth.platform, "auth_status": auth.auth_status},
        trace_id=trace_id_var.get(""),
    )


@router.get("", response_model=None)
async def list_authorizations(
    platform: str = Query(default=""),
    auth_status: str = Query(default=""),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = StoreAuthorizationService(session)
    items, total = await svc.list_authorizations(
        tenant_id_var.get(""), platform=platform, auth_status=auth_status,
        is_active=is_active, page=page, page_size=page_size,
    )
    data = [{
        "id": a.id, "store_id": a.store_id, "store_name": a.store_name,
        "platform": a.platform, "marketplace_id": a.marketplace_id,
        "seller_id": a.seller_id, "region": a.region,
        "auth_status": a.auth_status, "is_active": a.is_active,
        "token_expiry": a.token_expiry.isoformat() if a.token_expiry else None,
        "last_refresh_at": a.last_refresh_at.isoformat() if a.last_refresh_at else None,
        "refresh_failure_count": a.refresh_failure_count,
    } for a in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/expiring", response_model=None)
async def get_expiring_tokens(within_minutes: int = Query(default=30, ge=1, le=1440),
                               session: AsyncSession = Depends(get_db_session)):
    svc = StoreAuthorizationService(session)
    items = await svc.get_stores_needing_refresh(tenant_id_var.get(""), within_minutes=within_minutes)
    data = [{
        "id": a.id, "store_id": a.store_id, "store_name": a.store_name,
        "platform": a.platform, "token_expiry": a.token_expiry.isoformat() if a.token_expiry else None,
    } for a in items]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/check-expired", response_model=None)
async def check_expired_tokens(session: AsyncSession = Depends(get_db_session)):
    svc = StoreAuthorizationService(session)
    expired = await svc.check_and_mark_expired(tenant_id_var.get(""))
    return Result.ok(
        data={"expired_count": len(expired),
              "expired_stores": [a.store_name for a in expired]},
        trace_id=trace_id_var.get(""),
    )


@router.get("/{store_auth_id}/status", response_model=None)
async def get_auth_status(store_auth_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = StoreAuthorizationService(session)
    status = await svc.get_authorization_status(store_auth_id, tenant_id_var.get(""))
    return Result.ok(data=status, trace_id=trace_id_var.get(""))


@router.post("/{store_auth_id}/refresh", response_model=None)
async def refresh_token(store_auth_id: str, req: RefreshTokenRequest,
                         session: AsyncSession = Depends(get_db_session)):
    svc = StoreAuthorizationService(session)
    auth = await svc.refresh_token(
        store_auth_id, tenant_id_var.get(""),
        new_access_token=req.new_access_token, new_refresh_token=req.new_refresh_token,
        new_token_expiry=req.new_token_expiry, refresh_type=req.refresh_type,
    )
    return Result.ok(
        data={"id": auth.id, "auth_status": auth.auth_status,
              "token_expiry": auth.token_expiry.isoformat() if auth.token_expiry else None},
        trace_id=trace_id_var.get(""),
    )


@router.post("/{store_auth_id}/revoke", response_model=None)
async def revoke_authorization(store_auth_id: str, req: RevokeRequest,
                                session: AsyncSession = Depends(get_db_session)):
    svc = StoreAuthorizationService(session)
    auth = await svc.revoke_authorization(store_auth_id, tenant_id_var.get(""), reason=req.reason)
    return Result.ok(
        data={"id": auth.id, "auth_status": auth.auth_status, "is_active": auth.is_active},
        trace_id=trace_id_var.get(""),
    )
