from datetime import datetime

from pydantic import BaseModel, Field


class WarehouseCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=100)
    warehouse_type: str = Field(default="self", pattern=r"^(self|third_party|fba|virtual)$")
    region: str = Field(default="", max_length=100)
    address: str = Field(default="", max_length=500)
    contact_person: str = Field(default="", max_length=100)
    contact_phone: str = Field(default="", max_length=50)
    is_default: bool = False
    org_id: str | None = None


class WarehouseUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    region: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    contact_person: str | None = Field(default=None, max_length=100)
    contact_phone: str | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class WarehouseResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    code: str
    warehouse_type: str = "self"
    region: str = ""
    address: str = ""
    contact_person: str = ""
    contact_phone: str = ""
    is_default: bool = False
    status: str = "active"
    org_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class LocationCreateRequest(BaseModel):
    warehouse_id: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(default="", max_length=200)
    zone: str = Field(default="", max_length=50)
    aisle: str = Field(default="", max_length=20)
    shelf: str = Field(default="", max_length=20)
    bin: str = Field(default="", max_length=20)
    location_type: str = Field(default="storage", pattern=r"^(receiving|storage|picking|packing|shipping|defective|returns)$")


class LocationResponse(BaseModel):
    id: str
    tenant_id: str
    warehouse_id: str
    code: str
    name: str = ""
    zone: str = ""
    aisle: str = ""
    shelf: str = ""
    bin: str = ""
    location_type: str = "storage"
    status: str = "active"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class InventoryCreateRequest(BaseModel):
    warehouse_id: str = Field(..., min_length=1)
    sku_id: str = Field(..., min_length=1)
    location_id: str | None = None
    qty_on_hand: int = Field(default=0, ge=0)
    qty_reserved: int = Field(default=0, ge=0)
    safety_qty: int = Field(default=0, ge=0)
    batch_no: str = Field(default="", max_length=100)
    cost_price: float = Field(default=0.0, ge=0)
    cost_currency: str = Field(default="CNY", max_length=10)


class InventoryUpdateRequest(BaseModel):
    qty_on_hand: int | None = Field(default=None, ge=0)
    qty_reserved: int | None = Field(default=None, ge=0)
    safety_qty: int | None = Field(default=None, ge=0)
    cost_price: float | None = Field(default=None, ge=0)


class InventoryResponse(BaseModel):
    id: str
    tenant_id: str
    warehouse_id: str
    sku_id: str
    location_id: str | None = None
    qty_on_hand: int = 0
    qty_reserved: int = 0
    qty_available: int = 0
    qty_inbound: int = 0
    qty_outbound: int = 0
    qty_defective: int = 0
    safety_qty: int = 0
    batch_no: str = ""
    cost_price: float = 0.0
    cost_currency: str = "CNY"
    last_counted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class InboundOrderCreateRequest(BaseModel):
    inbound_no: str = Field(..., min_length=1, max_length=100)
    warehouse_id: str = Field(..., min_length=1)
    inbound_type: str = Field(default="purchase", pattern=r"^(purchase|return|transfer|other)$")
    source_id: str = ""
    items: list = Field(default_factory=list)
    remark: str = ""


class InboundOrderResponse(BaseModel):
    id: str
    tenant_id: str
    inbound_no: str
    warehouse_id: str
    inbound_type: str = "purchase"
    source_id: str = ""
    status: str = "pending"
    items: list = Field(default_factory=list)
    remark: str = ""
    created_by: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class OutboundOrderCreateRequest(BaseModel):
    outbound_no: str = Field(..., min_length=1, max_length=100)
    warehouse_id: str = Field(..., min_length=1)
    outbound_type: str = Field(default="sales", pattern=r"^(sales|transfer|other)$")
    source_id: str = ""
    items: list = Field(default_factory=list)
    remark: str = ""


class OutboundOrderResponse(BaseModel):
    id: str
    tenant_id: str
    outbound_no: str
    warehouse_id: str
    outbound_type: str = "sales"
    source_id: str = ""
    status: str = "pending"
    items: list = Field(default_factory=list)
    tracking_no: str = ""
    logistics_channel: str = ""
    remark: str = ""
    created_by: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class StockCountCreateRequest(BaseModel):
    count_no: str = Field(..., min_length=1, max_length=100)
    warehouse_id: str = Field(..., min_length=1)
    count_type: str = Field(default="full", pattern=r"^(full|cycle|spot)$")
    items: list = Field(default_factory=list)


class StockCountResponse(BaseModel):
    id: str
    tenant_id: str
    count_no: str
    warehouse_id: str
    count_type: str = "full"
    status: str = "draft"
    items: list = Field(default_factory=list)
    result: dict = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_by: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class StockAdjustRequest(BaseModel):
    warehouse_id: str = Field(..., min_length=1)
    sku_id: str = Field(..., min_length=1)
    qty_change: int
    movement_type: str = Field(default="adjustment", pattern=r"^(inbound|outbound|transfer|adjustment|freeze|unfreeze|qc_defect|stocktaking)$")
    reference_type: str = ""
    reference_id: str = ""
    remark: str = ""


