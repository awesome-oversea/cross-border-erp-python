"""
TMS 领域服务

包含发货单状态机、物流商校验、配送方式运费计算、运费估算、物流追踪等核心领域逻辑。
所有方法均为纯函数 / 静态方法，不依赖基础设施层。
"""
from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erp.modules.tms.domain.models import LogisticsProvider, Shipment

SHIPMENT_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["picked_up", "cancelled"],
    "picked_up": ["in_transit", "cancelled"],
    "in_transit": ["out_for_delivery", "cancelled"],
    "out_for_delivery": ["delivered", "failed_delivery"],
    "delivered": [],
    "failed_delivery": ["out_for_delivery", "returned"],
    "returned": [],
    "cancelled": [],
}
"""发货单状态机: 定义各状态之间的合法流转路径"""

MAX_SHIPPING_COST_PER_KG = 500.0
"""每公斤运费上限 (CNY)"""

MAX_WEIGHT_LIMIT = 1000.0
"""单票重量上限 (kg)"""


class ShipmentDomainService:
    """发货单领域服务 — 封装发货单状态流转与运费校验逻辑"""

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """判断发货单是否可以从 current_status 流转到 target_status"""
        return target_status in SHIPMENT_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_shipping_cost(weight: float, shipping_cost: float) -> list[str]:
        """
        校验运费合法性

        规则:
        1. 重量必须为正数
        2. 重量不超过 MAX_WEIGHT_LIMIT
        3. 运费不能为负
        4. 每公斤运费不超过 MAX_SHIPPING_COST_PER_KG
        """
        errors: list[str] = []
        if weight <= 0:
            errors.append("Weight must be positive")
        if weight > MAX_WEIGHT_LIMIT:
            errors.append(f"Weight exceeds maximum limit of {MAX_WEIGHT_LIMIT} kg")
        if shipping_cost < 0:
            errors.append("Shipping cost cannot be negative")
        if weight > 0 and shipping_cost / weight > MAX_SHIPPING_COST_PER_KG:
            errors.append(f"Shipping cost per kg exceeds maximum of {MAX_SHIPPING_COST_PER_KG}")
        return errors

    @staticmethod
    def calculate_cost_per_kg(weight: float, shipping_cost: float) -> float:
        """计算每公斤运费 (weight <= 0 时返回 0.0)"""
        if weight <= 0:
            return 0.0
        return round(shipping_cost / weight, 2)

    @staticmethod
    def is_overdue(shipment: Shipment) -> bool:
        """
        判断发货单是否已超期

        已完结状态 (delivered/returned/cancelled) 不会超期;
        仅当 estimated_delivery_date 早于当前时间时判定为超期。
        """
        from datetime import datetime
        if shipment.status in ("delivered", "returned", "cancelled"):
            return False
        eta = getattr(shipment, "estimated_delivery_date", None)
        if not eta:
            return False
        now = datetime.now(UTC)
        if hasattr(eta, "tzinfo") and eta.tzinfo is None:
            eta = eta.replace(tzinfo=UTC)
        return now > eta


class LogisticsProviderDomainService:
    """物流商领域服务 — 封装物流商状态校验与可用性判断"""

    @staticmethod
    def validate_provider_status(provider: LogisticsProvider) -> list[str]:
        """校验物流商状态 (inactive 状态不可用)"""
        errors: list[str] = []
        if provider.status == "inactive":
            errors.append("Provider is inactive")
        return errors

    @staticmethod
    def can_create_shipment(provider: LogisticsProvider) -> bool:
        """判断物流商是否可用于创建发货单 (仅 active 状态可用)"""
        return provider.status == "active"


VALID_SHIPPING_TYPES = {"standard", "express", "economy", "priority", "same_day", "next_day"}
"""合法的配送方式类型集合"""

VALID_CALCULATION_TYPES = {"by_weight", "by_volume", "by_item", "by_fixed"}
"""合法的运费计算方式集合"""


