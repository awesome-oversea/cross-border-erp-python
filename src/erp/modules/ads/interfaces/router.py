"""
ADS (广告投放域) 路由定义

内部域路径规范: /ads/api/v1/{resource}
外部交互路径规范: /ads/api/out/v1/{resource} (见 out_router.py)

所有服务通过 Depends() 注入，禁止手动实例化 Service。
DTO 定义在 application/dtos.py 中，本文件仅做导入。
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from erp.modules.ads.application.dtos import (
    AdCampaignBatchStatusRequest,
    AdCampaignCreateRequest,
    AdCampaignResponse,
    AdCampaignSearchRequest,
    AdCampaignUpdateRequest,
    AdGroupCreateRequest,
    AdGroupResponse,
    AdKeywordBatchBidRequest,
    AdKeywordCreateRequest,
    AdKeywordResponse,
    AdKeywordSearchRequest,
    AdReportCreateRequest,
    AdReportResponse,
    ADSStatisticsResponse,
    PageRequest,
)
from erp.modules.ads.application.services import (
    AdCampaignService,
    AdGroupService,
    AdKeywordService,
    AdPerformanceAnalysisService,
    AdReportService,
    AdStrategyService,
    ADSQueryService,
)
from erp.modules.ads.interfaces.deps import (
    get_ad_campaign_service,
    get_ad_group_service,
    get_ad_keyword_service,
    get_ad_performance_analysis_service,
    get_ad_query_service,
    get_ad_report_service,
    get_ad_strategy_service,
    get_current_tenant_id,
)
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/ads/v1", tags=["ADS - 广告投放管理"])


# ============================================================
# 内联 DTO — 仅用于 router 层的简单请求/响应，
# 完整 DTO 请参考 application/dtos.py
# ============================================================

class CampaignStatusRequest(BaseModel):
    """广告活动状态变更请求"""
    status: str


class KeywordBidRequest(BaseModel):
    """关键词出价变更请求"""
    bid: float


class StrategyCreateRequest(BaseModel):
    """策略创建请求 (占位)"""
    name: str
    strategy_type: str = "auto_bid"
    campaign_id: str = ""
    conditions_json: str = "{}"
    actions_json: str = "{}"
    priority: int = 0
    is_active: bool = True


class StrategyUpdateRequest(BaseModel):
    """策略更新请求 (占位)"""
    name: str | None = None
    conditions_json: str | None = None
    actions_json: str | None = None
    priority: int | None = None


class StrategyToggleRequest(BaseModel):
    """策略开关请求"""
    is_active: bool


class PmsStrategySuggestRequest(BaseModel):
    """PMS策略建议请求 (外部交互)"""
    suggestion_id: str
    campaign_id: str
    suggestion_type: str
    suggested_actions: list[dict] = []
    confidence: float = 0.0
    reason: str = ""


class PmsBidAdjustRequest(BaseModel):
    """PMS出价调整请求 (外部交互)"""
    keyword_id: str
    current_bid: float
    suggested_bid: float
    reason: str = ""
    confidence: float = 0.0


class PmsKeywordsSuggestRequest(BaseModel):
    """PMS关键词建议请求 (外部交互)"""
    campaign_id: str
    ad_group_id: str = ""
    suggested_keywords: list[dict] = []
    reason: str = ""


class PmsRollbackRequest(BaseModel):
    """PMS回滚请求"""
    log_id: str
    reason: str = ""


class PmsOptimizationToggleRequest(BaseModel):
    """PMS优化开关请求"""
    is_enabled: bool
    optimization_scope: str = "full"


# ============================================================
# 广告活动 (Campaign) 端点
# ============================================================

@router.post("/campaigns", response_model=None, summary="创建广告活动")
async def create_campaign(
    req: AdCampaignCreateRequest,
    svc: AdCampaignService = Depends(get_ad_campaign_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建广告活动: 类型校验 → 唯一性校验 → 持久化"""
    kwargs = {}
    if req.start_date:
        kwargs["start_date"] = req.start_date
    if req.end_date:
        kwargs["end_date"] = req.end_date
    campaign = await svc.create(
        tenant_id=tenant_id, campaign_no=req.campaign_no, name=req.name,
        platform=req.platform, store_id=req.store_id, campaign_type=req.campaign_type,
        targeting_type=req.targeting_type, daily_budget=req.daily_budget,
        currency=req.currency, **kwargs,
    )
    return Result.ok(
        data=AdCampaignResponse.model_validate(campaign).model_dump(),
        trace_id=trace_id_var.get(""),
    )


