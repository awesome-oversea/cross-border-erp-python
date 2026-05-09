from __future__ import annotations

import abc
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
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
    PROCUREMENT = "procurement"
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


@dataclass
class ConnectorCallResult:
    success: bool = True
    data: Any = None
    error: str = ""
    status_code: int = 200
    raw_response: str = ""
    trace_id: str = ""


@dataclass
class ConnectorAuthConfig:
    auth_type: str = "oauth2"
    client_id: str = ""
    client_secret: str = ""
    access_token: str = ""
    refresh_token: str = ""
    token_expiry: str = ""
    api_key: str = ""
    api_secret: str = ""
    extra: dict = field(default_factory=dict)


class ConnectorSPI(abc.ABC):
    @abc.abstractmethod
    async def authenticate(self, config: ConnectorAuthConfig) -> ConnectorAuthConfig:
        ...

    @abc.abstractmethod
    async def call(self, method: str, path: str, params: dict | None = None,
                   body: dict | None = None, headers: dict | None = None) -> ConnectorCallResult:
        ...

    @abc.abstractmethod
    async def health_check(self) -> bool:
        ...

    @abc.abstractmethod
    async def refresh_token(self) -> ConnectorAuthConfig:
        ...


class BaseConnector(ConnectorSPI):
    def __init__(self, connector_id: str, tenant_id: str, auth_config: ConnectorAuthConfig,
                 base_url: str = "", rate_limit: int = 100, timeout: int = 30):
        self.connector_id = connector_id
        self.tenant_id = tenant_id
        self.auth_config = auth_config
        self.base_url = base_url
        self.rate_limit = rate_limit
        self.timeout = timeout
        self._call_count = 0

    async def authenticate(self, config: ConnectorAuthConfig) -> ConnectorAuthConfig:
        self.auth_config = config
        return config

    async def call(self, method: str, path: str, params: dict | None = None,
                   body: dict | None = None, headers: dict | None = None) -> ConnectorCallResult:
        self._call_count += 1
        return ConnectorCallResult(
            success=True,
            data={"message": "Base connector call - override in subclass"},
            trace_id=trace_id_var.get(""),
        )

    async def health_check(self) -> bool:
        return True

    async def refresh_token(self) -> ConnectorAuthConfig:
        return self.auth_config


class ConnectorRegistry:
    _connectors: dict[str, type[ConnectorSPI]] = {}

    @classmethod
    def register(cls, connector_type: str, connector_cls: type[ConnectorSPI]):
        cls._connectors[connector_type] = connector_cls

    @classmethod
    def get(cls, connector_type: str) -> type[ConnectorSPI] | None:
        return cls._connectors.get(connector_type)

    @classmethod
    def list_types(cls) -> list[str]:
        return list(cls._connectors.keys())


class MarketplaceConnector(BaseConnector):
    async def fetch_orders(self, start_time: str = "", end_time: str = "",
                            page_size: int = 50) -> ConnectorCallResult:
        return ConnectorCallResult(success=True, data={"orders": [], "total": 0},
                                   trace_id=trace_id_var.get(""))

    async def fetch_listings(self, status: str = "") -> ConnectorCallResult:
        return ConnectorCallResult(success=True, data={"listings": [], "total": 0},
                                   trace_id=trace_id_var.get(""))

    async def update_listing(self, listing_id: str, data: dict) -> ConnectorCallResult:
        return ConnectorCallResult(success=True, data={"listing_id": listing_id},
                                   trace_id=trace_id_var.get(""))

    async def acknowledge_order(self, order_id: str) -> ConnectorCallResult:
        return ConnectorCallResult(success=True, data={"order_id": order_id},
                                   trace_id=trace_id_var.get(""))

    async def ship_order(self, order_id: str, tracking_number: str,
                          carrier: str = "") -> ConnectorCallResult:
        return ConnectorCallResult(success=True,
                                   data={"order_id": order_id, "tracking_number": tracking_number},
                                   trace_id=trace_id_var.get(""))


