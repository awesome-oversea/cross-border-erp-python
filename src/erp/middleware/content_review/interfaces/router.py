from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.content_review.application.services import ContentReviewService
from erp.shared.context import actor_id_var, tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/content-review", tags=["Content Review - 内容审核中心"])


class ReviewSubmitRequest(BaseModel):
    review_type: str = Field(default="auto", pattern="^(auto|manual)$")
    content_type: str = Field(default="text", pattern="^(text|image)$")
    content_text: str = Field(default="", max_length=5000)
    content_url: str = Field(default="", max_length=512)
    content_id: str = Field(default="")
    language: str = Field(default="en", max_length=10)
    source_domain: str = Field(default="")
    source_id: str = Field(default="")


class ManualReviewRequest(BaseModel):
    result: str = Field(pattern="^(pass|reject)$")
    detail: str = Field(default="")
    reviewer_id: str = Field(default="")


class ReviewRuleCreateRequest(BaseModel):
    rule_code: str = Field(..., min_length=1, max_length=64)
    rule_name: str = Field(..., min_length=1, max_length=128)
    rule_type: str = Field(default="text", max_length=32)
    language: str = Field(default="*", max_length=10)
    keywords: list[str] = Field(default_factory=list)
    regex_patterns: list[str] = Field(default_factory=list)
    severity: str = Field(default="warning", pattern="^(warning|critical)$")
    is_active: bool = Field(default=True)


@router.post("/submit", response_model=None)
async def submit_review(req: ReviewSubmitRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ContentReviewService(session)
    task = await svc.submit_review(
        tenant_id_var.get(""),
        review_type=req.review_type,
        content_type=req.content_type,
        content_text=req.content_text,
        content_url=req.content_url,
        content_id=req.content_id,
        language=req.language,
        source_domain=req.source_domain,
        source_id=req.source_id,
    )
    return Result.ok(data={
        "id": task.id, "status": task.status, "auto_result": task.auto_result,
    }, trace_id=trace_id_var.get(""))


@router.get("/tasks", response_model=None)
async def list_review_tasks(status: str = Query(default=""),
                            content_type: str = Query(default=""),
                            review_type: str = Query(default=""),
                            page: int = Query(default=1, ge=1),
                            page_size: int = Query(default=20, ge=1, le=100),
                            session: AsyncSession = Depends(get_db_session)):
    svc = ContentReviewService(session)
    tasks, total = await svc.list_tasks(
        tenant_id=tenant_id_var.get(""),
        status=status,
        content_type=content_type,
        review_type=review_type,
        page=page,
        page_size=page_size,
    )
    data = [{
        "id": t.id,
        "review_type": t.review_type,
        "content_type": t.content_type,
        "content_id": t.content_id,
        "status": t.status,
        "auto_result": t.auto_result,
        "manual_result": t.manual_result,
        "source_domain": t.source_domain,
        "source_id": t.source_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "reviewed_at": t.reviewed_at.isoformat() if t.reviewed_at else None,
    } for t in tasks]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/rules", response_model=None)
async def get_review_rules(language: str = Query(default=""),
                           include_inactive: bool = Query(default=False),
                           session: AsyncSession = Depends(get_db_session)):
    svc = ContentReviewService(session)
    rules = await svc.get_rules(tenant_id_var.get(""), language=language, include_inactive=include_inactive)
    items = [{
        "id": r.id,
        "rule_code": r.rule_code,
        "rule_name": r.rule_name,
        "rule_type": r.rule_type,
        "language": r.language,
        "severity": r.severity,
        "keywords": json.loads(r.keywords_json) if r.keywords_json else [],
        "regex_patterns": json.loads(r.regex_patterns_json) if r.regex_patterns_json else [],
        "is_active": r.is_active,
    } for r in rules]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.post("/rules", response_model=None)
async def create_review_rule(req: ReviewRuleCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ContentReviewService(session)
    rule = await svc.create_rule(
        tenant_id=tenant_id_var.get(""),
        rule_code=req.rule_code,
        rule_name=req.rule_name,
        rule_type=req.rule_type,
        language=req.language,
        keywords=req.keywords,
        regex_patterns=req.regex_patterns,
        severity=req.severity,
        is_active=req.is_active,
    )
    return Result.ok(data={
        "id": rule.id,
        "rule_code": rule.rule_code,
        "rule_name": rule.rule_name,
        "rule_type": rule.rule_type,
    }, trace_id=trace_id_var.get(""))


@router.post("/rules/init-defaults", response_model=None)
async def init_default_review_rules(session: AsyncSession = Depends(get_db_session)):
    svc = ContentReviewService(session)
    rules = await svc.init_default_rules(tenant_id_var.get(""))
    return Result.ok(data={"created_count": len(rules)}, trace_id=trace_id_var.get(""))


@router.get("/{task_id}/result", response_model=None)
async def get_review_result(task_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = ContentReviewService(session)
    task = await svc.get_result(task_id, tenant_id_var.get(""))
    if not task:
        return Result.fail(code=404, message="Review task not found", trace_id=trace_id_var.get(""))
    return Result.ok(data={
        "id": task.id,
        "status": task.status,
        "auto_result": task.auto_result,
        "manual_result": task.manual_result,
        "reviewer_id": task.reviewer_id,
        "auto_detail": json.loads(task.auto_detail) if task.auto_detail else {},
        "manual_detail": task.manual_detail,
    }, trace_id=trace_id_var.get(""))


@router.post("/{task_id}/manual-review", response_model=None)
async def manual_review(task_id: str, req: ManualReviewRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ContentReviewService(session)
    task = await svc.manual_review(
        task_id=task_id,
        tenant_id=tenant_id_var.get(""),
        result=req.result,
        detail=req.detail,
        reviewer_id=req.reviewer_id or actor_id_var.get(""),
    )
    return Result.ok(data={
        "id": task.id,
        "status": task.status,
        "manual_result": task.manual_result,
        "reviewer_id": task.reviewer_id,
    }, trace_id=trace_id_var.get(""))
