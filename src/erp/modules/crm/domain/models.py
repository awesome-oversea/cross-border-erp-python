"""
CRM域 - 客户关系管理域 ORM模型

本模块定义了客户关系管理域的所有数据库实体映射，包含:
- Customer: 客户表，多平台客户统一视图，支持RFM分群
- CustomerTag: 客户标签表，手动/自动两种标签类型
- CustomerCommunication: 客户沟通记录表，邮件/站内信/在线客服多渠道
- Review: 评价表，多平台评价监控与回复管理
- ServiceTicket: 客服工单表，SLA时效管理，支持工单关联与满意度评分
- ReturnRefund: 退货退款表，仅退款/退货退款/换货三种类型
- ReviewReplyTemplate: 评价回复模板表，按类型/语言/平台分类
- Complaint: 投诉表，4级严重度+6类投诉类型
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base


class Customer(Base):
    """客户表 - 多平台客户统一视图，支持RFM分群与客户画像"""
    __tablename__ = "customer"
    __table_args__ = {"schema": "crm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    customer_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="客户编号，租户内唯一")
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="客户姓名")
    email: Mapped[str] = mapped_column(String(200), nullable=False, default="", index=True, comment="邮箱")
    phone: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="电话")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="", index=True, comment="来源平台")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="店铺ID")
    platform_customer_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", index=True, comment="平台侧客户ID")
    country: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="国家")
    state: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="州/省")
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="城市")
    address: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="详细地址")
    zip_code: Mapped[str] = mapped_column(String(30), nullable=False, default="", comment="邮编")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="标签列表JSON")
    segment: Mapped[str] = mapped_column(String(50), nullable=False, default="normal", comment="客户分群: vip/high_value/normal/at_risk/churned")
    total_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="累计订单数")
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="累计消费金额")
    avg_order_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="平均订单金额")
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最近下单时间")
    first_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="首次下单时间")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True, comment="状态: active/inactive/blacklisted")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class CustomerTag(Base):
    """客户标签表 - 手动/自动两种标签类型，自动标签支持规则引擎"""
    __tablename__ = "customer_tag"
    __table_args__ = {"schema": "crm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="标签名称")
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#1890ff", comment="标签颜色，十六进制色值")
    tag_type: Mapped[str] = mapped_column(String(30), nullable=False, default="manual", comment="标签类型: manual手动/auto自动")
    auto_rule_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="自动标签规则JSON，tag_type=auto时生效")
    customer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="关联客户数")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class CustomerCommunication(Base):
    """客户沟通记录表 - 邮件/站内信/在线客服多渠道沟通记录"""
    __tablename__ = "customer_communication"
    __table_args__ = {"schema": "crm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="客户ID")
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="email", comment="沟通渠道: email/inbox/chat/phone")
    direction: Mapped[str] = mapped_column(String(20), nullable=False, default="outbound", comment="方向: inbound入站/outbound出站")
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="主题")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="沟通内容")
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="关联订单ID")
    platform_message_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="平台消息ID，用于去重")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sent", comment="状态: draft/sent/delivered/failed")
    handled_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="处理人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")


class Review(Base):
    """评价表 - 多平台评价监控与回复管理，支持差评预警"""
    __tablename__ = "review"
    __table_args__ = {"schema": "crm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="来源平台")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="店铺ID")
    platform_review_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", index=True, comment="平台评价ID，用于去重")
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="关联订单ID")
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="关联SKU ID")
    listing_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="关联Listing ID")
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="客户ID")
    rating: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="评分1-5")
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="评价标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="评价内容")
    reply: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="回复内容")
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="回复时间")
    replied_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="回复人ID")
    is_negative: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否差评(rating<=2)")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True, comment="状态: pending/replied/ignored/escalated")
    review_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="评价日期")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class ServiceTicket(Base):
    """客服工单表 - SLA时效管理，支持工单关联、分组派单与满意度评分"""
    __tablename__ = "service_ticket"
    __table_args__ = {"schema": "crm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    ticket_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="工单编号，系统生成唯一")
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="客户ID")
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="关联订单ID")
    ticket_type: Mapped[str] = mapped_column(String(30), nullable=False, default="inquiry", index=True, comment="工单类型: inquiry/complaint/return/technical/other")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal", index=True, comment="优先级: low/normal/high/urgent")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True, comment="状态: open/in_progress/pending_customer/resolved/closed")
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="email", comment="来源渠道: email/inbox/chat/phone")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="来源平台")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="店铺ID")
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="工单主题")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="问题描述")
    resolution: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="解决方案")
    assigned_to: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="当前处理人ID")
    assigned_group: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="处理组/客服组")
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="SLA截止时间")
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="首次响应时间")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="解决时间")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="关闭时间")
    satisfaction_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="满意度评分1-5，0=未评价")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="标签列表JSON")
    related_tickets_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="关联工单ID列表JSON")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class ReturnRefund(Base):
    """退货退款表 - 仅退款/退货退款/换货三种类型，关联工单与订单"""
    __tablename__ = "return_refund"
    __table_args__ = {"schema": "crm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    return_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="退货退款单编号，系统生成唯一")
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="关联订单ID")
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="客户ID")
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="关联SKU ID")
    ticket_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="关联工单ID")
    return_type: Mapped[str] = mapped_column(String(30), nullable=False, default="return", index=True, comment="类型: refund_only仅退款/return退货退款/exchange换货")
    reason: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="退货退款原因")
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="原因编码，用于统计分析")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="退货数量")
    refund_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="退款金额")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD", comment="币种")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="requested", index=True, comment="状态: requested/approved/received/refunded/rejected/cancelled")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="来源平台")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="店铺ID")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="收货时间")
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="退款完成时间")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="备注")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class ReviewReplyTemplate(Base):
    """评价回复模板表 - 按类型/语言/平台分类，支持变量占位符"""
    __tablename__ = "review_reply_template"
    __table_args__ = {"schema": "crm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="模板名称")
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general", comment="分类: general/positive/negative/neutral/complaint")
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en", comment="语言代码: en/zh/de/fr/es/ja")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="适用平台，空=通用")
    content_template: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="回复模板内容，支持变量占位符")
    variables_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="可用变量: {customer_name}/{product_name}/{order_id}/{rating}")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否默认模板")
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="使用次数")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class Complaint(Base):
    """投诉表 - 4级严重度+6类投诉类型，支持证据附件与升级处理"""
    __tablename__ = "complaint"
    __table_args__ = {"schema": "crm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    complaint_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="投诉编号，系统生成唯一")
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="客户ID")
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="关联订单ID")
    ticket_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="关联工单ID")
    complaint_type: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="投诉类型: product_quality/late_delivery/wrong_item/service_attitude/other")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", comment="严重度: low/medium/high/critical")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted", index=True, comment="状态: submitted/investigating/resolved/closed/escalated")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="来源平台")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="店铺ID")
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="投诉主题")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="投诉描述")
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="证据附件列表JSON，含图片/视频URL")
    resolution: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="处理结果")
    resolution_type: Mapped[str] = mapped_column(String(30), nullable=False, default="", comment="处理方式: refund/replacement/apology/credit/other")
    assigned_to: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="当前处理人ID")
    escalated_to: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="升级处理人ID")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="解决时间")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="关闭时间")
    satisfaction_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="满意度评分1-5，0=未评价")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
