from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class ApiEndpoint:
    endpoint_id: str = ""
    path: str = ""
    method: str = ""
    service: str = ""
    summary: str = ""
    version: str = "v1"
    is_deprecated: bool = False
    tags: list[str] = field(default_factory=list)
    created_at: str = ""


@dataclass
class ApiCallStat:
    stat_id: str = ""
    endpoint_id: str = ""
    tenant_id: str = ""
    path: str = ""
    method: str = ""
    status_code: int = 200
    response_time_ms: int = 0
    called_at: str = ""


@dataclass
class ApiVersion:
    version_id: str = ""
    version: str = ""
    service: str = ""
    is_active: bool = True
    release_date: str = ""
    description: str = ""


class ApiPlatformEngine:
    def __init__(self):
        self._endpoints: dict[str, ApiEndpoint] = {}
        self._stats: list[ApiCallStat] = []
        self._versions: dict[str, ApiVersion] = {}
        self._register_default_endpoints()

    def _register_default_endpoints(self):
        defaults = [
            ("/iam/api/v1/users", "GET", "iam", "获取用户列表"),
            ("/iam/api/v1/users", "POST", "iam", "创建用户"),
            ("/pdm/api/v1/products", "GET", "pdm", "获取产品列表"),
            ("/pdm/api/v1/products", "POST", "pdm", "创建产品"),
            ("/oms/api/v1/orders", "GET", "oms", "获取订单列表"),
            ("/oms/api/v1/orders", "POST", "oms", "创建订单"),
            ("/wms/api/v1/inventory", "GET", "wms", "获取库存列表"),
            ("/scm/api/v1/purchase-orders", "GET", "scm", "获取采购单列表"),
            ("/fms/api/v1/cost-events", "GET", "fms", "获取费用列表"),
            ("/sys/api/v1/notification/send", "POST", "sys", "发送通知"),
        ]
        for path, method, service, summary in defaults:
            eid = f"{method}:{path}"
            self._endpoints[eid] = ApiEndpoint(
                endpoint_id=str(uuid.uuid4())[:8], path=path, method=method,
                service=service, summary=summary, version="v1",
                tags=[service],
            )

    def list_endpoints(self, service: str = "", version: str = "",
                        method: str = "") -> list[dict]:
        results = list(self._endpoints.values())
        if service:
            results = [e for e in results if e.service == service]
        if version:
            results = [e for e in results if e.version == version]
        if method:
            results = [e for e in results if e.method == method]
        return [{"endpoint_id": e.endpoint_id, "path": e.path, "method": e.method,
                 "service": e.service, "summary": e.summary, "version": e.version,
                 "is_deprecated": e.is_deprecated, "tags": e.tags} for e in results]

    def record_call(self, tenant_id: str, path: str, method: str,
                     status_code: int = 200, response_time_ms: int = 0) -> dict:
        stat = ApiCallStat(
            stat_id=str(uuid.uuid4()), endpoint_id=f"{method}:{path}",
            tenant_id=tenant_id, path=path, method=method,
            status_code=status_code, response_time_ms=response_time_ms,
            called_at=datetime.now(UTC).isoformat(),
        )
        self._stats.append(stat)
        return {"stat_id": stat.stat_id, "recorded": True}

    def get_stats(self, tenant_id: str, service: str = "", path: str = "",
                   hours: int = 24) -> dict:
        datetime.now(UTC).timestamp() - hours * 3600
        results = [s for s in self._stats if s.tenant_id == tenant_id]
        if service:
            results = [s for s in results if service in s.path]
        if path:
            results = [s for s in results if path in s.path]

        total_calls = len(results)
        error_calls = len([s for s in results if s.status_code >= 400])
        avg_response_time = sum(s.response_time_ms for s in results) / total_calls if total_calls else 0
        error_rate = round(error_calls / total_calls * 100, 2) if total_calls else 0

        return {
            "total_calls": total_calls, "error_calls": error_calls,
            "error_rate_pct": error_rate, "avg_response_time_ms": round(avg_response_time, 2),
            "period_hours": hours,
        }

    def list_versions(self, service: str = "") -> list[dict]:
        results = list(self._versions.values())
        if service:
            results = [v for v in results if v.service == service]
        if not results:
            return [{"version": "v1", "service": "all", "is_active": True, "release_date": "2024-01-01"}]
        return [{"version_id": v.version_id, "version": v.version, "service": v.service,
                 "is_active": v.is_active, "release_date": v.release_date} for v in results]

    def test_endpoint(self, path: str, method: str, params: dict | None = None) -> dict:
        return {"path": path, "method": method, "status": "mock_success",
                "response": {"message": "API test mock response"}, "params": params or {}}
