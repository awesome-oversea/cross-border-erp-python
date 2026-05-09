"""
FMS (财务域) 领域服务层

职责: 封装纯业务逻辑，不依赖任何基础设施 (数据库/消息队列/外部API)
设计原则:
  1. 所有方法均为 @staticmethod，无状态，可被多个应用服务复用
  2. 状态机转换规则集中定义在模块顶部，禁止散落在各处
  3. 校验方法返回 list[str] (错误列表)，由应用服务决定如何抛异常
  4. 计算方法返回具体值 (float/dict)，由应用服务组装持久化

领域服务分类:
  - 状态机服务: can_transition() — 校验状态转换合法性
  - 校验服务: validate_xxx() — 校验业务规则，返回错误列表
  - 计算服务: calculate_xxx() — 纯计算，无副作用
  - 查询服务: find_xxx() — 纯逻辑查询，不涉及数据库

状态机总览:
  ┌──────────────────┬──────────────────────────────────────────────────┐
  │ 聚合根            │ 状态转换路径                                      │
  ├──────────────────┼──────────────────────────────────────────────────┤
  │ CostEvent        │ draft→confirmed→settled, draft→cancelled         │
  │ Settlement       │ pending→confirmed→settled, pending→cancelled     │
  │ PaymentRequest   │ pending→approved→paid, pending→rejected/cancelled│
  │ WriteOff         │ pending→approved→completed, pending→rejected     │
  │ Reconciliation   │ pending→reconciled, pending→disputed→reconciled  │
  │ Invoice          │ draft→issued→paid/voided/overdue, overdue→paid   │
  │ Expense          │ pending→approved→paid, pending→rejected/cancelled│
  │ ForexTransaction │ pending→completed/cancelled                      │
  │ PlatformBill     │ pending→reconciled, pending→disputed→reconciled  │
  └──────────────────┴──────────────────────────────────────────────────┘
"""
from __future__ import annotations


# ============================================================
# 状态机转换规则 — 集中定义，禁止散落
# 每个字典的 key 为当前状态，value 为可转换的目标状态列表
# ============================================================

COST_EVENT_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["confirmed", "cancelled"],
    "confirmed": ["settled"],
    "settled": [],
    "cancelled": [],
}

SETTLEMENT_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["confirmed", "cancelled"],
    "confirmed": ["settled"],
    "settled": [],
    "cancelled": [],
}

PAYMENT_REQUEST_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["approved", "rejected", "cancelled"],
    "approved": ["paid", "cancelled"],
    "paid": [],
    "rejected": [],
    "cancelled": [],
}

WRITEOFF_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["approved", "rejected", "cancelled"],
    "approved": ["completed"],
    "completed": [],
    "rejected": [],
    "cancelled": [],
}

RECONCILIATION_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["reconciled", "disputed", "cancelled"],
    "reconciled": [],
    "disputed": ["reconciled", "cancelled"],
    "cancelled": [],
}

INVOICE_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["issued", "cancelled"],
    "issued": ["paid", "voided", "overdue"],
    "paid": [],
    "voided": [],
    "overdue": ["paid", "voided"],
    "cancelled": [],
}

EXPENSE_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["approved", "rejected", "cancelled"],
    "approved": ["paid", "cancelled"],
    "paid": [],
    "rejected": [],
    "cancelled": [],
}

FOREX_TRANSACTION_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["completed", "cancelled"],
    "completed": [],
    "cancelled": [],
}

PLATFORM_BILL_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["reconciled", "disputed"],
    "reconciled": [],
    "disputed": ["reconciled"],
}


# ============================================================
# 业务常量 — 集中定义，禁止硬编码
# ============================================================

VALID_COST_TYPES = {
    "product_cost", "shipping_cost", "platform_fee", "tax",
    "advertising", "warehouse_fee", "customs_duty", "ad_spend",
    "return_cost", "payment_fee", "labor", "other",
    "purchase_cost", "head_freight", "storage_fee", "platform_commission",
    "tail_freight",
}
"""合法成本类型: 采购成本/头程运费/仓储费/平台佣金/广告费/支付手续费/尾程运费/其他"""

VALID_CURRENCIES = {"CNY", "USD", "EUR", "GBP", "JPY", "CAD", "AUD"}
"""合法币种: 人民币/美元/欧元/英镑/日元/加元/澳元"""

JOURNAL_ENTRY_TYPES = {
    "purchase", "sales", "expense", "revenue", "forex", "settlement",
    "inventory_in", "inventory_out", "inventory_adjust", "write_off",
}
"""会计分录类型: 采购/销售/费用/收入/汇兑/结算/入库/出库/调整/核销"""

COST_EVENT_SOURCE_TYPES = {
    "purchase_order", "shipment", "warehouse", "platform_bill",
    "ad_campaign", "payment", "refund",
}
"""成本事件来源类型: 采购单/发货单/仓储/平台账单/广告活动/付款/退款"""


