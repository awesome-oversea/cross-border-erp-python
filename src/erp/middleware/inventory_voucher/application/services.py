from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.inventory_voucher.domain.engine import InventoryVoucher, InventoryVoucherEngine
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.inventory_voucher")


class InventoryVoucherService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = InventoryVoucherEngine()

    async def create_voucher(self, tenant_id: str, voucher_type: str, warehouse_id: str,
                              lines: list[dict], reference_type: str = "", reference_id: str = "",
                              operator_id: str = "", remark: str = "") -> dict:
        voucher = self._engine.create_voucher(voucher_type, warehouse_id, lines, reference_type, reference_id, operator_id, remark)
        return self._voucher_to_dict(voucher)

    async def post_voucher(self, tenant_id: str, voucher_no: str) -> dict:
        voucher = InventoryVoucher(voucher_no=voucher_no, status="draft")
        return self._engine.post_voucher(voucher)

    async def cancel_voucher(self, tenant_id: str, voucher_no: str, reason: str = "") -> dict:
        voucher = InventoryVoucher(voucher_no=voucher_no, status="draft")
        return self._engine.cancel_voucher(voucher, reason)

    async def generate_from_purchase(self, tenant_id: str, purchase_order: dict) -> dict:
        voucher = self._engine.generate_from_purchase(purchase_order)
        return self._voucher_to_dict(voucher)

    async def generate_from_sales(self, tenant_id: str, sales_order: dict) -> dict:
        voucher = self._engine.generate_from_sales(sales_order)
        return self._voucher_to_dict(voucher)

    def _voucher_to_dict(self, voucher: InventoryVoucher) -> dict:
        return {
            "voucher_no": voucher.voucher_no, "voucher_type": voucher.voucher_type,
            "direction": voucher.direction, "warehouse_id": voucher.warehouse_id,
            "reference_type": voucher.reference_type, "reference_id": voucher.reference_id,
            "lines": [{"sku_id": line.sku_id, "sku_name": line.sku_name, "quantity": line.quantity,
                        "unit_cost": line.unit_cost, "amount": line.amount, "warehouse_id": line.warehouse_id,
                        "location_id": line.location_id, "batch_no": line.batch_no} for line in voucher.lines],
            "total_quantity": voucher.total_quantity, "total_amount": voucher.total_amount,
            "status": voucher.status, "operator_id": voucher.operator_id, "remark": voucher.remark,
        }
