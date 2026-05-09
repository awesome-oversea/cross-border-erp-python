from __future__ import annotations

from erp.connectors.base import ConnectorConfig, TaxConnector


class EuVatConnector(TaxConnector):
    EU_VAT_RATES: dict[str, float] = {
        "DE": 0.19,
        "FR": 0.20,
        "IT": 0.22,
        "ES": 0.21,
        "NL": 0.21,
        "BE": 0.21,
        "AT": 0.20,
        "PL": 0.23,
        "SE": 0.25,
        "DK": 0.25,
        "FI": 0.24,
        "IE": 0.23,
        "PT": 0.23,
        "GR": 0.24,
        "CZ": 0.21,
        "RO": 0.19,
        "HU": 0.27,
        "BG": 0.20,
        "HR": 0.25,
        "SK": 0.20,
    }

    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="eu_vat",
            connector_name="EU VAT",
            connector_type="tax",
            base_url="https://ec.europa.eu/taxation_customs",
        ))

    async def calculate_tax(self, amount: float, country: str, region: str = "", tax_code: str = "") -> dict:
        country_code = country.upper()
        vat_rate = self.EU_VAT_RATES.get(country_code, 0.0)
        tax_amount = round(amount * vat_rate, 2)
        return {
            "success": True,
            "country": country_code,
            "tax_type": "VAT",
            "tax_rate": vat_rate,
            "tax_amount": tax_amount,
            "total_amount": round(amount + tax_amount, 2),
            "currency": "EUR",
        }

    async def validate_vat(self, vat_number: str, country: str) -> dict:
        country_code = country.upper()
        is_valid_format = (
            vat_number.startswith(country_code)
            and len(vat_number) >= 8
            and vat_number[len(country_code):].isdigit()
        )
        return {
            "success": True,
            "vat_number": vat_number,
            "country": country_code,
            "is_valid": is_valid_format,
            "name": "Sample Company" if is_valid_format else "",
            "address": "Sample Address" if is_valid_format else "",
        }


class UsTaxConnector(TaxConnector):
    US_TAX_RATES: dict[str, float] = {
        "CA": 0.0825,
        "NY": 0.08,
        "TX": 0.0625,
        "FL": 0.06,
        "IL": 0.0625,
        "PA": 0.06,
        "OH": 0.0575,
        "GA": 0.04,
        "NC": 0.0475,
        "MI": 0.06,
        "NJ": 0.06625,
        "VA": 0.043,
        "WA": 0.065,
        "AZ": 0.056,
        "MA": 0.0625,
        "TN": 0.07,
        "IN": 0.07,
        "MO": 0.04225,
        "MD": 0.06,
        "WI": 0.05,
    }

    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="us_tax",
            connector_name="US Sales Tax",
            connector_type="tax",
            base_url="https://api.taxjar.com/v2",
        ))

    async def calculate_tax(self, amount: float, country: str, region: str = "", tax_code: str = "") -> dict:
        if country.upper() != "US":
            return {
                "success": False,
                "error": "US Tax connector only supports US",
                "country": country,
            }
        state_code = region.upper() if region else "CA"
        tax_rate = self.US_TAX_RATES.get(state_code, 0.0)
        tax_amount = round(amount * tax_rate, 2)
        return {
            "success": True,
            "country": "US",
            "state": state_code,
            "tax_type": "Sales Tax",
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "total_amount": round(amount + tax_amount, 2),
            "currency": "USD",
        }

    async def validate_vat(self, vat_number: str, country: str) -> dict:
        return {
            "success": True,
            "vat_number": vat_number,
            "country": country.upper(),
            "is_valid": False,
            "message": "US does not use VAT system",
        }
