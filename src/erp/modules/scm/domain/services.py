"""
SCM 领域服务模块

本模块定义了供应链管理系统中三个核心聚合的领域服务:
  - PurchaseOrderDomainService: 采购订单领域服务 — 状态机、完成率、逾期判定
  - SupplierDomainService:      供应商领域服务 — 评分计算、合作等级、升降级判定
  - InquiryDomainService:       询价领域服务 — 状态机、报价比较、截止日期判定

设计原则:
  1. 领域服务无状态，所有方法均为 @staticmethod，不持有可变数据
  2. 状态机使用 "当前状态 → 允许转移列表" 的字典结构，便于扩展
  3. 业务规则集中在此层，应用服务 (application/services.py) 仅做编排
"""
from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erp.modules.scm.domain.models import PurchaseOrder, Supplier

# ---------------------------------------------------------------------------
# 采购订单状态机
# ---------------------------------------------------------------------------
# 状态流转图:
#   draft → submitted → approved → in_production → shipped → received → completed
#      ↓        ↓          ↓            ↓            ↓          ↓
#  cancelled  cancelled  cancelled   cancelled   cancelled  cancelled
#                                                          partially_received → received
# ---------------------------------------------------------------------------
PO_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["submitted", "cancelled"],
    "submitted": ["approved", "cancelled"],
    "approved": ["in_production", "cancelled"],
    "in_production": ["shipped", "cancelled"],
    "shipped": ["partially_received", "received", "cancelled"],
    "partially_received": ["received", "cancelled"],
    "received": ["completed"],
    "completed": [],
    "cancelled": [],
}

# ---------------------------------------------------------------------------
# 供应商评分权重配置
# ---------------------------------------------------------------------------
# 综合评分 = 质量×0.4 + 交付×0.3 + 价格×0.2 + 服务×0.1
# ---------------------------------------------------------------------------
SUPPLIER_RATING_WEIGHTS = {
    "quality": 0.4,
    "delivery": 0.3,
    "price": 0.2,
    "service": 0.1,
}


class PurchaseOrderDomainService:
    """
    采购订单领域服务

    职责:
      - 状态机校验: 判断采购订单是否可以从当前状态转移到目标状态
      - 完成率计算: 根据已收货金额 / 总金额计算完成率
      - 逾期判定:   判断采购订单是否超过预期交货日期
      - 明细可添加判定: 判断订单是否仍可添加明细行
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        判断采购订单状态是否允许从 current_status 转移到 target_status

        参数:
            current_status: 当前状态 (如 "draft", "submitted")
            target_status:  目标状态 (如 "approved", "cancelled")

        返回:
            True 表示允许转移，False 表示不允许
        """
        return target_status in PO_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def calculate_completion_rate(po: PurchaseOrder) -> float:
        """
        计算采购订单的收货完成率

        计算公式: 已收货金额 / 总金额 × 100%
        如果总金额为 0 或为空，返回 0.0

        参数:
            po: 采购订单实体

        返回:
            完成率百分比 (0.0 ~ 100.0)，保留2位小数
        """
        if not po.total_amount or po.total_amount <= 0:
            return 0.0
        received = getattr(po, "received_amount", 0) or 0
        return round(received / po.total_amount * 100, 2)

    @staticmethod
    def is_overdue(po: PurchaseOrder) -> bool:
        """
        判断采购订单是否逾期

        判定逻辑:
          1. 已完成或已取消的订单不算逾期
          2. 未设置预期交货日期的不算逾期
          3. 当前时间 > 预期交货日期即为逾期

        参数:
            po: 采购订单实体

        返回:
            True 表示逾期
        """
        from datetime import datetime
        if po.status in ("completed", "cancelled"):
            return False
        expected = getattr(po, "expected_delivery_date", None)
        if not expected:
            return False
        now = datetime.now(UTC)
        if hasattr(expected, "tzinfo") and expected.tzinfo is None:
            expected = expected.replace(tzinfo=UTC)
        return now > expected

    @staticmethod
    def can_add_items(po: PurchaseOrder) -> bool:
        """
        判断采购订单是否可添加明细行

        仅 draft 和 submitted 状态的订单允许添加明细

        参数:
            po: 采购订单实体

        返回:
            True 表示可添加明细
        """
        return po.status in ("draft", "submitted")


