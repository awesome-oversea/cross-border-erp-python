"""
SOM 模块内部路由 - 销售运营域 API 端点

路径规范: /api/som/v1/{resource} (内部域子系统, main.py 注册 prefix=/api)
依赖注入: 通过 deps.py 工厂函数获取已注入仓储的服务实例
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from erp.modules.som.application.dtos import (
    AlertBatchActionRequest,
    AlertCheckRequest,
    AlertRuleCreateRequest,
    AlertRuleUpdateRequest,
    BatchJobCreateRequest,
    ListingBulkStatusRequest,
    ListingCreateRequest,
    ListingDuplicateRequest,
    ListingOptimizationApplyRequest,
    ListingOptimizationCreateRequest,
    ListingPlatformStatusRequest,
    ListingPriceRequest,
    ListingSearchRequest,
    ListingStatusRequest,
    ListingUpdateRequest,
    OperationMonitorRequest,
    PriceCalculateRequest,
    PriceRuleCreateRequest,
    PriceRuleUpdateRequest,
    StoreAuthRequest,
    StoreCreateRequest,
    StoreUpdateRequest,
)
from erp.modules.som.application.services import (
    LISTING_STATUS_ON_PLATFORM,
    LISTING_STATUS_TRANSITIONS,
    STORE_AUTH_STATUS_TRANSITIONS,
    AlertRecordService,
    AlertRuleService,
    ListingBatchJobService,
    ListingOptimizationService,
    ListingService,
    OperationMonitorService,
    PriceRuleService,
    StoreService,
)
from erp.modules.som.interfaces.deps import (
    get_alert_record_service,
    get_alert_rule_service,
    get_batch_job_service,
    get_listing_service,
    get_operation_monitor_service,
    get_optimization_service,
    get_price_rule_service,
    get_store_service,
)
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from datetime import datetime

router = APIRouter(prefix="/som/v1", tags=["SOM - 销售运营域"])


# ──── 店铺管理 ────


@router.post("/stores", response_model=None)
async def create_store(req: StoreCreateRequest, svc: StoreService = Depends(get_store_service)):
    store = await svc.create(tenant_id_var.get(""), name=req.name, code=req.code, platform=req.platform,
                             region=req.region, store_id_on_platform=req.store_id_on_platform,
                             seller_id=req.seller_id, currency=req.currency, org_id=req.org_id)
    return Result.ok(data={"id": store.id, "code": store.code, "platform": store.platform, "auth_status": store.auth_status}, trace_id=trace_id_var.get(""))


@router.get("/stores", response_model=None)
async def list_stores(platform: str = Query(default=""), page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                      svc: StoreService = Depends(get_store_service)):
    items, total = await svc.list_all(tenant_id_var.get(""), platform=platform, page=page, page_size=page_size)
    data = [{"id": s.id, "name": s.name, "code": s.code, "platform": s.platform, "status": s.status, "region": s.region, "auth_status": s.auth_status} for s in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.put("/stores/{store_id}/auth-status", response_model=None)
async def update_store_auth_status(store_id: str, req: StoreAuthRequest, svc: StoreService = Depends(get_store_service)):
    store = await svc.update_auth_status(store_id, tenant_id_var.get(""), req.new_auth_status,
                                         auth_token_encrypted=req.auth_token_encrypted,
                                         auth_expires_at=req.auth_expires_at)
    return Result.ok(data={"id": store.id, "auth_status": store.auth_status}, trace_id=trace_id_var.get(""))


@router.delete("/stores/{store_id}", response_model=None)
async def delete_store(store_id: str, svc: StoreService = Depends(get_store_service)):
    store = await svc.soft_delete(store_id, tenant_id_var.get(""))
    return Result.ok(data={"id": store.id, "deleted_at": str(store.deleted_at)}, trace_id=trace_id_var.get(""))


@router.get("/stores/auth-transitions", response_model=None)
async def get_store_auth_transitions():
    return Result.ok(data=STORE_AUTH_STATUS_TRANSITIONS, trace_id=trace_id_var.get(""))


@router.get("/stores/{store_id}", response_model=None)
async def get_store(store_id: str, svc: StoreService = Depends(get_store_service)):
    store = await svc.get_or_raise(store_id, tenant_id_var.get(""))
    return Result.ok(data={
        "id": store.id, "name": store.name, "code": store.code, "platform": store.platform,
        "region": store.region, "store_id_on_platform": store.store_id_on_platform,
        "seller_id": store.seller_id, "currency": store.currency, "status": store.status,
        "auth_status": store.auth_status,
        "auth_expires_at": str(store.auth_expires_at) if store.auth_expires_at else None,
        "org_id": store.org_id, "created_at": str(store.created_at), "updated_at": str(store.updated_at),
    }, trace_id=trace_id_var.get(""))


@router.put("/stores/{store_id}", response_model=None)
async def update_store(store_id: str, req: StoreUpdateRequest, svc: StoreService = Depends(get_store_service)):
    kwargs = {}
    for field_name in ["name", "region", "currency", "status"]:
        val = getattr(req, field_name, None)
        if val is not None:
            kwargs[field_name] = val
    store = await svc.update(store_id, tenant_id_var.get(""), **kwargs)
    return Result.ok(data={"id": store.id, "name": store.name, "status": store.status}, trace_id=trace_id_var.get(""))


@router.get("/stores/statistics/overview", response_model=None)
async def get_store_statistics(svc: StoreService = Depends(get_store_service)):
    data = await svc.get_statistics(tenant_id_var.get(""))
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


# ──── Listing 管理 ────


@router.post("/listings", response_model=None)
async def create_listing(req: ListingCreateRequest, svc: ListingService = Depends(get_listing_service)):
    listing = await svc.create(
        tenant_id_var.get(""), store_id=req.store_id, sku_id=req.sku_id,
        channel_sku=req.channel_sku, title=req.title, title_en=req.title_en,
        description=req.description, bullet_points_json=json.dumps(req.bullet_points, default=str),
        search_terms=req.search_terms, main_image=req.main_image,
        images_json=json.dumps(req.images, default=str),
        price=req.price, currency=req.currency, msrp=req.msrp, sale_price=req.sale_price,
        quantity=req.quantity, platform=req.platform, category_id=req.category_id,
    )
    return Result.ok(data={"id": listing.id, "status": listing.status, "listing_status": listing.listing_status}, trace_id=trace_id_var.get(""))


@router.get("/listings", response_model=None)
async def list_listings(store_id: str = Query(default=""), status: str = Query(default=""),
                        page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                        svc: ListingService = Depends(get_listing_service)):
    items, total = await svc.list_all(tenant_id_var.get(""), store_id=store_id, status=status, page=page, page_size=page_size)
    data = [{"id": item.id, "store_id": item.store_id, "sku_id": item.sku_id, "title": item.title, "price": item.price, "status": item.status, "listing_status": item.listing_status} for item in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/listings/{listing_id}", response_model=None)
async def get_listing(listing_id: str, svc: ListingService = Depends(get_listing_service)):
    listing = await svc.get_or_raise(listing_id, tenant_id_var.get(""))
    return Result.ok(data={
        "id": listing.id, "store_id": listing.store_id, "sku_id": listing.sku_id,
        "title": listing.title, "price": listing.price, "sale_price": listing.sale_price,
        "status": listing.status, "listing_status": listing.listing_status,
        "is_pms_draft": listing.is_pms_draft, "recommendation_id": listing.recommendation_id,
        "quantity": listing.quantity, "published_at": str(listing.published_at) if listing.published_at else None,
        "images": json.loads(listing.images_json) if listing.images_json else [],
    }, trace_id=trace_id_var.get(""))


@router.put("/listings/{listing_id}/price", response_model=None)
async def update_listing_price(listing_id: str, req: ListingPriceRequest, svc: ListingService = Depends(get_listing_service)):
    listing = await svc.update_price(listing_id, tenant_id_var.get(""), price=req.price, sale_price=req.sale_price)
    return Result.ok(data={"id": listing.id, "price": listing.price, "sale_price": listing.sale_price}, trace_id=trace_id_var.get(""))


@router.put("/listings/{listing_id}/status", response_model=None)
async def update_listing_status(listing_id: str, req: ListingStatusRequest, svc: ListingService = Depends(get_listing_service)):
    listing = await svc.update_status(listing_id, tenant_id_var.get(""), req.status)
    return Result.ok(data={"id": listing.id, "status": listing.status, "listing_status": listing.listing_status}, trace_id=trace_id_var.get(""))


@router.put("/listings/{listing_id}/platform-status", response_model=None)
async def update_listing_platform_status(listing_id: str, req: ListingPlatformStatusRequest, svc: ListingService = Depends(get_listing_service)):
    listing = await svc.update_listing_status(listing_id, tenant_id_var.get(""), req.listing_status)
    return Result.ok(data={"id": listing.id, "listing_status": listing.listing_status}, trace_id=trace_id_var.get(""))


@router.post("/listings/{listing_id}/apply-price-rule", response_model=None)
async def apply_price_rule_to_listing(listing_id: str, rule_id: str = Query(...), svc: ListingService = Depends(get_listing_service)):
    listing = await svc.apply_price_rule(listing_id, tenant_id_var.get(""), rule_id)
    return Result.ok(data={"id": listing.id, "price": listing.price}, trace_id=trace_id_var.get(""))


@router.post("/listings/batch-status", response_model=None)
async def batch_update_listing_status(listing_ids: list[str], status: str = Query(...), svc: ListingService = Depends(get_listing_service)):
    result = await svc.batch_update_status(tenant_id_var.get(""), listing_ids, status)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/listings/status-transitions", response_model=None)
async def get_listing_status_transitions():
    return Result.ok(data=LISTING_STATUS_TRANSITIONS, trace_id=trace_id_var.get(""))


@router.get("/listings/platform-status-transitions", response_model=None)
async def get_listing_platform_status_transitions():
    return Result.ok(data=LISTING_STATUS_ON_PLATFORM, trace_id=trace_id_var.get(""))


@router.put("/listings/{listing_id}", response_model=None)
async def update_listing(listing_id: str, req: ListingUpdateRequest, svc: ListingService = Depends(get_listing_service)):
    kwargs = {}
    for field_name in ["title", "title_en", "description", "bullet_points", "search_terms",
                        "main_image", "images", "quantity", "category_id", "platform", "channel_sku"]:
        val = getattr(req, field_name, None)
        if val is not None:
            kwargs[field_name] = val
    listing = await svc.update(listing_id, tenant_id_var.get(""), **kwargs)
    return Result.ok(data={"id": listing.id, "title": listing.title, "status": listing.status}, trace_id=trace_id_var.get(""))


@router.delete("/listings/{listing_id}", response_model=None)
async def delete_listing(listing_id: str, svc: ListingService = Depends(get_listing_service)):
    listing = await svc.soft_delete(listing_id, tenant_id_var.get(""))
    return Result.ok(data={"id": listing.id, "deleted_at": str(listing.deleted_at)}, trace_id=trace_id_var.get(""))


@router.post("/listings/{listing_id}/duplicate", response_model=None)
async def duplicate_listing(listing_id: str, req: ListingDuplicateRequest, svc: ListingService = Depends(get_listing_service)):
    listing = await svc.duplicate(
        listing_id, tenant_id_var.get(""),
        target_store_id=req.target_store_id, copy_images=req.copy_images,
        copy_price=req.copy_price, new_title=req.new_title,
    )
    return Result.ok(data={"id": listing.id, "title": listing.title, "status": listing.status}, trace_id=trace_id_var.get(""))


@router.post("/listings/search", response_model=None)
async def search_listings(req: ListingSearchRequest, svc: ListingService = Depends(get_listing_service)):
    items, total = await svc.search(
        tenant_id_var.get(""), keyword=req.keyword, store_id=req.store_id,
        platform=req.platform, status=req.status, listing_status=req.listing_status,
        min_price=req.min_price, max_price=req.max_price,
        page=req.page, page_size=req.page_size,
    )
    data = [{"id": item.id, "store_id": item.store_id, "sku_id": item.sku_id,
             "title": item.title, "price": item.price, "status": item.status,
             "listing_status": item.listing_status, "platform": item.platform,
             "quantity": item.quantity} for item in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


@router.get("/listings/statistics/overview", response_model=None)
async def get_listing_statistics(svc: ListingService = Depends(get_listing_service)):
    data = await svc.get_statistics(tenant_id_var.get(""))
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


# ──── 价格规则 ────


@router.post("/price-rules", response_model=None)
async def create_price_rule(req: PriceRuleCreateRequest, svc: PriceRuleService = Depends(get_price_rule_service)):
    rule = await svc.create(tenant_id_var.get(""), name=req.name, rule_type=req.rule_type,
                            platform=req.platform, region=req.region, category_id=req.category_id,
                            formula_json=json.dumps(req.formula, default=str),
                            min_price=req.min_price, max_price=req.max_price,
                            currency=req.currency, priority=req.priority)
    return Result.ok(data={"id": rule.id, "name": rule.name, "rule_type": rule.rule_type}, trace_id=trace_id_var.get(""))


@router.get("/price-rules", response_model=None)
async def list_price_rules(platform: str = Query(default=""), page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                           svc: PriceRuleService = Depends(get_price_rule_service)):
    items, total = await svc.list_all(tenant_id_var.get(""), platform=platform, page=page, page_size=page_size)
    data = [{"id": r.id, "name": r.name, "rule_type": r.rule_type, "platform": r.platform, "status": r.status, "priority": r.priority} for r in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/price-rules/{rule_id}", response_model=None)
async def get_price_rule(rule_id: str, svc: PriceRuleService = Depends(get_price_rule_service)):
    rule = await svc.get_or_raise(rule_id, tenant_id_var.get(""))
    return Result.ok(data={
        "id": rule.id, "name": rule.name, "rule_type": rule.rule_type,
        "platform": rule.platform, "region": rule.region, "category_id": rule.category_id,
        "formula": json.loads(rule.formula_json) if rule.formula_json else {},
        "min_price": rule.min_price, "max_price": rule.max_price,
        "currency": rule.currency, "priority": rule.priority, "status": rule.status,
        "created_at": str(rule.created_at), "updated_at": str(rule.updated_at),
    }, trace_id=trace_id_var.get(""))


@router.put("/price-rules/{rule_id}", response_model=None)
async def update_price_rule(rule_id: str, req: PriceRuleUpdateRequest, svc: PriceRuleService = Depends(get_price_rule_service)):
    kwargs = {}
    for field_name in ["name", "formula", "min_price", "max_price", "priority", "status"]:
        val = getattr(req, field_name, None)
        if val is not None:
            kwargs[field_name if field_name != "formula" else "formula_json"] = json.dumps(val, default=str) if field_name == "formula" else val
    rule = await svc.update(rule_id, tenant_id_var.get(""), **kwargs)
    return Result.ok(data={"id": rule.id, "name": rule.name, "rule_type": rule.rule_type, "status": rule.status}, trace_id=trace_id_var.get(""))


@router.post("/price-rules/calculate", response_model=None)
async def calculate_price(req: PriceCalculateRequest, svc: PriceRuleService = Depends(get_price_rule_service)):
    result = await svc.calculate_price(tenant_id_var.get(""), cost_price=req.cost_price,
                                       platform=req.platform, region=req.region, category_id=req.category_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/price-rules/batch-apply", response_model=None)
async def batch_apply_price_rule(listing_ids: list[str], rule_id: str = Query(...), svc: PriceRuleService = Depends(get_price_rule_service)):
    result = await svc.batch_apply(tenant_id_var.get(""), listing_ids, rule_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


# ──── 批量任务 ────


@router.post("/batch-jobs", response_model=None)
async def create_batch_job(req: BatchJobCreateRequest, svc: ListingBatchJobService = Depends(get_batch_job_service)):
    job = await svc.create_job(tenant_id_var.get(""), req.job_type, req.listing_ids)
    return Result.ok(data={"id": job.id, "job_type": job.job_type, "total_count": job.total_count, "status": job.status}, trace_id=trace_id_var.get(""))


@router.post("/batch-jobs/{job_id}/execute", response_model=None)
async def execute_batch_job(job_id: str, svc: ListingBatchJobService = Depends(get_batch_job_service)):
    job = await svc.execute_job(job_id, tenant_id_var.get(""))
    return Result.ok(data={"id": job.id, "status": job.status, "success_count": job.success_count, "fail_count": job.fail_count}, trace_id=trace_id_var.get(""))


@router.get("/batch-jobs", response_model=None)
async def list_batch_jobs(status: str = Query(default=""), page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                          svc: ListingBatchJobService = Depends(get_batch_job_service)):
    items, total = await svc.list_jobs(tenant_id_var.get(""), status=status, page=page, page_size=page_size)
    data = [{"id": j.id, "job_type": j.job_type, "total_count": j.total_count,
             "success_count": j.success_count, "fail_count": j.fail_count,
             "status": j.status, "created_at": str(j.created_at)} for j in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/batch-jobs/{job_id}/cancel", response_model=None)
async def cancel_batch_job(job_id: str, svc: ListingBatchJobService = Depends(get_batch_job_service)):
    job = await svc.cancel_job(job_id, tenant_id_var.get(""))
    return Result.ok(data={"id": job.id, "status": job.status}, trace_id=trace_id_var.get(""))


# ──── 运营监控 ────


@router.post("/metrics", response_model=None)
async def record_metrics(req: OperationMonitorRequest, svc: OperationMonitorService = Depends(get_operation_monitor_service)):
    monitor = await svc.record_metrics(tenant_id_var.get(""), req.store_id, req.metric_type, req.metric_date, req.metrics)
    return Result.ok(data={"id": monitor.id, "metric_type": monitor.metric_type}, trace_id=trace_id_var.get(""))


@router.get("/metrics", response_model=None)
async def get_metrics(store_id: str = Query(default=""), metric_type: str = Query(default=""),
                      start_date: datetime | None = None, end_date: datetime | None = None,
                      page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                      svc: OperationMonitorService = Depends(get_operation_monitor_service)):
    items, total = await svc.get_metrics(tenant_id_var.get(""), store_id=store_id, metric_type=metric_type,
                                         start_date=start_date, end_date=end_date, page=page, page_size=page_size)
    data = [{"id": m.id, "store_id": m.store_id, "metric_type": m.metric_type,
             "metric_date": str(m.metric_date), "metrics": json.loads(m.metrics_json)} for m in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/metrics/summary", response_model=None)
async def get_metrics_summary(store_id: str = Query(default=""), metric_type: str = Query(default=""),
                               start_date: datetime | None = None, end_date: datetime | None = None,
                               svc: OperationMonitorService = Depends(get_operation_monitor_service)):
    result = await svc.get_metrics_summary(tenant_id_var.get(""), store_id=store_id, metric_type=metric_type,
                                            start_date=start_date, end_date=end_date)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


# ──── Listing 优化 ────


@router.post("/optimizations/analyze", response_model=None)
async def analyze_listing_optimization(req: ListingOptimizationCreateRequest, svc: ListingOptimizationService = Depends(get_optimization_service)):
    opt = await svc.analyze(tenant_id_var.get(""), req.listing_id, req.opt_type)
    suggestions = json.loads(opt.suggestions_json) if opt.suggestions_json else []
    return Result.ok(data={
        "id": opt.id, "listing_id": opt.listing_id, "opt_type": opt.opt_type,
        "status": opt.status, "score_before": opt.score_before,
        "suggestions_count": len(suggestions), "suggestions": suggestions,
    }, trace_id=trace_id_var.get(""))


@router.get("/optimizations", response_model=None)
async def list_optimizations(listing_id: str = Query(default=""), opt_type: str = Query(default=""),
                              status: str = Query(default=""),
                              page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                              svc: ListingOptimizationService = Depends(get_optimization_service)):
    items, total = await svc.list_all(tenant_id_var.get(""), listing_id=listing_id, opt_type=opt_type,
                                       status=status, page=page, page_size=page_size)
    data = [{"id": o.id, "listing_id": o.listing_id, "opt_type": o.opt_type, "status": o.status,
             "score_before": o.score_before, "score_after": o.score_after,
             "created_at": str(o.created_at)} for o in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/optimizations/{optimization_id}", response_model=None)
async def get_optimization(optimization_id: str, svc: ListingOptimizationService = Depends(get_optimization_service)):
    opt = await svc.get_or_raise(optimization_id, tenant_id_var.get(""))
    return Result.ok(data={
        "id": opt.id, "listing_id": opt.listing_id, "opt_type": opt.opt_type, "status": opt.status,
        "score_before": opt.score_before, "score_after": opt.score_after,
        "suggestions": json.loads(opt.suggestions_json) if opt.suggestions_json else [],
        "applied_suggestions": json.loads(opt.applied_suggestions_json) if opt.applied_suggestions_json else [],
        "snapshot_before": json.loads(opt.snapshot_before_json) if opt.snapshot_before_json else {},
        "snapshot_after": json.loads(opt.snapshot_after_json) if opt.snapshot_after_json else {},
        "created_at": str(opt.created_at), "updated_at": str(opt.updated_at),
    }, trace_id=trace_id_var.get(""))


@router.post("/optimizations/{optimization_id}/apply", response_model=None)
async def apply_optimization_suggestions(optimization_id: str, req: ListingOptimizationApplyRequest,
                                          svc: ListingOptimizationService = Depends(get_optimization_service)):
    opt = await svc.apply_suggestions(optimization_id, tenant_id_var.get(""), req.suggestion_indices)
    return Result.ok(data={
        "id": opt.id, "status": opt.status,
        "score_before": opt.score_before, "score_after": opt.score_after,
    }, trace_id=trace_id_var.get(""))


@router.post("/optimizations/{optimization_id}/cancel", response_model=None)
async def cancel_optimization(optimization_id: str, svc: ListingOptimizationService = Depends(get_optimization_service)):
    opt = await svc.cancel(optimization_id, tenant_id_var.get(""))
    return Result.ok(data={"id": opt.id, "status": opt.status}, trace_id=trace_id_var.get(""))


@router.get("/listings/{listing_id}/score", response_model=None)
async def get_listing_score(listing_id: str, svc: ListingOptimizationService = Depends(get_optimization_service)):
    result = await svc.get_listing_score(listing_id, tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


# ──── 告警规则 ────


@router.post("/alert-rules", response_model=None)
async def create_alert_rule(req: AlertRuleCreateRequest, svc: AlertRuleService = Depends(get_alert_rule_service)):
    rule = await svc.create(
        tenant_id_var.get(""), name=req.name, metric_type=req.metric_type,
        condition_type=req.condition_type, threshold=req.threshold,
        threshold_max=req.threshold_max, time_window=req.time_window,
        severity=req.severity, notify_channels=req.notify_channels,
        notify_targets=req.notify_targets, platform=req.platform,
        store_id=req.store_id, cooldown_minutes=req.cooldown_minutes,
    )
    return Result.ok(data={"id": rule.id, "name": rule.name, "metric_type": rule.metric_type,
                           "condition_type": rule.condition_type, "severity": rule.severity,
                           "status": rule.status}, trace_id=trace_id_var.get(""))


@router.get("/alert-rules", response_model=None)
async def list_alert_rules(metric_type: str = Query(default=""), severity: str = Query(default=""),
                            status: str = Query(default=""),
                            page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                            svc: AlertRuleService = Depends(get_alert_rule_service)):
    items, total = await svc.list_all(tenant_id_var.get(""), metric_type=metric_type, severity=severity,
                                       status=status, page=page, page_size=page_size)
    data = [{"id": r.id, "name": r.name, "metric_type": r.metric_type, "condition_type": r.condition_type,
             "threshold": r.threshold, "severity": r.severity, "status": r.status,
             "notify_channels": r.notify_channels} for r in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/alert-rules/{rule_id}", response_model=None)
async def get_alert_rule(rule_id: str, svc: AlertRuleService = Depends(get_alert_rule_service)):
    rule = await svc.get_or_raise(rule_id, tenant_id_var.get(""))
    return Result.ok(data={
        "id": rule.id, "name": rule.name, "metric_type": rule.metric_type,
        "condition_type": rule.condition_type, "threshold": rule.threshold,
        "threshold_max": rule.threshold_max, "time_window": rule.time_window,
        "severity": rule.severity, "notify_channels": rule.notify_channels,
        "notify_targets": json.loads(rule.notify_targets_json) if rule.notify_targets_json else [],
        "platform": rule.platform, "store_id": rule.store_id,
        "cooldown_minutes": rule.cooldown_minutes, "status": rule.status,
    }, trace_id=trace_id_var.get(""))


@router.put("/alert-rules/{rule_id}", response_model=None)
async def update_alert_rule(rule_id: str, req: AlertRuleUpdateRequest, svc: AlertRuleService = Depends(get_alert_rule_service)):
    kwargs = {}
    for field_name in ["name", "metric_type", "condition_type", "threshold", "threshold_max",
                        "time_window", "severity", "notify_channels", "notify_targets",
                        "platform", "store_id", "cooldown_minutes"]:
        val = getattr(req, field_name, None)
        if val is not None:
            kwargs[field_name] = val
    rule = await svc.update(rule_id, tenant_id_var.get(""), **kwargs)
    return Result.ok(data={"id": rule.id, "name": rule.name, "status": rule.status}, trace_id=trace_id_var.get(""))


@router.post("/alert-rules/{rule_id}/toggle", response_model=None)
async def toggle_alert_rule(rule_id: str, svc: AlertRuleService = Depends(get_alert_rule_service)):
    rule = await svc.toggle_status(rule_id, tenant_id_var.get(""))
    return Result.ok(data={"id": rule.id, "status": rule.status}, trace_id=trace_id_var.get(""))


@router.delete("/alert-rules/{rule_id}", response_model=None)
async def delete_alert_rule(rule_id: str, svc: AlertRuleService = Depends(get_alert_rule_service)):
    rule = await svc.delete(rule_id, tenant_id_var.get(""))
    return Result.ok(data={"id": rule.id, "status": rule.status}, trace_id=trace_id_var.get(""))


# ──── 告警记录 ────


@router.get("/alert-records", response_model=None)
async def list_alert_records(rule_id: str = Query(default=""), severity: str = Query(default=""),
                              status: str = Query(default=""), store_id: str = Query(default=""),
                              page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                              svc: AlertRecordService = Depends(get_alert_record_service)):
    items, total = await svc.list_all(tenant_id_var.get(""), rule_id=rule_id, severity=severity,
                                       status=status, store_id=store_id, page=page, page_size=page_size)
    data = [{"id": r.id, "rule_id": r.rule_id, "rule_name": r.rule_name, "store_id": r.store_id,
             "metric_type": r.metric_type, "severity": r.severity, "actual_value": r.actual_value,
             "threshold_value": r.threshold_value, "message": r.message, "status": r.status,
             "created_at": str(r.created_at)} for r in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/alert-records/{record_id}", response_model=None)
async def get_alert_record(record_id: str, svc: AlertRecordService = Depends(get_alert_record_service)):
    record = await svc.get_or_raise(record_id, tenant_id_var.get(""))
    return Result.ok(data={
        "id": record.id, "rule_id": record.rule_id, "rule_name": record.rule_name,
        "store_id": record.store_id, "metric_type": record.metric_type,
        "severity": record.severity, "actual_value": record.actual_value,
        "threshold_value": record.threshold_value, "message": record.message,
        "detail": json.loads(record.detail_json) if record.detail_json else {},
        "status": record.status, "notified": record.notified,
        "acknowledged_by": record.acknowledged_by,
        "acknowledged_at": str(record.acknowledged_at) if record.acknowledged_at else None,
        "resolved_at": str(record.resolved_at) if record.resolved_at else None,
        "created_at": str(record.created_at),
    }, trace_id=trace_id_var.get(""))


@router.post("/alert-records/{record_id}/acknowledge", response_model=None)
async def acknowledge_alert(record_id: str, svc: AlertRecordService = Depends(get_alert_record_service)):
    record = await svc.acknowledge(record_id, tenant_id_var.get(""))
    return Result.ok(data={"id": record.id, "status": record.status}, trace_id=trace_id_var.get(""))


@router.post("/alert-records/{record_id}/resolve", response_model=None)
async def resolve_alert(record_id: str, svc: AlertRecordService = Depends(get_alert_record_service)):
    record = await svc.resolve(record_id, tenant_id_var.get(""))
    return Result.ok(data={"id": record.id, "status": record.status}, trace_id=trace_id_var.get(""))


@router.post("/alert-records/batch-acknowledge", response_model=None)
async def batch_acknowledge_alerts(req: AlertBatchActionRequest, svc: AlertRecordService = Depends(get_alert_record_service)):
    result = await svc.batch_acknowledge(tenant_id_var.get(""), req.record_ids)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/alert-records/batch-resolve", response_model=None)
async def batch_resolve_alerts(req: AlertBatchActionRequest, svc: AlertRecordService = Depends(get_alert_record_service)):
    result = await svc.batch_resolve(tenant_id_var.get(""), req.record_ids)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/alert-records/check", response_model=None)
async def check_and_trigger_alerts(req: AlertCheckRequest, svc: AlertRecordService = Depends(get_alert_record_service)):
    triggered = await svc.check_and_trigger(tenant_id_var.get(""), req.store_id, req.metric_type, req.actual_value)
    data = [{"id": t.id, "rule_name": t.rule_name, "severity": t.severity, "message": t.message}
            for t in triggered]
    return Result.ok(data={"triggered_count": len(triggered), "alerts": data}, trace_id=trace_id_var.get(""))


@router.get("/alert-records/summary", response_model=None)
async def get_alert_summary(svc: AlertRecordService = Depends(get_alert_record_service)):
    summary = await svc.get_alert_summary(tenant_id_var.get(""))
    return Result.ok(data=summary, trace_id=trace_id_var.get(""))
