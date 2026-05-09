from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.invoice_tax.domain.engine import InvoiceTaxEngine, TaxCalculationInput
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.invoice_tax")


class InvoiceTaxService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = InvoiceTaxEngine()

    async def generate_invoice(self, tenant_id: str, invoice_type: str, items: list[dict],
                                counterparty: dict, country_code: str = "DE") -> dict:
        return self._engine.generate_invoice(tenant_id, invoice_type, items, counterparty, country_code)

    async def get_tax_rates(self, country_code: str = "") -> list[dict]:
        return self._engine.get_tax_rates(country_code)

    async def calculate_tax(self, amount: float, country_code: str = "DE", tax_type: str = "vat",
                             is_b2b: bool = False, tax_inclusive: bool = False) -> dict:
        return self._engine.calculate_tax(TaxCalculationInput(
            amount=amount, country_code=country_code, tax_type=tax_type,
            is_b2b=is_b2b, tax_inclusive=tax_inclusive,
        ))

    async def get_filing_data(self, tenant_id: str, period_start: str, period_end: str,
                               country_code: str = "DE") -> dict:
        return self._engine.get_filing_data(tenant_id, period_start, period_end, country_code)

    async def void_invoice(self, tenant_id: str, invoice_id: str, reason: str = "") -> dict:
        logger.info("invoice_voided", invoice_id=invoice_id, reason=reason)
        return {"invoice_id": invoice_id, "status": "voided", "reason": reason}

    async def red_flush_invoice(self, tenant_id: str, invoice_id: str, reason: str = "") -> dict:
        logger.info("invoice_red_flushed", invoice_id=invoice_id, reason=reason)
        return {"invoice_id": invoice_id, "status": "red_flushed", "reason": reason}
