from __future__ import annotations

from dataclasses import dataclass

PLATFORM_COMMISSION_RATES: dict[str, dict] = {
    "amazon": {"default": 0.15, "categories": {"electronics": 0.08, "clothing": 0.17, "home": 0.15}},
    "ebay": {"default": 0.13, "categories": {}},
    "shopify": {"default": 0.0, "categories": {}, "note": "Shopify does not charge commission"},
    "aliexpress": {"default": 0.08, "categories": {}},
    "wish": {"default": 0.15, "categories": {}},
    "tiktok_shop": {"default": 0.05, "categories": {}},
}

WAREHOUSE_FEE_RATES: dict[str, dict] = {
    "fba": {"storage_per_cubic_foot_monthly": 2.40, "fulfillment_per_unit": 3.22, "long_term_monthly_per_cubic_foot": 6.90},
    "overseas": {"storage_per_unit_monthly": 0.50, "inbound_per_unit": 0.30, "outbound_per_unit": 0.50},
    "local": {"storage_per_unit_monthly": 0.20, "inbound_per_unit": 0.10, "outbound_per_unit": 0.20},
}

PACKAGING_COSTS: dict[str, float] = {
    "small_box": 0.50, "medium_box": 0.80, "large_box": 1.20,
    "poly_mailer": 0.15, "bubble_wrap": 0.30, "label": 0.05,
}


@dataclass
class BillingSimulationInput:
    platform: str = "amazon"
    category: str = ""
    sale_price: float = 0.0
    quantity: int = 1
    currency: str = "USD"
    weight_kg: float = 0.0
    warehouse_type: str = "fba"
    shipping_cost: float = 0.0
    cost_price: float = 0.0
    packaging_type: str = "medium_box"


class BillingEngine:
    def calculate_platform_commission(self, platform: str, sale_price: float, quantity: int = 1,
                                       category: str = "") -> dict:
        rates = PLATFORM_COMMISSION_RATES.get(platform, PLATFORM_COMMISSION_RATES["amazon"])
        rate = rates.get("categories", {}).get(category, rates.get("default", 0.15))
        commission = round(sale_price * quantity * rate, 2)
        return {"platform": platform, "category": category, "rate": rate,
                "commission": commission, "currency": "USD"}

    def calculate_warehouse_fee(self, warehouse_type: str, quantity: int = 1,
                                 storage_months: int = 1, cubic_feet: float = 0.0) -> dict:
        rates = WAREHOUSE_FEE_RATES.get(warehouse_type, WAREHOUSE_FEE_RATES["fba"])
        if warehouse_type == "fba":
            storage = round(rates["storage_per_cubic_foot_monthly"] * cubic_feet * storage_months, 2)
            fulfillment = round(rates["fulfillment_per_unit"] * quantity, 2)
            return {"warehouse_type": warehouse_type, "storage_fee": storage,
                    "fulfillment_fee": fulfillment, "total": round(storage + fulfillment, 2)}
        else:
            storage = round(rates["storage_per_unit_monthly"] * quantity * storage_months, 2)
            inbound = round(rates["inbound_per_unit"] * quantity, 2)
            outbound = round(rates["outbound_per_unit"] * quantity, 2)
            return {"warehouse_type": warehouse_type, "storage_fee": storage,
                    "inbound_fee": inbound, "outbound_fee": outbound,
                    "total": round(storage + inbound + outbound, 2)}

    def simulate(self, input_data: BillingSimulationInput) -> dict:
        commission = self.calculate_platform_commission(
            input_data.platform, input_data.sale_price, input_data.quantity, input_data.category)
        warehouse = self.calculate_warehouse_fee(input_data.warehouse_type, input_data.quantity)
        packaging = round(PACKAGING_COSTS.get(input_data.packaging_type, 0.5) * input_data.quantity, 2)

        total_revenue = round(input_data.sale_price * input_data.quantity, 2)
        total_cost = round(input_data.cost_price * input_data.quantity, 2)
        total_fees = round(commission["commission"] + warehouse["total"] + input_data.shipping_cost + packaging, 2)
        profit = round(total_revenue - total_cost - total_fees, 2)
        margin = round(profit / total_revenue * 100, 2) if total_revenue > 0 else 0

        return {
            "revenue": total_revenue, "cost": total_cost,
            "commission": commission["commission"], "warehouse_fee": warehouse["total"],
            "shipping_cost": input_data.shipping_cost, "packaging": packaging,
            "total_fees": total_fees, "profit": profit, "margin_pct": margin,
            "currency": input_data.currency,
            "breakdown": {"commission": commission, "warehouse": warehouse, "packaging": packaging},
        }

    def calculate_freight_allocate(self, total_freight: float, items: list[dict]) -> list[dict]:
        total_weight = sum(i.get("weight_kg", 0) for i in items)
        if total_weight <= 0:
            per_item = total_freight / len(items) if items else 0
            return [{"sku_id": i.get("sku_id", ""), "allocated_freight": round(per_item, 2)} for i in items]
        results = []
        for item in items:
            weight = item.get("weight_kg", 0)
            allocated = round(total_freight * (weight / total_weight), 2)
            results.append({"sku_id": item.get("sku_id", ""), "weight_kg": weight, "allocated_freight": allocated})
        return results

    def calculate_fba_head_cost(self, shipment_cost: float, total_units: int,
                                 damaged_units: int = 0, lost_units: int = 0) -> dict:
        per_unit = round(shipment_cost / total_units, 4) if total_units > 0 else 0
        damage_cost = round(per_unit * damaged_units, 2)
        lost_cost = round(per_unit * lost_units, 2)
        return {
            "shipment_cost": shipment_cost, "total_units": total_units,
            "per_unit_cost": per_unit, "damaged_units": damaged_units,
            "damage_cost": damage_cost, "lost_units": lost_units,
            "lost_cost": lost_cost, "net_cost": round(shipment_cost + damage_cost + lost_cost, 2),
        }