class LogisticsConnector(BaseConnector):
    async def create_shipment(self, shipment_data: dict) -> ConnectorCallResult:
        return ConnectorCallResult(success=True, data={"shipment_id": "", "label_url": ""},
                                   trace_id=trace_id_var.get(""))

    async def get_tracking(self, tracking_number: str) -> ConnectorCallResult:
        return ConnectorCallResult(success=True, data={"status": "", "events": []},
                                   trace_id=trace_id_var.get(""))

    async def estimate_shipping_cost(self, params: dict) -> ConnectorCallResult:
        return ConnectorCallResult(success=True, data={"cost": 0, "currency": "CNY"},
                                   trace_id=trace_id_var.get(""))

    async def cancel_shipment(self, shipment_id: str) -> ConnectorCallResult:
        return ConnectorCallResult(success=True, data={"shipment_id": shipment_id},
                                   trace_id=trace_id_var.get(""))


class PaymentConnector(BaseConnector):
    async def get_balance(self) -> ConnectorCallResult:
        return ConnectorCallResult(success=True, data={"balance": 0, "currency": "USD"},
                                   trace_id=trace_id_var.get(""))

    async def get_transactions(self, start_date: str = "", end_date: str = "") -> ConnectorCallResult:
        return ConnectorCallResult(success=True, data={"transactions": []},
                                   trace_id=trace_id_var.get(""))

    async def initiate_payout(self, amount: float, currency: str = "USD") -> ConnectorCallResult:
        return ConnectorCallResult(success=True, data={"payout_id": ""},
                                   trace_id=trace_id_var.get(""))


class WarehouseConnector(BaseConnector):
    async def get_inventory(self, sku: str = "") -> ConnectorCallResult:
        return ConnectorCallResult(success=True, data={"inventory": []},
                                   trace_id=trace_id_var.get(""))

    async def create_inbound(self, inbound_data: dict) -> ConnectorCallResult:
        return ConnectorCallResult(success=True, data={"inbound_id": ""},
                                   trace_id=trace_id_var.get(""))


ConnectorRegistry.register("marketplace", MarketplaceConnector)
ConnectorRegistry.register("logistics", LogisticsConnector)
ConnectorRegistry.register("payment", PaymentConnector)
ConnectorRegistry.register("warehouse", WarehouseConnector)


