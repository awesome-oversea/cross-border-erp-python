"""
OMS域 - 订单管理域 ORM模型

本模块定义了订单管理域的所有数据库实体映射，包含:
- SalesOrder: 销售订单表，订单四层模型(pending→confirmed→shipped→completed)
- SalesOrderItem: 订单明细表，SKU级别的订单行项
- RefundOrder: 退款单表，仅退款/退货退款/换货三种类型
- Promotion: 促销活动表，折扣/赠品/捆绑/秒杀/优惠券
- OrderSplitRule: 拆单规则表，按仓库/平台/重量/SKU拆分
- OrderAuditLog: 订单审计日志表，全状态变更留痕

技术栈: SQLAlchemy 2.x + async + PostgreSQL
主键策略: UUID由应用层生成
多租户: 所有业务表包含tenant_id字段实现隔离
软删除: deleted_at字段，非物理删除
订单模型: 四层状态机 pending→confirmed→shipped→completed
拆合单: is_split/parent_order_id支持拆单，is_merged/merged_into_id支持合单
风控: risk_flags_json记录风险标记
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base


class SalesOrder(Base):
    """销售订单表 - 订单四层模型核心实体，支持拆合单与风控标记"""
    __tablename__ = "sales_order"
    __table_args__ = {"schema": "oms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    order_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="订单编号，系统生成唯一")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="销售平台: amazon/shopify/ebay/...")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="店铺ID")
    platform_order_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", index=True, comment="平台原始订单ID")
    order_type: Mapped[str] = mapped_column(String(30), nullable=False, default="standard", comment="订单类型: standard/refund/exchange")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True, comment="订单状态: pending/confirmed/shipped/completed/cancelled")
    order_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="下单时间")
    pay_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="支付时间")
    ship_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="发货时间")
    complete_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="完成时间")
    buyer_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="买家ID")
    buyer_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="买家姓名")
    recipient_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="收件人姓名")
    recipient_phone: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="收件人电话")
    recipient_address: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="收件人地址")
    recipient_city: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="收件人城市")
    recipient_state: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="收件人州/省")
    recipient_country: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="收件人国家")
    recipient_zip: Mapped[str] = mapped_column(String(30), nullable=False, default="", comment="收件人邮编")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD", comment="币种")
    item_subtotal: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="商品小计")
    shipping_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="运费")
    discount_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="优惠金额")
    tax_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="税费")
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="订单总额")
    settlement_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="结算金额")
    warehouse_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="分配仓库ID")
    logistics_channel: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="物流渠道")
    tracking_no: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="物流追踪号")
    is_split: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否拆单")
    parent_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="拆单父订单ID")
    is_merged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否合单")
    merged_into_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="合单目标订单ID")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="备注")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="标签列表JSON")
    risk_flags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="风险标记JSON")
    raw_data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="平台原始数据JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class SalesOrderItem(Base):
    """订单明细表 - SKU级别的订单行项，记录商品、数量、价格"""
    __tablename__ = "sales_order_item"
    __table_args__ = {"schema": "oms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="所属订单ID")
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="SKU ID")
    channel_sku: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="渠道SKU编码")
    product_name: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="商品名称")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="数量")
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="单价")
    discount_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="优惠金额")
    item_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="行项总额")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", comment="行项状态: pending/shipped/refunded/cancelled")
    platform_item_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="平台行项ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")


class RefundOrder(Base):
    """退款单表 - 仅退款/退货退款/换货三种类型，关联审批流程"""
    __tablename__ = "refund_order"
    __table_args__ = {"schema": "oms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    refund_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="退款单号，系统生成唯一")
    original_order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="原订单ID")
    refund_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="退款类型: refund_only/return_refund/exchange")
    reason: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="退款原因")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True, comment="退款状态: pending/approved/processing/completed/rejected")
    refund_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="退款金额")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD", comment="币种")
    platform_refund_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="平台退款ID")
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="退款商品列表JSON")
    approval_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="审批流程实例ID")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="处理完成时间")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class Promotion(Base):
    """促销活动表 - 折扣/赠品/捆绑/秒杀/优惠券五种类型"""
    __tablename__ = "promotion"
    __table_args__ = {"schema": "oms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    promo_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="促销编号")
    name: Mapped[str] = mapped_column(String(500), nullable=False, comment="促销名称")
    promo_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="促销类型: discount/gift/bundle/flash_sale/coupon")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True, comment="状态: draft/active/paused/ended")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="适用平台")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="适用店铺ID")
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="开始时间")
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="结束时间")
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False, default="percentage", comment="折扣类型: percentage/fixed_amount/free_shipping")
    discount_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="折扣值")
    min_purchase_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="最低消费金额")
    max_discount_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="最大优惠金额")
    usage_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="总使用次数限制，0=不限")
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="已使用次数")
    per_customer_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="每人使用次数限制，0=不限")
    applicable_skus_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="适用SKU列表JSON，空=全部")
    applicable_categories_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="适用分类列表JSON")
    conditions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="附加条件JSON")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="优先级，数字越大优先级越高")
    can_stack: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否可叠加其他促销")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class OrderSplitRule(Base):
    """拆单规则表 - 按仓库/平台/重量/SKU维度自动拆单"""
    __tablename__ = "order_split_rule"
    __table_args__ = {"schema": "oms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="规则名称")
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="规则类型: by_warehouse/by_platform/by_weight/by_sku")
    conditions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="规则条件JSON")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="优先级")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class OrderAuditLog(Base):
    """订单审计日志表 - 全状态变更留痕，支持追溯与审计"""
    __tablename__ = "order_audit_log"
    __table_args__ = {"schema": "oms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="订单ID")
    action: Mapped[str] = mapped_column(String(50), nullable=False, comment="操作类型: create/status_change/split/merge/refund")
    from_status: Mapped[str] = mapped_column(String(30), nullable=False, default="", comment="变更前状态")
    to_status: Mapped[str] = mapped_column(String(30), nullable=False, default="", comment="变更后状态")
    operator_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="操作人ID")
    operator_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="操作人姓名")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="操作备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
