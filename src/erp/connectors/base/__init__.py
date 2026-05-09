from __future__ import annotations

import abc
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ConnectorType(StrEnum):
    PLATFORM = "platform"
    LOGISTICS = "logistics"
    PAYMENT = "payment"
    WAREHOUSE = "warehouse"
    PROCUREMENT = "procurement"
    TAX = "tax"
    AI = "ai"


class ConnectorStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


@dataclass
class ConnectorConfig:
    connector_id: str = ""
    connector_type: str = ""
    connector_name: str = ""
    base_url: str = ""
    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    refresh_token: str = ""
    seller_id: str = ""
    store_id: str = ""
    marketplace_id: str = ""
    extra: dict = field(default_factory=dict)
    rate_limit_per_minute: int = 60
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 5


@dataclass
class APIResponse:
    success: bool = True
    status_code: int = 200
    data: Any = None
    error_code: str = ""
    error_message: str = ""
    request_id: str = ""
    rate_limit_remaining: int = 0
    rate_limit_reset_at: str = ""


@dataclass
class OrderFetchParams:
    start_time: str = ""
    end_time: str = ""
    status: str = ""
    page_size: int = 50
    page_token: str = ""


@dataclass
class OrderItem:
    item_id: str = ""
    sku: str = ""
    title: str = ""
    quantity: int = 0
    unit_price: float = 0.0
    currency: str = "USD"
    item_status: str = ""


@dataclass
class PlatformOrder:
    order_id: str = ""
    platform_order_id: str = ""
    platform: str = ""
    store_id: str = ""
    status: str = ""
    order_date: str = ""
    buyer_name: str = ""
    buyer_email: str = ""
    shipping_address: dict = field(default_factory=dict)
    items: list[OrderItem] = field(default_factory=list)
    total_amount: float = 0.0
    currency: str = "USD"
    shipping_cost: float = 0.0
    tax_amount: float = 0.0
    discount_amount: float = 0.0
    raw_data: dict = field(default_factory=dict)


@dataclass
class InventorySyncItem:
    sku: str = ""
    quantity: int = 0
    warehouse_id: str = ""
    location_id: str = ""


@dataclass
class SyncResult:
    success: bool = True
    synced_count: int = 0
    failed_count: int = 0
    errors: list[dict] = field(default_factory=list)


@dataclass
class ListingUpdateData:
    title: str = ""
    description: str = ""
    price: float = 0.0
    quantity: int = 0
    status: str = ""


@dataclass
class UpdateResult:
    success: bool = True
    listing_id: str = ""
    error_message: str = ""


@dataclass
class ListingFetchParams:
    status: str = ""
    page_size: int = 50
    page_token: str = ""


@dataclass
class PlatformListing:
    listing_id: str = ""
    platform_listing_id: str = ""
    platform: str = ""
    store_id: str = ""
    sku: str = ""
    title: str = ""
    description: str = ""
    price: float = 0.0
    currency: str = "USD"
    quantity: int = 0
    status: str = ""
    images: list[str] = field(default_factory=list)
    raw_data: dict = field(default_factory=dict)


@dataclass
class RateEstimateParams:
    origin_country: str = "CN"
    destination_country: str = "US"
    weight_kg: float = 1.0
    length_cm: float = 0.0
    width_cm: float = 0.0
    height_cm: float = 0.0
    declared_value: float = 0.0
    currency: str = "USD"


@dataclass
class RateOption:
    service_code: str = ""
    service_name: str = ""
    carrier: str = ""
    cost: float = 0.0
    currency: str = "USD"
    estimated_days_min: int = 0
    estimated_days_max: int = 0
    tracking_available: bool = True


@dataclass
class ShipmentCreate:
    order_id: str = ""
    carrier_code: str = ""
    service_code: str = ""
    sender: dict = field(default_factory=dict)
    recipient: dict = field(default_factory=dict)
    items: list[dict] = field(default_factory=list)
    weight_kg: float = 0.0
    dimensions_cm: dict = field(default_factory=dict)
    declared_value: float = 0.0
    currency: str = "USD"
    reference: str = ""


@dataclass
class ShipmentResult:
    success: bool = True
    tracking_number: str = ""
    label_url: str = ""
    carrier: str = ""
    cost: float = 0.0
    currency: str = "USD"
    error_message: str = ""


@dataclass
class TrackingInfo:
    tracking_number: str = ""
    carrier: str = ""
    status: str = ""
    events: list[dict] = field(default_factory=list)
    estimated_delivery: str = ""


@dataclass
class PaymentCreate:
    order_id: str = ""
    amount: float = 0.0
    currency: str = "USD"
    payment_method: str = ""
    return_url: str = ""
    cancel_url: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class PaymentResult:
    success: bool = True
    payment_id: str = ""
    redirect_url: str = ""
    status: str = ""
    error_message: str = ""


@dataclass
class PaymentRefund:
    payment_id: str = ""
    refund_amount: float = 0.0
    currency: str = "USD"
    reason: str = ""


