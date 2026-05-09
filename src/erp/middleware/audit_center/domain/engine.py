from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class AuditRecord:
    id: str = ""
    tenant_id: str = ""
    trace_id: str = ""
    actor_id: str = ""
    actor_type: str = "user"
    actor_name: str = ""
    action: str = ""
    resource_type: str = ""
    resource_id: str = ""
    resource_name: str = ""
    domain: str = ""
    before_data: dict = field(default_factory=dict)
    after_data: dict = field(default_factory=dict)
    diff: dict = field(default_factory=dict)
    ip_address: str = ""
    user_agent: str = ""
    request_path: str = ""
    request_method: str = ""
    status: str = "success"
    error_message: str = ""
    created_at: str = ""


class AuditCenterEngine:
    def __init__(self):
        self._records: list[AuditRecord] = []

    def log(self, tenant_id: str, action: str, resource_type: str, resource_id: str = "",
             resource_name: str = "", domain: str = "", actor_id: str = "",
             actor_type: str = "user", actor_name: str = "",
             before: dict | None = None, after: dict | None = None,
             ip_address: str = "", user_agent: str = "",
             request_path: str = "", request_method: str = "",
             status: str = "success", error_message: str = "",
             trace_id: str = "") -> AuditRecord:
        diff = {}
        if before and after:
            for key in set(list(before.keys()) + list(after.keys())):
                b_val = before.get(key)
                a_val = after.get(key)
                if b_val != a_val:
                    diff[key] = {"before": b_val, "after": a_val}

        record = AuditRecord(
            id=str(uuid.uuid4()), tenant_id=tenant_id, trace_id=trace_id,
            actor_id=actor_id, actor_type=actor_type, actor_name=actor_name,
            action=action, resource_type=resource_type, resource_id=resource_id,
            resource_name=resource_name, domain=domain,
            before_data=before or {}, after_data=after or {}, diff=diff,
            ip_address=ip_address, user_agent=user_agent,
            request_path=request_path, request_method=request_method,
            status=status, error_message=error_message,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._records.append(record)
        return record

    def query(self, tenant_id: str, domain: str = "", action: str = "",
              actor_id: str = "", resource_type: str = "", resource_id: str = "",
              start_date: str = "", end_date: str = "",
              status: str = "", limit: int = 50, offset: int = 0) -> list[AuditRecord]:
        results = [r for r in self._records if r.tenant_id == tenant_id]
        if domain:
            results = [r for r in results if r.domain == domain]
        if action:
            results = [r for r in results if r.action == action]
        if actor_id:
            results = [r for r in results if r.actor_id == actor_id]
        if resource_type:
            results = [r for r in results if r.resource_type == resource_type]
        if resource_id:
            results = [r for r in results if r.resource_id == resource_id]
        if status:
            results = [r for r in results if r.status == status]
        return results[offset:offset + limit]

    def export(self, tenant_id: str, domain: str = "", start_date: str = "",
               end_date: str = "", output_format: str = "json") -> list[dict]:
        records = self.query(tenant_id, domain=domain, start_date=start_date, end_date=end_date, limit=10000)
        return [self._record_to_dict(r) for r in records]

    def _record_to_dict(self, r: AuditRecord) -> dict:
        return {"id": r.id, "trace_id": r.trace_id, "actor_id": r.actor_id,
                "actor_name": r.actor_name, "action": r.action,
                "resource_type": r.resource_type, "resource_id": r.resource_id,
                "resource_name": r.resource_name, "domain": r.domain,
                "diff": r.diff, "ip_address": r.ip_address,
                "request_path": r.request_path, "status": r.status,
                "created_at": r.created_at}
