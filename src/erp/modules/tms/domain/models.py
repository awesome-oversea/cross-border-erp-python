"""
TMS域 - 物流管理域 ORM模型

本模块定义了物流管理域的所有数据库实体映射，包含:
- LogisticsProvider: 物流商表，快递/空运/海运/铁路/多式联运
- ShippingMethod: 配送方式表，首重续重计费模型
- Shipment: 发货单表，订单→仓库→物流全链路
- ShippingBatch: 批量发货表，批量拣货发货管理
- FreightTemplate: 运费模板表，按重量/体积/件数/固定四种计费

技术栈: SQLAlchemy 2.x + async + PostgreSQL
主键策略: UUID由应用层生成
多租户: 所有业务表包含tenant_id字段实现隔离
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base


class LogisticsProvider(Base):
    """物流商表 - 快递/空运/海运/铁路/多式联运，支持API对接"""
    __tablename__ = "logistics_provider"
    __table_args__ = {"schema": "tms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="物流商名称")
    code: Mapped[str] = mapped_column(String(100), nullable=False, comment="物流商编码，租户内唯一")
    provider_type: Mapped[str] = mapped_column(String(30), nullable=False, default="express", comment="类型: express快递/air空运/sea海运/rail铁路/multi多式联运")
    api_endpoint: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="API对接地址")
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="加密API密钥")
    supported_regions: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="支持区域，逗号分隔，如US,UK,DE")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True, comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class ShippingMethod(Base):
    """配送方式表 - 首重续重计费模型，关联物流商"""
    __tablename__ = "shipping_method"
    __table_args__ = {"schema": "tms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    provider_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="物流商ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="配送方式名称")
    code: Mapped[str] = mapped_column(String(100), nullable=False, comment="配送方式编码，租户内唯一")
    shipping_type: Mapped[str] = mapped_column(String(30), nullable=False, default="standard", comment="配送类型: standard标准/express快递/economy经济")
    estimated_days_min: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="预计最短运输天数")
    estimated_days_max: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="预计最长运输天数")
    first_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="首重(kg)")
    first_weight_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="首重价格")
    additional_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="续重单位(kg)")
    additional_weight_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="续重单价")
    min_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="最低运费")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY", comment="币种")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class Shipment(Base):
    """发货单表 - 订单→仓库→物流全链路，支持轨迹追踪"""
    __tablename__ = "shipment"
    __table_args__ = {"schema": "tms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    shipment_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="发货单号，租户内唯一")
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="关联订单ID")
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="发货仓库ID")
    provider_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="物流商ID")
    shipping_method_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="配送方式ID")
    tracking_no: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True, comment="物流追踪号")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True, comment="状态: pending/processing/shipped/in_transit/delivered/failed/returned")
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="包裹重量(kg)")
    shipping_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="运费")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY", comment="币种")
    recipient_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="收件人姓名")
    recipient_phone: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="收件人电话")
    recipient_address: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="收件人地址")
    recipient_country: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="收件人国家")
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="发货明细JSON，含SKU/数量/重量等")
    tracking_events_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="物流轨迹事件JSON，含时间/地点/状态等")
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="发货时间")
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="签收时间")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class ShippingBatch(Base):
    """批量发货表 - 批量拣货发货管理，关联多个发货单"""
    __tablename__ = "shipping_batch"
    __table_args__ = {"schema": "tms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    batch_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="批次号，租户内唯一")
    carrier_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="承运商ID")
    carrier_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="承运商名称(冗余)")
    shipment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="发货单数量")
    total_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="总重量(kg)")
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="总运费")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY", comment="币种")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="created", index=True,
                                         comment="状态: created/picking/shipped/completed/cancelled")
    shipment_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="关联发货单ID列表JSON")
    remark: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="备注")
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="发货时间")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="完成时间")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class FreightTemplate(Base):
    """运费模板表 - 按重量/体积/件数/固定四种计费规则"""
    __tablename__ = "freight_template"
    __table_args__ = {"schema": "tms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="模板名称")
    calculation_type: Mapped[str] = mapped_column(String(30), nullable=False, default="by_weight", comment="计费方式: by_weight按重量/by_volume按体积/by_item按件数/by_fixed固定运费")
    rules_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="计费规则JSON，含区域/首重/续重/价格等")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
