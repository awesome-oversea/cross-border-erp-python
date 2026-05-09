"""
FBA 领域服务 - FBA 货件管理域的纯业务规则

本模块定义了货件、库存、费用、箱标签、补货计划、入库计划六个核心领域服务，
所有方法均为无状态纯函数，不依赖数据库或外部 IO，
仅对输入进行校验和计算，确保业务规则的可测试性。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erp.modules.fba.domain.models import FbaBoxLabel, FbaInboundPlan, FbaInventory, FbaReplenishmentPlan, FbaShipment

# ──── 状态机定义 ────

SHIPMENT_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["submitted", "cancelled"],
    "submitted": ["in_production", "cancelled"],
    "in_production": ["shipped", "cancelled"],
    "shipped": ["in_transit", "cancelled"],
    "in_transit": ["received", "partially_received", "cancelled"],
    "partially_received": ["received"],
    "received": ["closed"],
    "closed": [],
    "cancelled": [],
}
"""货件状态转移矩阵 - 定义货件生命周期中合法的状态流转"""

FBA_FEE_TYPES = {
    "fulfillment_fee", "storage_fee", "long_term_storage_fee",
    "removal_fee", "return_fee", "prep_fee", "label_fee",
}
"""合法的 FBA 费用类型集合"""

BOX_LABEL_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "created": ["printed", "voided"],
    "printed": ["attached", "voided"],
    "attached": [],
    "voided": [],
}
"""箱标签状态转移矩阵"""

REPLENISHMENT_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["approved", "rejected", "cancelled"],
    "approved": ["in_progress", "cancelled"],
    "in_progress": ["completed", "cancelled"],
    "completed": [],
    "rejected": [],
    "cancelled": [],
}
"""补货计划状态转移矩阵"""

INBOUND_PLAN_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["submitted", "cancelled"],
    "submitted": ["confirmed", "cancelled"],
    "confirmed": ["in_progress", "cancelled"],
    "in_progress": ["shipped", "cancelled"],
    "shipped": ["completed", "cancelled"],
    "completed": [],
    "cancelled": [],
}
"""入库计划状态转移矩阵"""

VALID_REPLENISHMENT_PRIORITIES = {"urgent", "high", "normal", "low"}
"""合法的补货优先级集合"""


class FbaShipmentDomainService:
    """
    货件领域服务 - 货件状态流转与校验

    职责:
    1. 判断货件状态转移是否合法
    2. 校验货件提交前的必填字段
    3. 计算货件接收百分比
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """判断货件是否可以从 current_status 转移到 target_status"""
        return target_status in SHIPMENT_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_for_submit(shipment: FbaShipment) -> list[str]:
        """
        校验货件提交前的必填字段

        必须满足:
        - FBA 货件 ID 不为空
        - 目标 FBA 中心 ID 不为空
        - 总件数大于 0
        """
        errors: list[str] = []
        if not getattr(shipment, "fba_shipment_id", None):
            errors.append("FBA shipment ID is required")
        if not getattr(shipment, "destination_fulfillment_center_id", None):
            errors.append("Destination fulfillment center ID is required")
        if getattr(shipment, "total_units", 0) <= 0:
            errors.append("Total units must be positive")
        return errors

    @staticmethod
    def calculate_received_percentage(shipment: FbaShipment) -> float:
        """计算货件已接收百分比，总件数为 0 时返回 0.0"""
        total = getattr(shipment, "total_units", 0) or 0
        received = getattr(shipment, "received_units", 0) or 0
        if total <= 0:
            return 0.0
        return round(received / total * 100, 2)