class SupplierDomainService:
    """
    供应商领域服务

    职责:
      - 评分计算: 根据质量/交付/价格/服务四个维度加权计算综合评分
      - 合作等级判定: 根据综合评分判定供应商合作等级
      - 升降级判定: 判断供应商是否满足升级/降级条件
    """

    @staticmethod
    def calculate_rating(
        quality_score: float = 0,
        delivery_score: float = 0,
        price_score: float = 0,
        service_score: float = 0,
    ) -> float:
        """
        计算供应商综合评分

        计算公式: 质量×0.4 + 交付×0.3 + 价格×0.2 + 服务×0.1
        权重由 SUPPLIER_RATING_WEIGHTS 配置

        参数:
            quality_score:  质量评分 (0~100)
            delivery_score: 交付评分 (0~100)
            price_score:    价格评分 (0~100)
            service_score:  服务评分 (0~100)

        返回:
            综合评分 (0~100)，保留2位小数
        """
        total = (
            quality_score * SUPPLIER_RATING_WEIGHTS["quality"]
            + delivery_score * SUPPLIER_RATING_WEIGHTS["delivery"]
            + price_score * SUPPLIER_RATING_WEIGHTS["price"]
            + service_score * SUPPLIER_RATING_WEIGHTS["service"]
        )
        return round(total, 2)

    @staticmethod
    def get_cooperation_level(rating: float) -> str:
        """
        根据综合评分判定合作等级

        等级划分:
          - ≥ 90: strategic  (战略供应商)
          - ≥ 75: preferred  (优选供应商)
          - ≥ 60: qualified  (合格供应商)
          - < 60: probationary (观察供应商)

        参数:
            rating: 综合评分

        返回:
            合作等级字符串
        """
        if rating >= 90:
            return "strategic"
        elif rating >= 75:
            return "preferred"
        elif rating >= 60:
            return "qualified"
        else:
            return "probationary"

    @staticmethod
    def should_upgrade(supplier: Supplier) -> bool:
        """
        判断供应商是否满足升级条件

        升级条件: 评分 ≥ 85 且当前等级为 normal 或 qualified

        参数:
            supplier: 供应商实体

        返回:
            True 表示满足升级条件
        """
        rating = getattr(supplier, "quality_score", 0) or 0
        return rating >= 85 and supplier.cooperation_level in ("normal", "qualified")

    @staticmethod
    def should_downgrade(supplier: Supplier) -> bool:
        """
        判断供应商是否满足降级条件

        降级条件: 评分 < 50 且当前等级为 preferred 或 strategic

        参数:
            supplier: 供应商实体

        返回:
            True 表示满足降级条件
        """
        rating = getattr(supplier, "quality_score", 0) or 0
        return rating < 50 and supplier.cooperation_level in ("preferred", "strategic")


# ---------------------------------------------------------------------------
# 询价单状态机
# ---------------------------------------------------------------------------
# 状态流转图:
#   draft → published → quoting → evaluating → awarded → completed
#      ↓        ↓          ↓          ↓
#  cancelled  cancelled  cancelled  cancelled
# ---------------------------------------------------------------------------
INQUIRY_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["published", "cancelled"],
    "published": ["quoting", "cancelled"],
    "quoting": ["evaluating", "cancelled"],
    "evaluating": ["awarded", "cancelled"],
    "awarded": ["completed"],
    "completed": [],
    "cancelled": [],
}


# ---------------------------------------------------------------------------
# 五种采购模式业务规则 (V4新增)
# ---------------------------------------------------------------------------
# 模式说明:
#   1. standard_purchase: 标准采购 — 常规PO，供应商发货→收货→质检→入库→付款
#   2. consignment:       寄售采购 — 供应商将货物放置在我方仓库，消耗后结算
#   3. jit_dropship:      JIT直发 — 供应商直接发货给终端客户，不经过我方仓库
#   4. vmi_subcontracting: VMI代工 — 供应商管理库存，按实际消耗结算
#   5. centralized:       集中采购 — 集中采购后分发给各实体
# ---------------------------------------------------------------------------
PURCHASE_MODES = {
    "standard_purchase": {
        "name": "标准采购",
        "requires_warehouse": True,
        "requires_inspection": True,
        "payment_on_receipt": True,
        "dropship": False,
        "description": "常规采购流程：下单→发货→收货→质检→入库→付款",
    },
    "consignment": {
        "name": "寄售采购",
        "requires_warehouse": True,
        "requires_inspection": True,
        "payment_on_receipt": False,
        "payment_on_consumption": True,
        "dropship": False,
        "description": "供应商将货物寄存在我方仓库，出库消耗后才结算",
    },
    "jit_dropship": {
        "name": "JIT直发",
        "requires_warehouse": False,
        "requires_inspection": False,
        "payment_on_receipt": True,
        "dropship": True,
        "description": "供应商直接发货给终端客户，不经过我方仓库",
    },
    "vmi_subcontracting": {
        "name": "VMI代工",
        "requires_warehouse": True,
        "requires_inspection": False,
        "payment_on_receipt": False,
        "payment_on_consumption": True,
        "dropship": False,
        "vmi": True,
        "description": "供应商管理库存(VMI)，代工厂按消耗结算",
    },
    "centralized": {
        "name": "集中采购",
        "requires_warehouse": True,
        "requires_inspection": True,
        "payment_on_receipt": True,
        "dropship": False,
        "centralized": True,
        "description": "集中采购后分配至各仓库/实体",
    },
}


