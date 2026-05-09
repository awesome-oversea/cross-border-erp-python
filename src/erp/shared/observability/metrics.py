from __future__ import annotations

import time
from typing import TYPE_CHECKING

from fastapi import Response

if TYPE_CHECKING:
    from fastapi import FastAPI, Request

METRICS_REGISTRY: dict[str, float] = {}
REQUEST_COUNT: dict[str, int] = {}
REQUEST_LATENCY: dict[str, list[float]] = {}


def _build_label_key(name: str, labels: dict[str, str] | None) -> str:
    if not labels:
        return name
    parts = []
    for k, v in labels.items():
        parts.append(f'{k}="{v}"')
    return f"{name}{{{','.join(parts)}}}"


def increment_counter(name: str, labels: dict[str, str] | None = None, value: float = 1.0):
    key = _build_label_key(name, labels)
    METRICS_REGISTRY[key] = METRICS_REGISTRY.get(key, 0) + value


def observe_histogram(name: str, value: float, labels: dict[str, str] | None = None):
    key = _build_label_key(name, labels)
    if key not in REQUEST_LATENCY:
        REQUEST_LATENCY[key] = []
    REQUEST_LATENCY[key].append(value)


def format_prometheus_metrics() -> str:
    lines = []
    for key, value in sorted(METRICS_REGISTRY.items()):
        lines.append(f"{key} {value}")

    for key, values in sorted(REQUEST_LATENCY.items()):
        if not values:
            continue
        count = len(values)
        total = sum(values)
        sorted_vals = sorted(values)
        p50 = sorted_vals[int(count * 0.5)] if count > 0 else 0
        p95 = sorted_vals[int(count * 0.95)] if count > 0 else 0
        p99 = sorted_vals[int(count * 0.99)] if count > 0 else 0

        base_name = key.split("{")[0]
        labels_str = key[key.find("{"):] if "{" in key else ""
        lines.append(f"{base_name}_count{labels_str} {count}")
        lines.append(f"{base_name}_sum{labels_str} {total:.6f}")
        inner = labels_str[1:-1] if labels_str else ""
        sep = "," if inner else ""
        lines.append(f'{base_name}{{quantile="0.5"{sep}{inner}}} {p50:.6f}')
        lines.append(f'{base_name}{{quantile="0.95"{sep}{inner}}} {p95:.6f}')
        lines.append(f'{base_name}{{quantile="0.99"{sep}{inner}}} {p99:.6f}')

    return "\n".join(lines) + "\n"


def setup_metrics_middleware(app: FastAPI):
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration = (time.perf_counter() - start) * 1000

        method = request.method
        path = request.url.path
        status = response.status_code

        increment_counter(
            "erp_http_requests_total",
            labels={"method": method, "path": path, "status": str(status)},
        )
        observe_histogram(
            "erp_http_request_duration_ms",
            duration,
            labels={"method": method, "path": path},
        )

        if path.startswith("/api/"):
            domain = _extract_domain(path)
            if domain:
                increment_counter(
                    "erp_domain_requests_total",
                    labels={"domain": domain, "method": method, "status": str(status)},
                )

        return response

    @app.get("/api/v1/metrics", tags=["Monitoring"])
    async def metrics_endpoint():
        content = format_prometheus_metrics()
        return Response(content=content, media_type="text/plain; version=0.0.4")


def _extract_domain(path: str) -> str:
    parts = path.strip("/").split("/")
    if len(parts) >= 2:
        domain_map = {
            "iam": "iam", "pdm": "pdm", "som": "som", "ads": "ads",
            "oms": "oms", "scm": "scm", "wms": "wms", "fba": "fba",
            "tms": "tms", "crm": "crm", "fms": "fms", "bi": "bi",
            "sys": "sys", "dashboard": "dashboard",
        }
        for part in parts:
            if part in domain_map:
                return domain_map[part]
    return ""
