"""
ADS (广告管理域) 应用服务层

职责: 编排广告活动/广告组/关键词/报表/策略/分析的完整业务流程

核心服务:
  - AdCampaignService: 广告活动管理，创建/暂停/预算/竞价
  - AdGroupService: 广告组管理，活动下的广告组配置
  - AdKeywordService: 广告关键词管理，关键词竞价与匹配类型
  - AdReportService: 广告报表管理，多维度数据导出
  - AdStrategyService: 广告策略管理，自动竞价/预算优化规则
  - AdPerformanceAnalysisService: 广告效果分析，ROI/ACOS/转化率分析
  - ADSQueryService: 统一查询服务，跨实体聚合查询
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func as sa_func
from sqlalchemy import select

from erp.modules.ads.domain.models import AdCampaign, AdGroup, AdKeyword, AdReport
from erp.modules.ads.domain.repositories import (
    AdCampaignRepository,
    AdGroupRepository,
    AdKeywordRepository,
    AdReportRepository,
)
from erp.modules.ads.domain.services import AdGroupDomainService, AdKeywordDomainService, AdPerformanceDomainService
from erp.shared.context import actor_id_var
from erp.shared.exceptions import DuplicateCodeException, NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.ads")

CAMPAIGN_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["pending", "cancelled"],
    "pending": ["active", "rejected", "cancelled"],
    "active": ["paused", "completed", "cancelled"],
    "paused": ["active", "completed", "cancelled"],
    "completed": [],
    "rejected": ["draft"],
    "cancelled": [],
}

CAMPAIGN_TYPES = {"sponsored_products", "sponsored_brands", "sponsored_display", "video"}
TARGETING_TYPES = {"manual", "auto"}
MATCH_TYPES = {"broad", "phrase", "exact"}

MIN_DAILY_BUDGET = 1.0
MIN_KEYWORD_BID = 0.02
MAX_KEYWORD_BID = 1000.0


class AdCampaignService:
    """
    广告活动应用服务

    通过 AdCampaignRepository 仓储接口操作数据。
    管理广告活动的创建、状态变更、预算调整、效果指标更新等。
    """

    def __init__(self, session: AsyncSession, repo: AdCampaignRepository | None = None):
        self._session = session
        self._repo = repo

    async def create(self, tenant_id: str, campaign_no: str, name: str, platform: str,
                     store_id: str, campaign_type: str = "sponsored_products",
                     targeting_type: str = "manual", daily_budget: float = 0.0,
                     currency: str = "USD", **kwargs) -> AdCampaign:
        """创建广告活动: 类型校验 → 唯一性校验 → 持久化"""
        if campaign_type not in CAMPAIGN_TYPES:
            raise ValidationException(
                message=f"Invalid campaign type '{campaign_type}', allowed: {', '.join(sorted(CAMPAIGN_TYPES))}"
            )
        if targeting_type not in TARGETING_TYPES:
            raise ValidationException(
                message=f"Invalid targeting type '{targeting_type}', allowed: {', '.join(sorted(TARGETING_TYPES))}"
            )
        if self._repo:
            existing = await self._repo.get_by_campaign_no(campaign_no, tenant_id)
        else:
            stmt = select(AdCampaign).where(
                AdCampaign.campaign_no == campaign_no, AdCampaign.tenant_id == tenant_id
            )
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Campaign no '{campaign_no}' already exists")
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise ValidationException(message="End date must be after start date")
        campaign = AdCampaign(
            tenant_id=tenant_id, campaign_no=campaign_no, name=name,
            platform=platform, store_id=store_id, campaign_type=campaign_type,
            targeting_type=targeting_type, daily_budget=daily_budget, currency=currency,
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(AdCampaign, k)},
        )
        if self._repo:
            return await self._repo.create(campaign)
        self._session.add(campaign)
        await self._session.flush()
        return campaign

    async def get_by_id(self, campaign_id: str, tenant_id: str = "") -> AdCampaign | None:
        stmt = select(AdCampaign).where(AdCampaign.id == campaign_id, AdCampaign.deleted_at.is_(None))
        if tenant_id:
            stmt = stmt.where(AdCampaign.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, campaign_id: str, tenant_id: str = "") -> AdCampaign:
        campaign = await self.get_by_id(campaign_id, tenant_id)
        if not campaign:
            raise NotFoundException(message=f"Campaign '{campaign_id}' not found")
        return campaign

    async def list_by_tenant(self, tenant_id: str, status: str | None = None,
                             platform: str | None = None, offset: int = 0, limit: int = 20) -> list[AdCampaign]:
        stmt = select(AdCampaign).where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
        if status:
            stmt = stmt.where(AdCampaign.status == status)
        if platform:
            stmt = stmt.where(AdCampaign.platform == platform)
        stmt = stmt.order_by(AdCampaign.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, campaign_id: str, tenant_id: str, new_status: str) -> AdCampaign:
        campaign = await self.get_by_id(campaign_id, tenant_id)
        if not campaign:
            raise NotFoundException(message=f"Campaign '{campaign_id}' not found")
        allowed = CAMPAIGN_STATUS_TRANSITIONS.get(campaign.status, [])
        if new_status not in allowed:
            raise ValidationException(
                message=f"Cannot transition campaign from '{campaign.status}' to '{new_status}'"
            )
        if new_status == "active" and campaign.daily_budget < MIN_DAILY_BUDGET:
            raise ValidationException(
                message=f"Cannot activate campaign: daily_budget must be at least {MIN_DAILY_BUDGET}"
            )
        if new_status == "active" and not campaign.start_date:
            campaign.start_date = datetime.now(UTC)
        campaign.status = new_status
        await self._session.flush()
        return campaign

    async def update_budget(self, campaign_id: str, tenant_id: str, daily_budget: float) -> AdCampaign:
        campaign = await self.get_by_id(campaign_id, tenant_id)
        if not campaign:
            raise NotFoundException(message=f"Campaign '{campaign_id}' not found")
        if daily_budget < MIN_DAILY_BUDGET:
            raise ValidationException(
                message=f"Daily budget must be at least {MIN_DAILY_BUDGET}"
            )
        campaign.daily_budget = daily_budget
        await self._session.flush()
        return campaign

    async def update_metrics(self, campaign_id: str, spend: float = 0, sales: float = 0,
                             impressions: int = 0, clicks: int = 0, orders: int = 0) -> AdCampaign | None:
        campaign = await self.get_by_id(campaign_id)
        if not campaign:
            return None
        campaign.total_spend = spend
        campaign.total_sales = sales
        campaign.total_impressions = impressions
        campaign.total_clicks = clicks
        campaign.total_orders = orders
        if spend > 0 and sales > 0:
            campaign.acos = round(spend / sales * 100, 2)
            campaign.roas = round(sales / spend, 2)
        elif spend > 0 and sales == 0:
            campaign.acos = 999.99
            campaign.roas = 0.0
        if impressions > 0:
            campaign.ctr = round(clicks / impressions * 100, 4)
        await self._session.flush()
        return campaign

    async def get_performance_summary(self, tenant_id: str, platform: str | None = None) -> dict:
        stmt = select(
            sa_func.count(AdCampaign.id),
            sa_func.sum(AdCampaign.total_spend),
            sa_func.sum(AdCampaign.total_sales),
            sa_func.sum(AdCampaign.total_impressions),
            sa_func.sum(AdCampaign.total_clicks),
            sa_func.sum(AdCampaign.total_orders),
        ).where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
        if platform:
            stmt = stmt.where(AdCampaign.platform == platform)
        result = await self._session.execute(stmt)
        row = result.one()
        total_spend = float(row[1] or 0)
        total_sales = float(row[2] or 0)
        total_impressions = int(row[3] or 0)
        total_clicks = int(row[4] or 0)
        total_orders = int(row[5] or 0)
        return {
            "total_campaigns": int(row[0] or 0),
            "total_spend": round(total_spend, 2),
            "total_sales": round(total_sales, 2),
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_orders": total_orders,
            "overall_acos": round(total_spend / total_sales * 100, 2) if total_sales > 0 else 0,
            "overall_roas": round(total_sales / total_spend, 2) if total_spend > 0 else 0,
            "overall_ctr": round(total_clicks / total_impressions * 100, 4) if total_impressions > 0 else 0,
        }

    async def list_paginated(self, tenant_id: str, status: str = "", platform: str = "",
                              campaign_type: str = "", store_id: str = "",
                              keyword: str = "",
                              min_budget: float | None = None, max_budget: float | None = None,
                              page: int = 1, page_size: int = 20) -> tuple[list[AdCampaign], int]:
        """分页查询广告活动列表 (含总数)"""
        conditions = [AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None)]
        if status:
            conditions.append(AdCampaign.status == status)
        if platform:
            conditions.append(AdCampaign.platform == platform)
        if campaign_type:
            conditions.append(AdCampaign.campaign_type == campaign_type)
        if store_id:
            conditions.append(AdCampaign.store_id == store_id)
        if keyword:
            conditions.append((AdCampaign.campaign_no.contains(keyword) | AdCampaign.name.contains(keyword)))
        if min_budget is not None:
            conditions.append(AdCampaign.daily_budget >= min_budget)
        if max_budget is not None:
            conditions.append(AdCampaign.daily_budget <= max_budget)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(AdCampaign).where(*conditions)
        )).scalar() or 0
        stmt = select(AdCampaign).where(*conditions).order_by(
            AdCampaign.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total

    async def search(self, tenant_id: str, keyword: str = "", platform: str = "",
                     status: str = "", campaign_type: str = "", store_id: str = "",
                     min_budget: float | None = None, max_budget: float | None = None,
                     start_date=None, end_date=None,
                     page: int = 1, page_size: int = 20) -> tuple[list[AdCampaign], int]:
        """多维度搜索广告活动"""
        conditions = [AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None)]
        if keyword:
            conditions.append((AdCampaign.campaign_no.contains(keyword) | AdCampaign.name.contains(keyword)))
        if platform:
            conditions.append(AdCampaign.platform == platform)
        if status:
            conditions.append(AdCampaign.status == status)
        if campaign_type:
            conditions.append(AdCampaign.campaign_type == campaign_type)
        if store_id:
            conditions.append(AdCampaign.store_id == store_id)
        if min_budget is not None:
            conditions.append(AdCampaign.daily_budget >= min_budget)
        if max_budget is not None:
            conditions.append(AdCampaign.daily_budget <= max_budget)
        if start_date:
            conditions.append(AdCampaign.start_date >= start_date)
        if end_date:
            conditions.append(AdCampaign.end_date <= end_date)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(AdCampaign).where(*conditions)
        )).scalar() or 0
        stmt = select(AdCampaign).where(*conditions).order_by(
            AdCampaign.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total

    async def batch_update_status(self, tenant_id: str, campaign_ids: list[str], status: str) -> list[AdCampaign]:
        """批量更新广告活动状态"""
        results = []
        for cid in campaign_ids:
            campaign = await self.update_status(cid, tenant_id, status)
            results.append(campaign)
        return results

    async def update(self, campaign_id: str, tenant_id: str, **kwargs) -> AdCampaign:
        """更新广告活动信息"""
        campaign = await self.get_by_id(campaign_id, tenant_id)
        if not campaign:
            raise NotFoundException(message=f"Campaign '{campaign_id}' not found")
        if campaign.status not in ("draft", "paused"):
            raise ValidationException(message=f"Cannot update campaign in '{campaign.status}' status")
        for k, v in kwargs.items():
            if v is not None and hasattr(campaign, k):
                setattr(campaign, k, v)
        await self._session.flush()
        return campaign

    async def soft_delete(self, campaign_id: str, tenant_id: str) -> bool:
        """软删除广告活动"""
        campaign = await self.get_by_id(campaign_id, tenant_id)
        if not campaign:
            raise NotFoundException(message=f"Campaign '{campaign_id}' not found")
        if campaign.status not in ("draft", "paused", "ended"):
            raise ValidationException(message=f"Cannot delete campaign in '{campaign.status}' status")
        campaign.deleted_at = datetime.now(UTC)
        campaign.status = "deleted"
        await self._session.flush()
        return True


class AdGroupService:
    """
    广告组应用服务

    通过 AdGroupRepository 仓储接口操作数据。
    管理广告组的创建、更新、状态变更、效果汇总等。
    """

    def __init__(self, session: AsyncSession, repo: AdGroupRepository | None = None):
        self._session = session
        self._repo = repo

    async def create(self, tenant_id: str, campaign_id: str, name: str,
                     default_bid: float = 0.0, **kwargs) -> AdGroup:
        campaign = await self._session.get(AdCampaign, campaign_id)
        if not campaign or campaign.deleted_at:
            raise NotFoundException(message=f"Campaign '{campaign_id}' not found")
        if default_bid < 0:
            raise ValidationException(message="Default bid cannot be negative")
        group = AdGroup(
            tenant_id=tenant_id, campaign_id=campaign_id, name=name,
            default_bid=default_bid,
            **{k: v for k, v in kwargs.items() if hasattr(AdGroup, k)},
        )
        self._session.add(group)
        await self._session.flush()
        return group

    async def list_by_campaign(self, campaign_id: str) -> list[AdGroup]:
        stmt = select(AdGroup).where(AdGroup.campaign_id == campaign_id).order_by(AdGroup.created_at)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, group_id: str, tenant_id: str = "") -> AdGroup | None:
        stmt = select(AdGroup).where(AdGroup.id == group_id)
        if tenant_id:
            stmt = stmt.where(AdGroup.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, group_id: str, tenant_id: str = "") -> AdGroup:
        group = await self.get_by_id(group_id, tenant_id)
        if not group:
            raise NotFoundException(message=f"Ad group '{group_id}' not found")
        return group

    async def update(self, group_id: str, tenant_id: str, **kwargs) -> AdGroup:
        group = await self.get_by_id(group_id, tenant_id)
        if not group:
            raise NotFoundException(message=f"Ad group '{group_id}' not found")
        if "name" in kwargs:
            if not kwargs["name"] or not kwargs["name"].strip():
                raise ValidationException(message="Ad group name cannot be empty")
            group.name = kwargs["name"]
        if "default_bid" in kwargs:
            if kwargs["default_bid"] < 0:
                raise ValidationException(message="Default bid cannot be negative")
            group.default_bid = kwargs["default_bid"]
        if "status" in kwargs:
            new_status = kwargs["status"]
            if not AdGroupDomainService.can_transition(group.status, new_status):
                raise ValidationException(
                    message=f"Cannot transition ad group from '{group.status}' to '{new_status}'"
                )
            group.status = new_status
        await self._session.flush()
        return group

    async def get_group_performance(self, group_id: str, tenant_id: str) -> dict:
        group = await self.get_by_id(group_id, tenant_id)
        if not group:
            raise NotFoundException(message=f"Ad group '{group_id}' not found")
        stmt = select(AdKeyword).where(AdKeyword.ad_group_id == group_id)
        keywords = (await self._session.execute(stmt)).scalars().all()
        kw_data = [
            {"impressions": kw.impressions, "clicks": kw.clicks, "spend": kw.spend,
             "sales": kw.sales, "orders": kw.orders}
            for kw in keywords
        ]
        return AdGroupDomainService.calculate_group_performance(kw_data)


class AdKeywordService:
    """
    广告关键词应用服务

    通过 AdKeywordRepository 仓储接口操作数据。
    管理关键词的创建、出价调整、状态变更、效果指标更新等。
    """

    def __init__(self, session: AsyncSession, repo: AdKeywordRepository | None = None):
        self._session = session
        self._repo = repo

    async def create(self, tenant_id: str, campaign_id: str, ad_group_id: str,
                     keyword_text: str, match_type: str = "broad",
                     bid: float = 0.0, **kwargs) -> AdKeyword:
        if match_type not in MATCH_TYPES:
            raise ValidationException(
                message=f"Invalid match type '{match_type}', allowed: {', '.join(sorted(MATCH_TYPES))}"
            )
        if not keyword_text.strip():
            raise ValidationException(message="Keyword text cannot be empty")
        if bid < MIN_KEYWORD_BID:
            raise ValidationException(
                message=f"Keyword bid must be at least {MIN_KEYWORD_BID}"
            )
        if bid > MAX_KEYWORD_BID:
            raise ValidationException(
                message=f"Keyword bid cannot exceed {MAX_KEYWORD_BID}"
            )
        kw = AdKeyword(
            tenant_id=tenant_id, campaign_id=campaign_id, ad_group_id=ad_group_id,
            keyword_text=keyword_text.strip(), match_type=match_type, bid=bid,
            **{k: v for k, v in kwargs.items() if hasattr(AdKeyword, k)},
        )
        self._session.add(kw)
        await self._session.flush()
        return kw

    async def list_by_ad_group(self, ad_group_id: str) -> list[AdKeyword]:
        stmt = select(AdKeyword).where(AdKeyword.ad_group_id == ad_group_id).order_by(AdKeyword.created_at)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_bid(self, keyword_id: str, new_bid: float) -> AdKeyword:
        kw = await self._session.get(AdKeyword, keyword_id)
        if not kw:
            raise NotFoundException(message=f"Keyword '{keyword_id}' not found")
        if new_bid < MIN_KEYWORD_BID:
            raise ValidationException(message=f"Keyword bid must be at least {MIN_KEYWORD_BID}")
        if new_bid > MAX_KEYWORD_BID:
            raise ValidationException(message=f"Keyword bid cannot exceed {MAX_KEYWORD_BID}")
        kw.bid = new_bid
        await self._session.flush()
        return kw

    async def update_status(self, keyword_id: str, new_status: str) -> AdKeyword:
        kw = await self._session.get(AdKeyword, keyword_id)
        if not kw:
            raise NotFoundException(message=f"Keyword '{keyword_id}' not found")
        if new_status not in ("enabled", "paused", "archived"):
            raise ValidationException(message="Keyword status must be 'enabled', 'paused' or 'archived'")
        kw.status = new_status
        await self._session.flush()
        return kw

    async def get_by_id(self, keyword_id: str, tenant_id: str = "") -> AdKeyword | None:
        stmt = select(AdKeyword).where(AdKeyword.id == keyword_id)
        if tenant_id:
            stmt = stmt.where(AdKeyword.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, keyword_id: str, tenant_id: str = "") -> AdKeyword:
        keyword = await self.get_by_id(keyword_id, tenant_id)
        if not keyword:
            raise NotFoundException(message=f"Keyword '{keyword_id}' not found")
        return keyword

    async def list_by_tenant(self, tenant_id: str, campaign_id: str = "",
                              status: str = "", offset: int = 0, limit: int = 100) -> list[AdKeyword]:
        stmt = select(AdKeyword).where(AdKeyword.tenant_id == tenant_id)
        if campaign_id:
            stmt = stmt.where(AdKeyword.campaign_id == campaign_id)
        if status:
            stmt = stmt.where(AdKeyword.status == status)
        stmt = stmt.order_by(AdKeyword.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_metrics(self, keyword_id: str, impressions: int = 0, clicks: int = 0,
                              spend: float = 0.0, sales: float = 0.0, orders: int = 0) -> AdKeyword | None:
        kw = await self._session.get(AdKeyword, keyword_id)
        if not kw:
            return None
        kw.impressions = impressions
        kw.clicks = clicks
        kw.spend = spend
        kw.sales = sales
        kw.orders = orders
        kw.ctr = AdPerformanceDomainService.calculate_ctr(impressions, clicks) if impressions > 0 else 0.0
        kw.cpc = AdPerformanceDomainService.calculate_cpc(spend, clicks) if clicks > 0 else 0.0
        kw.conversion_rate = AdPerformanceDomainService.calculate_conversion_rate(orders, clicks) if clicks > 0 else 0.0
        await self._session.flush()
        return kw

    async def batch_update_bids(self, tenant_id: str, bid_updates: list[dict]) -> dict:
        success_count = 0
        failed_items = []
        for item in bid_updates:
            keyword_id = item.get("keyword_id", "")
            new_bid = item.get("bid", 0)
            try:
                await self.update_bid(keyword_id, new_bid)
                success_count += 1
            except (NotFoundException, ValidationException) as e:
                failed_items.append({"keyword_id": keyword_id, "reason": e.message})
        return {"success_count": success_count, "failed_count": len(failed_items), "failed_items": failed_items}

    async def search(self, tenant_id: str, keyword_text: str = "", campaign_id: str = "",
                     ad_group_id: str = "", match_type: str = "", status: str = "",
                     min_bid: float | None = None, max_bid: float | None = None,
                     page: int = 1, page_size: int = 20) -> tuple[list[AdKeyword], int]:
        """多维度搜索关键词"""
        conditions = [AdKeyword.tenant_id == tenant_id]
        if keyword_text:
            conditions.append(AdKeyword.keyword_text.contains(keyword_text))
        if campaign_id:
            conditions.append(AdKeyword.campaign_id == campaign_id)
        if ad_group_id:
            conditions.append(AdKeyword.ad_group_id == ad_group_id)
        if match_type:
            conditions.append(AdKeyword.match_type == match_type)
        if status:
            conditions.append(AdKeyword.status == status)
        if min_bid is not None:
            conditions.append(AdKeyword.bid >= min_bid)
        if max_bid is not None:
            conditions.append(AdKeyword.bid <= max_bid)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(AdKeyword).where(*conditions)
        )).scalar() or 0
        stmt = select(AdKeyword).where(*conditions).order_by(
            AdKeyword.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total


class AdReportService:
    """
    广告报表应用服务

    通过 AdReportRepository 仓储接口操作数据。
    管理广告效果报表的创建、查询、汇总等。
    """

    def __init__(self, session: AsyncSession, repo: AdReportRepository | None = None):
        self._session = session
        self._repo = repo

    async def create(self, tenant_id: str, campaign_id: str, report_date: datetime,
                     granularity: str = "daily", **kwargs) -> AdReport:
        if granularity not in ("daily", "weekly", "monthly"):
            raise ValidationException(message="Granularity must be 'daily', 'weekly' or 'monthly'")
        report = AdReport(
            tenant_id=tenant_id, campaign_id=campaign_id, report_date=report_date,
            granularity=granularity,
            **{k: v for k, v in kwargs.items() if hasattr(AdReport, k)},
        )
        self._session.add(report)
        await self._session.flush()
        return report

    async def list_by_campaign(self, campaign_id: str, start_date: datetime | None = None,
                               end_date: datetime | None = None) -> list[AdReport]:
        stmt = select(AdReport).where(AdReport.campaign_id == campaign_id)
        if start_date:
            stmt = stmt.where(AdReport.report_date >= start_date)
        if end_date:
            stmt = stmt.where(AdReport.report_date <= end_date)
        stmt = stmt.order_by(AdReport.report_date.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_tenant(self, tenant_id: str, platform: str | None = None,
                             start_date: datetime | None = None, end_date: datetime | None = None,
                             offset: int = 0, limit: int = 50) -> list[AdReport]:
        stmt = select(AdReport).where(AdReport.tenant_id == tenant_id)
        if platform:
            stmt = stmt.where(AdReport.platform == platform)
        if start_date:
            stmt = stmt.where(AdReport.report_date >= start_date)
        if end_date:
            stmt = stmt.where(AdReport.report_date <= end_date)
        stmt = stmt.order_by(AdReport.report_date.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class AdStrategyService:
    """
    广告策略应用服务

    复杂聚合查询服务，仅注入 Session。
    管理预算分配、出价建议、异常检测、预算节奏、活动排名、关键词建议等。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def allocate_budget(self, tenant_id: str, total_budget: float,
                               campaigns: list[dict]) -> list[dict]:
        if total_budget <= 0:
            raise ValidationException(message="Total budget must be positive")
        active_campaigns = [c for c in campaigns if c.get("status") == "active"]
        if not active_campaigns:
            return []
        total_weight = sum(c.get("performance_weight", 1.0) for c in active_campaigns)
        allocations = []
        for c in active_campaigns:
            weight = c.get("performance_weight", 1.0)
            allocated = round(total_budget * weight / total_weight, 2)
            min_budget = c.get("min_daily_budget", MIN_DAILY_BUDGET)
            allocated = max(allocated, min_budget)
            allocations.append({
                "campaign_id": c.get("id", ""),
                "campaign_name": c.get("name", ""),
                "allocated_budget": allocated,
                "weight": weight,
                "previous_budget": c.get("daily_budget", 0),
                "change_pct": round((allocated - c.get("daily_budget", 0)) / c.get("daily_budget", 1) * 100, 2),
            })
        total_allocated = sum(a["allocated_budget"] for a in allocations)
        if total_allocated > total_budget and allocations:
            scale = total_budget / total_allocated
            for a in allocations:
                a["allocated_budget"] = round(a["allocated_budget"] * scale, 2)
        return allocations

    async def suggest_bid_adjustments(self, tenant_id: str, keywords: list[dict],
                                       target_acos: float = 30.0) -> list[dict]:
        suggestions = []
        for kw in keywords:
            current_bid = kw.get("bid", 0)
            avg_cpc = kw.get("avg_cpc", current_bid)
            conversion_rate = kw.get("conversion_rate", 0.1)
            current_acos = kw.get("acos", 0)
            suggested = AdKeywordDomainService.suggest_bid(avg_cpc, target_acos, conversion_rate)
            if current_acos > target_acos and suggested < current_bid:
                action = "decrease"
            elif current_acos < target_acos * 0.7 and suggested > current_bid:
                action = "increase"
            else:
                action = "maintain"
            suggestions.append({
                "keyword_id": kw.get("id", ""),
                "keyword_text": kw.get("keyword_text", ""),
                "current_bid": current_bid,
                "suggested_bid": suggested,
                "current_acos": current_acos,
                "action": action,
                "confidence": round(min(abs(current_acos - target_acos) / target_acos, 1.0), 2),
            })
        return suggestions

    async def detect_anomalies(self, tenant_id: str, campaign_id: str,
                                current_metrics: dict, baseline_metrics: dict) -> list[dict]:
        anomalies = []
        spend_change = self._calc_change(current_metrics.get("spend", 0), baseline_metrics.get("spend", 1))
        if abs(spend_change) > 50:
            anomalies.append({
                "metric": "spend", "current": current_metrics.get("spend", 0),
                "baseline": baseline_metrics.get("spend", 0),
                "change_pct": spend_change, "severity": "high" if abs(spend_change) > 100 else "medium",
            })
        acos_change = self._calc_change(current_metrics.get("acos", 0), baseline_metrics.get("acos", 1))
        if acos_change > 30:
            anomalies.append({
                "metric": "acos", "current": current_metrics.get("acos", 0),
                "baseline": baseline_metrics.get("acos", 0),
                "change_pct": acos_change, "severity": "high" if acos_change > 50 else "medium",
            })
        ctr_change = self._calc_change(current_metrics.get("ctr", 0), baseline_metrics.get("ctr", 0.01))
        if ctr_change < -30:
            anomalies.append({
                "metric": "ctr", "current": current_metrics.get("ctr", 0),
                "baseline": baseline_metrics.get("ctr", 0),
                "change_pct": ctr_change, "severity": "medium",
            })
        return anomalies

    @staticmethod
    def _calc_change(current: float, baseline: float) -> float:
        if baseline <= 0:
            return 0.0
        return round((current - baseline) / baseline * 100, 2)

    async def get_budget_pacing(self, tenant_id: str, campaign_id: str,
                                 spend_today: float, hours_elapsed: float) -> dict:
        campaign = await self._session.get(AdCampaign, campaign_id)
        if not campaign or campaign.tenant_id != tenant_id:
            raise NotFoundException(message=f"Campaign '{campaign_id}' not found")
        return AdPerformanceDomainService.calculate_budget_pacing(
            campaign.daily_budget, spend_today, hours_elapsed
        )

    async def rank_campaigns(self, tenant_id: str, platform: str | None = None) -> list[dict]:
        stmt = select(AdCampaign).where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
        if platform:
            stmt = stmt.where(AdCampaign.platform == platform)
        campaigns = (await self._session.execute(stmt)).scalars().all()
        campaign_data = [
            {"id": str(c.id), "name": c.name, "acos": c.acos, "roas": c.roas,
             "ctr": round(c.total_clicks / c.total_impressions * 100, 4) if c.total_impressions > 0 else 0.0,
             "total_spend": c.total_spend, "total_sales": c.total_sales}
            for c in campaigns
        ]
        return AdPerformanceDomainService.rank_campaigns_by_efficiency(campaign_data)

    async def get_keyword_suggestions(self, tenant_id: str, campaign_id: str,
                                       ad_group_id: str, seed_keywords: list[str]) -> list[dict]:
        if not seed_keywords:
            return []
        suggestions = []
        for seed in seed_keywords:
            if not seed.strip():
                continue
            broad = f"{seed} broad variant"
            phrase = f'{seed} phrase match'
            exact = f"[{seed}]"
            suggestions.append({
                "seed_keyword": seed, "suggested_keywords": [
                    {"keyword_text": broad, "match_type": "broad", "suggested_bid": MIN_KEYWORD_BID},
                    {"keyword_text": phrase, "match_type": "phrase", "suggested_bid": MIN_KEYWORD_BID},
                    {"keyword_text": exact, "match_type": "exact", "suggested_bid": MIN_KEYWORD_BID},
                ],
            })
        return suggestions


