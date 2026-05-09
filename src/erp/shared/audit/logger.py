from __future__ import annotations

import json
import uuid
from datetime import datetime
from functools import wraps
from typing import TYPE_CHECKING

from fastapi import Request
from sqlalchemy import DateTime, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, actor_type_var, tenant_id_var, trace_id_var
from erp.shared.db.base import Base

if TYPE_CHECKING:
    from collections.abc import Callable


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "iam"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False, default="user")
    actor_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    resource_name: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    domain: Mapped[str] = mapped_column(String(50), nullable=False, default="", index=True)
    before_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    after_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    diff_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    ip_address: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    user_agent: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    request_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    request_method: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditLogService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(self, action: str, resource_type: str, resource_id: str = "",
                  resource_name: str = "", domain: str = "", before: dict | None = None,
                  after: dict | None = None, ip_address: str = "", user_agent: str = "",
                  request_path: str = "", request_method: str = "", status: str = "success",
                  error_message: str = "") -> AuditLog:
        diff = {}
        if before and after:
            for key in set(list(before.keys()) + list(after.keys())):
                b_val = before.get(key)
                a_val = after.get(key)
                if b_val != a_val:
                    diff[key] = {"before": b_val, "after": a_val}

        log_entry = AuditLog(
            tenant_id=tenant_id_var.get(""),
            trace_id=trace_id_var.get(""),
            actor_id=actor_id_var.get(""),
            actor_type=actor_type_var.get("user"),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            domain=domain,
            before_json=json.dumps(before or {}, default=str, ensure_ascii=False),
            after_json=json.dumps(after or {}, default=str, ensure_ascii=False),
            diff_json=json.dumps(diff, default=str, ensure_ascii=False),
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request_path,
            request_method=request_method,
            status=status,
            error_message=error_message,
        )
        self.session.add(log_entry)
        await self.session.flush()
        return log_entry

    async def query(self, tenant_id: str, domain: str | None = None,
                    resource_type: str | None = None, action: str | None = None,
                    actor_id: str | None = None, start_date: datetime | None = None,
                    end_date: datetime | None = None, offset: int = 0,
                    limit: int = 50) -> list[AuditLog]:
        stmt = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
        if domain:
            stmt = stmt.where(AuditLog.domain == domain)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if actor_id:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        if start_date:
            stmt = stmt.where(AuditLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(AuditLog.created_at <= end_date)
        stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


def audit_log(action: str, resource_type: str, domain: str = ""):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            try:
                session = kwargs.get("session")
                if session and isinstance(session, AsyncSession):
                    svc = AuditLogService(session)
                    request = kwargs.get("request")
                    ip_address = ""
                    user_agent = ""
                    request_path = ""
                    request_method = ""
                    if request and isinstance(request, Request):
                        ip_address = request.client.host if request.client else ""
                        user_agent = request.headers.get("user-agent", "")
                        request_path = str(request.url.path)
                        request_method = request.method
                    resource_id = ""
                    resource_name = ""
                    if isinstance(result, dict):
                        data = result.get("data", {})
                        if isinstance(data, dict):
                            resource_id = data.get("id", "")
                            resource_name = data.get("name", data.get("code", ""))
                    await svc.log(
                        action=action,
                        resource_type=resource_type,
                        domain=domain,
                        resource_id=resource_id,
                        resource_name=resource_name,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        request_path=request_path,
                        request_method=request_method,
                    )
            except Exception:
                pass
            return result
        return wrapper
    return decorator
