from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.sys.application.services import (
    DraftDocumentService,
    InsightCardService,
    RecommendationService,
    RiskAlertService,
)
from erp.shared.auth.pms_auth import PMSAuthContext, verify_pms_read_request, verify_pms_request
from erp.shared.context import trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import NotFoundException, Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/api/in/v1/pms", tags=["PMS-Integration"])


class RecommendationSubmitRequest(BaseModel):
    recommendation_id: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    recommendation_type: str = Field(..., min_length=1)
    target_object_type: str = Field(default="")
    target_object_id: str = Field(default="")
    content: dict = Field(default_factory=dict)
    score: float = Field(default=0.0)
    confidence: float = Field(default=0.0)
    evidence_chain_id: str = Field(default="")
    data_sources: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    explainability: str = Field(default="")
    requested_action: str = Field(default="")


class DraftSubmitRequest(BaseModel):
    recommendation_id: str = Field(..., min_length=1)
    draft_type: str = Field(..., min_length=1)
    draft_data: dict = Field(default_factory=dict)
    domain: str = Field(..., min_length=1)


class RiskAlertSubmitRequest(BaseModel):
    domain: str = Field(..., min_length=1)
    risk_type: str = Field(..., min_length=1)
    risk_level: str = Field(default="medium", pattern=r"^(low|medium|high|critical)$")
    title: str = Field(..., min_length=1)
    description: str = Field(default="")
    evidence: dict = Field(default_factory=dict)
    recommendation_id: str = Field(default="")


class InsightCardSubmitRequest(BaseModel):
    domain: str = Field(..., min_length=1)
    card_type: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    content: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)
    recommendation_id: str = Field(default="")


class RecommendationStatusRequest(BaseModel):
    status: str = Field(..., min_length=1)
    reason: str = Field(default="")
    execution_result: dict = Field(default_factory=dict)


class RiskAlertResolveRequest(BaseModel):
    resolution: str = Field(..., min_length=1)


@router.post("/recommendations", response_model=None)
async def submit_recommendation(
    req: RecommendationSubmitRequest,
    pms: PMSAuthContext = Depends(verify_pms_request),
    session: AsyncSession = Depends(get_db_session),
):
    svc = RecommendationService(session)
    rec = await svc.receive_recommendation(
        tenant_id=pms.tenant_id,
        recommendation_id=req.recommendation_id,
        domain=req.domain,
        recommendation_type=req.recommendation_type,
        target_object_type=req.target_object_type,
        target_object_id=req.target_object_id,
        content=req.content,
        score=req.score,
        confidence=req.confidence,
        evidence_chain_id=req.evidence_chain_id,
        data_sources=req.data_sources,
        risk_flags=req.risk_flags,
        explainability=req.explainability,
        requested_action=req.requested_action,
        idempotency_key=pms.idempotency_key,
        actor_id=pms.service_account_id,
        actor_type=pms.actor_type,
        agent_id=pms.agent_id,
        scope=pms.scope,
        purpose=pms.purpose,
    )
    return Result.ok(
        data={
            "erp_reference_id": rec.id,
            "recommendation_id": rec.recommendation_id,
            "status": rec.status,
            "audit_id": rec.id,
            "trace_id": trace_id_var.get(""),
        },
        trace_id=trace_id_var.get(""),
    )