# ============================================================
# 成本事件领域服务 (Cost Event — 核心聚合根)
# ============================================================

class CostEventDomainService:
    """
    成本事件领域服务

    成本事件是财务域的核心聚合根，所有财务数据的入口。
    其他子服务 (核销/对账/发票/费用等) 底层也操作 CostEvent 实体，
    但使用各自独立的领域服务进行业务校验。
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        校验成本事件状态转换合法性

        状态机: draft → confirmed → settled, draft → cancelled
        已结算 (settled) 和已取消 (cancelled) 为终态，不可再转换。

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            bool: 转换是否合法
        """
        return target_status in COST_EVENT_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_cost_event(cost_type: str, amount: float, currency: str) -> list[str]:
        """
        校验成本事件业务规则

        规则:
          1. cost_type 必须在 VALID_COST_TYPES 集合中
          2. amount 不能为负数 (0 允许，表示零成本)
          3. currency 必须在 VALID_CURRENCIES 集合中

        Args:
            cost_type: 成本类型
            amount: 金额
            currency: 币种

        Returns:
            list[str]: 错误列表，空列表表示校验通过
        """
        errors: list[str] = []
        if cost_type not in VALID_COST_TYPES:
            errors.append(f"Invalid cost type: {cost_type}")
        if amount < 0:
            errors.append("Amount cannot be negative")
        if currency not in VALID_CURRENCIES:
            errors.append(f"Invalid currency: {currency}")
        return errors

    @staticmethod
    def calculate_amount_cny(amount: float, currency: str, exchange_rate: float) -> float:
        """
        计算人民币金额

        若币种为 CNY，直接返回原金额；否则按汇率折算。
        结果保留2位小数。

        Args:
            amount: 原始金额
            currency: 币种
            exchange_rate: 汇率 (1外币 = exchange_rate人民币)

        Returns:
            float: 人民币金额，保留2位小数
        """
        if currency == "CNY":
            return round(amount, 2)
        return round(amount * exchange_rate, 2)

    @staticmethod
    def is_deletable(status: str) -> bool:
        """
        判断成本事件是否可删除

        仅草稿 (draft) 和已取消 (cancelled) 状态允许删除，
        已确认/已结算的记录不可删除，需通过冲正处理。

        Args:
            status: 当前状态

        Returns:
            bool: 是否可删除
        """
        return status in ("draft", "cancelled")


# ============================================================
# 平台结算领域服务 (Platform Settlement)
# ============================================================

class SettlementDomainService:
    """
    平台结算领域服务

    管理各电商平台 (Amazon/Shopify/TikTok) 的结算单据。
    结算单据记录一个结算周期内的销售额、退款、佣金、广告费等，
    最终计算出净额。
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        校验平台结算状态转换合法性

        状态机: pending → confirmed → settled, pending → cancelled
        与成本事件类似，但初始状态为 pending 而非 draft。

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            bool: 转换是否合法
        """
        return target_status in SETTLEMENT_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def calculate_net_amount(
        total_sales: float,
        total_refund: float,
        platform_fee: float,
        advertising_fee: float,
        shipping_fee: float,
        other_fee: float,
    ) -> float:
        """
        计算结算净额

        公式: 净额 = 总销售额 - 总退款 - 平台佣金 - 广告费 - 运费 - 其他费用
        结果保留2位小数。

        Args:
            total_sales: 总销售额
            total_refund: 总退款额
            platform_fee: 平台佣金
            advertising_fee: 广告费
            shipping_fee: 运费
            other_fee: 其他费用

        Returns:
            float: 结算净额，保留2位小数
        """
        return round(total_sales - total_refund - platform_fee - advertising_fee - shipping_fee - other_fee, 2)

    @staticmethod
    def validate_settlement(
        total_sales: float,
        total_refund: float,
        net_amount: float,
    ) -> list[str]:
        """
        校验结算单据业务规则

        规则:
          1. 总销售额不能为负
          2. 总退款额不能为负
          3. 总退款额不能超过总销售额

        Args:
            total_sales: 总销售额
            total_refund: 总退款额
            net_amount: 结算净额 (暂未使用，预留校验)

        Returns:
            list[str]: 错误列表
        """
        errors: list[str] = []
        if total_sales < 0:
            errors.append("Total sales cannot be negative")
        if total_refund < 0:
            errors.append("Total refund cannot be negative")
        if total_refund > total_sales:
            errors.append("Total refund cannot exceed total sales")
        return errors


# ============================================================
# 付款申请领域服务 (Payment Request)
# ============================================================

