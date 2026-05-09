"""
供应链域(SCM) - 领域模型

包含供应商管理、采购订单、采购明细、补货计划、供应商评估、询价/报价等核心聚合。
所有模型遵循DDD领域驱动设计，支持多租户隔离、软删除、审计追踪。

聚合根:
    - Supplier: 供应商
    - PurchaseOrder: 采购订单(支持5种采购模式)
    - ReplenishmentPlan: 补货计划
    - Inquiry: 询价单

V4新增:
    - PurchaseOrder.purchase_mode: 5种采购模式(标准采购/寄售/JIT直发/VMI代工/集中采购)
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base


class Supplier(Base):
    """供应商表 - 管理供应商基本信息、合作等级和绩效评分"""
    __tablename__ = "supplier"
    __table_args__ = {"schema": "scm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="供应商名称")
    code: Mapped[str] = mapped_column(String(100), nullable=False, comment="供应商编码，租户内唯一")
    short_name: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="供应商简称")
    contact_person: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="联系人姓名")
    contact_phone: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="联系电话")
    contact_email: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="联系邮箱")
    address: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="详细地址")
    region: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="所在区域")
    supplier_type: Mapped[str] = mapped_column(String(30), nullable=False, default="general", comment="供应商类型: general/factory/trading")
    cooperation_level: Mapped[str] = mapped_column(String(20), nullable=False, default="normal", comment="合作等级: strategic/normal/trial")
    payment_terms: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="付款条件，如Net30/Net60等")
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="交货提前期(天)")
    min_order_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="最小起订量")
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="质量评分，0-100")
    delivery_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="交期评分，0-100")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True, comment="状态: active/disabled/blacklisted")
    org_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="所属组织ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class PurchaseOrder(Base):
    """采购订单表 - 管理采购全流程，支持5种采购模式(V4新增)"""
    __tablename__ = "purchase_order"
    __table_args__ = {"schema": "scm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    po_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="采购单号，租户内唯一")
    supplier_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="供应商ID")
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="收货仓库ID")
    po_type: Mapped[str] = mapped_column(String(30), nullable=False, default="standard", comment="采购类型: standard/urgent/replenishment/sample")
    purchase_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="standard_purchase", comment="采购模式(V4): standard_purchase/consignment/jit_dropship/vmi_subcontracting/centralized")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True, comment="状态: draft/pending_approval/approved/partially_received/received/closed/cancelled")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY", comment="币种")
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="订单总金额")
    paid_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="已付金额")
    expected_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="预计交货日期")
    actual_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="实际交货日期")
    approval_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="审批流程实例ID")
    recommendation_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="PMS推荐ID")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="备注")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class PurchaseOrderItem(Base):
    """采购明细表 - 采购订单的SKU明细行，记录采购数量、单价和收货进度"""
    __tablename__ = "purchase_order_item"
    __table_args__ = {"schema": "scm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    po_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="采购订单ID")
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="SKU ID")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="采购数量")
    received_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="已收货数量")
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="单价")
    item_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="行金额小计")
    expected_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="预计交货日期")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", comment="状态: pending/partially_received/received/cancelled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")


class ReplenishmentPlan(Base):
    """补货计划表 - 基于库存水位和销量预测自动/手动生成补货计划"""
    __tablename__ = "replenishment_plan"
    __table_args__ = {"schema": "scm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    plan_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, comment="计划编号，租户内唯一")
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="仓库ID")
    plan_type: Mapped[str] = mapped_column(String(30), nullable=False, default="auto", comment="计划类型: auto/manual/pms_suggested")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True, comment="状态: draft/pending_approval/approved/in_progress/completed/cancelled")
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="计划明细JSON，包含SKU/数量/仓库等")
    recommendation_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="PMS推荐ID")
    approval_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="审批流程实例ID")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class SupplierEvaluation(Base):
    """供应商评估表 - 按周期对供应商进行多维度评分，支持质量/交期/价格/服务四维评估"""
    __tablename__ = "supplier_evaluation"
    __table_args__ = {"schema": "scm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    supplier_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="供应商ID")
    period: Mapped[str] = mapped_column(String(20), nullable=False, comment="评估周期，格式: YYYY-MM")
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="质量评分，0-100")
    delivery_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="交期评分，0-100")
    price_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="价格评分，0-100")
    service_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="服务评分，0-100")
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="综合评分，加权平均")
    remarks: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="评估备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")


class Inquiry(Base):
    """询价单表 - 管理向供应商发起的询价流程，支持多供应商比价"""
    __tablename__ = "inquiry"
    __table_args__ = {"schema": "scm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    inquiry_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="询价单号，租户内唯一")
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="询价标题")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True, comment="状态: draft/published/quoted/completed/cancelled")
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="报价截止时间")
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="询价明细JSON，包含SKU/数量/要求等")
    target_supplier_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="目标供应商ID列表JSON")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class InquiryQuote(Base):
    """询价报价表 - 供应商对询价单的报价回复，支持比价和中标选择"""
    __tablename__ = "inquiry_quote"
    __table_args__ = {"schema": "scm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    inquiry_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="询价单ID")
    supplier_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="供应商ID")
    quote_items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="报价明细JSON，包含SKU/单价/交期等")
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="报价总金额")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY", comment="币种")
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="交货提前期(天)")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="备注")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted", index=True, comment="状态: submitted/shortlisted/rejected/awarded")
    is_winner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否中标")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )