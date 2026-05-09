from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.som.domain.models import AlertRecord, AlertRule, Listing, ListingBatchJob, ListingOptimization, OperationMonitor, PriceRule, Store
from erp.modules.som.domain.repositories import (
    AlertRecordRepository,
    AlertRuleRepository,
    ListingBatchJobRepository,
    ListingOptimizationRepository,
    ListingRepository,
    OperationMonitorRepository,
    PriceRuleRepository,
    StoreRepository,
)


class SqlStoreRepository(StoreRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, store_id: str, tenant_id: str) -> Store | None:
        stmt = select(Store).where(Store.id == store_id, Store.tenant_id == tenant_id, Store.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, code: str, tenant_id: str) -> Store | None:
        stmt = select(Store).where(Store.code == code, Store.tenant_id == tenant_id, Store.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, platform: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[Store], int]:
        conditions = [Store.tenant_id == tenant_id, Store.deleted_at.is_(None)]
        if platform:
            conditions.append(Store.platform == platform)
        total = (await self._session.execute(select(func.count()).select_from(Store).where(*conditions))).scalar() or 0
        stmt = select(Store).where(*conditions).order_by(Store.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, store: Store) -> Store:
        self._session.add(store)
        await self._session.flush()
        return store

    async def update(self, store: Store) -> Store:
        await self._session.flush()
        return store

    async def soft_delete(self, store_id: str, tenant_id: str) -> bool:
        stmt = update(Store).where(Store.id == store_id, Store.tenant_id == tenant_id).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlListingRepository(ListingRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, listing_id: str, tenant_id: str) -> Listing | None:
        stmt = select(Listing).where(Listing.id == listing_id, Listing.tenant_id == tenant_id, Listing.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, store_id: str = "", status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[Listing], int]:
        conditions = [Listing.tenant_id == tenant_id, Listing.deleted_at.is_(None)]
        if store_id:
            conditions.append(Listing.store_id == store_id)
        if status:
            conditions.append(Listing.status == status)
        total = (await self._session.execute(select(func.count()).select_from(Listing).where(*conditions))).scalar() or 0
        stmt = select(Listing).where(*conditions).order_by(Listing.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def list_by_store(self, store_id: str, tenant_id: str) -> Sequence[Listing]:
        stmt = select(Listing).where(Listing.store_id == store_id, Listing.tenant_id == tenant_id, Listing.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, listing: Listing) -> Listing:
        self._session.add(listing)
        await self._session.flush()
        return listing

    async def update(self, listing: Listing) -> Listing:
        await self._session.flush()
        return listing

    async def soft_delete(self, listing_id: str, tenant_id: str) -> bool:
        stmt = update(Listing).where(Listing.id == listing_id, Listing.tenant_id == tenant_id).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlPriceRuleRepository(PriceRuleRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, rule_id: str, tenant_id: str) -> PriceRule | None:
        stmt = select(PriceRule).where(PriceRule.id == rule_id, PriceRule.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_active(self, tenant_id: str, platform: str = "", region: str = "") -> PriceRule | None:
        conditions = [PriceRule.tenant_id == tenant_id, PriceRule.status == "active"]
        if platform:
            conditions.append(PriceRule.platform == platform)
        if region:
            conditions.append(PriceRule.region == region)
        stmt = select(PriceRule).where(*conditions).order_by(PriceRule.priority).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, platform: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[PriceRule], int]:
        conditions = [PriceRule.tenant_id == tenant_id]
        if platform:
            conditions.append(PriceRule.platform == platform)
        total = (await self._session.execute(select(func.count()).select_from(PriceRule).where(*conditions))).scalar() or 0
        stmt = select(PriceRule).where(*conditions).order_by(PriceRule.priority).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, rule: PriceRule) -> PriceRule:
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def update(self, rule: PriceRule) -> PriceRule:
        await self._session.flush()
        return rule


class SqlListingBatchJobRepository(ListingBatchJobRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, job_id: str, tenant_id: str) -> ListingBatchJob | None:
        stmt = select(ListingBatchJob).where(ListingBatchJob.id == job_id, ListingBatchJob.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[ListingBatchJob], int]:
        conditions = [ListingBatchJob.tenant_id == tenant_id]
        if status:
            conditions.append(ListingBatchJob.status == status)
        total = (await self._session.execute(select(func.count()).select_from(ListingBatchJob).where(*conditions))).scalar() or 0
        stmt = select(ListingBatchJob).where(*conditions).order_by(ListingBatchJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, job: ListingBatchJob) -> ListingBatchJob:
        self._session.add(job)
        await self._session.flush()
        return job

    async def update(self, job: ListingBatchJob) -> ListingBatchJob:
        await self._session.flush()
        return job