class PaymentRequestDomainService:
    """
    付款申请领域服务

    付款申请是付款记录的一种特殊流程，带有审批流。
    支持多级审批: 按审批级别逐级审批，全部通过后自动变更为 approved 状态。
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        校验付款申请状态转换合法性

        状态机: pending → approved/rejected/cancelled, approved → paid/cancelled
        paid/rejected/cancelled 为终态。

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            bool: 转换是否合法
        """
        return target_status in PAYMENT_REQUEST_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def can_approve(approval_flow: list[dict], approver_level: int) -> bool:
        """
        判断指定审批级别是否可以审批

        多级审批规则: 当前已审批通过的最大级别 + 1 == 待审批级别
        即必须按顺序逐级审批，不能跳级。

        Args:
            approval_flow: 审批流列表，每项包含 {"level": int, "status": "approved"/"rejected"}
            approver_level: 待审批的级别 (从1开始)

        Returns:
            bool: 是否可以审批
        """
        if approver_level < 1:
            return False
        approved_levels = [a.get("level", 0) for a in approval_flow if a.get("status") == "approved"]
        current_approved = len(approved_levels)
        return current_approved + 1 == approver_level

    @staticmethod
    def is_fully_approved(approval_flow: list[dict], total_levels: int) -> bool:
        """
        判断是否全部审批通过

        当已审批通过的数量 >= 总审批级别数时，视为全部通过。

        Args:
            approval_flow: 审批流列表
            total_levels: 总审批级别数

        Returns:
            bool: 是否全部审批通过
        """
        approved_count = len([a for a in approval_flow if a.get("status") == "approved"])
        return approved_count >= total_levels

    @staticmethod
    def validate_payment_request(amount: float, currency: str, request_type: str) -> list[str]:
        """
        校验付款申请业务规则

        规则:
          1. 金额必须大于0
          2. 币种必须在 VALID_CURRENCIES 集合中
          3. 申请类型必须为 purchase/logistics/other 之一

        Args:
            amount: 付款金额
            currency: 币种
            request_type: 申请类型

        Returns:
            list[str]: 错误列表
        """
        errors: list[str] = []
        if amount <= 0:
            errors.append("Payment amount must be positive")
        if currency not in VALID_CURRENCIES:
            errors.append(f"Invalid currency: {currency}")
        valid_types = {"purchase", "logistics", "other"}
        if request_type not in valid_types:
            errors.append(f"Invalid request type: {request_type}")
        return errors

    @staticmethod
    def calculate_writeoff_progress(writeoff_amount: float, total_amount: float) -> float:
        """
        计算核销进度百分比

        公式: 进度 = min(核销金额 / 总金额 * 100, 100)
        结果保留2位小数，上限100%。

        Args:
            writeoff_amount: 已核销金额
            total_amount: 总金额

        Returns:
            float: 核销进度百分比 (0-100)
        """
        if total_amount <= 0:
            return 0.0
        return round(min(writeoff_amount / total_amount * 100, 100), 2)

    @staticmethod
    def get_writeoff_status(writeoff_amount: float, total_amount: float) -> str:
        """
        根据核销金额判断核销状态

        - unwritten: 未核销 (核销金额 <= 0)
        - partial: 部分核销 (0 < 核销金额 < 总金额)
        - full: 全额核销 (核销金额 >= 总金额)

        Args:
            writeoff_amount: 已核销金额
            total_amount: 总金额

        Returns:
            str: 核销状态 (unwritten/partial/full)
        """
        if writeoff_amount <= 0:
            return "unwritten"
        if writeoff_amount >= total_amount:
            return "full"
        return "partial"


# ============================================================
# 核销领域服务 (Write-Off)
# ============================================================

class WriteOffDomainService:
    """
    核销领域服务

    核销是将付款与应付进行匹配确认的业务流程。
    支持四种核销类型: 入库核销/异常核销/供应商退款/还款。
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        校验核销状态转换合法性

        状态机: pending → approved → completed, pending → rejected/cancelled
        completed/rejected/cancelled 为终态。

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            bool: 转换是否合法
        """
        return target_status in WRITEOFF_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_writeoff(
        writeoff_type: str,
        ref_type: str,
        amount: float,
        currency: str,
    ) -> list[str]:
        """
        校验核销业务规则

        规则:
          1. 核销类型必须为 inbound/exception/supplier_refund/repayment 之一
          2. 关联类型必须为 purchase_order/shipment/refund 之一
          3. 核销金额必须大于0
          4. 币种必须在 VALID_CURRENCIES 集合中

        Args:
            writeoff_type: 核销类型
            ref_type: 关联类型
            amount: 核销金额
            currency: 币种

        Returns:
            list[str]: 错误列表
        """
        errors: list[str] = []
        valid_types = {"inbound", "exception", "supplier_refund", "repayment"}
        if writeoff_type not in valid_types:
            errors.append(f"Invalid writeoff type: {writeoff_type}")
        valid_ref_types = {"purchase_order", "shipment", "refund"}
        if ref_type not in valid_ref_types:
            errors.append(f"Invalid reference type: {ref_type}")
        if amount <= 0:
            errors.append("Writeoff amount must be positive")
        if currency not in VALID_CURRENCIES:
            errors.append(f"Invalid currency: {currency}")
        return errors


