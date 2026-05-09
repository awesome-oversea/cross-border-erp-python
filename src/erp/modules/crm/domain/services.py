"""
CRM 域服务模块 - 客户关系管理核心业务规则

本模块包含 CRM 域的所有领域服务，负责封装不可变的业务规则和状态机定义。
域服务不依赖任何基础设施（数据库、外部API），仅操作纯领域模型。

域服务职责：
  - 状态机转换规则校验
  - 业务规则验证（如金额校验、分类规则）
  - 领域计算逻辑（如客户分群、LTV计算、选品评分）
  - 不涉及持久化操作，由应用服务层负责调用域服务后持久化

包含的域服务：
  - CustomerDomainService: 客户分群与生命周期价值计算
  - ReviewDomainService: 评价状态机与紧急响应判定
  - ServiceTicketDomainService: 工单状态机与SLA超时判定
  - ReturnRefundDomainService: 退货退款状态机与自动审批判定
  - ComplaintDomainService: 投诉状态机与升级判定
  - ReviewReplyTemplateDomainService: 回复模板渲染与分类匹配
"""
from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erp.modules.crm.domain.models import Customer, ReturnRefund, Review, ServiceTicket

# ============================================================
# 客户分群规则定义
# ============================================================
# 分群优先级从高到低：vip → high_value → regular → new → normal
# 判定条件：订单数 >= min_orders 且 累计金额 >= min_amount
# inactive 为特殊分群，由定时任务根据最后活跃时间判定
SEGMENT_RULES: dict[str, dict] = {
    "vip": {"min_orders": 10, "min_amount": 5000.0},
    "high_value": {"min_orders": 5, "min_amount": 2000.0},
    "regular": {"min_orders": 2, "min_amount": 0.0},
    "new": {"min_orders": 1, "min_amount": 0.0},
    "inactive": {"min_orders": 0, "min_amount": 0.0},
    "normal": {"min_orders": 0, "min_amount": 0.0},
}

# ============================================================
# 工单状态机定义
# ============================================================
# 工单生命周期：open → in_progress → resolved → closed
# 支持挂起(pending_customer)、升级(escalated)、重开(reopened)等分支
TICKET_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "open": ["in_progress", "pending_customer", "cancelled"],
    "in_progress": ["pending_customer", "resolved", "escalated", "cancelled"],
    "pending_customer": ["in_progress", "resolved", "cancelled"],
    "escalated": ["in_progress", "resolved", "cancelled"],
    "resolved": ["closed", "reopened"],
    "closed": ["reopened"],
    "reopened": ["in_progress", "cancelled"],
    "cancelled": [],
}

# ============================================================
# 评价状态机定义
# ============================================================
# 评价处理流程：pending → acknowledged → replied → closed
# 支持升级(escalated)、跟进(followed_up)、忽略(ignored)
REVIEW_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["acknowledged", "ignored"],
    "acknowledged": ["replied", "escalated"],
    "escalated": ["replied"],
    "replied": ["followed_up", "closed"],
    "followed_up": ["closed"],
    "ignored": [],
    "closed": [],
}

# ============================================================
# 退货退款状态机定义
# ============================================================
# 退货退款流程：requested → approved → return_shipping → received → inspecting → refunding → refunded
# 支持拒绝(rejected)、退货被拒(rejected_return)、取消(cancelled)
RETURN_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "requested": ["approved", "rejected", "cancelled"],
    "approved": ["return_shipping", "cancelled"],
    "return_shipping": ["received", "cancelled"],
    "received": ["inspecting"],
    "inspecting": ["refunding", "rejected_return"],
    "refunding": ["refunded"],
    "refunded": [],
    "rejected": [],
    "rejected_return": [],
    "cancelled": [],
}


