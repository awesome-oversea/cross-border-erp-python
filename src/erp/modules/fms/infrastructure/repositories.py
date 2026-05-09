from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.fms.domain.models import CostEvent, ExchangeRate, PaymentRecord, PlatformSettlement
from erp.modules.fms.domain.repositories import (
    CostEventRepository,
    ExchangeRateRepository,
    PaymentRecordRepository,
    PlatformSettlementRepository,
)


class SqlCostEventRepository(CostEventRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, event_id: str, tenant_id: str) -> CostEvent | None:
        stmt = select(CostEvent).where(CostEvent.id == event_id, CostEvent.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_event_no(self, event_no: str, tenant_id: str) -> CostEvent | None:
        stmt = select(CostEvent).where(CostEvent.event_no == event_no, CostEvent.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, cost_type: str = "", sku_id: str = "",
                             start_date: datetime | None = None, end_date: datetime | None = None,
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[CostEvent], int]:
        conditions = [CostEvent.tenant_id == tenant_id]
        if cost_type:
            conditions.append(CostEvent.cost_type == cost_type)
        if sku_id:
            conditions.append(CostEvent.sku_id == sku_id)
        if start_date:
            conditions.append(CostEvent.occurred_date >= start_date)
        if end_date:
            conditions.append(CostEvent.occurred_date <= end_date)
        total = (await self._session.execute(select(func.count()).select_from(CostEvent).where(*conditions))).scalar() or 0
        stmt = select(CostEvent).where(*conditions).order_by(CostEvent.occurred_date.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, event: CostEvent) -> CostEvent:
        self._session.add(event)
        await self._session.flush()
        return event

    async def update(self, event: CostEvent) -> CostEvent:
        await self._session.flush()
        return event


class SqlPlatformSettlementRepository(PlatformSettlementRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, settlement_id: str, tenant_id: str) -> PlatformSettlement | None:
        stmt = select(PlatformSettlement).where(PlatformSettlement.id == settlement_id, PlatformSettlement.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_settlement_no(self, settlement_no: str, tenant_id: str) -> PlatformSettlement | None:
        stmt = select(PlatformSettlement).where(PlatformSettlement.settlement_no == settlement_no, PlatformSettlement.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, platform: str = "", store_id: str = "",
                             status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[PlatformSettlement], int]:
        conditions = [PlatformSettlement.tenant_id == tenant_id]
        if platform:
            conditions.append(PlatformSettlement.platform == platform)
        if store_id:
            conditions.append(PlatformSettlement.store_id == store_id)
        if status:
            conditions.append(PlatformSettlement.status == status)
        total = (await self._session.execute(select(func.count()).select_from(PlatformSettlement).where(*conditions))).scalar() or 0
        stmt = select(PlatformSettlement).where(*conditions).order_by(PlatformSettlement.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, settlement: PlatformSettlement) -> PlatformSettlement:
        self._session.add(settlement)
        await self._session.flush()
        return settlement

    async def update(self, settlement: PlatformSettlement) -> PlatformSettlement:
        await self._session.flush()
        return settlement


class SqlPaymentRecordRepository(PaymentRecordRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, payment_id: str, tenant_id: str) -> PaymentRecord | None:
        stmt = select(PaymentRecord).where(PaymentRecord.id == payment_id, PaymentRecord.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_payment_no(self, payment_no: str, tenant_id: str) -> PaymentRecord | None:
        stmt = select(PaymentRecord).where(PaymentRecord.payment_no == payment_no, PaymentRecord.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, payment_type: str = "", status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[PaymentRecord], int]:
        conditions = [PaymentRecord.tenant_id == tenant_id]
        if payment_type:
            conditions.append(PaymentRecord.payment_type == payment_type)
        if status:
            conditions.append(PaymentRecord.status == status)
        total = (await self._session.execute(select(func.count()).select_from(PaymentRecord).where(*conditions))).scalar() or 0
        stmt = select(PaymentRecord).where(*conditions).order_by(PaymentRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, payment: PaymentRecord) -> PaymentRecord:
        self._session.add(payment)
        await self._session.flush()
        return payment

    async def update(self, payment: PaymentRecord) -> PaymentRecord:
        await self._session.flush()
        return payment


class SqlExchangeRateRepository(ExchangeRateRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_latest(self, from_currency: str, to_currency: str, tenant_id: str) -> ExchangeRate | None:
        stmt = select(ExchangeRate).where(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.tenant_id == tenant_id,
        ).order_by(ExchangeRate.rate_date.desc()).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, rate_date: datetime | None = None) -> Sequence[ExchangeRate]:
        conditions = [ExchangeRate.tenant_id == tenant_id]
        if rate_date:
            conditions.append(ExchangeRate.rate_date == rate_date)
        stmt = select(ExchangeRate).where(*conditions).order_by(ExchangeRate.rate_date.desc())
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, rate: ExchangeRate) -> ExchangeRate:
        self._session.add(rate)
        await self._session.flush()
        return rate
