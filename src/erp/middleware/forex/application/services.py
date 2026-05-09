from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import desc, select

from erp.middleware.forex.domain.models import ExchangeRate, ForexAlertRule
from erp.middleware.forex.domain.providers import ForexProvider, MockForexProvider
from erp.shared.exceptions import NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.forex")
DEFAULT_RATE_TARGETS = ["CNY", "EUR", "GBP", "JPY", "CAD", "AUD"]
DEFAULT_ALERT_RULES = [
    ("USD", "CNY", 1.5, "both"),
    ("EUR", "CNY", 1.5, "both"),
    ("GBP", "CNY", 2.0, "both"),
    ("USD", "JPY", 2.0, "both"),
]


class ForexService:
    def __init__(self, session: AsyncSession, provider: ForexProvider | None = None):
        self._session = session
        self._provider = provider or MockForexProvider()

    async def get_rate(self, tenant_id: str, from_currency: str, to_currency: str, rate_date: date | None = None) -> dict:
        from_currency = self._normalize_currency(from_currency)
        to_currency = self._normalize_currency(to_currency)
        if from_currency == to_currency:
            return {"from": from_currency, "to": to_currency, "rate": 1.0, "source": "identity", "date": str(rate_date or date.today())}

        target_date = rate_date or date.today()
        stmt = select(ExchangeRate).where(
            ExchangeRate.tenant_id == tenant_id,
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.rate_date <= target_date,
        ).order_by(desc(ExchangeRate.rate_date)).limit(1)
        res = await self._session.execute(stmt)
        rate_record = res.scalar_one_or_none()

        if rate_record:
            return {
                "from": from_currency, "to": to_currency, "rate": rate_record.rate,
                "source": rate_record.source, "date": str(rate_record.rate_date),
            }

        live_rate = await self._provider.get_rate(from_currency, to_currency, target_date)
        if live_rate is not None:
            return {
                "from": from_currency, "to": to_currency, "rate": live_rate,
                "source": "live", "date": str(target_date),
            }

        raise NotFoundException(message=f"No exchange rate found for {from_currency}->{to_currency}")

    async def list_rates(
        self,
        tenant_id: str,
        base_currency: str = "USD",
        target_currencies: list[str] | None = None,
        rate_date: date | None = None,
    ) -> dict:
        base_currency = self._normalize_currency(base_currency)
        targets = self._normalize_currency_list(target_currencies) or DEFAULT_RATE_TARGETS
        rates: dict[str, float] = {}
        missing: list[str] = []
        for target in targets:
            if target == base_currency:
                continue
            try:
                rate_info = await self.get_rate(tenant_id, base_currency, target, rate_date)
                rates[target] = rate_info["rate"]
            except NotFoundException:
                missing.append(target)

        return {
            "base": base_currency,
            "date": str(rate_date or date.today()),
            "rates": rates,
            "missing_targets": missing,
        }

    async def get_snapshot(self, tenant_id: str, from_currency: str, to_currency: str, snapshot_date: date) -> dict:
        from_currency = self._normalize_currency(from_currency)
        to_currency = self._normalize_currency(to_currency)
        stmt = select(ExchangeRate).where(
            ExchangeRate.tenant_id == tenant_id,
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.rate_date == snapshot_date,
            ExchangeRate.is_snapshot,
        )
        res = await self._session.execute(stmt)
        rate_record = res.scalar_one_or_none()
        if not rate_record:
            raise NotFoundException(message=f"No snapshot found for {from_currency}->{to_currency} on {snapshot_date}")
        return {"from": from_currency, "to": to_currency, "rate": rate_record.rate, "date": str(rate_record.rate_date)}

    async def get_history(self, tenant_id: str, from_currency: str, to_currency: str,
                          start_date: date, end_date: date) -> Sequence[ExchangeRate]:
        from_currency = self._normalize_currency(from_currency)
        to_currency = self._normalize_currency(to_currency)
        stmt = select(ExchangeRate).where(
            ExchangeRate.tenant_id == tenant_id,
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.rate_date >= start_date,
            ExchangeRate.rate_date <= end_date,
        ).order_by(ExchangeRate.rate_date)
        res = await self._session.execute(stmt)
        return res.scalars().all()

    async def convert(self, tenant_id: str, items: list[dict]) -> list[dict]:
        results = []
        for item in items:
            amount = item.get("amount", 0)
            from_curr = self._normalize_currency(item.get("from_currency", ""))
            to_curr = self._normalize_currency(item.get("to_currency", ""))
            rate_date = item.get("rate_date")
            target_date = date.fromisoformat(rate_date) if rate_date else date.today()

            rate_info = await self.get_rate(tenant_id, from_curr, to_curr, target_date)
            converted = round(amount * rate_info["rate"], 2)
            results.append({
                "original_amount": amount, "from_currency": from_curr,
                "to_currency": to_curr, "rate": rate_info["rate"],
                "converted_amount": converted, "rate_date": str(target_date),
            })
        return results

    async def calculate_gain_loss(self, tenant_id: str, original_amount: float, original_currency: str,
                                  original_rate: float, current_rate: float, target_currency: str = "CNY") -> dict:
        original_currency = self._normalize_currency(original_currency)
        target_currency = self._normalize_currency(target_currency)
        original_in_target = round(original_amount * original_rate, 2)
        current_in_target = round(original_amount * current_rate, 2)
        gain_loss = round(current_in_target - original_in_target, 2)
        return {
            "original_amount": original_amount, "original_currency": original_currency,
            "original_rate": original_rate, "current_rate": current_rate,
            "target_currency": target_currency,
            "original_in_target": original_in_target, "current_in_target": current_in_target,
            "gain_loss": gain_loss, "gain_loss_pct": round(gain_loss / original_in_target * 100, 4) if original_in_target else 0,
        }

    async def sync_rates(self, tenant_id: str, pairs: list[tuple[str, str]] | None = None) -> dict:
        if not pairs:
            pairs = [
                ("USD", "CNY"), ("EUR", "CNY"), ("GBP", "CNY"), ("JPY", "CNY"),
                ("USD", "EUR"), ("USD", "GBP"), ("USD", "JPY"), ("USD", "CAD"), ("USD", "AUD"),
            ]
        pairs = [(self._normalize_currency(from_c), self._normalize_currency(to_c)) for from_c, to_c in pairs]
        rates = await self._provider.get_rates_batch(pairs)
        today = date.today()
        saved = 0
        for (from_c, to_c), rate in rates.items():
            stmt = select(ExchangeRate).where(
                ExchangeRate.tenant_id == tenant_id,
                ExchangeRate.from_currency == from_c,
                ExchangeRate.to_currency == to_c,
                ExchangeRate.rate_date == today,
            )
            res = await self._session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                existing.rate = rate
                existing.source = "sync"
                existing.synced_at = datetime.now(UTC)
            else:
                record = ExchangeRate(
                    tenant_id=tenant_id, from_currency=from_c, to_currency=to_c,
                    rate=rate, source="sync", rate_date=today, is_snapshot=True,
                    synced_at=datetime.now(UTC),
                )
                self._session.add(record)
            saved += 1
        await self._session.flush()
        logger.info("forex_rates_synced", tenant_id=tenant_id, count=saved)
        return {"synced_count": saved, "date": str(today)}

    async def list_alert_rules(self, tenant_id: str, is_active: bool | None = None) -> Sequence[ForexAlertRule]:
        conditions = [ForexAlertRule.tenant_id == tenant_id]
        if is_active is not None:
            conditions.append(ForexAlertRule.is_active == is_active)
        stmt = select(ForexAlertRule).where(*conditions).order_by(ForexAlertRule.from_currency, ForexAlertRule.to_currency)
        res = await self._session.execute(stmt)
        return res.scalars().all()

    async def init_default_alert_rules(self, tenant_id: str) -> list[ForexAlertRule]:
        created: list[ForexAlertRule] = []
        for from_currency, to_currency, threshold_pct, direction in DEFAULT_ALERT_RULES:
            try:
                created.append(
                    await self.create_alert_rule(
                        tenant_id=tenant_id,
                        from_currency=from_currency,
                        to_currency=to_currency,
                        threshold_pct=threshold_pct,
                        direction=direction,
                    )
                )
            except ValidationException:
                continue
        return created

    async def create_alert_rule(
        self,
        tenant_id: str,
        from_currency: str,
        to_currency: str,
        threshold_pct: float = 5.0,
        direction: str = "both",
        is_active: bool = True,
    ) -> ForexAlertRule:
        from_currency = self._normalize_currency(from_currency)
        to_currency = self._normalize_currency(to_currency)
        direction = direction.strip().lower()

        if threshold_pct <= 0:
            raise ValidationException(message="Alert threshold_pct must be greater than 0")
        if direction not in {"up", "down", "both"}:
            raise ValidationException(message=f"Unsupported alert direction '{direction}'")

        existing = await self._get_alert_rule(tenant_id, from_currency, to_currency)
        if existing:
            raise ValidationException(message=f"Forex alert rule '{from_currency}->{to_currency}' already exists")

        rule = ForexAlertRule(
            tenant_id=tenant_id,
            from_currency=from_currency,
            to_currency=to_currency,
            threshold_pct=threshold_pct,
            direction=direction,
            is_active=is_active,
        )
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def get_risk_alerts(self, tenant_id: str) -> list[dict]:
        stmt = select(ForexAlertRule).where(
            ForexAlertRule.tenant_id == tenant_id,
            ForexAlertRule.is_active,
        )
        res = await self._session.execute(stmt)
        rules = res.scalars().all()
        alerts = []
        for rule in rules:
            try:
                rate_info = await self.get_rate(tenant_id, rule.from_currency, rule.to_currency)
                current_rate = rate_info["rate"]
                previous_rate = await self._get_previous_rate(tenant_id, rule.from_currency, rule.to_currency, date.today())
                base_rate = previous_rate.rate if previous_rate else current_rate
                if base_rate > 0:
                    change_pct_value = (current_rate - base_rate) / base_rate * 100
                    change_pct = abs(change_pct_value)
                    direction = "up" if change_pct_value > 0 else "down" if change_pct_value < 0 else "flat"
                    direction_matched = rule.direction == "both" or rule.direction == direction
                    already_alerted_today = rule.last_alerted_at is not None and rule.last_alerted_at.date() == date.today()
                    if change_pct >= rule.threshold_pct and direction_matched and not already_alerted_today:
                        rule.last_alerted_at = datetime.now(UTC)
                        alerts.append({
                            "from": rule.from_currency, "to": rule.to_currency,
                            "current_rate": current_rate, "base_rate": base_rate,
                            "change_pct": round(change_pct_value, 4),
                            "threshold_pct": rule.threshold_pct, "direction": direction,
                        })
            except Exception as exc:
                logger.warning(
                    "forex_alert_evaluation_failed",
                    from_currency=rule.from_currency,
                    to_currency=rule.to_currency,
                    error=str(exc),
                )
                continue

        if alerts:
            await self._session.flush()
        return alerts

    async def _get_alert_rule(self, tenant_id: str, from_currency: str, to_currency: str) -> ForexAlertRule | None:
        from_currency = self._normalize_currency(from_currency)
        to_currency = self._normalize_currency(to_currency)
        stmt = select(ForexAlertRule).where(
            ForexAlertRule.tenant_id == tenant_id,
            ForexAlertRule.from_currency == from_currency,
            ForexAlertRule.to_currency == to_currency,
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def _get_previous_rate(
        self,
        tenant_id: str,
        from_currency: str,
        to_currency: str,
        before_date: date,
    ) -> ExchangeRate | None:
        from_currency = self._normalize_currency(from_currency)
        to_currency = self._normalize_currency(to_currency)
        stmt = (
            select(ExchangeRate)
            .where(
                ExchangeRate.tenant_id == tenant_id,
                ExchangeRate.from_currency == from_currency,
                ExchangeRate.to_currency == to_currency,
                ExchangeRate.rate_date < before_date,
            )
            .order_by(desc(ExchangeRate.rate_date))
            .limit(1)
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    def _normalize_currency(currency: str) -> str:
        return currency.strip().upper()

    def _normalize_currency_list(self, currencies: list[str] | None) -> list[str] | None:
        if currencies is None:
            return None

        normalized: list[str] = []
        seen: set[str] = set()
        for currency in currencies:
            code = self._normalize_currency(currency)
            if not code or code in seen:
                continue
            seen.add(code)
            normalized.append(code)
        return normalized
