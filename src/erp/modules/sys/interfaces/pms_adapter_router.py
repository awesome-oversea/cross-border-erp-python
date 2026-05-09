from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.sys.domain.pms_adapter_models import PMSAdapterService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/pms-adapter", tags=["PMS-Adapter"])


class RecommendationReceiveRequest(BaseModel):
    recommendation_id: str = Field(..., min_length=1, max_length=100)
    domain: str = Field(..., min_length=1, max_length=50)
    scene: str = Field(default="", max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="")
    priority: str = Field(default="medium", pattern=r"^(low|medium|high|critical)$")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    payload: dict = Field(default_factory=dict)
    evidence: dict = Field(default_factory=dict)
    requires_approval: bool = Field(default=True)
    source: str = Field(default="pms")


class RecommendationAcceptRequest(BaseModel):
    erp_reference_type: str = Field(default="")
    erp_reference_id: str = Field(default="")


class RecommendationRejectRequest(BaseModel):
    reason: str = Field(default="")


class RecommendationExecuteRequest(BaseModel):
    execution_result: dict = Field(default_factory=dict)


class RecommendationRollbackRequest(BaseModel):
    reason: str = Field(default="")


class DraftReceiveRequest(BaseModel):
    draft_id: str = Field(..., min_length=1, max_length=100)
    recommendation_id: str = Field(..., min_length=1, max_length=100)
    domain: str = Field(..., min_length=1, max_length=50)
    draft_type: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    content: dict = Field(default_factory=dict)


class DraftAcceptRequest(BaseModel):
    erp_reference_type: str = Field(default="")
    erp_reference_id: str = Field(default="")


@router.post("/recommendations", response_model=None)
async def receive_recommendation(req: RecommendationReceiveRequest,
                                  session: AsyncSession = Depends(get_db_session)):
    svc = PMSAdapterService(session)
    rec = await svc.receive_recommendation(
        tenant_id=tenant_id_var.get(""), recommendation_id=req.recommendation_id,
        domain=req.domain, scene=req.scene, title=req.title,
        description=req.description, priority=req.priority,
        confidence=req.confidence, payload=req.payload,
        evidence=req.evidence, requires_approval=req.requires_approval,
        source=req.source,
    )
    return Result.ok(
        data={"id": rec.id, "recommendation_id": rec.recommendation_id,
              "domain": rec.domain, "status": rec.status,
              "requires_approval": rec.requires_approval},
        trace_id=trace_id_var.get(""),
    )


