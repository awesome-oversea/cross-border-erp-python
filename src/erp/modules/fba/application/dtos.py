from datetime import datetime

from pydantic import BaseModel, Field


class FbaShipmentCreateRequest(BaseModel):
    shipment_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(default="", max_length=500)
    platform: str = Field(default="amazon", max_length=50)
    store_id: str = Field(..., min_length=1)
    fba_shipment_id: str = Field(default="", max_length=200)
    destination_fulfillment_center_id: str = Field(default="", max_length=50)
    box_count: int = Field(default=0, ge=0)
    total_units: int = Field(default=0, ge=0)
    total_weight: float = Field(default=0.0, ge=0)
    currency: str = Field(default="USD", max_length=10)
    estimated_shipping_cost: float = Field(default=0.0, ge=0)
    items: list = Field(default_factory=list)
    remark: str = ""


class FbaShipmentStatusRequest(BaseModel):
    shipment_status: str = Field(..., min_length=1)
    tracking_no: str = ""
    carrier: str = ""


class FbaShipmentResponse(BaseModel):
    id: str
    tenant_id: str
    shipment_id: str
    name: str = ""
    platform: str = "amazon"
    store_id: str
    fba_shipment_id: str = ""
    destination_fulfillment_center_id: str = ""
    shipment_status: str = "draft"
    box_count: int = 0
    total_units: int = 0
    total_weight: float = 0.0
    currency: str = "USD"
    estimated_shipping_cost: float = 0.0
    actual_shipping_cost: float = 0.0
    tracking_no: str = ""
    carrier: str = ""
    shipped_at: datetime | None = None
    received_at: datetime | None = None
    status: str = "draft"
    remark: str = ""
    created_by: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class FbaInventoryCreateRequest(BaseModel):
    sku_id: str = Field(..., min_length=1)
    store_id: str = Field(..., min_length=1)
    platform: str = Field(default="amazon", max_length=50)
    fnsku: str = Field(default="", max_length=50)
    asin: str = Field(default="", max_length=50)
    fulfillment_center_id: str = Field(default="", max_length=50)
    condition_type: str = Field(default="New", max_length=30)
    qty_available: int = Field(default=0, ge=0)
    qty_fulfillable: int = Field(default=0, ge=0)
    qty_inbound: int = Field(default=0, ge=0)
    qty_reserved: int = Field(default=0, ge=0)
    qty_unfulfillable: int = Field(default=0, ge=0)


class FbaInventoryResponse(BaseModel):
    id: str
    tenant_id: str
    sku_id: str
    store_id: str
    platform: str = "amazon"
    fnsku: str = ""
    asin: str = ""
    fulfillment_center_id: str = ""
    condition_type: str = "New"
    qty_available: int = 0
    qty_fulfillable: int = 0
    qty_inbound: int = 0
    qty_reserved: int = 0
    qty_unfulfillable: int = 0
    qty_researching: int = 0
    last_updated_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class FbaFeeCreateRequest(BaseModel):
    sku_id: str = Field(..., min_length=1)
    store_id: str = Field(..., min_length=1)
    platform: str = Field(default="amazon", max_length=50)
    fee_type: str = Field(..., min_length=1, max_length=50)
    fee_amount: float = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=10)
    fee_date: datetime | None = None
    quantity: int = Field(default=0, ge=0)
    per_unit_fee: float = Field(default=0.0, ge=0)
    order_id: str = ""
    reference_type: str = ""
    reference_id: str = ""
    raw_data: dict = Field(default_factory=dict)


class FbaFeeResponse(BaseModel):
    id: str
    tenant_id: str
    sku_id: str
    store_id: str
    platform: str = "amazon"
    fee_type: str
    fee_amount: float = 0.0
    currency: str = "USD"
    fee_date: datetime | None = None
    quantity: int = 0
    per_unit_fee: float = 0.0
    order_id: str = ""
    reference_type: str = ""
    reference_id: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class FbaShipmentSearchRequest(BaseModel):
    keyword: str = Field(default="", description="关键词搜索 (货件编号/名称)")
    platform: str = Field(default="", description="平台筛选")
    status: str = Field(default="", description="状态筛选")
    store_id: str = Field(default="", description="店铺ID筛选")
    start_date: datetime | None = Field(default=None, description="开始日期")
    end_date: datetime | None = Field(default=None, description="结束日期")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class FbaInventorySearchRequest(BaseModel):
    sku_id: str = Field(default="", description="SKU ID筛选")
    store_id: str = Field(default="", description="店铺ID筛选")
    fnsku: str = Field(default="", description="FNSKU筛选")
    asin: str = Field(default="", description="ASIN筛选")
    condition_type: str = Field(default="", description="条件类型筛选")
    low_stock_only: bool = Field(default=False, description="仅显示低库存")
    low_stock_threshold: int = Field(default=10, ge=0, description="低库存阈值")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class FbaFeeSearchRequest(BaseModel):
    fee_type: str = Field(default="", description="费用类型筛选")
    sku_id: str = Field(default="", description="SKU ID筛选")
    store_id: str = Field(default="", description="店铺ID筛选")
    start_date: datetime | None = Field(default=None, description="开始日期")
    end_date: datetime | None = Field(default=None, description="结束日期")
    min_amount: float | None = Field(default=None, ge=0, description="最小金额")
    max_amount: float | None = Field(default=None, ge=0, description="最大金额")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class FbaReplenishmentSearchRequest(BaseModel):
    sku_id: str = Field(default="", description="SKU ID筛选")
    store_id: str = Field(default="", description="店铺ID筛选")
    status: str = Field(default="", description="状态筛选")
    priority: str = Field(default="", description="优先级筛选")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class FBAStatisticsResponse(BaseModel):
    total_shipments: int = 0
    active_shipments: int = 0
    total_inventory_items: int = 0
    total_fulfillable_qty: int = 0
    total_inbound_qty: int = 0
    total_reserved_qty: int = 0
    low_stock_items: int = 0
    total_fees: float = 0.0
    fees_by_type: dict[str, float] = {}
    total_replenishment_plans: int = 0
    pending_replenishment_plans: int = 0
    total_inbound_plans: int = 0
    shipments_by_status: dict[str, int] = {}
    inventory_by_store: dict[str, int] = {}
