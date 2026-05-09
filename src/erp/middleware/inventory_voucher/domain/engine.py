from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class VoucherType(StrEnum):
    PURCHASE_IN = "purchase_in"
    PURCHASE_RETURN = "purchase_return"
    SALES_OUT = "sales_out"
    SALES_RETURN = "sales_return"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    ADJUSTMENT_IN = "adjustment_in"
    ADJUSTMENT_OUT = "adjustment_out"
    FBA_SHIP_OUT = "fba_ship_out"
    DAMAGE_WRITE_OFF = "damage_write_off"


VOUCHER_TYPE_DIRECTIONS = {
    "purchase_in": "in", "purchase_return": "out",
    "sales_out": "out", "sales_return": "in",
    "transfer_in": "in", "transfer_out": "out",
    "adjustment_in": "in", "adjustment_out": "out",
    "fba_ship_out": "out", "damage_write_off": "out",
}


@dataclass
class VoucherLine:
    sku_id: str = ""
    sku_name: str = ""
    quantity: int = 0
    unit_cost: float = 0.0
    amount: float = 0.0
    warehouse_id: str = ""
    location_id: str = ""
    batch_no: str = ""


@dataclass
class InventoryVoucher:
    voucher_no: str = ""
    voucher_type: str = ""
    direction: str = ""
    warehouse_id: str = ""
    reference_type: str = ""
    reference_id: str = ""
    lines: list[VoucherLine] = field(default_factory=list)
    total_quantity: int = 0
    total_amount: float = 0.0
    status: str = "draft"
    operator_id: str = ""
    remark: str = ""


class InventoryVoucherEngine:
    def create_voucher(self, voucher_type: str, warehouse_id: str, lines: list[dict],
                        reference_type: str = "", reference_id: str = "",
                        operator_id: str = "", remark: str = "") -> InventoryVoucher:
        direction = VOUCHER_TYPE_DIRECTIONS.get(voucher_type, "in")
        voucher_lines: list[VoucherLine] = []
        total_qty = 0
        total_amount = 0.0

        for line in lines:
            qty = line.get("quantity", 0)
            unit_cost = line.get("unit_cost", 0)
            amount = round(qty * unit_cost, 2)
            voucher_lines.append(VoucherLine(
                sku_id=line.get("sku_id", ""), sku_name=line.get("sku_name", ""),
                quantity=qty, unit_cost=unit_cost, amount=amount,
                warehouse_id=warehouse_id, location_id=line.get("location_id", ""),
                batch_no=line.get("batch_no", ""),
            ))
            total_qty += qty
            total_amount += amount

        return InventoryVoucher(
            voucher_no=f"IV-{voucher_type[:3].upper()}-{id(lines) % 100000:05d}",
            voucher_type=voucher_type, direction=direction, warehouse_id=warehouse_id,
            reference_type=reference_type, reference_id=reference_id,
            lines=voucher_lines, total_quantity=total_qty, total_amount=round(total_amount, 2),
            status="draft", operator_id=operator_id, remark=remark,
        )

    def post_voucher(self, voucher: InventoryVoucher) -> dict:
        if voucher.status != "draft":
            return {"success": False, "error": f"Cannot post voucher in '{voucher.status}' status"}
        voucher.status = "posted"
        return {
            "success": True, "voucher_no": voucher.voucher_no,
            "status": "posted", "direction": voucher.direction,
            "total_quantity": voucher.total_quantity, "total_amount": voucher.total_amount,
            "inventory_changes": [
                {"sku_id": line.sku_id, "warehouse_id": line.warehouse_id,
                 "direction": voucher.direction, "quantity": line.quantity, "amount": line.amount}
                for line in voucher.lines
            ],
        }

    def cancel_voucher(self, voucher: InventoryVoucher, reason: str = "") -> dict:
        if voucher.status == "cancelled":
            return {"success": False, "error": "Voucher already cancelled"}
        voucher.status = "cancelled"
        return {"success": True, "voucher_no": voucher.voucher_no, "status": "cancelled", "reason": reason}

    def generate_from_purchase(self, purchase_order: dict) -> InventoryVoucher:
        lines = []
        for item in purchase_order.get("items", []):
            lines.append({
                "sku_id": item.get("sku_id", ""), "sku_name": item.get("sku_name", ""),
                "quantity": item.get("quantity", 0), "unit_cost": item.get("unit_cost", 0),
                "batch_no": item.get("batch_no", ""),
            })
        return self.create_voucher(
            voucher_type="purchase_in", warehouse_id=purchase_order.get("warehouse_id", ""),
            lines=lines, reference_type="purchase_order",
            reference_id=purchase_order.get("id", ""),
            operator_id=purchase_order.get("operator_id", ""),
            remark=f"Auto-generated from PO {purchase_order.get('id', '')}",
        )

    def generate_from_sales(self, sales_order: dict) -> InventoryVoucher:
        lines = []
        for item in sales_order.get("items", []):
            lines.append({
                "sku_id": item.get("sku_id", ""), "sku_name": item.get("sku_name", ""),
                "quantity": item.get("quantity", 0), "unit_cost": item.get("unit_cost", 0),
            })
        return self.create_voucher(
            voucher_type="sales_out", warehouse_id=sales_order.get("warehouse_id", ""),
            lines=lines, reference_type="sales_order",
            reference_id=sales_order.get("id", ""),
            operator_id=sales_order.get("operator_id", ""),
            remark=f"Auto-generated from SO {sales_order.get('id', '')}",
        )


class ExternalVoucherService:
    """外部凭证推送(V4 10.14): 金蝶/用友"""

    @staticmethod
    def format_for_kingdee(voucher: dict) -> dict:
        return {"FVoucherType": "transfer", "FDate": voucher.get("date", ""),
                "FEntry": [{"FAccountCode": e.get("account"), "FDebit": e.get("debit", 0), "FCredit": e.get("credit", 0)} for e in voucher.get("entries", [])]}

    @staticmethod
    def format_for_yonyou(voucher: dict) -> dict:
        return {"acc_id": voucher.get("tenant_id"), "voucher_type": "transfer",
                "entries": [{"code": e.get("account"), "debit": e.get("debit", 0), "credit": e.get("credit", 0)} for e in voucher.get("entries", [])]}

    @staticmethod
    def validate_voucher(entries: list[dict]) -> list[str]:
        errors = []
        if not entries: errors.append("凭证分录不能为空")
        total_debit = sum(e.get("debit", 0) for e in entries)
        total_credit = sum(e.get("credit", 0) for e in entries)
        if abs(total_debit - total_credit) > 0.01:
            errors.append(f"借贷不平衡: 借{total_debit}贷{total_credit}")
        return errors
