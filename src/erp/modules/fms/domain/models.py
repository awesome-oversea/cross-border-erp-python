"""
FMS域 - 财务管理域 ORM模型

本模块定义了财务管理域的所有数据库实体映射，包含:
- CostEvent: 成本事件表，8类成本归集(采购/运费/平台费/广告/仓储/其他)
- PlatformSettlement: 平台结算表，平台账单对账与利润核算
- PaymentRecord: 付款记录表，供应商付款/平台打款/退款付款
- ExchangeRate: 汇率表，多币种转换与汇率矩阵

技术栈: SQLAlchemy 2.x + async + PostgreSQL
主键策略: UUID由应用层生成
多租户: 所有业务表包含tenant_id字段实现隔离
成本模型: 8类成本事件归集，自动换算人民币(amount_cny)
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base


class CostEvent(Base):
    """成本事件表 - 8类成本归集(采购/运费/平台费/广告/仓储/其他)，自动换算人民币"""
    __tablename__ = "cost_event"
    __table_args__ = {"schema": "fms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    event_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="成本事件编号，租户内唯一")
    cost_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="成本类型: purchase采购/shipping运费/platform_fee平台费/advertising广告/warehouse仓储/other其他")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="原币金额")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY", comment="原币币种")
    exchange_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, comment="汇率，原币→人民币")
    amount_cny: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="人民币金额，amount*exchange_rate")
    sku_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="关联SKU ID，可空(非SKU级成本)")
    order_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="关联订单ID，可空")
    shipment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="关联发货单ID，可空")
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="关联单据类型，如purchase_order/platform_bill等")
    reference_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="关联单据ID")
    occurred_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="成本发生日期")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmed", index=True, comment="状态: draft草稿/confirmed已确认/cancelled已取消")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="备注")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class PlatformSettlement(Base):
    """平台结算表 - 平台账单对账与利润核算，含销售/退款/平台费/广告费"""
    __tablename__ = "platform_settlement"
    __table_args__ = {"schema": "fms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    settlement_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="结算单号，租户内唯一")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="平台标识: amazon/shopee/lazada等")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="店铺ID")
    settlement_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="结算周期开始日期")
    settlement_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="结算周期结束日期")
    total_sales: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="销售总额")
    total_refund: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="退款总额")
    platform_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="平台佣金")
    advertising_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="广告费")
    shipping_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="运费")
    other_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="其他费用")
    net_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="净结算金额")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD", comment="币种")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True, comment="状态: pending待对账/reconciling对账中/reconciled已对账/disputed有争议")
    raw_data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="平台原始数据JSON，含账单明细等")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class PaymentRecord(Base):
    """付款记录表 - 供应商付款/平台打款/退款付款，关联审批流程"""
    __tablename__ = "payment_record"
    __table_args__ = {"schema": "fms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    payment_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="付款单号，租户内唯一")
    payment_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="付款类型: supplier_payment供应商付款/platform_payout平台打款/refund_payment退款付款/other其他")
    counterparty_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="对手方ID，如供应商ID/平台账户ID")
    counterparty_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="对手方名称(冗余)")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="付款金额")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY", comment="币种")
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False, default="bank_transfer", comment="付款方式: bank_transfer银行转账/online_payment在线支付/check支票/other其他")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True, comment="状态: pending待付款/approved已审批/paid已付款/failed失败/cancelled已取消")
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="关联单据类型，如purchase_order/refund_order等")
    reference_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="关联单据ID")
    approval_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="审批流程实例ID")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="实际付款时间")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="备注")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class ExchangeRate(Base):
    """汇率表 - 多币种转换与汇率矩阵，支持手动/自动更新"""
    __tablename__ = "exchange_rate"
    __table_args__ = {"schema": "fms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    from_currency: Mapped[str] = mapped_column(String(10), nullable=False, comment="源币种，如USD/EUR/GBP等")
    to_currency: Mapped[str] = mapped_column(String(10), nullable=False, comment="目标币种，通常为CNY")
    rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, comment="汇率值，1源币种=rate目标币种")
    rate_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True, comment="汇率日期")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual", comment="来源: manual手动/api自动/central_bank央行")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
