from __future__ import annotations

import base64
import hashlib
import os
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SecretType(StrEnum):
    OAUTH_TOKEN = "oauth_token"
    API_KEY = "api_key"
    API_SECRET = "api_secret"
    PASSWORD = "password"
    CERTIFICATE = "certificate"
    WEBHOOK_SECRET = "webhook_secret"
    OTHER = "other"


class EncryptedSecret(Base):
    __tablename__ = "encrypted_secret"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    owner_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    secret_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    secret_name: Mapped[str] = mapped_column(String(100), nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    iv: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_accessed_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SecretAccessLog(Base):
    __tablename__ = "secret_access_log"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    secret_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    owner_type: Mapped[str] = mapped_column(String(50), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    ip_address: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    is_success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SecretEncryptionService:
    _master_key: bytes = b"erp-secret-master-key-32byte"

    @classmethod
    def set_master_key(cls, key: str):
        derived = hashlib.sha256(key.encode()).digest()
        cls._master_key = derived

    @classmethod
    def encrypt(cls, plaintext: str) -> tuple[str, str]:
        if not plaintext:
            return "", ""
        iv = os.urandom(16)
        key = cls._master_key
        from cryptography.hazmat.primitives import padding as sym_padding
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        padder = sym_padding.PKCS7(128).padder()
        padded = padder.update(plaintext.encode()) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ct = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(ct).decode(), base64.b64encode(iv).decode()

    @classmethod
    def decrypt(cls, encrypted_value: str, iv: str) -> str:
        if not encrypted_value or not iv:
            return ""
        key = cls._master_key
        ct = base64.b64decode(encrypted_value)
        iv_bytes = base64.b64decode(iv)
        from cryptography.hazmat.primitives import padding as sym_padding
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv_bytes))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ct) + decryptor.finalize()
        unpadder = sym_padding.PKCS7(128).unpadder()
        data = unpadder.update(padded) + unpadder.finalize()
        return data.decode()

    @classmethod
    def mask(cls, value: str, visible_chars: int = 4) -> str:
        if not value or len(value) <= visible_chars:
            return "****"
        return value[:visible_chars] + "*" * min(len(value) - visible_chars, 20)


class SecretStoreService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def store_secret(self, tenant_id: str, owner_type: str, owner_id: str,
                            secret_type: str, secret_name: str, plaintext: str) -> EncryptedSecret:
        encrypted_value, iv = SecretEncryptionService.encrypt(plaintext)
        secret = EncryptedSecret(
            tenant_id=tenant_id, owner_type=owner_type, owner_id=owner_id,
            secret_type=secret_type, secret_name=secret_name,
            encrypted_value=encrypted_value, iv=iv,
            created_by=actor_id_var.get(""),
        )
        self.session.add(secret)
        await self.session.flush()
        await self._log_access(tenant_id, secret.id, owner_type, owner_id, "create")
        return secret

    async def get_secret(self, secret_id: str, tenant_id: str) -> str:
        secret = await self._get_by_id(secret_id, tenant_id)
        if not secret:
            raise NotFoundException(message=f"Secret '{secret_id}' not found")
        if not secret.is_active:
            raise ValidationException(message="Secret is inactive")

        plaintext = SecretEncryptionService.decrypt(secret.encrypted_value, secret.iv)
        secret.last_accessed_at = datetime.now(UTC)
        secret.last_accessed_by = actor_id_var.get("")
        secret.access_count += 1
        await self.session.flush()
        await self._log_access(tenant_id, secret_id, secret.owner_type, secret.owner_id, "read")
        return plaintext

    async def get_masked_secret(self, secret_id: str, tenant_id: str) -> dict:
        secret = await self._get_by_id(secret_id, tenant_id)
        if not secret:
            raise NotFoundException(message=f"Secret '{secret_id}' not found")
        return {
            "id": secret.id,
            "owner_type": secret.owner_type,
            "owner_id": secret.owner_id,
            "secret_type": secret.secret_type,
            "secret_name": secret.secret_name,
            "masked_value": SecretEncryptionService.mask(
                SecretEncryptionService.decrypt(secret.encrypted_value, secret.iv)
            ),
            "is_active": secret.is_active,
            "last_accessed_at": secret.last_accessed_at.isoformat() if secret.last_accessed_at else None,
            "access_count": secret.access_count,
        }

    async def update_secret(self, secret_id: str, tenant_id: str, plaintext: str) -> EncryptedSecret:
        secret = await self._get_by_id(secret_id, tenant_id)
        if not secret:
            raise NotFoundException(message=f"Secret '{secret_id}' not found")
        encrypted_value, iv = SecretEncryptionService.encrypt(plaintext)
        secret.encrypted_value = encrypted_value
        secret.iv = iv
        secret.key_version += 1
        await self.session.flush()
        await self._log_access(tenant_id, secret_id, secret.owner_type, secret.owner_id, "update")
        return secret

    async def deactivate_secret(self, secret_id: str, tenant_id: str) -> EncryptedSecret:
        secret = await self._get_by_id(secret_id, tenant_id)
        if not secret:
            raise NotFoundException(message=f"Secret '{secret_id}' not found")
        secret.is_active = False
        await self.session.flush()
        await self._log_access(tenant_id, secret_id, secret.owner_type, secret.owner_id, "deactivate")
        return secret

    async def list_secrets(self, tenant_id: str, owner_type: str = "",
                            owner_id: str = "", secret_type: str = "") -> list[dict]:
        conditions = [EncryptedSecret.tenant_id == tenant_id, EncryptedSecret.is_active]
        if owner_type:
            conditions.append(EncryptedSecret.owner_type == owner_type)
        if owner_id:
            conditions.append(EncryptedSecret.owner_id == owner_id)
        if secret_type:
            conditions.append(EncryptedSecret.secret_type == secret_type)

        stmt = select(EncryptedSecret).where(*conditions).order_by(EncryptedSecret.created_at.desc())
        result = await self.session.execute(stmt)
        secrets = list(result.scalars().all())

        return [{
            "id": s.id, "owner_type": s.owner_type, "owner_id": s.owner_id,
            "secret_type": s.secret_type, "secret_name": s.secret_name,
            "masked_value": SecretEncryptionService.mask(
                SecretEncryptionService.decrypt(s.encrypted_value, s.iv)
            ),
            "key_version": s.key_version,
            "last_accessed_at": s.last_accessed_at.isoformat() if s.last_accessed_at else None,
            "access_count": s.access_count,
        } for s in secrets]

    async def _log_access(self, tenant_id: str, secret_id: str, owner_type: str,
                           owner_id: str, action: str, is_success: bool = True,
                           error_message: str = ""):
        log = SecretAccessLog(
            tenant_id=tenant_id, secret_id=secret_id,
            owner_type=owner_type, owner_id=owner_id,
            action=action, actor_id=actor_id_var.get(""),
            is_success=is_success, error_message=error_message,
            trace_id=trace_id_var.get(""),
        )
        self.session.add(log)
        await self.session.flush()

    async def _get_by_id(self, secret_id: str, tenant_id: str) -> EncryptedSecret | None:
        stmt = select(EncryptedSecret).where(
            EncryptedSecret.id == secret_id,
            EncryptedSecret.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