class PurchaseModeService:
    """
    采购模式领域服务

    职责:
      - 校验采购模式是否合法
      - 判断当前模式是否需要仓库收货
      - 判断当前模式是否需要质检
      - 判断当前模式的结算方式
      - 根据采购模式生成对应的业务流程步骤
    """

    VALID_MODES = set(PURCHASE_MODES.keys())

    @staticmethod
    def is_valid_mode(mode: str) -> bool:
        """校验采购模式是否在支持的五种模式中"""
        return mode in PURCHASE_MODES

    @staticmethod
    def get_mode_config(mode: str) -> dict:
        """获取指定采购模式的完整配置"""
        return PURCHASE_MODES.get(mode, PURCHASE_MODES["standard_purchase"])

    @staticmethod
    def requires_warehouse_receipt(mode: str) -> bool:
        """
        判断该模式是否需要经过仓库收货流程

        直发模式(JIT)不需要仓库收货，直接由供应商发货给客户。
        VMI代工模式下货物已在仓库，仅做消耗确认。
        """
        config = PURCHASE_MODES.get(mode, PURCHASE_MODES["standard_purchase"])
        return config.get("requires_warehouse", True)

    @staticmethod
    def requires_quality_inspection(mode: str) -> bool:
        """
        判断该模式是否需要质检

        标准采购、寄售采购、集中采购需要质检。
        JIT直发和VMI代工不经过我方仓库，不安排质检。
        """
        config = PURCHASE_MODES.get(mode, PURCHASE_MODES["standard_purchase"])
        return config.get("requires_inspection", True)

    @staticmethod
    def is_dropship_mode(mode: str) -> bool:
        """判断是否为直发模式(JIT)，直接由供应商发货给终端客户"""
        config = PURCHASE_MODES.get(mode, PURCHASE_MODES["standard_purchase"])
        return config.get("dropship", False)

    @staticmethod
    def get_payment_trigger(mode: str) -> str:
        """
        获取该模式的付款触发条件

        Returns:
            "on_receipt":      收货后付款（标准采购/JIT直发/集中采购）
            "on_consumption":  消耗后付款（寄售采购/VMI代工）
        """
        config = PURCHASE_MODES.get(mode, PURCHASE_MODES["standard_purchase"])
        if config.get("payment_on_consumption"):
            return "on_consumption"
        return "on_receipt"

    @staticmethod
    def get_workflow_steps(mode: str) -> list[str]:
        """根据采购模式生成标准业务流程步骤"""
        base_steps = ["创建采购单", "审核采购单"]
        config = PURCHASE_MODES.get(mode, PURCHASE_MODES["standard_purchase"])

        if not config.get("dropship", False):
            base_steps.append("供应商发货")
            if config.get("requires_inspection", True):
                base_steps.append("到货质检")
            base_steps.append("仓库入库")

        if config.get("payment_on_consumption"):
            base_steps.append("消耗确认")
            base_steps.append("根据消耗量结算")
        else:
            base_steps.append("对账付款")

        if config.get("centralized"):
            base_steps.append("库存分配")
        base_steps.append("采购单完结")
        return base_steps


