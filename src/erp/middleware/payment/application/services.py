from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.payment.domain.adapters import (
    SUPPORTED_CHANNELS,
    PaymentRequest,
    RefundRequest,
    get_payment_registry,
)
from erp.shared.exceptions import ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.payment")


class PaymentAggregationService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._registry = get_payment_registry()

    async def pay(self, tenant_id: str, channel: str, amount: float, currency: str,
                  payment_type: str = "payment", counterparty_id: str = "",
                  counterparty_name: str = "", reference_type: str = "",
                  reference_id: str = "") -> dict:
        if channel not in SUPPORTED_CHANNELS:
            raise ValidationException(message=f"Unsupported payment channel: {channel}")
        if amount <= 0:
            raise ValidationException(message="Payment amount must be positive")

        adapter = self._registry.get(channel)
        if not adapter:
            raise ValidationException(message=f"Payment channel adapter not found: {channel}")

        request = PaymentRequest(
            tenant_id=tenant_id, channel=channel, amount=amount,
            currency=currency, payment_type=payment_type,
            counterparty_id=counterparty_id, counterparty_name=counterparty_name,
            reference_type=reference_type, reference_id=reference_id,
        )
        result = await adapter.pay(request)
        logger.info("payment_processed", channel=channel, amount=amount, currency=currency, success=result.success)
        return {
            "success": result.success, "channel": result.channel,
            "transaction_id": result.transaction_id, "status": result.status,
            "message": result.message,
        }

    async def refund(self, tenant_id: str, channel: str, original_transaction_id: str,
                     refund_amount: float, currency: str = "USD", reason: str = "") -> dict:
        if channel not in SUPPORTED_CHANNELS:
            raise ValidationException(message=f"Unsupported payment channel: {channel}")
        if refund_amount <= 0:
            raise ValidationException(message="Refund amount must be positive")

        adapter = self._registry.get(channel)
        if not adapter:
            raise ValidationException(message=f"Payment channel adapter not found: {channel}")

        request = RefundRequest(
            tenant_id=tenant_id, channel=channel,
            original_transaction_id=original_transaction_id,
            refund_amount=refund_amount, currency=currency, reason=reason,
        )
        result = await adapter.refund(request)
        logger.info("refund_processed", channel=channel, amount=refund_amount, success=result.success)
        return {
            "success": result.success, "refund_transaction_id": result.refund_transaction_id,
            "status": result.status, "message": result.message,
        }

    async def batch_pay(self, tenant_id: str, items: list[dict]) -> list[dict]:
        results = []
        for item in items:
            try:
                result = await self.pay(
                    tenant_id=tenant_id, channel=item.get("channel", "mock"),
                    amount=item.get("amount", 0), currency=item.get("currency", "USD"),
                    payment_type=item.get("payment_type", "payment"),
                    counterparty_id=item.get("counterparty_id", ""),
                    counterparty_name=item.get("counterparty_name", ""),
                    reference_type=item.get("reference_type", ""),
                    reference_id=item.get("reference_id", ""),
                )
                results.append(result)
            except Exception as e:
                results.append({"success": False, "message": str(e)})
        return results

    async def get_channels(self) -> list[dict]:
        channels = self._registry.list_channels()
        return [{"channel": c, "name": c.title(), "supported": True} for c in channels]

    async def get_balance(self, tenant_id: str, channel: str = "mock", currency: str = "USD") -> dict:
        adapter = self._registry.get(channel)
        if not adapter:
            raise ValidationException(message=f"Payment channel adapter not found: {channel}")
        balance = await adapter.get_balance(tenant_id, currency)
        return {
            "channel": balance.channel, "currency": balance.currency,
            "available": balance.available, "pending": balance.pending, "frozen": balance.frozen,
        }

    async def settlement_withdraw(self, tenant_id: str, channel: str, amount: float,
                                   currency: str = "USD", target_account: str = "") -> dict:
        logger.info("settlement_withdraw", channel=channel, amount=amount, currency=currency)
        return {
            "success": True, "channel": channel, "amount": amount,
            "currency": currency, "status": "processing",
            "message": "Withdrawal request submitted",
        }

    async def amazon_claim(self, tenant_id: str, order_id: str, claim_type: str,
                           claim_amount: float, currency: str = "USD") -> dict:
        logger.info("amazon_claim", order_id=order_id, claim_type=claim_type, amount=claim_amount)
        return {
            "success": True, "order_id": order_id, "claim_type": claim_type,
            "claim_amount": claim_amount, "currency": currency,
            "status": "submitted", "message": "Amazon claim submitted",
        }