class FbaInventoryDomainService:
    """
    FBA 库存领域服务 - 库存预警与补货计算

    职责:
    1. 判断库存是否低于安全阈值
    2. 计算库存可供应天数
    3. 计算建议补货数量
    4. 根据可供应天数划分紧急程度
    """

    @staticmethod
    def is_low_stock(inventory: FbaInventory, threshold: int = 10) -> bool:
        """判断库存是否低于安全阈值（默认 10 件）"""
        fulfillable = getattr(inventory, "qty_fulfillable", 0) or 0
        return fulfillable <= threshold

    @staticmethod
    def calculate_days_of_supply(qty_fulfillable: int, avg_daily_sales: float) -> float:
        """
        计算库存可供应天数

        公式: qty_fulfillable / avg_daily_sales
        特殊处理: 日均销量为 0 时，有库存返回 inf，无库存返回 0.0
        """
        if avg_daily_sales <= 0:
            return float("inf") if qty_fulfillable > 0 else 0.0
        return round(qty_fulfillable / avg_daily_sales, 1)

    @staticmethod
    def calculate_restock_qty(qty_fulfillable: int, qty_inbound: int, safety_stock: int,
                              lead_time_days: int, avg_daily_sales: float) -> int:
        """
        计算建议补货数量

        公式: (safety_stock + demand_during_lead) - (qty_fulfillable + qty_inbound)
        结果为负数时返回 0（无需补货）
        """
        if avg_daily_sales <= 0:
            return 0
        demand_during_lead = avg_daily_sales * lead_time_days
        total_available = qty_fulfillable + qty_inbound
        shortage = (safety_stock + demand_during_lead) - total_available
        return max(0, int(shortage))

    @staticmethod
    def classify_urgency(days_of_supply: float, lead_time_days: int) -> str:
        """
        根据可供应天数划分紧急程度

        - ≤ 交期天数 → urgent
        - ≤ 2×交期天数 → high
        - ≤ 3×交期天数 → normal
        - > 3×交期天数 → low
        """
        if days_of_supply <= lead_time_days:
            return "urgent"
        if days_of_supply <= lead_time_days * 2:
            return "high"
        if days_of_supply <= lead_time_days * 3:
            return "normal"
        return "low"


class FbaFeeDomainService:
    """
    FBA 费用领域服务 - 费用类型校验与单价计算

    职责:
    1. 校验费用类型是否合法
    2. 根据总费用和数量计算单价
    """

    @staticmethod
    def validate_fee_type(fee_type: str) -> bool:
        """判断费用类型是否在 FBA_FEE_TYPES 中"""
        return fee_type in FBA_FEE_TYPES

    @staticmethod
    def calculate_per_unit_fee(total_fee: float, quantity: int) -> float:
        """计算单价，数量为 0 时返回 0.0"""
        if quantity <= 0:
            return 0.0
        return round(total_fee / quantity, 4)