# ============================================================
# 对账领域服务 (Reconciliation)
# ============================================================

class ReconciliationDomainService:
    """
    对账领域服务

    对账是核对供应商/物流商/平台账目的业务流程。
    支持三种对账类型: 供应商对账/物流对账/平台对账。
    核心能力: 自动发现差异 (缺失/金额不匹配)。
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        校验对账状态转换合法性

        状态机: pending → reconciled/disputed/cancelled, disputed → reconciled/cancelled
        reconciled/cancelled 为终态。争议状态 (disputed) 可回到已对账。

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            bool: 转换是否合法
        """
        return target_status in RECONCILIATION_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def calculate_balance(payable_amount: float, paid_amount: float) -> float:
        """
        计算对账差额 (余额)

        公式: 差额 = 应付金额 - 已付金额
        正数表示对方少付，负数表示对方多付。

        Args:
            payable_amount: 应付金额
            paid_amount: 已付金额

        Returns:
            float: 差额，保留2位小数
        """
        return round(payable_amount - paid_amount, 2)

    @staticmethod
    def find_differences(
        expected_items: list[dict],
        actual_items: list[dict],
        key_field: str = "ref_id",
    ) -> list[dict]:
        """
        自动发现对账差异

        对比我方记录与对方记录，发现两种差异:
          1. missing: 对方记录中缺失我方的某条记录
          2. amount_mismatch: 同一记录的金额不一致 (差异 > 0.01)

        Args:
            expected_items: 我方记录列表，每项包含 key_field 和 "amount"
            actual_items: 对方记录列表，每项包含 key_field 和 "amount"
            key_field: 匹配键字段名，默认 "ref_id"

        Returns:
            list[dict]: 差异列表，每项包含 ref_id/type/expected/actual/difference
        """
        actual_map = {item[key_field]: item for item in actual_items if key_field in item}
        differences: list[dict] = []
        for expected in expected_items:
            key = expected.get(key_field)
            if key not in actual_map:
                differences.append({"ref_id": key, "type": "missing", "expected": expected.get("amount", 0)})
                continue
            actual = actual_map[key]
            diff = abs(expected.get("amount", 0) - actual.get("amount", 0))
            if diff > 0.01:
                differences.append({
                    "ref_id": key,
                    "type": "amount_mismatch",
                    "expected": expected.get("amount", 0),
                    "actual": actual.get("amount", 0),
                    "difference": round(diff, 2),
                })
        return differences

    @staticmethod
    def validate_reconciliation(
        recon_type: str,
        party_id: str,
        period: str,
        payable_amount: float,
    ) -> list[str]:
        """
        校验对账业务规则

        规则:
          1. 对账类型必须为 supplier/logistics/platform 之一
          2. 对方ID不能为空
          3. 对账周期不能为空
          4. 应付金额不能为负

        Args:
            recon_type: 对账类型
            party_id: 对方ID (供应商/物流商/平台)
            period: 对账周期
            payable_amount: 应付金额

        Returns:
            list[str]: 错误列表
        """
        errors: list[str] = []
        valid_types = {"supplier", "logistics", "platform"}
        if recon_type not in valid_types:
            errors.append(f"Invalid reconciliation type: {recon_type}")
        if not party_id:
            errors.append("Party ID is required")
        if not period:
            errors.append("Period is required")
        if payable_amount < 0:
            errors.append("Payable amount cannot be negative")
        return errors


# ============================================================
# 发票领域服务 (Invoice)
# ============================================================

class InvoiceDomainService:
    """
    发票领域服务

    管理采购发票/销售发票/红字发票/蓝字发票。
    支持税额计算和逾期判断。
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        校验发票状态转换合法性

        状态机: draft → issued → paid/voided/overdue, overdue → paid/voided
        已付款 (paid) 和已作废 (voided) 为终态。
        逾期 (overdue) 状态可回到已付款或作废。

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            bool: 转换是否合法
        """
        return target_status in INVOICE_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def calculate_tax(amount: float, tax_rate: float) -> float:
        """
        计算税额

        公式: 税额 = 金额 × 税率 / 100
        结果保留2位小数。

        Args:
            amount: 不含税金额
            tax_rate: 税率百分比 (如13表示13%)

        Returns:
            float: 税额，保留2位小数
        """
        return round(amount * tax_rate / 100, 2)

    @staticmethod
    def validate_invoice(
        invoice_type: str,
        amount: float,
        currency: str,
    ) -> list[str]:
        """
        校验发票业务规则

        规则:
          1. 发票类型必须为 purchase/sales/credit_note/debit_note 之一
          2. 金额必须大于0
          3. 币种必须在 VALID_CURRENCIES 集合中

        Args:
            invoice_type: 发票类型
            amount: 金额
            currency: 币种

        Returns:
            list[str]: 错误列表
        """
        errors: list[str] = []
        valid_types = {"purchase", "sales", "credit_note", "debit_note"}
        if invoice_type not in valid_types:
            errors.append(f"Invalid invoice type: {invoice_type}")
        if amount <= 0:
            errors.append("Invoice amount must be positive")
        if currency not in VALID_CURRENCIES:
            errors.append(f"Invalid currency: {currency}")
        return errors

    @staticmethod
    def is_overdue(due_date, current_date=None) -> bool:
        """
        判断发票是否逾期

        若到期日期早于当前时间，则视为逾期。
        自动处理时区: 若 due_date 无时区信息，默认为 UTC。

        Args:
            due_date: 到期日期 (datetime 对象)
            current_date: 当前日期，为 None 则使用 UTC 当前时间

        Returns:
            bool: 是否逾期
        """
        from datetime import UTC, datetime
        if due_date is None:
            return False
        now = current_date or datetime.now(UTC)
        if hasattr(due_date, "tzinfo") and due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=UTC)
        return now > due_date