class ShippingMethodDomainService:
    """配送方式领域服务 — 封装运费计算与校验逻辑"""

    @staticmethod
    def validate_shipping_method(name: str, shipping_type: str, first_weight: float,
                                  first_weight_price: float, additional_weight: float,
                                  additional_weight_price: float) -> list[str]:
        """
        校验配送方式参数合法性

        规则:
        1. 名称不能为空
        2. shipping_type 必须在 VALID_SHIPPING_TYPES 内
        3. 首重 / 续重单位必须为正数
        4. 首重价格 / 续重价格不能为负
        """
        errors: list[str] = []
        if not name or not name.strip():
            errors.append("Shipping method name cannot be empty")
        if shipping_type not in VALID_SHIPPING_TYPES:
            errors.append(f"Invalid shipping type '{shipping_type}'")
        if first_weight <= 0:
            errors.append("First weight must be positive")
        if first_weight_price < 0:
            errors.append("First weight price cannot be negative")
        if additional_weight <= 0:
            errors.append("Additional weight unit must be positive")
        if additional_weight_price < 0:
            errors.append("Additional weight price cannot be negative")
        return errors

    @staticmethod
    def calculate_freight_by_weight(weight: float, first_weight: float, first_weight_price: float,
                                     additional_weight: float, additional_weight_price: float,
                                     min_price: float = 0.0) -> float:
        """
        按重量计算运费

        逻辑: 首重内按首重价格; 超出部分按续重单位向上取整后乘以续重价格。
        最终取 max(计算值, min_price)。
        """
        if weight <= 0:
            return 0.0
        if weight <= first_weight:
            cost = first_weight_price
        else:
            extra = weight - first_weight
            additional_units = -(-int(extra * 100) // int(additional_weight * 100))
            cost = first_weight_price + additional_units * additional_weight_price
        return round(max(cost, min_price), 2)

    @staticmethod
    def calculate_freight_by_volume(volume: float, price_per_unit: float, min_price: float = 0.0) -> float:
        """按体积计算运费: volume × price_per_unit, 不低于 min_price"""
        if volume <= 0:
            return 0.0
        return round(max(volume * price_per_unit, min_price), 2)

    @staticmethod
    def calculate_freight_by_item(quantity: int, price_per_item: float, min_price: float = 0.0) -> float:
        """按件数计算运费: quantity × price_per_item, 不低于 min_price"""
        if quantity <= 0:
            return 0.0
        return round(max(quantity * price_per_item, min_price), 2)

    @staticmethod
    def calculate_estimated_delivery_days(estimated_days_min: int, estimated_days_max: int) -> str:
        """格式化预计送达天数"""
        if estimated_days_min == estimated_days_max:
            return f"{estimated_days_min} days"
        return f"{estimated_days_min}-{estimated_days_max} days"


class FreightEstimationDomainService:
    """运费估算领域服务 — 根据多种计算方式估算运费并支持对比"""

    @staticmethod
    def estimate_freight(weight: float, volume: float, quantity: int,
                          shipping_method: dict, destination_country: str = "") -> dict:
        """
        根据配送方式的计算类型估算运费

        支持 by_weight / by_volume / by_item / by_fixed 四种模式。
        返回包含估算费用、币种、预计时效的字典。
        """
        calc_type = shipping_method.get("calculation_type", "by_weight")
        if calc_type == "by_weight":
            cost = ShippingMethodDomainService.calculate_freight_by_weight(
                weight,
                shipping_method.get("first_weight", 0.1),
                shipping_method.get("first_weight_price", 0.0),
                shipping_method.get("additional_weight", 0.1),
                shipping_method.get("additional_weight_price", 0.0),
                shipping_method.get("min_price", 0.0),
            )
        elif calc_type == "by_volume":
            cost = ShippingMethodDomainService.calculate_freight_by_volume(
                volume, shipping_method.get("price_per_unit", 0.0), shipping_method.get("min_price", 0.0)
            )
        elif calc_type == "by_item":
            cost = ShippingMethodDomainService.calculate_freight_by_item(
                quantity, shipping_method.get("price_per_item", 0.0), shipping_method.get("min_price", 0.0)
            )
        else:
            cost = shipping_method.get("fixed_price", 0.0)
        estimated_days = ShippingMethodDomainService.calculate_estimated_delivery_days(
            shipping_method.get("estimated_days_min", 0), shipping_method.get("estimated_days_max", 0)
        )
        return {
            "shipping_method_id": shipping_method.get("id", ""),
            "shipping_method_name": shipping_method.get("name", ""),
            "estimated_cost": cost,
            "currency": shipping_method.get("currency", "CNY"),
            "estimated_days": estimated_days,
            "calculation_type": calc_type,
        }

    @staticmethod
    def compare_shipping_methods(weight: float, volume: float, quantity: int,
                                  methods: list[dict], destination_country: str = "") -> list[dict]:
        """
        对比多种配送方式的运费估算

        返回按估算费用升序排列的结果列表。
        """
        estimates = []
        for m in methods:
            est = FreightEstimationDomainService.estimate_freight(weight, volume, quantity, m, destination_country)
            estimates.append(est)
        return sorted(estimates, key=lambda x: x["estimated_cost"])


class TrackingDomainService:
    """物流追踪领域服务 — 封装轨迹解析、状态提取与异常检测"""

    @staticmethod
    def parse_tracking_events(raw_events: list[dict]) -> list[dict]:
        """
        解析原始物流轨迹事件

        标准化字段: timestamp / location / status / description,
        按时间倒序排列。
        """
        parsed = []
        for event in raw_events:
            parsed.append({
                "timestamp": event.get("timestamp", ""),
                "location": event.get("location", ""),
                "status": event.get("status", ""),
                "description": event.get("description", ""),
            })
        return sorted(parsed, key=lambda x: x["timestamp"], reverse=True)

    @staticmethod
    def get_latest_status(tracking_events: list[dict]) -> dict:
        """获取最新一条轨迹事件的状态信息"""
        if not tracking_events:
            return {"status": "unknown", "description": "No tracking events", "timestamp": ""}
        sorted_events = sorted(tracking_events, key=lambda x: x.get("timestamp", ""), reverse=True)
        latest = sorted_events[0]
        return {
            "status": latest.get("status", "unknown"),
            "description": latest.get("description", ""),
            "timestamp": latest.get("timestamp", ""),
            "location": latest.get("location", ""),
        }

    @staticmethod
    def is_delivered(tracking_events: list[dict]) -> bool:
        """判断物流是否已签收 (delivered / signed / completed)"""
        latest = TrackingDomainService.get_latest_status(tracking_events)
        return latest["status"] in ("delivered", "signed", "completed")

    @staticmethod
    def detect_exception(tracking_events: list[dict]) -> dict | None:
        """
        检测物流异常

        从最新事件开始扫描，匹配异常关键词:
        exception / failed / returned / customs_hold / damaged / lost
        返回异常详情字典或 None。
        """
        if not tracking_events:
            return None
        exception_keywords = ["exception", "failed", "returned", "customs_hold", "damaged", "lost"]
        for event in sorted(tracking_events, key=lambda x: x.get("timestamp", ""), reverse=True):
            status = event.get("status", "").lower()
            desc = event.get("description", "").lower()
            for kw in exception_keywords:
                if kw in status or kw in desc:
                    return {
                        "exception_type": kw,
                        "description": event.get("description", ""),
                        "timestamp": event.get("timestamp", ""),
                    }
        return None


# ---------------------------------------------------------------------------
# 发货后修改运费 (P2-064)
# ---------------------------------------------------------------------------
# 场景: 物流商结算价与估算价存在差异时，录入实际运费精准核算成本
# 规则: 实际运费不可低于估算运费的50%，不可高于300%
# ---------------------------------------------------------------------------


class FreightAdjustmentService:
    """
    发货后运费调整领域服务

    职责:
      - 运费差异校验: 实际运费与估算运费的偏差在合理范围内
      - 成本影响计算: 运费变更对订单利润的影响
      - 调整审批判定: 大额运费变更需审批
    """

    MIN_RATIO = 0.5
    MAX_RATIO = 3.0
    APPROVAL_THRESHOLD = 100.0

    @staticmethod
    def validate_adjustment(estimated_cost: float, actual_cost: float) -> list[str]:
        errors = []
        if actual_cost < 0:
            errors.append("实际运费不能为负数")
        if estimated_cost > 0:
            ratio = actual_cost / estimated_cost
            if ratio < FreightAdjustmentService.MIN_RATIO:
                errors.append(f"实际运费({actual_cost})低于估算价({estimated_cost})的50%")
            if ratio > FreightAdjustmentService.MAX_RATIO:
                errors.append(f"实际运费({actual_cost})超过估算价({estimated_cost})的300%")
        return errors

    @staticmethod
    def calculate_cost_impact(estimated_cost: float, actual_cost: float) -> dict:
        diff = actual_cost - estimated_cost
        return {
            "estimated_cost": round(estimated_cost, 2),
            "actual_cost": round(actual_cost, 2),
            "difference": round(diff, 2),
            "increase_pct": round(diff / estimated_cost * 100, 2) if estimated_cost > 0 else 0,
            "currency": "CNY",
        }

    @staticmethod
    def requires_approval(actual_cost: float, diff: float) -> bool:
        return actual_cost > FreightAdjustmentService.APPROVAL_THRESHOLD and diff > 0
