from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.ads.domain.models import AdCampaign, AdGroup, AdKeyword, AdReport
from erp.modules.ads.domain.repositories import (
    AdCampaignRepository,
    AdGroupRepository,
    AdKeywordRepository,
    AdReportRepository,
)


class SqlAdCampaignRepository(AdCampaignRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, campaign_id: str, tenant_id: str) -> AdCampaign | None:
        stmt = select(AdCampaign).where(AdCampaign.id == campaign_id, AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_campaign_no(self, campaign_no: str, tenant_id: str) -> AdCampaign | None:
        stmt = select(AdCampaign).where(AdCampaign.campaign_no == campaign_no, AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "", platform: str = "", store_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[AdCampaign], int]:
        conditions = [AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None)]
        if status:
            conditions.append(AdCampaign.status == status)
        if platform:
            conditions.append(AdCampaign.platform == platform)
        if store_id:
            conditions.append(AdCampaign.store_id == store_id)
        total = (await self._session.execute(select(func.count()).select_from(AdCampaign).where(*conditions))).scalar() or 0
        stmt = select(AdCampaign).where(*conditions).order_by(AdCampaign.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, campaign: AdCampaign) -> AdCampaign:
        self._session.add(campaign)
        await self._session.flush()
        return campaign

    async def update(self, campaign: AdCampaign) -> AdCampaign:
        await self._session.flush()
        return campaign

    async def soft_delete(self, campaign_id: str, tenant_id: str) -> bool:
        stmt = update(AdCampaign).where(AdCampaign.id == campaign_id, AdCampaign.tenant_id == tenant_id).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlAdGroupRepository(AdGroupRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, group_id: str, tenant_id: str) -> AdGroup | None:
        stmt = select(AdGroup).where(AdGroup.id == group_id, AdGroup.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_campaign(self, campaign_id: str, tenant_id: str) -> Sequence[AdGroup]:
        stmt = select(AdGroup).where(AdGroup.campaign_id == campaign_id, AdGroup.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, group: AdGroup) -> AdGroup:
        self._session.add(group)
        await self._session.flush()
        return group

    async def update(self, group: AdGroup) -> AdGroup:
        await self._session.flush()
        return group


class SqlAdKeywordRepository(AdKeywordRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, keyword_id: str, tenant_id: str) -> AdKeyword | None:
        stmt = select(AdKeyword).where(AdKeyword.id == keyword_id, AdKeyword.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_ad_group(self, ad_group_id: str, tenant_id: str) -> Sequence[AdKeyword]:
        stmt = select(AdKeyword).where(AdKeyword.ad_group_id == ad_group_id, AdKeyword.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_campaign(self, campaign_id: str, tenant_id: str) -> Sequence[AdKeyword]:
        stmt = select(AdKeyword).where(AdKeyword.campaign_id == campaign_id, AdKeyword.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, keyword: AdKeyword) -> AdKeyword:
        self._session.add(keyword)
        await self._session.flush()
        return keyword

    async def update(self, keyword: AdKeyword) -> AdKeyword:
        await self._session.flush()
        return keyword


class SqlAdReportRepository(AdReportRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_campaign(self, campaign_id: str, tenant_id: str,
                               start_date=None, end_date=None) -> Sequence[AdReport]:
        conditions = [AdReport.campaign_id == campaign_id, AdReport.tenant_id == tenant_id]
        if start_date:
            conditions.append(AdReport.report_date >= start_date)
        if end_date:
            conditions.append(AdReport.report_date <= end_date)
        stmt = select(AdReport).where(*conditions).order_by(AdReport.report_date.desc())
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_tenant(self, tenant_id: str, store_id: str = "", platform: str = "",
                             start_date=None, end_date=None,
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[AdReport], int]:
        conditions = [AdReport.tenant_id == tenant_id]
        if store_id:
            conditions.append(AdReport.store_id == store_id)
        if platform:
            conditions.append(AdReport.platform == platform)
        if start_date:
            conditions.append(AdReport.report_date >= start_date)
        if end_date:
            conditions.append(AdReport.report_date <= end_date)
        total = (await self._session.execute(select(func.count()).select_from(AdReport).where(*conditions))).scalar() or 0
        stmt = select(AdReport).where(*conditions).order_by(AdReport.report_date.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, report: AdReport) -> AdReport:
        self._session.add(report)
        await self._session.flush()
        return report
