from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.sys.domain.ai_suggestion_models import AISuggestionService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/ai-suggestions", tags=["SYS-AISuggestion"])


class ReceiveSuggestionRequest(BaseModel):
    suggestion_type: str = Field(..., min_length=1, max_length=50)
    domain: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="", max_length=2000)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    priority: str = Field(default="medium", max_length=20)
    target_entity_type: str = Field(default="", max_length=100)
    target_entity_id: str = Field(default="", max_length=36)
    suggestion_data: dict = Field(default_factory=dict)
    pms_suggestion_id: str = Field(default="", max_length=100)
    actor_type: str = Field(default="pms", max_length=50)
    actor_id: str = Field(default="", max_length=36)
    scope: str = Field(default="", max_length=100)
    purpose: str = Field(default="", max_length=200)
    idempotency_key: str = Field(default="", max_length=100)


class RejectSuggestionRequest(BaseModel):
    reason: str = Field(default="", max_length=500)


class FeedbackRequest(BaseModel):
    feedback_type: str = Field(..., min_length=1, max_length=50)
    feedback_detail: str = Field(default="", max_length=1000)
    rating: int = Field(default=0, ge=0, le=5)


@router.post("", response_model=None)
async def receive_suggestion(req: ReceiveSuggestionRequest, session: AsyncSession = Depends(get_db_session)):
    svc = AISuggestionService(session)
    suggestion = await svc.receive_suggestion(
        tenant_id=tenant_id_var.get(""), suggestion_type=req.suggestion_type,
        domain=req.domain, title=req.title, description=req.description,
        confidence_score=req.confidence_score, priority=req.priority,
        target_entity_type=req.target_entity_type, target_entity_id=req.target_entity_id,
        suggestion_data=req.suggestion_data, pms_suggestion_id=req.pms_suggestion_id,
        actor_type=req.actor_type, actor_id=req.actor_id,
        scope=req.scope, purpose=req.purpose, idempotency_key=req.idempotency_key,
    )
    return Result.ok(
        data={"id": suggestion.id, "suggestion_type": suggestion.suggestion_type,
              "domain": suggestion.domain, "status": suggestion.status,
              "title": suggestion.title, "confidence_score": suggestion.confidence_score},
        trace_id=trace_id_var.get(""),
    )


@router.get("", response_model=None)
async def list_suggestions(
    domain: str = Query(default=""),
    suggestion_type: str = Query(default=""),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = AISuggestionService(session)
    suggestions, total = await svc.list_suggestions(
        tenant_id_var.get(""), domain=domain, suggestion_type=suggestion_type,
        status=status, page=page, page_size=page_size,
    )
    items = [
        {"id": s.id, "suggestion_type": s.suggestion_type, "domain": s.domain,
         "title": s.title, "status": s.status, "priority": s.priority,
         "confidence_score": s.confidence_score, "target_entity_type": s.target_entity_type,
         "pms_suggestion_id": s.pms_suggestion_id,
         "created_at": s.created_at.isoformat() if s.created_at else None}
        for s in suggestions
    ]
    return Result.paginate(items=items, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/handlers", response_model=None)
async def get_handlers(
    domain: str = Query(default=""),
    session: AsyncSession = Depends(get_db_session),
):
    svc = AISuggestionService(session)
    handlers = await svc.get_domain_handlers(domain=domain)
    return Result.ok(data=handlers, trace_id=trace_id_var.get(""))


@router.post("/{suggestion_id}/accept", response_model=None)
async def accept_suggestion(
    suggestion_id: str,
    auto_execute: bool = Query(default=False),
    session: AsyncSession = Depends(get_db_session),
):
    svc = AISuggestionService(session)
    suggestion = await svc.accept_suggestion(suggestion_id, tenant_id_var.get(""), auto_execute=auto_execute)
    return Result.ok(
        data={"id": suggestion.id, "status": suggestion.status,
              "execution_result": suggestion.execution_result_json if suggestion.status == "completed" else None},
        trace_id=trace_id_var.get(""),
    )


@router.post("/{suggestion_id}/reject", response_model=None)
async def reject_suggestion(suggestion_id: str, req: RejectSuggestionRequest, session: AsyncSession = Depends(get_db_session)):
    svc = AISuggestionService(session)
    suggestion = await svc.reject_suggestion(suggestion_id, tenant_id_var.get(""), reason=req.reason)
    return Result.ok(
        data={"id": suggestion.id, "status": suggestion.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/{suggestion_id}/execute", response_model=None)
async def execute_suggestion(suggestion_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = AISuggestionService(session)
    suggestion = await svc.execute_suggestion(suggestion_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": suggestion.id, "status": suggestion.status,
              "execution_result": suggestion.execution_result_json},
        trace_id=trace_id_var.get(""),
    )


@router.post("/{suggestion_id}/rollback", response_model=None)
async def rollback_suggestion(
    suggestion_id: str,
    reason: str = Query(default=""),
    session: AsyncSession = Depends(get_db_session),
):
    svc = AISuggestionService(session)
    suggestion = await svc.rollback_suggestion(suggestion_id, tenant_id_var.get(""), reason=reason)
    return Result.ok(
        data={"id": suggestion.id, "status": suggestion.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/{suggestion_id}/feedback", response_model=None)
async def provide_feedback(suggestion_id: str, req: FeedbackRequest, session: AsyncSession = Depends(get_db_session)):
    svc = AISuggestionService(session)
    suggestion = await svc.provide_feedback(
        suggestion_id, tenant_id_var.get(""),
        feedback_type=req.feedback_type, feedback_detail=req.feedback_detail, rating=req.rating,
    )
    return Result.ok(
        data={"id": suggestion.id, "feedback": suggestion.feedback_json},
        trace_id=trace_id_var.get(""),
    )
