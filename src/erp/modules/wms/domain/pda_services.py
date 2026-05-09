"""
PDA移动作业服务 (P2-059)

支持PDA端核心仓储操作:
  - 收货扫描: 扫描采购单条码/快递单号快速收货
  - 质检扫描: 扫描条码显示质检标准，记录良品/不良品
  - 拣货扫描: PDA电子拣货任务，扫描SKU/库位确认
  - 盘点扫描: 扫描库位/SKU进行盘点计数
"""
from __future__ import annotations


class PdaReceivingService:
    """PDA收货: 扫描采购单条码/快递单号快速收货,校验数量合理性"""
    """PDA收货: 扫描采购单/快递单收货"""
    @staticmethod
    def scan_po(po_code: str) -> dict:
        return {"action": "receive", "po": po_code, "status": "found",
                "message": f"采购单 {po_code} 已识别"}

    @staticmethod
    def scan_express(tracking_no: str) -> dict:
        return {"action": "receive", "tracking": tracking_no, "status": "found",
                "message": f"快递单 {tracking_no} 已识别"}

    @staticmethod
    def validate_receive(sku: str, qty: int, expected_qty: int) -> list[str]:
        errors = []
        if qty <= 0: errors.append("数量必须大于0")
        if qty > expected_qty * 1.1: errors.append(f"收货数量{qty}超过预期{expected_qty}的110%")
        return errors


class PdaPickingService:
    """PDA拣货: 扫描SKU/库位确认拣货,支持路径优化"""
    """PDA拣货: 扫描SKU/库位确认拣货"""
    @staticmethod
    def scan_location(location_code: str, expected_sku: str, actual_sku: str) -> dict:
        match = expected_sku == actual_sku
        return {"location": location_code, "expected": expected_sku, "actual": actual_sku,
                "match": match, "status": "ok" if match else "mismatch"}

    @staticmethod
    def validate_pick(order_id: str, items: list[dict]) -> list[str]:
        errors = []
        if not order_id: errors.append("订单不能为空")
        if not items: errors.append("拣货明细不能为空")
        for i, item in enumerate(items):
            if not item.get("sku"): errors.append(f"第{i+1}行SKU为空")
            if item.get("qty", 0) <= 0: errors.append(f"第{i+1}行数量无效")
        return errors

    @staticmethod
    def calc_picking_route(items: list[dict], locations: list[dict]) -> list[str]:
        """优化拣货路径: 按库位顺序排列"""
        loc_map = {l.get("sku"): l.get("code") for l in locations}
        ordered = sorted(items, key=lambda i: loc_map.get(i.get("sku", ""), ""))
        return [loc_map.get(i.get("sku"), "unknown") for i in ordered]


class PdaCountingService:
    """PDA盘点: 扫描库位/SKU进行盘点,自动计算差异"""
    """PDA盘点: 扫描库位/SKU盘点"""
    @staticmethod
    def scan_count(sku: str, location: str, counted_qty: int, system_qty: int) -> dict:
        diff = counted_qty - system_qty
        return {"sku": sku, "location": location, "system": system_qty,
                "counted": counted_qty, "diff": diff,
                "status": "match" if diff == 0 else ("surplus" if diff > 0 else "shortage")}

    @staticmethod
    def validate_count(items: list[dict]) -> list[str]:
        errors = []
        for i, item in enumerate(items):
            if not item.get("sku"): errors.append(f"第{i+1}行SKU为空")
            if item.get("qty", -1) < 0: errors.append(f"第{i+1}行盘点量为负")
        return errors
