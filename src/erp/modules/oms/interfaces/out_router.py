"""
OMS (订单域) 路由层 — 外部交互

职责: 接收外部系统的HTTP请求 → 参数校验(DTO) → 调用应用服务 → 返回统一响应
禁止: 在此文件定义 Pydantic 模型 / 手动实例化 Service / 编写业务逻辑

API 路径规范:
  - 外部交互: /oms/api/out/v1/{resource}  (如 PMS / WMS / 风控系统调用)
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query

from erp.modules.oms.application.dtos import RiskMarkRequest
from erp.modules.oms.interfaces.deps import get_current_tenant_id, get_sales_order_service
from erp.modules.oms.application.services import SalesOrderService
from erp.shared.context import trace_id_var
from erp.shared.exceptions import NotFoundException, Result

router = APIRouter(prefix="/oms/out/v1", tags=["OMS-Outbound"])


@router.get("/risk-alerts", response_model=None, summary="获取风控预警列表")
async def get_risk_alerts(
    level: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """获取风控预警列表 (供外部风控系统调用)"""
    return Result.ok(data=[], trace_id=trace_id_var.get(""))


@router.put("/orders/{order_id}/risk-mark", response_model=None, summary="标记订单风控等级")
async def mark_order_risk(
    order_id: str, req: RiskMarkRequest,
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """标记订单风控等级 (供外部风控系统调用)"""
    order = await svc.get_by_id(order_id, tenant_id)
    if order is not None:
        order.risk_flags_json = json.dumps(req.risk_flags, default=str)
        order.remark = req.remark or order.remark
        await svc._order_repo.update(order)
    return Result.ok(
        data={"order_id": order_id, "risk_level": req.risk_level, "risk_flags": req.risk_flags, "remark": req.remark},
        trace_id=trace_id_var.get(""),
    )
