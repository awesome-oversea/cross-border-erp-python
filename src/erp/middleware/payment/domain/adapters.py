from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PaymentRequest:
    tenant_id: str = ""
    channel: str = ""
    amount: float = 0.0
    currency: str = "USD"
    payment_type: str = "payment"
    counterparty_id: str = ""
    counterparty_name: str = ""
    reference_type: str = ""
    reference_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PaymentResult:
    success: bool = False
    channel: str = ""
    transaction_id: str = ""
    status: str = ""
    message: str = ""


@dataclass
class RefundRequest:
    tenant_id: str = ""
    channel: str = ""
    original_transaction_id: str = ""
    refund_amount: float = 0.0
    currency: str = "USD"
    reason: str = ""


@dataclass
class RefundResult:
    success: bool = False
    refund_transaction_id: str = ""
    status: str = ""
    message: str = ""


@dataclass
class AccountBalance:
    channel: str = ""
    currency: str = ""
    available: float = 0.0
    pending: float = 0.0
    frozen: float = 0.0


class PaymentChannelAdapter(ABC):
    @abstractmethod
    async def pay(self, request: PaymentRequest) -> PaymentResult:
        pass

    @abstractmethod
    async def refund(self, request: RefundRequest) -> RefundResult:
        pass

    @abstractmethod
    async def get_balance(self, tenant_id: str, currency: str = "USD") -> AccountBalance:
        pass

    @abstractmethod
    def get_channel_name(self) -> str:
        pass


class MockPaymentAdapter(PaymentChannelAdapter):
    async def pay(self, request: PaymentRequest) -> PaymentResult:
        return PaymentResult(
            success=True, channel=request.channel,
            transaction_id=f"MOCK-{request.channel}-{id(request)}",
            status="completed", message="Mock payment processed",
        )

    async def refund(self, request: RefundRequest) -> RefundResult:
        return RefundResult(
            success=True,
            refund_transaction_id=f"MOCK-REFUND-{id(request)}",
            status="completed", message="Mock refund processed",
        )

    async def get_balance(self, tenant_id: str, currency: str = "USD") -> AccountBalance:
        return AccountBalance(channel="mock", currency=currency, available=100000.0, pending=5000.0, frozen=2000.0)

    def get_channel_name(self) -> str:
        return "mock"


SUPPORTED_CHANNELS = {
    "payoneer", "lianlian", "worldfirst", "alipay", "wechat",
    "paypal", "stripe", "mock",
}


class PaymentChannelRegistry:
    def __init__(self):
        self._adapters: dict[str, PaymentChannelAdapter] = {}

    def register(self, channel: str, adapter: PaymentChannelAdapter):
        self._adapters[channel] = adapter

    def get(self, channel: str) -> PaymentChannelAdapter | None:
        return self._adapters.get(channel)

    def list_channels(self) -> list[str]:
        return list(self._adapters.keys())


_registry = PaymentChannelRegistry()
_registry.register("mock", MockPaymentAdapter())
_registry.register("payoneer", MockPaymentAdapter())
_registry.register("paypal", MockPaymentAdapter())
_registry.register("stripe", MockPaymentAdapter())
_registry.register("alipay", MockPaymentAdapter())
_registry.register("wechat", MockPaymentAdapter())
_registry.register("lianlian", MockPaymentAdapter())
_registry.register("worldfirst", MockPaymentAdapter())


def get_payment_registry() -> PaymentChannelRegistry:
    return _registry