class StockFreezeRequest(BaseModel):
    warehouse_id: str = Field(..., min_length=1)
    sku_id: str = Field(..., min_length=1)
    freeze_qty: int = Field(..., ge=1)
    freeze_reason: str = ""


class StockUnfreezeRequest(BaseModel):
    warehouse_id: str = Field(..., min_length=1)
    sku_id: str = Field(..., min_length=1)
    unfreeze_qty: int = Field(..., ge=1)


class StockMovementResponse(BaseModel):
    id: str
    tenant_id: str
    warehouse_id: str
    sku_id: str
    movement_type: str = ""
    qty_change: int = 0
    qty_before: int = 0
    qty_after: int = 0
    reference_type: str = ""
    reference_id: str = ""
    operator_id: str = ""
    remark: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class InboundReceiveRequest(BaseModel):
    items: list[dict] = Field(..., min_length=1)


class OutboundShipRequest(BaseModel):
    items: list[dict] = Field(..., min_length=1)
    tracking_no: str = ""
    logistics_channel: str = ""


class QualityInspectionCreateRequest(BaseModel):
    inspection_no: str = Field(..., min_length=1, max_length=100)
    warehouse_id: str = Field(..., min_length=1)
    sku_id: str = Field(..., min_length=1)
    quantity_inspected: int = Field(..., ge=1)
    quantity_passed: int = Field(default=0, ge=0)
    quantity_failed: int = Field(default=0, ge=0)
    defect_type: str = Field(default="", max_length=100)
    defect_description: str = Field(default="", max_length=500)
    inspector_id: str = Field(default="", max_length=36)
    remark: str = ""


class QualityInspectionCompleteRequest(BaseModel):
    quantity_passed: int = Field(..., ge=0)
    quantity_failed: int = Field(..., ge=0)
    defect_type: str = Field(default="", max_length=100)
    defect_description: str = Field(default="", max_length=500)
    inspector_id: str = Field(default="", max_length=36)


class QualityInspectionResponse(BaseModel):
    id: str
    tenant_id: str
    inspection_no: str = ""
    warehouse_id: str = ""
    sku_id: str = ""
    quantity_inspected: int = 0
    quantity_passed: int = 0
    quantity_failed: int = 0
    inspection_result: str = "pending"
    defect_type: str = ""
    defect_description: str = ""
    inspector_id: str = ""
    inspected_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class QualityInspectionPassRateResponse(BaseModel):
    total_inspections: int = 0
    total_inspected_qty: int = 0
    total_passed_qty: int = 0
    pass_rate: float = 0.0


class TransferCreateRequest(BaseModel):
    from_warehouse_id: str = Field(..., min_length=1)
    to_warehouse_id: str = Field(..., min_length=1)
    items: list[dict] = Field(..., min_length=1)
    reason: str = Field(default="", max_length=500)


class TransferResponse(BaseModel):
    id: str
    tenant_id: str
    transfer_no: str = ""
    from_warehouse_id: str = ""
    to_warehouse_id: str = ""
    status: str = "draft"
    reason: str = ""
    items_json: str = "[]"
    total_qty: int = 0
    shipped_at: datetime | None = None
    received_at: datetime | None = None
    created_by: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class FBAReplenishmentGenerateRequest(BaseModel):
    sku_id: str = Field(..., min_length=1)
    fba_warehouse_id: str = Field(..., min_length=1)
    source_warehouse_id: str = Field(..., min_length=1)
    current_fba_qty: int = Field(default=0, ge=0)
    avg_daily_sales: float = Field(default=0.0, ge=0.0)
    lead_time_days: int = Field(default=14, ge=1)
    safety_stock_days: int = Field(default=7, ge=1)
    strategy: str = Field(default="min_max", pattern=r"^(min_max|fixed_quantity|eoq|reorder_point)$")
    strategy_params: dict = Field(default_factory=dict)


class FBAReplenishmentApproveRequest(BaseModel):
    approved_qty: int | None = Field(default=None, ge=0)


