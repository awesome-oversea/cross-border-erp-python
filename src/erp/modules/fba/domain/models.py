"""
FBA/海外仓域 - 领域模型

包含FBA货件管理、FBA库存、FBA费用、箱标签、补货计划、入库计划、异常处理等核心聚合。
所有模型遵循DDD领域驱动设计，支持多租户隔离、软删除、审计追踪。

聚合根:
    - FbaShipment: FBA货件
    - FbaInventory: FBA库存
    - FbaFee: FBA费用
    - FbaReplenishmentPlan: FBA补货计划
    - FbaInboundPlan: FBA入库计划
    - FbaException: FBA异常处理(V4新增)
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base


class FbaShipment(Base):
    """FBA货件表 - 管理FBA发货的全生命周期，从创建到收货确认"""
    __tablename__ = "fba_shipment"
    __table_args__ = {"schema": "fba"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    shipment_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="货件业务编号，租户内唯一")
    name: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="货件名称")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="amazon", index=True, comment="平台标识: amazon/walmart等")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="店铺ID")
    fba_shipment_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", index=True, comment="平台FBA货件ID")
    destination_fulfillment_center_id: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="目的FBA仓库编码")
    shipment_status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True, comment="平台货件状态: draft/submitted/in_review/working/shipped/received/cancelled")
    shipping_plan_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="发货计划ID")
    box_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="箱数")
    total_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="总商品数量")
    total_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="总重量(kg)")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD", comment="币种")
    estimated_shipping_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="预估运费")
    actual_shipping_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="实际运费")
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="货件明细JSON，包含SKU/数量/单价等")
    tracking_no: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="物流追踪号")
    carrier: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="承运商名称")
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="发货时间")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="签收时间")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True, comment="系统状态: draft/submitted/in_review/working/shipped/received/partial_received/closed/cancelled")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="备注")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class FbaInventory(Base):
    """FBA库存表 - 实时同步FBA仓库的库存快照，支持多维度库存查询"""
    __tablename__ = "fba_inventory"
    __table_args__ = {"schema": "fba"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="SKU ID")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="店铺ID")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="amazon", comment="平台标识")
    fnsku: Mapped[str] = mapped_column(String(50), nullable=False, default="", index=True, comment="FBA SKU编码")
    asin: Mapped[str] = mapped_column(String(50), nullable=False, default="", index=True, comment="Amazon标准识别号")
    fulfillment_center_id: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="FBA仓库编码")
    condition_type: Mapped[str] = mapped_column(String(30), nullable=False, default="New", comment="商品状况: New/Used/Refurbished等")
    qty_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="可用库存数量")
    qty_fulfillable: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="可配送数量")
    qty_inbound: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="在途数量")
    qty_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="预留数量")
    qty_unfulfillable: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="不可配送数量")
    qty_researching: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="调查中数量")
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最后同步时间")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class FbaFee(Base):
    """FBA费用表 - 记录FBA各项费用明细，支持费用分析和成本归集"""
    __tablename__ = "fba_fee"
    __table_args__ = {"schema": "fba"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="SKU ID")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="店铺ID")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="amazon", comment="平台标识")
    fee_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="费用类型: fba_fulfillment_fee/storage_fee/long_term_storage_fee/removal_fee/return_fee/prep_fee/label_fee等")
    fee_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="费用金额")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD", comment="币种")
    fee_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True, comment="费用产生日期")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="关联商品数量")
    per_unit_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="单位费用")
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="关联订单ID")
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="关联类型")
    reference_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="关联ID")
    raw_data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="平台原始数据JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")


class FbaBoxLabel(Base):
    """FBA箱标签表 - 管理FBA发货的箱标签打印和追踪"""
    __tablename__ = "fba_box_label"
    __table_args__ = {"schema": "fba"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    shipment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="关联货件ID")
    box_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="箱号，从1开始递增")
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="SKU ID")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="本箱商品数量")
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="本箱重量(kg)")
    dimensions: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="箱尺寸，格式: LxWxH(cm)")
    label_url: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="标签文件URL")
    fnsku: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="FBA SKU编码")
    asin: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="Amazon标准识别号")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created", index=True, comment="标签状态: created/printed/attached/voided")
    printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="打印时间")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class FbaReplenishmentPlan(Base):
    """FBA补货计划表 - 基于销量预测和安全库存自动生成补货建议"""
    __tablename__ = "fba_replenishment_plan"
    __table_args__ = {"schema": "fba"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="SKU ID")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="店铺ID")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="amazon", comment="平台标识")
    suggested_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="建议补货数量")
    approved_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="审批通过数量")
    current_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="当前FBA库存")
    qty_inbound: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="在途数量")
    avg_daily_sales: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="日均销量")
    days_of_supply: Mapped[int] = mapped_column(Integer, nullable=False, default=30, comment="可供应天数")
    safety_stock_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14, comment="安全库存天数")
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7, comment="采购提前期(天)")
    destination_center: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="目的FBA仓库编码")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal", index=True, comment="优先级: urgent/high/normal/low")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True, comment="状态: pending/approved/rejected/in_progress/completed/cancelled")
    approved_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="审批人ID")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="审批时间")
    shipment_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="关联货件ID")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="备注")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class FbaInboundPlan(Base):
    """FBA入库计划表 - 管理从国内仓到FBA仓库的入库计划"""
    __tablename__ = "fba_inbound_plan"
    __table_args__ = {"schema": "fba"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="计划名称")
    plan_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="计划编号，租户内唯一")
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="发货仓库ID")
    destination_fba_center: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="目的FBA仓库编码")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="amazon", comment="平台标识")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="店铺ID")
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="计划明细JSON，包含SKU/数量等")
    total_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="总商品数量")
    total_boxes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="总箱数")
    total_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="总重量(kg)")
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="预估费用")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD", comment="币种")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True, comment="状态: draft/submitted/confirmed/in_progress/shipped/completed/cancelled")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="提交时间")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="完成时间")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="备注")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class FbaException(Base):
    """FBA异常处理表(V4新增) - 记录FBA运营中的各类异常事件，支持异常分类、分级和处理追踪"""
    __tablename__ = "fba_exception"
    __table_args__ = {"schema": "fba"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    exception_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="异常编号，租户内唯一")
    exception_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="异常类型: inventory_discrepancy/shipment_delay/receiving_shortage/damage_in_transit/label_error/overage/stranded_inventory/long_term_storage/return_issue/fee_discrepancy")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", index=True, comment="严重程度: low/medium/high/critical")
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="异常标题")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="异常详细描述")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="amazon", comment="平台标识")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="店铺ID")
    shipment_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="关联货件ID")
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="关联SKU ID")
    fba_shipment_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="平台FBA货件ID")
    fulfillment_center_id: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="FBA仓库编码")
    expected_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="预期值(数量/金额)")
    actual_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="实际值(数量/金额)")
    discrepancy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="差值(实际-预期)")
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="异常证据JSON，包含截图/日志/数据快照等")
    resolution: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="处理方案")
    resolution_type: Mapped[str] = mapped_column(String(30), nullable=False, default="", comment="处理方式: adjust/reorder/claim/dispose/ignore/escalate")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True, comment="状态: open/investigating/resolved/closed/escalated")
    assigned_to: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="处理人ID")
    assigned_group: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="处理组")
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="发现时间")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="解决时间")
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="处理截止时间")
    impact_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="影响评估JSON，包含影响范围/金额/客户数等")
    is_auto_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否系统自动检测")
    source_system: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="来源系统: fba_api/inventory_sync/shipment_receiving/manual")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="标签JSON")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="备注")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")
