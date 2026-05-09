from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:

    from sqlalchemy.ext.asyncio import AsyncSession


class ConnectorType(StrEnum):
    MARKETPLACE = "marketplace"
    LOGISTICS = "logistics"
    PAYMENT = "payment"
    AD_PLATFORM = "ad_platform"
    ERP = "erp"
    PMS = "pms"
    WAREHOUSE = "warehouse"
    CUSTOM = "custom"


class ConnectorStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    SYNCING = "syncing"


class SyncStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class Connector(Base):
    __tablename__ = "connector"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    connector_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    credentials_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    endpoint_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ConnectorStatus.DRAFT.value, index=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    sync_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    is_auto_sync: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ConnectorSyncLog(Base):
    __tablename__ = "connector_sync_log"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sync_type: Mapped[str] = mapped_column(String(50), nullable=False, default="full")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SyncStatus.PENDING.value, index=True)
    records_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ConnectorService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, tenant_id: str, name: str, code: str,
                     connector_type: str, platform: str = "", **kwargs) -> Connector:
        existing = await self.session.execute(
            select(Connector).where(Connector.code == code)
        )
        if existing.scalar_one_or_none():
            raise ValidationException(f"Connector code already exists: {code}")
        connector = Connector(
            tenant_id=tenant_id, name=name, code=code,
            connector_type=connector_type, platform=platform,
            **{k: v for k, v in kwargs.items() if hasattr(Connector, k) and k != "id"}
        )
        self.session.add(connector)
        await self.session.flush()
        return connector

    async def get_by_id(self, connector_id: str) -> Connector | None:
        return await self.session.get(Connector, connector_id)

    async def get_or_raise(self, connector_id: str) -> Connector:
        connector = await self.get_by_id(connector_id)
        if not connector:
            raise NotFoundException(message=f"Connector '{connector_id}' not found")
        return connector

    async def get_by_code(self, code: str) -> Connector | None:
        stmt = select(Connector).where(Connector.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, connector_type: str | None = None,
                             status: str | None = None) -> list[Connector]:
        stmt = select(Connector).where(Connector.tenant_id == tenant_id)
        if connector_type:
            stmt = stmt.where(Connector.connector_type == connector_type)
        if status:
            stmt = stmt.where(Connector.status == status)
        stmt = stmt.order_by(Connector.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, connector_id: str, status: str) -> Connector:
        connector = await self.get_by_id(connector_id)
        if not connector:
            raise NotFoundException(f"Connector not found: {connector_id}")
        connector.status = status
        await self.session.flush()
        return connector

    async def update_config(self, connector_id: str, config_json: str,
                            credentials_json: str = "") -> Connector:
        connector = await self.get_by_id(connector_id)
        if not connector:
            raise NotFoundException(f"Connector not found: {connector_id}")
        connector.config_json = config_json
        if credentials_json:
            connector.credentials_json = credentials_json
        await self.session.flush()
        return connector

    async def delete(self, connector_id: str):
        connector = await self.get_by_id(connector_id)
        if not connector:
            raise NotFoundException(f"Connector not found: {connector_id}")
        await self.session.delete(connector)
        await self.session.flush()


class ConnectorSyncService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_log(self, tenant_id: str, connector_id: str,
                         sync_type: str = "full") -> ConnectorSyncLog:
        log = ConnectorSyncLog(
            tenant_id=tenant_id, connector_id=connector_id,
            sync_type=sync_type, status=SyncStatus.PENDING.value,
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def start_sync(self, log_id: str):
        log = await self.session.get(ConnectorSyncLog, log_id)
        if log:
            log.status = SyncStatus.RUNNING.value
            log.started_at = func.now()
            await self.session.flush()

    async def complete_sync(self, log_id: str, records_total: int = 0,
                            records_success: int = 0, records_failed: int = 0,
                            error_message: str = ""):
        log = await self.session.get(ConnectorSyncLog, log_id)
        if log:
            log.records_total = records_total
            log.records_success = records_success
            log.records_failed = records_failed
            log.error_message = error_message
            log.finished_at = func.now()
            if records_failed == 0:
                log.status = SyncStatus.SUCCESS.value
            elif records_success == 0:
                log.status = SyncStatus.FAILED.value
            else:
                log.status = SyncStatus.PARTIAL.value
            await self.session.flush()

    async def list_logs(self, tenant_id: str, connector_id: str | None = None,
                        limit: int = 50) -> list[ConnectorSyncLog]:
        stmt = select(ConnectorSyncLog).where(ConnectorSyncLog.tenant_id == tenant_id)
        if connector_id:
            stmt = stmt.where(ConnectorSyncLog.connector_id == connector_id)
        stmt = stmt.order_by(ConnectorSyncLog.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
