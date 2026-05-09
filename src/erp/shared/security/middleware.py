from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import HTTPException, Request


class SecurityMiddleware:
    def __init__(
        self,
        max_request_size: int = 50 * 1024 * 1024,
        rate_limit_per_minute: int = 100,
        signature_timeout_seconds: int = 300,
    ):
        self.max_request_size = max_request_size
        self.rate_limit_per_minute = rate_limit_per_minute
        self.signature_timeout_seconds = signature_timeout_seconds
        self._request_counts: dict[str, list[float]] = {}

    async def check_request_size(self, request: Request) -> None:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_request_size:
            raise HTTPException(status_code=413, detail="Request too large")

    def check_rate_limit(self, client_id: str) -> None:
        now = time.monotonic()
        window = self._request_counts.get(client_id, [])
        window = [t for t in window if now - t < 60]
        if len(window) >= self.rate_limit_per_minute:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        window.append(now)
        self._request_counts[client_id] = window

    def verify_signature(
        self,
        body: bytes,
        timestamp: str,
        signature: str,
        secret: str,
    ) -> None:
        now = time.time()
        try:
            req_time = float(timestamp)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=401, detail="Invalid timestamp") from exc

        if abs(now - req_time) > self.signature_timeout_seconds:
            raise HTTPException(status_code=401, detail="Signature expired")

        expected = hmac.new(
            secret.encode("utf-8"),
            body + timestamp.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    def check_replay(self, nonce: str, timestamp: str, ttl: int = 300) -> None:
        pass

    def sanitize_headers(self, request: Request) -> dict:
        sensitive = {"authorization", "cookie", "x-api-key", "x-secret"}
        return {
            k: ("***" if k.lower() in sensitive else v)
            for k, v in request.headers.items()
        }
