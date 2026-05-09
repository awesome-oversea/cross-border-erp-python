from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import TenantModel


class ContentReviewTask(TenantModel):
    __tablename__ = "content_review_task"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="listing/image/description/review")
    content_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    content_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", comment="pending/auto_approved/auto_rejected/manual_review/approved/rejected")
    auto_result: Mapped[str] = mapped_column(String(20), nullable=False, default="", comment="pass/flag/reject")
    auto_reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    reviewer_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    review_comment: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    reviewed_at: Mapped[str] = mapped_column(String(30), nullable=False, default="")


class ForexRate(TenantModel):
    __tablename__ = "forex_rate"
    __table_args__ = {"schema": "fms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    base_currency: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    target_currency: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="ecb", comment="ecb/cbc/manual")
    rate_date: Mapped[str] = mapped_column(String(20), nullable=False, index=True)


class PaymentRecord(TenantModel):
    __tablename__ = "payment_record"
    __table_args__ = {"schema": "fms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    order_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False, comment="stripe/paypal/alipay/wechat/transfer")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", comment="pending/success/failed/refunded")
    channel_transaction_id: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    refund_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    refund_reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")


class OrderStrategyRule(TenantModel):
    __tablename__ = "order_strategy_rule"
    __table_args__ = {"schema": "oms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="risk_check/warehouse_assign/logistics_select/auto_approve")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conditions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    actions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LogisticsStrategyRule(TenantModel):
    __tablename__ = "logistics_strategy_rule"
    __table_args__ = {"schema": "tms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="carrier_select/rate_calc/priority_score")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conditions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    actions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BillingRule(TenantModel):
    __tablename__ = "billing_rule"
    __table_args__ = {"schema": "fms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    billing_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="fixed/percentage/tiered")
    base_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tiers_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CdpCustomerProfile(TenantModel):
    __tablename__ = "cdp_customer_profile"
    __table_args__ = {"schema": "crm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    segment: Mapped[str] = mapped_column(String(30), nullable=False, default="normal", comment="vip/high_value/normal/new/churned")
    total_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_revenue: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_order_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_order_date: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    attributes_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class CdpBehaviorEvent(TenantModel):
    __tablename__ = "cdp_behavior_event"
    __table_args__ = {"schema": "crm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="page_view/add_to_cart/purchase/review/return")
    event_data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    occurred_at: Mapped[str] = mapped_column(String(30), nullable=False, default="")


class InvoiceRecord(TenantModel):
    __tablename__ = "invoice_record"
    __table_args__ = {"schema": "fms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    invoice_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="sales_invoice/purchase_invoice/credit_note")
    order_id: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tax_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tax_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", comment="draft/issued/paid/cancelled")
    issue_date: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    due_date: Mapped[str] = mapped_column(String(20), nullable=False, default="")


class ComplianceCheck(TenantModel):
    __tablename__ = "compliance_check"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    check_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    check_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="product_compliance/trade_compliance/data_privacy/tax_compliance")
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", comment="pending/passed/failed/review")
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    violations_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    checked_at: Mapped[str] = mapped_column(String(30), nullable=False, default="")


class SelectionAnalysis(TenantModel):
    __tablename__ = "selection_analysis"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    market: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    demand_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    competition_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    profit_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trend_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recommendation: Mapped[str] = mapped_column(String(20), nullable=False, default="neutral", comment="strong_buy/buy/neutral/avoid")
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class AdOptimizationSuggestion(TenantModel):
    __tablename__ = "ad_optimization_suggestion"
    __table_args__ = {"schema": "ads"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    suggestion_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    campaign_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    suggestion_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="bid_adjust/budget_reallocate/keyword_add/keyword_pause")
    current_value: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    suggested_value: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", comment="pending/applied/dismissed")


class CostEventRecord(TenantModel):
    __tablename__ = "cost_event_record"
    __table_args__ = {"schema": "fms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    cost_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="purchase/head_freight/warehouse/platform_commission/advertising/payment_fee/last_mile/other")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    order_id: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    reference_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    occurred_date: Mapped[str] = mapped_column(String(20), nullable=False, default="")


class ProfitSettlement(TenantModel):
    __tablename__ = "profit_settlement"
    __table_args__ = {"schema": "fms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    settlement_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    revenue: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    purchase_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    head_freight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    platform_commission: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    advertising_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payment_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    other_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gross_profit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    operating_profit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    period: Mapped[str] = mapped_column(String(20), nullable=False, default="")


class InventoryVoucher(TenantModel):
    __tablename__ = "inventory_voucher"
    __table_args__ = {"schema": "wms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    voucher_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    voucher_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="purchase_in/sales_out/transfer_in/transfer_out/adjustment_in/adjustment_out/return_in/return_out")
    direction: Mapped[str] = mapped_column(String(10), nullable=False, default="in", comment="in/out")
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    reference_id: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    lines_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", comment="draft/posted/cancelled")
    operator_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    posted_at: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    cancelled_at: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    cancel_reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
