"""
TMS 基础设施层 — SQLAlchemy 仓储实现

为 domain/repositories.py 中定义的所有仓储接口提供
基于 SQLAlchemy 2.0 异步查询的具体实现。
"""
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.tms.domain.logistics_connector_models import (
    DispatchRecord,
    FreightQuote,
    LogisticsConnector,
    ShipmentLabel,
    TrackingRecord,
)
from erp.modules.tms.domain.models import FreightTemplate, LogisticsProvider, Shipment, ShippingBatch, ShippingMethod
from erp.modules.tms.domain.repositories import (
    DispatchRecordRepository,
    FreightQuoteRepository,
    FreightTemplateRepository,
    LogisticsConnectorRepository,
    LogisticsProviderRepository,
    LogisticsStrategyExecutionLogRepository,
    LogisticsStrategyRepository,
    ShippingBatchRepository,
    ShipmentLabelRepository,
    ShipmentRepository,
    ShippingMethodRepository,
    TrackingRecordRepository,
)
from erp.modules.tms.domain.strategy_models import LogisticsStrategy, LogisticsStrategyExecutionLog


class SqlLogisticsProviderRepository(LogisticsProviderRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, provider_id: str, tenant_id: str) -> LogisticsProvider | None:
        stmt = select(LogisticsProvider).where(
            LogisticsProvider.id == provider_id,
            LogisticsProvider.tenant_id == tenant_id,
            LogisticsProvider.deleted_at.is_(None),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, code: str, tenant_id: str) -> LogisticsProvider | None:
        stmt = select(LogisticsProvider).where(
            LogisticsProvider.code == code,
            LogisticsProvider.tenant_id == tenant_id,
            LogisticsProvider.deleted_at.is_(None),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "", provider_type: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[LogisticsProvider], int]:
        conditions = [LogisticsProvider.tenant_id == tenant_id, LogisticsProvider.deleted_at.is_(None)]
        if status:
            conditions.append(LogisticsProvider.status == status)
        if provider_type:
            conditions.append(LogisticsProvider.provider_type == provider_type)
        total = (await self._session.execute(
            select(func.count()).select_from(LogisticsProvider).where(*conditions)
        )).scalar() or 0
        stmt = select(LogisticsProvider).where(*conditions).order_by(
            LogisticsProvider.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, provider: LogisticsProvider) -> LogisticsProvider:
        self._session.add(provider)
        await self._session.flush()
        return provider

    async def update(self, provider: LogisticsProvider) -> LogisticsProvider:
        await self._session.flush()
        return provider

    async def soft_delete(self, provider_id: str, tenant_id: str) -> bool:
        stmt = update(LogisticsProvider).where(
            LogisticsProvider.id == provider_id,
            LogisticsProvider.tenant_id == tenant_id,
        ).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlShippingMethodRepository(ShippingMethodRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, method_id: str, tenant_id: str) -> ShippingMethod | None:
        stmt = select(ShippingMethod).where(
            ShippingMethod.id == method_id,
            ShippingMethod.tenant_id == tenant_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, code: str, tenant_id: str) -> ShippingMethod | None:
        stmt = select(ShippingMethod).where(
            ShippingMethod.code == code,
            ShippingMethod.tenant_id == tenant_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_provider(self, provider_id: str, tenant_id: str) -> Sequence[ShippingMethod]:
        stmt = select(ShippingMethod).where(
            ShippingMethod.provider_id == provider_id,
            ShippingMethod.tenant_id == tenant_id,
            ShippingMethod.status == "active",
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_tenant(self, tenant_id: str, status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[ShippingMethod], int]:
        conditions = [ShippingMethod.tenant_id == tenant_id]
        if status:
            conditions.append(ShippingMethod.status == status)
        total = (await self._session.execute(
            select(func.count()).select_from(ShippingMethod).where(*conditions)
        )).scalar() or 0
        stmt = select(ShippingMethod).where(*conditions).order_by(
            ShippingMethod.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, method: ShippingMethod) -> ShippingMethod:
        self._session.add(method)
        await self._session.flush()
        return method

    async def update(self, method: ShippingMethod) -> ShippingMethod:
        await self._session.flush()
        return method


class SqlShipmentRepository(ShipmentRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, shipment_id: str, tenant_id: str) -> Shipment | None:
        stmt = select(Shipment).where(
            Shipment.id == shipment_id,
            Shipment.tenant_id == tenant_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_shipment_no(self, shipment_no: str, tenant_id: str) -> Shipment | None:
        stmt = select(Shipment).where(
            Shipment.shipment_no == shipment_no,
            Shipment.tenant_id == tenant_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "", order_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Shipment], int]:
        conditions = [Shipment.tenant_id == tenant_id]
        if status:
            conditions.append(Shipment.status == status)
        if order_id:
            conditions.append(Shipment.order_id == order_id)
        total = (await self._session.execute(
            select(func.count()).select_from(Shipment).where(*conditions)
        )).scalar() or 0
        stmt = select(Shipment).where(*conditions).order_by(
            Shipment.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def list_by_status(self, tenant_id: str, status: str,
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Shipment], int]:
        return await self.list_by_tenant(tenant_id, status=status, page=page, page_size=page_size)

    async def create(self, shipment: Shipment) -> Shipment:
        self._session.add(shipment)
        await self._session.flush()
        return shipment

    async def update(self, shipment: Shipment) -> Shipment:
        await self._session.flush()
        return shipment


class SqlFreightTemplateRepository(FreightTemplateRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, template_id: str, tenant_id: str) -> FreightTemplate | None:
        stmt = select(FreightTemplate).where(
            FreightTemplate.id == template_id,
            FreightTemplate.tenant_id == tenant_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[FreightTemplate], int]:
        conditions = [FreightTemplate.tenant_id == tenant_id]
        if status:
            conditions.append(FreightTemplate.status == status)
        total = (await self._session.execute(
            select(func.count()).select_from(FreightTemplate).where(*conditions)
        )).scalar() or 0
        stmt = select(FreightTemplate).where(*conditions).order_by(
            FreightTemplate.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, template: FreightTemplate) -> FreightTemplate:
        self._session.add(template)
        await self._session.flush()
        return template

    async def update(self, template: FreightTemplate) -> FreightTemplate:
        await self._session.flush()
        return template


class SqlLogisticsStrategyRepository(LogisticsStrategyRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, strategy_id: str, tenant_id: str) -> LogisticsStrategy | None:
        stmt = select(LogisticsStrategy).where(
            LogisticsStrategy.id == strategy_id,
            LogisticsStrategy.tenant_id == tenant_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, tenant_id: str, strategy_code: str) -> LogisticsStrategy | None:
        stmt = select(LogisticsStrategy).where(
            LogisticsStrategy.tenant_id == tenant_id,
            LogisticsStrategy.strategy_code == strategy_code,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, strategy_type: str = "",
                             is_active: bool | None = None,
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[LogisticsStrategy], int]:
        conditions = [LogisticsStrategy.tenant_id == tenant_id]
        if strategy_type:
            conditions.append(LogisticsStrategy.strategy_type == strategy_type)
        if is_active is not None:
            conditions.append(LogisticsStrategy.is_active == is_active)
        total = (await self._session.execute(
            select(func.count()).select_from(LogisticsStrategy).where(*conditions)
        )).scalar() or 0
        stmt = select(LogisticsStrategy).where(*conditions).order_by(
            LogisticsStrategy.strategy_type, LogisticsStrategy.priority.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, strategy: LogisticsStrategy) -> LogisticsStrategy:
        self._session.add(strategy)
        await self._session.flush()
        return strategy

    async def update(self, strategy: LogisticsStrategy) -> LogisticsStrategy:
        await self._session.flush()
        return strategy


class SqlLogisticsStrategyExecutionLogRepository(LogisticsStrategyExecutionLogRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_tenant(self, tenant_id: str, strategy_type: str = "",
                             order_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[LogisticsStrategyExecutionLog], int]:
        conditions = [LogisticsStrategyExecutionLog.tenant_id == tenant_id]
        if strategy_type:
            conditions.append(LogisticsStrategyExecutionLog.strategy_type == strategy_type)
        if order_id:
            conditions.append(LogisticsStrategyExecutionLog.order_id == order_id)
        total = (await self._session.execute(
            select(func.count()).select_from(LogisticsStrategyExecutionLog).where(*conditions)
        )).scalar() or 0
        stmt = select(LogisticsStrategyExecutionLog).where(*conditions).order_by(
            LogisticsStrategyExecutionLog.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, log: LogisticsStrategyExecutionLog) -> LogisticsStrategyExecutionLog:
        self._session.add(log)
        await self._session.flush()
        return log


class SqlLogisticsConnectorRepository(LogisticsConnectorRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, connector_id: str, tenant_id: str) -> LogisticsConnector | None:
        stmt = select(LogisticsConnector).where(
            LogisticsConnector.id == connector_id,
            LogisticsConnector.tenant_id == tenant_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, tenant_id: str, code: str) -> LogisticsConnector | None:
        stmt = select(LogisticsConnector).where(
            LogisticsConnector.tenant_id == tenant_id,
            LogisticsConnector.connector_code == code,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, connector_type: str = "",
                             carrier_code: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[LogisticsConnector], int]:
        conditions = [LogisticsConnector.tenant_id == tenant_id]
        if connector_type:
            conditions.append(LogisticsConnector.connector_type == connector_type)
        if carrier_code:
            conditions.append(LogisticsConnector.carrier_code == carrier_code)
        total = (await self._session.execute(
            select(func.count()).select_from(LogisticsConnector).where(*conditions)
        )).scalar() or 0
        stmt = select(LogisticsConnector).where(*conditions).order_by(
            LogisticsConnector.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, connector: LogisticsConnector) -> LogisticsConnector:
        self._session.add(connector)
        await self._session.flush()
        return connector

    async def update(self, connector: LogisticsConnector) -> LogisticsConnector:
        await self._session.flush()
        return connector


class SqlShipmentLabelRepository(ShipmentLabelRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, label: ShipmentLabel) -> ShipmentLabel:
        self._session.add(label)
        await self._session.flush()
        return label


class SqlTrackingRecordRepository(TrackingRecordRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_tracking_number(self, tenant_id: str, tracking_number: str) -> TrackingRecord | None:
        stmt = select(TrackingRecord).where(
            TrackingRecord.tenant_id == tenant_id,
            TrackingRecord.tracking_number == tracking_number,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create(self, record: TrackingRecord) -> TrackingRecord:
        self._session.add(record)
        await self._session.flush()
        return record

    async def update(self, record: TrackingRecord) -> TrackingRecord:
        await self._session.flush()
        return record


class SqlFreightQuoteRepository(FreightQuoteRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, quote: FreightQuote) -> FreightQuote:
        self._session.add(quote)
        await self._session.flush()
        return quote


class SqlDispatchRecordRepository(DispatchRecordRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, dispatch_id: str, tenant_id: str) -> DispatchRecord | None:
        stmt = select(DispatchRecord).where(
            DispatchRecord.id == dispatch_id,
            DispatchRecord.tenant_id == tenant_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create(self, dispatch: DispatchRecord) -> DispatchRecord:
        self._session.add(dispatch)
        await self._session.flush()
        return dispatch

    async def update(self, dispatch: DispatchRecord) -> DispatchRecord:
        await self._session.flush()
        return dispatch


class SqlShippingBatchRepository(ShippingBatchRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, batch_id: str, tenant_id: str) -> ShippingBatch | None:
        stmt = select(ShippingBatch).where(
            ShippingBatch.id == batch_id,
            ShippingBatch.tenant_id == tenant_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_batch_no(self, batch_no: str, tenant_id: str) -> ShippingBatch | None:
        stmt = select(ShippingBatch).where(
            ShippingBatch.batch_no == batch_no,
            ShippingBatch.tenant_id == tenant_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "", carrier_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[ShippingBatch], int]:
        conditions = [ShippingBatch.tenant_id == tenant_id]
        if status:
            conditions.append(ShippingBatch.status == status)
        if carrier_id:
            conditions.append(ShippingBatch.carrier_id == carrier_id)
        total = (await self._session.execute(
            select(func.count()).select_from(ShippingBatch).where(*conditions)
        )).scalar() or 0
        stmt = select(ShippingBatch).where(*conditions).order_by(
            ShippingBatch.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, batch: ShippingBatch) -> ShippingBatch:
        self._session.add(batch)
        await self._session.flush()
        return batch

    async def update(self, batch: ShippingBatch) -> ShippingBatch:
        await self._session.flush()
        return batch
