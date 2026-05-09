"""
TMS 物流策略路由

提供物流策略的创建、更新、停用、评估、执行及执行日志查询接口。
内部域路径规范: /tms/api/v1/strategies
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query

from erp.modules.tms.application.dtos import (
    StrategyCreateRequest,
    StrategyExecutionRequest,
    StrategyUpdateRequest,
)
from erp.modules.tms.domain.strategy_models import LogisticsStrategyService
from erp.modules.tms.interfaces.deps import get_logistics_strategy_service
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import Result

router = APIRouter(prefix="/tms/v1/strategies", tags=["TMS-LogisticsStrategy"])


@router.post("", response_model=None)
async def create_strategy(
    req: StrategyCreateRequest,
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    """创建物流策略"""
    strategy = await svc.create_strategy(
        tenant_id=tenant_id_var.get(""), strategy_code=req.strategy_code,
        strategy_name=req.strategy_name, strategy_type=req.strategy_type,
        description=req.description, condition=req.condition,
        action=req.action, priority=req.priority,
        effective_from=req.effective_from, effective_to=req.effective_to,
    )
    return Result.ok(
        data={"id": strategy.id, "strategy_code": strategy.strategy_code,
              "strategy_name": strategy.strategy_name, "strategy_type": strategy.strategy_type,
              "priority": strategy.priority, "version": strategy.version},
        trace_id=trace_id_var.get(""),
    )


@router.get("", response_model=None)
async def list_strategies(
    strategy_type: str = Query(default=""),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    """分页查询物流策略列表"""
    strategies, total = await svc.list_strategies(
        tenant_id_var.get(""), strategy_type=strategy_type,
        is_active=is_active, page=page, page_size=page_size,
    )
    data = [{
        "id": s.id, "strategy_code": s.strategy_code, "strategy_name": s.strategy_name,
        "strategy_type": s.strategy_type, "description": s.description,
        "priority": s.priority, "is_active": s.is_active, "version": s.version,
        "effective_from": s.effective_from.isoformat() if s.effective_from else None,
        "effective_to": s.effective_to.isoformat() if s.effective_to else None,
    } for s in strategies]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.put("/{strategy_id}", response_model=None)
async def update_strategy(
    strategy_id: str,
    req: StrategyUpdateRequest,
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    """更新物流策略"""
    strategy = await svc.update_strategy(
        strategy_id, tenant_id_var.get(""),
        strategy_name=req.strategy_name, description=req.description,
        condition=req.condition, action=req.action, priority=req.priority,
    )
    return Result.ok(data={"id": strategy.id, "version": strategy.version}, trace_id=trace_id_var.get(""))


@router.put("/{strategy_id}/deactivate", response_model=None)
async def deactivate_strategy(
    strategy_id: str,
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    """停用物流策略"""
    strategy = await svc.deactivate_strategy(strategy_id, tenant_id_var.get(""))
    return Result.ok(data={"id": strategy.id, "is_active": strategy.is_active}, trace_id=trace_id_var.get(""))


@router.post("/evaluate", response_model=None)
async def evaluate_strategies(
    strategy_type: str = Query(..., min_length=1),
    context: dict = {},
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    """评估物流策略 (根据条件匹配)"""
    matched = await svc.evaluate_strategies(tenant_id_var.get(""), strategy_type, context)
    return Result.ok(data=matched, trace_id=trace_id_var.get(""))


@router.post("/{strategy_id}/execute", response_model=None)
async def execute_strategy(
    strategy_id: str,
    req: StrategyExecutionRequest,
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    """执行物流策略"""
    log = await svc.execute_strategy(
        tenant_id_var.get(""), strategy_id,
        shipment_id=req.shipment_id, order_id=req.order_id,
        context=req.context,
    )
    return Result.ok(
        data={"id": log.id, "strategy_code": log.strategy_code, "result": log.result},
        trace_id=trace_id_var.get(""),
    )


@router.get("/execution-logs", response_model=None)
async def list_execution_logs(
    strategy_type: str = Query(default=""),
    order_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    """分页查询策略执行日志"""
    logs, total = await svc.list_execution_logs(
        tenant_id_var.get(""), strategy_type=strategy_type,
        order_id=order_id, page=page, page_size=page_size,
    )
    data = [{
        "id": log.id, "strategy_code": log.strategy_code, "strategy_type": log.strategy_type,
        "shipment_id": log.shipment_id, "order_id": log.order_id,
        "action_taken": json.loads(log.action_taken),
        "result": log.result, "result_detail": log.result_detail,
        "trace_id": log.trace_id,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    } for log in logs]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/init-defaults", response_model=None)
async def init_default_strategies(
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    """初始化默认物流策略"""
    await svc.init_defaults(tenant_id_var.get(""))
    return Result.ok(data={"message": "Default logistics strategies initialized"}, trace_id=trace_id_var.get(""))
