from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi.responses import JSONResponse

from erp.shared.context import trace_id_var
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import Request, Response


@dataclass
class RateLimitRule:
    key_prefix: str
    max_requests: int
    window_seconds: int
    burst: int = 0


class InMemoryRateLimiter:
    _instance = None

    def __init__(self):
        self._store: dict[str, list[float]] = {}

    @classmethod
    def get_instance(cls) -> InMemoryRateLimiter:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int, int]:
        now = time.time()
        window_start = now - window_seconds
        if key not in self._store:
            self._store[key] = []
        self._store[key] = [ts for ts in self._store[key] if ts > window_start]
        current_count = len(self._store[key])
        remaining = max(0, max_requests - current_count)
        if current_count < max_requests:
            self._store[key].append(now)
            return True, max_requests, remaining - 1
        return False, max_requests, 0

    def reset(self, key: str):
        self._store.pop(key, None)


class RateLimitMiddleware:
    def __init__(self, app, default_max: int = 100, default_window: int = 60):
        self.app = app
        self.default_max = default_max
        self.default_window = default_window
        self.limiter = InMemoryRateLimiter.get_instance()
        self._path_rules: dict[str, RateLimitRule] = {}

    def add_rule(self, path_pattern: str, rule: RateLimitRule):
        self._path_rules[path_pattern] = rule

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        tenant_id = request.headers.get("X-Tenant-ID", "anonymous")
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        max_req = self.default_max
        window = self.default_window
        key_prefix = "global"

        for pattern, rule in self._path_rules.items():
            if pattern in path:
                max_req = rule.max_requests
                window = rule.window_seconds
                key_prefix = rule.key_prefix
                break

        key = f"ratelimit:{key_prefix}:{tenant_id}:{client_ip}"
        allowed, limit, remaining = self.limiter.is_allowed(key, max_req, window)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content=Result.fail(
                    code=4290,
                    message="Too many requests, please try again later",
                    trace_id=trace_id_var.get(""),
                ).__dict__,
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": str(remaining),
                    "Retry-After": str(window),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30,
                 half_open_max: int = 3):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self._circuits: dict[str, dict[str, Any]] = {}

    def _get_circuit(self, name: str) -> dict[str, Any]:
        if name not in self._circuits:
            self._circuits[name] = {
                "state": "closed",
                "failure_count": 0,
                "last_failure_time": 0,
                "half_open_count": 0,
            }
        return self._circuits[name]

    def is_allowed(self, name: str) -> bool:
        circuit = self._get_circuit(name)
        state = circuit["state"]

        if state == "closed":
            return True
        if state == "open":
            if time.time() - circuit["last_failure_time"] > self.recovery_timeout:
                circuit["state"] = "half_open"
                circuit["half_open_count"] = 0
                return True
            return False
        if state == "half_open":
            return circuit["half_open_count"] < self.half_open_max
        return False

    def record_success(self, name: str):
        circuit = self._get_circuit(name)
        if circuit["state"] == "half_open":
            circuit["state"] = "closed"
            circuit["failure_count"] = 0
            circuit["half_open_count"] = 0

    def record_failure(self, name: str):
        circuit = self._get_circuit(name)
        circuit["failure_count"] += 1
        circuit["last_failure_time"] = time.time()
        if circuit["state"] == "half_open":
            circuit["state"] = "open"
            circuit["half_open_count"] = 0
        elif circuit["failure_count"] >= self.failure_threshold:
            circuit["state"] = "open"


class IdempotencyGuard:
    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}

    def _make_key(self, tenant_id: str, idempotency_key: str) -> str:
        raw = f"{tenant_id}:{idempotency_key}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def check_and_lock(self, tenant_id: str, idempotency_key: str,
                       request_hash: str = "") -> tuple[bool, dict[str, Any] | None]:
        key = self._make_key(tenant_id, idempotency_key)
        if key in self._store:
            entry = self._store[key]
            if request_hash and entry.get("request_hash") != request_hash:
                return False, {"error": "Request hash mismatch for same idempotency key"}
            return False, entry.get("response_data", {})
        self._store[key] = {
            "status": "processing",
            "request_hash": request_hash,
            "response_data": None,
            "created_at": time.time(),
        }
        return True, None

    def store_result(self, tenant_id: str, idempotency_key: str, response_data: dict[str, Any]):
        key = self._make_key(tenant_id, idempotency_key)
        if key in self._store:
            self._store[key]["status"] = "completed"
            self._store[key]["response_data"] = response_data

    def cleanup(self, max_age_seconds: int = 86400):
        now = time.time()
        expired = [k for k, v in self._store.items() if now - v.get("created_at", 0) > max_age_seconds]
        for k in expired:
            del self._store[k]


circuit_breaker = CircuitBreaker()
idempotency_guard = IdempotencyGuard()
