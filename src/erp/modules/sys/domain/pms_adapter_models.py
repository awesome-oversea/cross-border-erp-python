from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RecommendationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RecommendationPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PMSRecommendation(Base):
    __tablename__ = "pms_recommendation"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scene: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    erp_reference_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    erp_reference_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    approval_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    execution_log_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    feedback_type: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    feedback_reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="pms")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PMSDraft(Base):
    __tablename__ = "pms_draft"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    draft_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    draft_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    erp_reference_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    erp_reference_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PMSAdapterService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def receive_recommendation(self, tenant_id: str, recommendation_id: str,
                                      domain: str, scene: str, title: str,
                                      description: str = "", priority: str = "medium",
                                      confidence: float = 0.0, payload: dict | None = None,
                                      evidence: dict | None = None,
                                      requires_approval: bool = True,
                                      source: str = "pms") -> PMSRecommendation:
        existing = await self._get_by_rec_id(tenant_id, recommendation_id)
        if existing:
            raise ValidationException(message=f"Recommendation '{recommendation_id}' already exists")

        rec = PMSRecommendation(
            tenant_id=tenant_id, recommendation_id=recommendation_id,
            domain=domain, scene=scene, title=title, description=description,
            priority=priority, confidence=confidence,
            payload_json=json.dumps(payload or {}, default=str),
            evidence_json=json.dumps(evidence or {}, default=str),
            requires_approval=requires_approval,
            source=source, trace_id=trace_id_var.get(""),
        )
        self.session.add(rec)
        await self.session.flush()
        return rec

    async def accept_recommendation(self, tenant_id: str, recommendation_id: str,
                                     erp_reference_type: str = "",
                                     erp_reference_id: str = "") -> PMSRecommendation:
        rec = await self._get_by_rec_id(tenant_id, recommendation_id)
        if not rec:
            raise NotFoundException(message=f"Recommendation '{recommendation_id}' not found")
        if rec.status != "pending":
            raise ValidationException(message=f"Cannot accept recommendation in status '{rec.status}'")

        rec.status = "accepted"
        rec.erp_reference_type = erp_reference_type
        rec.erp_reference_id = erp_reference_id
        await self.session.flush()
        return rec

    async def reject_recommendation(self, tenant_id: str, recommendation_id: str,
                                     reason: str = "") -> PMSRecommendation:
        rec = await self._get_by_rec_id(tenant_id, recommendation_id)
        if not rec:
            raise NotFoundException(message=f"Recommendation '{recommendation_id}' not found")
        if rec.status not in ("pending", "accepted"):
            raise ValidationException(message=f"Cannot reject recommendation in status '{rec.status}'")

        rec.status = "rejected"
        rec.feedback_type = "rejected"
        rec.feedback_reason = reason
        await self.session.flush()
        return rec

    async def execute_recommendation(self, tenant_id: str, recommendation_id: str,
                                      execution_result: dict | None = None) -> PMSRecommendation:
        rec = await self._get_by_rec_id(tenant_id, recommendation_id)
        if not rec:
            raise NotFoundException(message=f"Recommendation '{recommendation_id}' not found")
        if rec.status != "accepted":
            raise ValidationException(message=f"Cannot execute recommendation in status '{rec.status}'")

        rec.status = "executed"
        rec.executed_at = datetime.now(UTC)
        rec.executed_by = actor_id_var.get("")
        await self.session.flush()
        return rec

    async def rollback_recommendation(self, tenant_id: str, recommendation_id: str,
                                       reason: str = "") -> PMSRecommendation:
        rec = await self._get_by_rec_id(tenant_id, recommendation_id)
        if not rec:
            raise NotFoundException(message=f"Recommendation '{recommendation_id}' not found")
        if rec.status != "executed":
            raise ValidationException(message=f"Cannot rollback recommendation in status '{rec.status}'")

        rec.status = "rolled_back"
        rec.feedback_type = "rolled_back"
        rec.feedback_reason = reason
        await self.session.flush()
        return rec

    async def receive_draft(self, tenant_id: str, draft_id: str,
                             recommendation_id: str, domain: str,
                             draft_type: str, title: str,
                             content: dict | None = None) -> PMSDraft:
        existing = await self._get_draft_by_id(tenant_id, draft_id)
        if existing:
            raise ValidationException(message=f"Draft '{draft_id}' already exists")

        draft = PMSDraft(
            tenant_id=tenant_id, draft_id=draft_id,
            recommendation_id=recommendation_id, domain=domain,
            draft_type=draft_type, title=title,
            content_json=json.dumps(content or {}, default=str),
            trace_id=trace_id_var.get(""),
        )
        self.session.add(draft)
        await self.session.flush()
        return draft

    async def accept_draft(self, tenant_id: str, draft_id: str,
                            erp_reference_type: str = "",
                            erp_reference_id: str = "") -> PMSDraft:
        draft = await self._get_draft_by_id(tenant_id, draft_id)
        if not draft:
            raise NotFoundException(message=f"Draft '{draft_id}' not found")
        if draft.status != "draft":
            raise ValidationException(message=f"Cannot accept draft in status '{draft.status}'")

        draft.status = "accepted"
        draft.erp_reference_type = erp_reference_type
        draft.erp_reference_id = erp_reference_id
        await self.session.flush()
        return draft

    async def list_recommendations(self, tenant_id: str, domain: str = "",
                                    status: str = "", scene: str = "",
                                    page: int = 1, page_size: int = 20) -> tuple[list[PMSRecommendation], int]:
        conditions = [PMSRecommendation.tenant_id == tenant_id]
        if domain:
            conditions.append(PMSRecommendation.domain == domain)
        if status:
            conditions.append(PMSRecommendation.status == status)
        if scene:
            conditions.append(PMSRecommendation.scene == scene)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(PMSRecommendation).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(PMSRecommendation).where(*conditions).order_by(
            PMSRecommendation.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_drafts(self, tenant_id: str, domain: str = "",
                           status: str = "", page: int = 1,
                           page_size: int = 20) -> tuple[list[PMSDraft], int]:
        conditions = [PMSDraft.tenant_id == tenant_id]
        if domain:
            conditions.append(PMSDraft.domain == domain)
        if status:
            conditions.append(PMSDraft.status == status)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(PMSDraft).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(PMSDraft).where(*conditions).order_by(
            PMSDraft.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def _get_by_rec_id(self, tenant_id: str, recommendation_id: str) -> PMSRecommendation | None:
        stmt = select(PMSRecommendation).where(
            PMSRecommendation.tenant_id == tenant_id,
            PMSRecommendation.recommendation_id == recommendation_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _get_draft_by_id(self, tenant_id: str, draft_id: str) -> PMSDraft | None:
        stmt = select(PMSDraft).where(
            PMSDraft.tenant_id == tenant_id,
            PMSDraft.draft_id == draft_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