class FbaBoxLabelDomainService:
    """
    箱标签领域服务 - 标签状态流转与校验

    职责:
    1. 判断标签状态转移是否合法
    2. 校验箱标签创建参数
    3. 计算一组标签的总重量
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """判断箱标签是否可以从 current_status 转移到 target_status"""
        return target_status in BOX_LABEL_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_box_label(shipment_id: str, box_no: int, sku_id: str, quantity: int) -> list[str]:
        """
        校验箱标签创建参数

        必须满足:
        - shipment_id 不为空
        - box_no ≥ 1
        - sku_id 不为空
        - quantity ≥ 1
        """
        errors: list[str] = []
        if not shipment_id:
            errors.append("Shipment ID is required")
        if box_no < 1:
            errors.append("Box number must be at least 1")
        if not sku_id:
            errors.append("SKU ID is required")
        if quantity < 1:
            errors.append("Quantity must be at least 1")
        return errors

    @staticmethod
    def calculate_total_weight(box_labels: list[FbaBoxLabel]) -> float:
        """计算一组箱标签的总重量"""
        return round(sum(getattr(bl, "weight", 0) or 0 for bl in box_labels), 2)


class FbaReplenishmentDomainService:
    """
    补货计划领域服务 - 补货校验、建议数量计算与优先级划分

    职责:
    1. 判断补货计划状态转移是否合法
    2. 校验补货计划创建参数
    3. 根据库存、日均销量、交期等计算建议补货数量
    4. 自动划分补货优先级
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """判断补货计划是否可以从 current_status 转移到 target_status"""
        return target_status in REPLENISHMENT_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_replenishment(
        sku_id: str, store_id: str, suggested_qty: int, avg_daily_sales: float,
        days_of_supply: int, priority: str,
    ) -> list[str]:
        """
        校验补货计划创建参数

        必须满足:
        - sku_id 和 store_id 不为空
        - suggested_qty ≥ 0
        - avg_daily_sales ≥ 0
        - days_of_supply ≥ 1
        - priority 在合法集合中
        """
        errors: list[str] = []
        if not sku_id:
            errors.append("SKU ID is required")
        if not store_id:
            errors.append("Store ID is required")
        if suggested_qty < 0:
            errors.append("Suggested quantity cannot be negative")
        if avg_daily_sales < 0:
            errors.append("Average daily sales cannot be negative")
        if days_of_supply < 1:
            errors.append("Days of supply must be at least 1")
        if priority not in VALID_REPLENISHMENT_PRIORITIES:
            errors.append(f"Invalid priority: {priority}")
        return errors

    @staticmethod
    def calculate_suggested_qty(
        current_qty: int, qty_inbound: int, avg_daily_sales: float,
        days_of_supply: int, safety_stock_days: int, lead_time_days: int,
    ) -> int:
        """
        计算建议补货数量

        公式:
        - target_stock = avg_daily_sales × (days_of_supply + safety_stock_days)
        - reorder_point = avg_daily_sales × lead_time_days + avg_daily_sales × safety_stock_days
        - 当 total_available < reorder_point 时: shortage = target_stock - total_available
        - 否则无需补货，返回 0
        """
        if avg_daily_sales <= 0:
            return 0
        target_stock = avg_daily_sales * (days_of_supply + safety_stock_days)
        demand_during_lead = avg_daily_sales * lead_time_days
        reorder_point = demand_during_lead + (avg_daily_sales * safety_stock_days)
        total_available = current_qty + qty_inbound
        if total_available >= reorder_point:
            return 0
        shortage = target_stock - total_available
        return max(0, int(shortage))

    @staticmethod
    def auto_prioritize(
        current_qty: int, avg_daily_sales: float, lead_time_days: int,
    ) -> str:
        """
        根据当前库存和日均销量自动划分优先级

        - 可供应天数 ≤ 交期天数 → urgent
        - 可供应天数 ≤ 2×交期天数 → high
        - 可供应天数 ≤ 3×交期天数 → normal
        - 其余 → low
        """
        if avg_daily_sales <= 0:
            return "low"
        days_left = current_qty / avg_daily_sales if avg_daily_sales > 0 else float("inf")
        if days_left <= lead_time_days:
            return "urgent"
        if days_left <= lead_time_days * 2:
            return "high"
        if days_left <= lead_time_days * 3:
            return "normal"
        return "low"


