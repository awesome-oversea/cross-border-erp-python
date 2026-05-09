"""
BI 指标定义路由 - 指标元数据管理 API 端点

路径规范: /api/bi/v1/metric-defs/{resource}
依赖注入: 通过 domain 服务直接操作
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query

from erp.modules.bi.interfaces.deps import get_metric_service
from erp.modules.bi.application.services import BiMetricService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import Result

router = APIRouter(prefix="/bi/v1/metric-defs", tags=["BI-MetricDefs"])


@router.get("", response_model=None)
async def list_metric_defs(category: str = Query(default=""),
                           svc: BiMetricService = Depends(get_metric_service)):
    metrics = await svc.list_by_tenant(tenant_id_var.get(""), category=category or None)
    data = [{"id": m.id, "metric_code": m.metric_code, "metric_name": m.metric_name,
             "metric_category": m.metric_category, "metric_unit": m.metric_unit,
             "refresh_frequency": m.refresh_frequency, "status": m.status} for m in metrics]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))