# ---------------------------------------------------------------------------
# 智能补货业务规则 (P2-046)
# ---------------------------------------------------------------------------
# 支持三种补货模式:
#   1. local_warehouse:   本地仓补货 — 基于本地销量+库存+在途计算
#   2. fba:               FBA补货 — 基于FBA销量+FBA库存+在途+头程时效
#   3. overseas_warehouse: 海外仓补货 — 基于全平台销量+海外仓库存+本地库存
# ---------------------------------------------------------------------------
REPLENISHMENT_RULES = {
    "local_warehouse": {
        "safety_stock_days": 7,
        "lead_time_days": 3,
        "order_cycle_days": 7,
        "max_stock_days": 30,
    },
    "fba": {
        "safety_stock_days": 14,
        "lead_time_days": 10,
        "order_cycle_days": 7,
        "max_stock_days": 60,
        "min_shipment_qty": 20,
    },
    "overseas_warehouse": {
        "safety_stock_days": 21,
        "lead_time_days": 15,
        "order_cycle_days": 14,
        "max_stock_days": 90,
    },
}


class ReplenishmentDomainService:
    """
    智能补货领域服务

    职责:
      - 计算建议补货量: 基于日均销量、当前库存、在途库存、安全库存
      - 计算补货建议: 支持本地仓/FBA/海外仓三种模式
      - 销量去噪: 排除促销等异常销量数据
      - 补货参数校验: 校验补货规则配置的合理性
    """

    @staticmethod
    def calculate_replenish_qty(
        daily_sales: float,
        current_stock: int,
        inbound_qty: int,
        safety_stock_days: int,
        lead_time_days: int,
        order_cycle_days: int,
        max_stock_days: int = 0,
        min_order_qty: int = 1,
    ) -> dict:
        """
        计算建议补货量

        公式:
          安全库存 = 日均销量 × 安全库存天数
          补货点 = 日均销量 × (备货时效 + 采购周期) + 安全库存
          建议补货量 = max(补货点 - 当前库存 - 在途数量, 最小起订量)

        参数:
            daily_sales:       日均销量
            current_stock:     当前可用库存
            inbound_qty:       在途/采购中数量
            safety_stock_days: 安全库存天数
            lead_time_days:    备货时效(天)
            order_cycle_days:  采购周期(天)
            max_stock_days:    最大库存天数(0=不限制)
            min_order_qty:     最小起订量

        返回:
            包含安全库存、补货点、建议补货量、库存天数的字典
        """
        if daily_sales <= 0:
            return {
                "safety_stock": 0,
                "reorder_point": 0,
                "suggested_qty": 0,
                "stock_on_hand_days": 999,
                "need_replenish": False,
            }

        safety_stock = round(daily_sales * safety_stock_days)
        reorder_point = round(daily_sales * (lead_time_days + order_cycle_days)) + safety_stock
        gap = reorder_point - current_stock - inbound_qty

        if max_stock_days > 0:
            max_stock = round(daily_sales * max_stock_days)
            max_allowed = max(0, max_stock - current_stock)
            gap = min(gap, max_allowed)

        suggested_qty = max(gap, min_order_qty) if gap > 0 else 0
        stock_days = round(current_stock / daily_sales, 1) if daily_sales > 0 else 999

        return {
            "safety_stock": safety_stock,
            "reorder_point": reorder_point,
            "suggested_qty": int(suggested_qty),
            "stock_on_hand_days": stock_days,
            "need_replenish": suggested_qty > 0,
        }

    @staticmethod
    def get_replenish_params(replenish_type: str, custom_params: dict | None = None) -> dict:
        """
        获取指定补货模式的参数配置

        支持自定义参数覆盖默认配置，用于不同SKU/仓库的特殊设置。
        """
        default = REPLENISHMENT_RULES.get(replenish_type, REPLENISHMENT_RULES["local_warehouse"])
        if custom_params:
            default = {**default, **custom_params}
        return default

    @staticmethod
    def denoise_sales(sales_data: list[dict]) -> list[dict]:
        """
        销量去噪 — 识别并过滤异常销量数据

        去噪逻辑:
          1. 使用IQR方法识别异常值
          2. 排除促销期间(标记为promotion的)数据
          3. 排除断货期间(销量为0但之前有稳定销量)的数据

        参数:
            sales_data: 销量数据列表，每项含 {date, qty, is_promotion, is_out_of_stock}

        返回:
            去噪后的销量数据
        """
        if not sales_data:
            return []
        filtered = [d for d in sales_data if not d.get("is_promotion") and not d.get("is_out_of_stock")]
        if not filtered:
            return sales_data
        qtys = sorted(d["qty"] for d in filtered)
        n = len(qtys)
        q1 = qtys[n // 4]
        q3 = qtys[3 * n // 4]
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        return [d for d in filtered if lower <= d["qty"] <= upper]

    @staticmethod
    def estimate_daily_sales(
        sales_data: list[dict],
        default_days: int = 30,
    ) -> float:
        """
        估算日均销量

        使用去噪后的数据，取最近 default_days 天的日均值。
        如果没有数据，返回0。

        参数:
            sales_data: 去噪后的销量数据
            default_days: 统计周期天数

        返回:
            日均销量 (保留2位小数)
        """
        recent = [d for d in sales_data if d.get("date")]
        if not recent:
            return 0.0
        recent = recent[-default_days:]
        total = sum(d["qty"] for d in recent)
        return round(total / max(len(recent), 1), 2)


class InquiryDomainService:
    """
    询价领域服务

    职责:
      - 状态机校验: 判断询价单是否可以从当前状态转移到目标状态
      - 报价比较:   对多个供应商报价进行综合评分排序
      - 截止日期判定: 判断询价是否已过截止日期
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        判断询价单状态是否允许从 current_status 转移到 target_status

        参数:
            current_status: 当前状态 (如 "draft", "published")
            target_status:  目标状态 (如 "quoting", "cancelled")

        返回:
            True 表示允许转移，False 表示不允许
        """
        return target_status in INQUIRY_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def compare_quotes(quotes: list[dict]) -> list[dict]:
        """
        对多个供应商报价进行综合评分排序

        评分维度:
          1. 价格维度 (40分): 有报价即得40分
          2. 交期维度 (30分): ≤7天+30分, ≤14天+20分, ≤30天+10分
          3. 供应商评分 (30分): ≥80+30分, ≥60+20分, ≥40+10分

        参数:
            quotes: 报价列表，每项包含:
                    - total_amount:     报价金额
                    - lead_time_days:   交货天数
                    - supplier_rating:  供应商评分

        返回:
            按评分降序排列的报价列表 (每项新增 evaluation_score 字段)
        """
        if not quotes:
            return []
        for q in quotes:
            score = 0
            total_amount = q.get("total_amount", 0)
            lead_time = q.get("lead_time_days", 999)
            if total_amount > 0:
                score += 40
            if lead_time <= 7:
                score += 30
            elif lead_time <= 14:
                score += 20
            elif lead_time <= 30:
                score += 10
            supplier_rating = q.get("supplier_rating", 0)
            if supplier_rating >= 80:
                score += 30
            elif supplier_rating >= 60:
                score += 20
            elif supplier_rating >= 40:
                score += 10
            q["evaluation_score"] = score
        return sorted(quotes, key=lambda x: x["evaluation_score"], reverse=True)

    @staticmethod
    def is_deadline_passed(inquiry) -> bool:
        """
        判断询价是否已过截止日期

        参数:
            inquiry: 询价单实体 (需有 deadline 属性)

        返回:
            True 表示已过截止日期
        """
        if not inquiry.deadline:
            return False
        return inquiry.deadline < datetime.now(UTC)


# ---------------------------------------------------------------------------
# 采购审批规则 (P2-045)
# ---------------------------------------------------------------------------
# 审批规则:
#   1. 按金额自动决定审批层级: 小额自动审批/中额主管审批/大额多级审批
#   2. 按采购模式特殊处理: JIT直发需额外审核供应商
#   3. 按供应商等级差异化: 战略供应商放宽额度
# ---------------------------------------------------------------------------
APPROVAL_THRESHOLDS = [
    {"max_amount": 1000, "level": "auto", "name": "自动审批"},
    {"max_amount": 10000, "level": "manager", "name": "主管审批"},
    {"max_amount": 100000, "level": "director", "name": "经理审批"},
    {"max_amount": float("inf"), "level": "multi", "name": "多级审批"},
]
"""采购审批额度阈值配置"""


class PurchaseApprovalService:
    """
    采购审批领域服务

    职责:
      - 审批层级判定: 根据金额/采购模式/供应商等级判定审批层级
      - 自动审批判定: 小额采购自动审批
      - 审批条件校验: 校验审批前置条件是否满足
    """

    @staticmethod
    def determine_approval_level(total_amount: float, purchase_mode: str = "standard_purchase",
                                  supplier_rating: float = 0) -> dict:
        """
        根据金额/模式/供应商等级判定审批层级

        规则:
          1. 按金额匹配审批级别
          2. JIT直发模式自动升一级
          3. 战略供应商(评分≥90)自动降一级
          4. 新供应商(评分=0)禁止自动审批

        参数:
            total_amount:   采购总金额
            purchase_mode:  采购模式
            supplier_rating: 供应商评分(0-100)

        返回:
            {level, name, requires_approval, approver_roles}
        """
        for threshold in APPROVAL_THRESHOLDS:
            if total_amount <= threshold["max_amount"]:
                level = threshold["level"]
                break
        else:
            level = "multi"

        # JIT直发模式: 自动升一级
        if purchase_mode == "jit_dropship" and level == "auto":
            level = "manager"

        # 战略供应商(评分≥90): 自动降一级
        if supplier_rating >= 90 and level == "director":
            level = "manager"
        elif supplier_rating >= 90 and level == "manager":
            level = "auto"

        # 新供应商(评分=0): 禁止自动审批
        if supplier_rating == 0 and level == "auto":
            level = "manager"

        return {
            "level": level,
            "requires_approval": level != "auto",
            "approver_roles": PurchaseApprovalService._get_approver_roles(level),
        }

    @staticmethod
    def _get_approver_roles(level: str) -> list[str]:
        role_map = {
            "auto": [],
            "manager": ["purchase_manager"],
            "director": ["purchase_director"],
            "multi": ["purchase_manager", "purchase_director", "finance_manager"],
        }
        return role_map.get(level, [])

    @staticmethod
    def check_prerequisites(po) -> list[str]:
        """
        校验审批前置条件

        检查项:
          1. 采购单有明细行
          2. 供应商状态为active
          3. 金额大于0
        """
        errors = []
        items = getattr(po, "items", []) or []
        if not items:
            errors.append("采购单没有明细行，无法提交审批")
        if po.total_amount <= 0:
            errors.append("采购金额必须大于0")
        supplier_status = getattr(po, "supplier_status", "active")
        if supplier_status != "active":
            errors.append("供应商状态异常，请先确认供应商状态")
        return errors


# ---------------------------------------------------------------------------
# 供应商平台服务 (P2-050)
# ---------------------------------------------------------------------------
# 供应商平台功能: 线上接单、回复备货、打印采购条码
# ---------------------------------------------------------------------------


class SupplierPlatformService:
    """
    供应商平台领域服务

    职责:
      - 接单确认: 供应商确认采购单并回复预计交期
      - 备货进度: 供应商更新备货进度
      - 条码打印: 生成采购条码信息
      - 新品推送: 供应商推送新品供卖家选品
    """

    @staticmethod
    def validate_order_confirmation(po_no: str, supplier_id: str, confirm_status: str,
                                     expected_delivery_date: str = "") -> list[str]:
        """
        校验供应商接单确认参数

        参数:
            po_no:                 采购单号
            supplier_id:           供应商ID
            confirm_status:        确认状态(accepted/rejected/negotiating)
            expected_delivery_date: 预计交货日期
        """
        errors = []
        if not po_no:
            errors.append("采购单号不能为空")
        if not supplier_id:
            errors.append("供应商ID不能为空")
        valid_statuses = {"accepted", "rejected", "negotiating"}
        if confirm_status not in valid_statuses:
            errors.append(f"无效的确认状态: {confirm_status}")
        if confirm_status == "accepted" and not expected_delivery_date:
            errors.append("接受采购单时必须回复预计交货日期")
        return errors

    @staticmethod
    def calculate_progress(ordered_qty: int, produced_qty: int, shipped_qty: int) -> dict:
        """
        计算备货进度

        参数:
            ordered_qty:  订购数量
            produced_qty: 已生产数量
            shipped_qty:  已发货数量

        返回:
            {production_pct, shipping_pct, remaining_qty}
        """
        if ordered_qty <= 0:
            return {"production_pct": 0, "shipping_pct": 0, "remaining_qty": 0}
        return {
            "production_pct": round(min(produced_qty / ordered_qty, 1) * 100, 2),
            "shipping_pct": round(min(shipped_qty / ordered_qty, 1) * 100, 2),
            "remaining_qty": max(0, ordered_qty - shipped_qty),
        }

    @staticmethod
    def generate_barcode_data(po_no: str, sku_id: str, sku_code: str, qty: int) -> dict:
        """
        生成采购条码数据

        用于供应商打印采购条码，包含采购单号、SKU信息、数量等。
        """
        return {
            "barcode_type": "CODE128",
            "data": {
                "po_no": po_no,
                "sku_id": sku_id,
                "sku_code": sku_code,
                "qty": qty,
            },
            "label": f"{po_no}-{sku_code}",
        }


class FinishedGoodsService:
    PROCESS_STATUS_TRANSITIONS = {
        "planned": ["in_production", "cancelled"],
        "in_production": ["completed", "paused", "cancelled"],
        "paused": ["in_production", "cancelled"],
        "completed": ["quality_check"],
        "quality_check": ["passed", "failed"],
        "passed": ["warehoused"],
        "warehoused": [], "failed": ["rework", "scrapped"],
        "rework": ["in_production", "scrapped"], "scrapped": [], "cancelled": [],
    }
    @staticmethod
    def can_transition(current: str, target: str) -> bool:
        return target in FinishedGoodsService.PROCESS_STATUS_TRANSITIONS.get(current, [])
    @staticmethod
    def calc_yield(total: int, good: int) -> dict:
        rate = round(good / total * 100, 2) if total > 0 else 0
        return {"total": total, "good": good, "yield": rate, "grade": "A" if rate >= 95 else ("B" if rate >= 85 else "C")}


class InvoiceTemplateService:
    @staticmethod
    def validate(items: list[dict], total: float) -> list[str]:
        e = []
        if not items: e.append("发票明细不能为空")
        if total <= 0: e.append("发票金额必须大于0")
        return e
    @staticmethod
    def calc_tax(subtotal: float, rate: float, vat: bool = False) -> dict:
        t = round(subtotal * rate, 2)
        return {"subtotal": round(subtotal, 2), "rate": rate, "tax": t, "total": subtotal + t if vat else subtotal}


class TemplateConfigService:
    TYPES = {"invoice", "contract", "barcode", "picklist", "package_label", "box_label", "shipping_label"}
    @staticmethod
    def is_valid(t: str) -> bool: return t in TemplateConfigService.TYPES
    @staticmethod
    def validate(cfg: dict) -> list[str]:
        e = []
        if not cfg.get("name"): e.append("模板名称不能为空")
        if cfg.get("type") and not TemplateConfigService.is_valid(cfg["type"]): e.append(f"类型不合法: {cfg['type']}")
        return e


# ---------------------------------------------------------------------------
# Temu/Shein/Amazon供应商模式 (P2-051)
# ---------------------------------------------------------------------------
# 平台供应商模式下，订单来自平台(如Temu/Shein)，供应商按平台要求备货发货
# ---------------------------------------------------------------------------


class PlatformSupplierService:
    """
    平台供应商模式领域服务

    支持三种平台供应商模式:
      1. Temu: Temu平台代销，供应商按Temu备货单发货到Temu国内仓
      2. Shein: Shein平台代销，供应商按Shein要求备货
      3. Amazon Vendor: Amazon Vendor Central模式，直接供应Amazon
    """
    PLATFORM_SUPPLIER_MODES = {"temu": "Temu代销", "shein": "Shein代销", "amazon_vendor": "Amazon Vendor"}

    @staticmethod
    def is_valid_mode(mode: str) -> bool:
        return mode in PlatformSupplierService.PLATFORM_SUPPLIER_MODES

    @staticmethod
    def generate_consignment_no(mode: str, tenant_short: str, seq: int) -> str:
        """生成平台备货单号"""
        from datetime import datetime
        prefix = {"temu": "TM", "shein": "SH", "amazon_vendor": "AV"}.get(mode, "PS")
        return f"{prefix}-{tenant_short}-{datetime.now().strftime('%Y%m%d')}-{seq:04d}"

    @staticmethod
    def validate_consignment(mode: str, items: list[dict], warehouse: str) -> list[str]:
        """校验平台备货单"""
        errors = []
        if not PlatformSupplierService.is_valid_mode(mode):
            errors.append(f"不支持的平台供应商模式: {mode}")
        if not items:
            errors.append("备货明细不能为空")
        if not warehouse:
            errors.append("发货仓库不能为空")
        return errors

    @staticmethod
    def get_target_warehouse(mode: str) -> str:
        """获取平台供应商模式的收货仓库"""
        warehouses = {
            "temu": "Temu国内质检仓",
            "shein": "Shein国内集货仓",
            "amazon_vendor": "Amazon Vendor Central",
        }
        return warehouses.get(mode, "未知")