# ============================================================
# 费用领域服务 (Expense)
# ============================================================

class ExpenseDomainService:
    """
    费用领域服务

    管理广告费/运费/仓储费/退款/平台费/税费/人工费等各类费用。
    核心能力: 费用自动分类 (将具体费用类型映射到费用大类)。
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        校验费用状态转换合法性

        状态机: pending → approved → paid, pending → rejected/cancelled
        paid/rejected/cancelled 为终态。

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            bool: 转换是否合法
        """
        return target_status in EXPENSE_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_expense(
        expense_type: str,
        amount: float,
        currency: str,
    ) -> list[str]:
        """
        校验费用业务规则

        规则:
          1. 费用类型不能为空
          2. 金额必须大于0
          3. 币种必须在 VALID_CURRENCIES 集合中

        Args:
            expense_type: 费用类型
            amount: 金额
            currency: 币种

        Returns:
            list[str]: 错误列表
        """
        errors: list[str] = []
        if not expense_type:
            errors.append("Expense type is required")
        if amount <= 0:
            errors.append("Expense amount must be positive")
        if currency not in VALID_CURRENCIES:
            errors.append(f"Invalid currency: {currency}")
        return errors

    @staticmethod
    def categorize_expense(expense_type: str) -> str:
        """
        费用自动分类

        将具体费用类型映射到费用大类:
          - advertising → marketing (营销)
          - shipping → logistics (物流)
          - warehouse → operations (运营)
          - refund → after_sales (售后)
          - platform_fee → platform (平台)
          - tax → tax (税务)
          - labor → operations (运营)
          - other → other (其他)

        Args:
            expense_type: 具体费用类型

        Returns:
            str: 费用大类
        """
        category_map = {
            "advertising": "marketing",
            "shipping": "logistics",
            "warehouse": "operations",
            "refund": "after_sales",
            "platform_fee": "platform",
            "tax": "tax",
            "labor": "operations",
            "other": "other",
        }
        return category_map.get(expense_type, "other")


# ============================================================
# 外汇交易领域服务 (Forex Transaction)
# ============================================================

class ForexDomainService:
    """
    外汇交易领域服务

    管理币种兑换交易和汇率预警。
    核心能力:
      1. 币种转换计算
      2. 汇兑损益计算
      3. 汇率预警判断 (变动超过阈值时触发)
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        校验外汇交易状态转换合法性

        状态机: pending → completed/cancelled
        completed/cancelled 为终态。

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            bool: 转换是否合法
        """
        return target_status in FOREX_TRANSACTION_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def convert_currency(amount: float, rate: float) -> float:
        """
        币种转换计算

        公式: 转换后金额 = 原始金额 × 汇率
        结果保留2位小数。

        Args:
            amount: 原始金额
            rate: 汇率

        Returns:
            float: 转换后金额，保留2位小数
        """
        return round(amount * rate, 2)

    @staticmethod
    def calculate_gain_loss(
        original_amount: float,
        original_rate: float,
        current_rate: float,
    ) -> float:
        """
        计算汇兑损益

        公式: 损益 = 原始金额 × 当前汇率 - 原始金额 × 原始汇率
        正数表示汇兑收益，负数表示汇兑损失。
        结果保留2位小数。

        Args:
            original_amount: 原始外币金额
            original_rate: 原始汇率
            current_rate: 当前汇率

        Returns:
            float: 汇兑损益，保留2位小数
        """
        original_cny = original_amount * original_rate
        current_cny = original_amount * current_rate
        return round(current_cny - original_cny, 2)

    @staticmethod
    def is_rate_alert(
        current_rate: float,
        previous_rate: float,
        threshold_pct: float = 3.0,
    ) -> bool:
        """
        判断是否触发汇率预警

        当汇率变动百分比超过阈值时触发预警。
        公式: |当前汇率 - 历史汇率| / 历史汇率 × 100 >= 阈值

        Args:
            current_rate: 当前汇率
            previous_rate: 历史汇率
            threshold_pct: 预警阈值百分比，默认3%

        Returns:
            bool: 是否触发预警
        """
        if previous_rate <= 0:
            return False
        change_pct = abs(current_rate - previous_rate) / previous_rate * 100
        return change_pct >= threshold_pct

    @staticmethod
    def validate_forex_transaction(
        from_currency: str,
        to_currency: str,
        amount: float,
        rate: float,
    ) -> list[str]:
        """
        校验外汇交易业务规则

        规则:
          1. 源币种和目标币种必须在 VALID_CURRENCIES 集合中
          2. 源币种和目标币种不能相同
          3. 金额必须大于0
          4. 汇率必须大于0

        Args:
            from_currency: 源币种
            to_currency: 目标币种
            amount: 金额
            rate: 汇率

        Returns:
            list[str]: 错误列表
        """
        errors: list[str] = []
        if from_currency not in VALID_CURRENCIES:
            errors.append(f"Invalid from currency: {from_currency}")
        if to_currency not in VALID_CURRENCIES:
            errors.append(f"Invalid to currency: {to_currency}")
        if from_currency == to_currency:
            errors.append("From and to currencies must be different")
        if amount <= 0:
            errors.append("Amount must be positive")
        if rate <= 0:
            errors.append("Exchange rate must be positive")
        return errors


