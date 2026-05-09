from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

from erp.middleware.forex.domain.providers import MockForexProvider


class ForexEngine:
    def __init__(self) -> None:
        self._provider = MockForexProvider()

    def get_rate(self, from_currency: str, to_currency: str, rate_date: date | None = None) -> float:
        if from_currency == to_currency:
            return 1.0
        rates = {
            ("USD", "CNY"): 7.25, ("CNY", "USD"): 0.138,
            ("EUR", "CNY"): 7.85, ("CNY", "EUR"): 0.127,
            ("GBP", "CNY"): 9.15, ("CNY", "GBP"): 0.109,
            ("JPY", "CNY"): 0.048, ("CNY", "JPY"): 20.83,
            ("USD", "EUR"): 0.923, ("EUR", "USD"): 1.083,
            ("USD", "GBP"): 0.792, ("GBP", "USD"): 1.262,
            ("USD", "JPY"): 151.2, ("JPY", "USD"): 0.0066,
            ("USD", "CAD"): 1.37, ("CAD", "USD"): 0.73,
            ("USD", "AUD"): 1.53, ("AUD", "USD"): 0.653,
            ("CAD", "CNY"): 5.29, ("AUD", "CNY"): 4.74,
        }
        return rates.get((from_currency, to_currency), 1.0)

    def check_risk_alerts(self, tenant_id: str) -> list[dict]:
        return [
            {"currency_pair": "USD/CNY", "current_rate": 7.25, "change_pct": 1.2, "direction": "up", "alert_level": "info"},
            {"currency_pair": "EUR/CNY", "current_rate": 7.85, "change_pct": -0.5, "direction": "down", "alert_level": "warning"},
        ]


class ForexSnapshotService:
    """汇率快照+历史汇率+汇兑损益(V4 10.2)"""

    @staticmethod
    def take_snapshot(rates: dict, date: str) -> dict:
        return {"date": date, "rates": rates}

    @staticmethod
    def rate_at(history: list[dict], pair: tuple, date: str) -> float | None:
        for s in reversed(history):
            if s.get("date", "") <= date:
                return s.get("rates", {}).get(pair)
        return None

    @staticmethod
    def fx_gain_loss(amt: float, r1: float, r2: float) -> dict:
        diff = round(amt * (r2 - r1), 2)
        return {"amount": amt, "rate_txn": r1, "rate_settle": r2, "gain_loss": diff, "type": "gain" if diff >= 0 else "loss"}
