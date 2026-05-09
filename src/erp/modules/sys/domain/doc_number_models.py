from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base
from erp.shared.exceptions import ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class DocNumberRule(Base):
    __tablename__ = "doc_number_rule"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    prefix: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    date_format: Mapped[str] = mapped_column(String(30), nullable=False, default="%Y%m%d")
    seq_length: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    reset_rule: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    separator: Mapped[str] = mapped_column(String(5), nullable=False, default="-")
    current_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DocNumberService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def define_rule(self, tenant_id: str, doc_type: str, prefix: str = "",
                          date_format: str = "%Y%m%d", seq_length: int = 4,
                          reset_rule: str = "daily", separator: str = "-") -> DocNumberRule:
        stmt = select(DocNumberRule).where(
            DocNumberRule.tenant_id == tenant_id,
            DocNumberRule.doc_type == doc_type,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise ValidationException(f"Doc number rule already exists: {doc_type}")
        rule = DocNumberRule(
            tenant_id=tenant_id, doc_type=doc_type, prefix=prefix,
            date_format=date_format, seq_length=seq_length,
            reset_rule=reset_rule, separator=separator,
        )
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def generate(self, tenant_id: str, doc_type: str) -> str:
        stmt = select(DocNumberRule).where(
            DocNumberRule.tenant_id == tenant_id,
            DocNumberRule.doc_type == doc_type,
        )
        rule = (await self.session.execute(stmt)).scalar_one_or_none()
        if not rule:
            raise ValidationException(f"Doc number rule not found: {doc_type}")

        now = datetime.now(UTC)
        should_reset = False
        if rule.last_generated_at:
            if rule.reset_rule == "daily":
                should_reset = rule.last_generated_at.date() != now.date()
            elif rule.reset_rule == "monthly":
                should_reset = (rule.last_generated_at.year != now.year or
                                rule.last_generated_at.month != now.month)
            elif rule.reset_rule == "yearly":
                should_reset = rule.last_generated_at.year != now.year
        else:
            should_reset = True

        if should_reset:
            rule.current_seq = 0

        rule.current_seq += 1
        rule.last_generated_at = now

        date_part = now.strftime(rule.date_format) if rule.date_format else ""
        seq_part = str(rule.current_seq).zfill(rule.seq_length)

        parts = [p for p in [rule.prefix, date_part, seq_part] if p]
        doc_number = rule.separator.join(parts)

        await self.session.flush()
        return doc_number

    async def list_rules(self, tenant_id: str) -> list[DocNumberRule]:
        stmt = select(DocNumberRule).where(DocNumberRule.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def init_defaults(self, tenant_id: str):
        defaults = [
            ("PO", "PO", "%Y%m%d", 4, "daily"),
            ("SO", "SO", "%Y%m%d", 4, "daily"),
            ("WO", "WO", "%Y%m%d", 4, "daily"),
            ("RO", "RO", "%Y%m%d", 4, "daily"),
            ("ASN", "ASN", "%Y%m%d", 4, "daily"),
            ("SHIP", "SHIP", "%Y%m%d", 4, "daily"),
            ("REFUND", "RF", "%Y%m%d", 4, "daily"),
            ("TRANSFER", "TR", "%Y%m%d", 4, "daily"),
            ("STOCKTAKE", "ST", "%Y%m%d", 4, "daily"),
            ("PAYMENT", "PAY", "%Y%m%d", 4, "daily"),
            ("SETTLEMENT", "SET", "%Y%m%d", 4, "daily"),
            ("FBA_SHIPMENT", "FBA", "%Y%m%d", 4, "daily"),
            ("CAMPAIGN", "AD", "%Y%m%d", 4, "daily"),
            ("PMS_SUGGESTION", "AI", "%Y%m%d", 6, "daily"),
        ]
        for doc_type, prefix, date_fmt, seq_len, reset in defaults:
            stmt = select(DocNumberRule).where(
                DocNumberRule.tenant_id == tenant_id,
                DocNumberRule.doc_type == doc_type,
            )
            existing = (await self.session.execute(stmt)).scalar_one_or_none()
            if not existing:
                await self.define_rule(tenant_id, doc_type, prefix, date_fmt, seq_len, reset)
