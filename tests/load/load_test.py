from __future__ import annotations

import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field


@dataclass
class LoadTestConfig:
    base_url: str = "http://localhost:8000"
    api_prefix: str = "/api/admin/v1"
    concurrent_users: int = 50
    duration_seconds: int = 60
    ramp_up_seconds: int = 10
    endpoints: list[dict] = field(default_factory=lambda: [
        {"path": "/health", "method": "GET", "weight": 5},
        {"path": "/iam/v1/users", "method": "GET", "weight": 5, "headers": {"X-Tenant-ID": "T001", "X-Actor-ID": "U001"}},
        {"path": "/pdm/v1/spus", "method": "GET", "weight": 8, "headers": {"X-Tenant-ID": "T001", "X-Actor-ID": "U001"}},
        {"path": "/oms/v1/sales-orders", "method": "GET", "weight": 10, "headers": {"X-Tenant-ID": "T001", "X-Actor-ID": "U001"}},
        {"path": "/scm/v1/purchase-orders", "method": "GET", "weight": 6, "headers": {"X-Tenant-ID": "T001", "X-Actor-ID": "U001"}},
        {"path": "/wms/v1/inventory", "method": "GET", "weight": 10, "headers": {"X-Tenant-ID": "T001", "X-Actor-ID": "U001"}},
        {"path": "/fms/v1/cost-events", "method": "GET", "weight": 5, "headers": {"X-Tenant-ID": "T001", "X-Actor-ID": "U001"}},
        {"path": "/tms/v1/shipments", "method": "GET", "weight": 5, "headers": {"X-Tenant-ID": "T001", "X-Actor-ID": "U001"}},
        {"path": "/bi/v1/metrics", "method": "GET", "weight": 4, "headers": {"X-Tenant-ID": "T001", "X-Actor-ID": "U001"}},
        {"path": "/oms/orders", "method": "GET", "weight": 8, "headers": {"X-Tenant-ID": "tenant-00000000-0000-0000-0000-000000000001"}},
        {"path": "/wms/inventory", "method": "GET", "weight": 6, "headers": {"X-Tenant-ID": "tenant-00000000-0000-0000-0000-000000000001"}},
        {"path": "/fms/profit", "method": "GET", "weight": 4, "headers": {"X-Tenant-ID": "tenant-00000000-0000-0000-0000-000000000001"}},
        {"path": "/sys/dicts", "method": "GET", "weight": 3, "headers": {"X-Tenant-ID": "tenant-00000000-0000-0000-0000-000000000001"}},
        {"path": "/bi/metrics", "method": "GET", "weight": 3, "headers": {"X-Tenant-ID": "tenant-00000000-0000-0000-0000-000000000001"}},
    ])


@dataclass
class RequestResult:
    status_code: int
    elapsed_ms: float
    error: str = ""


class LoadTestRunner:
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results: list[RequestResult] = []
        self._stop = False

    async def run(self) -> dict:
        import httpx

        endpoints = self._weighted_endpoints()
        start_time = time.monotonic()
        end_time = start_time + self.config.duration_seconds

        async def worker(worker_id: int):
            async with httpx.AsyncClient(base_url=self.config.base_url, timeout=30.0) as client:
                while not self._stop and time.monotonic() < end_time:
                    ep = endpoints[worker_id % len(endpoints)]
                    req_start = time.monotonic()
                    try:
                        resp = await client.request(
                            method=ep["method"],
                            url=ep["path"],
                            headers=ep.get("headers", {}),
                        )
                        elapsed = (time.monotonic() - req_start) * 1000
                        self.results.append(RequestResult(status_code=resp.status_code, elapsed_ms=elapsed))
                    except Exception as e:
                        elapsed = (time.monotonic() - req_start) * 1000
                        self.results.append(RequestResult(status_code=0, elapsed_ms=elapsed, error=str(e)))

        ramp_step = self.config.concurrent_users / max(self.config.ramp_up_seconds, 1)
        tasks = []
        for i in range(self.config.concurrent_users):
            if i > 0 and i % int(ramp_step) == 0:
                await asyncio.sleep(1.0)
            tasks.append(asyncio.create_task(worker(i)))

        await asyncio.gather(*tasks, return_exceptions=True)
        return self._generate_report()

    def _weighted_endpoints(self) -> list[dict]:
        weighted = []
        for ep in self.config.endpoints:
            path = ep["path"]
            if not path.startswith(self.config.api_prefix):
                path = self.config.api_prefix + path
            weighted.extend([{**ep, "path": path}] * ep.get("weight", 1))
        return weighted

    def _generate_report(self) -> dict:
        if not self.results:
            return {"error": "No results collected"}

        latencies = [r.elapsed_ms for r in self.results]
        errors = [r for r in self.results if r.error]
        status_counts = {}
        for r in self.results:
            key = str(r.status_code)
            status_counts[key] = status_counts.get(key, 0) + 1

        latencies_sorted = sorted(latencies)
        total_time = self.config.duration_seconds

        return {
            "total_requests": len(self.results),
            "total_errors": len(errors),
            "error_rate": round(len(errors) / len(self.results) * 100, 2),
            "requests_per_second": round(len(self.results) / total_time, 2),
            "latency_ms": {
                "min": round(min(latencies), 2),
                "max": round(max(latencies), 2),
                "mean": round(statistics.mean(latencies), 2),
                "median": round(statistics.median(latencies), 2),
                "p90": round(latencies_sorted[int(len(latencies_sorted) * 0.9)], 2),
                "p95": round(latencies_sorted[int(len(latencies_sorted) * 0.95)], 2),
                "p99": round(latencies_sorted[int(len(latencies_sorted) * 0.99)], 2),
            },
            "status_codes": status_counts,
            "concurrent_users": self.config.concurrent_users,
            "duration_seconds": total_time,
        }


async def main():
    config = LoadTestConfig()
    runner = LoadTestRunner(config)
    report = await runner.run()
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
