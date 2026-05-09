from datetime import UTC, datetime
from typing import Any

import bcrypt as _bcrypt
from jose import JWTError, jwt

from erp.bootstrap.config import get_settings
from erp.shared.exceptions import UnauthorizedException
from erp.shared.observability.logging import get_logger

logger = get_logger("erp.iam.auth")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(
    subject: str,
    tenant_id: str,
    roles: list[str] | None = None,
    extra: dict[str, Any] | None = None,
    expires_delta_minutes: int | None = None,
) -> str:
    settings = get_settings()
    expire_minutes = expires_delta_minutes or ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "roles": roles or [],
        "type": "access",
        "iat": now,
        "exp": now.__class__.fromtimestamp(now.timestamp() + expire_minutes * 60, tz=UTC),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def create_refresh_token(
    subject: str,
    tenant_id: str,
    expires_delta_days: int | None = None,
) -> str:
    settings = get_settings()
    expire_days = expires_delta_days or REFRESH_TOKEN_EXPIRE_DAYS
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "type": "refresh",
        "iat": now,
        "exp": now.__class__.fromtimestamp(now.timestamp() + expire_days * 86400, tz=UTC),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning("jwt_decode_failed", error=str(e))
        raise UnauthorizedException(message="Invalid or expired token") from e


def validate_access_token(token: str) -> dict[str, Any]:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise UnauthorizedException(message="Not an access token")
    return payload


def validate_refresh_token(token: str) -> dict[str, Any]:
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise UnauthorizedException(message="Not a refresh token")
    return payload
