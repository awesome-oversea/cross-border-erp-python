"""
WMS 领域服务

提供仓库管理核心业务规则的纯函数实现，不依赖基础设施层。
包含:
- InventoryDomainService: 库存领域服务 (低库存判断、可用量计算、流水校验、库存估值)
- LocationDomainService: 库位领域服务 (类型校验、编码生成、存储能力判断)
- QualityInspectionDomainService: 质检领域服务 (校验、结果判定、合格率计算)
- StockCountDomainService: 盘点领域服务 (状态机、差异计算、明细校验)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erp.modules.wms.domain.models import Inventory, Location

VALID_LOCATION_TYPES = {"storage", "picking", "packing", "receiving", "shipping", "returns", "staging"}
VALID_MOVEMENT_TYPES = {"inbound", "outbound", "transfer", "adjustment", "return", "hold", "release"}


class InventoryDomainService:
    """
    库存领域服务

    提供库存相关的纯业务规则:
    - 低库存判断: 可用量 ≤ 安全库存即为低库存
    - 可用量计算: 在库量 - 预留量 (最小为0)
    - 流水校验: 移动类型合法性 + 出库库存充足性
    - 库存估值: 数量 × 单位成本
    """

    @staticmethod
    def is_low_stock(inventory: Inventory) -> bool:
        """
        判断是否低库存: 可用量 ≤ 安全库存

        参数:
            inventory: 库存实体

        返回:
            True 表示低库存
        """
        safety = getattr(inventory, "safety_qty", 0) or 0
        available = getattr(inventory, "available_qty", 0) or 0
        return available <= safety

    @staticmethod
    def calculate_available(qty_on_hand: int, qty_reserved: int) -> int:
        """
        计算可用量: 在库量 - 预留量 (最小为0，防止负数)

        参数:
            qty_on_hand: 在库量
            qty_reserved: 预留量

        返回:
            可用量 (≥ 0)
        """
        return max(0, qty_on_hand - qty_reserved)

    @staticmethod
    def validate_movement(movement_type: str, qty_change: int, current_qty: int) -> list[str]:
        """
        校验库存流水: 移动类型合法性 + 出库库存充足性

        参数:
            movement_type: 移动类型 (inbound/outbound/transfer/adjustment/return/hold/release)
            qty_change: 变更数量 (正数入库, 负数出库)
            current_qty: 当前在库量

        返回:
            错误列表 (空列表表示校验通过)
        """
        errors: list[str] = []
        if movement_type not in VALID_MOVEMENT_TYPES:
            errors.append(f"Invalid movement type '{movement_type}'")
        if movement_type == "outbound" and qty_change < 0 and current_qty + qty_change < 0:
            errors.append("Insufficient stock for outbound")
        return errors

    @staticmethod
    def calculate_stock_value(qty: int, unit_cost: float) -> float:
        """
        计算库存估值: 数量 × 单位成本，保留2位小数

        参数:
            qty: 库存数量
            unit_cost: 单位成本

        返回:
            库存估值
        """
        return round(qty * unit_cost, 2)


class LocationDomainService:
    """
    库位领域服务

    提供库位相关的纯业务规则:
    - 类型校验: 判断库位类型是否合法
    - 编码生成: 按 区域-通道-货架-货位 格式拼接
    - 存储能力判断: 活跃状态 + 允许存储的库位类型
    """

    @staticmethod
    def validate_location_type(location_type: str) -> bool:
        """
        校验库位类型是否合法

        参数:
            location_type: 库位类型

        返回:
            True 表示合法
        """
        return location_type in VALID_LOCATION_TYPES

    @staticmethod
    def generate_location_code(zone: str, aisle: str, shelf: str, bin_no: str) -> str:
        """
        生成库位编码: 按 区域-通道-货架-货位 格式拼接，忽略空值

        参数:
            zone: 区域
            aisle: 通道
            shelf: 货架
            bin_no: 货位

        返回:
            拼接后的库位编码 (如 A-01-03-05)
        """
        parts = [p for p in [zone, aisle, shelf, bin_no] if p]
        return "-".join(parts)

    @staticmethod
    def can_store_item(location: Location) -> bool:
        """
        判断库位是否可存放商品: 活跃状态 + 允许存储的库位类型

        参数:
            location: 库位实体

        返回:
            True 表示可存放
        """
        return location.status == "active" and location.location_type in ("storage", "staging", "receiving")


VALID_INSPECTION_RESULTS = {"pending", "passed", "failed", "partial"}
VALID_DEFECT_TYPES = {"none", "damaged", "wrong_item", "quality_issue", "missing"}
VALID_COUNT_TYPES = {"full", "cycle", "spot"}
COUNT_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["in_progress", "cancelled"],
    "in_progress": ["completed", "cancelled"],
    "completed": [],
    "cancelled": [],
}


class QualityInspectionDomainService:
    """
    质检领域服务

    提供质检相关的纯业务规则:
    - 校验: 检查数量合法性 (正数、非负、不超过总量)
    - 结果判定: 全部合格→passed, 全部不合格→failed, 部分→partial
    - 合格率计算: 合格数 / 总数 × 100%
    """

    @staticmethod
    def validate_inspection(quantity_inspected: int, quantity_passed: int, quantity_failed: int) -> list[str]:
        """
        校验质检数量: 正数、非负、合格+不合格≤总量

        参数:
            quantity_inspected: 待检数量 (必须 > 0)
            quantity_passed: 合格数量 (≥ 0)
            quantity_failed: 不合格数量 (≥ 0)

        返回:
            错误列表 (空列表表示校验通过)
        """
        errors: list[str] = []
        if quantity_inspected <= 0:
            errors.append("Inspected quantity must be positive")
        if quantity_passed < 0:
            errors.append("Passed quantity cannot be negative")
        if quantity_failed < 0:
            errors.append("Failed quantity cannot be negative")
        if quantity_passed + quantity_failed > quantity_inspected:
            errors.append("Passed + failed quantity cannot exceed inspected quantity")
        return errors

    @staticmethod
    def determine_result(quantity_inspected: int, quantity_passed: int, quantity_failed: int) -> str:
        """
        判定质检结果: passed / failed / partial / pending

        规则:
        - 总量 ≤ 0 → pending
        - 不合格数 = 0 → passed
        - 合格数 = 0 → failed
        - 其他 → partial

        参数:
            quantity_inspected: 待检数量
            quantity_passed: 合格数量
            quantity_failed: 不合格数量

        返回:
            质检结果字符串
        """
        if quantity_inspected <= 0:
            return "pending"
        if quantity_failed == 0:
            return "passed"
        if quantity_passed == 0:
            return "failed"
        return "partial"

    @staticmethod
    def calculate_pass_rate(quantity_inspected: int, quantity_passed: int) -> float:
        """
        计算合格率: 合格数 / 总数 × 100%，保留2位小数

        参数:
            quantity_inspected: 待检数量
            quantity_passed: 合格数量

        返回:
            合格率百分比 (0.0 ~ 100.0)
        """
        if quantity_inspected <= 0:
            return 0.0
        return round(quantity_passed / quantity_inspected * 100, 2)


class StockCountDomainService:
    """
    盘点领域服务

    提供盘点相关的纯业务规则:
    - 状态机: draft → in_progress → completed / cancelled
    - 差异计算: 盘点量 - 系统量，计算差异百分比，判定 match/surplus/shortage
    - 明细校验: SKU必填、盘点量非负
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        判断盘点单状态是否可转换

        状态机:
        - draft → in_progress, cancelled
        - in_progress → completed, cancelled
        - completed → (终态)
        - cancelled → (终态)

        参数:
            current_status: 当前状态
            target_status: 目标状态

        返回:
            True 表示可转换
        """
        return target_status in COUNT_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def calculate_variance(system_qty: int, counted_qty: int) -> dict:
        """
        计算盘点差异: 盘点量 - 系统量

        参数:
            system_qty: 系统账面数量
            counted_qty: 实际盘点数量

        返回:
            差异详情字典:
            - system_qty: 系统量
            - counted_qty: 盘点量
            - variance: 差异值 (正=盘盈, 负=盘亏)
            - variance_pct: 差异百分比
            - status: match(一致) / surplus(盘盈) / shortage(盘亏)
        """
        variance = counted_qty - system_qty
        variance_pct = round(variance / system_qty * 100, 2) if system_qty > 0 else 0.0
        return {
            "system_qty": system_qty, "counted_qty": counted_qty,
            "variance": variance, "variance_pct": variance_pct,
            "status": "match" if variance == 0 else ("surplus" if variance > 0 else "shortage"),
        }

    @staticmethod
    def validate_count_items(items: list[dict]) -> list[str]:
        """
        校验盘点明细: SKU必填、盘点量非负

        参数:
            items: 盘点明细列表 [{sku_id, counted_qty}, ...]

        返回:
            错误列表 (空列表表示校验通过)
        """
        errors: list[str] = []
        if not items:
            errors.append("Count items cannot be empty")
        for i, item in enumerate(items):
            if not item.get("sku_id"):
                errors.append(f"Item {i}: sku_id is required")
            if item.get("counted_qty", -1) < 0:
                errors.append(f"Item {i}: counted_qty cannot be negative")
        return errors


class TransferDomainService:
    """
    调拨领域服务 (P2-056)

    提供调拨相关的纯业务规则:
    - 调拨状态机: draft → approved → in_transit → received → completed
    - 调拨量校验: 出库库存充足性校验
    - 调拨汇总: 按SKU汇总调拨数量
    - 手工出入库校验: 办公借用/美工拍照/拍卖/销毁/盘盈入库 (P2-061)
    """

    TRANSFER_STATUS_TRANSITIONS: dict[str, list[str]] = {
        "draft": ["approved", "cancelled"],
        "approved": ["in_transit", "cancelled"],
        "in_transit": ["partially_received", "received"],
        "partially_received": ["received", "cancelled"],
        "received": ["completed"],
        "completed": [],
        "cancelled": [],
    }

    # 手工出入库类型白名单
    MANUAL_INOUT_TYPES = {
        "office_borrow": "办公借用",
        "photo_sample": "美工拍照",
        "auction": "拍卖出库",
        "destruction": "销毁出库",
        "count_surplus": "盘盈入库",
        "donation": "捐赠出库",
        "sample": "样品出库",
        "return_to_supplier": "退供出库",
        "adjustment_in": "调整入库",
        "adjustment_out": "调整出库",
    }

    @staticmethod
    def can_transfer(current_status: str, target_status: str) -> bool:
        return target_status in TransferDomainService.TRANSFER_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_transfer_qty(source_available: int, transfer_qty: int) -> list[str]:
        """
        校验调拨量: 出库库存充足性

        参数:
            source_available: 源仓库可用库存
            transfer_qty:     调拨数量

        返回:
            错误列表
        """
        errors = []
        if transfer_qty <= 0:
            errors.append("调拨数量必须大于0")
        if transfer_qty > source_available:
            errors.append(f"源仓库可用库存不足: 需{transfer_qty}, 仅剩{source_available}")
        return errors

    @staticmethod
    def calculate_transfer_summary(items: list[dict]) -> dict:
        """
        计算调拨汇总信息

        参数:
            items: 调拨明细 [{sku_id, qty}, ...]

        返回:
            包含 total_qty, unique_skus 的字典
        """
        total_qty = sum(item.get("qty", 0) for item in items)
        unique_skus = len({item.get("sku_id") for item in items if item.get("sku_id")})
        return {"total_qty": total_qty, "unique_skus": unique_skus}

    @staticmethod
    def is_valid_manual_type(manual_type: str) -> bool:
        """校验手工出入库类型是否合法"""
        return manual_type in TransferDomainService.MANUAL_INOUT_TYPES

    @staticmethod
    def get_manual_type_name(manual_type: str) -> str:
        """获取手工出入库类型的中文名称"""
        return TransferDomainService.MANUAL_INOUT_TYPES.get(manual_type, "未知类型")

    @staticmethod
    def validate_reason(reason: str, is_manual: bool = False) -> list[str]:
        """校验出入库原因说明"""
        errors = []
        if is_manual and not reason:
            errors.append("手工出入库必须填写原因说明")
        return errors


# ---------------------------------------------------------------------------
# 出货质检管理 (P2-058)
# ---------------------------------------------------------------------------
# 拣货后打包前再检，记录发货前不良品
# ---------------------------------------------------------------------------


class OutboundQcService:
    """出货质检领域服务: 拣货后打包前再检"""
    QC_RESULTS = {"pending", "passed", "failed", "partial"}

    @staticmethod
    def validate_qc(inspected: int, passed: int, total_picked: int) -> list[str]:
        errors = []
        if inspected <= 0: errors.append("待检数量必须大于0")
        if passed < 0: errors.append("合格数量不能为负数")
        if inspected > total_picked: errors.append("待检数量不能超过拣货总数")
        if passed > inspected: errors.append("合格数量不能超过待检数量")
        return errors

    @staticmethod
    def determine_result(passed: int, failed: int) -> str:
        if passed > 0 and failed == 0: return "passed"
        if passed == 0 and failed > 0: return "failed"
        if passed > 0 and failed > 0: return "partial"
        return "pending"

    @staticmethod
    def calc_pass_rate(passed: int, total: int) -> float:
        return round(passed / total * 100, 2) if total > 0 else 0


class DefectiveProductService:
    """
    不良品处理领域服务 (P2-057)

    职责:
      - 不良品判定: 根据质检结果判定是否纳入不良品管理
      - 处理方式建议: 根据不良品类型推荐处理方式(退货/返修/报废)
      - 返修流程校验: 校验返修出库→维修→重新质检→入库流程
      - 退货供应商: 按采购回复处理不良品退货
    """

    DEFECTIVE_ACTIONS = {
        "return_to_supplier": "退货供应商",
        "rework": "返修处理",
        "scrap": "报废处理",
        "downgrade": "降级使用",
        "return_to_vendor_credit": "退货退款",
        "exchange_only": "仅换货不退款",
    }

    @staticmethod
    def suggest_action(defect_type: str, severity: str, has_supplier: bool = False) -> str:
        """
        根据不良品类型和建议严重程度推荐处理方式

        规则:
          - 严重损坏/无修复价值 → 报废
          - 轻微外观问题 → 降级使用
          - 功能性问题且有供应商 → 退货供应商
          - 可修复 → 返修处理
        """
        if severity == "critical":
            return "scrap"
        if defect_type == "damaged" and severity == "high":
            return "return_to_supplier" if has_supplier else "scrap"
        if defect_type == "quality_issue" and severity == "low":
            return "downgrade"
        if defect_type in ("wrong_item", "missing"):
            return "return_to_supplier" if has_supplier else "exchange_only"
        return "rework"

    @staticmethod
    def validate_rework_flow(steps: list[dict]) -> list[str]:
        """
        校验返修流程的完整性和合法性

        标准返修流程: 返修出库 → 维修 → 重新质检 → 良品入库
        """
        required_steps = ["rework_out", "repair", "re_inspect", "rework_in"]
        errors = []
        step_types = [s.get("step_type") for s in steps]
        for required in required_steps:
            if required not in step_types:
                names = {
                    "rework_out": "返修出库", "repair": "维修处理",
                    "re_inspect": "重新质检", "rework_in": "良品入库",
                }
                errors.append(f"缺少必要步骤: {names.get(required, required)}")
        return errors

    @staticmethod
    def validate_return_to_supplier(
        defective_qty: int,
        supplier_agreed: bool,
        has_replacement: bool = False,
    ) -> list[str]:
        """
        校验退货供应商的合法性

        参数:
            defective_qty:   不良品数量
            supplier_agreed: 供应商是否同意退货
            has_replacement: 是否有换货
        """
        errors = []
        if defective_qty <= 0:
            errors.append("退货数量必须大于0")
        if not supplier_agreed:
            errors.append("供应商未确认退货，请先联系供应商")
        return errors


class LocationStatsService:
    """库位分组统计 (P2-060): 按类型/区域统计占用率"""
    @staticmethod
    def by_type(locations: list[dict]) -> dict:
        stats = {}
        for loc in locations:
            t = loc.get("type", "unknown")
            if t not in stats: stats[t] = {"count": 0, "used": 0}
            stats[t]["count"] += 1
            if loc.get("is_occupied"): stats[t]["used"] += 1
        for t, s in stats.items():
            s["usage_rate"] = round(s["used"] / max(s["count"], 1) * 100, 2)
        return stats

    @staticmethod
    def by_zone(locations: list[dict]) -> dict:
        stats = {}
        for loc in locations:
            z = loc.get("zone", "unknown")
            if z not in stats: stats[z] = {"total": 0, "occupied": 0}
            stats[z]["total"] += 1
            if loc.get("is_occupied"): stats[z]["occupied"] += 1
            stats[z]["rate"] = round(stats[z]["occupied"] / max(stats[z]["total"], 1) * 100, 2)
        return stats


class PackingSopService:
    """发货打包SOP (P3-014): 按SKU特殊包装要求"""
    @staticmethod
    def get_requirements(sku: dict) -> dict:
        return {"sku": sku.get("code"), "fragile": sku.get("is_fragile", False),
                "bubble_wrap": sku.get("is_fragile", False) or sku.get("has_electronics", False),
                "custom_box": sku.get("oversized", False), "max_per_box": sku.get("max_per_box", 50)}
    @staticmethod
    def estimate_time(items: list[dict]) -> dict:
        base = sum(30 for i in items)
        extra = sum(60 for i in items if i.get("is_fragile"))
        return {"items": len(items), "seconds": base + extra, "minutes": round((base + extra) / 60, 1)}