@dataclass
class RefundResult:
    success: bool = True
    refund_id: str = ""
    status: str = ""
    error_message: str = ""


@dataclass
class WarehouseReceipt:
    receipt_id: str = ""
    warehouse_id: str = ""
    items: list[dict] = field(default_factory=list)
    reference: str = ""


@dataclass
class WarehouseReceiptResult:
    success: bool = True
    receipt_id: str = ""
    status: str = ""
    error_message: str = ""


@dataclass
class WarehouseInventoryQuery:
    warehouse_id: str = ""
    sku: str = ""


@dataclass
class WarehouseInventory:
    sku: str = ""
    warehouse_id: str = ""
    quantity_on_hand: int = 0
    quantity_reserved: int = 0
    quantity_available: int = 0
    location: str = ""


class BaseConnector:
    def __init__(self, config: ConnectorConfig):
        self.config = config
        self._status = ConnectorStatus.ACTIVE
        self._last_request_at: str = ""
        self._request_count = 0

    @property
    def connector_type(self) -> str:
        return ""

    @property
    def connector_name(self) -> str:
        return self.config.connector_name

    @property
    def status(self) -> ConnectorStatus:
        return self._status

    def get_request_id(self) -> str:
        return str(uuid.uuid4())

    async def health_check(self) -> bool:
        return self._status == ConnectorStatus.ACTIVE

    def mark_error(self):
        self._status = ConnectorStatus.ERROR

    def mark_active(self):
        self._status = ConnectorStatus.ACTIVE

    def mark_rate_limited(self, reset_at: str = ""):
        self._status = ConnectorStatus.RATE_LIMITED


class PlatformConnector(BaseConnector):
    @property
    def connector_type(self) -> str:
        return ConnectorType.PLATFORM.value

    @abc.abstractmethod
    async def fetch_orders(self, params: OrderFetchParams) -> tuple[list[PlatformOrder], str]:
        ...

    @abc.abstractmethod
    async def sync_inventory(self, items: list[InventorySyncItem]) -> SyncResult:
        ...

    @abc.abstractmethod
    async def update_listing(self, listing_id: str, data: ListingUpdateData) -> UpdateResult:
        ...

    @abc.abstractmethod
    async def fetch_listings(self, params: ListingFetchParams) -> tuple[list[PlatformListing], str]:
        ...


class CarrierConnector(BaseConnector):
    @property
    def connector_type(self) -> str:
        return ConnectorType.LOGISTICS.value

    @abc.abstractmethod
    async def estimate_rate(self, params: RateEstimateParams) -> list[RateOption]:
        ...

    @abc.abstractmethod
    async def create_shipment(self, shipment: ShipmentCreate) -> ShipmentResult:
        ...

    @abc.abstractmethod
    async def get_tracking(self, tracking_number: str) -> TrackingInfo:
        ...

    @abc.abstractmethod
    async def cancel_shipment(self, tracking_number: str) -> bool:
        ...


class PaymentConnector(BaseConnector):
    @property
    def connector_type(self) -> str:
        return ConnectorType.PAYMENT.value

    @abc.abstractmethod
    async def create_payment(self, payment: PaymentCreate) -> PaymentResult:
        ...

    @abc.abstractmethod
    async def query_payment(self, payment_id: str) -> PaymentResult:
        ...

    @abc.abstractmethod
    async def refund(self, refund: PaymentRefund) -> RefundResult:
        ...

    @abc.abstractmethod
    async def get_balance(self, currency: str = "USD") -> dict:
        ...


class WarehouseConnector(BaseConnector):
    @property
    def connector_type(self) -> str:
        return ConnectorType.WAREHOUSE.value

    @abc.abstractmethod
    async def create_receipt(self, receipt: WarehouseReceipt) -> WarehouseReceiptResult:
        ...

    @abc.abstractmethod
    async def query_inventory(self, query: WarehouseInventoryQuery) -> list[WarehouseInventory]:
        ...

    @abc.abstractmethod
    async def create_outbound(self, order_id: str, items: list[dict]) -> dict:
        ...


class ProcurementConnector(BaseConnector):
    @property
    def connector_type(self) -> str:
        return ConnectorType.PROCUREMENT.value

    @abc.abstractmethod
    async def search_products(self, keyword: str, page: int = 1, page_size: int = 20) -> dict:
        ...

    @abc.abstractmethod
    async def get_product_detail(self, product_id: str) -> dict:
        ...

    @abc.abstractmethod
    async def place_order(self, items: list[dict], shipping_address: dict) -> dict:
        ...


class TaxConnector(BaseConnector):
    @property
    def connector_type(self) -> str:
        return ConnectorType.TAX.value

    @abc.abstractmethod
    async def calculate_tax(self, amount: float, country: str, region: str = "", tax_code: str = "") -> dict:
        ...

    @abc.abstractmethod
    async def validate_vat(self, vat_number: str, country: str) -> dict:
        ...
