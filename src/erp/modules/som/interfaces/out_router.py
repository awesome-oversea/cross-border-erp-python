"""
SOM 模块对外路由 - 供外部系统调用的 API 端点

路径规范: /som/api/out/v1/{resource} (对外暴露接口)
依赖注入: 通过 deps.py 工厂函数获取已注入仓储的服务实例
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from erp.modules.som.application.dtos import (
    AlertCheckRequest,
    ListingOptimizationCreateRequest,
    ListingPriceRequest,
)
from erp.modules.som.interfaces.deps import (
    get_alert_record_service,
    get_optimization_service,
)
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import Result

router = APIRouter(prefix="/som/out/v1", tags=["SOM-Outbound"])


@router.put("/listings/{listing_id}", response_model=None)
async def optimize_listing(listing_id: str, trace_id: str = ""):
    return Result.ok(data={"id": listing_id, "optimized": True}, trace_id=trace_id_var.get(""))


@router.put("/listings/{listing_id}/price", response_model=None)
async def adjust_price(listing_id: str, req: ListingPriceRequest):
    return Result.ok(data={"id": listing_id, "price": req.price, "sale_price": req.sale_price},
                     trace_id=trace_id_var.get(""))


@router.post("/listings/{listing_id}/analyze", response_model=None)
async def out_analyze_listing(listing_id: str, req: ListingOptimizationCreateRequest,
                               svc=Depends(get_optimization_service)):
    opt = await svc.analyze(tenant_id_var.get(""), listing_id, req.opt_type)
    suggestions = json.loads(opt.suggestions_json) if opt.suggestions_json else []
    return Result.ok(data={
        "optimization_id": opt.id,
        "listing_id": opt.listing_id,
        "score_before": opt.score_before,
        "suggestions_count": len(suggestions),
    }, trace_id=trace_id_var.get(""))


@router.get("/listings/{listing_id}/score", response_model=None)
async def out_get_listing_score(listing_id: str, svc=Depends(get_optimization_service)):
    result = await svc.get_listing_score(listing_id, tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/alerts/check", response_model=None)
async def out_check_alerts(req: AlertCheckRequest, svc=Depends(get_alert_record_service)):
    triggered = await svc.check_and_trigger(tenant_id_var.get(""), req.store_id, req.metric_type, req.actual_value)
    data = [{"id": t.id, "rule_name": t.rule_name, "severity": t.severity, "message": t.message}
            for t in triggered]
    return Result.ok(data={"triggered_count": len(triggered), "alerts": data}, trace_id=trace_id_var.get(""))


@router.get("/alerts/summary", response_model=None)
async def out_get_alert_summary(svc=Depends(get_alert_record_service)):
    summary = await svc.get_alert_summary(tenant_id_var.get(""))
    return Result.ok(data=summary, trace_id=trace_id_var.get(""))