class CustomerDomainService:
    """客户域服务 - 封装客户分群与价值计算的业务规则

    职责：
      - 根据订单数和累计金额自动判定客户分群
      - 判定客户是否为VIP
      - 计算客户生命周期价值(LTV)
    """

    @staticmethod
    def classify_segment(total_orders: int, total_amount: float) -> str:
        """根据订单数和累计金额自动判定客户分群

        分群优先级从高到低依次判定：vip → high_value → regular → new
        如果都不满足，则归为 normal 分群

        Args:
            total_orders: 客户历史总订单数
            total_amount: 客户历史累计消费金额

        Returns:
            分群标识：vip / high_value / regular / new / normal
        """
        for seg_name in ("vip", "high_value", "regular", "new"):
            rule = SEGMENT_RULES[seg_name]
            if total_orders >= rule["min_orders"] and total_amount >= rule["min_amount"]:
                return seg_name
        return "normal"

    @staticmethod
    def is_vip(customer: Customer) -> bool:
        """判定客户是否为VIP分群

        Args:
            customer: 客户领域模型

        Returns:
            True 表示VIP客户
        """
        return customer.segment == "vip"

    @staticmethod
    def calculate_lifetime_value(total_amount: float, avg_margin_pct: float) -> float:
        """计算客户生命周期价值(LTV)

        LTV = 累计消费金额 × 平均毛利率百分比 / 100
        结果保留两位小数

        Args:
            total_amount: 客户历史累计消费金额
            avg_margin_pct: 平均毛利率百分比（如 30.0 表示 30%）

        Returns:
            客户生命周期价值，保留两位小数
        """
        return round(total_amount * avg_margin_pct / 100, 2)


class ReviewDomainService:
    """评价域服务 - 封装评价处理与状态转换的业务规则

    职责：
      - 判定评价是否为负面评价（评分 ≤ 2）
      - 校验评价状态转换是否合法
      - 判定评价是否需要紧急响应
    """

    @staticmethod
    def is_negative(rating: int) -> bool:
        """判定评价是否为负面评价

        评分 ≤ 2 视为负面评价，需要优先处理

        Args:
            rating: 评价评分（1-5）

        Returns:
            True 表示负面评价
        """
        return rating <= 2

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """校验评价状态转换是否合法

        根据 REVIEW_STATUS_TRANSITIONS 状态机定义判定

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            True 表示转换合法
        """
        return target_status in REVIEW_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def requires_urgent_response(review: Review) -> bool:
        """判定评价是否需要紧急响应

        紧急响应条件：负面评价 且 状态为 pending 或 acknowledged
        此类评价需要客服团队优先处理，避免影响店铺评分

        Args:
            review: 评价领域模型

        Returns:
            True 表示需要紧急响应
        """
        return review.is_negative and review.status in ("pending", "acknowledged")


class ServiceTicketDomainService:
    """工单域服务 - 封装工单状态转换与SLA判定的业务规则

    职责：
      - 校验工单状态转换是否合法
      - 判定工单是否SLA超时
      - 根据优先级计算SLA截止时间
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """校验工单状态转换是否合法

        根据 TICKET_STATUS_TRANSITIONS 状态机定义判定

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            True 表示转换合法
        """
        return target_status in TICKET_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def is_sla_breached(ticket: ServiceTicket) -> bool:
        """判定工单是否SLA超时

        SLA超时条件：
          1. 工单有SLA截止时间
          2. 工单状态非终态（resolved / closed / cancelled）
          3. 当前时间已超过SLA截止时间

        Args:
            ticket: 工单领域模型

        Returns:
            True 表示SLA已超时
        """
        from datetime import datetime
        if not ticket.sla_due_at:
            return False
        if ticket.status in ("resolved", "closed", "cancelled"):
            return False
        now = datetime.now(UTC)
        sla = ticket.sla_due_at
        if hasattr(sla, "tzinfo") and sla.tzinfo is None:
            sla = sla.replace(tzinfo=UTC)
        return now > sla

    @staticmethod
    def calculate_sla_deadline(priority: str) -> dict:
        """根据工单优先级计算SLA响应截止时间

        优先级与响应时效映射：
          - urgent: 2小时
          - high: 4小时
          - normal: 24小时
          - low: 48小时

        Args:
            priority: 工单优先级（urgent / high / normal / low）

        Returns:
            包含 hours（小时数）和 description（描述）的字典
        """
        sla_map = {
            "urgent": {"hours": 2, "description": "2 hours"},
            "high": {"hours": 4, "description": "4 hours"},
            "normal": {"hours": 24, "description": "24 hours"},
            "low": {"hours": 48, "description": "48 hours"},
        }
        return sla_map.get(priority, sla_map["normal"])


class ReturnRefundDomainService:
    """退货退款域服务 - 封装退货退款状态转换与自动审批的业务规则

    职责：
      - 校验退货退款状态转换是否合法
      - 校验退款金额是否合法
      - 判定是否满足自动审批条件
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """校验退货退款状态转换是否合法

        根据 RETURN_STATUS_TRANSITIONS 状态机定义判定

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            True 表示转换合法
        """
        return target_status in RETURN_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_refund_amount(refund_amount: float, order_amount: float) -> bool:
        """校验退款金额是否合法

        合法条件：0 < 退款金额 ≤ 订单金额

        Args:
            refund_amount: 申请退款金额
            order_amount: 原始订单金额

        Returns:
            True 表示退款金额合法
        """
        return 0 < refund_amount <= order_amount

    @staticmethod
    def is_auto_approve_eligible(return_refund: ReturnRefund) -> bool:
        """判定退货退款是否满足自动审批条件

        自动审批条件（同时满足）：
          1. 仅退款类型（refund_only），无需退货物流
          2. 退款金额 ≤ 100.0（低金额风险可控）
          3. 退款数量 ≤ 1（单件商品）

        满足以上条件的退货退款可自动审批通过，减少人工处理成本

        Args:
            return_refund: 退货退款领域模型

        Returns:
            True 表示满足自动审批条件
        """
        return (
            return_refund.return_type == "refund_only"
            and return_refund.refund_amount <= 100.0
            and return_refund.quantity <= 1
        )


