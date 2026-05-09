from __future__ import annotations

from dataclasses import dataclass

VAT_RATES: dict[str, float] = {
    "DE": 0.19, "FR": 0.20, "IT": 0.22, "ES": 0.21, "NL": 0.21,
    "GB": 0.20, "PL": 0.23, "BE": 0.21, "AT": 0.20, "SE": 0.25,
    "JP": 0.10, "AU": 0.10, "CA": 0.05, "US": 0.0,
}

INVOICE_TYPES = ["purchase", "sales", "credit_note", "proforma"]


@dataclass
class TaxCalculationInput:
    amount: float = 0.0
    currency: str = "USD"
    country_code: str = "DE"
    tax_type: str = "vat"
    is_b2b: bool = False
    tax_inclusive: bool = False


class InvoiceTaxEngine:
    def calculate_tax(self, input_data: TaxCalculationInput) -> dict:
        rate = VAT_RATES.get(input_data.country_code, 0.0)
        if input_data.is_b2b:
            rate = 0.0

        if input_data.tax_inclusive:
            net_amount = round(input_data.amount / (1 + rate), 2)
            tax_amount = round(input_data.amount - net_amount, 2)
        else:
            net_amount = input_data.amount
            tax_amount = round(input_data.amount * rate, 2)

        return {
            "net_amount": net_amount, "tax_rate": rate,
            "tax_amount": tax_amount, "gross_amount": round(net_amount + tax_amount, 2),
            "country_code": input_data.country_code, "tax_type": input_data.tax_type,
            "is_b2b": input_data.is_b2b,
        }

    def generate_invoice(self, tenant_id: str, invoice_type: str, items: list[dict],
                          counterparty: dict, country_code: str = "DE") -> dict:
        subtotal = sum(i.get("amount", 0) * i.get("quantity", 1) for i in items)
        tax_result = self.calculate_tax(TaxCalculationInput(amount=subtotal, country_code=country_code))
        return {
            "invoice_no": f"INV-{tenant_id[:8]}-{id(items) % 10000:04d}",
            "invoice_type": invoice_type, "status": "draft",
            "counterparty": counterparty, "items": items,
            "subtotal": subtotal, "tax_amount": tax_result["tax_amount"],
            "total": tax_result["gross_amount"], "currency": "EUR",
            "country_code": country_code, "tax_rate": tax_result["tax_rate"],
        }

    def get_tax_rates(self, country_code: str = "") -> list[dict]:
        if country_code:
            rate = VAT_RATES.get(country_code, 0.0)
            return [{"country_code": country_code, "vat_rate": rate}]
        return [{"country_code": k, "vat_rate": v} for k, v in VAT_RATES.items()]

    def get_filing_data(self, tenant_id: str, period_start: str, period_end: str,
                         country_code: str = "DE") -> dict:
        rate = VAT_RATES.get(country_code, 0.0)
        return {
            "period_start": period_start, "period_end": period_end,
            "country_code": country_code, "vat_rate": rate,
            "total_sales": 0, "total_vat_collected": 0,
            "total_purchases": 0, "total_vat_paid": 0,
            "net_vat_due": 0, "status": "draft",
        }


class InvoiceRedBlueService:
    """发票红冲(V4 10.8): 红字发票/作废"""

    @staticmethod
    def red_credit(original_invoice: dict, reason: str) -> dict:
        return {"red_invoice_no": f"RD-{original_invoice.get("invoice_no", "")}",
                "original_no": original_invoice.get("invoice_no", ""),
                "amount": -abs(original_invoice.get("amount", 0)),
                "reason": reason, "status": "red_credited"}

    @staticmethod
    def void_invoice(invoice_no: str, reason: str) -> dict:
        return {"invoice_no": invoice_no, "void_reason": reason, "status": "voided"}
