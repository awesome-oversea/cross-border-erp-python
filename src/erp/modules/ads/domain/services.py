"""
ADS (广告投放域) 领域服务

包含纯业务逻辑，不依赖任何基础设施 (数据库/外部API)。
所有方法均为静态方法，仅操作入参和内存对象。

领域服务清单:
  - AdCampaignDomainService: 广告活动状态机、效果指标计算
  - AdKeywordDomainService: 关键词出价校验、出价建议
  - AdGroupDomainService: 广告组状态机、组级效果汇总
  - AdPerformanceDomainService: 效果指标计算、异常检测、预算节奏、效率排名
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erp.modules.ads.domain.models import AdCampaign

# ============================================================
# 广告活动状态机
# draft → pending → active → paused → completed
# draft → cancelled, pending → rejected → draft
# completed / cancelled 为终态
# ============================================================

CAMPAIGN_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["pending", "cancelled"],
    "pending": ["active", "rejected", "cancelled"],
    "active": ["paused", "completed", "cancelled"],
    "paused": ["active", "completed", "cancelled"],
    "completed": [],
    "rejected": ["draft"],
    "cancelled": [],
}

MIN_DAILY_BUDGET = 1.0
MIN_KEYWORD_BID = 0.02
MAX_KEYWORD_BID = 1000.0


class AdCampaignDomainService:
    """
    广告活动领域服务

    管理广告活动的状态转换、激活校验、效果指标计算 (ACOS/ROAS/CTR)。
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        校验广告活动状态转换合法性

        状态机: draft → pending → active → paused → completed
        特殊路径: draft → cancelled, pending → rejected → draft
        completed / cancelled 为终态，不可再转换。

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            bool: 转换是否合法
        """
        return target_status in CAMPAIGN_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_for_activation(campaign: AdCampaign) -> list[str]:
        """
        校验广告活动是否可激活

        规则:
          1. 日预算必须 >= MIN_DAILY_BUDGET (1.0)
          2. 必须设置开始日期

        Args:
            campaign: 广告活动实体

        Returns:
            list[str]: 错误列表，空列表表示校验通过
        """
        errors: list[str] = []
        if campaign.daily_budget < MIN_DAILY_BUDGET:
            errors.append(f"Daily budget must be at least {MIN_DAILY_BUDGET}")
        if not campaign.start_date:
            errors.append("Start date is required for activation")
        return errors

    @staticmethod
    def calculate_acos(spend: float, sales: float) -> float:
        """
        计算 ACOS (广告销售成本比)

        ACOS = 花费 / 销售额 × 100
        - 销售额为0且有花费时返回 999.99 (表示极差)
        - 销售额和花费均为0时返回 0.0

        Args:
            spend: 广告花费
            sales: 广告销售额

        Returns:
            float: ACOS 百分比值
        """
        if sales <= 0:
            return 999.99 if spend > 0 else 0.0
        return round(spend / sales * 100, 2)

    @staticmethod
    def calculate_roas(spend: float, sales: float) -> float:
        """
        计算 ROAS (广告投资回报率)

        ROAS = 销售额 / 花费
        - 花费为0时返回 0.0

        Args:
            spend: 广告花费
            sales: 广告销售额

        Returns:
            float: ROAS 值
        """
        if spend <= 0:
            return 0.0
        return round(sales / spend, 2)

    @staticmethod
    def calculate_ctr(impressions: int, clicks: int) -> float:
        """
        计算 CTR (点击率)

        CTR = 点击量 / 展示量 × 100
        - 展示量为0时返回 0.0

        Args:
            impressions: 展示量
            clicks: 点击量

        Returns:
            float: CTR 百分比值
        """
        if impressions <= 0:
            return 0.0
        return round(clicks / impressions * 100, 4)

    @staticmethod
    def is_performing_well(campaign: AdCampaign, target_acos: float = 30.0) -> bool:
        """
        判断广告活动表现是否良好

        规则: ACOS > 0 且 ACOS <= target_acos

        Args:
            campaign: 广告活动实体
            target_acos: 目标 ACOS 阈值，默认 30%

        Returns:
            bool: 表现是否良好
        """
        acos = campaign.acos or 0
        return acos > 0 and acos <= target_acos


class AdKeywordDomainService:
    """
    关键词领域服务

    管理关键词出价校验和出价建议。
    出价范围: [MIN_KEYWORD_BID, MAX_KEYWORD_BID] = [0.02, 1000.0]
    """

    @staticmethod
    def validate_bid(bid: float) -> list[str]:
        """
        校验关键词出价合法性

        规则:
          1. 出价 >= MIN_KEYWORD_BID (0.02)
          2. 出价 <= MAX_KEYWORD_BID (1000.0)

        Args:
            bid: 出价金额

        Returns:
            list[str]: 错误列表，空列表表示校验通过
        """
        errors: list[str] = []
        if bid < MIN_KEYWORD_BID:
            errors.append(f"Keyword bid must be at least {MIN_KEYWORD_BID}")
        if bid > MAX_KEYWORD_BID:
            errors.append(f"Keyword bid cannot exceed {MAX_KEYWORD_BID}")
        return errors

    @staticmethod
    def suggest_bid(avg_cpc: float, target_acos: float, conversion_rate: float) -> float:
        """
        建议关键词出价

        公式: suggested = avg_cpc × (100 / target_acos) × conversion_rate
        结果限制在 [MIN_KEYWORD_BID, MAX_KEYWORD_BID] 范围内。

        Args:
            avg_cpc: 平均点击成本
            target_acos: 目标 ACOS
            conversion_rate: 转化率

        Returns:
            float: 建议出价
        """
        if conversion_rate <= 0 or target_acos <= 0:
            return MIN_KEYWORD_BID
        suggested = avg_cpc * (100 / target_acos) * conversion_rate
        return max(MIN_KEYWORD_BID, min(round(suggested, 2), MAX_KEYWORD_BID))


# ============================================================
# 广告组状态机
# enabled → paused → archived
# archived 为终态
# ============================================================

AD_GROUP_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "enabled": ["paused", "archived"],
    "paused": ["enabled", "archived"],
    "archived": [],
}


class AdGroupDomainService:
    """
    广告组领域服务

    管理广告组状态转换、创建校验、组级效果汇总。
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        校验广告组状态转换合法性

        状态机: enabled ↔ paused → archived
        archived 为终态，不可再转换。

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            bool: 转换是否合法
        """
        return target_status in AD_GROUP_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_for_creation(name: str, default_bid: float) -> list[str]:
        """
        校验广告组创建参数

        规则:
          1. 名称不能为空
          2. 默认出价不能为负数

        Args:
            name: 广告组名称
            default_bid: 默认出价

        Returns:
            list[str]: 错误列表，空列表表示校验通过
        """
        errors: list[str] = []
        if not name or not name.strip():
            errors.append("Ad group name cannot be empty")
        if default_bid < 0:
            errors.append("Default bid cannot be negative")
        return errors

    @staticmethod
    def calculate_group_performance(keywords: list[dict]) -> dict:
        """
        汇总广告组下所有关键词的效果数据

        汇总维度: 展示量/点击量/花费/销售额/订单数/CTR/ACOS/ROAS

        Args:
            keywords: 关键词效果数据列表，每项包含 impressions/clicks/spend/sales/orders

        Returns:
            dict: 汇总后的效果数据
        """
        if not keywords:
            return {"total_impressions": 0, "total_clicks": 0, "total_spend": 0.0,
                    "total_sales": 0.0, "total_orders": 0, "ctr": 0.0, "acos": 0.0, "roas": 0.0}
        total_impressions = sum(kw.get("impressions", 0) for kw in keywords)
        total_clicks = sum(kw.get("clicks", 0) for kw in keywords)
        total_spend = sum(kw.get("spend", 0.0) for kw in keywords)
        total_sales = sum(kw.get("sales", 0.0) for kw in keywords)
        total_orders = sum(kw.get("orders", 0) for kw in keywords)
        return {
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_spend": round(total_spend, 2),
            "total_sales": round(total_sales, 2),
            "total_orders": total_orders,
            "ctr": round(total_clicks / total_impressions * 100, 4) if total_impressions > 0 else 0.0,
            "acos": round(total_spend / total_sales * 100, 2) if total_sales > 0 else 0.0,
            "roas": round(total_sales / total_spend, 2) if total_spend > 0 else 0.0,
        }


class AdPerformanceDomainService:
    """
    广告效果领域服务

    管理效果指标计算 (CPC/转化率)、花费异常检测、预算节奏分析、活动效率排名。
    """

    @staticmethod
    def calculate_cpc(spend: float, clicks: int) -> float:
        """
        计算 CPC (单次点击成本)

        CPC = 花费 / 点击量
        - 点击量为0时返回 0.0

        Args:
            spend: 广告花费
            clicks: 点击量

        Returns:
            float: CPC 值
        """
        if clicks <= 0:
            return 0.0
        return round(spend / clicks, 2)

    @staticmethod
    def calculate_conversion_rate(orders: int, clicks: int) -> float:
        """
        计算转化率

        转化率 = 订单数 / 点击量 × 100
        - 点击量为0时返回 0.0

        Args:
            orders: 订单数
            clicks: 点击量

        Returns:
            float: 转化率百分比值
        """
        if clicks <= 0:
            return 0.0
        return round(orders / clicks * 100, 4)

    @staticmethod
    def detect_spend_anomaly(current_spend: float, avg_spend: float, threshold: float = 2.0) -> bool:
        """
        检测花费异常

        规则: |当前花费 - 平均花费| / 平均花费 > threshold
        - 平均花费为0时，有花费即异常

        Args:
            current_spend: 当前花费
            avg_spend: 平均花费
            threshold: 异常阈值，默认 2.0 (即偏差超过200%)

        Returns:
            bool: 是否异常
        """
        if avg_spend <= 0:
            return current_spend > 0
        return abs(current_spend - avg_spend) / avg_spend > threshold

    @staticmethod
    def calculate_budget_pacing(daily_budget: float, spend_today: float, hours_elapsed: float, hours_total: float = 24.0) -> dict:
        """
        计算预算节奏

        预期花费 = 日预算 × (已过小时 / 总小时)
        节奏百分比 = 今日花费 / 预期花费 × 100
        - >120%: overspending (超支)
        - 80%~120%: on_track (正常)
        - <80%: underspending (欠支)

        Args:
            daily_budget: 日预算
            spend_today: 今日已花费
            hours_elapsed: 已过小时数
            hours_total: 总小时数，默认24

        Returns:
            dict: 包含 pacing_pct / expected_spend / status
        """
        if hours_total <= 0 or daily_budget <= 0:
            return {"pacing_pct": 0.0, "expected_spend": 0.0, "status": "unknown"}
        expected_spend = daily_budget * (hours_elapsed / hours_total)
        pacing_pct = round(spend_today / expected_spend * 100, 2) if expected_spend > 0 else 0.0
        if pacing_pct > 120:
            status = "overspending"
        elif pacing_pct > 80:
            status = "on_track"
        else:
            status = "underspending"
        return {"pacing_pct": pacing_pct, "expected_spend": round(expected_spend, 2), "status": status}

    @staticmethod
    def rank_campaigns_by_efficiency(campaigns: list[dict], weight_acos: float = 0.4, weight_roas: float = 0.3, weight_ctr: float = 0.3) -> list[dict]:
        """
        按效率排名广告活动

        效率评分 = ACOS得分×weight_acos + ROAS得分×weight_roas + CTR得分×weight_ctr
        - ACOS得分: max(0, 100 - ACOS) — ACOS越低越好
        - ROAS得分: min(100, ROAS × 10) — ROAS越高越好
        - CTR得分: min(100, CTR × 100) — CTR越高越好

        Args:
            campaigns: 广告活动数据列表
            weight_acos: ACOS权重，默认0.4
            weight_roas: ROAS权重，默认0.3
            weight_ctr: CTR权重，默认0.3

        Returns:
            list[dict]: 按效率评分降序排列的活动列表
        """
        if not campaigns:
            return []
        for c in campaigns:
            acos_score = max(0, 100 - (c.get("acos", 100) or 100))
            roas_score = min(100, (c.get("roas", 0) or 0) * 10)
            ctr_score = min(100, (c.get("ctr", 0) or 0) * 100)
            c["efficiency_score"] = round(
                acos_score * weight_acos + roas_score * weight_roas + ctr_score * weight_ctr, 2
            )
        return sorted(campaigns, key=lambda x: x["efficiency_score"], reverse=True)