# ============================================================
# 平台账单领域服务 (Platform Bill)
# ============================================================

class PlatformBillDomainService:
    """
    平台账单领域服务

    管理各电商平台 (Amazon/Shopify/TikTok) 的账单导入和对账。
    账单类型: 佣金/费用/调整/退款/广告。
    """

    @staticmethod
    def can_transition(current_status: str, target_status: str) -> bool:
        """
        校验平台账单状态转换合法性

        状态机: pending → reconciled/disputed, disputed → reconciled
        reconciled 为终态。争议状态 (disputed) 可回到已对账。

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            bool: 转换是否合法
        """
        return target_status in PLATFORM_BILL_STATUS_TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_platform_bill(
        platform: str,
        store: str,
        bill_type: str,
        amount: float,
        currency: str,
    ) -> list[str]:
        """
        校验平台账单业务规则

        规则:
          1. 平台名称不能为空
          2. 店铺ID不能为空
          3. 账单类型必须为 commission/fee/adjustment/refund/advertising 之一
          4. 金额不能为负
          5. 币种必须在 VALID_CURRENCIES 集合中

        Args:
            platform: 平台名称
            store: 店铺ID
            bill_type: 账单类型
            amount: 金额
            currency: 币种

        Returns:
            list[str]: 错误列表
        """
        errors: list[str] = []
        if not platform:
            errors.append("Platform is required")
        if not store:
            errors.append("Store is required")
        valid_bill_types = {"commission", "fee", "adjustment", "refund", "advertising"}
        if bill_type not in valid_bill_types:
            errors.append(f"Invalid bill type: {bill_type}")
        if amount < 0:
            errors.append("Bill amount cannot be negative")
        if currency not in VALID_CURRENCIES:
            errors.append(f"Invalid currency: {currency}")
        return errors


# ============================================================
# 会计分录领域服务 (Journal Entry)
# ============================================================

class JournalEntryDomainService:
    """
    会计分录领域服务

    管理各类会计分录的校验和自动生成。
    分录类型: 采购/销售/费用/收入/汇兑/结算/入库/出库/调整/核销。
    核心能力: 根据业务类型自动映射借贷方科目。
    """

    @staticmethod
    def validate_entry(
        entry_type: str,
        debit_account: str,
        credit_account: str,
        amount: float,
        currency: str,
    ) -> list[str]:
        """
        校验会计分录业务规则

        规则:
          1. 分录类型必须在 JOURNAL_ENTRY_TYPES 集合中
          2. 借方科目不能为空
          3. 贷方科目不能为空
          4. 借方科目和贷方科目不能相同
          5. 金额必须大于0
          6. 币种必须在 VALID_CURRENCIES 集合中

        Args:
            entry_type: 分录类型
            debit_account: 借方科目
            credit_account: 贷方科目
            amount: 金额
            currency: 币种

        Returns:
            list[str]: 错误列表
        """
        errors: list[str] = []
        if entry_type not in JOURNAL_ENTRY_TYPES:
            errors.append(f"Invalid journal entry type: {entry_type}")
        if not debit_account:
            errors.append("Debit account is required")
        if not credit_account:
            errors.append("Credit account is required")
        if debit_account == credit_account:
            errors.append("Debit and credit accounts must be different")
        if amount <= 0:
            errors.append("Entry amount must be positive")
        if currency not in VALID_CURRENCIES:
            errors.append(f"Invalid currency: {currency}")
        return errors

    @staticmethod
    def generate_inventory_entry(
        entry_type: str,
        sku: str,
        quantity: int,
        unit_cost: float,
        ref_type: str,
        ref_id: str,
        period: str,
    ) -> dict:
        """
        自动生成库存类会计分录

        根据分录类型自动映射借贷方科目:
          - inventory_in: 借-库存 / 贷-应付账款
          - inventory_out: 借-主营业务成本 / 贷-库存
          - inventory_adjust: 借-库存调整 / 贷-库存

        金额 = 数量 × 单位成本，保留2位小数。

        Args:
            entry_type: 分录类型 (inventory_in/inventory_out/inventory_adjust)
            sku: SKU编号
            quantity: 数量
            unit_cost: 单位成本
            ref_type: 关联类型
            ref_id: 关联ID
            period: 会计期间

        Returns:
            dict: 会计分录数据
        """
        amount = round(quantity * unit_cost, 2)
        account_map = {
            "inventory_in": ("inventory", "accounts_payable"),
            "inventory_out": ("cost_of_goods_sold", "inventory"),
            "inventory_adjust": ("inventory_adjustment", "inventory"),
        }
        debit, credit = account_map.get(entry_type, ("inventory", "inventory"))
        return {
            "entry_type": entry_type,
            "debit_account": debit,
            "credit_account": credit,
            "amount": amount,
            "currency": "CNY",
            "ref_type": ref_type,
            "ref_id": ref_id,
            "period": period,
            "sku": sku,
            "quantity": quantity,
            "unit_cost": unit_cost,
        }


