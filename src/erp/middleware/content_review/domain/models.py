from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import TenantModel


class ContentReviewTask(TenantModel):
    __tablename__ = "sys_content_review_task"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    review_type: Mapped[str] = mapped_column(String(32))
    content_type: Mapped[str] = mapped_column(String(32))
    content_id: Mapped[str] = mapped_column(String(64), default="")
    content_text: Mapped[str] = mapped_column(Text, default="")
    content_url: Mapped[str] = mapped_column(String(512), default="")
    language: Mapped[str] = mapped_column(String(10), default="en")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    auto_result: Mapped[str] = mapped_column(String(32), default="")
    auto_detail: Mapped[str] = mapped_column(Text, default="")
    manual_result: Mapped[str] = mapped_column(String(32), default="")
    manual_detail: Mapped[str] = mapped_column(Text, default="")
    reviewer_id: Mapped[str] = mapped_column(String(64), default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rule_set_id: Mapped[str] = mapped_column(String(64), default="")
    source_domain: Mapped[str] = mapped_column(String(32), default="")
    source_id: Mapped[str] = mapped_column(String(64), default="")


class ContentReviewRule(TenantModel):
    __tablename__ = "sys_content_review_rule"
    __table_args__ = (
        UniqueConstraint("tenant_id", "rule_code", name="uq_content_review_rule_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_code: Mapped[str] = mapped_column(String(64))
    rule_name: Mapped[str] = mapped_column(String(128))
    rule_type: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(10), default="*")
    keywords_json: Mapped[str] = mapped_column(Text, default="[]")
    regex_patterns_json: Mapped[str] = mapped_column(Text, default="[]")
    severity: Mapped[str] = mapped_column(String(16), default="warning")
    is_active: Mapped[bool] = mapped_column(default=True)
