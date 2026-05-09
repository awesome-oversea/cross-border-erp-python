from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from erp.modules.tms.domain.repositories import (
        DispatchRecordRepository,
        FreightQuoteRepository,
        LogisticsConnectorRepository,
        ShipmentLabelRepository,
        TrackingRecordRepository,
    )


class LogisticsConnectorType(StrEnum):
    DOMESTIC = "domestic"
    INTERNATIONAL = "international"
    FBA = "fba"
    OVERSEAS = "overseas"
    EXPRESS = "express"


class LabelFormat(StrEnum):
    PDF = "pdf"
    PNG = "png"
    ZPL = "zpl"
    EPL = "epl"


class TrackingStatus(StrEnum):
    PENDING = "pending"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    EXCEPTION = "exception"
    RETURNED = "returned"


class LogisticsConnector(Base):
    __tablename__ = "logistics_connector"
    __table_args__ = {"schema": "tms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    connector_name: Mapped[str] = mapped_column(String(200), nullable=False)
    connector_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    carrier_name: Mapped[str] = mapped_column(String(200), nullable=False)
    carrier_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    connector_type: Mapped[str] = mapped_column(String(50), nullable=False, default="domestic")
    api_base_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    auth_type: Mapped[str] = mapped_column(String(50), nullable=False, default="api_key")
    auth_config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    supported_services_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    supported_label_formats_json: Mapped[str] = mapped_column(Text, nullable=False, default='["pdf"]')
    supported_origins_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    supported_destinations_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    health_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ShipmentLabel(Base):
    __tablename__ = "shipment_label"
    __table_args__ = {"schema": "tms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    shipment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tracking_number: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    carrier_code: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    service_code: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    label_format: Mapped[str] = mapped_column(String(20), nullable=False, default="pdf")
    label_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    label_data_base64: Mapped[str] = mapped_column(Text, nullable=False, default="")
    label_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    request_params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    response_meta_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error_message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TrackingRecord(Base):
    __tablename__ = "tracking_record"
    __table_args__ = {"schema": "tms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    shipment_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    tracking_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    carrier_code: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    current_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    origin_location: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    destination_location: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    events_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    estimated_delivery: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_delivery: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exception_code: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    exception_message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FreightQuote(Base):
    __tablename__ = "freight_quote"
    __table_args__ = {"schema": "tms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    quote_request_id: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    origin_country: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    origin_zip: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    destination_country: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    destination_zip: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    weight_grams: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dimensions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    service_code: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    service_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    carrier_code: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    estimated_days_min: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_days_max: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    freight_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    fuel_surcharge: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    other_surcharge: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    quote_response_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_expired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DispatchRecord(Base):
    __tablename__ = "dispatch_record"
    __table_args__ = {"schema": "tms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    shipment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    tracking_number: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    carrier_code: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    service_code: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    dispatch_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    request_params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    response_meta_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error_message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    dispatch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class LogisticsConnectorService:
    """
    物流连接器应用服务

    编排物流连接器的完整生命周期: 创建 → 面单申请 → 轨迹查询 →
    运费报价 → 发货调度 → 健康检查
    通过多个仓储接口操作数据。
    """

    def __init__(self, session: AsyncSession,
                 connector_repo: LogisticsConnectorRepository | None = None,
                 label_repo: ShipmentLabelRepository | None = None,
                 tracking_record_repo: TrackingRecordRepository | None = None,
                 quote_repo: FreightQuoteRepository | None = None,
                 dispatch_repo: DispatchRecordRepository | None = None):
        self.session = session
        self._connector_repo = connector_repo
        self._label_repo = label_repo
        self._tracking_record_repo = tracking_record_repo
        self._quote_repo = quote_repo
        self._dispatch_repo = dispatch_repo

    async def create_connector(self, tenant_id: str, connector_name: str, connector_code: str,
                                carrier_name: str, carrier_code: str,
                                connector_type: str = "domestic",
                                api_base_url: str = "", auth_type: str = "api_key",
                                auth_config: dict | None = None,
                                supported_services: list | None = None,
                                supported_label_formats: list | None = None,
                                supported_origins: list | None = None,
                                supported_destinations: list | None = None,
                                rate_limit_per_minute: int = 60,
                                timeout_seconds: int = 30,
                                max_retries: int = 3,
                                description: str = "") -> LogisticsConnector:
        """创建物流连接器: 唯一性校验(code) → 持久化"""
        existing = await self._get_by_code(tenant_id, connector_code)
        if existing:
            raise ValidationException(message=f"Connector code '{connector_code}' already exists")

        connector = LogisticsConnector(
            tenant_id=tenant_id, connector_name=connector_name, connector_code=connector_code,
            carrier_name=carrier_name, carrier_code=carrier_code,
            connector_type=connector_type, api_base_url=api_base_url,
            auth_type=auth_type, auth_config_json=json.dumps(auth_config or {}, default=str),
            supported_services_json=json.dumps(supported_services or [], default=str),
            supported_label_formats_json=json.dumps(supported_label_formats or ["pdf"], default=str),
            supported_origins_json=json.dumps(supported_origins or [], default=str),
            supported_destinations_json=json.dumps(supported_destinations or [], default=str),
            rate_limit_per_minute=rate_limit_per_minute, timeout_seconds=timeout_seconds,
            max_retries=max_retries, description=description,
            created_by=actor_id_var.get(""),
        )
        if self._connector_repo:
            return await self._connector_repo.create(connector)
        self.session.add(connector)
        await self.session.flush()
        return connector

    async def init_default_connectors(self, tenant_id: str) -> list[LogisticsConnector]:
        defaults = [
            ("顺丰速运", "sf_express", "顺丰", "SF", "domestic",
             "https://api.sf-express.com", "oauth2",
             {"client_id": "", "client_secret": "", "grant_type": "client_credentials"},
             ["standard", "express", "economy"], ["pdf", "zpl"],
             ["CN"], ["CN"], 120, 30, 3, "顺丰国内快递"),
            ("云途物流", "yunexpress", "云途", "YUN", "international",
             "https://api.yunexpress.com", "api_key",
             {"api_key": "", "api_secret": ""},
             ["standard", "registered", "express"], ["pdf"],
             ["CN"], ["US", "GB", "DE", "FR", "JP", "AU", "CA"], 60, 30, 3, "云途国际物流"),
            ("递四方", "4px", "递四方", "4PX", "international",
             "https://api.4px.com", "api_key",
             {"api_key": "", "api_secret": ""},
             ["standard", "express", "economy"], ["pdf"],
             ["CN"], ["US", "GB", "DE", "FR", "AU"], 60, 30, 3, "递四方国际物流"),
            ("亚马逊FBA", "amazon_fba", "Amazon", "AMZ_FBA", "fba",
             "https://sellingpartnerapi.amazon.com", "oauth2",
             {"client_id": "", "client_secret": "", "refresh_token": ""},
             ["fba_small", "fba_standard", "fba_oversize"], ["pdf", "zpl"],
             ["CN", "US"], ["US", "GB", "DE", "JP", "AU", "CA"], 30, 60, 5, "亚马逊FBA货件"),
            ("燕文物流", "yanwen", "燕文", "YW", "international",
             "https://api.yanwen.com", "api_key",
             {"api_key": ""},
             ["standard", "registered", "express"], ["pdf"],
             ["CN"], ["US", "GB", "DE", "FR", "ES", "IT"], 60, 30, 3, "燕文国际物流"),
        ]
        connectors = []
        for name, code, carrier, carrier_code, ctype, url, atype, auth, svc, lf, orig, dest, rl, to, mr, desc in defaults:
            existing = await self._get_by_code(tenant_id, code)
            if not existing:
                c = await self.create_connector(
                    tenant_id=tenant_id, connector_name=name, connector_code=code,
                    carrier_name=carrier, carrier_code=carrier_code,
                    connector_type=ctype, api_base_url=url, auth_type=atype,
                    auth_config=auth, supported_services=svc,
                    supported_label_formats=lf, supported_origins=orig,
                    supported_destinations=dest, rate_limit_per_minute=rl,
                    timeout_seconds=to, max_retries=mr, description=desc,
                )
                connectors.append(c)
        return connectors

    async def request_label(self, tenant_id: str, connector_id: str,
                             shipment_id: str, service_code: str = "",
                             label_format: str = "pdf",
                             shipper: dict | None = None,
                             recipient: dict | None = None,
                             packages: list | None = None,
                             request_params: dict | None = None) -> ShipmentLabel:
        """申请面单: 连接器校验 → 创建面单记录"""
        connector = await self._get_connector(connector_id, tenant_id)
        if not connector or not connector.is_active:
            raise ValidationException(message=f"Connector '{connector_id}' not available")

        label = ShipmentLabel(
            tenant_id=tenant_id, connector_id=connector_id,
            shipment_id=shipment_id, carrier_code=connector.carrier_code,
            service_code=service_code, label_format=label_format,
            label_status="pending",
            request_params_json=json.dumps({
                "shipper": shipper or {}, "recipient": recipient or {},
                "packages": packages or [], "params": request_params or {},
            }, default=str),
            trace_id=trace_id_var.get(""),
        )
        if self._label_repo:
            return await self._label_repo.create(label)
        self.session.add(label)
        await self.session.flush()
        return label

    async def query_tracking(self, tenant_id: str, connector_id: str,
                              tracking_number: str, shipment_id: str = "",
                              carrier_code: str = "") -> TrackingRecord:
        """查询物流轨迹: 连接器校验 → 已有记录则更新同步次数 → 否则新建"""
        connector = await self._get_connector(connector_id, tenant_id)
        if not connector or not connector.is_active:
            raise ValidationException(message=f"Connector '{connector_id}' not available")

        existing = await self._get_tracking(tenant_id, tracking_number)
        if existing:
            existing.sync_count += 1
            existing.last_synced_at = datetime.now(UTC)
            existing.trace_id = trace_id_var.get("")
            if self._tracking_record_repo:
                await self._tracking_record_repo.update(existing)
                return existing
            await self.session.flush()
            return existing

        record = TrackingRecord(
            tenant_id=tenant_id, connector_id=connector_id,
            shipment_id=shipment_id, tracking_number=tracking_number,
            carrier_code=carrier_code or connector.carrier_code,
            current_status=TrackingStatus.PENDING.value,
            events_json="[]",
            trace_id=trace_id_var.get(""),
        )
        if self._tracking_record_repo:
            return await self._tracking_record_repo.create(record)
        self.session.add(record)
        await self.session.flush()
        return record

    async def request_freight_quote(self, tenant_id: str, connector_id: str,
                                     origin_country: str, destination_country: str,
                                     weight_grams: int = 0,
                                     dimensions: dict | None = None,
                                     origin_zip: str = "", destination_zip: str = "",
                                     service_code: str = "") -> FreightQuote:
        """请求运费报价: 连接器校验 → 创建报价记录"""
        connector = await self._get_connector(connector_id, tenant_id)
        if not connector or not connector.is_active:
            raise ValidationException(message=f"Connector '{connector_id}' not available")

        quote = FreightQuote(
            tenant_id=tenant_id, connector_id=connector_id,
            quote_request_id=f"QR-{uuid.uuid4().hex[:12].upper()}",
            origin_country=origin_country, origin_zip=origin_zip,
            destination_country=destination_country, destination_zip=destination_zip,
            weight_grams=weight_grams,
            dimensions_json=json.dumps(dimensions or {}, default=str),
            service_code=service_code,
            carrier_code=connector.carrier_code,
            trace_id=trace_id_var.get(""),
        )
        if self._quote_repo:
            return await self._quote_repo.create(quote)
        self.session.add(quote)
        await self.session.flush()
        return quote

    async def create_dispatch(self, tenant_id: str, connector_id: str,
                               shipment_id: str, service_code: str = "",
                               packages: list | None = None,
                               request_params: dict | None = None) -> DispatchRecord:
        """创建发货调度: 连接器校验 → 创建调度记录"""
        connector = await self._get_connector(connector_id, tenant_id)
        if not connector or not connector.is_active:
            raise ValidationException(message=f"Connector '{connector_id}' not available")

        dispatch = DispatchRecord(
            tenant_id=tenant_id, connector_id=connector_id,
            shipment_id=shipment_id, carrier_code=connector.carrier_code,
            service_code=service_code, dispatch_status="pending",
            request_params_json=json.dumps({
                "packages": packages or [], "params": request_params or {},
            }, default=str),
            trace_id=trace_id_var.get(""),
            created_by=actor_id_var.get(""),
        )
        if self._dispatch_repo:
            return await self._dispatch_repo.create(dispatch)
        self.session.add(dispatch)
        await self.session.flush()
        return dispatch

    async def cancel_dispatch(self, dispatch_id: str, tenant_id: str) -> DispatchRecord:
        """取消发货调度: 状态校验 → 更新为cancelled"""
        dispatch = await self._get_dispatch(dispatch_id, tenant_id)
        if not dispatch:
            raise NotFoundException(message=f"Dispatch '{dispatch_id}' not found")
        if dispatch.dispatch_status not in ["pending", "submitted"]:
            raise ValidationException(message=f"Cannot cancel dispatch in status '{dispatch.dispatch_status}'")

        dispatch.dispatch_status = "cancelled"
        dispatch.cancel_at = datetime.now(UTC)
        if self._dispatch_repo:
            return await self._dispatch_repo.update(dispatch)
        await self.session.flush()
        return dispatch

    async def health_check(self, connector_id: str, tenant_id: str) -> dict:
        """连接器健康检查: 更新健康状态"""
        connector = await self._get_connector(connector_id, tenant_id)
        if not connector:
            raise NotFoundException(message=f"Connector '{connector_id}' not found")

        connector.health_status = "healthy"
        connector.last_health_check_at = datetime.now(UTC)
        if self._connector_repo:
            await self._connector_repo.update(connector)
        else:
            await self.session.flush()
        return {
            "connector_id": connector.id, "connector_name": connector.connector_name,
            "carrier_name": connector.carrier_name, "health_status": connector.health_status,
            "last_health_check_at": connector.last_health_check_at.isoformat() if connector.last_health_check_at else None,
        }

    async def list_connectors(self, tenant_id: str, connector_type: str = "",
                               carrier_code: str = "",
                               page: int = 1, page_size: int = 20) -> tuple[list[LogisticsConnector], int]:
        """分页查询物流连接器列表"""
        if self._connector_repo:
            items, total = await self._connector_repo.list_by_tenant(
                tenant_id, connector_type=connector_type,
                carrier_code=carrier_code, page=page, page_size=page_size,
            )
            return list(items), total
        conditions = [LogisticsConnector.tenant_id == tenant_id]
        if connector_type:
            conditions.append(LogisticsConnector.connector_type == connector_type)
        if carrier_code:
            conditions.append(LogisticsConnector.carrier_code == carrier_code)

        stmt = select(LogisticsConnector).where(*conditions).order_by(LogisticsConnector.created_at.desc())
        total_result = await self.session.execute(
            select(func.count()).select_from(LogisticsConnector).where(*conditions)
        )
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size
        result = await self.session.execute(stmt.offset(offset).limit(page_size))
        return list(result.scalars().all()), total

    async def get_connector(self, connector_id: str, tenant_id: str) -> LogisticsConnector | None:
        """获取物流连接器详情"""
        return await self._get_connector(connector_id, tenant_id)

    async def get_connector_or_raise(self, connector_id: str, tenant_id: str) -> LogisticsConnector:
        """获取物流连接器详情，不存在则抛出 NotFoundException"""
        connector = await self._get_connector(connector_id, tenant_id)
        if not connector:
            raise NotFoundException(message=f"Connector '{connector_id}' not found")
        return connector

    async def update_connector(self, connector_id: str, tenant_id: str, **kwargs) -> LogisticsConnector:
        """更新物流连接器"""
        connector = await self._get_connector(connector_id, tenant_id)
        if not connector:
            raise NotFoundException(message=f"Connector '{connector_id}' not found")
        for field in ("connector_name", "api_base_url", "auth_type",
                       "rate_limit_per_minute", "timeout_seconds",
                       "max_retries", "description"):
            if field in kwargs and kwargs[field] is not None:
                setattr(connector, field, kwargs[field])
        if "auth_config" in kwargs and kwargs["auth_config"] is not None:
            connector.auth_config_json = json.dumps(kwargs["auth_config"], default=str)
        if "is_active" in kwargs and kwargs["is_active"] is not None:
            connector.is_active = kwargs["is_active"]
        if self._connector_repo:
            return await self._connector_repo.update(connector)
        await self.session.flush()
        return connector

    async def _get_connector(self, connector_id: str, tenant_id: str) -> LogisticsConnector | None:
        if self._connector_repo:
            return await self._connector_repo.get_by_id(connector_id, tenant_id)
        stmt = select(LogisticsConnector).where(
            LogisticsConnector.id == connector_id, LogisticsConnector.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_by_code(self, tenant_id: str, code: str) -> LogisticsConnector | None:
        if self._connector_repo:
            return await self._connector_repo.get_by_code(tenant_id, code)
        stmt = select(LogisticsConnector).where(
            LogisticsConnector.tenant_id == tenant_id, LogisticsConnector.connector_code == code,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_tracking(self, tenant_id: str, tracking_number: str) -> TrackingRecord | None:
        if self._tracking_record_repo:
            return await self._tracking_record_repo.get_by_tracking_number(tenant_id, tracking_number)
        stmt = select(TrackingRecord).where(
            TrackingRecord.tenant_id == tenant_id, TrackingRecord.tracking_number == tracking_number,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_dispatch(self, dispatch_id: str, tenant_id: str) -> DispatchRecord | None:
        if self._dispatch_repo:
            return await self._dispatch_repo.get_by_id(dispatch_id, tenant_id)
        stmt = select(DispatchRecord).where(
            DispatchRecord.id == dispatch_id, DispatchRecord.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
