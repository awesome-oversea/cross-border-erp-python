"""
OMS 领域服务模块

本模块定义了订单管理系统中三个核心聚合的领域服务:
  - OrderDomainService:     销售订单领域服务 — 状态机、风控校验、金额计算
  - RefundDomainService:    退款单领域服务 — 状态机、退款金额校验、自动审批判定
  - PromotionDomainService: 促销活动领域服务 — 状态机、促销规则校验、折扣计算、适用性判定

设计原则:
  1. 领域服务无状态，所有方法均为 @staticmethod，不持有可变数据
  2. 状态机使用 "当前状态 → 允许转移列表" 的字典结构，便于扩展
  3. 业务规则集中在此层，应用服务 (application/services.py) 仅做编排
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erp.modules.oms.domain.models import Promotion, RefundOrder, SalesOrder, SalesOrderItem

# ---------------------------------------------------------------------------
# 销售订单状态机
# ---------------------------------------------------------------------------
# 状态流转图:
#   pending → confirmed → processing → shipped → delivered → completed
#        ↓        ↓           ↓          ↓          ↓
#    cancelled  cancelled  cancelled  returned  returned
#                                                        ↓
#                                                    refunded
# ---------------------------------------------------------------------------
ORDER_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["confirmed", "cancelled"],
    "confirmed": ["processing", "cancelled"],
    "processing": ["shipped", "cancelled"],
    "shipped": ["delivered", "returned"],
    "delivered": ["completed", "returned"],
    "returned": ["refunded"],
    "refunded": [],
    "completed": [],
    "cancelled": [],
}

# ---------------------------------------------------------------------------
# 退款单状态机
# ---------------------------------------------------------------------------
# 状态流转图:
#   pending → approved → processing → completed
#        ↓        ↓           ↓
#    rejected  cancelled   failed → processing (可重试)
#        ↓
#    cancelled
# ---------------------------------------------------------------------------
REFUND_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["approved", "rejected", "cancelled"],
    "approved": ["processing", "cancelled"],
    "processing": ["completed", "failed"],
    "completed": [],
    "failed": ["processing"],
    "rejected": [],
    "cancelled": [],
}

# ---------------------------------------------------------------------------
# 订单风控阈值配置
# ---------------------------------------------------------------------------
# 超过以下任一阈值即触发风控告警，由 OrderDomainService.validate_order_risk() 使用
# ---------------------------------------------------------------------------
RISK_RULES = {
    "max_amount_per_order": 500000.0,
    "max_items_per_order": 200,
    "max_quantity_per_item": 10000,
}

# ---------------------------------------------------------------------------
# 促销活动状态机
# ---------------------------------------------------------------------------
# 状态流转图:
#   draft → scheduled → active → completed
#     ↓        ↓         ↓
#  cancelled  cancelled  paused → active (可恢复)
#                        ↓
#                     cancelled
# ---------------------------------------------------------------------------
PROMO_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["scheduled", "cancelled"],
    "scheduled": ["active", "cancelled"],
    "active": ["paused", "completed", "cancelled"],
    "paused": ["active", "cancelled"],
    "completed": [],
    "cancelled": [],
}

# 促销类型白名单
PROMO_TYPES = {"discount", "gift", "bundle", "flash_sale", "coupon"}

# 折扣类型白名单
DISCOUNT_TYPES = {"percentage", "fixed_amount", "free_shipping"}


class OrderDomainService:
    """
    销售订单领域服务

    职责:
      - 状态机校验: 判断订单是否可以从当前状态转移到目标状态
      - 风控校验:   检查订单金额、商品数量、单品数量是否超出阈值
      - 金额计算:   根据订单明细汇总订单总额
      - 操作判定:   判断订单是否可取消、是否可添加明细
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        判断订单状态是否允许从 current_status 转移到 target_status

        参数:
            current_status: 当前状态 (如 "pending", "confirmed")
            target_status:  目标状态 (如 "processing", "cancelled")

        返回:
            True 表示允许转移，False 表示不允许
        """
        return target_status in ORDER_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_order_risk(total_amount: float, item_count: int, max_quantity: int) -> list[str]:
        """
        订单风控校验

        检查三个维度:
          1. 订单总金额是否超过 max_amount_per_order (默认 500,000)
          2. 商品种类数是否超过 max_items_per_order (默认 200)
          3. 单品最大数量是否超过 max_quantity_per_item (默认 10,000)

        参数:
            total_amount: 订单总金额
            item_count:   商品种类数 (非购买总数)
            max_quantity: 所有明细中最大的单品数量

        返回:
            风控告警列表，空列表表示通过校验
        """
        risks: list[str] = []
        if total_amount > RISK_RULES["max_amount_per_order"]:
            risks.append(f"Order amount {total_amount} exceeds maximum {RISK_RULES['max_amount_per_order']}")
        if item_count > RISK_RULES["max_items_per_order"]:
            risks.append(f"Item count {item_count} exceeds maximum {RISK_RULES['max_items_per_order']}")
        if max_quantity > RISK_RULES["max_quantity_per_item"]:
            risks.append(f"Item quantity {max_quantity} exceeds maximum {RISK_RULES['max_quantity_per_item']}")
        return risks

    @staticmethod
    def calculate_order_total(items: list[SalesOrderItem]) -> float:
        """
        根据订单明细汇总计算订单总额

        汇总逻辑: sum(item.item_total)，item_total 为 None 时按 0 处理

        参数:
            items: 订单明细列表

        返回:
            订单明细总额
        """
        return sum(i.item_total or 0 for i in items)

    @staticmethod
    def is_cancellable(order: SalesOrder) -> bool:
        """
        判断订单是否可取消

        仅 pending 和 confirmed 状态的订单允许取消，
        已进入 processing 及之后状态的订单不可取消 (需走退货流程)

        参数:
            order: 销售订单实体

        返回:
            True 表示可取消
        """
        return order.status in ("pending", "confirmed")

    @staticmethod
    def can_add_items(order: SalesOrder) -> bool:
        """
        判断订单是否可添加明细行

        仅 pending 和 confirmed 状态的订单允许添加明细，
        已进入 processing 及之后状态的订单不可修改明细

        参数:
            order: 销售订单实体

        返回:
            True 表示可添加明细
        """
        return order.status in ("pending", "confirmed")


class RefundDomainService:
    """
    退款单领域服务

    职责:
      - 状态机校验: 判断退款单是否可以从当前状态转移到目标状态
      - 退款金额校验: 确保退款金额在合理范围内 (0 < 退款金额 ≤ 原单金额)
      - 自动审批判定: 判断退款单是否符合自动审批条件 (仅退款 + 低额)
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        判断退款单状态是否允许从 current_status 转移到 target_status

        参数:
            current_status: 当前状态 (如 "pending", "approved")
            target_status:  目标状态 (如 "processing", "rejected")

        返回:
            True 表示允许转移，False 表示不允许
        """
        return target_status in REFUND_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_refund_amount(refund_amount: float, original_order_amount: float) -> bool:
        """
        校验退款金额的合理性

        规则:
          1. 退款金额必须大于 0
          2. 退款金额不能超过原订单金额

        参数:
            refund_amount:         申请退款金额
            original_order_amount: 原订单金额

        返回:
            True 表示金额合理
        """
        return 0 < refund_amount <= original_order_amount

    @staticmethod
    def is_auto_approve_eligible(refund: RefundOrder) -> bool:
        """
        判断退款单是否符合自动审批条件

        自动审批条件 (两个条件必须同时满足):
          1. 退款类型为 "refund_only" (仅退款，不退货)
          2. 退款金额 ≤ 100.0 (低额退款，降低人工审核成本)

        参数:
            refund: 退款单实体

        返回:
            True 表示符合自动审批条件
        """
        return (
            refund.refund_type == "refund_only"
            and refund.refund_amount <= 100.0
        )


class PromotionDomainService:
    """
    促销活动领域服务

    职责:
      - 状态机校验: 判断促销活动是否可以从当前状态转移到目标状态
      - 促销规则校验: 验证促销类型、折扣类型、时间范围等是否合法
      - 折扣计算:   根据促销规则和订单金额计算实际折扣金额
      - 适用性判定: 判断促销活动是否适用于指定 SKU / 分类
      - 使用量判定: 判断促销活动是否仍在使用量限制内
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        判断促销活动状态是否允许从 current_status 转移到 target_status

        参数:
            current_status: 当前状态 (如 "draft", "scheduled")
            target_status:  目标状态 (如 "active", "cancelled")

        返回:
            True 表示允许转移，False 表示不允许
        """
        return target_status in PROMO_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_promotion(promo: Promotion) -> list[str]:
        """
        促销规则完整性校验

        校验维度:
          1. promo_type 必须在 PROMO_TYPES 白名单中
          2. discount_type 必须在 DISCOUNT_TYPES 白名单中
          3. 百分比折扣值必须在 [0, 100] 范围内
          4. 固定金额折扣不能为负数
          5. 结束时间必须晚于开始时间
          6. 最低消费金额不能为负数
          7. 最大折扣金额不能为负数

        参数:
            promo: 促销活动实体

        返回:
            校验错误列表，空列表表示通过校验
        """
        errors: list[str] = []
        if promo.promo_type not in PROMO_TYPES:
            errors.append(f"Invalid promo type '{promo.promo_type}'")
        if promo.discount_type not in DISCOUNT_TYPES:
            errors.append(f"Invalid discount type '{promo.discount_type}'")
        if promo.discount_type == "percentage" and (promo.discount_value < 0 or promo.discount_value > 100):
            errors.append("Percentage discount must be between 0 and 100")
        if promo.discount_type == "fixed_amount" and promo.discount_value < 0:
            errors.append("Fixed discount amount cannot be negative")
        if promo.start_time and promo.end_time and promo.end_time <= promo.start_time:
            errors.append("End time must be after start time")
        if promo.min_purchase_amount < 0:
            errors.append("Minimum purchase amount cannot be negative")
        if promo.max_discount_amount < 0:
            errors.append("Maximum discount amount cannot be negative")
        return errors

    @staticmethod
    def calculate_discount(promo: Promotion, order_amount: float, quantity: int = 1) -> float:
        """
        根据促销规则计算折扣金额

        计算逻辑:
          1. 如果订单金额 < 最低消费金额 (min_purchase_amount)，返回 0
          2. 根据折扣类型计算:
             - percentage:    折扣 = 订单金额 × 折扣值 / 100
             - fixed_amount:  折扣 = 固定折扣值
             - free_shipping: 折扣 = 0 (免邮费由物流模块处理)
          3. 如果设置了最大折扣金额 (max_discount_amount > 0)，取 min(计算值, 上限)
          4. 折扣金额不能为负数，四舍五入保留2位小数

        参数:
            promo:        促销活动实体
            order_amount: 订单金额
            quantity:     购买数量 (预留参数，当前未使用)

        返回:
            实际折扣金额 (≥ 0)
        """
        if order_amount < promo.min_purchase_amount:
            return 0.0
        if promo.discount_type == "percentage":
            discount = order_amount * promo.discount_value / 100
        elif promo.discount_type == "fixed_amount":
            discount = promo.discount_value
        elif promo.discount_type == "free_shipping":
            discount = 0.0
        else:
            discount = 0.0
        if promo.max_discount_amount > 0:
            discount = min(discount, promo.max_discount_amount)
        return round(max(discount, 0.0), 2)

    @staticmethod
    def is_applicable(promo: Promotion, sku_id: str = "", category_id: str = "") -> bool:
        """
        判断促销活动是否适用于指定的 SKU / 分类

        判定逻辑:
          1. 促销状态必须为 "active"
          2. 如果促销指定了适用 SKU 列表，则 sku_id 必须在列表中
          3. 如果促销指定了适用分类列表，则 category_id 必须在列表中
          4. 未指定适用范围 (空列表) 表示不限制

        参数:
            promo:       促销活动实体
            sku_id:      SKU 编码 (可选)
            category_id: 分类编码 (可选)

        返回:
            True 表示促销适用于该 SKU / 分类
        """
        import json
        if promo.status != "active":
            return False
        if promo.applicable_skus_json and promo.applicable_skus_json != "[]":
            applicable_skus = json.loads(promo.applicable_skus_json)
            if sku_id and applicable_skus and sku_id not in applicable_skus:
                return False
        if promo.applicable_categories_json and promo.applicable_categories_json != "[]":
            applicable_cats = json.loads(promo.applicable_categories_json)
            if category_id and applicable_cats and category_id not in applicable_cats:
                return False
        return True

    @staticmethod
    def is_within_usage_limit(promo: Promotion) -> bool:
        """
        判断促销活动是否仍在使用量限制内

        判定逻辑:
          1. 如果 usage_limit ≤ 0，表示不限制使用次数，返回 True
          2. 否则比较 used_count < usage_limit

        参数:
            promo: 促销活动实体

        返回:
            True 表示仍可使用
        """
        if promo.usage_limit <= 0:
            return True
        return promo.used_count < promo.usage_limit


# ---------------------------------------------------------------------------
# 物流申报规则 (P2-032)
# ---------------------------------------------------------------------------
# 规则匹配优先级: 国家 + 物流渠道 > 国家 + 品类 > 国家 + 重量段 > 默认规则
# 支持按国家/物流渠道/品类/重量设置申报信息(金额/HS编码/品名)
# ---------------------------------------------------------------------------
DECLARATION_RULE_PRIORITIES = [
    "country_channel",
    "country_category",
    "country_weight",
    "country_default",
    "global_default",
]


class LogisticsDeclarationService:
    """
    物流申报领域服务

    职责:
      - 申报规则匹配: 按优先级匹配最优的申报规则
      - 申报金额计算: 根据规则和订单信息计算申报金额
      - HS编码匹配: 根据SKU品类和国家匹配HS编码
      - 申报合规校验: 校验申报信息是否满足目的国合规要求
    """

    @staticmethod
    def match_declaration_rule(
        rules: list[dict],
        country: str,
        logistics_channel: str = "",
        category_id: str = "",
        weight: float = 0.0,
    ) -> dict | None:
        """
        按优先级匹配申报规则

        匹配顺序:
          1. 国家+物流渠道 精确匹配
          2. 国家+品类 精确匹配
          3. 国家+重量段 匹配 (按重量范围)
          4. 国家默认规则
          5. 全局默认规则

        参数:
            rules:            申报规则列表
            country:          目的国代码
            logistics_channel: 物流渠道
            category_id:      品类ID
            weight:           包裹重量(kg)

        返回:
            匹配到的规则，None表示无匹配规则
        """
        if not rules:
            return None

        # 优先级1: 国家+物流渠道
        for rule in rules:
            if (rule.get("country") == country
                    and rule.get("logistics_channel") == logistics_channel
                    and rule.get("rule_type") == "country_channel"):
                return rule

        # 优先级2: 国家+品类
        for rule in rules:
            if (rule.get("country") == country
                    and rule.get("category_id") == category_id
                    and rule.get("rule_type") == "country_category"):
                return rule

        # 优先级3: 国家+重量段
        for rule in rules:
            if rule.get("country") == country and rule.get("rule_type") == "country_weight":
                min_w = rule.get("min_weight", 0)
                max_w = rule.get("max_weight", 9999)
                if min_w <= weight <= max_w:
                    return rule

        # 优先级4: 国家默认
        for rule in rules:
            if rule.get("country") == country and rule.get("rule_type") == "country_default":
                return rule

        # 优先级5: 全局默认
        for rule in rules:
            if rule.get("rule_type") == "global_default":
                return rule

        return None

    @staticmethod
    def calculate_declared_value(
        item_total: float,
        rule: dict | None = None,
        declared_ratio: float = 1.0,
        min_declared: float = 0.0,
        max_declared: float = 0.0,
    ) -> dict:
        """
        计算申报金额

        规则:
          1. 有规则时按规则的申报比例/固定金额计算
          2. 无规则时按订单金额 × 默认申报比例
          3. 结果不能低于最低申报金额(如欧盟22欧元)
          4. 结果不能高于最高申报金额

        参数:
            item_total:     订单商品金额
            rule:           匹配到的申报规则
            declared_ratio: 默认申报比例 (0-1)
            min_declared:   最低申报金额
            max_declared:   最高申报金额

        返回:
            包含申报金额和建议的字典
        """
        if rule:
            if rule.get("declared_amount", 0) > 0:
                # 固定申报金额
                declared = rule["declared_amount"]
            else:
                ratio = rule.get("declared_ratio", declared_ratio)
                declared = item_total * ratio
        else:
            declared = item_total * declared_ratio

        declared = round(declared, 2)

        if min_declared > 0 and declared < min_declared:
            declared = min_declared
            warning = f"申报金额已提升至最低限额 {min_declared}"
        elif max_declared > 0 and declared > max_declared:
            declared = max_declared
            warning = f"申报金额已降低至最高限额 {max_declared}"
        else:
            warning = ""

        return {"declared_value": declared, "currency": "USD", "warning": warning}

    @staticmethod
    def validate_declaration(country: str, declared_value: float, hs_code: str = "") -> list[str]:
        """
        申报合规校验

        校验维度:
          1. 申报金额不能为0或负数
          2. 欧盟国家申报金额≥22欧元(约24美元)
          3. HS编码不能为空(部分国家要求)
          4. 特定品类(电子/纺织)需额外申报信息

        参数:
            country:        目的国
            declared_value: 申报金额
            hs_code:        HS编码

        返回:
            合规警告列表
        """
        warnings = []
        if declared_value <= 0:
            warnings.append("申报金额必须大于0")
        eu_countries = {"DE", "FR", "IT", "ES", "NL", "BE", "AT", "SE", "PL", "DK", "FI", "PT", "IE", "GR", "CZ", "HU", "RO"}
        if country in eu_countries and declared_value < 24:
            warnings.append(f"欧盟国家最低申报金额为22欧元(约24美元)，当前{declared_value}美元")
        if not hs_code:
            warnings.append("HS编码为空，建议填写以加速清关")
        return warnings


# ---------------------------------------------------------------------------
# 运输统计与交运批次 (P2-040)
# ---------------------------------------------------------------------------
# 核心指标: 估算运费vs实际运费差异、交运准时率、物流商时效统计
# ---------------------------------------------------------------------------


class TransportStatisticsService:
    """
    运输统计领域服务

    职责:
      - 运费差异计算: 估算运费与实际运费对比分析
      - 交运批次统计: 批次发货量/准时率等指标
      - 物流商时效: 按物流渠道统计平均时效
    """

    @staticmethod
    def calculate_freight_difference(estimated: float, actual: float) -> dict:
        """
        计算运费差异

        参数:
            estimated: 估算运费
            actual:    实际运费

        返回:
            差异分析结果
        """
        diff = actual - estimated
        diff_pct = round(diff / estimated * 100, 2) if estimated > 0 else 0
        return {
            "estimated": round(estimated, 2),
            "actual": round(actual, 2),
            "difference": round(diff, 2),
            "difference_pct": diff_pct,
            "is_over_budget": diff > 0,
        }

    @staticmethod
    def calculate_on_time_rate(shipments: list[dict]) -> dict:
        """
        计算交运准时率

        参数:
            shipments: 发运记录列表，每项含 {estimated_delivery, actual_delivery, status}

        返回:
            准时率统计
        """
        from datetime import UTC, datetime

        total = len(shipments)
        if total == 0:
            return {"on_time_rate": 0, "early_count": 0, "late_count": 0, "total": 0}

        on_time = 0
        early = 0
        late = 0
        for s in shipments:
            estimated = s.get("estimated_delivery")
            actual = s.get("actual_delivery")
            if not estimated or not actual:
                continue
            if isinstance(estimated, str):
                estimated = datetime.fromisoformat(estimated.replace("Z", "+00:00"))
            if isinstance(actual, str):
                actual = datetime.fromisoformat(actual.replace("Z", "+00:00"))
            if actual <= estimated:
                on_time += 1
            else:
                late += 1

        return {
            "on_time_rate": round(on_time / total * 100, 2) if total > 0 else 0,
            "early_count": early,
            "late_count": late,
            "total": total,
        }


# ---------------------------------------------------------------------------
# 插头国标规则 (P2-033)
# ---------------------------------------------------------------------------
# 按收货国家自动匹配对应插头规格SKU
# 规则: 不同国家/地区使用不同的插头标准
# ---------------------------------------------------------------------------
PLUG_STANDARDS = {
    "CN": {"standard": "GB", "plug_type": "A/C", "countries": ["CN"]},
    "US": {"standard": "NEMA", "plug_type": "A/B", "countries": ["US", "CA", "MX", "JP", "KR", "PH", "TW"]},
    "EU": {"standard": "CEE", "plug_type": "C/F", "countries": ["DE", "FR", "IT", "ES", "NL", "BE", "AT", "SE", "PL", "DK", "FI", "PT", "GR", "CZ", "HU", "RO", "BG", "HR", "LT", "LV", "EE", "SI", "SK", "LU"]},
    "UK": {"standard": "BS", "plug_type": "G", "countries": ["GB", "IE", "HK", "MY", "SG", "MT", "CY"]},
    "AU": {"standard": "AS", "plug_type": "I", "countries": ["AU", "NZ", "PG", "FJ"]},
    "IN": {"standard": "IS", "plug_type": "D/M", "countries": ["IN", "NP", "LK"]},
    "BR": {"standard": "NBR", "plug_type": "N", "countries": ["BR"]},
    "ZA": {"standard": "SANS", "plug_type": "D/M/N", "countries": ["ZA"]},
}


class PlugStandardService:
    """插头国标标准领域服务: 按收货国家匹配插头标准并推荐对应SKU"""

    @staticmethod
    def get_plug_type(country_code: str) -> str:
        """根据国家代码获取插头类型"""
        for std in PLUG_STANDARDS.values():
            if country_code in std["countries"]:
                return std["plug_type"]
        return "A/C"

    @staticmethod
    def get_plug_standard(country_code: str) -> dict:
        for std in PLUG_STANDARDS.values():
            if country_code in std["countries"]:
                return {"standard": std["standard"], "plug_type": std["plug_type"]}
        return {"standard": "GB", "plug_type": "A/C"}

    @staticmethod
    def should_swap_plug(origin_country: str, target_country: str) -> bool:
        """判断是否需要更换插头规格"""
        return PlugStandardService.get_plug_type(origin_country) != PlugStandardService.get_plug_type(target_country)


# ---------------------------------------------------------------------------
# 分拣口设置 (P2-039)
# ---------------------------------------------------------------------------
class SortingPortService:
    """分拣口设置领域服务: 配合智能分拣硬件按物流渠道分拣"""
    @staticmethod
    def assign_port(logistics_channel: str, port_mapping: dict) -> str:
        """根据物流渠道分配分拣口"""
        return port_mapping.get(logistics_channel, "default")

    @staticmethod
    def validate_port_config(ports: list[dict]) -> list[str]:
        errors = []
        used_channels = set()
        used_ports = set()
        for p in ports:
            ch = p.get("logistics_channel")
            port = p.get("port_code")
            if ch in used_channels:
                errors.append(f"物流渠道 '{ch}' 重复配置")
            if port in used_ports:
                errors.append(f"分拣口 '{port}' 被多个渠道共享")
            used_channels.add(ch)
            used_ports.add(port)
        return errors
