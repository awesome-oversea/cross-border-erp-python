from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProfitCalculationInput:
    revenue: float = 0.0
    purchase_cost: float = 0.0
    head_freight: float = 0.0
    warehouse_fee: float = 0.0
    platform_commission: float = 0.0
    advertising_cost: float = 0.0
    payment_fee: float = 0.0
    last_mile_cost: float = 0.0
    other_costs: float = 0.0
    vat_amount: float = 0.0
    currency: str = "USD"
    quantity: int = 1


@dataclass
class ProfitResult:
    gross_profit: float = 0.0
    gross_margin_pct: float = 0.0
    operating_profit: float = 0.0
    operating_margin_pct: float = 0.0
    net_profit: float = 0.0
    net_margin_pct: float = 0.0
    cost_breakdown: dict = field(default_factory=dict)
    currency: str = "USD"


class ProfitEngine:
    def calculate(self, input_data: ProfitCalculationInput) -> ProfitResult:
        cogs = input_data.purchase_cost + input_data.head_freight
        gross_profit = input_data.revenue - cogs
        gross_margin = round(gross_profit / input_data.revenue * 100, 2) if input_data.revenue > 0 else 0

        operating_expenses = (input_data.warehouse_fee + input_data.platform_commission +
                              input_data.advertising_cost + input_data.payment_fee +
                              input_data.last_mile_cost + input_data.other_costs)
        operating_profit = gross_profit - operating_expenses
        operating_margin = round(operating_profit / input_data.revenue * 100, 2) if input_data.revenue > 0 else 0

        net_profit = operating_profit - input_data.vat_amount
        net_margin = round(net_profit / input_data.revenue * 100, 2) if input_data.revenue > 0 else 0

        return ProfitResult(
            gross_profit=round(gross_profit, 2), gross_margin_pct=gross_margin,
            operating_profit=round(operating_profit, 2), operating_margin_pct=operating_margin,
            net_profit=round(net_profit, 2), net_margin_pct=net_margin,
            cost_breakdown={
                "cogs": round(cogs, 2),
                "purchase_cost": input_data.purchase_cost,
                "head_freight": input_data.head_freight,
                "operating_expenses": round(operating_expenses, 2),
                "warehouse_fee": input_data.warehouse_fee,
                "platform_commission": input_data.platform_commission,
                "advertising_cost": input_data.advertising_cost,
                "payment_fee": input_data.payment_fee,
                "last_mile_cost": input_data.last_mile_cost,
                "other_costs": input_data.other_costs,
                "vat": input_data.vat_amount,
            },
            currency=input_data.currency,
        )

    def calculate_settlement(self, order_amount: float, platform: str = "amazon",
                              cost_price: float = 0.0, shipping_fee: float = 0.0,
                              commission_rate: float = 0.15, vat_rate: float = 0.0,
                              advertising_share: float = 0.0) -> dict:
        commission = round(order_amount * commission_rate, 2)
        vat = round(order_amount * vat_rate, 2)
        total_deductions = round(commission + vat + advertising_share, 2)
        settlement_amount = round(order_amount - total_deductions, 2)
        profit = round(settlement_amount - cost_price - shipping_fee, 2)
        margin = round(profit / order_amount * 100, 2) if order_amount > 0 else 0

        return {
            "order_amount": order_amount, "commission": commission,
            "vat": vat, "advertising_share": advertising_share,
            "total_deductions": total_deductions, "settlement_amount": settlement_amount,
            "cost_price": cost_price, "shipping_fee": shipping_fee,
            "profit": profit, "margin_pct": margin, "platform": platform,
        }

    def aggregate_by_period(self, records: list[dict], period_key: str = "month") -> dict:
        aggregated: dict[str, dict] = {}
        for r in records:
            key = r.get(period_key, "unknown")
            if key not in aggregated:
                aggregated[key] = {"revenue": 0, "cost": 0, "profit": 0, "count": 0}
            aggregated[key]["revenue"] += r.get("revenue", 0)
            aggregated[key]["cost"] += r.get("cost", 0)
            aggregated[key]["profit"] += r.get("profit", 0)
            aggregated[key]["count"] += 1

        result = {}
        for key, val in aggregated.items():
            margin = round(val["profit"] / val["revenue"] * 100, 2) if val["revenue"] > 0 else 0
            result[key] = {k: round(v, 2) if isinstance(v, float) else v for k, v in val.items()}
            result[key]["margin_pct"] = margin
        return result