class SqlOperationMonitorRepository(OperationMonitorRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_tenant(self, tenant_id: str, store_id: str = "", metric_type: str = "",
                             start_date: datetime | None = None, end_date: datetime | None = None,
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[OperationMonitor], int]:
        conditions = [OperationMonitor.tenant_id == tenant_id]
        if store_id:
            conditions.append(OperationMonitor.store_id == store_id)
        if metric_type:
            conditions.append(OperationMonitor.metric_type == metric_type)
        if start_date:
            conditions.append(OperationMonitor.metric_date >= start_date)
        if end_date:
            conditions.append(OperationMonitor.metric_date <= end_date)
        total = (await self._session.execute(select(func.count()).select_from(OperationMonitor).where(*conditions))).scalar() or 0
        stmt = select(OperationMonitor).where(*conditions).order_by(OperationMonitor.metric_date.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, monitor: OperationMonitor) -> OperationMonitor:
        self._session.add(monitor)
        await self._session.flush()
        return monitor


class SqlListingOptimizationRepository(ListingOptimizationRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, optimization_id: str, tenant_id: str) -> ListingOptimization | None:
        stmt = select(ListingOptimization).where(
            ListingOptimization.id == optimization_id, ListingOptimization.tenant_id == tenant_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_listing(self, listing_id: str, tenant_id: str) -> Sequence[ListingOptimization]:
        stmt = select(ListingOptimization).where(
            ListingOptimization.listing_id == listing_id, ListingOptimization.tenant_id == tenant_id
        ).order_by(ListingOptimization.created_at.desc())
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_tenant(self, tenant_id: str, listing_id: str = "", opt_type: str = "",
                             status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[ListingOptimization], int]:
        conditions = [ListingOptimization.tenant_id == tenant_id]
        if listing_id:
            conditions.append(ListingOptimization.listing_id == listing_id)
        if opt_type:
            conditions.append(ListingOptimization.opt_type == opt_type)
        if status:
            conditions.append(ListingOptimization.status == status)
        total = (await self._session.execute(select(func.count()).select_from(ListingOptimization).where(*conditions))).scalar() or 0
        stmt = select(ListingOptimization).where(*conditions).order_by(
            ListingOptimization.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, optimization: ListingOptimization) -> ListingOptimization:
        self._session.add(optimization)
        await self._session.flush()
        return optimization

    async def update(self, optimization: ListingOptimization) -> ListingOptimization:
        await self._session.flush()
        return optimization


class SqlAlertRuleRepository(AlertRuleRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, rule_id: str, tenant_id: str) -> AlertRule | None:
        stmt = select(AlertRule).where(AlertRule.id == rule_id, AlertRule.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, metric_type: str = "", severity: str = "",
                             status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[AlertRule], int]:
        conditions = [AlertRule.tenant_id == tenant_id]
        if metric_type:
            conditions.append(AlertRule.metric_type == metric_type)
        if severity:
            conditions.append(AlertRule.severity == severity)
        if status:
            conditions.append(AlertRule.status == status)
        total = (await self._session.execute(select(func.count()).select_from(AlertRule).where(*conditions))).scalar() or 0
        stmt = select(AlertRule).where(*conditions).order_by(AlertRule.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def find_active_by_metric(self, tenant_id: str, metric_type: str, store_id: str = "") -> Sequence[AlertRule]:
        conditions = [AlertRule.tenant_id == tenant_id, AlertRule.metric_type == metric_type, AlertRule.status == "active"]
        if store_id:
            conditions.append((AlertRule.store_id == store_id) | (AlertRule.store_id == ""))
        stmt = select(AlertRule).where(*conditions)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, rule: AlertRule) -> AlertRule:
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def update(self, rule: AlertRule) -> AlertRule:
        await self._session.flush()
        return rule


class SqlAlertRecordRepository(AlertRecordRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, record_id: str, tenant_id: str) -> AlertRecord | None:
        stmt = select(AlertRecord).where(AlertRecord.id == record_id, AlertRecord.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, rule_id: str = "", severity: str = "",
                             status: str = "", store_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[AlertRecord], int]:
        conditions = [AlertRecord.tenant_id == tenant_id]
        if rule_id:
            conditions.append(AlertRecord.rule_id == rule_id)
        if severity:
            conditions.append(AlertRecord.severity == severity)
        if status:
            conditions.append(AlertRecord.status == status)
        if store_id:
            conditions.append(AlertRecord.store_id == store_id)
        total = (await self._session.execute(select(func.count()).select_from(AlertRecord).where(*conditions))).scalar() or 0
        stmt = select(AlertRecord).where(*conditions).order_by(
            AlertRecord.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def find_recent_by_rule(self, rule_id: str, tenant_id: str, hours: int = 24) -> Sequence[AlertRecord]:
        from datetime import timedelta
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        stmt = select(AlertRecord).where(
            AlertRecord.rule_id == rule_id,
            AlertRecord.tenant_id == tenant_id,
            AlertRecord.created_at >= cutoff,
        ).order_by(AlertRecord.created_at.desc())
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, record: AlertRecord) -> AlertRecord:
        self._session.add(record)
        await self._session.flush()
        return record

    async def update(self, record: AlertRecord) -> AlertRecord:
        await self._session.flush()
        return record
