from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from erp.connectors import (
    CONNECTOR_REGISTRY,
    get_connector,
    list_connectors,
)
from erp.shared.context import trace_id_var
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from erp.connectors.base import (
        InventorySyncItem,
        ListingFetchParams,
        ListingUpdateData,
        OrderFetchParams,
        PaymentCreate,
        PaymentRefund,
        RateEstimateParams,
        ShipmentCreate,
        WarehouseInventoryQuery,
        WarehouseReceipt,
    )

router = APIRouter(prefix="/connectors", tags=["Connectors"])


@router.get("")
async def list_all_connectors():
    connectors = list_connectors()
    return Result.ok(data=connectors, trace_id=trace_id_var.get(""))


@router.get("/{connector_id}")
async def get_connector_info(connector_id: str):
    if connector_id not in CONNECTOR_REGISTRY:
        return Result.fail(code=404, message=f"Connector not found: {connector_id}", trace_id=trace_id_var.get(""))
    connector = get_connector(connector_id)
    return Result.ok(
        data={
            "connector_id": connector.config.connector_id,
            "connector_name": connector.connector_name,
            "connector_type": connector.connector_type,
            "status": connector.status,
        },
        trace_id=trace_id_var.get(""),
    )


@router.get("/{connector_id}/health")
async def check_connector_health(connector_id: str):
    if connector_id not in CONNECTOR_REGISTRY:
        return Result.fail(code=404, message=f"Connector not found: {connector_id}", trace_id=trace_id_var.get(""))
    connector = get_connector(connector_id)
    healthy = await connector.health_check()
    return Result.ok(data={"healthy": healthy}, trace_id=trace_id_var.get(""))


@router.post("/platform/{connector_id}/fetch-orders")
async def fetch_orders(connector_id: str, params: OrderFetchParams):
    if connector_id not in CONNECTOR_REGISTRY:
        return Result.fail(code=404, message=f"Connector not found: {connector_id}", trace_id=trace_id_var.get(""))
    connector = get_connector(connector_id)
    orders, next_token = await connector.fetch_orders(params)
    return Result.ok(
        data={
            "orders": [o.__dict__ for o in orders],
            "next_token": next_token,
            "count": len(orders),
        },
        trace_id=trace_id_var.get(""),
    )


@router.post("/platform/{connector_id}/sync-inventory")
async def sync_inventory(connector_id: str, items: list[InventorySyncItem]):
    if connector_id not in CONNECTOR_REGISTRY:
        return Result.fail(code=404, message=f"Connector not found: {connector_id}", trace_id=trace_id_var.get(""))
    connector = get_connector(connector_id)
    result = await connector.sync_inventory(items)
    return Result.ok(data=result.__dict__, trace_id=trace_id_var.get(""))


@router.post("/platform/{connector_id}/update-listing")
async def update_listing(connector_id: str, listing_id: str, data: ListingUpdateData):
    if connector_id not in CONNECTOR_REGISTRY:
        return Result.fail(code=404, message=f"Connector not found: {connector_id}", trace_id=trace_id_var.get(""))
    connector = get_connector(connector_id)
    result = await connector.update_listing(listing_id, data)
    return Result.ok(data=result.__dict__, trace_id=trace_id_var.get(""))


@router.post("/platform/{connector_id}/fetch-listings")
async def fetch_listings(connector_id: str, params: ListingFetchParams):
    if connector_id not in CONNECTOR_REGISTRY:
        return Result.fail(code=404, message=f"Connector not found: {connector_id}", trace_id=trace_id_var.get(""))
    connector = get_connector(connector_id)
    listings, next_token = await connector.fetch_listings(params)
    return Result.ok(
        data={
            "listings": [item.__dict__ for item in listings],
            "next_token": next_token,
            "count": len(listings),
        },
        trace_id=trace_id_var.get(""),
    )


@router.post("/logistics/{connector_id}/estimate-rate")
async def estimate_rate(connector_id: str, params: RateEstimateParams):
    if connector_id not in CONNECTOR_REGISTRY:
        return Result.fail(code=404, message=f"Connector not found: {connector_id}", trace_id=trace_id_var.get(""))
    connector = get_connector(connector_id)
    rates = await connector.estimate_rate(params)
    return Result.ok(
        data=[r.__dict__ for r in rates],
        trace_id=trace_id_var.get(""),
    )


@router.post("/logistics/{connector_id}/create-shipment")
async def create_shipment(connector_id: str, shipment: ShipmentCreate):
    if connector_id not in CONNECTOR_REGISTRY:
        return Result.fail(code=404, message=f"Connector not found: {connector_id}", trace_id=trace_id_var.get(""))
    connector = get_connector(connector_id)
    result = await connector.create_shipment(shipment)
    return Result.ok(data=result.__dict__, trace_id=trace_id_var.get(""))


@router.get("/logistics/{connector_id}/tracking/{tracking_number}")
async def get_tracking(connector_id: str, tracking_number: str):
    if connector_id not in CONNECTOR_REGISTRY:
        return Result.fail(code=404, message=f"Connector not found: {connector_id}", trace_id=trace_id_var.get(""))
    connector = get_connector(connector_id)
    info = await connector.get_tracking(tracking_number)
    return Result.ok(data=info.__dict__, trace_id=trace_id_var.get(""))


@router.post("/payment/{connector_id}/create-payment")
async def create_payment(connector_id: str, payment: PaymentCreate):
    if connector_id not in CONNECTOR_REGISTRY:
        return Result.fail(code=404, message=f"Connector not found: {connector_id}", trace_id=trace_id_var.get(""))
    connector = get_connector(connector_id)
    result = await connector.create_payment(payment)
    return Result.ok(data=result.__dict__, trace_id=trace_id_var.get(""))


@router.post("/payment/{connector_id}/refund")
async def refund_payment(connector_id: str, refund: PaymentRefund):
    if connector_id not in CONNECTOR_REGISTRY:
        return Result.fail(code=404, message=f"Connector not found: {connector_id}", trace_id=trace_id_var.get(""))
    connector = get_connector(connector_id)
    result = await connector.refund(refund)
    return Result.ok(data=result.__dict__, trace_id=trace_id_var.get(""))


@router.post("/warehouse/{connector_id}/create-receipt")
async def create_warehouse_receipt(connector_id: str, receipt: WarehouseReceipt):
    if connector_id not in CONNECTOR_REGISTRY:
        return Result.fail(code=404, message=f"Connector not found: {connector_id}", trace_id=trace_id_var.get(""))
    connector = get_connector(connector_id)
    result = await connector.create_receipt(receipt)
    return Result.ok(data=result.__dict__, trace_id=trace_id_var.get(""))


@router.post("/warehouse/{connector_id}/query-inventory")
async def query_warehouse_inventory(connector_id: str, query: WarehouseInventoryQuery):
    if connector_id not in CONNECTOR_REGISTRY:
        return Result.fail(code=404, message=f"Connector not found: {connector_id}", trace_id=trace_id_var.get(""))
    connector = get_connector(connector_id)
    items = await connector.query_inventory(query)
    return Result.ok(data=[i.__dict__ for i in items], trace_id=trace_id_var.get(""))