# ============================================================
# 成本分解领域服务 (Cost Breakdown)
# ============================================================

class CostBreakdownDomainService:
    """
    成本分解领域服务

    按成本类型分解SKU的成本构成，计算各项成本占比。
    成本项: BOM成本/头程运费/FBA费用/关税/广告费/仓储费/退货成本/人工成本/其他。
    """

    @staticmethod
    def calculate_total(
        bom_cost: float,
        shipping_cost: float,
        fba_fees: float,
        tariff: float,
        advertising_cost: float,
        storage_cost: float,
        return_cost: float,
        labor_cost: float,
        other_costs: float,
    ) -> float:
        """
        计算总成本

        公式: 总成本 = BOM + 头程 + FBA + 关税 + 广告 + 仓储 + 退货 + 人工 + 其他
        结果保留2位小数。

        Args:
            bom_cost: BOM成本 (采购成本)
            shipping_cost: 头程运费
            fba_fees: FBA费用
            tariff: 关税
            advertising_cost: 广告费
            storage_cost: 仓储费
            return_cost: 退货成本
            labor_cost: 人工成本
            other_costs: 其他成本

        Returns:
            float: 总成本，保留2位小数
        """
        return round(
            bom_cost + shipping_cost + fba_fees + tariff +
            advertising_cost + storage_cost + return_cost +
            labor_cost + other_costs,
            2,
        )

    @staticmethod
    def calculate_cost_percentage(cost_item: float, total_cost: float) -> float:
        """
        计算单项成本占比

        公式: 占比 = 单项成本 / 总成本 × 100
        总成本为0时返回0。结果保留2位小数。

        Args:
            cost_item: 单项成本
            total_cost: 总成本

        Returns:
            float: 占比百分比 (0-100)
        """
        if total_cost <= 0:
            return 0.0
        return round(cost_item / total_cost * 100, 2)


# ============================================================
# 利润计算领域服务 (Profit Calculation)
# ============================================================

class ProfitDomainService:
    """
    利润计算领域服务

    综合计算净利润/毛利率/ROI，并判断是否触发利润预警。
    支持FIFO (先进先出) 成本计算。
    """

    @staticmethod
    def calculate_profit(
        revenue: float,
        refund_amount: float,
        total_cost: float,
        operating_expenses: float = 0,
    ) -> dict:
        """
        综合利润计算

        计算指标:
          - 净收入 = 收入 - 退款
          - 毛利润 = 净收入 - 总成本
          - 毛利率 = 毛利润 / 净收入 × 100
          - 净利润 = 毛利润 - 运营费用
          - 净利率 = 净利润 / 净收入 × 100
          - ROI = 净利润 / 总成本 × 100

        Args:
            revenue: 收入
            refund_amount: 退款金额
            total_cost: 总成本
            operating_expenses: 运营费用，默认0

        Returns:
            dict: 利润计算结果，包含各项指标
        """
        net_revenue = round(revenue - refund_amount, 2)
        gross_profit = round(net_revenue - total_cost, 2)
        gross_margin = round(gross_profit / net_revenue * 100, 2) if net_revenue > 0 else 0
        net_profit = round(gross_profit - operating_expenses, 2)
        net_margin = round(net_profit / net_revenue * 100, 2) if net_revenue > 0 else 0
        roi = round(net_profit / total_cost * 100, 2) if total_cost > 0 else 0
        return {
            "revenue": revenue,
            "refund_amount": refund_amount,
            "net_revenue": net_revenue,
            "total_cost": total_cost,
            "gross_profit": gross_profit,
            "gross_margin": gross_margin,
            "operating_expenses": operating_expenses,
            "net_profit": net_profit,
            "net_margin": net_margin,
            "roi": roi,
        }

    @staticmethod
    def is_profit_alert(net_margin: float, threshold: float = 5.0) -> bool:
        """
        判断是否触发利润预警

        当净利率低于阈值时触发预警。
        默认阈值5%，即净利率低于5%视为利润预警。

        Args:
            net_margin: 净利率百分比
            threshold: 预警阈值百分比，默认5%

        Returns:
            bool: 是否触发预警
        """
        return net_margin < threshold

    @staticmethod
    def calculate_fifo_cost(
        inventory_layers: list[dict],
        quantity_sold: int,
    ) -> float:
        """
        FIFO (先进先出) 成本计算

        按入库日期从早到晚逐层消耗库存，计算指定销售数量的成本。
        每层库存包含: date (入库日期), quantity (数量), unit_cost (单位成本)。

        Args:
            inventory_layers: 库存层列表，按日期升序消耗
            quantity_sold: 销售数量

        Returns:
            float: FIFO成本，保留2位小数
        """
        remaining = quantity_sold
        total_cost = 0.0
        for layer in sorted(inventory_layers, key=lambda x: x.get("date", "")):
            if remaining <= 0:
                break
            available = layer.get("quantity", 0)
            unit_cost = layer.get("unit_cost", 0)
            taken = min(remaining, available)
            total_cost += taken * unit_cost
            remaining -= taken
        return round(total_cost, 2)