class FbaInboundPlanDomainService:
    """
    入库计划领域服务 - 入库计划状态流转与校验

    职责:
    1. 判断入库计划状态转移是否合法
    2. 校验入库计划提交前的必填字段
    3. 计算入库计划汇总信息
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """判断入库计划是否可以从 current_status 转移到 target_status"""
        return target_status in INBOUND_PLAN_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_for_submit(plan: FbaInboundPlan) -> list[str]:
        """
        校验入库计划提交前的必填字段

        必须满足:
        - 计划名称不为空
        - 目标 FBA 中心不为空
        - 总件数大于 0
        """
        errors: list[str] = []
        if not getattr(plan, "name", None):
            errors.append("Plan name is required")
        if not getattr(plan, "destination_fba_center", None):
            errors.append("Destination FBA center is required")
        if getattr(plan, "total_units", 0) <= 0:
            errors.append("Total units must be positive")
        return errors

    @staticmethod
    def get_plan_summary(items: list[dict]) -> dict:
        """
        计算入库计划汇总信息

        Returns:
            包含 total_units, total_weight, unique_skus, item_count 的字典
        """
        total_units = sum(item.get("quantity", 0) for item in items)
        total_weight = sum(item.get("weight", 0) * item.get("quantity", 1) for item in items)
        unique_skus = len({item.get("sku_id", "") for item in items if item.get("sku_id")})
        return {
            "total_units": total_units,
            "total_weight": round(total_weight, 2),
            "unique_skus": unique_skus,
            "item_count": len(items),
        }


# ---------------------------------------------------------------------------
# FBA备货计划三种创建模式 (P3-012)
# ---------------------------------------------------------------------------
# 模式1: sync_from_amazon — 同步Amazon后台已有货件计划
# 模式2: load_shipment_id — 输入Amazon ShipmentID加载货件信息
# 模式3: create_without_id  — 先在ERP创建计划，后续关联Amazon ShipmentID
# ---------------------------------------------------------------------------
FBA_PLAN_CREATION_MODES = {
    "sync_from_amazon": {
        "name": "同步Amazon后台",
        "requires_auth": True,
        "requires_shipment_id": False,
        "auto_create_shipment": True,
    },
    "load_shipment_id": {
        "name": "加载ShipmentID",
        "requires_auth": True,
        "requires_shipment_id": True,
        "auto_create_shipment": False,
    },
    "create_without_id": {
        "name": "先创建无ID计划",
        "requires_auth": False,
        "requires_shipment_id": False,
        "auto_create_shipment": False,
    },
}


class FbaPlanCreationService:
    """
    FBA备货计划创建模式领域服务

    职责:
      - 校验创建模式是否合法
      - 根据创建模式校验前置条件
      - 生成对应的创建流程步骤
      - 生成计划编号
    """

    VALID_MODES = set(FBA_PLAN_CREATION_MODES.keys())

    @staticmethod
    def is_valid_mode(mode: str) -> bool:
        return mode in FBA_PLAN_CREATION_MODES

    @staticmethod
    def validate_mode_prerequisites(mode: str, has_auth: bool = False, shipment_id: str = "") -> list[str]:
        """
        校验创建模式的前置条件

        参数:
            mode:        创建模式
            has_auth:    是否有Amazon API授权
            shipment_id: Amazon ShipmentID(仅load_shipment_id模式需要)

        返回:
            校验错误列表
        """
        errors = []
        config = FBA_PLAN_CREATION_MODES.get(mode)
        if not config:
            errors.append(f"不支持的创建模式: {mode}")
            return errors

        if config["requires_auth"] and not has_auth:
            errors.append(f"模式'{config['name']}'需要Amazon API授权")
        if config["requires_shipment_id"] and not shipment_id:
            errors.append(f"模式'{config['name']}'需要输入Amazon ShipmentID")
        return errors

    @staticmethod
    def get_creation_steps(mode: str) -> list[str]:
        """根据创建模式生成创建流程步骤"""
        base_steps = ["填写备货计划信息"]
        if mode == "sync_from_amazon":
            base_steps.extend([
                "选择要同步的Amazon店铺",
                "从Amazon后台获取货件计划列表",
                "选择需要导入的货件计划",
                "确认并生成ERP备货计划单",
            ])
        elif mode == "load_shipment_id":
            base_steps.extend([
                "输入Amazon ShipmentID",
                "从Amazon加载货件信息",
                "确认并生成ERP备货计划单",
            ])
        elif mode == "create_without_id":
            base_steps.extend([
                "填写备货SKU/数量/目标FBA中心",
                "生成ERP备货计划单(无Amazon ShipmentID)",
                "发货后通过Amazon后台补填ShipmentID",
            ])
        return base_steps

    @staticmethod
    def generate_plan_no(mode: str, tenant_id: str, sequence: int = 1) -> str:
        """
        根据创建模式生成计划编号

        编号规则:
          - sync_from_amazon: FBA-SA-{tenant_short}-{seq}
          - load_shipment_id: FBA-LS-{tenant_short}-{seq}
          - create_without_id: FBA-CW-{tenant_short}-{seq}
        """
        from datetime import datetime
        prefix_map = {
            "sync_from_amazon": "FBA-SA",
            "load_shipment_id": "FBA-LS",
            "create_without_id": "FBA-CW",
        }
        prefix = prefix_map.get(mode, "FBA")
        tenant_short = tenant_id[:6] if len(tenant_id) >= 6 else tenant_id
        return f"{prefix}-{tenant_short}-{datetime.now().strftime('%Y%m%d')}-{sequence:04d}"


# ---------------------------------------------------------------------------
# FBA头程五大异常处理 (P3-015)
# ---------------------------------------------------------------------------
class FbaHeadTripExceptionService:
    """FBA头程五大异常处理: damaged/lost/returned/removed/shared_inventory"""
    EXCEPTION_TYPES = {"damaged", "lost", "returned", "removed", "shared_inventory"}

    @staticmethod
    def is_valid_exception_type(exc_type: str) -> bool:
        return exc_type in FbaHeadTripExceptionService.EXCEPTION_TYPES

    @staticmethod
    def suggest_workflow(exc_type: str, quantity: int, unit_cost: float = 0) -> dict:
        workflows = {
            "damaged": ["拍照存档", "申请赔偿", "报废或折价处理"],
            "lost": ["查询物流轨迹", "提交索赔申请", "补发货或退款"],
            "returned": ["检查产品状态", "重新入库或报废"],
            "removed": ["选择处理方式(退回/销毁/清货)", "安排移除订单"],
            "shared_inventory": ["确认共享库存数量", "调整库存归属", "跨账号结算"],
        }
        return {
            "exception_type": exc_type,
            "suggested_workflow": workflows.get(exc_type, []),
            "estimated_loss": round(quantity * unit_cost, 2), "currency": "CNY",
        }


class FbaInventoryAgeService:
    """FBA库存库龄分析: 计算库龄、分类预警、长期仓储费预估"""
    @staticmethod
    def calculate_age_in_days(inbound_date) -> int:
        if not inbound_date:
            return 0
        from datetime import UTC, datetime
        if hasattr(inbound_date, "tzinfo") and inbound_date.tzinfo is None:
            inbound_date = inbound_date.replace(tzinfo=UTC)
        return max(0, (datetime.now(UTC) - inbound_date).days)

    @staticmethod
    def classify_age(age_days: int) -> dict:
        if age_days <= 30:
            return {"level": "normal", "label": "正常库存", "suggestion": ""}
        elif age_days <= 90:
            return {"level": "attention", "label": "短期库存", "suggestion": "关注动销"}
        elif age_days <= 180:
            return {"level": "warning", "label": "预警库存", "suggestion": "建议降价促销或移除"}
        elif age_days <= 365:
            return {"level": "critical", "label": "警告库存", "suggestion": "长期仓储费即将征收"}
        else:
            return {"level": "severe", "label": "严重库存", "suggestion": "立即处理，已产生长期仓储费"}


class FbaShipmentAnalysisService:
    """FBA货件分析 (P6-015): 货件时效/费用/物流商对比"""
    @staticmethod
    def analyze(shipment: dict) -> dict:
        c, s, r, cl = shipment.get("created_at"), shipment.get("shipped_at"), shipment.get("received_at"), shipment.get("closed_at")
        def days(a, b):
            if not a or not b: return None
            from datetime import UTC, datetime
            d1 = datetime.fromisoformat(a.replace("Z","+00:00")) if isinstance(a, str) else a
            d2 = datetime.fromisoformat(b.replace("Z","+00:00")) if isinstance(b, str) else b
            return max(0, (d2 - d1).days)
        return {"id": shipment.get("id"), "units": shipment.get("total_units", 0),
                "received": shipment.get("received_units", 0),
                "receive_rate": round(shipment.get("received_units", 0)/max(shipment.get("total_units", 0),1)*100, 2),
                "to_fulfill_days": days(c, s), "transit_days": days(s, r),
                "to_close_days": days(r, cl), "total_days": days(c, cl)}

    @staticmethod
    def compare_providers(shipments: list[dict]) -> list[dict]:
        by_p = {}
        for s in shipments:
            p = s.get("carrier", "unknown")
            if p not in by_p: by_p[p] = []
            by_p[p].append(s)
        return [{"carrier": p, "count": len(v),
                 "avg_days": round(sum(s.get("transit_days", 0) for s in v)/max(len(v),1), 1),
                 "avg_cost": round(sum(s.get("cost", 0) for s in v)/max(len(v),1), 2)}
                for p, v in by_p.items()]


class FbaRemovalOrderService:
    @staticmethod
    def validate(order: dict) -> list[str]:
        e = []
        if not order.get("sku"): e.append("SKU不能为空")
        if order.get("qty", 0) <= 0: e.append("数量必须大于0")
        return e
    @staticmethod
    def calc_fees(qty: int, rtype: str) -> dict:
        unit = {"return": 0.5, "destroy": 0.15, "liquidate": 0.0}.get(rtype, 0.5)
        return {"unit": unit, "total": round(qty * unit, 2)}
    @staticmethod
    def suggest_action(age: int, stock: int, sales: float) -> str:
        if age > 365 and stock > 0: return "liquidate"
        if age > 180 and sales < 1: return "destroy"
        if age > 90 and sales == 0: return "return"
        return "keep"
