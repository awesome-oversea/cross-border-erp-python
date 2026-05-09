from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class AuthStatus(StrEnum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    TOKEN_EXPIRED = "token_expired"
    REVOKED = "revoked"
    AUTH_FAILED = "auth_failed"
    REFRESH_FAILED = "refresh_failed"


class PlatformType(StrEnum):
    AMAZON = "amazon"
    EBAY = "ebay"
    SHOPIFY = "shopify"
    TIKTOK_SHOP = "tiktok_shop"
    ALIEXPRESS = "aliexpress"
    WALMART = "walmart"
    MERCADO_LIBRE = "mercado_libre"
    SHOPEE = "shopee"
    LAZADA = "lazada"
    CUSTOM = "custom"


class StoreAuthorization(Base):
    __tablename__ = "store_authorization"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    store_name: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    marketplace_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    seller_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    region: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    auth_type: Mapped[str] = mapped_column(String(30), nullable=False, default="oauth2")
    auth_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_scope: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_refresh_status: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    refresh_failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auth_meta_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    authorized_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    revoke_reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TokenRefreshLog(Base):
    __tablename__ = "token_refresh_log"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    store_auth_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    refresh_type: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")
    is_success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    old_token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    new_token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StoreAuthorizationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def authorize_store(self, tenant_id: str, store_id: str, store_name: str,
                               platform: str, marketplace_id: str = "",
                               seller_id: str = "", region: str = "",
                               auth_type: str = "oauth2",
                               access_token: str = "", refresh_token: str = "",
                               token_expiry: datetime | None = None,
                               token_scope: str = "",
                               auth_meta: dict | None = None) -> StoreAuthorization:
        existing = await self._get_by_store(tenant_id, store_id)
        if existing and existing.is_active:
            raise ValidationException(message=f"Store '{store_id}' already authorized and active")

        if existing and not existing.is_active:
            existing.is_active = True
            existing.auth_status = AuthStatus.AUTHORIZED.value
            existing.store_name = store_name
            existing.platform = platform
            existing.marketplace_id = marketplace_id
            existing.seller_id = seller_id
            existing.region = region
            existing.access_token_encrypted = self._encrypt_token(access_token)
            existing.refresh_token_encrypted = self._encrypt_token(refresh_token)
            existing.token_expiry = token_expiry
            existing.token_scope = token_scope
            existing.auth_meta_json = json.dumps(auth_meta or {}, default=str)
            existing.authorized_by = actor_id_var.get("")
            existing.revoked_at = None
            existing.revoked_by = ""
            existing.revoke_reason = ""
            existing.trace_id = trace_id_var.get("")
            await self.session.flush()
            return existing

        auth = StoreAuthorization(
            tenant_id=tenant_id, store_id=store_id, store_name=store_name,
            platform=platform, marketplace_id=marketplace_id,
            seller_id=seller_id, region=region, auth_type=auth_type,
            auth_status=AuthStatus.AUTHORIZED.value if access_token else AuthStatus.PENDING.value,
            access_token_encrypted=self._encrypt_token(access_token),
            refresh_token_encrypted=self._encrypt_token(refresh_token),
            token_expiry=token_expiry, token_scope=token_scope,
            auth_meta_json=json.dumps(auth_meta or {}, default=str),
            authorized_by=actor_id_var.get(""),
            trace_id=trace_id_var.get(""),
        )
        self.session.add(auth)
        await self.session.flush()
        return auth

    async def refresh_token(self, store_auth_id: str, tenant_id: str,
                             new_access_token: str = "", new_refresh_token: str = "",
                             new_token_expiry: datetime | None = None,
                             refresh_type: str = "auto") -> StoreAuthorization:
        auth = await self._get_by_id(store_auth_id, tenant_id)
        if not auth:
            raise NotFoundException(message=f"Store authorization '{store_auth_id}' not found")
        if not auth.is_active:
            raise ValidationException(message="Cannot refresh token for inactive authorization")

        start = datetime.now(UTC)
        old_expiry = auth.token_expiry

        try:
            auth.access_token_encrypted = self._encrypt_token(new_access_token) if new_access_token else auth.access_token_encrypted
            auth.refresh_token_encrypted = self._encrypt_token(new_refresh_token) if new_refresh_token else auth.refresh_token_encrypted
            auth.token_expiry = new_token_expiry or auth.token_expiry
            auth.last_refresh_at = datetime.now(UTC)
            auth.last_refresh_status = "success"
            auth.refresh_failure_count = 0
            auth.auth_status = AuthStatus.AUTHORIZED.value
            await self.session.flush()

            duration = int((datetime.now(UTC) - start).total_seconds() * 1000)
            await self._log_refresh(tenant_id, store_auth_id, auth.platform,
                                     refresh_type, True, old_expiry, new_token_expiry, "", duration)
            return auth
        except Exception as e:
            auth.last_refresh_status = "failed"
            auth.refresh_failure_count += 1
            if auth.refresh_failure_count >= 5:
                auth.auth_status = AuthStatus.REFRESH_FAILED.value
            else:
                auth.auth_status = AuthStatus.TOKEN_EXPIRED.value
            await self.session.flush()

            duration = int((datetime.now(UTC) - start).total_seconds() * 1000)
            await self._log_refresh(tenant_id, store_auth_id, auth.platform,
                                     refresh_type, False, old_expiry, None, str(e)[:500], duration)
            raise

    async def revoke_authorization(self, store_auth_id: str, tenant_id: str,
                                    reason: str = "") -> StoreAuthorization:
        auth = await self._get_by_id(store_auth_id, tenant_id)
        if not auth:
            raise NotFoundException(message=f"Store authorization '{store_auth_id}' not found")

        auth.auth_status = AuthStatus.REVOKED.value
        auth.is_active = False
        auth.access_token_encrypted = ""
        auth.refresh_token_encrypted = ""
        auth.revoked_at = datetime.now(UTC)
        auth.revoked_by = actor_id_var.get("")
        auth.revoke_reason = reason
        await self.session.flush()
        return auth

    async def check_and_mark_expired(self, tenant_id: str) -> list[StoreAuthorization]:
        now = datetime.now(UTC)
        stmt = select(StoreAuthorization).where(
            StoreAuthorization.tenant_id == tenant_id,
            StoreAuthorization.is_active,
            StoreAuthorization.auth_status == AuthStatus.AUTHORIZED.value,
            StoreAuthorization.token_expiry is not None,
            StoreAuthorization.token_expiry < now,
        )
        result = await self.session.execute(stmt)
        expired = list(result.scalars().all())

        for auth in expired:
            auth.auth_status = AuthStatus.TOKEN_EXPIRED.value
        if expired:
            await self.session.flush()
        return expired

    async def get_authorization_status(self, store_auth_id: str, tenant_id: str) -> dict:
        auth = await self._get_by_id(store_auth_id, tenant_id)
        if not auth:
            raise NotFoundException(message=f"Store authorization '{store_auth_id}' not found")

        now = datetime.now(UTC)
        is_expired = False
        expires_in_seconds = None
        if auth.token_expiry:
            delta = (auth.token_expiry - now).total_seconds()
            is_expired = delta <= 0
            expires_in_seconds = max(0, int(delta))

        return {
            "id": auth.id,
            "store_id": auth.store_id,
            "store_name": auth.store_name,
            "platform": auth.platform,
            "marketplace_id": auth.marketplace_id,
            "seller_id": auth.seller_id,
            "auth_status": auth.auth_status,
            "is_expired": is_expired,
            "expires_in_seconds": expires_in_seconds,
            "last_refresh_at": auth.last_refresh_at.isoformat() if auth.last_refresh_at else None,
            "last_refresh_status": auth.last_refresh_status,
            "refresh_failure_count": auth.refresh_failure_count,
            "is_active": auth.is_active,
        }

    async def list_authorizations(self, tenant_id: str, platform: str = "",
                                   auth_status: str = "",
                                   is_active: bool | None = None,
                                   page: int = 1, page_size: int = 20) -> tuple[list[StoreAuthorization], int]:
        conditions = [StoreAuthorization.tenant_id == tenant_id]
        if platform:
            conditions.append(StoreAuthorization.platform == platform)
        if auth_status:
            conditions.append(StoreAuthorization.auth_status == auth_status)
        if is_active is not None:
            conditions.append(StoreAuthorization.is_active == is_active)

        stmt = select(StoreAuthorization).where(*conditions).order_by(StoreAuthorization.created_at.desc())
        total_result = await self.session.execute(
            select(func.count()).select_from(StoreAuthorization).where(*conditions)
        )
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(stmt.offset(offset).limit(page_size))
        items = list(result.scalars().all())
        return items, total

    async def get_stores_needing_refresh(self, tenant_id: str,
                                          within_minutes: int = 30) -> list[StoreAuthorization]:
        now = datetime.now(UTC)
        threshold = now + timedelta(minutes=within_minutes)
        stmt = select(StoreAuthorization).where(
            StoreAuthorization.tenant_id == tenant_id,
            StoreAuthorization.is_active,
            StoreAuthorization.auth_status == AuthStatus.AUTHORIZED.value,
            StoreAuthorization.token_expiry is not None,
            StoreAuthorization.token_expiry <= threshold,
            StoreAuthorization.token_expiry > now,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def _encrypt_token(self, token: str) -> str:
        if not token:
            return ""
        import base64
        return base64.b64encode(token.encode()).decode()

    def _decrypt_token(self, encrypted: str) -> str:
        if not encrypted:
            return ""
        import base64
        return base64.b64decode(encrypted.encode()).decode()

    async def _log_refresh(self, tenant_id: str, store_auth_id: str, platform: str,
                            refresh_type: str, is_success: bool,
                            old_expiry: datetime | None, new_expiry: datetime | None,
                            error_message: str, duration_ms: int) -> TokenRefreshLog:
        log = TokenRefreshLog(
            tenant_id=tenant_id, store_auth_id=store_auth_id,
            platform=platform, refresh_type=refresh_type,
            is_success=is_success, old_token_expiry=old_expiry,
            new_token_expiry=new_expiry, error_message=error_message,
            duration_ms=duration_ms, trace_id=trace_id_var.get(""),
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def _get_by_id(self, store_auth_id: str, tenant_id: str) -> StoreAuthorization | None:
        stmt = select(StoreAuthorization).where(
            StoreAuthorization.id == store_auth_id,
            StoreAuthorization.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_by_store(self, tenant_id: str, store_id: str) -> StoreAuthorization | None:
        stmt = select(StoreAuthorization).where(
            StoreAuthorization.tenant_id == tenant_id,
            StoreAuthorization.store_id == store_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