class FBAReplenishmentResponse(BaseModel):
    id: str
    tenant_id: str
    plan_no: str = ""
    sku_id: str = ""
    fba_warehouse_id: str = ""
    source_warehouse_id: str = ""
    current_fba_qty: int = 0
    avg_daily_sales: float = 0.0
    days_of_supply: float = 0.0
    suggested_qty: int = 0
    approved_qty: int = 0
    status: str = "draft"
    strategy_name: str = ""
    min_replenishment_qty: int = 0
    max_replenishment_qty: int = 0
    lead_time_days: int = 14
    safety_stock_days: int = 7
    created_by: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class InventorySnapshotResponse(BaseModel):
    id: str
    tenant_id: str
    snapshot_date: str = ""
    warehouse_id: str = ""
    sku_id: str = ""
    qty_on_hand: int = 0
    qty_reserved: int = 0
    qty_available: int = 0
    qty_inbound: int = 0
    qty_outbound: int = 0
    qty_defective: int = 0
    cost_price: float = 0.0
    cost_currency: str = "CNY"
    daily_out_qty: int = 0
    avg_daily_out_7d: float = 0.0
    avg_daily_out_30d: float = 0.0
    days_of_supply: float = 0.0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AlertRuleCreateRequest(BaseModel):
    rule_name: str = Field(..., min_length=1, max_length=200)
    alert_type: str = Field(..., min_length=1, max_length=50, pattern=r"^(low_stock|overstock|stockout|slow_moving|dead_stock|replenishment_needed|inbound_delayed|defective_high)$")
    severity: str = Field(default="warning", pattern=r"^(info|warning|critical)$")
    condition: dict = Field(default_factory=dict)
    warehouse_scope: list[str] = Field(default_factory=list)
    sku_scope: list[str] = Field(default_factory=list)
    category_scope: list[str] = Field(default_factory=list)
    cooldown_hours: int = Field(default=24, ge=1)
    notify_channels: list[str] = Field(default_factory=lambda: ["in_app"])


class AlertRuleResponse(BaseModel):
    id: str
    tenant_id: str
    rule_name: str = ""
    alert_type: str = ""
    severity: str = "warning"
    condition_json: str = "{}"
    warehouse_scope: str = "[]"
    sku_scope: str = "[]"
    category_scope: str = "[]"
    is_active: bool = True
    cooldown_hours: int = 24
    notify_channels: str = '["in_app"]'
    created_by: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AlertResolveRequest(BaseModel):
    resolution_note: str = Field(default="", max_length=500)


class AlertResponse(BaseModel):
    id: str
    tenant_id: str
    rule_id: str = ""
    alert_type: str = ""
    severity: str = "warning"
    warehouse_id: str = ""
    sku_id: str = ""
    current_value: float = 0.0
    threshold_value: float = 0.0
    message: str = ""
    detail_json: str = "{}"
    status: str = "pending"
    resolved_by: str = ""
    resolved_at: datetime | None = None
    resolution_note: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PageRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class InventorySummaryResponse(BaseModel):
    total_skus: int = 0
    total_qty_on_hand: int = 0
    total_qty_reserved: int = 0
    total_qty_available: int = 0


class WarehouseCapacityResponse(BaseModel):
    warehouse_id: str = ""
    total_skus: int = 0
    total_qty: int = 0


class StockReserveRequest(BaseModel):
    warehouse_id: str = Field(..., min_length=1)
    sku_id: str = Field(..., min_length=1)
    reserve_qty: int = Field(..., ge=1)
    reference_type: str = ""
    reference_id: str = ""
    remark: str = ""


class StockUnreserveRequest(BaseModel):
    warehouse_id: str = Field(..., min_length=1)
    sku_id: str = Field(..., min_length=1)
    unreserve_qty: int = Field(..., ge=1)
    reference_type: str = ""
    reference_id: str = ""
    remark: str = ""


class StockMovementQueryRequest(BaseModel):
    sku_id: str = Field(default="")
    reference_type: str = Field(default="")
    reference_id: str = Field(default="")
    limit: int = Field(default=50, ge=1, le=200)


class InboundOrderListRequest(BaseModel):
    status: str = Field(default="")
    warehouse_id: str = Field(default="")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class OutboundOrderListRequest(BaseModel):
    status: str = Field(default="")
    warehouse_id: str = Field(default="")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class TransferListRequest(BaseModel):
    status: str = Field(default="")
    from_warehouse_id: str = Field(default="")
    to_warehouse_id: str = Field(default="")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class FBAReplenishmentListRequest(BaseModel):
    sku_id: str = Field(default="")
    status: str = Field(default="")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class SnapshotQueryRequest(BaseModel):
    snapshot_date: str = Field(..., min_length=1)
    warehouse_id: str = Field(default="")
    sku_id: str = Field(default="")


class AlertListRequest(BaseModel):
    alert_type: str = Field(default="")
    severity: str = Field(default="")
    status: str = Field(default="")
    warehouse_id: str = Field(default="")
    sku_id: str = Field(default="")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AlertRuleUpdateRequest(BaseModel):
    rule_name: str | None = Field(default=None, max_length=200)
    severity: str | None = Field(default=None, pattern=r"^(info|warning|critical)$")
    condition: dict | None = Field(default=None)
    is_active: bool | None = None
    cooldown_hours: int | None = Field(default=None, ge=1)
    notify_channels: list[str] | None = None


class WMSOverviewResponse(BaseModel):
    warehouse: dict = Field(default_factory=dict)
    inventory: dict = Field(default_factory=dict)
    inbound: dict = Field(default_factory=dict)
    outbound: dict = Field(default_factory=dict)
    stock_count: dict = Field(default_factory=dict)