@router.get("/recommendations", response_model=None)
async def list_recommendations(
    domain: str = Query(default=""),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    pms: PMSAuthContext = Depends(verify_pms_read_request),
    session: AsyncSession = Depends(get_db_session),
):
    svc = RecommendationService(session)
    items, total = await svc.list_by_tenant(
        pms.tenant_id, domain=domain, status=status, page=page, page_size=page_size
    )
    data = [
        {
            "id": r.id,
            "recommendation_id": r.recommendation_id,
            "domain": r.domain,
            "recommendation_type": r.recommendation_type,
            "status": r.status,
            "score": r.score,
            "confidence": r.confidence,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in items
    ]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/recommendations/{rec_id}", response_model=None)
async def get_recommendation(
    rec_id: str,
    pms: PMSAuthContext = Depends(verify_pms_read_request),
    session: AsyncSession = Depends(get_db_session),
):
    svc = RecommendationService(session)
    rec = await svc.get_or_raise(rec_id, pms.tenant_id)
    return Result.ok(
        data={
            "id": rec.id,
            "recommendation_id": rec.recommendation_id,
            "erp_reference_id": rec.id,
            "domain": rec.domain,
            "recommendation_type": rec.recommendation_type,
            "status": rec.status,
            "content": json.loads(rec.content_json) if rec.content_json else {},
            "score": rec.score,
            "confidence": rec.confidence,
            "evidence_chain_id": rec.evidence_chain_id,
            "risk_flags": json.loads(rec.risk_flags_json) if rec.risk_flags_json else [],
            "explainability": rec.explainability,
            "rejection_reason": rec.rejection_reason,
            "execution_result": json.loads(rec.execution_result_json) if rec.execution_result_json else {},
            "trace_id": rec.trace_id,
        },
        trace_id=trace_id_var.get(""),
    )


@router.put("/recommendations/{rec_id}/status", response_model=None)
async def transition_recommendation_status(
    rec_id: str,
    req: RecommendationStatusRequest,
    pms: PMSAuthContext = Depends(verify_pms_request),
    session: AsyncSession = Depends(get_db_session),
):
    svc = RecommendationService(session)
    rec = await svc.transition_status(
        rec_id=rec_id,
        tenant_id=pms.tenant_id,
        new_status=req.status,
        reason=req.reason,
        execution_result=req.execution_result,
    )
    return Result.ok(
        data={
            "erp_reference_id": rec.id,
            "status": rec.status,
            "trace_id": trace_id_var.get(""),
        },
        trace_id=trace_id_var.get(""),
    )


@router.post("/drafts", response_model=None)
async def submit_draft(
    req: DraftSubmitRequest,
    pms: PMSAuthContext = Depends(verify_pms_request),
    session: AsyncSession = Depends(get_db_session),
):
    svc = DraftDocumentService(session)
    draft = await svc.receive_draft(
        tenant_id=pms.tenant_id,
        recommendation_id=req.recommendation_id,
        draft_type=req.draft_type,
        draft_data=req.draft_data,
        domain=req.domain,
        idempotency_key=pms.idempotency_key,
        created_by=pms.service_account_id,
    )
    return Result.ok(
        data={
            "erp_reference_id": draft.id,
            "status": draft.status,
            "trace_id": trace_id_var.get(""),
        },
        trace_id=trace_id_var.get(""),
    )


@router.post("/risk-alerts", response_model=None)
async def submit_risk_alert(
    req: RiskAlertSubmitRequest,
    pms: PMSAuthContext = Depends(verify_pms_request),
    session: AsyncSession = Depends(get_db_session),
):
    svc = RiskAlertService(session)
    alert = await svc.receive_alert(
        tenant_id=pms.tenant_id,
        domain=req.domain,
        risk_type=req.risk_type,
        risk_level=req.risk_level,
        title=req.title,
        description=req.description,
        evidence=req.evidence,
        recommendation_id=req.recommendation_id,
        idempotency_key=pms.idempotency_key,
    )
    return Result.ok(
        data={
            "erp_reference_id": alert.id,
            "status": alert.status,
            "trace_id": trace_id_var.get(""),
        },
        trace_id=trace_id_var.get(""),
    )


@router.put("/risk-alerts/{alert_id}/resolve", response_model=None)
async def resolve_risk_alert(
    alert_id: str,
    req: RiskAlertResolveRequest,
    pms: PMSAuthContext = Depends(verify_pms_request),
    session: AsyncSession = Depends(get_db_session),
):
    svc = RiskAlertService(session)
    alert = await svc.resolve_alert(
        alert_id=alert_id,
        tenant_id=pms.tenant_id,
        resolution=req.resolution,
        assigned_to=pms.service_account_id,
    )
    return Result.ok(
        data={"erp_reference_id": alert.id, "status": alert.status, "trace_id": trace_id_var.get("")},
        trace_id=trace_id_var.get(""),
    )


@router.post("/insight-cards", response_model=None)
async def submit_insight_card(
    req: InsightCardSubmitRequest,
    pms: PMSAuthContext = Depends(verify_pms_request),
    session: AsyncSession = Depends(get_db_session),
):
    svc = InsightCardService(session)
    card = await svc.receive_card(
        tenant_id=pms.tenant_id,
        domain=req.domain,
        card_type=req.card_type,
        title=req.title,
        content=req.content,
        metrics=req.metrics,
        recommendation_id=req.recommendation_id,
        idempotency_key=pms.idempotency_key,
    )
    return Result.ok(
        data={
            "erp_reference_id": card.id,
            "status": card.status,
            "trace_id": trace_id_var.get(""),
        },
        trace_id=trace_id_var.get(""),
    )
