"""
OMS (订单域) 路由层 — 订单策略

职责: 接收HTTP请求 → 参数校验(DTO) → 调用策略服务 → 返回统一响应
禁止: 在此文件定义 Pydantic 模型 / 手动实例化 Service / 编写业务逻辑

API 路径规范:
  - 内部域: /oms/api/v1/strategies/{resource}
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query

from erp.modules.oms.application.dtos import (
    StrategyCreateRequest,
    StrategyEvaluateRequest,
    StrategyExecuteRequest,
    StrategyUpdateRequest,
)
from erp.modules.oms.domain.strategy_models import OrderStrategyService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

router = APIRouter(prefix="/oms/v1/strategies", tags=["OMS-OrderStrategy"])


@router.post("", response_model=None, summary="创建订单策略")
async def create_strategy(
    req: StrategyCreateRequest,
    session=Depends(get_db_session),
    tenant_id: str = Depends(lambda: tenant_id_var.get("")),
):
    """创建订单策略: 唯一性校验(strategy_code) → 持久化"""
    svc = OrderStrategyService(session)
    strategy = await svc.create_strategy(
        tenant_id=tenant_id, strategy_code=req.strategy_code,
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


@router.get("", response_model=None, summary="查询策略列表")
async def list_strategies(
    strategy_type: str = Query(default=""),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session=Depends(get_db_session),
    tenant_id: str = Depends(lambda: tenant_id_var.get("")),
):
    """分页查询策略列表"""
    svc = OrderStrategyService(session)
    strategies, total = await svc.list_strategies(
        tenant_id, strategy_type=strategy_type,
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


@router.get("/{strategy_id}", response_model=None, summary="查询策略详情")
async def get_strategy(
    strategy_id: str,
    session=Depends(get_db_session),
    tenant_id: str = Depends(lambda: tenant_id_var.get("")),
):
    """查询策略详情 (含条件/动作JSON)"""
    svc = OrderStrategyService(session)
    strategies, _ = await svc.list_strategies(tenant_id, page=1, page_size=1)
    strategy = next((s for s in strategies if s.id == strategy_id), None)
    if not strategy:
        return Result.fail(code=404, message="Strategy not found", trace_id=trace_id_var.get(""))
    return Result.ok(
        data={
            "id": strategy.id, "strategy_code": strategy.strategy_code,
            "strategy_name": strategy.strategy_name, "strategy_type": strategy.strategy_type,
            "description": strategy.description,
            "condition": json.loads(strategy.condition_json),
            "action": json.loads(strategy.action_json),
            "priority": strategy.priority, "is_active": strategy.is_active,
            "version": strategy.version,
        },
        trace_id=trace_id_var.get(""),
    )


@router.put("/{strategy_id}", response_model=None, summary="更新策略")
async def update_strategy(
    strategy_id: str, req: StrategyUpdateRequest,
    session=Depends(get_db_session),
    tenant_id: str = Depends(lambda: tenant_id_var.get("")),
):
    """更新策略: 版本号自增"""
    svc = OrderStrategyService(session)
    strategy = await svc.update_strategy(
        strategy_id, tenant_id,
        strategy_name=req.strategy_name, description=req.description,
        condition=req.condition, action=req.action, priority=req.priority,
        effective_from=req.effective_from, effective_to=req.effective_to,
    )
    return Result.ok(
        data={"id": strategy.id, "version": strategy.version},
        trace_id=trace_id_var.get(""),
    )


@router.put("/{strategy_id}/deactivate", response_model=None, summary="停用策略")
async def deactivate_strategy(
    strategy_id: str,
    session=Depends(get_db_session),
    tenant_id: str = Depends(lambda: tenant_id_var.get("")),
):
    """停用策略: is_active → False"""
    svc = OrderStrategyService(session)
    strategy = await svc.deactivate_strategy(strategy_id, tenant_id)
    return Result.ok(data={"id": strategy.id, "is_active": strategy.is_active}, trace_id=trace_id_var.get(""))


@router.post("/evaluate", response_model=None, summary="评估策略")
async def evaluate_strategies(
    req: StrategyEvaluateRequest,
    session=Depends(get_db_session),
    tenant_id: str = Depends(lambda: tenant_id_var.get("")),
):
    """评估策略: 条件匹配 → 返回匹配的策略列表"""
    svc = OrderStrategyService(session)
    matched = await svc.evaluate_strategies(tenant_id, req.strategy_type, req.context)
    return Result.ok(data=matched, trace_id=trace_id_var.get(""))


@router.post("/{strategy_id}/execute", response_model=None, summary="执行策略")
async def execute_strategy(
    strategy_id: str, req: StrategyExecuteRequest,
    session=Depends(get_db_session),
    tenant_id: str = Depends(lambda: tenant_id_var.get("")),
):
    """执行策略: 记录执行日志"""
    svc = OrderStrategyService(session)
    log = await svc.execute_strategy(
        tenant_id, strategy_id,
        order_id=req.order_id, order_no=req.order_no,
        context=req.context,
    )
    return Result.ok(
        data={"id": log.id, "strategy_code": log.strategy_code,
              "order_id": log.order_id, "result": log.result},
        trace_id=trace_id_var.get(""),
    )


@router.get("/execution-logs", response_model=None, summary="查询执行日志")
async def list_execution_logs(
    strategy_type: str = Query(default=""),
    order_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session=Depends(get_db_session),
    tenant_id: str = Depends(lambda: tenant_id_var.get("")),
):
    """分页查询策略执行日志"""
    svc = OrderStrategyService(session)
    logs, total = await svc.list_execution_logs(
        tenant_id, strategy_type=strategy_type,
        order_id=order_id, page=page, page_size=page_size,
    )
    data = [{
        "id": log.id, "strategy_code": log.strategy_code, "strategy_type": log.strategy_type,
        "order_id": log.order_id, "order_no": log.order_no,
        "matched_conditions": json.loads(log.matched_conditions),
        "action_taken": json.loads(log.action_taken),
        "result": log.result, "result_detail": log.result_detail,
        "trace_id": log.trace_id,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    } for log in logs]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/init-defaults", response_model=None, summary="初始化默认策略")
async def init_default_strategies(
    session=Depends(get_db_session),
    tenant_id: str = Depends(lambda: tenant_id_var.get("")),
):
    """初始化默认订单策略 (审核/拆合/利润/风控)"""
    svc = OrderStrategyService(session)
    await svc.init_defaults(tenant_id)
    return Result.ok(data={"message": "Default order strategies initialized"}, trace_id=trace_id_var.get(""))
