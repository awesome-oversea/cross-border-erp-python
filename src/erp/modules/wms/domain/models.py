"""
WMS域 - 仓储管理域 ORM模型

本模块定义了仓储管理域的所有数据库实体映射，包含:
- Warehouse: 仓库表，自营/第三方/FBA/虚拟四种类型
- Location: 库位表，收货/存储/拣货/打包/发货/次品六种类型
- Inventory: 库存台账表，五类状态(在手/预留/可用/在途/次品)
- InboundOrder: 入库单表，采购/退货/调拨/其他四种来源
- OutboundOrder: 出库单表，销售/调拨/其他三种类型
- StockMovement: 库存流水表，入库/出库/调拨/调整/盘点五种类型
- StockCount: 盘点单表，全盘/循环盘/抽盘三种模式
- QualityInspection: 质检单表，收货质检与在库质检

技术栈: SQLAlchemy 2.x + async + PostgreSQL
主键策略: UUID由应用层生成
多租户: 所有业务表包含tenant_id字段实现隔离
库存模型: 五类状态台账 qty_on_hand/qty_reserved/qty_available/qty_inbound/qty_defective
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base


class Warehouse(Base):
    """仓库表 - 自营/第三方/FBA/虚拟四种类型，支持仓库容量与区域管理"""
    __tablename__ = "warehouse"
    __table_args__ = {"schema": "wms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    warehouse_type: Mapped[str] = mapped_column(String(30), nullable=False, default="self", comment="self/third_party/fba/virtual")
    region: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    address: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    contact_person: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    contact_phone: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    org_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Location(Base):
    """库位表 - 收货/存储/拣货/打包/发货/次品六种类型，四级编码(区-通道-架-位)"""
    __tablename__ = "location"
    __table_args__ = {"schema": "wms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    zone: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    aisle: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    shelf: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    bin: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    location_type: Mapped[str] = mapped_column(String(30), nullable=False, default="storage", comment="receiving/storage/picking/packing/shipping/defective")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Inventory(Base):
    """库存台账表 - 五类状态(在手/预留/可用/在途/次品)，支持批次与成本价管理"""
    __tablename__ = "inventory"
    __table_args__ = {"schema": "wms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    location_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    qty_on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_inbound: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_outbound: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_defective: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    safety_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Safety stock threshold")
    batch_no: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    cost_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    last_counted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最后盘点时间")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="乐观锁版本号，防止并发超卖")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class InboundOrder(Base):
    """入库单表 - 采购/退货/调拨/其他四种来源，关联收货质检流程"""
    __tablename__ = "inbound_order"
    __table_args__ = {"schema": "wms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    inbound_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    inbound_type: Mapped[str] = mapped_column(String(30), nullable=False, default="purchase", comment="purchase/return/transfer/other")
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="PO ID or return ID")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    received_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OutboundOrder(Base):
    """出库单表 - 销售/调拨/其他三种类型，关联拣货发货与物流"""
    __tablename__ = "outbound_order"
    __table_args__ = {"schema": "wms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    outbound_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    outbound_type: Mapped[str] = mapped_column(String(30), nullable=False, default="sales", comment="sales/transfer/other")
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="Order ID or transfer ID")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    shipped_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    tracking_no: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    logistics_channel: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StockMovement(Base):
    """库存流水表 - 入库/出库/调拨/调整/盘点五种类型，全量变动留痕"""
    __tablename__ = "stock_movement"
    __table_args__ = {"schema": "wms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="inbound/outbound/transfer/adjustment/count")
    qty_change: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_before: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_after: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    reference_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    location_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    operator_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StockCount(Base):
    """盘点单表 - 全盘/循环盘/抽盘三种模式，记录盘盈盘亏"""
    __tablename__ = "stock_count"
    __table_args__ = {"schema": "wms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    count_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    count_type: Mapped[str] = mapped_column(String(30), nullable=False, default="full", comment="full/cycle/spot")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class QualityInspection(Base):
    """质检单表 - 收货质检与在库质检，记录合格/不合格/部分合格"""
    __tablename__ = "quality_inspection"
    __table_args__ = {"schema": "wms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    inspection_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    inbound_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    quantity_inspected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inspection_result: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", comment="pending/passed/failed/partial")
    defect_type: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="none/damaged/wrong_item/quality_issue/missing")
    defect_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    inspector_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StockTransfer(Base):
    """库存调拨单表 - 仓库间/库位间库存调拨，支持审批与在途跟踪"""
    __tablename__ = "stock_transfer"
    __table_args__ = {"schema": "wms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    transfer_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="调拨单号，租户内唯一")
    from_warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="源仓库ID")
    to_warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="目标仓库ID")
    from_location_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="源库位ID")
    to_location_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="目标库位ID")
    transfer_type: Mapped[str] = mapped_column(String(30), nullable=False, default="warehouse", comment="调拨类型: warehouse仓库间/location库位间")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True, comment="状态: draft/pending_approval/approved/in_transit/completed/cancelled")
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="调拨明细JSON，含SKU/数量等")
    reason: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="调拨原因")
    approval_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="审批流程实例ID")
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="发货时间")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="收货时间")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