class ConnectorEntity(Base):
    __tablename__ = "connector_config"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    connector_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    base_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    auth_config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    rate_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ConnectorCallLog(Base):
    __tablename__ = "connector_call_log"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    connector_code: Mapped[str] = mapped_column(String(100), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False, default="GET")
    path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    request_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    response_status: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ConnectorSPIService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_connector(self, tenant_id: str, name: str, code: str,
                                connector_type: str, provider: str = "",
                                base_url: str = "", auth_config: dict | None = None,
                                rate_limit: int = 100, timeout: int = 30,
                                config: dict | None = None) -> ConnectorEntity:
        existing = await self._get_by_code(tenant_id, code)
        if existing:
            raise ValidationException(message=f"Connector code '{code}' already exists")

        connector = ConnectorEntity(
            tenant_id=tenant_id, name=name, code=code,
            connector_type=connector_type, provider=provider,
            base_url=base_url,
            auth_config_json=json.dumps(auth_config or {}, default=str),
            rate_limit=rate_limit, timeout=timeout,
            config_json=json.dumps(config or {}, default=str),
            created_by=actor_id_var.get(""),
        )
        self.session.add(connector)
        await self.session.flush()
        return connector

    async def update_connector(self, connector_id: str, tenant_id: str,
                                name: str | None = None, base_url: str | None = None,
                                auth_config: dict | None = None,
                                rate_limit: int | None = None,
                                timeout: int | None = None,
                                config: dict | None = None) -> ConnectorEntity:
        connector = await self._get_by_id(connector_id, tenant_id)
        if not connector:
            raise NotFoundException(message=f"Connector '{connector_id}' not found")
        if name is not None:
            connector.name = name
        if base_url is not None:
            connector.base_url = base_url
        if auth_config is not None:
            connector.auth_config_json = json.dumps(auth_config, default=str)
        if rate_limit is not None:
            connector.rate_limit = rate_limit
        if timeout is not None:
            connector.timeout = timeout
        if config is not None:
            connector.config_json = json.dumps(config, default=str)
        await self.session.flush()
        return connector

    async def activate_connector(self, connector_id: str, tenant_id: str) -> ConnectorEntity:
        connector = await self._get_by_id(connector_id, tenant_id)
        if not connector:
            raise NotFoundException(message=f"Connector '{connector_id}' not found")
        connector.status = "active"
        connector.is_active = True
        await self.session.flush()
        return connector

    async def deactivate_connector(self, connector_id: str, tenant_id: str) -> ConnectorEntity:
        connector = await self._get_by_id(connector_id, tenant_id)
        if not connector:
            raise NotFoundException(message=f"Connector '{connector_id}' not found")
        connector.status = "inactive"
        connector.is_active = False
        await self.session.flush()
        return connector

    async def health_check(self, connector_id: str, tenant_id: str) -> dict:
        connector = await self._get_by_id(connector_id, tenant_id)
        if not connector:
            raise NotFoundException(message=f"Connector '{connector_id}' not found")

        connector_cls = ConnectorRegistry.get(connector.connector_type)
        if not connector_cls:
            return {"connector_id": connector_id, "status": "unknown_type",
                    "message": f"No SPI registered for type '{connector.connector_type}'"}

        auth_config = ConnectorAuthConfig(**json.loads(connector.auth_config_json))
        instance = connector_cls(
            connector_id=connector.id, tenant_id=tenant_id,
            auth_config=auth_config, base_url=connector.base_url,
            rate_limit=connector.rate_limit, timeout=connector.timeout,
        )

        try:
            is_healthy = await instance.health_check()
            connector.status = "active" if is_healthy else "error"
            await self.session.flush()
            return {"connector_id": connector_id, "status": "healthy" if is_healthy else "unhealthy"}
        except Exception as e:
            connector.status = "error"
            connector.error_count += 1
            await self.session.flush()
            return {"connector_id": connector_id, "status": "error", "error": str(e)}

    async def list_connectors(self, tenant_id: str, connector_type: str = "",
                               is_active: bool | None = None,
                               page: int = 1, page_size: int = 20) -> tuple[list[ConnectorEntity], int]:
        conditions = [ConnectorEntity.tenant_id == tenant_id]
        if connector_type:
            conditions.append(ConnectorEntity.connector_type == connector_type)
        if is_active is not None:
            conditions.append(ConnectorEntity.is_active == is_active)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(ConnectorEntity).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(ConnectorEntity).where(*conditions).order_by(
            ConnectorEntity.connector_type, ConnectorEntity.name
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_call_logs(self, tenant_id: str, connector_id: str = "",
                              page: int = 1, page_size: int = 20) -> tuple[list[ConnectorCallLog], int]:
        conditions = [ConnectorCallLog.tenant_id == tenant_id]
        if connector_id:
            conditions.append(ConnectorCallLog.connector_id == connector_id)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(ConnectorCallLog).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(ConnectorCallLog).where(*conditions).order_by(
            ConnectorCallLog.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def _get_by_code(self, tenant_id: str, code: str) -> ConnectorEntity | None:
        stmt = select(ConnectorEntity).where(
            ConnectorEntity.tenant_id == tenant_id,
            ConnectorEntity.code == code,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _get_by_id(self, connector_id: str, tenant_id: str) -> ConnectorEntity | None:
        stmt = select(ConnectorEntity).where(
            ConnectorEntity.id == connector_id,
            ConnectorEntity.tenant_id == tenant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
