"""
BI 模块外部路由 - 供外部系统调用的 API 端点

路径规范: /api/bi/out/v1/{resource} (外部子系统, main.py 注册 prefix=/api)
依赖注入: 通过 deps.py 工厂函数获取已注入仓储的服务实例
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from erp.modules.bi.application.services import BiMetricService, BiMetricValueService, BiReportService
from erp.modules.bi.interfaces.deps import get_metric_service, get_metric_value_service, get_report_service
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import Result

router = APIRouter(prefix="/bi/out/v1", tags=["BI-Outbound"])


class MetricValuePushRequest(BaseModel):
    metric_code: str = Field(..., min_length=1)
    period_type: str = "daily"
    period_date: str
    numeric_value: float = 0.0
    text_value: str = ""
    store_id: str = ""
    platform: str = ""
    dimension_json: str = "{}"


class ReportDataQueryRequest(BaseModel):
    report_code: str = Field(..., min_length=1)
    filters_json: str = "{}"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


@router.post("/metric-values", response_model=None)
async def push_metric_value(req: MetricValuePushRequest, svc: BiMetricValueService = Depends(get_metric_value_service)):
    val = await svc.record(
        tenant_id_var.get(""), metric_id="", metric_code=req.metric_code,
        period_type=req.period_type, period_date=datetime.fromisoformat(req.period_date),
        numeric_value=req.numeric_value, text_value=req.text_value,
        store_id=req.store_id, platform=req.platform, dimension_json=req.dimension_json,
    )
    return Result.ok(data={"id": val.id, "metric_code": req.metric_code, "numeric_value": val.numeric_value},
                     trace_id=trace_id_var.get(""))


@router.post("/report-data", response_model=None)
async def query_report_data(req: ReportDataQueryRequest, svc: BiReportService = Depends(get_report_service)):
    report = await svc.get_by_code(req.report_code, tenant_id_var.get(""))
    if not report:
        return Result.fail(code=404, message=f"Report '{req.report_code}' not found",
                           trace_id=trace_id_var.get(""))
    return Result.ok(data={"report_code": report.report_code, "name": report.name,
                           "report_type": report.report_type, "data": []},
                     trace_id=trace_id_var.get(""))


@router.get("/export/metric-values", response_model=None)
async def export_metric_values(metric_code: str = Query(..., min_length=1),
                                period_type: str = Query(default="daily"),
                                store_id: str = Query(default=""),
                                format: str = Query(default="csv", pattern=r"^(csv|json)$"),
                                svc: BiMetricValueService = Depends(get_metric_value_service)):
    values = await svc.query(tenant_id_var.get(""), metric_code=metric_code,
                              period_type=period_type, store_id=store_id or None, limit=1000)
    if format == "json":
        data = [{"metric_code": metric_code, "period_date": v.period_date.isoformat() if v.period_date else "",
                 "numeric_value": v.numeric_value, "text_value": v.text_value,
                 "store_id": v.store_id, "platform": v.platform} for v in values]
        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        return StreamingResponse(
            io.BytesIO(json_bytes),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={metric_code}_export.json"},
        )
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["metric_code", "period_date", "numeric_value",
                                                 "text_value", "store_id", "platform"])
    writer.writeheader()
    for v in values:
        writer.writerow({
            "metric_code": metric_code,
            "period_date": v.period_date.isoformat() if v.period_date else "",
            "numeric_value": v.numeric_value,
            "text_value": v.text_value or "",
            "store_id": v.store_id or "",
            "platform": v.platform or "",
        })
    csv_bytes = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={metric_code}_export.csv"},
    )


@router.get("/export/report/{report_id}", response_model=None)
async def export_report(report_id: str, format: str = Query(default="csv", pattern=r"^(csv|json)$"),
                         svc: BiReportService = Depends(get_report_service)):
    report = await svc.get_by_id(report_id)
    if not report:
        return Result.fail(code=404, message="Report not found", trace_id=trace_id_var.get(""))
    data = []
    if format == "json":
        json_bytes = json.dumps({"report_code": report.report_code, "name": report.name,
                                  "data": data}, ensure_ascii=False, indent=2).encode("utf-8")
        return StreamingResponse(
            io.BytesIO(json_bytes),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={report.report_code}_export.json"},
        )
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["report_code", "name"])
    writer.writeheader()
    writer.writerow({"report_code": report.report_code, "name": report.name})
    csv_bytes = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={report.report_code}_export.csv"},
    )


@router.get("/metrics/summary", response_model=None)
async def get_metrics_summary(metric_category: str = Query(default=""),
                               metric_svc: BiMetricService = Depends(get_metric_service),
                               val_svc: BiMetricValueService = Depends(get_metric_value_service)):
    metrics = await metric_svc.list_by_tenant(tenant_id_var.get(""), category=metric_category or None)
    summary = []
    for m in metrics:
        latest_vals = await val_svc.query(tenant_id_var.get(""), metric_code=m.metric_code,
                                           period_type="daily", limit=1)
        current = latest_vals[0].numeric_value if latest_vals else 0.0
        summary.append({
            "metric_code": m.metric_code, "metric_name": m.metric_name,
            "metric_category": m.metric_category, "metric_unit": m.metric_unit,
            "current_value": current,
        })
    return Result.ok(data=summary, trace_id=trace_id_var.get(""))
