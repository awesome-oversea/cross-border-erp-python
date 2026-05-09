from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.crm.domain.lifecycle_models import CustomerLifecycleService
from erp.modules.crm.interfaces.deps import get_lifecycle_service
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import Result

router = APIRouter(prefix="/crm/v1", tags=["CRM-Lifecycle - 客户生命周期管理"])


class SegmentCreateRequest(BaseModel):
    segment_name: str = Field(..., min_length=1, max_length=200)
    segment_code: str = Field(..., min_length=1, max_length=100)
    segment_type: str = Field(default="lifecycle", pattern=r"^(lifecycle|rfm|value|custom)$")
    description: str = Field(default="")
    criteria: dict = Field(default_factory=dict)
    lifecycle_stage: str = Field(default="")
    is_auto: bool = Field(default=False)


class CustomerAssignRequest(BaseModel):
    segment_id: str = Field(..., min_length=1)
    customer_id: str = Field(..., min_length=1)
    lifecycle_stage: str = Field(default="")
    rfm_score: dict = Field(default_factory=dict)


class LifecycleEvaluateRequest(BaseModel):
    customer_id: str = Field(..., min_length=1)
    total_orders: int = Field(default=0, ge=0)
    total_revenue: float = Field(default=0.0, ge=0)
    first_order_date: str = Field(default="")
    last_order_date: str = Field(default="")
    avg_days_between_orders: float = Field(default=0.0, ge=0)


class BatchAssignRequest(BaseModel):
    customers: list[dict] = Field(..., min_length=1)


@router.post("/segments", response_model=None)
async def create_segment(req: SegmentCreateRequest,
                         svc: CustomerLifecycleService = Depends(get_lifecycle_service)):
    segment = await svc.create_segment(
        tenant_id=tenant_id_var.get(""), segment_name=req.segment_name,
        segment_code=req.segment_code, segment_type=req.segment_type,
        description=req.description, criteria=req.criteria,
        lifecycle_stage=req.lifecycle_stage, is_auto=req.is_auto,
    )
    return Result.ok(
        data={"id": segment.id, "segment_name": segment.segment_name,
              "segment_code": segment.segment_code, "lifecycle_stage": segment.lifecycle_stage},
        trace_id=trace_id_var.get(""),
    )


@router.get("/segments", response_model=None)
async def list_segments(segment_type: str = Query(default=""),
                         lifecycle_stage: str = Query(default=""),
                         svc: CustomerLifecycleService = Depends(get_lifecycle_service)):
    segments = await svc.list_segments(tenant_id_var.get(""), segment_type=segment_type,
                                        lifecycle_stage=lifecycle_stage)
    data = [{
        "id": s.id, "segment_name": s.segment_name, "segment_code": s.segment_code,
        "segment_type": s.segment_type, "lifecycle_stage": s.lifecycle_stage,
        "customer_count": s.customer_count, "is_auto": s.is_auto, "is_active": s.is_active,
        "criteria": json.loads(s.criteria_json),
    } for s in segments]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/assign", response_model=None)
async def assign_customer(req: CustomerAssignRequest,
                          svc: CustomerLifecycleService = Depends(get_lifecycle_service)):
    member = await svc.assign_customer(
        tenant_id=tenant_id_var.get(""), segment_id=req.segment_id,
        customer_id=req.customer_id, lifecycle_stage=req.lifecycle_stage,
        rfm_score=req.rfm_score,
    )
    return Result.ok(
        data={"id": member.id, "segment_id": member.segment_id,
              "customer_id": member.customer_id, "lifecycle_stage": member.lifecycle_stage},
        trace_id=trace_id_var.get(""),
    )


@router.post("/evaluate", response_model=None)
async def evaluate_lifecycle(req: LifecycleEvaluateRequest,
                              svc: CustomerLifecycleService = Depends(get_lifecycle_service)):
    result = await svc.evaluate_lifecycle(
        tenant_id=tenant_id_var.get(""), customer_id=req.customer_id,
        total_orders=req.total_orders, total_revenue=req.total_revenue,
        first_order_date=req.first_order_date, last_order_date=req.last_order_date,
        avg_days_between_orders=req.avg_days_between_orders,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/batch-assign", response_model=None)
async def batch_assign(req: BatchAssignRequest,
                       svc: CustomerLifecycleService = Depends(get_lifecycle_service)):
    result = await svc.batch_assign_lifecycle(tenant_id_var.get(""), customers=req.customers)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/segments/{segment_id}/members", response_model=None)
async def list_segment_members(segment_id: str, page: int = Query(default=1, ge=1),
                                page_size: int = Query(default=20, ge=1, le=100),
                                svc: CustomerLifecycleService = Depends(get_lifecycle_service)):
    members, total = await svc.list_segment_members(
        tenant_id_var.get(""), segment_id=segment_id,
        page=page, page_size=page_size,
    )
    data = [{
        "id": m.id, "segment_id": m.segment_id, "customer_id": m.customer_id,
        "lifecycle_stage": m.lifecycle_stage,
        "rfm_score": json.loads(m.rfm_score_json),
        "assigned_at": m.assigned_at.isoformat() if m.assigned_at else None,
    } for m in members]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/init-defaults", response_model=None)
async def init_default_segments(svc: CustomerLifecycleService = Depends(get_lifecycle_service)):
    segments = await svc.init_default_segments(tenant_id_var.get(""))
    return Result.ok(
        data={"segments_created": len(segments)},
        trace_id=trace_id_var.get(""),
    )