@router.get("/recommendations", response_model=None)
async def list_recommendations(
    domain: str = Query(default=""),
    status: str = Query(default=""),
    scene: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = PMSAdapterService(session)
    recs, total = await svc.list_recommendations(
        tenant_id_var.get(""), domain=domain, status=status,
        scene=scene, page=page, page_size=page_size,
    )
    data = [{
        "id": r.id, "recommendation_id": r.recommendation_id,
        "domain": r.domain, "scene": r.scene, "title": r.title,
        "priority": r.priority, "confidence": r.confidence,
        "status": r.status, "requires_approval": r.requires_approval,
        "erp_reference_type": r.erp_reference_type,
        "erp_reference_id": r.erp_reference_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in recs]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/recommendations/{recommendation_id}", response_model=None)
async def get_recommendation(recommendation_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = PMSAdapterService(session)
    recs, _ = await svc.list_recommendations(tenant_id_var.get(""), page=1, page_size=1)
    rec = None
    for r in recs:
        if r.recommendation_id == recommendation_id:
            rec = r
            break
    if not rec:
        return Result.fail(code=404, message="Recommendation not found", trace_id=trace_id_var.get(""))
    return Result.ok(
        data={"id": rec.id, "recommendation_id": rec.recommendation_id,
              "domain": rec.domain, "scene": rec.scene, "title": rec.title,
              "description": rec.description, "priority": rec.priority,
              "confidence": rec.confidence, "payload": json.loads(rec.payload_json),
              "evidence": json.loads(rec.evidence_json),
              "status": rec.status, "requires_approval": rec.requires_approval,
              "erp_reference_type": rec.erp_reference_type,
              "erp_reference_id": rec.erp_reference_id,
              "executed_at": rec.executed_at.isoformat() if rec.executed_at else None,
              "feedback_type": rec.feedback_type, "feedback_reason": rec.feedback_reason},
        trace_id=trace_id_var.get(""),
    )


@router.post("/recommendations/{recommendation_id}/accept", response_model=None)
async def accept_recommendation(recommendation_id: str, req: RecommendationAcceptRequest,
                                 session: AsyncSession = Depends(get_db_session)):
    svc = PMSAdapterService(session)
    rec = await svc.accept_recommendation(
        tenant_id_var.get(""), recommendation_id,
        erp_reference_type=req.erp_reference_type,
        erp_reference_id=req.erp_reference_id,
    )
    return Result.ok(
        data={"recommendation_id": rec.recommendation_id, "status": rec.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/recommendations/{recommendation_id}/reject", response_model=None)
async def reject_recommendation(recommendation_id: str, req: RecommendationRejectRequest,
                                 session: AsyncSession = Depends(get_db_session)):
    svc = PMSAdapterService(session)
    rec = await svc.reject_recommendation(
        tenant_id_var.get(""), recommendation_id, reason=req.reason,
    )
    return Result.ok(
        data={"recommendation_id": rec.recommendation_id, "status": rec.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/recommendations/{recommendation_id}/execute", response_model=None)
async def execute_recommendation(recommendation_id: str, req: RecommendationExecuteRequest,
                                  session: AsyncSession = Depends(get_db_session)):
    svc = PMSAdapterService(session)
    rec = await svc.execute_recommendation(
        tenant_id_var.get(""), recommendation_id,
        execution_result=req.execution_result,
    )
    return Result.ok(
        data={"recommendation_id": rec.recommendation_id, "status": rec.status,
              "executed_at": rec.executed_at.isoformat() if rec.executed_at else None},
        trace_id=trace_id_var.get(""),
    )


@router.post("/recommendations/{recommendation_id}/rollback", response_model=None)
async def rollback_recommendation(recommendation_id: str, req: RecommendationRollbackRequest,
                                   session: AsyncSession = Depends(get_db_session)):
    svc = PMSAdapterService(session)
    rec = await svc.rollback_recommendation(
        tenant_id_var.get(""), recommendation_id, reason=req.reason,
    )
    return Result.ok(
        data={"recommendation_id": rec.recommendation_id, "status": rec.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/drafts", response_model=None)
async def receive_draft(req: DraftReceiveRequest, session: AsyncSession = Depends(get_db_session)):
    svc = PMSAdapterService(session)
    draft = await svc.receive_draft(
        tenant_id=tenant_id_var.get(""), draft_id=req.draft_id,
        recommendation_id=req.recommendation_id, domain=req.domain,
        draft_type=req.draft_type, title=req.title, content=req.content,
    )
    return Result.ok(
        data={"id": draft.id, "draft_id": draft.draft_id,
              "domain": draft.domain, "status": draft.status},
        trace_id=trace_id_var.get(""),
    )


@router.get("/drafts", response_model=None)
async def list_drafts(
    domain: str = Query(default=""),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = PMSAdapterService(session)
    drafts, total = await svc.list_drafts(
        tenant_id_var.get(""), domain=domain, status=status,
        page=page, page_size=page_size,
    )
    data = [{
        "id": d.id, "draft_id": d.draft_id,
        "recommendation_id": d.recommendation_id,
        "domain": d.domain, "draft_type": d.draft_type,
        "title": d.title, "status": d.status,
        "erp_reference_type": d.erp_reference_type,
        "erp_reference_id": d.erp_reference_id,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    } for d in drafts]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/drafts/{draft_id}/accept", response_model=None)
async def accept_draft(draft_id: str, req: DraftAcceptRequest,
                        session: AsyncSession = Depends(get_db_session)):
    svc = PMSAdapterService(session)
    draft = await svc.accept_draft(
        tenant_id_var.get(""), draft_id,
        erp_reference_type=req.erp_reference_type,
        erp_reference_id=req.erp_reference_id,
    )
    return Result.ok(
        data={"draft_id": draft.draft_id, "status": draft.status},
        trace_id=trace_id_var.get(""),
    )
