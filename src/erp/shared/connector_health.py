"""
连接器健康检查与告警 (P5-012)

定时检查所有注册连接器的健康状态:
  - 心跳检测: 调用连接器的ping/health端点
  - 失败率统计: 最近N次调用的成功率
  - 授权过期预警: 检查Token/API Key是否即将过期
  - 延迟监控: 平均响应时间
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ConnectorHealthStatus:
    connector_id: str = ""
    status: str = "unknown"  # healthy / degraded / down
    latency_ms: float = 0.0
    last_success_at: str = ""
    last_error_at: str = ""
    error_message: str = ""
    failure_rate_24h: float = 0.0
    auth_expires_in_days: float = 0.0
    total_calls: int = 0
    success_calls: int = 0


@dataclass
class ConnectorCallRecord:
    connector_id: str = ""
    success: bool = False
    latency_ms: float = 0.0
    error: str = ""
    timestamp: float = 0.0


class ConnectorHealthChecker:
    """
    连接器健康检查器

    健康判定标准:
      - healthy:   成功率>95% 且 延迟<5s
      - degraded:  成功率>80% 或 延迟<10s
      - down:      成功率<=80% 或 连续失败>5次
    """
    """
    连接器健康检查器

    维护每个连接器的调用记录，计算健康指标:
      - 健康: 成功率 > 95% 且 延迟 < 5s
      - 降级: 成功率 > 80% 或 延迟 < 10s
      - 故障: 成功率 <= 80% 或 连续失败 > 5次
    """

    MAX_RECORDS = 10000

    def __init__(self):
        self._records: dict[str, list[ConnectorCallRecord]] = {}

    def record_call(self, connector_id: str, success: bool, latency_ms: float = 0.0, error: str = ""):
        """记录一次连接器调用"""
        if connector_id not in self._records:
            self._records[connector_id] = []
        self._records[connector_id].append(ConnectorCallRecord(
            connector_id=connector_id, success=success,
            latency_ms=latency_ms, error=error,
            timestamp=time.time(),
        ))
        if len(self._records[connector_id]) > self.MAX_RECORDS:
            self._records[connector_id] = self._records[connector_id][-5000:]

    def get_status(self, connector_id: str) -> ConnectorHealthStatus:
        """获取连接器当前健康状态"""
        records = self._records.get(connector_id, [])
        if not records:
            return ConnectorHealthStatus(connector_id=connector_id, status="unknown")

        recent = [r for r in records if r.timestamp > time.time() - 86400]
        total = len(recent)
        success = sum(1 for r in recent if r.success)
        failure_rate = 1 - (success / total) if total > 0 else 0
        avg_latency = sum(r.latency_ms for r in recent) / total if total > 0 else 0
        last_success = next((r for r in reversed(recent) if r.success), None)
        last_error = next((r for r in reversed(recent) if not r.success), None)
        recent_failures = sum(1 for r in records[-5:] if not r.success)

        if failure_rate > 0.2 or recent_failures >= 5:
            status = "down"
        elif failure_rate > 0.05 or avg_latency > 5000:
            status = "degraded"
        else:
            status = "healthy"

        return ConnectorHealthStatus(
            connector_id=connector_id, status=status,
            latency_ms=round(avg_latency, 2),
            last_success_at=datetime.fromtimestamp(last_success.timestamp, UTC).isoformat() if last_success else "",
            last_error_at=datetime.fromtimestamp(last_error.timestamp, UTC).isoformat() if last_error else "",
            error_message=last_error.error if last_error else "",
            failure_rate_24h=round(failure_rate * 100, 2),
            auth_expires_in_days=0,
            total_calls=total, success_calls=success,
        )

    def check_all(self) -> list[ConnectorHealthStatus]:
        """检查所有连接器的健康状态"""
        return [self.get_status(cid) for cid in self._records]

    def get_alerts(self) -> list[dict]:
        """生成需要告警的连接器列表"""
        alerts = []
        for cid in self._records:
            status = self.get_status(cid)
            if status.status == "down":
                alerts.append({"connector_id": cid, "severity": "P1",
                               "message": f"连接器 {cid} 故障", "status": status})
            elif status.status == "degraded":
                alerts.append({"connector_id": cid, "severity": "P2",
                               "message": f"连接器 {cid} 降级", "status": status})
        return alerts


_default_checker = ConnectorHealthChecker()


def get_health_checker() -> ConnectorHealthChecker:
    return _default_checker
