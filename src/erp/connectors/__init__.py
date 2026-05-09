from erp.connectors.amazon import AmazonConnector
from erp.connectors.base import (
    APIResponse as APIResponse,
)
from erp.connectors.base import (
    BaseConnector as BaseConnector,
)
from erp.connectors.base import (
    CarrierConnector as CarrierConnector,
)
from erp.connectors.base import (
    ConnectorConfig as ConnectorConfig,
)
from erp.connectors.base import (
    ConnectorStatus as ConnectorStatus,
)
from erp.connectors.base import (
    ConnectorType as ConnectorType,
)
from erp.connectors.base import (
    InventorySyncItem as InventorySyncItem,
)
from erp.connectors.base import (
    ListingFetchParams as ListingFetchParams,
)
from erp.connectors.base import (
    ListingUpdateData as ListingUpdateData,
)
from erp.connectors.base import (
    OrderFetchParams as OrderFetchParams,
)
from erp.connectors.base import (
    OrderItem as OrderItem,
)
from erp.connectors.base import (
    PaymentConnector as PaymentConnector,
)
from erp.connectors.base import (
    PaymentCreate as PaymentCreate,
)
from erp.connectors.base import (
    PaymentRefund as PaymentRefund,
)
from erp.connectors.base import (
    PaymentResult as PaymentResult,
)
from erp.connectors.base import (
    PlatformConnector as PlatformConnector,
)
from erp.connectors.base import (
    PlatformListing as PlatformListing,
)
from erp.connectors.base import (
    PlatformOrder as PlatformOrder,
)
from erp.connectors.base import (
    ProcurementConnector as ProcurementConnector,
)
from erp.connectors.base import (
    RateEstimateParams as RateEstimateParams,
)
from erp.connectors.base import (
    RateOption as RateOption,
)
from erp.connectors.base import (
    RefundResult as RefundResult,
)
from erp.connectors.base import (
    ShipmentCreate as ShipmentCreate,
)
from erp.connectors.base import (
    ShipmentResult as ShipmentResult,
)
from erp.connectors.base import (
    SyncResult as SyncResult,
)
from erp.connectors.base import (
    TaxConnector as TaxConnector,
)
from erp.connectors.base import (
    TrackingInfo as TrackingInfo,
)
from erp.connectors.base import (
    UpdateResult as UpdateResult,
)
from erp.connectors.base import (
    WarehouseConnector as WarehouseConnector,
)
from erp.connectors.base import (
    WarehouseInventory as WarehouseInventory,
)
from erp.connectors.base import (
    WarehouseInventoryQuery as WarehouseInventoryQuery,
)
from erp.connectors.base import (
    WarehouseReceipt as WarehouseReceipt,
)
from erp.connectors.base import (
    WarehouseReceiptResult as WarehouseReceiptResult,
)
from erp.connectors.logistics import (
    DHLConnector,
    FedExConnector,
    FourPXConnector,
    UPSConnector,
    YanwenConnector,
)
from erp.connectors.payment import (
    AlipayConnector,
    PayPalConnector,
    StripeConnector,
)
from erp.connectors.procurement import (
    Alibaba1688Connector,
    AlibabaGlobalConnector,
)
from erp.connectors.shopify import ShopifyConnector
from erp.connectors.tax import (
    EuVatConnector,
    UsTaxConnector,
)
from erp.connectors.tiktok_shop import TikTokShopConnector
from erp.connectors.warehouse import (
    FBAConnector,
    ShipBobConnector,
)

CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {
    "amazon": AmazonConnector,
    "shopify": ShopifyConnector,
    "tiktok_shop": TikTokShopConnector,
    "yanwen": YanwenConnector,
    "4px": FourPXConnector,
    "dhl": DHLConnector,
    "fedex": FedExConnector,
    "ups": UPSConnector,
    "paypal": PayPalConnector,
    "stripe": StripeConnector,
    "alipay": AlipayConnector,
    "fba": FBAConnector,
    "shipbob": ShipBobConnector,
    "1688": Alibaba1688Connector,
    "alibaba_global": AlibabaGlobalConnector,
    "eu_vat": EuVatConnector,
    "us_tax": UsTaxConnector,
}


def get_connector(connector_id: str, config: ConnectorConfig | None = None) -> BaseConnector:
    connector_cls = CONNECTOR_REGISTRY.get(connector_id)
    if not connector_cls:
        raise ValueError(f"Unknown connector: {connector_id}")
    return connector_cls(config)


def list_connectors() -> list[dict]:
    return [
        {
            "connector_id": cls(None).config.connector_id if hasattr(cls(None), 'config') else "unknown",
            "connector_name": cls.connector_name if hasattr(cls, 'connector_name') else cls.__name__,
            "connector_type": cls(None).config.connector_type if hasattr(cls(None), 'config') else "unknown",
        }
        for cls in CONNECTOR_REGISTRY.values()
    ]
