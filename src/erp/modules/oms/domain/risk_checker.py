"""
OMS 订单风控检查与拆单引擎模块

本模块提供两个核心领域能力:
  - OrderRiskChecker:  订单风控检查器 — 多维度评分，判定订单风险等级
  - OrderSplitEngine:  订单拆分引擎 — 根据仓库/平台/重量/SKU规则拆分订单

设计原则:
  1. 风控检查采用评分制，各维度独立加分，最终根据总分判定风险等级
  2. 拆单引擎支持多种拆分策略，按优先级依次匹配
  3. 两个类均为无状态设计，所有方法为 @classmethod，便于直接调用
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from erp.shared.observability.logging import get_logger

logger = get_logger("erp.oms.risk")


@dataclass
class RiskCheckResult:
    """
    风控检查结果数据类

    属性:
        passed:     是否通过风控 (risk_level != "high" 即为通过)
        risk_level: 风险等级 — "low" / "medium" / "high"
        flags:      触发的风控标记列表 (如 ["high_amount", "suspicious_email"])
        score:      风控评分 (0~100+，分数越高风险越大)

    评分阈值:
        - score < 25:  low    (低风险，自动通过)
        - 25 ≤ score < 50: medium (中风险，需人工审核)
        - score ≥ 50:  high   (高风险，自动拦截)
    """
    passed: bool = True
    risk_level: str = "low"
    flags: list[str] = None
    score: int = 0

    def __post_init__(self):
        if self.flags is None:
            self.flags = []


class OrderRiskChecker:
    """
    订单风控检查器

    从以下维度对订单进行风险评估:
      1. 金额维度:     订单总金额是否超过 HIGH_AMOUNT_THRESHOLD (默认 10,000)
      2. 数量维度:     商品总数量是否超过 HIGH_QUANTITY_THRESHOLD (默认 100)
      3. 邮箱维度:     买家邮箱是否匹配可疑模式 (测试邮箱、连续数字等)
      4. 国家维度:     收件国家是否属于高风险国家列表
      5. 频率维度:     同一买家当日下单数是否超过 MAX_ORDERS_PER_BUYER_PER_DAY (默认 20)
      6. 历史维度:     买家是否有历史欺诈记录
      7. 地址维度:     收件地址与账单地址是否不同
      8. IP维度:       下单IP所属国家与收件国家是否不匹配

    各维度独立评分，最终汇总判定风险等级:
      - score ≥ 50: high   (拦截)
      - score ≥ 25: medium (人工审核)
      - score < 25: low    (放行)
    """

    # 高金额阈值 — 订单总金额 ≥ 此值触发 "high_amount" 标记 (+30分)
    HIGH_AMOUNT_THRESHOLD = 10000.0

    # 高数量阈值 — 商品总数量 ≥ 此值触发 "high_quantity" 标记 (+20分)
    HIGH_QUANTITY_THRESHOLD = 100

    # 可疑邮箱正则模式列表 — 匹配任一模式触发 "suspicious_email" 标记 (+15分)
    SUSPICIOUS_PATTERNS = [
        r"test@",           # 测试邮箱 (如 test@example.com)
        r"\.test\b",        # 测试域名 (如 user@test.com)
        r"123456",          # 连续数字 (如 user123456@mail.com)
        r"test\s*user",     # 测试用户名 (如 testuser, test user)
    ]

    # 高风险国家代码列表 — 收件国家在此列表触发 "risky_country" 标记 (+25分)
    RISKY_COUNTRIES = ["XX", "YY"]

    # 单买家每日最大下单数 — 超过触发 "high_frequency_buyer" 标记 (+20分)
    MAX_ORDERS_PER_BUYER_PER_DAY = 20

    @classmethod
    def check(cls, order_data: dict, buyer_history: dict | None = None) -> RiskCheckResult:
        """
        执行订单风控检查

        检查流程:
          1. 金额检查: total_amount ≥ HIGH_AMOUNT_THRESHOLD → +30分
          2. 数量检查: 商品总数量 ≥ HIGH_QUANTITY_THRESHOLD → +20分
          3. 邮箱检查: 买家邮箱匹配可疑模式 → +15分
          4. 国家检查: 收件国家在 RISKY_COUNTRIES → +25分
          5. 频率检查: 买家当日下单数 ≥ MAX_ORDERS_PER_BUYER_PER_DAY → +20分
          6. 欺诈历史: 买家有过往欺诈记录 → +35分
          7. 地址检查: 收件地址 ≠ 账单地址 → +5分
          8. IP检查:   下单IP国家 ≠ 收件国家 → +15分

        参数:
            order_data:    订单数据字典，包含以下关键字段:
                           - total_amount:     订单总金额
                           - items:            商品列表 (每项含 quantity)
                           - buyer_email:      买家邮箱
                           - recipient_country: 收件国家代码
                           - recipient_address: 收件地址
                           - billing_address:   账单地址
                           - ip_country:        下单IP国家代码
            buyer_history: 买家历史数据字典 (可选)，包含:
                           - daily_order_count: 当日下单数
                           - previous_fraud_count: 历史欺诈次数

        返回:
            RiskCheckResult 实例，包含 passed / risk_level / flags / score
        """
        flags: list[str] = []
        score = 0

        # --- 维度1: 金额检查 ---
        amount = float(order_data.get("total_amount", 0))
        if amount >= cls.HIGH_AMOUNT_THRESHOLD:
            flags.append("high_amount")
            score += 30

        # --- 维度2: 数量检查 ---
        items = order_data.get("items", [])
        total_qty = sum(item.get("quantity", 0) for item in items) if items else 0
        if total_qty >= cls.HIGH_QUANTITY_THRESHOLD:
            flags.append("high_quantity")
            score += 20

        # --- 维度3: 邮箱检查 ---
        buyer_email = order_data.get("buyer_email", "")
        if buyer_email and cls._is_suspicious_email(buyer_email):
            flags.append("suspicious_email")
            score += 15

        # --- 维度4: 国家检查 ---
        shipping_country = order_data.get("recipient_country", "")
        if shipping_country in cls.RISKY_COUNTRIES:
            flags.append("risky_country")
            score += 25

        # --- 维度5~6: 买家历史检查 (需要 buyer_history) ---
        if buyer_history:
            daily_count = buyer_history.get("daily_order_count", 0)
            if daily_count >= cls.MAX_ORDERS_PER_BUYER_PER_DAY:
                flags.append("high_frequency_buyer")
                score += 20

            previous_fraud = buyer_history.get("previous_fraud_count", 0)
            if previous_fraud > 0:
                flags.append("previous_fraud_history")
                score += 35

        # --- 维度7: 地址检查 ---
        shipping_address = order_data.get("recipient_address", "")
        billing_address = order_data.get("billing_address", "")
        if shipping_address and billing_address and shipping_address != billing_address:
            flags.append("different_billing_shipping")
            score += 5

        # --- 维度8: IP国家检查 ---
        ip_country = order_data.get("ip_country", "")
        if ip_country and shipping_country and ip_country != shipping_country:
            flags.append("ip_country_mismatch")
            score += 15

        # --- 汇总判定风险等级 ---
        risk_level = "low"
        if score >= 50:
            risk_level = "high"
        elif score >= 25:
            risk_level = "medium"

        passed = risk_level != "high"

        return RiskCheckResult(
            passed=passed,
            risk_level=risk_level,
            flags=flags,
            score=score,
        )

    @classmethod
    def _is_suspicious_email(cls, email: str) -> bool:
        """
        判断邮箱是否匹配可疑模式

        将邮箱转为小写后，逐一匹配 SUSPICIOUS_PATTERNS 中的正则表达式，
        任一匹配即判定为可疑。

        参数:
            email: 买家邮箱地址

        返回:
            True 表示邮箱可疑
        """
        email_lower = email.lower()
        return any(re.search(pattern, email_lower) for pattern in cls.SUSPICIOUS_PATTERNS)


class OrderSplitEngine:
    """
    订单拆分引擎

    根据拆单规则将一个订单拆分为多个子订单，支持以下拆分策略:
      - by_warehouse: 按仓库拆分 — 不同仓库的商品拆为不同子订单
      - by_platform:  按平台拆分 — (预留，当前返回原订单)
      - by_weight:    按重量拆分 — 超过最大重量的包裹拆分
      - by_sku:       按SKU拆分 — (预留，当前返回原订单)

    拆分流程:
      1. 遍历规则列表，按顺序匹配第一个有效规则
      2. 根据规则类型执行对应的拆分策略
      3. 如果没有匹配到任何规则，返回原订单 (不拆分)

    设计说明:
      - 拆单规则由 OrderSplitRule 实体定义，通过仓储加载
      - 拆分结果为字典列表，每个字典代表一个子订单
    """

    @classmethod
    def evaluate_split(cls, order_data: dict, rules: list[dict]) -> list[dict]:
        """
        评估订单拆分方案

        按规则列表顺序依次匹配，第一个匹配成功的规则决定拆分方式。
        如果没有匹配到任何规则，返回包含原订单的列表 (不拆分)。

        参数:
            order_data: 订单数据字典，必须包含 "items" 字段
            rules:      拆单规则列表，每条规则包含:
                        - rule_type:  规则类型 ("by_warehouse" / "by_platform" / "by_weight" / "by_sku")
                        - conditions: 规则条件字典

        返回:
            拆分后的子订单列表，每个元素为一个字典
        """
        if not rules:
            return [order_data]

        splits: list[dict] = []
        items = order_data.get("items", [])
        if not items:
            return [order_data]

        for rule in rules:
            rule_type = rule.get("rule_type", "")
            conditions = rule.get("conditions", {})

            if rule_type == "by_warehouse":
                splits = cls._split_by_warehouse(items, conditions)
            elif rule_type == "by_platform":
                splits = cls._split_by_platform(items, conditions)
            elif rule_type == "by_weight":
                splits = cls._split_by_weight(items, conditions)
            elif rule_type == "by_sku":
                splits = cls._split_by_sku(items, conditions)

            if splits:
                break

        if not splits:
            splits = [order_data]

        return splits

    @classmethod
    def _split_by_warehouse(cls, items: list[dict], conditions: dict) -> list[dict]:
        """
        按仓库拆分订单

        将商品按 warehouse_id 分组，同一仓库的商品归入同一子订单。
        如果商品未指定仓库，使用 conditions 中的 default_warehouse (默认 "wh-default")。

        参数:
            items:      商品列表，每项含 warehouse_id 字段
            conditions: 规则条件，含 default_warehouse 字段

        返回:
            按仓库分组的子订单列表
        """
        warehouse_map: dict[str, list] = {}
        for item in items:
            wh = item.get("warehouse_id", conditions.get("default_warehouse", "wh-default"))
            if wh not in warehouse_map:
                warehouse_map[wh] = []
            warehouse_map[wh].append(item)

        return [{"warehouse_id": wh, "items": its} for wh, its in warehouse_map.items()]

    @classmethod
    def _split_by_platform(cls, items: list[dict], conditions: dict) -> list[dict]:
        """
        按平台拆分订单 (预留实现)

        当前返回不拆分的结果，后续可根据平台属性分组

        参数:
            items:      商品列表
            conditions: 规则条件

        返回:
            包含全部商品的单一子订单列表
        """
        return [{"items": items}]

    @classmethod
    def _split_by_weight(cls, items: list[dict], conditions: dict) -> list[dict]:
        """
        按重量拆分订单

        将商品按重量分组，每组总重量不超过 max_weight_kg (默认 30kg)。
        使用贪心算法: 依次将商品加入当前组，超重则新建一组。

        参数:
            items:      商品列表，每项含 weight_kg 字段 (默认 0.5kg)
            conditions: 规则条件，含 max_weight_kg 字段

        返回:
            按重量分组的子订单列表
        """
        max_weight = conditions.get("max_weight_kg", 30.0)
        current_weight = 0.0
        groups: list[list] = []
        current_group: list = []

        for item in items:
            weight = item.get("weight_kg", 0.5)
            if current_weight + weight > max_weight and current_group:
                groups.append(current_group)
                current_group = []
                current_weight = 0.0
            current_group.append(item)
            current_weight += weight

        if current_group:
            groups.append(current_group)

        return [{"items": g} for g in groups]

    @classmethod
    def _split_by_sku(cls, items: list[dict], conditions: dict) -> list[dict]:
        """
        按SKU拆分订单 (预留实现)

        当前返回不拆分的结果，后续可根据SKU属性分组

        参数:
            items:      商品列表
            conditions: 规则条件

        返回:
            包含全部商品的单一子订单列表
        """
        return [{"items": items}]