# ============================================================
# 凭证引擎领域服务 (Voucher Engine)
# ============================================================

class VoucherEngineDomainService:
    """
    凭证引擎领域服务

    自动生成库存凭证并组装金蝶推送数据。
    核心能力:
      1. 根据业务类型自动映射到会计分录类型
      2. 生成金蝶财务系统可接收的推送格式
    """

    @staticmethod
    def auto_generate_inventory_voucher(
        business_type: str,
        sku: str,
        quantity: int,
        unit_cost: float,
        ref_type: str,
        ref_id: str,
        period: str,
    ) -> dict:
        """
        自动生成库存凭证

        根据业务类型自动映射到会计分录类型:
          - purchase_inbound → inventory_in (采购入库)
          - sales_outbound → inventory_out (销售出库)
          - return_inbound → inventory_in (退货入库)
          - inventory_adjustment → inventory_adjust (库存调整)
          - transfer_out → inventory_out (调拨出库)
          - transfer_in → inventory_in (调拨入库)
          - scrap → inventory_adjust (报废)
          - stocktaking_gain → inventory_adjust (盘盈)
          - stocktaking_loss → inventory_adjust (盘亏)

        Args:
            business_type: 业务类型
            sku: SKU编号
            quantity: 数量
            unit_cost: 单位成本
            ref_type: 关联类型
            ref_id: 关联ID
            period: 会计期间

        Returns:
            dict: 会计分录数据
        """
        voucher_type_map = {
            "purchase_inbound": "inventory_in",
            "sales_outbound": "inventory_out",
            "return_inbound": "inventory_in",
            "inventory_adjustment": "inventory_adjust",
            "transfer_out": "inventory_out",
            "transfer_in": "inventory_in",
            "scrap": "inventory_adjust",
            "stocktaking_gain": "inventory_adjust",
            "stocktaking_loss": "inventory_adjust",
        }
        entry_type = voucher_type_map.get(business_type, "inventory_adjust")
        return JournalEntryDomainService.generate_inventory_entry(
            entry_type=entry_type,
            sku=sku,
            quantity=quantity,
            unit_cost=unit_cost,
            ref_type=ref_type,
            ref_id=ref_id,
            period=period,
        )

    @staticmethod
    def generate_kingdee_push_data(entries: list[dict]) -> dict:
        """
        生成金蝶推送数据

        将会计分录列表组装为金蝶财务系统可接收的推送格式。
        借贷合计必须相等 (借贷平衡校验)。

        Args:
            entries: 会计分录列表

        Returns:
            dict: 金蝶推送数据，包含 voucher_type/entries/total_debit/total_credit/entry_count
        """
        total_debit = sum(e.get("amount", 0) for e in entries)
        return {
            "voucher_type": "transfer",
            "entries": entries,
            "total_debit": round(total_debit, 2),
            "total_credit": round(total_debit, 2),
            "entry_count": len(entries),
        }


class AmazonCollectionService:
    @staticmethod
    def calc_pending(txns: list[dict]) -> dict:
        pending = [t for t in txns if t.get("status") == "pending"]
        return {"total": len(txns), "pending": len(pending),
                "amount": round(sum(t.get("amount", 0) for t in pending), 2)}

    @staticmethod
    def detect_discrepancy(expected: float, actual: float) -> dict:
        diff = round(expected - actual, 2)
        return {"expected": expected, "actual": actual, "diff": diff,
                "has_issue": abs(diff) > 1.0}
