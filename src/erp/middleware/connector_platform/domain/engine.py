from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class PlatformConnector:
    connector_id: str = ""
    connector_type: str = ""
    connector_name: str = ""
    platform: str = ""
    version: str = "1.0.0"
    config: dict = field(default_factory=dict)
    is_active: bool = True
    health_status: str = "unknown"
    last_health_check: str = ""
    registered_at: str = ""


@dataclass
class ConnectorCallStat:
    stat_id: str = ""
    connector_id: str = ""
    tenant_id: str = ""
    success: bool = True
    response_time_ms: int = 0
    called_at: str = ""


class ConnectorPlatformEngine:
    def __init__(self):
        self._connectors: dict[str, PlatformConnector] = {}
        self._call_stats: list[ConnectorCallStat] = []
        self._register_default_connectors()

    def _register_default_connectors(self):
        defaults = [
            ("amazon-sp", "marketplace", "Amazon SP-API", "amazon", "1.0.0"),
            ("shopify", "marketplace", "Shopify API", "shopify", "1.0.0"),
            ("ebay", "marketplace", "eBay API", "ebay", "1.0.0"),
            ("yanwen", "logistics", "燕文物流", "yanwen", "1.0.0"),
            ("4px", "logistics", "递四方", "4px", "1.0.0"),
            ("dhl", "logistics", "DHL Express", "dhl", "1.0.0"),
            ("stripe", "payment", "Stripe", "stripe", "1.0.0"),
            ("paypal", "payment", "PayPal", "paypal", "1.0.0"),
            ("pingpong", "payment", "PingPong", "pingpong", "1.0.0"),
        ]
        for cid, ctype, name, platform, version in defaults:
            self._connectors[cid] = PlatformConnector(
                connector_id=cid, connector_type=ctype, connector_name=name,
                platform=platform, version=version, health_status="healthy",
                registered_at=datetime.now(UTC).isoformat(),
            )

    def list_connectors(self, connector_type: str = "", platform: str = "") -> list[dict]:
        results = list(self._connectors.values())
        if connector_type:
            results = [c for c in results if c.connector_type == connector_type]
        if platform:
            results = [c for c in results if c.platform == platform]
        return [{"connector_id": c.connector_id, "connector_type": c.connector_type,
                 "connector_name": c.connector_name, "platform": c.platform,
                 "version": c.version, "is_active": c.is_active,
                 "health_status": c.health_status, "registered_at": c.registered_at}
                for c in results]

    def register_connector(self, connector_type: str, connector_name: str, platform: str,
                            version: str = "1.0.0", config: dict | None = None) -> dict:
        connector_id = f"{platform}-{connector_type}"
        connector = PlatformConnector(
            connector_id=connector_id, connector_type=connector_type,
            connector_name=connector_name, platform=platform, version=version,
            config=config or {}, health_status="unknown",
            registered_at=datetime.now(UTC).isoformat(),
        )
        self._connectors[connector_id] = connector
        return {"connector_id": connector_id, "connector_name": connector_name, "status": "registered"}

    def health_check(self, connector_id: str = "") -> dict:
        if connector_id:
            connector = self._connectors.get(connector_id)
            if not connector:
                return {"success": False, "error": "Connector not found"}
            connector.health_status = "healthy"
            connector.last_health_check = datetime.now(UTC).isoformat()
            return {"connector_id": connector_id, "health_status": "healthy"}

        results = {}
        for cid, connector in self._connectors.items():
            connector.health_status = "healthy"
            connector.last_health_check = datetime.now(UTC).isoformat()
            results[cid] = {"health_status": "healthy", "last_check": connector.last_health_check}
        return {"total": len(results), "healthy": len(results), "results": results}

    def record_call(self, tenant_id: str, connector_id: str, success: bool = True,
                     response_time_ms: int = 0) -> dict:
        stat = ConnectorCallStat(
            stat_id=str(uuid.uuid4()), connector_id=connector_id,
            tenant_id=tenant_id, success=success, response_time_ms=response_time_ms,
            called_at=datetime.now(UTC).isoformat(),
        )
        self._call_stats.append(stat)
        return {"stat_id": stat.stat_id, "recorded": True}

    def get_stats(self, tenant_id: str, connector_id: str = "", hours: int = 24) -> dict:
        results = [s for s in self._call_stats if s.tenant_id == tenant_id]
        if connector_id:
            results = [s for s in results if s.connector_id == connector_id]
        total = len(results)
        success = len([s for s in results if s.success])
        avg_time = sum(s.response_time_ms for s in results) / total if total else 0
        return {"total_calls": total, "success_calls": success,
                "failed_calls": total - success,
                "success_rate_pct": round(success / total * 100, 2) if total else 0,
                "avg_response_time_ms": round(avg_time, 2), "period_hours": hours}
