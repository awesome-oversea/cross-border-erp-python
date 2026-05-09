"""
ADS (广告投放域) 依赖注入工厂

所有 Service 和 Repository 实例通过 FastAPI Depends() 链式注入，
禁止在 router 中手动实例化 Service。

注入链路 (铁律):
  router → Depends(get_xxx_service) → Service(session, repo) → Repository(session)

仓储注入规则:
  - AdCampaignRepository: 被 AdCampaignService 使用
  - AdGroupRepository: 被 AdGroupService 使用
  - AdKeywordRepository: 被 AdKeywordService 使用
  - AdReportRepository: 被 AdReportService 使用
  - AdStrategyService / AdPerformanceAnalysisService:
    复杂聚合查询，仅注入 Session，不通过仓储接口
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.ads.application.services import (
    AdCampaignService,
    AdGroupService,
    AdKeywordService,
    AdPerformanceAnalysisService,
    AdReportService,
    AdStrategyService,
    ADSQueryService,
)
from erp.modules.ads.domain.repositories import (
    AdCampaignRepository,
    AdGroupRepository,
    AdKeywordRepository,
    AdReportRepository,
)
from erp.modules.ads.infrastructure.repositories import (
    SqlAdCampaignRepository,
    SqlAdGroupRepository,
    SqlAdKeywordRepository,
    SqlAdReportRepository,
)
from erp.shared.context import TenantContext, tenant_id_var
from erp.shared.db.session import get_db_session


# ============================================================
# 仓储工厂: Session → Repository 实例
# ============================================================

def _ad_campaign_repo(session: AsyncSession = Depends(get_db_session)) -> AdCampaignRepository:
    """创建广告活动仓储实例 — 被 AdCampaignService 使用"""
    return SqlAdCampaignRepository(session)


def _ad_group_repo(session: AsyncSession = Depends(get_db_session)) -> AdGroupRepository:
    """创建广告组仓储实例 — 被 AdGroupService 使用"""
    return SqlAdGroupRepository(session)


def _ad_keyword_repo(session: AsyncSession = Depends(get_db_session)) -> AdKeywordRepository:
    """创建关键词仓储实例 — 被 AdKeywordService 使用"""
    return SqlAdKeywordRepository(session)


def _ad_report_repo(session: AsyncSession = Depends(get_db_session)) -> AdReportRepository:
    """创建广告报表仓储实例 — 被 AdReportService 使用"""
    return SqlAdReportRepository(session)


# ============================================================
# 服务工厂: Session + Repository → Service 实例
# ============================================================

def get_ad_campaign_service(
    session: AsyncSession = Depends(get_db_session),
    repo: AdCampaignRepository = Depends(_ad_campaign_repo),
) -> AdCampaignService:
    """获取广告活动服务实例 — 注入 AdCampaignRepository"""
    return AdCampaignService(session=session, repo=repo)


def get_ad_group_service(
    session: AsyncSession = Depends(get_db_session),
    repo: AdGroupRepository = Depends(_ad_group_repo),
) -> AdGroupService:
    """获取广告组服务实例 — 注入 AdGroupRepository"""
    return AdGroupService(session=session, repo=repo)


def get_ad_keyword_service(
    session: AsyncSession = Depends(get_db_session),
    repo: AdKeywordRepository = Depends(_ad_keyword_repo),
) -> AdKeywordService:
    """获取关键词服务实例 — 注入 AdKeywordRepository"""
    return AdKeywordService(session=session, repo=repo)


def get_ad_report_service(
    session: AsyncSession = Depends(get_db_session),
    repo: AdReportRepository = Depends(_ad_report_repo),
) -> AdReportService:
    """获取广告报表服务实例 — 注入 AdReportRepository"""
    return AdReportService(session=session, repo=repo)


# ============================================================
# 复杂聚合查询服务 — 仅注入 Session，不通过仓储接口
# 这些服务涉及多表 JOIN / SUM / GROUP BY 等复杂查询，
# 仓储接口的 CRUD 粒度无法满足，保留 Session 直接操作。
# ============================================================

def get_ad_strategy_service(
    session: AsyncSession = Depends(get_db_session),
) -> AdStrategyService:
    """获取广告策略服务实例 — 复杂聚合查询，仅注入 Session"""
    return AdStrategyService(session=session)


def get_ad_performance_analysis_service(
    session: AsyncSession = Depends(get_db_session),
) -> AdPerformanceAnalysisService:
    """获取广告效果分析服务实例 — 复杂聚合查询，仅注入 Session"""
    return AdPerformanceAnalysisService(session=session)


def get_ad_query_service(
    session: AsyncSession = Depends(get_db_session),
) -> ADSQueryService:
    """获取ADS统计查询服务实例 — 复杂聚合查询，仅注入 Session"""
    return ADSQueryService(session=session)


# ============================================================
# 通用上下文依赖
# ============================================================

def get_tenant_context() -> TenantContext:
    """获取当前租户上下文 (从 ContextVar 读取)"""
    return TenantContext.current()


def get_current_tenant_id() -> str:
    """获取当前租户ID (从 ContextVar 读取)"""
    return tenant_id_var.get("")
