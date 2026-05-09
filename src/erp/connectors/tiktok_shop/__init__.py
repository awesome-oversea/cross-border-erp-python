from __future__ import annotations

import uuid
from datetime import UTC, datetime

from erp.connectors.base import (
    ConnectorConfig,
    InventorySyncItem,
    ListingFetchParams,
    ListingUpdateData,
    OrderFetchParams,
    OrderItem,
    PlatformConnector,
    PlatformListing,
    PlatformOrder,
    SyncResult,
    UpdateResult,
)


class TikTokShopConnector(PlatformConnector):
    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="tiktok_shop",
            connector_name="TikTok Shop",
            connector_type="platform",
            base_url="https://open-api.tiktokglobalshop.com",
        ))

    async def fetch_orders(self, params: OrderFetchParams) -> tuple[list[PlatformOrder], str]:
        order = PlatformOrder(
            order_id=str(uuid.uuid4()),
            platform_order_id=f"TT-{uuid.uuid4().hex[:8].upper()}",
            platform="tiktok_shop",
            store_id=self.config.store_id,
            status=params.status or "UNPAID",
            order_date=datetime.now(UTC).isoformat(),
            buyer_name="TikTok Buyer",
            items=[
                OrderItem(
                    item_id=str(uuid.uuid4()),
                    sku="TT-SKU-001",
                    title="TikTok Shop Product",
                    quantity=1,
                    unit_price=15.99,
                    currency="USD",
                ),
            ],
            total_amount=15.99,
            currency="USD",
            shipping_cost=3.99,
        )
        return [order], ""

    async def sync_inventory(self, items: list[InventorySyncItem]) -> SyncResult:
        synced = 0
        failed = 0
        errors = []
        for item in items:
            if item.sku and item.quantity >= 0:
                synced += 1
            else:
                failed += 1
                errors.append({"sku": item.sku, "error": "Invalid SKU or quantity"})
        return SyncResult(success=failed == 0, synced_count=synced, failed_count=failed, errors=errors)

    async def update_listing(self, listing_id: str, data: ListingUpdateData) -> UpdateResult:
        if not listing_id:
            return UpdateResult(success=False, listing_id=listing_id, error_message="Listing ID required")
        return UpdateResult(success=True, listing_id=listing_id)

    async def fetch_listings(self, params: ListingFetchParams) -> tuple[list[PlatformListing], str]:
        listing = PlatformListing(
            listing_id=str(uuid.uuid4()),
            platform_listing_id=f"TT-PROD-{uuid.uuid4().hex[:8].upper()}",
            platform="tiktok_shop",
            store_id=self.config.store_id,
            sku="TT-SKU-001",
            title="TikTok Shop Listing",
            price=15.99,
            currency="USD",
            quantity=30,
            status=params.status or "PENDING_REVIEW",
        )
        return [listing], ""
