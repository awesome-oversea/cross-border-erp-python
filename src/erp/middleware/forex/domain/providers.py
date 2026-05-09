"""
汇率提供器 - 支持银联/央行/XE等多数据源 (P5-019)

数据源:
  - ChinaUnionPayProvider: 银联国际官网汇率(实时)
  - XeProvider: XE.com汇率(备用)
  - MockForexProvider: 开发/测试用
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from datetime import date


class ForexProvider(ABC):
    @abstractmethod
    async def get_rate(self, from_currency: str, to_currency: str, rate_date: date | None = None) -> float | None:
        pass

    @abstractmethod
    async def get_rates_batch(self, pairs: list[tuple[str, str]], rate_date: date | None = None) -> dict[tuple[str, str], float]:
        pass


class ChinaUnionPayProvider(ForexProvider):
    """
    银联国际汇率提供器

    数据源: https://www.unionpayintl.com/rates/
    返回银联发布的实时外汇牌价, 每日更新一次。
    """

    BASE_URL = "https://www.unionpayintl.com/rates"

    async def get_rate(self, from_currency: str, to_currency: str, rate_date: date | None = None) -> float | None:
        if from_currency == to_currency:
            return 1.0
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(f"{self.BASE_URL}/queryRate", params={
                    "baseCurrency": from_currency.upper(),
                    "targetCurrency": to_currency.upper(),
                }, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    return float(data.get("rate", data.get("exchangeRate", 0)))
        except Exception:
            pass
        return None

    async def get_rates_batch(self, pairs: list[tuple[str, str]], rate_date: date | None = None) -> dict[tuple[str, str], float]:
        result = {}
        for f, t in pairs:
            rate = await self.get_rate(f, t, rate_date)
            if rate is not None:
                result[(f, t)] = rate
        return result


class XeProvider(ForexProvider):
    """
    XE.com汇率提供器(备用源)

    当银联数据不可用时作为降级方案。
    """

    BASE_URL = "https://xecdapi.xe.com/v1"

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self._auth = (api_key, api_secret)

    async def get_rate(self, from_currency: str, to_currency: str, rate_date: date | None = None) -> float | None:
        if from_currency == to_currency:
            return 1.0
        try:
            async with httpx.AsyncClient(auth=self._auth) as c:
                r = await c.get(f"{self.BASE_URL}/convert_to.json", params={
                    "from": from_currency.upper(), "to": to_currency.upper(), "amount": 1.0,
                }, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    rates = data.get("to", [])
                    if rates:
                        return float(rates[0].get("mid", 0))
        except Exception:
            pass
        return None

    async def get_rates_batch(self, pairs: list[tuple[str, str]], rate_date: date | None = None) -> dict[tuple[str, str], float]:
        result = {}
        for f, t in pairs:
            rate = await self.get_rate(f, t, rate_date)
            if rate is not None:
                result[(f, t)] = rate
        return result


class MockForexProvider(ForexProvider):
    """Mock汇率提供器 - 用于开发/测试"""

    MOCK_RATES: dict[tuple[str, str], float] = {
        ("USD", "CNY"): 7.25, ("CNY", "USD"): 0.138,
        ("EUR", "CNY"): 7.85, ("CNY", "EUR"): 0.127,
        ("GBP", "CNY"): 9.15, ("CNY", "GBP"): 0.109,
        ("JPY", "CNY"): 0.048, ("CNY", "JPY"): 20.83,
        ("USD", "EUR"): 0.923, ("EUR", "USD"): 1.083,
        ("USD", "GBP"): 0.792, ("GBP", "USD"): 1.262,
        ("USD", "JPY"): 151.2, ("JPY", "USD"): 0.0066,
    }

    async def get_rate(self, from_currency: str, to_currency: str, rate_date: date | None = None) -> float | None:
        if from_currency == to_currency:
            return 1.0
        return self.MOCK_RATES.get((from_currency, to_currency))

    async def get_rates_batch(self, pairs: list[tuple[str, str]], rate_date: date | None = None) -> dict[tuple[str, str], float]:
        result = {}
        for pair in pairs:
            rate = await self.get_rate(pair[0], pair[1], rate_date)
            if rate is not None:
                result[pair] = rate
        return result