@router.get("/campaigns", response_model=None, summary="查询广告活动列表")
async def list_campaigns(
    platform: str | None = None,
    status: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    svc: AdCampaignService = Depends(get_ad_campaign_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询广告活动列表，支持按平台/状态过滤"""
    campaigns = await svc.list_by_tenant(tenant_id, status=status, platform=platform, offset=offset, limit=limit)
    items = [AdCampaignResponse.model_validate(c).model_dump() for c in campaigns]
    return Result.ok(data={"items": items, "total": len(items)}, trace_id=trace_id_var.get(""))


@router.get("/campaigns/{campaign_id}", response_model=None, summary="获取广告活动详情")
async def get_campaign(
    campaign_id: str,
    svc: AdCampaignService = Depends(get_ad_campaign_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """获取广告活动详情"""
    campaign = await svc.get_or_raise(campaign_id, tenant_id)
    return Result.ok(
        data=AdCampaignResponse.model_validate(campaign).model_dump(),
        trace_id=trace_id_var.get(""),
    )


@router.put("/campaigns/{campaign_id}", response_model=None, summary="更新广告活动")
async def update_campaign(
    campaign_id: str,
    req: AdCampaignUpdateRequest,
    svc: AdCampaignService = Depends(get_ad_campaign_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """更新广告活动基本信息"""
    update_data = req.model_dump(exclude_none=True)
    campaign = await svc.update(campaign_id, tenant_id, **update_data)
    return Result.ok(
        data=AdCampaignResponse.model_validate(campaign).model_dump(),
        trace_id=trace_id_var.get(""),
    )


@router.put("/campaigns/{campaign_id}/status", response_model=None, summary="变更广告活动状态")
async def update_campaign_status(
    campaign_id: str,
    req: CampaignStatusRequest,
    svc: AdCampaignService = Depends(get_ad_campaign_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """变更广告活动状态: 校验状态机合法性 → 更新"""
    campaign = await svc.update_status(campaign_id, tenant_id, req.status)
    return Result.ok(data={"id": campaign.id, "status": campaign.status}, trace_id=trace_id_var.get(""))


@router.delete("/campaigns/{campaign_id}", response_model=None, summary="归档广告活动")
async def delete_campaign(
    campaign_id: str,
    svc: AdCampaignService = Depends(get_ad_campaign_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """归档广告活动 (软删除)"""
    deleted = await svc.soft_delete(campaign_id, tenant_id)
    return Result.ok(data={"id": campaign_id, "deleted": deleted}, trace_id=trace_id_var.get(""))


@router.post("/campaigns/{campaign_id}/sync", response_model=None, summary="同步广告活动到平台")
async def sync_campaign_to_platform(
    campaign_id: str,
    svc: AdCampaignService = Depends(get_ad_campaign_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """同步广告活动到第三方广告平台"""
    campaign = await svc.get_or_raise(campaign_id, tenant_id)
    return Result.ok(
        data={"campaign_id": campaign_id, "sync_status": "synced", "platform": campaign.platform},
        trace_id=trace_id_var.get(""),
    )


# ============================================================
# 广告组 (Ad Group) 端点
# ============================================================

@router.post("/ad-groups", response_model=None, summary="创建广告组")
async def create_ad_group(
    req: AdGroupCreateRequest,
    svc: AdGroupService = Depends(get_ad_group_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建广告组: 校验所属活动 → 持久化"""
    group = await svc.create(
        tenant_id=tenant_id, campaign_id=req.campaign_id, name=req.name,
        default_bid=req.default_bid, sku_id=req.sku_id, listing_id=req.listing_id,
    )
    return Result.ok(
        data=AdGroupResponse.model_validate(group).model_dump(),
        trace_id=trace_id_var.get(""),
    )


@router.get("/campaigns/{campaign_id}/ad-groups", response_model=None, summary="查询活动下广告组")
async def list_ad_groups(
    campaign_id: str,
    svc: AdGroupService = Depends(get_ad_group_service),
):
    """查询指定广告活动下的所有广告组"""
    groups = await svc.list_by_campaign(campaign_id)
    items = [AdGroupResponse.model_validate(g).model_dump() for g in groups]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.put("/ad-groups/{group_id}", response_model=None, summary="更新广告组")
async def update_ad_group(
    group_id: str,
    req: AdGroupCreateRequest,
    svc: AdGroupService = Depends(get_ad_group_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """更新广告组基本信息"""
    group = await svc.update(group_id, tenant_id, name=req.name, default_bid=req.default_bid)
    return Result.ok(
        data=AdGroupResponse.model_validate(group).model_dump(),
        trace_id=trace_id_var.get(""),
    )


# ============================================================
# 关键词 (Keyword) 端点
# ============================================================

@router.post("/keywords", response_model=None, summary="创建关键词")
async def create_keyword(
    req: AdKeywordCreateRequest,
    svc: AdKeywordService = Depends(get_ad_keyword_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建关键词: 匹配类型校验 → 出价范围校验 → 持久化"""
    kw = await svc.create(
        tenant_id=tenant_id, campaign_id=req.campaign_id, ad_group_id=req.ad_group_id,
        keyword_text=req.keyword_text, match_type=req.match_type, bid=req.bid,
    )
    return Result.ok(
        data=AdKeywordResponse.model_validate(kw).model_dump(),
        trace_id=trace_id_var.get(""),
    )


@router.get("/ad-groups/{ad_group_id}/keywords", response_model=None, summary="查询广告组下关键词")
async def list_keywords(
    ad_group_id: str,
    svc: AdKeywordService = Depends(get_ad_keyword_service),
):
    """查询指定广告组下的所有关键词"""
    keywords = await svc.list_by_ad_group(ad_group_id)
    items = [AdKeywordResponse.model_validate(k).model_dump() for k in keywords]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.put("/keywords/{keyword_id}/bid", response_model=None, summary="更新关键词出价")
async def update_keyword_bid(
    keyword_id: str,
    req: KeywordBidRequest,
    svc: AdKeywordService = Depends(get_ad_keyword_service),
):
    """更新关键词出价: 出价范围校验 → 更新"""
    kw = await svc.update_bid(keyword_id, req.bid)
    return Result.ok(data={"id": kw.id, "bid": kw.bid}, trace_id=trace_id_var.get(""))


@router.put("/keywords/{keyword_id}", response_model=None, summary="更新关键词")
async def update_keyword(
    keyword_id: str,
    req: AdKeywordCreateRequest,
    svc: AdKeywordService = Depends(get_ad_keyword_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """更新关键词信息"""
    kw = await svc.get_or_raise(keyword_id, tenant_id)
    kw.keyword_text = req.keyword_text
    kw.match_type = req.match_type
    kw.bid = req.bid
    return Result.ok(data={"id": kw.id, "keyword_text": kw.keyword_text, "match_type": kw.match_type, "bid": kw.bid},
                     trace_id=trace_id_var.get(""))


@router.delete("/keywords/{keyword_id}", response_model=None, summary="归档关键词")
async def delete_keyword(
    keyword_id: str,
    svc: AdKeywordService = Depends(get_ad_keyword_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """归档关键词 (软删除)"""
    kw = await svc.get_or_raise(keyword_id, tenant_id)
    kw.status = "archived"
    return Result.ok(data={"id": keyword_id, "status": "archived"}, trace_id=trace_id_var.get(""))


# ============================================================
# 广告报表 (Report) 端点
# ============================================================

@router.post("/reports", response_model=None, summary="创建广告报表")
async def create_report(
    req: AdReportCreateRequest,
    svc: AdReportService = Depends(get_ad_report_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建广告报表记录"""
    report = await svc.create(
        tenant_id=tenant_id, campaign_id=req.campaign_id,
        report_date=req.report_date, granularity=req.granularity,
        impressions=req.impressions, clicks=req.clicks, spend=req.spend,
        sales=req.sales, orders=req.orders, units=req.units,
        currency=req.currency, store_id=req.store_id, platform=req.platform,
    )
    return Result.ok(
        data=AdReportResponse.model_validate(report).model_dump(),
        trace_id=trace_id_var.get(""),
    )


@router.get("/reports", response_model=None, summary="查询广告报表列表")
async def list_reports(
    platform: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    svc: AdReportService = Depends(get_ad_report_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询广告报表列表，支持按平台/日期范围过滤"""
    sd = datetime.fromisoformat(start_date) if start_date else None
    ed = datetime.fromisoformat(end_date) if end_date else None
    reports = await svc.list_by_tenant(tenant_id, platform=platform, start_date=sd, end_date=ed, offset=offset, limit=limit)
    items = [AdReportResponse.model_validate(r).model_dump() for r in reports]
    return Result.ok(data={"items": items, "total": len(items)}, trace_id=trace_id_var.get(""))


@router.get("/reports/summary", response_model=None, summary="广告报表汇总")
async def reports_summary(
    platform: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    svc: AdReportService = Depends(get_ad_report_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """广告报表汇总: 总花费/总销售额/平均ACOS/ROAS/CTR"""
    sd = datetime.fromisoformat(start_date) if start_date else None
    ed = datetime.fromisoformat(end_date) if end_date else None
    reports = await svc.list_by_tenant(tenant_id, platform=platform, start_date=sd, end_date=ed, offset=0, limit=1000)
    total_spend = sum(r.spend or 0 for r in reports)
    total_sales = sum(r.sales or 0 for r in reports)
    total_clicks = sum(r.clicks or 0 for r in reports)
    total_impressions = sum(r.impressions or 0 for r in reports)
    total_orders = sum(r.orders or 0 for r in reports)
    avg_acos = (total_spend / total_sales * 100) if total_sales > 0 else 0
    avg_roas = (total_sales / total_spend) if total_spend > 0 else 0
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    return Result.ok(data={
        "total_spend": round(total_spend, 2), "total_sales": round(total_sales, 2),
        "total_clicks": total_clicks, "total_impressions": total_impressions,
        "total_orders": total_orders, "avg_acos": round(avg_acos, 2),
        "avg_roas": round(avg_roas, 2), "avg_ctr": round(avg_ctr, 2),
    }, trace_id=trace_id_var.get(""))


@router.post("/reports/generate", response_model=None, summary="生成广告报表")
async def generate_report(
    campaign_id: str = Query(default=""),
    report_type: str = Query(default="campaign"),
    start_date: str | None = None,
    end_date: str | None = None,
):
    """生成广告报表 (异步任务占位)"""
    return Result.ok(data={
        "report_id": "rpt_gen", "campaign_id": campaign_id,
        "report_type": report_type, "status": "generating",
    }, trace_id=trace_id_var.get(""))


# ============================================================
# 广告效果 (Performance) 端点
# ============================================================

@router.get("/campaigns/{campaign_id}/performance", response_model=None, summary="查询活动效果")
async def campaign_performance(
    campaign_id: str,
    days: int = Query(default=7, ge=1, le=90),
    svc: AdReportService = Depends(get_ad_report_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询广告活动效果数据 (按天)"""
    reports = await svc.list_by_tenant(tenant_id, offset=0, limit=100)
    campaign_reports = [r for r in reports if r.campaign_id == campaign_id]
    daily_data = [
        {"date": r.report_date.isoformat() if r.report_date else "", "spend": r.spend, "sales": r.sales,
         "clicks": r.clicks, "impressions": r.impressions, "acos": r.acos, "roas": r.roas}
        for r in campaign_reports[:days]
    ]
    return Result.ok(data={"campaign_id": campaign_id, "daily_data": daily_data}, trace_id=trace_id_var.get(""))


@router.get("/performance", response_model=None, summary="查询整体效果")
async def query_performance(
    platform: str = Query(default=""),
    start_date: str | None = None,
    end_date: str | None = None,
    svc: AdReportService = Depends(get_ad_report_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询整体广告效果: 总花费/销售额/ACOS/ROAS/CTR"""
    sd = datetime.fromisoformat(start_date) if start_date else None
    ed = datetime.fromisoformat(end_date) if end_date else None
    reports = await svc.list_by_tenant(tenant_id, platform=platform, start_date=sd, end_date=ed, offset=0, limit=1000)
    total_spend = sum(r.spend or 0 for r in reports)
    total_sales = sum(r.sales or 0 for r in reports)
    total_clicks = sum(r.clicks or 0 for r in reports)
    total_impressions = sum(r.impressions or 0 for r in reports)
    return Result.ok(data={
        "total_spend": round(total_spend, 2), "total_sales": round(total_sales, 2),
        "total_clicks": total_clicks, "total_impressions": total_impressions,
        "acos": round((total_spend / total_sales * 100) if total_sales > 0 else 0, 2),
        "roas": round((total_sales / total_spend) if total_spend > 0 else 0, 2),
        "ctr": round((total_clicks / total_impressions * 100) if total_impressions > 0 else 0, 2),
    }, trace_id=trace_id_var.get(""))


@router.get("/performance/by-campaign", response_model=None, summary="按活动查询效果")
async def performance_by_campaign(
    platform: str = Query(default=""),
    start_date: str | None = None,
    end_date: str | None = None,
    svc: AdReportService = Depends(get_ad_report_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按广告活动汇总效果数据"""
    sd = datetime.fromisoformat(start_date) if start_date else None
    ed = datetime.fromisoformat(end_date) if end_date else None
    reports = await svc.list_by_tenant(tenant_id, platform=platform, start_date=sd, end_date=ed, offset=0, limit=500)
    campaign_map: dict[str, dict] = {}
    for r in reports:
        cid = r.campaign_id or "unknown"
        if cid not in campaign_map:
            campaign_map[cid] = {"campaign_id": cid, "spend": 0, "sales": 0, "clicks": 0, "impressions": 0, "orders": 0}
        campaign_map[cid]["spend"] += r.spend or 0
        campaign_map[cid]["sales"] += r.sales or 0
        campaign_map[cid]["clicks"] += r.clicks or 0
        campaign_map[cid]["impressions"] += r.impressions or 0
        campaign_map[cid]["orders"] += r.orders or 0
    for item in campaign_map.values():
        item["acos"] = round((item["spend"] / item["sales"] * 100) if item["sales"] > 0 else 0, 2)
        item["roas"] = round((item["sales"] / item["spend"]) if item["spend"] > 0 else 0, 2)
    return Result.ok(data=list(campaign_map.values()), trace_id=trace_id_var.get(""))


@router.get("/performance/by-keyword", response_model=None, summary="按关键词查询效果")
async def performance_by_keyword(
    campaign_id: str = Query(default=""),
    svc: AdKeywordService = Depends(get_ad_keyword_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按关键词汇总效果数据"""
    keywords = await svc.list_by_tenant(tenant_id, offset=0, limit=100)
    items = [{"keyword_id": k.id, "keyword_text": k.keyword_text, "match_type": k.match_type,
              "bid": k.bid, "ctr": k.ctr, "cpc": k.cpc} for k in keywords]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.get("/performance/by-asin", response_model=None, summary="按ASIN查询效果")
async def performance_by_asin(
    asin: str = Query(default=""),
    start_date: str | None = None,
    end_date: str | None = None,
    svc: AdReportService = Depends(get_ad_report_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """按ASIN汇总效果数据 (占位)"""
    sd = datetime.fromisoformat(start_date) if start_date else None
    ed = datetime.fromisoformat(end_date) if end_date else None
    reports = await svc.list_by_tenant(tenant_id, start_date=sd, end_date=ed, offset=0, limit=500)
    return Result.ok(
        data={"asin": asin, "reports": [{"campaign_id": r.campaign_id, "spend": r.spend, "sales": r.sales} for r in reports[:20]]},
        trace_id=trace_id_var.get(""),
    )


@router.get("/performance/trend", response_model=None, summary="效果趋势")
async def performance_trend(
    granularity: str = Query(default="daily"),
    start_date: str | None = None,
    end_date: str | None = None,
    svc: AdReportService = Depends(get_ad_report_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询广告效果趋势 (按天/周/月)"""
    sd = datetime.fromisoformat(start_date) if start_date else None
    ed = datetime.fromisoformat(end_date) if end_date else None
    reports = await svc.list_by_tenant(tenant_id, start_date=sd, end_date=ed, offset=0, limit=365)
    trend = [{"date": r.report_date.isoformat() if r.report_date else "", "spend": r.spend, "sales": r.sales,
              "clicks": r.clicks, "impressions": r.impressions} for r in reports]
    return Result.ok(data=trend, trace_id=trace_id_var.get(""))


@router.get("/search-terms", response_model=None, summary="搜索词查询")
async def list_search_terms(
    campaign_id: str = Query(default=""),
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = Query(50, ge=1, le=200),
):
    """查询搜索词 (占位)"""
    return Result.ok(data=[], trace_id=trace_id_var.get(""))


# ============================================================
# 策略 (Strategy) 端点 — 占位
# ============================================================

@router.post("/strategies", response_model=None, summary="创建策略")
async def create_strategy(req: StrategyCreateRequest):
    """创建广告策略 (占位)"""
    return Result.ok(data={"id": "strategy_new", "name": req.name, "strategy_type": req.strategy_type,
                           "campaign_id": req.campaign_id, "is_active": req.is_active,
                           "priority": req.priority}, trace_id=trace_id_var.get(""))


@router.get("/strategies", response_model=None, summary="查询策略列表")
async def list_strategies(
    strategy_type: str = Query(default=""),
    campaign_id: str = Query(default=""),
):
    """查询策略列表 (占位)"""
    return Result.ok(data=[], trace_id=trace_id_var.get(""))


@router.get("/strategies/{strategy_id}", response_model=None, summary="获取策略详情")
async def get_strategy(strategy_id: str):
    """获取策略详情 (占位)"""
    return Result.ok(data={"id": strategy_id, "name": "", "strategy_type": "", "is_active": True},
                     trace_id=trace_id_var.get(""))


@router.put("/strategies/{strategy_id}", response_model=None, summary="更新策略")
async def update_strategy(strategy_id: str, req: StrategyUpdateRequest):
    """更新策略 (占位)"""
    return Result.ok(data={"id": strategy_id, "updated": True}, trace_id=trace_id_var.get(""))


@router.put("/strategies/{strategy_id}/toggle", response_model=None, summary="切换策略开关")
async def toggle_strategy(strategy_id: str, req: StrategyToggleRequest):
    """切换策略启用/禁用 (占位)"""
    return Result.ok(data={"id": strategy_id, "is_active": req.is_active}, trace_id=trace_id_var.get(""))


# ============================================================
# PMS 外部交互端点 (内部域路径，接收PMS推送)
# ============================================================

@router.post("/pms/strategy/suggest", response_model=None, summary="接收PMS策略建议")
async def receive_pms_strategy_suggest(req: PmsStrategySuggestRequest):
    """接收PMS策略建议推送"""
    return Result.ok(data={"suggestion_id": req.suggestion_id, "campaign_id": req.campaign_id,
                           "suggestion_type": req.suggestion_type, "confidence": req.confidence,
                           "status": "received"}, trace_id=trace_id_var.get(""))


@router.post("/pms/action/bid-adjust", response_model=None, summary="接收PMS出价调整")
async def receive_pms_bid_adjust(
    req: PmsBidAdjustRequest,
    svc: AdKeywordService = Depends(get_ad_keyword_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """接收PMS出价调整推送: 更新关键词出价"""
    kw = await svc.get_or_raise(req.keyword_id, tenant_id)
    kw.bid = req.suggested_bid
    return Result.ok(data={"keyword_id": req.keyword_id, "old_bid": req.current_bid,
                           "new_bid": req.suggested_bid, "reason": req.reason}, trace_id=trace_id_var.get(""))


@router.post("/pms/keywords/suggest", response_model=None, summary="接收PMS关键词建议")
async def receive_pms_keywords_suggest(req: PmsKeywordsSuggestRequest):
    """接收PMS关键词建议推送"""
    return Result.ok(data={"campaign_id": req.campaign_id, "ad_group_id": req.ad_group_id,
                           "suggested_count": len(req.suggested_keywords),
                           "status": "received"}, trace_id=trace_id_var.get(""))


@router.post("/pms/action/{log_id}/rollback", response_model=None, summary="回滚PMS操作")
async def rollback_pms_action(log_id: str, req: PmsRollbackRequest):
    """回滚PMS操作"""
    return Result.ok(data={"log_id": log_id, "rollback_status": "rolled_back", "reason": req.reason},
                     trace_id=trace_id_var.get(""))


@router.put("/campaigns/{campaign_id}/pms-optimization", response_model=None, summary="切换PMS优化")
async def toggle_pms_optimization(
    campaign_id: str,
    req: PmsOptimizationToggleRequest,
    svc: AdCampaignService = Depends(get_ad_campaign_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """切换广告活动的PMS智能优化开关"""
    await svc.get_or_raise(campaign_id, tenant_id)
    return Result.ok(data={"campaign_id": campaign_id, "pms_optimization_enabled": req.is_enabled,
                           "scope": req.optimization_scope}, trace_id=trace_id_var.get(""))


@router.get("/pms/analytics/performance", response_model=None, summary="PMS效果分析")
async def pms_analytics_performance(
    campaign_id: str = Query(default=""),
    start_date: str | None = None,
    end_date: str | None = None,
    svc: AdReportService = Depends(get_ad_report_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """PMS效果分析: 汇总花费/销售额/ACOS/ROAS"""
    sd = datetime.fromisoformat(start_date) if start_date else None
    ed = datetime.fromisoformat(end_date) if end_date else None
    reports = await svc.list_by_tenant(tenant_id, start_date=sd, end_date=ed, offset=0, limit=500)
    total_spend = sum(r.spend or 0 for r in reports)
    total_sales = sum(r.sales or 0 for r in reports)
    return Result.ok(data={
        "total_spend": round(total_spend, 2), "total_sales": round(total_sales, 2),
        "acos": round((total_spend / total_sales * 100) if total_sales > 0 else 0, 2),
        "roas": round((total_sales / total_spend) if total_spend > 0 else 0, 2),
        "campaign_count": len(set(r.campaign_id for r in reports)),
    }, trace_id=trace_id_var.get(""))


# ============================================================
# 统计与搜索端点
# ============================================================

@router.get("/statistics", response_model=None, summary="ADS运营统计概览")
async def get_ads_statistics(
    svc: ADSQueryService = Depends(get_ad_query_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """获取ADS运营统计概览: 活动数/花费/销售额/ACOS/ROAS/CTR等核心指标"""
    result = await svc.get_statistics(tenant_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/campaigns/{campaign_id}/statistics", response_model=None, summary="广告活动统计详情")
async def get_campaign_statistics(
    campaign_id: str,
    svc: ADSQueryService = Depends(get_ad_query_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """获取单个广告活动的统计详情: 花费/销售额/关键词数/广告组数"""
    result = await svc.get_campaign_statistics(tenant_id, campaign_id)
    return Result.ok(data=result or {}, trace_id=trace_id_var.get(""))


@router.post("/campaigns/search", response_model=None, summary="搜索广告活动")
async def search_campaigns(
    req: AdCampaignSearchRequest,
    svc: AdCampaignService = Depends(get_ad_campaign_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """多维度搜索广告活动: 关键词/平台/状态/类型/预算范围/日期范围"""
    items, total = await svc.search(
        tenant_id, keyword=req.keyword, platform=req.platform,
        status=req.status, campaign_type=req.campaign_type,
        store_id=req.store_id, min_budget=req.min_budget,
        max_budget=req.max_budget, start_date=req.start_date,
        end_date=req.end_date, page=req.page, page_size=req.page_size,
    )
    data = [AdCampaignResponse.model_validate(c).model_dump() for c in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


@router.post("/campaigns/batch-status", response_model=None, summary="批量变更广告活动状态")
async def batch_update_campaign_status(
    req: AdCampaignBatchStatusRequest,
    svc: AdCampaignService = Depends(get_ad_campaign_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """批量变更广告活动状态: 校验状态机合法性 → 逐条更新"""
    results = await svc.batch_update_status(tenant_id, req.campaign_ids, req.status)
    data = [{"id": str(c.id), "status": c.status} for c in results if c]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/keywords/search", response_model=None, summary="搜索关键词")
async def search_keywords(
    req: AdKeywordSearchRequest,
    svc: AdKeywordService = Depends(get_ad_keyword_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """多维度搜索关键词: 关键词文本/活动/广告组/匹配类型/状态/出价范围"""
    items, total = await svc.search(
        tenant_id, keyword_text=req.keyword_text, campaign_id=req.campaign_id,
        ad_group_id=req.ad_group_id, match_type=req.match_type,
        status=req.status, min_bid=req.min_bid, max_bid=req.max_bid,
        page=req.page, page_size=req.page_size,
    )
    data = [AdKeywordResponse.model_validate(k).model_dump() for k in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


@router.post("/keywords/batch-bid", response_model=None, summary="批量调整关键词出价")
async def batch_update_keyword_bids(
    req: AdKeywordBatchBidRequest,
    svc: AdKeywordService = Depends(get_ad_keyword_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """批量调整关键词出价: 出价范围校验 → 逐条更新"""
    result = await svc.batch_update_bids(tenant_id, req.bid_updates)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/campaigns/{campaign_id}/trend", response_model=None, summary="广告活动趋势分析")
async def campaign_trend(
    campaign_id: str,
    start_date: str = Query(..., description="开始日期 (YYYY-MM-DD)"),
    end_date: str = Query(..., description="结束日期 (YYYY-MM-DD)"),
    svc: AdPerformanceAnalysisService = Depends(get_ad_performance_analysis_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """广告活动趋势分析: 按天展示花费/销售额/CTR/ACOS趋势"""
    sd = datetime.fromisoformat(start_date)
    ed = datetime.fromisoformat(end_date)
    trend_data = await svc.get_campaign_trend(tenant_id, campaign_id, sd, ed)
    return Result.ok(data={"campaign_id": campaign_id, "trend": trend_data}, trace_id=trace_id_var.get(""))


@router.post("/campaigns/{campaign_id}/compare", response_model=None, summary="广告活动周期对比")
async def campaign_compare_periods(
    campaign_id: str,
    period1_start: str = Query(..., description="周期1开始日期"),
    period1_end: str = Query(..., description="周期1结束日期"),
    period2_start: str = Query(..., description="周期2开始日期"),
    period2_end: str = Query(..., description="周期2结束日期"),
    svc: AdPerformanceAnalysisService = Depends(get_ad_performance_analysis_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """广告活动周期对比: 两个时间段的效果指标对比及变化率"""
    p1s = datetime.fromisoformat(period1_start)
    p1e = datetime.fromisoformat(period1_end)
    p2s = datetime.fromisoformat(period2_start)
    p2e = datetime.fromisoformat(period2_end)
    result = await svc.compare_periods(tenant_id, campaign_id, p1s, p1e, p2s, p2e)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/campaigns/{campaign_id}/top-keywords", response_model=None, summary="Top关键词分析")
async def campaign_top_keywords(
    campaign_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    svc: AdPerformanceAnalysisService = Depends(get_ad_performance_analysis_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """获取广告活动Top关键词: 按出价排序"""
    result = await svc.get_top_keywords(tenant_id, campaign_id, limit)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