class AdPerformanceAnalysisService:
    """
    广告效果分析应用服务

    复杂聚合查询服务，仅注入 Session。
    管理广告活动趋势分析、周期对比、Top关键词分析等。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_campaign_trend(self, tenant_id: str, campaign_id: str,
                                  start_date, end_date) -> list[dict]:
        stmt = select(AdReport).where(
            AdReport.tenant_id == tenant_id,
            AdReport.campaign_id == campaign_id,
            AdReport.report_date >= start_date,
            AdReport.report_date <= end_date,
        ).order_by(AdReport.report_date)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            {
                "date": str(r.report_date),
                "impressions": r.impressions,
                "clicks": r.clicks,
                "spend": r.spend,
                "sales": r.sales,
                "orders": r.orders,
                "ctr": round(r.clicks / r.impressions * 100, 4) if r.impressions and r.impressions > 0 else 0,
                "acos": round(r.spend / r.sales * 100, 2) if r.sales and r.sales > 0 else 0,
                "roas": round(r.sales / r.spend, 2) if r.spend and r.spend > 0 else 0,
            }
            for r in rows
        ]

    async def compare_periods(self, tenant_id: str, campaign_id: str,
                               period1_start, period1_end,
                               period2_start, period2_end) -> dict:
        p1_stmt = select(
            sa_func.coalesce(sa_func.sum(AdReport.impressions), 0),
            sa_func.coalesce(sa_func.sum(AdReport.clicks), 0),
            sa_func.coalesce(sa_func.sum(AdReport.spend), 0),
            sa_func.coalesce(sa_func.sum(AdReport.sales), 0),
            sa_func.coalesce(sa_func.sum(AdReport.orders), 0),
        ).where(
            AdReport.tenant_id == tenant_id,
            AdReport.campaign_id == campaign_id,
            AdReport.report_date >= period1_start,
            AdReport.report_date <= period1_end,
        )
        p1 = (await self._session.execute(p1_stmt)).one()

        p2_stmt = select(
            sa_func.coalesce(sa_func.sum(AdReport.impressions), 0),
            sa_func.coalesce(sa_func.sum(AdReport.clicks), 0),
            sa_func.coalesce(sa_func.sum(AdReport.spend), 0),
            sa_func.coalesce(sa_func.sum(AdReport.sales), 0),
            sa_func.coalesce(sa_func.sum(AdReport.orders), 0),
        ).where(
            AdReport.tenant_id == tenant_id,
            AdReport.campaign_id == campaign_id,
            AdReport.report_date >= period2_start,
            AdReport.report_date <= period2_end,
        )
        p2 = (await self._session.execute(p2_stmt)).one()

        def _metrics(row):
            imp, clk, sp, sl, ord_ = [float(x) for x in row]
            return {
                "impressions": imp, "clicks": clk, "spend": sp, "sales": sl, "orders": ord_,
                "ctr": round(clk / imp * 100, 4) if imp > 0 else 0,
                "acos": round(sp / sl * 100, 2) if sl > 0 else 0,
                "roas": round(sl / sp, 2) if sp > 0 else 0,
                "cpc": round(sp / clk, 2) if clk > 0 else 0,
            }

        m1, m2 = _metrics(p1), _metrics(p2)
        changes = {}
        for k in m1:
            if m2[k] != 0:
                changes[k] = round((m1[k] - m2[k]) / m2[k] * 100, 2)
            else:
                changes[k] = 0
        return {"period1": m1, "period2": m2, "changes": changes}

    async def get_top_keywords(self, tenant_id: str, campaign_id: str,
                                limit: int = 20) -> list[dict]:
        stmt = select(AdKeyword).where(
            AdKeyword.tenant_id == tenant_id,
            AdKeyword.campaign_id == campaign_id,
        ).order_by(AdKeyword.bid.desc()).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            {
                "keyword_id": str(kw.id),
                "keyword_text": kw.keyword_text,
                "match_type": kw.match_type,
                "bid": kw.bid,
                "status": kw.status,
            }
            for kw in rows
        ]


# ============================================================
# ADS 统计查询服务 (ADS Query Service)
# ============================================================

class ADSQueryService:
    """
    ADS 统计查询服务

    提供广告模块的运营统计概览、各子域统计数据聚合。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_statistics(self, tenant_id: str) -> dict:
        """获取ADS运营统计概览"""
        total_campaigns = (await self._session.execute(
            select(sa_func.count()).select_from(AdCampaign)
            .where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
        )).scalar() or 0

        active_campaigns = (await self._session.execute(
            select(sa_func.count()).select_from(AdCampaign)
            .where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None), AdCampaign.status == "active")
        )).scalar() or 0

        paused_campaigns = (await self._session.execute(
            select(sa_func.count()).select_from(AdCampaign)
            .where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None), AdCampaign.status == "paused")
        )).scalar() or 0

        total_spend = float((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(AdCampaign.total_spend), 0))
            .where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
        )).scalar() or 0)

        total_sales = float((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(AdCampaign.total_sales), 0))
            .where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
        )).scalar() or 0)

        total_impressions = int((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(AdCampaign.total_impressions), 0))
            .where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
        )).scalar() or 0)

        total_clicks = int((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(AdCampaign.total_clicks), 0))
            .where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
        )).scalar() or 0)

        total_orders = int((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(AdCampaign.total_orders), 0))
            .where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
        )).scalar() or 0)

        by_platform_rows = (await self._session.execute(
            select(AdCampaign.platform, sa_func.count())
            .where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
            .group_by(AdCampaign.platform)
        )).all()
        campaigns_by_platform = {r[0]: r[1] for r in by_platform_rows}

        by_type_rows = (await self._session.execute(
            select(AdCampaign.campaign_type, sa_func.count())
            .where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
            .group_by(AdCampaign.campaign_type)
        )).all()
        campaigns_by_type = {r[0]: r[1] for r in by_type_rows}

        by_status_rows = (await self._session.execute(
            select(AdCampaign.status, sa_func.count())
            .where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
            .group_by(AdCampaign.status)
        )).all()
        campaigns_by_status = {r[0]: r[1] for r in by_status_rows}

        spend_by_platform_rows = (await self._session.execute(
            select(AdCampaign.platform, sa_func.coalesce(sa_func.sum(AdCampaign.total_spend), 0))
            .where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
            .group_by(AdCampaign.platform)
        )).all()
        spend_by_platform = {r[0]: float(r[1]) for r in spend_by_platform_rows}

        sales_by_platform_rows = (await self._session.execute(
            select(AdCampaign.platform, sa_func.coalesce(sa_func.sum(AdCampaign.total_sales), 0))
            .where(AdCampaign.tenant_id == tenant_id, AdCampaign.deleted_at.is_(None))
            .group_by(AdCampaign.platform)
        )).all()
        sales_by_platform = {r[0]: float(r[1]) for r in sales_by_platform_rows}

        total_keywords = (await self._session.execute(
            select(sa_func.count()).select_from(AdKeyword).where(AdKeyword.tenant_id == tenant_id)
        )).scalar() or 0

        active_keywords = (await self._session.execute(
            select(sa_func.count()).select_from(AdKeyword)
            .where(AdKeyword.tenant_id == tenant_id, AdKeyword.status == "enabled")
        )).scalar() or 0

        total_ad_groups = (await self._session.execute(
            select(sa_func.count()).select_from(AdGroup).where(AdGroup.tenant_id == tenant_id)
        )).scalar() or 0

        return {
            "total_campaigns": total_campaigns,
            "active_campaigns": active_campaigns,
            "paused_campaigns": paused_campaigns,
            "total_spend": round(total_spend, 2),
            "total_sales": round(total_sales, 2),
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_orders": total_orders,
            "overall_acos": round(total_spend / total_sales * 100, 2) if total_sales > 0 else 0,
            "overall_roas": round(total_sales / total_spend, 2) if total_spend > 0 else 0,
            "overall_ctr": round(total_clicks / total_impressions * 100, 4) if total_impressions > 0 else 0,
            "campaigns_by_platform": campaigns_by_platform,
            "campaigns_by_type": campaigns_by_type,
            "campaigns_by_status": campaigns_by_status,
            "spend_by_platform": spend_by_platform,
            "sales_by_platform": sales_by_platform,
            "total_keywords": total_keywords,
            "active_keywords": active_keywords,
            "total_ad_groups": total_ad_groups,
        }

    async def get_campaign_statistics(self, tenant_id: str, campaign_id: str) -> dict:
        """获取单个广告活动统计"""
        campaign = (await self._session.execute(
            select(AdCampaign).where(AdCampaign.id == campaign_id, AdCampaign.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not campaign:
            return {}
        keyword_count = (await self._session.execute(
            select(sa_func.count()).select_from(AdKeyword)
            .where(AdKeyword.campaign_id == campaign_id)
        )).scalar() or 0
        group_count = (await self._session.execute(
            select(sa_func.count()).select_from(AdGroup)
            .where(AdGroup.campaign_id == campaign_id)
        )).scalar() or 0
        return {
            "campaign_id": campaign_id,
            "name": campaign.name,
            "status": campaign.status,
            "daily_budget": campaign.daily_budget,
            "total_spend": campaign.total_spend,
            "total_sales": campaign.total_sales,
            "acos": campaign.acos,
            "roas": campaign.roas,
            "ctr": campaign.ctr,
            "keyword_count": keyword_count,
            "ad_group_count": group_count,
        }


class SmartBiddingService:
    """
    智能调价执行应用服务

    编排广告关键词的智能调价: 策略生成 → 安全校验 → 批量执行 → 效果跟踪
    支持基于ACOS/ROAS目标的自动竞价调整。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def execute_bid_adjustments(self, tenant_id: str,
                                      adjustments: list[dict]) -> dict:
        """
        执行竞价调整

        流程: 安全校验 → 逐条调整 → 记录变更 → 返回结果
        adjustments: [{keyword_id, current_bid, new_bid, reason}, ...]
        """
        success_count = 0
        failed_items: list[dict] = []
        for adj in adjustments:
            keyword_id = adj.get("keyword_id", "")
            new_bid = adj.get("new_bid", 0)
            current_bid = adj.get("current_bid", 0)
            if new_bid <= 0:
                failed_items.append({"keyword_id": keyword_id, "reason": "Bid must be positive"})
                continue
            if new_bid > current_bid * 3:
                failed_items.append({"keyword_id": keyword_id, "reason": "Bid increase exceeds 3x limit"})
                continue
            keyword = (await self._session.execute(
                select(AdKeyword).where(AdKeyword.id == keyword_id, AdKeyword.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if not keyword:
                failed_items.append({"keyword_id": keyword_id, "reason": "Keyword not found"})
                continue
            keyword.current_bid = new_bid
            success_count += 1
        if success_count > 0:
            await self._session.flush()
        return {
            "total": len(adjustments), "success_count": success_count,
            "failed_count": len(failed_items), "failed_items": failed_items,
        }

    async def auto_optimize_by_acos(self, tenant_id: str, campaign_id: str,
                                     target_acos: float = 25.0) -> dict:
        """
        基于ACOS目标自动优化关键词竞价

        流程: 查询关键词表现 → 计算ACOS偏差 → 生成调价建议 → 执行
        """
        campaign = (await self._session.execute(
            select(AdCampaign).where(AdCampaign.id == campaign_id, AdCampaign.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not campaign:
            raise NotFoundException(message=f"Campaign '{campaign_id}' not found")
        keywords = list((await self._session.execute(
            select(AdKeyword).where(AdKeyword.campaign_id == campaign_id, AdKeyword.tenant_id == tenant_id)
        )).scalars().all())
        adjustments: list[dict] = []
        for kw in keywords:
            if kw.total_spend <= 0 or kw.total_sales <= 0:
                continue
            current_acos = (kw.total_spend / kw.total_sales) * 100
            if current_acos > target_acos * 1.5:
                new_bid = kw.current_bid * 0.7
                adjustments.append({
                    "keyword_id": str(kw.id), "keyword_text": kw.keyword_text,
                    "current_bid": kw.current_bid, "new_bid": round(new_bid, 2),
                    "current_acos": round(current_acos, 1),
                    "reason": f"ACOS {current_acos:.1f}% exceeds target {target_acos}%",
                })
            elif current_acos < target_acos * 0.5 and kw.ctr > 0.5:
                new_bid = kw.current_bid * 1.2
                adjustments.append({
                    "keyword_id": str(kw.id), "keyword_text": kw.keyword_text,
                    "current_bid": kw.current_bid, "new_bid": round(new_bid, 2),
                    "current_acos": round(current_acos, 1),
                    "reason": f"ACOS {current_acos:.1f}% well below target, increasing bid",
                })
        result = await self.execute_bid_adjustments(tenant_id, adjustments)
        return {
            "campaign_id": campaign_id, "target_acos": target_acos,
            "keywords_analyzed": len(keywords),
            "adjustments_generated": len(adjustments),
            "execution_result": result,
        }


class BudgetOptimizationService:
    """
    预算自动优化应用服务

    编排广告预算的自动优化: 预算消耗监控 → 效率评估 → 预算重分配 → 执行
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def optimize_budget_allocation(self, tenant_id: str,
                                          total_daily_budget: float) -> dict:
        """
        优化预算分配

        流程: 查询所有活跃活动 → 按ROAS排序 → 按效率加权分配预算
        """
        campaigns = list((await self._session.execute(
            select(AdCampaign).where(
                AdCampaign.tenant_id == tenant_id,
                AdCampaign.status == "enabled",
            )
        )).scalars().all())
        if not campaigns:
            return {"total_budget": total_daily_budget, "allocations": [], "reason": "no active campaigns"}
        campaign_scores: list[dict] = []
        for c in campaigns:
            roas = c.roas if c.roas > 0 else 0.01
            score = roas
            campaign_scores.append({
                "campaign_id": str(c.id), "campaign_name": c.name,
                "current_budget": c.daily_budget, "roas": roas,
                "total_spend": c.total_spend, "total_sales": c.total_sales,
                "score": score,
            })
        total_score = sum(cs["score"] for cs in campaign_scores)
        allocations: list[dict] = []
        for cs in campaign_scores:
            share = cs["score"] / total_score if total_score > 0 else 1 / len(campaign_scores)
            allocated = round(total_daily_budget * share, 2)
            allocations.append({
                "campaign_id": cs["campaign_id"],
                "campaign_name": cs["campaign_name"],
                "current_budget": cs["current_budget"],
                "allocated_budget": allocated,
                "roas": round(cs["roas"], 2),
                "budget_change": round(allocated - cs["current_budget"], 2),
            })
        return {
            "total_budget": total_daily_budget,
            "active_campaigns": len(campaigns),
            "allocations": sorted(allocations, key=lambda x: x["roas"], reverse=True),
        }

    async def detect_overspend(self, tenant_id: str) -> list[dict]:
        """检测超预算活动"""
        campaigns = list((await self._session.execute(
            select(AdCampaign).where(
                AdCampaign.tenant_id == tenant_id,
                AdCampaign.status == "enabled",
            )
        )).scalars().all())
        overspend: list[dict] = []
        for c in campaigns:
            if c.daily_budget > 0 and c.total_spend > c.daily_budget * 1.2:
                overspend.append({
                    "campaign_id": str(c.id), "campaign_name": c.name,
                    "daily_budget": c.daily_budget, "total_spend": c.total_spend,
                    "overspend_pct": round((c.total_spend / c.daily_budget - 1) * 100, 1),
                    "roas": c.roas,
                })
        return overspend


class AdPlacementOptimizationService:
    """
    广告投放位优化服务

    分析各投放位效果: 位置效果对比 → 竞价建议 → 投放策略调整
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def analyze_placement_performance(self, tenant_id: str, campaign_id: str) -> dict:
        """分析投放位效果"""
        campaign = (await self._session.execute(
            select(AdCampaign).where(AdCampaign.id == campaign_id, AdCampaign.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not campaign:
            raise NotFoundException(message=f"Campaign '{campaign_id}' not found")
        groups = (await self._session.execute(
            select(AdGroup).where(AdGroup.campaign_id == campaign_id, AdGroup.tenant_id == tenant_id)
        )).scalars().all()
        placements = []
        for group in groups:
            keywords = (await self._session.execute(
                select(AdKeyword).where(AdKeyword.ad_group_id == str(group.id), AdKeyword.tenant_id == tenant_id)
            )).scalars().all()
            for kw in keywords:
                if kw.impressions > 0:
                    ctr = (kw.clicks or 0) / kw.impressions * 100
                    cpc = (kw.total_cost or 0) / kw.clicks if kw.clicks and kw.clicks > 0 else 0
                    conversions = kw.conversions or 0
                    cr = conversions / kw.clicks * 100 if kw.clicks and kw.clicks > 0 else 0
                    placements.append({
                        "keyword_id": str(kw.id), "keyword_text": kw.keyword_text,
                        "match_type": kw.match_type, "impressions": kw.impressions,
                        "clicks": kw.clicks, "ctr": round(ctr, 2),
                        "cpc": round(cpc, 2), "conversions": conversions,
                        "cr": round(cr, 2), "acos": kw.acos,
                    })
        placements.sort(key=lambda x: x.get("cr", 0), reverse=True)
        return {
            "campaign_id": campaign_id, "total_keywords": len(placements),
            "top_performers": placements[:10],
            "low_performers": placements[-10:] if len(placements) > 10 else [],
        }

    async def suggest_bid_adjustments(self, tenant_id: str, campaign_id: str) -> list[dict]:
        """建议竞价调整"""
        groups = (await self._session.execute(
            select(AdGroup).where(AdGroup.campaign_id == campaign_id, AdGroup.tenant_id == tenant_id)
        )).scalars().all()
        suggestions = []
        for group in groups:
            keywords = (await self._session.execute(
                select(AdKeyword).where(AdKeyword.ad_group_id == str(group.id), AdKeyword.tenant_id == tenant_id)
            )).scalars().all()
            for kw in keywords:
                if kw.acos and kw.acos > 0:
                    if kw.acos < 15:
                        suggestion = "increase_bid"
                        reason = f"ACoS {kw.acos:.1f}% 低，建议加价获取更多流量"
                    elif kw.acos > 40:
                        suggestion = "decrease_bid"
                        reason = f"ACoS {kw.acos:.1f}% 过高，建议降价控制成本"
                    else:
                        suggestion = "maintain"
                        reason = f"ACoS {kw.acos:.1f}% 正常，维持当前竞价"
                    suggestions.append({
                        "keyword_id": str(kw.id), "keyword_text": kw.keyword_text,
                        "current_bid": kw.bid, "acos": kw.acos,
                        "suggestion": suggestion, "reason": reason,
                    })
        return suggestions


class KeywordMiningService:
    """
    关键词挖掘服务

    基于搜索词报告挖掘高潜力关键词: 搜索词分析 → 否词建议 → 新词推荐
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def suggest_negative_keywords(self, tenant_id: str, campaign_id: str) -> dict:
        """建议否定关键词"""
        groups = (await self._session.execute(
            select(AdGroup).where(AdGroup.campaign_id == campaign_id, AdGroup.tenant_id == tenant_id)
        )).scalars().all()
        negatives = []
        for group in groups:
            keywords = (await self._session.execute(
                select(AdKeyword).where(AdKeyword.ad_group_id == str(group.id), AdKeyword.tenant_id == tenant_id)
            )).scalars().all()
            for kw in keywords:
                if kw.impressions > 100 and kw.clicks and kw.clicks > 0:
                    cr = (kw.conversions or 0) / kw.clicks * 100
                    if cr < 1 and (kw.total_cost or 0) > 10:
                        negatives.append({
                            "keyword_id": str(kw.id), "keyword_text": kw.keyword_text,
                            "match_type": kw.match_type, "impressions": kw.impressions,
                            "clicks": kw.clicks, "conversions": kw.conversions or 0,
                            "cr": round(cr, 2), "total_cost": kw.total_cost,
                            "suggested_action": "add_to_negative",
                        })
        return {"campaign_id": campaign_id, "negative_suggestions": negatives}

    async def find_high_potential_keywords(self, tenant_id: str, store_id: str = "") -> list[dict]:
        """发现高潜力关键词"""
        high_performers = (await self._session.execute(
            select(AdKeyword).where(
                AdKeyword.tenant_id == tenant_id,
                AdKeyword.conversions > 0,
                AdKeyword.acos < 20,
            ).order_by(AdKeyword.conversions.desc()).limit(20)
        )).scalars().all()
        return [
            {"keyword_text": kw.keyword_text, "match_type": kw.match_type,
             "conversions": kw.conversions, "acos": kw.acos, "cr": round(kw.conversions / kw.clicks * 100, 2) if kw.clicks else 0}
            for kw in high_performers
        ]
