from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import TenantModel


class ExchangeRate(TenantModel):
    __tablename__ = "fms_exchange_rate"
    __table_args__ = (
        UniqueConstraint("tenant_id", "from_currency", "to_currency", "rate_date", name="uq_exchange_rate_date"),
        Index("ix_exchange_rate_lookup", "tenant_id", "from_currency", "to_currency", "rate_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    from_currency: Mapped[str] = mapped_column(String(10))
    to_currency: Mapped[str] = mapped_column(String(10))
    rate: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    rate_date: Mapped[date] = mapped_column(Date)
    is_snapshot: Mapped[bool] = mapped_column(default=False)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ForexAlertRule(TenantModel):
    __tablename__ = "fms_forex_alert_rule"
    __table_args__ = (
        UniqueConstraint("tenant_id", "from_currency", "to_currency", name="uq_forex_alert_pair"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    from_currency: Mapped[str] = mapped_column(String(10))
    to_currency: Mapped[str] = mapped_column(String(10))
    threshold_pct: Mapped[float] = mapped_column(Float, default=5.0)
    direction: Mapped[str] = mapped_column(String(10), default="both")
    is_active: Mapped[bool] = mapped_column(default=True)
    last_alerted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
