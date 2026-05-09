from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class AISuggestionType(StrEnum):
    PRODUCT_SELECTION = "product_selection"
    AD_BIDDING = "ad_bidding"
    ORDER_RISK = "order_risk"
    REPLENISHMENT = "replenishment"
    INVENTORY_PREDICTION = "inventory_prediction"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    COST_ALLOCATION = "cost_allocation"


class SuggestionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class AISuggestion(Base):
    __tablename__ = "ai_suggestion"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    suggestion_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="pms")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    target_entity_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    target_entity_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    suggestion_data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    draft_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    execution_result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    feedback_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    rollback_data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    pms_suggestion_id: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False, default="pms")
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    scope: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    purpose: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AISuggestionExecutionLog(Base):
    __tablename__ = "ai_suggestion_execution_log"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    suggestion_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    suggestion_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    action_detail_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AISuggestionService:
    DOMAIN_SUGGESTION_HANDLERS = {
        "pdm": {
            "product_selection": {
                "label": "AI选品建议",
                "target_entities": ["category", "product_project", "sku"],
                "draft_types": ["product_project_draft", "sku_draft"],
                "default_priority": "high",
            },
        },
        "ads": {
            "ad_bidding": {
                "label": "AI广告优化建议",
                "target_entities": ["campaign", "ad_group", "keyword"],
                "draft_types": ["bid_adjustment_draft", "budget_adjustment_draft"],
                "default_priority": "medium",
            },
        },
        "oms": {
            "order_risk": {
                "label": "AI订单风控建议",
                "target_entities": ["order", "order_item"],
                "draft_types": ["order_hold_draft", "order_cancel_draft"],
                "default_priority": "high",
            },
        },
        "scm": {
            "replenishment": {
                "label": "AI补货建议",
                "target_entities": ["purchase_order", "replenishment_plan"],
                "draft_types": ["purchase_order_draft", "replenishment_draft"],
                "default_priority": "high",
            },
        },
        "wms": {
            "inventory_prediction": {
                "label": "AI仓储预测建议",
                "target_entities": ["inventory", "warehouse_location"],
                "draft_types": ["stock_transfer_draft", "inventory_alert_draft"],
                "default_priority": "medium",
            },
        },
        "crm": {
            "sentiment_analysis": {
                "label": "AI情感分析建议",
                "target_entities": ["customer", "review", "ticket"],
                "draft_types": ["reply_template_draft", "ticket_escalation_draft"],
                "default_priority": "low",
            },
        },
        "fms": {
            "cost_allocation": {
                "label": "AI成本归集建议",
                "target_entities": ["cost_event", "profit_record"],
                "draft_types": ["cost_adjustment_draft", "profit_correction_draft"],
                "default_priority": "medium",
            },
        },
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def receive_suggestion(self, tenant_id: str, suggestion_type: str, domain: str,
                                  title: str, description: str = "",
                                  confidence_score: float = 0.0, priority: str = "medium",
                                  target_entity_type: str = "", target_entity_id: str = "",
                                  suggestion_data: dict | None = None,
                                  pms_suggestion_id: str = "",
                                  actor_type: str = "pms", actor_id: str = "",
                                  scope: str = "", purpose: str = "",
                                  idempotency_key: str = "") -> AISuggestion:
        if idempotency_key:
            existing = await self._get_by_idempotency_key(tenant_id, idempotency_key)
            if existing:
                return existing

        handler = self.DOMAIN_SUGGESTION_HANDLERS.get(domain, {}).get(suggestion_type)
        if not handler:
            raise ValidationException(
                message=f"No handler for suggestion_type='{suggestion_type}' in domain='{domain}'"
            )

        suggestion = AISuggestion(
            tenant_id=tenant_id, suggestion_type=suggestion_type, domain=domain,
            source="pms", title=title, description=description,
            confidence_score=confidence_score,
            priority=priority or handler.get("default_priority", "medium"),
            status=SuggestionStatus.PENDING.value,
            target_entity_type=target_entity_type, target_entity_id=target_entity_id,
            suggestion_data_json=json.dumps(suggestion_data or {}, default=str),
            pms_suggestion_id=pms_suggestion_id,
            actor_type=actor_type, actor_id=actor_id,
            scope=scope, purpose=purpose,
            idempotency_key=idempotency_key or str(uuid.uuid4()),
            trace_id=trace_id_var.get(""),
        )
        self.session.add(suggestion)
        await self.session.flush()

        await self._log_execution(
            tenant_id, suggestion.id, suggestion_type, domain,
            "received", {"title": title, "confidence": confidence_score},
            True, "", 0,
        )
        return suggestion

    async def accept_suggestion(self, suggestion_id: str, tenant_id: str,
                                 auto_execute: bool = False) -> AISuggestion:
        suggestion = await self._get_suggestion(suggestion_id, tenant_id)
        if not suggestion:
            raise NotFoundException(message=f"Suggestion '{suggestion_id}' not found")
        if suggestion.status != SuggestionStatus.PENDING.value:
            raise ValidationException(message=f"Cannot accept suggestion in status '{suggestion.status}'")

        suggestion.status = SuggestionStatus.ACCEPTED.value
        await self.session.flush()

        await self._log_execution(
            tenant_id, suggestion_id, suggestion.suggestion_type, suggestion.domain,
            "accepted", {"auto_execute": auto_execute}, True, "", 0,
        )

        if auto_execute:
            return await self.execute_suggestion(suggestion_id, tenant_id)
        return suggestion

    async def reject_suggestion(self, suggestion_id: str, tenant_id: str,
                                 reason: str = "") -> AISuggestion:
        suggestion = await self._get_suggestion(suggestion_id, tenant_id)
        if not suggestion:
            raise NotFoundException(message=f"Suggestion '{suggestion_id}' not found")
        if suggestion.status != SuggestionStatus.PENDING.value:
            raise ValidationException(message=f"Cannot reject suggestion in status '{suggestion.status}'")

        suggestion.status = SuggestionStatus.REJECTED.value
        suggestion.feedback_json = json.dumps({"reason": reason}, default=str)
        await self.session.flush()

        await self._log_execution(
            tenant_id, suggestion_id, suggestion.suggestion_type, suggestion.domain,
            "rejected", {"reason": reason}, True, "", 0,
        )
        return suggestion

    async def execute_suggestion(self, suggestion_id: str, tenant_id: str) -> AISuggestion:
        suggestion = await self._get_suggestion(suggestion_id, tenant_id)
        if not suggestion:
            raise NotFoundException(message=f"Suggestion '{suggestion_id}' not found")
        if suggestion.status not in [SuggestionStatus.ACCEPTED.value, SuggestionStatus.PENDING.value]:
            raise ValidationException(message=f"Cannot execute suggestion in status '{suggestion.status}'")

        start = datetime.now(UTC)
        suggestion.status = SuggestionStatus.EXECUTING.value
        await self.session.flush()

        try:
            result = await self._execute_domain_action(suggestion)
            suggestion.status = SuggestionStatus.COMPLETED.value
            suggestion.execution_result_json = json.dumps(result, default=str)
            duration = int((datetime.now(UTC) - start).total_seconds() * 1000)

            await self._log_execution(
                tenant_id, suggestion_id, suggestion.suggestion_type, suggestion.domain,
                "executed", result, True, "", duration,
            )
        except Exception as e:
            suggestion.status = SuggestionStatus.FAILED.value
            suggestion.execution_result_json = json.dumps({"error": str(e)[:500]}, default=str)
            duration = int((datetime.now(UTC) - start).total_seconds() * 1000)

            await self._log_execution(
                tenant_id, suggestion_id, suggestion.suggestion_type, suggestion.domain,
                "execution_failed", {"error": str(e)[:500]}, False, str(e)[:500], duration,
            )

        await self.session.flush()
        return suggestion

    async def rollback_suggestion(self, suggestion_id: str, tenant_id: str,
                                   reason: str = "") -> AISuggestion:
        suggestion = await self._get_suggestion(suggestion_id, tenant_id)
        if not suggestion:
            raise NotFoundException(message=f"Suggestion '{suggestion_id}' not found")
        if suggestion.status != SuggestionStatus.COMPLETED.value:
            raise ValidationException(message=f"Cannot rollback suggestion in status '{suggestion.status}'")

        suggestion.status = SuggestionStatus.ROLLED_BACK.value
        suggestion.rollback_data_json = json.dumps({"reason": reason, "rolled_back_at": datetime.now(UTC).isoformat()}, default=str)
        await self.session.flush()

        await self._log_execution(
            tenant_id, suggestion_id, suggestion.suggestion_type, suggestion.domain,
            "rolled_back", {"reason": reason}, True, "", 0,
        )
        return suggestion

    async def provide_feedback(self, suggestion_id: str, tenant_id: str,
                                feedback_type: str, feedback_detail: str = "",
                                rating: int = 0) -> AISuggestion:
        suggestion = await self._get_suggestion(suggestion_id, tenant_id)
        if not suggestion:
            raise NotFoundException(message=f"Suggestion '{suggestion_id}' not found")

        existing_feedback = json.loads(suggestion.feedback_json) if suggestion.feedback_json else {}
        existing_feedback.update({
            "feedback_type": feedback_type,
            "feedback_detail": feedback_detail,
            "rating": rating,
            "feedback_at": datetime.now(UTC).isoformat(),
            "feedback_by": actor_id_var.get(""),
        })
        suggestion.feedback_json = json.dumps(existing_feedback, default=str)
        await self.session.flush()
        return suggestion

    async def list_suggestions(self, tenant_id: str, domain: str = "",
                                suggestion_type: str = "", status: str = "",
                                page: int = 1, page_size: int = 20) -> tuple[list[AISuggestion], int]:
        conditions = [AISuggestion.tenant_id == tenant_id]
        if domain:
            conditions.append(AISuggestion.domain == domain)
        if suggestion_type:
            conditions.append(AISuggestion.suggestion_type == suggestion_type)
        if status:
            conditions.append(AISuggestion.status == status)

        stmt = select(AISuggestion).where(*conditions).order_by(AISuggestion.created_at.desc())
        total_result = await self.session.execute(
            select(func.count()).select_from(AISuggestion).where(*conditions)
        )
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size
        result = await self.session.execute(stmt.offset(offset).limit(page_size))
        return list(result.scalars().all()), total

    async def get_domain_handlers(self, domain: str = "") -> dict:
        if domain:
            return self.DOMAIN_SUGGESTION_HANDLERS.get(domain, {})
        return self.DOMAIN_SUGGESTION_HANDLERS

    async def _execute_domain_action(self, suggestion: AISuggestion) -> dict:
        data = json.loads(suggestion.suggestion_data_json)
        handler = self.DOMAIN_SUGGESTION_HANDLERS.get(suggestion.domain, {}).get(suggestion.suggestion_type)

        if not handler:
            return {"status": "skipped", "reason": "No handler configured"}

        result = {
            "domain": suggestion.domain,
            "suggestion_type": suggestion.suggestion_type,
            "action": "draft_created",
            "target_entity_type": suggestion.target_entity_type,
            "draft_type": handler.get("draft_types", ["unknown"])[0] if handler.get("draft_types") else "unknown",
            "data_keys": list(data.keys()) if isinstance(data, dict) else [],
        }
        return result

    async def _log_execution(self, tenant_id: str, suggestion_id: str,
                              suggestion_type: str, domain: str, action: str,
                              detail: dict, is_success: bool, error_message: str,
                              duration_ms: int):
        log = AISuggestionExecutionLog(
            tenant_id=tenant_id, suggestion_id=suggestion_id,
            suggestion_type=suggestion_type, domain=domain,
            action=action, action_detail_json=json.dumps(detail, default=str),
            is_success=is_success, error_message=error_message,
            duration_ms=duration_ms, actor_id=actor_id_var.get(""),
            trace_id=trace_id_var.get(""),
        )
        self.session.add(log)
        await self.session.flush()

    async def _get_suggestion(self, suggestion_id: str, tenant_id: str) -> AISuggestion | None:
        stmt = select(AISuggestion).where(
            AISuggestion.id == suggestion_id, AISuggestion.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_by_idempotency_key(self, tenant_id: str, key: str) -> AISuggestion | None:
        stmt = select(AISuggestion).where(
            AISuggestion.tenant_id == tenant_id, AISuggestion.idempotency_key == key,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