# ============================================================
# 投诉状态机定义
# ============================================================
# 投诉处理流程：submitted → investigating → resolved → closed
# 支持升级(escalated)、重开(reopened)、取消(cancelled)
COMPLAINT_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "submitted": ["investigating", "cancelled"],
    "investigating": ["resolved", "escalated", "cancelled"],
    "escalated": ["investigating", "resolved", "cancelled"],
    "resolved": ["closed", "reopened"],
    "closed": ["reopened"],
    "reopened": ["investigating", "cancelled"],
    "cancelled": [],
}

# 投诉类型枚举
COMPLAINT_TYPES = {"product_quality", "late_delivery", "wrong_item", "service_attitude", "other"}

# 严重程度枚举（从低到高）
SEVERITY_LEVELS = {"low", "medium", "high", "critical"}

# 回复模板分类枚举
TEMPLATE_CATEGORIES = {"general", "positive", "negative", "neutral", "complaint"}

# 模板变量占位符集合，用于模板渲染时的变量替换
TEMPLATE_VARIABLES = {"{customer_name}", "{product_name}", "{order_id}", "{rating}"}


class ComplaintDomainService:
    """投诉域服务 - 封装投诉状态转换与升级判定的业务规则

    职责：
      - 校验投诉状态转换是否合法
      - 校验投诉类型和严重程度是否合法
      - 判定投诉是否需要升级处理
      - 计算投诉处理优先级分数
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """校验投诉状态转换是否合法

        根据 COMPLAINT_STATUS_TRANSITIONS 状态机定义判定

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            True 表示转换合法
        """
        return target_status in COMPLAINT_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_complaint(complaint_type: str, severity: str) -> list[str]:
        """校验投诉类型和严重程度是否合法

        Args:
            complaint_type: 投诉类型
            severity: 严重程度

        Returns:
            错误信息列表，空列表表示校验通过
        """
        errors: list[str] = []
        if complaint_type not in COMPLAINT_TYPES:
            errors.append(f"Invalid complaint type '{complaint_type}'")
        if severity not in SEVERITY_LEVELS:
            errors.append(f"Invalid severity '{severity}'")
        return errors

    @staticmethod
    def requires_escalation(severity: str, complaint_type: str) -> bool:
        """判定投诉是否需要升级处理

        升级条件（满足任一）：
          1. 严重程度为 high 或 critical
          2. 投诉类型为 product_quality（产品质量问题影响品牌声誉）

        Args:
            severity: 严重程度
            complaint_type: 投诉类型

        Returns:
            True 表示需要升级处理
        """
        return severity in ("high", "critical") or complaint_type == "product_quality"

    @staticmethod
    def calculate_resolution_priority(severity: str, is_vip: bool = False) -> int:
        """计算投诉处理优先级分数

        优先级分数越高，越需要优先处理。
        基础分数根据严重程度确定：critical=100, high=80, medium=50, low=20
        VIP客户的投诉额外加30分

        Args:
            severity: 严重程度
            is_vip: 是否VIP客户

        Returns:
            优先级分数（0-130）
        """
        priority_map = {"critical": 100, "high": 80, "medium": 50, "low": 20}
        score = priority_map.get(severity, 50)
        if is_vip:
            score += 30
        return score


class ReviewReplyTemplateDomainService:
    """评价回复模板域服务 - 封装模板渲染与分类匹配的业务规则

    职责：
      - 渲染回复模板（替换占位符变量）
      - 校验模板内容是否合法
      - 根据评价评分自动匹配模板分类
    """

    @staticmethod
    def render_template(template_content: str, variables: dict[str, str]) -> str:
        """渲染回复模板，替换占位符变量为实际值

        将模板中的 {key} 占位符替换为 variables 中对应的值。
        支持的占位符：{customer_name}, {product_name}, {order_id}, {rating}

        Args:
            template_content: 模板内容字符串
            variables: 变量字典，key 为占位符名称，value 为替换值

        Returns:
            渲染后的内容字符串
        """
        result = template_content
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))
        return result

    @staticmethod
    def validate_template(content_template: str) -> list[str]:
        """校验模板内容是否合法

        当前校验规则：模板内容不能为空

        Args:
            content_template: 模板内容字符串

        Returns:
            错误信息列表，空列表表示校验通过
        """
        errors: list[str] = []
        if not content_template.strip():
            errors.append("Template content cannot be empty")
        return errors

    @staticmethod
    def match_template_category(rating: int) -> str:
        """根据评价评分自动匹配回复模板分类

        评分与模板分类映射：
          - 评分 ≤ 2: negative（负面评价，使用安抚类模板）
          - 评分 = 3: neutral（中性评价，使用中性模板）
          - 评分 ≥ 4: positive（正面评价，使用感谢类模板）

        Args:
            rating: 评价评分（1-5）

        Returns:
            模板分类：negative / neutral / positive
        """
        if rating <= 2:
            return "negative"
        elif rating <= 3:
            return "neutral"
        else:
            return "positive"


class RefundReportService:
    """
    退款报告领域服务 (P3-024)

    职责:
      - 退款原因分类: 按退款原因归类统计
      - 退款趋势分析: 按时间维度统计退款趋势
      - 退款率计算: 按SKU/店铺/渠道维度计算退款率
    """

    REFUND_REASON_CATEGORIES = {
        "quality": ["产品质量问题", "功能故障", "外观破损", "配件缺失"],
        "logistics": ["物流延误", "包裹丢失", "包裹损坏", "送错地址"],
        "customer": ["不想要了", "误购", "重复下单", "价格不满意"],
        "fulfillment": ["发错商品", "数量不对", "颜色/尺码错误"],
        "other": ["其他原因"],
    }

    @staticmethod
    def categorize_reason(reason: str) -> str:
        """
        自动归类退款原因

        参数:
            reason: 原始退款原因文本

        返回:
            退款分类: quality/logistics/customer/fulfillment/other
        """
        reason_lower = reason.lower()
        for category, keywords in RefundReportService.REFUND_REASON_CATEGORIES.items():
            for keyword in keywords:
                if keyword.lower() in reason_lower:
                    return category
        return "other"

    @staticmethod
    def calculate_refund_rate(refund_count: int, total_orders: int) -> dict:
        """
        计算退款率

        参数:
            refund_count:  退款订单数
            total_orders:  总订单数

        返回:
            {rate, level, suggestion}
        """
        rate = round(refund_count / total_orders * 100, 2) if total_orders > 0 else 0
        if rate > 10:
            level = "critical"
            suggestion = "退款率过高，需要立即排查原因"
        elif rate > 5:
            level = "warning"
            suggestion = "退款率偏高，建议关注主要退款原因"
        else:
            level = "normal"
            suggestion = "退款率在正常范围内"
        return {"refund_rate": rate, "level": level, "suggestion": suggestion}


class QualityIssueService:
    """
    质量问题记录与PDM/WMS联动服务 (P3-025)

    职责:
      - 质量问题分类: 按来源(质检/客服/评论)归类
      - 严重程度判定: 根据问题类型和影响范围判定
      - PDM联动: 自动创建产品问题记录
      - WMS联动: 触发库存锁定或退货流程
    """

    ISSUE_SOURCES = {"qc_inspection": "质检", "customer_service": "客服", "review": "评论"}
    ISSUE_PRIORITIES = {"critical": "紧急", "high": "高", "medium": "中", "low": "低"}

    @staticmethod
    def determine_priority(issue_type: str, frequency: int = 1) -> str:
        """
        根据问题类型和发生频率判定优先级

        规则:
          - 安全问题(critical): 紧急
          - 功能问题(high): 发生≥3次为高，否则为中
          - 外观问题(medium): 发生≥5次为中，否则为低
          - 其他(low): 低
        """
        priority_map = {
            "safety": "critical",
            "functional": "high" if frequency >= 3 else "medium",
            "appearance": "medium" if frequency >= 5 else "low",
            "packaging": "medium" if frequency >= 5 else "low",
            "labeling": "low",
        }
        return priority_map.get(issue_type, "low")

    @staticmethod
    def should_notify_pdm(issue_type: str, priority: str) -> bool:
        """
        判断是否需要通知PDM创建产品问题记录

        规则: 紧急/高优先级问题需要通知PDM
        """
        return priority in ("critical", "high")

    @staticmethod
    def should_lock_inventory(issue_type: str, priority: str) -> bool:
        """
        判断是否需要通知WMS锁定库存

        规则: 安全问题或紧急优先级需要锁定库存
        """
        return issue_type == "safety" or priority == "critical"


class MessageIntegrationService:
    """多平台消息/邮件接入 (P3-018): Amazon/Shopify/eBay等平台消息统一接入"""
    SUPPORTED_PLATFORMS = {"amazon", "shopify", "ebay", "walmart", "aliexpress"}

    @staticmethod
    def normalize(raw: dict, platform: str) -> dict:
        return {"platform": platform, "id": raw.get("id") or raw.get("message_id"),
                "from": raw.get("from") or raw.get("sender"), "subject": raw.get("subject", ""),
                "body": raw.get("body") or raw.get("content", ""), "created_at": raw.get("created_at") or raw.get("timestamp")}

    @staticmethod
    def is_supported(platform: str) -> bool:
        return platform in MessageIntegrationService.SUPPORTED_PLATFORMS


class CustomerServiceAssignmentService:
    """客服分配服务 (P3-019): 按规则智能分配客服"""
    @staticmethod
    def assign(ticket: dict, agents: list[dict]) -> str:
        candidates = [a for a in agents if a.get("status") == "online" and ticket.get("category") in a.get("skills", [])]
        if not candidates: candidates = [a for a in agents if a.get("status") == "online"]
        if not candidates: return ""
        return min(candidates, key=lambda a: (a.get("active_tickets", 0), a.get("workload", 0))).get("id", "")

    @staticmethod
    def workload_balance(agents: list[dict]) -> list[dict]:
        return sorted(agents, key=lambda a: a.get("active_tickets", 0))


class ReviewRequestService:
    """请求评论 (P3-022): 自动排除退款/差评订单"""
    @staticmethod
    def is_eligible(order: dict) -> bool:
        if order.get("has_refund"): return False
        if order.get("rating", 5) <= 2: return False
        if order.get("is_review_requested"): return False
        return True

    @staticmethod
    def filter_batch(orders: list[dict]) -> list[dict]:
        return [o for o in orders if ReviewRequestService.is_eligible(o)]


class EmailMarketingService:
    """邮件营销 (P3-023): 自动推广邮件"""
    @staticmethod
    def segment(customers: list[dict], min_orders: int = 1, max_days_since: int = 90) -> list[dict]:
        from datetime import UTC, datetime, timedelta
        cutoff = datetime.now(UTC) - timedelta(days=max_days_since)
        return [c for c in customers if c.get("order_count", 0) >= min_orders]


class CsStatisticsService:
    """客服统计 (P3-026): 回复时效/质量/绩效"""
    @staticmethod
    def calc_response_time(ticket) -> float:
        created = getattr(ticket, "created_at", None)
        first_reply = getattr(ticket, "first_reply_at", None)
        if not created or not first_reply: return 0
        return max(0, (first_reply - created).total_seconds() / 3600)

    @staticmethod
    def performance(tickets: list) -> dict:
        total = len(tickets)
        resolved = sum(1 for t in tickets if getattr(t, "status", "") in ("resolved", "closed"))
        resolved_ok = sum(1 for t in tickets if getattr(t, "satisfaction", 0) >= 4)
        avg_resp = sum(CsStatisticsService.calc_response_time(t) for t in tickets) / max(total, 1)
        return {"total": total, "resolved": resolved, "satisfied": resolved_ok,
                "resolution_rate": round(resolved / max(total, 1) * 100, 2),
                "avg_response_hours": round(avg_resp, 1)}
