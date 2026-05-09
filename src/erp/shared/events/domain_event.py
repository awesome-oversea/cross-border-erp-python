from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    event_version: str = "v1"
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = None
    tenant_id: str = ""
    domain: str = ""
    aggregate_type: str = ""
    aggregate_id: str = ""
    trace_id: str = ""
    actor: str = ""
    data_scope: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    payload_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "tenant_id": self.tenant_id,
            "domain": self.domain,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "trace_id": self.trace_id,
            "actor": self.actor,
            "data_scope": self.data_scope,
            "payload": self.payload,
            "payload_hash": self.payload_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainEvent:
        occurred = data.get("occurred_at")
        published = data.get("published_at")
        if isinstance(occurred, str):
            occurred = datetime.fromisoformat(occurred)
        if isinstance(published, str):
            published = datetime.fromisoformat(published)
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=data.get("event_type", ""),
            event_version=data.get("event_version", "v1"),
            occurred_at=occurred or datetime.now(UTC),
            published_at=published,
            tenant_id=data.get("tenant_id", ""),
            domain=data.get("domain", ""),
            aggregate_type=data.get("aggregate_type", ""),
            aggregate_id=data.get("aggregate_id", ""),
            trace_id=data.get("trace_id", ""),
            actor=data.get("actor", ""),
            data_scope=data.get("data_scope", ""),
            payload=data.get("payload", {}),
            payload_hash=data.get("payload_hash", ""),
        )


@dataclass
class RecommendationSubmitted(DomainEvent):
    recommendation_id: str = ""
    erp_reference_id: str = ""
    recommendation_type: str = ""
    target_object_type: str = ""
    target_object_id: str = ""
    content: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    confidence: float = 0.0
    evidence_chain_id: str = ""
    data_sources: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    explainability: str = ""
    requested_action: str = ""
    approval_policy: str = ""

    def __post_init__(self):
        self.event_type = "erp.recommendation.submitted.v1"
        self.domain = self.domain or "pms_integration"
        self.aggregate_type = "recommendation"


@dataclass
class RecommendationAccepted(DomainEvent):
    recommendation_id: str = ""
    erp_reference_id: str = ""

    def __post_init__(self):
        self.event_type = "erp.recommendation.accepted.v1"
        self.domain = "pms_integration"
        self.aggregate_type = "recommendation"


@dataclass
class RecommendationRejected(DomainEvent):
    recommendation_id: str = ""
    erp_reference_id: str = ""
    rejection_reason: str = ""

    def __post_init__(self):
        self.event_type = "erp.recommendation.rejected.v1"
        self.domain = "pms_integration"
        self.aggregate_type = "recommendation"


@dataclass
class RecommendationApproved(DomainEvent):
    recommendation_id: str = ""
    erp_reference_id: str = ""

    def __post_init__(self):
        self.event_type = "erp.recommendation.approved.v1"
        self.domain = "pms_integration"
        self.aggregate_type = "recommendation"


@dataclass
class RecommendationExecuting(DomainEvent):
    recommendation_id: str = ""
    erp_reference_id: str = ""

    def __post_init__(self):
        self.event_type = "erp.recommendation.executing.v1"
        self.domain = "pms_integration"
        self.aggregate_type = "recommendation"


@dataclass
class RecommendationExecuted(DomainEvent):
    recommendation_id: str = ""
    erp_reference_id: str = ""
    execution_result: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.event_type = "erp.recommendation.executed.v1"
        self.domain = "pms_integration"
        self.aggregate_type = "recommendation"


@dataclass
class RecommendationFailed(DomainEvent):
    recommendation_id: str = ""
    erp_reference_id: str = ""
    failure_reason: str = ""

    def __post_init__(self):
        self.event_type = "erp.recommendation.failed.v1"
        self.domain = "pms_integration"
        self.aggregate_type = "recommendation"


@dataclass
class RecommendationRolledBack(DomainEvent):
    recommendation_id: str = ""
    erp_reference_id: str = ""
    rollback_reason: str = ""

    def __post_init__(self):
        self.event_type = "erp.recommendation.rolled_back.v1"
        self.domain = "pms_integration"
        self.aggregate_type = "recommendation"


@dataclass
class RecommendationEffectMeasured(DomainEvent):
    recommendation_id: str = ""
    erp_reference_id: str = ""
    measured_result: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.event_type = "erp.bi.recommendation_effect.measured.v1"
        self.domain = "bi"
        self.aggregate_type = "recommendation_effect"
