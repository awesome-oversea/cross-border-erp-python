"""
WMS 模块主路由

内部域路径规范: /wms/v1/{resource}
涵盖: 仓库、库位、库存、入库、出库、质检、盘点、调拨、FBA补货、快照、预警
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query

from erp.modules.wms.application.dtos import (
    AlertResponse,
    AlertRuleCreateRequest,
    AlertRuleResponse,
    AlertRuleUpdateRequest,
    FBAReplenishmentGenerateRequest,
    FBAReplenishmentListRequest,
    FBAReplenishmentApproveRequest,
    FBAReplenishmentResponse,
    InboundOrderCreateRequest,
    InboundOrderResponse,
    InboundReceiveRequest,
    InventoryResponse,
    InventorySnapshotResponse,
    InventorySummaryResponse,
    LocationCreateRequest,
    LocationResponse,
    OutboundOrderCreateRequest,
    OutboundOrderResponse,
    OutboundShipRequest,
    QualityInspectionCompleteRequest,
    QualityInspectionCreateRequest,
    QualityInspectionPassRateResponse,
    QualityInspectionResponse,
    SnapshotQueryRequest,
    StockAdjustRequest,
    StockCountCreateRequest,
    StockCountResponse,
    StockFreezeRequest,
    StockMovementResponse,
    StockReserveRequest,
    StockUnfreezeRequest,
    StockUnreserveRequest,
    TransferCreateRequest,
    TransferResponse,
    WarehouseCapacityResponse,
    WarehouseCreateRequest,
    WarehouseResponse,
    WarehouseUpdateRequest,
    WMSOverviewResponse,
)
from erp.modules.wms.application.services import (
    InboundService,
    InventoryService,
    LocationService,
    OutboundService,
    QualityInspectionService,
    StockCountService,
    WMSQueryService,
    WarehouseService,
)
from erp.modules.wms.domain.inventory_alert_models import (
    InventoryAlertService,
    InventorySnapshotService,
)
from erp.modules.wms.domain.transfer_replenishment_models import (
    FBAReplenishmentService,
    StockTransferService,
)
from erp.modules.wms.interfaces.deps import (
    get_fba_replenishment_service,
    get_inbound_service,
    get_inventory_alert_service,
    get_inventory_service,
    get_inventory_snapshot_service,
    get_location_service,
    get_outbound_service,
    get_quality_inspection_service,
    get_stock_count_service,
    get_stock_transfer_service,
    get_warehouse_service,
    get_wms_query_service,
)
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import Result

router = APIRouter(prefix="/wms/v1", tags=["WMS"])


@router.post("/warehouses", response_model=None, summary="创建仓库")
async def create_warehouse(
    req: WarehouseCreateRequest,
    svc: WarehouseService = Depends(get_warehouse_service),
):
    wh = await svc.create(
        tenant_id_var.get(""), name=req.name, code=req.code,
        warehouse_type=req.warehouse_type, region=req.region,
        address=req.address, contact_person=req.contact_person,
        contact_phone=req.contact_phone, is_default=req.is_default, org_id=req.org_id,
    )
    return Result.ok(data=WarehouseResponse.model_validate(wh).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/warehouses", response_model=None, summary="查询仓库列表")
async def list_warehouses(
    warehouse_type: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: WarehouseService = Depends(get_warehouse_service),
):
    items, total = await svc.list_all(
        tenant_id_var.get(""), warehouse_type=warehouse_type, page=page, page_size=page_size,
    )
    data = [WarehouseResponse.model_validate(w).model_dump() for w in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/warehouses/{warehouse_id}", response_model=None, summary="查询仓库详情")
async def get_warehouse(
    warehouse_id: str,
    svc: WarehouseService = Depends(get_warehouse_service),
):
    wh = await svc.get_or_raise(warehouse_id, tenant_id_var.get(""))
    return Result.ok(data=WarehouseResponse.model_validate(wh).model_dump(), trace_id=trace_id_var.get(""))


@router.patch("/warehouses/{warehouse_id}", response_model=None, summary="更新仓库")
async def update_warehouse(
    warehouse_id: str,
    req: WarehouseUpdateRequest,
    svc: WarehouseService = Depends(get_warehouse_service),
):
    wh = await svc.update(warehouse_id, tenant_id_var.get(""), **req.model_dump(exclude_none=True))
    return Result.ok(data=WarehouseResponse.model_validate(wh).model_dump(), trace_id=trace_id_var.get(""))


@router.delete("/warehouses/{warehouse_id}", response_model=None, summary="删除仓库")
async def delete_warehouse(
    warehouse_id: str,
    svc: WarehouseService = Depends(get_warehouse_service),
):
    ok = await svc.soft_delete(warehouse_id, tenant_id_var.get(""))
    return Result.ok(data={"deleted": ok}, trace_id=trace_id_var.get(""))


@router.get("/warehouses/{warehouse_id}/capacity", response_model=None, summary="查询仓库容量")
async def get_warehouse_capacity(
    warehouse_id: str,
    svc: InventoryService = Depends(get_inventory_service),
):
    items, total = await svc.query_stock(
        tenant_id_var.get(""), warehouse_id=warehouse_id, sku_id="", page=1, page_size=1000,
    )
    cap = WarehouseCapacityResponse(
        warehouse_id=warehouse_id, total_skus=total,
        total_qty=sum(i.qty_on_hand for i in items),
    )
    return Result.ok(data=cap.model_dump(), trace_id=trace_id_var.get(""))


@router.post("/locations", response_model=None, summary="创建库位")
async def create_location(
    req: LocationCreateRequest,
    svc: LocationService = Depends(get_location_service),
):
    loc = await svc.create(
        tenant_id_var.get(""), warehouse_id=req.warehouse_id, code=req.code,
        name=req.name, zone=req.zone, aisle=req.aisle, shelf=req.shelf,
        bin=req.bin, location_type=req.location_type,
    )
    return Result.ok(data=LocationResponse.model_validate(loc).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/warehouses/{warehouse_id}/locations", response_model=None, summary="查询仓库库位")
async def list_locations(
    warehouse_id: str,
    svc: LocationService = Depends(get_location_service),
):
    items = await svc.list_by_warehouse(warehouse_id, tenant_id_var.get(""))
    data = [LocationResponse.model_validate(item).model_dump() for item in items]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/inventory", response_model=None, summary="查询库存列表")
async def query_inventory(
    warehouse_id: str = Query(default=""),
    sku_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: InventoryService = Depends(get_inventory_service),
):
    items, total = await svc.query_stock(
        tenant_id_var.get(""), warehouse_id=warehouse_id, sku_id=sku_id,
        page=page, page_size=page_size,
    )
    data = [InventoryResponse.model_validate(i).model_dump() for i in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/inventory/adjust", response_model=None, summary="库存调整")
async def adjust_stock(
    req: StockAdjustRequest,
    svc: InventoryService = Depends(get_inventory_service),
):
    inv = await svc.adjust_stock(
        tenant_id_var.get(""), warehouse_id=req.warehouse_id, sku_id=req.sku_id,
        qty_change=req.qty_change, movement_type=req.movement_type,
        reference_type=req.reference_type, reference_id=req.reference_id, remark=req.remark,
    )
    return Result.ok(data=InventoryResponse.model_validate(inv).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/inventory/reserve", response_model=None, summary="预留库存")
async def reserve_stock(
    req: StockReserveRequest,
    svc: InventoryService = Depends(get_inventory_service),
):
    inv = await svc.reserve_stock(
        tenant_id_var.get(""), warehouse_id=req.warehouse_id, sku_id=req.sku_id,
        reserve_qty=req.reserve_qty, reference_type=req.reference_type,
        reference_id=req.reference_id, remark=req.remark,
    )
    return Result.ok(data=InventoryResponse.model_validate(inv).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/inventory/unreserve", response_model=None, summary="释放预留库存")
async def unreserve_stock(
    req: StockUnreserveRequest,
    svc: InventoryService = Depends(get_inventory_service),
):
    inv = await svc.unreserve_stock(
        tenant_id_var.get(""), warehouse_id=req.warehouse_id, sku_id=req.sku_id,
        unreserve_qty=req.unreserve_qty, reference_type=req.reference_type,
        reference_id=req.reference_id, remark=req.remark,
    )
    return Result.ok(data=InventoryResponse.model_validate(inv).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/inventory/freeze", response_model=None, summary="冻结库存")
async def freeze_stock(
    req: StockFreezeRequest,
    svc: InventoryService = Depends(get_inventory_service),
):
    inv = await svc.reserve_stock(
        tenant_id_var.get(""), warehouse_id=req.warehouse_id, sku_id=req.sku_id,
        reserve_qty=req.freeze_qty, remark=req.freeze_reason or "Freeze stock",
    )
    return Result.ok(
        data={"sku_id": inv.sku_id, "qty_on_hand": inv.qty_on_hand, "qty_reserved": inv.qty_reserved},
        trace_id=trace_id_var.get(""),
    )


@router.post("/inventory/unfreeze", response_model=None, summary="解冻库存")
async def unfreeze_stock(
    req: StockUnfreezeRequest,
    svc: InventoryService = Depends(get_inventory_service),
):
    inv = await svc.unreserve_stock(
        tenant_id_var.get(""), warehouse_id=req.warehouse_id, sku_id=req.sku_id,
        unreserve_qty=req.unfreeze_qty, remark="Unfreeze stock",
    )
    return Result.ok(
        data={"sku_id": inv.sku_id, "qty_on_hand": inv.qty_on_hand, "qty_reserved": inv.qty_reserved},
        trace_id=trace_id_var.get(""),
    )


@router.get("/inventory/low-stock", response_model=None, summary="查询低库存")
async def list_low_stock(
    warehouse_id: str = Query(default=""),
    svc: InventoryService = Depends(get_inventory_service),
):
    items = await svc.check_low_stock(tenant_id_var.get(""), warehouse_id=warehouse_id)
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.get("/inventory/summary", response_model=None, summary="库存汇总")
async def inventory_summary(
    warehouse_id: str = Query(default=""),
    svc: InventoryService = Depends(get_inventory_service),
):
    items, total = await svc.query_stock(
        tenant_id_var.get(""), warehouse_id=warehouse_id, sku_id="", page=1, page_size=1000,
    )
    summary = InventorySummaryResponse(
        total_skus=total,
        total_qty_on_hand=sum(i.qty_on_hand for i in items),
        total_qty_reserved=sum(i.qty_reserved for i in items),
        total_qty_available=sum(i.qty_available for i in items),
    )
    return Result.ok(data=summary.model_dump(), trace_id=trace_id_var.get(""))


@router.get("/inventory/movements", response_model=None, summary="查询库存流水")
async def list_stock_movements(
    sku_id: str = Query(default=""),
    reference_type: str = Query(default=""),
    reference_id: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    svc: InventoryService = Depends(get_inventory_service),
):
    movements = await svc.get_stock_movements(
        tenant_id_var.get(""), sku_id=sku_id,
        reference_type=reference_type, reference_id=reference_id, limit=limit,
    )
    data = [StockMovementResponse.model_validate(m).model_dump() for m in movements]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/inbound-orders", response_model=None, summary="创建入库单")
async def create_inbound(
    req: InboundOrderCreateRequest,
    svc: InboundService = Depends(get_inbound_service),
):
    inbound = await svc.create(
        tenant_id_var.get(""), inbound_no=req.inbound_no, warehouse_id=req.warehouse_id,
        inbound_type=req.inbound_type, source_id=req.source_id,
        items_json=json.dumps(req.items, default=str), remark=req.remark,
    )
    return Result.ok(data=InboundOrderResponse.model_validate(inbound).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/inbound-orders", response_model=None, summary="查询入库单列表")
async def list_inbound_orders(
    status: str = Query(default=""),
    warehouse_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: InboundService = Depends(get_inbound_service),
):
    items, total = await svc.list_all(
        tenant_id_var.get(""), status=status, warehouse_id=warehouse_id,
        page=page, page_size=page_size,
    )
    data = [InboundOrderResponse.model_validate(i).model_dump() for i in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/inbound-orders/{inbound_id}", response_model=None, summary="查询入库单详情")
async def get_inbound_order(
    inbound_id: str,
    svc: InboundService = Depends(get_inbound_service),
):
    inbound = await svc.get_or_raise(inbound_id, tenant_id_var.get(""))
    return Result.ok(data=InboundOrderResponse.model_validate(inbound).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/inbound-orders/{inbound_id}/receive", response_model=None, summary="入库收货")
async def receive_inbound(
    inbound_id: str,
    req: InboundReceiveRequest,
    svc: InboundService = Depends(get_inbound_service),
):
    inbound = await svc.receive(inbound_id, tenant_id_var.get(""), received_items=req.items)
    return Result.ok(
        data={"id": inbound.id, "status": inbound.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/inbound-orders/{inbound_id}/cancel", response_model=None, summary="取消入库单")
async def cancel_inbound(
    inbound_id: str,
    svc: InboundService = Depends(get_inbound_service),
):
    inbound = await svc.cancel(inbound_id, tenant_id_var.get(""))
    return Result.ok(data={"id": inbound.id, "status": inbound.status}, trace_id=trace_id_var.get(""))


@router.post("/outbound-orders", response_model=None, summary="创建出库单")
async def create_outbound(
    req: OutboundOrderCreateRequest,
    svc: OutboundService = Depends(get_outbound_service),
):
    outbound = await svc.create(
        tenant_id_var.get(""), outbound_no=req.outbound_no, warehouse_id=req.warehouse_id,
        outbound_type=req.outbound_type, source_id=req.source_id,
        items_json=json.dumps(req.items, default=str), remark=req.remark,
    )
    return Result.ok(data=OutboundOrderResponse.model_validate(outbound).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/outbound-orders", response_model=None, summary="查询出库单列表")
async def list_outbound_orders(
    status: str = Query(default=""),
    warehouse_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: OutboundService = Depends(get_outbound_service),
):
    items, total = await svc.list_all(
        tenant_id_var.get(""), status=status, warehouse_id=warehouse_id,
        page=page, page_size=page_size,
    )
    data = [OutboundOrderResponse.model_validate(i).model_dump() for i in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/outbound-orders/{outbound_id}", response_model=None, summary="查询出库单详情")
async def get_outbound_order(
    outbound_id: str,
    svc: OutboundService = Depends(get_outbound_service),
):
    outbound = await svc.get_or_raise(outbound_id, tenant_id_var.get(""))
    return Result.ok(data=OutboundOrderResponse.model_validate(outbound).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/outbound-orders/{outbound_id}/ship", response_model=None, summary="出库发货")
async def ship_outbound(
    outbound_id: str,
    req: OutboundShipRequest,
    svc: OutboundService = Depends(get_outbound_service),
):
    outbound = await svc.ship(
        outbound_id, tenant_id_var.get(""), shipped_items=req.items,
        tracking_no=req.tracking_no, logistics_channel=req.logistics_channel,
    )
    return Result.ok(
        data={"id": outbound.id, "status": outbound.status, "tracking_no": outbound.tracking_no},
        trace_id=trace_id_var.get(""),
    )


@router.post("/outbound-orders/{outbound_id}/cancel", response_model=None, summary="取消出库单")
async def cancel_outbound(
    outbound_id: str,
    svc: OutboundService = Depends(get_outbound_service),
):
    outbound = await svc.cancel(outbound_id, tenant_id_var.get(""))
    return Result.ok(data={"id": outbound.id, "status": outbound.status}, trace_id=trace_id_var.get(""))


@router.post("/quality-inspections", response_model=None, summary="创建质检单")
async def create_quality_inspection(
    req: QualityInspectionCreateRequest,
    svc: QualityInspectionService = Depends(get_quality_inspection_service),
):
    inspection = await svc.create(
        tenant_id_var.get(""), inspection_no=req.inspection_no,
        warehouse_id=req.warehouse_id, sku_id=req.sku_id,
        quantity_inspected=req.quantity_inspected,
        quantity_passed=req.quantity_passed, quantity_failed=req.quantity_failed,
        defect_type=req.defect_type, defect_description=req.defect_description,
        inspector_id=req.inspector_id, remark=req.remark,
    )
    return Result.ok(data=QualityInspectionResponse.model_validate(inspection).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/quality-inspections", response_model=None, summary="查询质检单列表")
async def list_quality_inspections(
    warehouse_id: str = Query(default=""),
    result: str = Query(default=""),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    svc: QualityInspectionService = Depends(get_quality_inspection_service),
):
    items = await svc.list_by_warehouse(
        tenant_id_var.get(""), warehouse_id=warehouse_id, result=result,
        offset=offset, limit=limit,
    )
    data = [QualityInspectionResponse.model_validate(i).model_dump() for i in items]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/quality-inspections/{inspection_id}/complete", response_model=None, summary="完成质检")
async def complete_quality_inspection(
    inspection_id: str,
    req: QualityInspectionCompleteRequest,
    svc: QualityInspectionService = Depends(get_quality_inspection_service),
):
    inspection = await svc.complete_inspection(
        inspection_id, tenant_id_var.get(""),
        quantity_passed=req.quantity_passed, quantity_failed=req.quantity_failed,
        defect_type=req.defect_type, defect_description=req.defect_description,
        inspector_id=req.inspector_id,
    )
    return Result.ok(data=QualityInspectionResponse.model_validate(inspection).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/quality-inspections/pass-rate", response_model=None, summary="质检合格率统计")
async def get_quality_pass_rate(
    warehouse_id: str = Query(default=""),
    svc: QualityInspectionService = Depends(get_quality_inspection_service),
):
    stats = await svc.get_pass_rate(tenant_id_var.get(""), warehouse_id=warehouse_id)
    return Result.ok(data=QualityInspectionPassRateResponse(**stats).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/stock-counts", response_model=None, summary="创建盘点单")
async def create_stock_count(
    req: StockCountCreateRequest,
    svc: StockCountService = Depends(get_stock_count_service),
):
    count = await svc.create(
        tenant_id_var.get(""), count_no=req.count_no, warehouse_id=req.warehouse_id,
        count_type=req.count_type,
    )
    return Result.ok(data=StockCountResponse.model_validate(count).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/stock-counts", response_model=None, summary="查询盘点单列表")
async def list_stock_counts(
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: StockCountService = Depends(get_stock_count_service),
):
    items, total = await svc.list_all(
        tenant_id_var.get(""), status=status, page=page, page_size=page_size,
    )
    data = [StockCountResponse.model_validate(c).model_dump() for c in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/stock-counts/{count_id}", response_model=None, summary="查询盘点单详情")
async def get_stock_count(
    count_id: str,
    svc: StockCountService = Depends(get_stock_count_service),
):
    count = await svc.get_or_raise(count_id, tenant_id_var.get(""))
    return Result.ok(data=StockCountResponse.model_validate(count).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/stock-counts/{count_id}/start", response_model=None, summary="开始盘点")
async def start_stock_count(
    count_id: str,
    svc: StockCountService = Depends(get_stock_count_service),
):
    count = await svc.start_count(count_id, tenant_id_var.get(""))
    return Result.ok(data={"id": count.id, "status": count.status}, trace_id=trace_id_var.get(""))


@router.post("/stock-counts/{count_id}/submit", response_model=None, summary="提交盘点结果")
async def submit_stock_count_result(
    count_id: str,
    count_items: list[dict],
    svc: StockCountService = Depends(get_stock_count_service),
):
    count = await svc.submit_count_result(count_id, tenant_id_var.get(""), count_items=count_items)
    return Result.ok(data=StockCountResponse.model_validate(count).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/transfers", response_model=None, summary="创建调拨单")
async def create_transfer(
    req: TransferCreateRequest,
    svc: StockTransferService = Depends(get_stock_transfer_service),
):
    transfer = await svc.create_transfer(
        tenant_id_var.get(""), from_warehouse_id=req.from_warehouse_id,
        to_warehouse_id=req.to_warehouse_id, items=req.items, reason=req.reason,
    )
    return Result.ok(data=TransferResponse.model_validate(transfer).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/transfers", response_model=None, summary="查询调拨单列表")
async def list_transfers(
    status: str = Query(default=""),
    from_warehouse_id: str = Query(default=""),
    to_warehouse_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: StockTransferService = Depends(get_stock_transfer_service),
):
    items, total = await svc.list_transfers(
        tenant_id_var.get(""), status=status,
        from_warehouse_id=from_warehouse_id, to_warehouse_id=to_warehouse_id,
        page=page, page_size=page_size,
    )
    data = [TransferResponse.model_validate(t).model_dump() for t in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/transfers/{transfer_id}/submit", response_model=None, summary="提交调拨单")
async def submit_transfer(
    transfer_id: str,
    svc: StockTransferService = Depends(get_stock_transfer_service),
):
    transfer = await svc.submit_transfer(transfer_id, tenant_id_var.get(""))
    return Result.ok(data={"id": transfer.id, "status": transfer.status}, trace_id=trace_id_var.get(""))


@router.post("/transfers/{transfer_id}/ship", response_model=None, summary="调拨发货")
async def ship_transfer(
    transfer_id: str,
    svc: StockTransferService = Depends(get_stock_transfer_service),
):
    transfer = await svc.ship_transfer(transfer_id, tenant_id_var.get(""))
    return Result.ok(data={"id": transfer.id, "status": transfer.status}, trace_id=trace_id_var.get(""))


@router.post("/transfers/{transfer_id}/receive", response_model=None, summary="调拨收货")
async def receive_transfer(
    transfer_id: str,
    svc: StockTransferService = Depends(get_stock_transfer_service),
):
    transfer = await svc.receive_transfer(transfer_id, tenant_id_var.get(""))
    return Result.ok(data={"id": transfer.id, "status": transfer.status}, trace_id=trace_id_var.get(""))


@router.post("/transfers/{transfer_id}/cancel", response_model=None, summary="取消调拨单")
async def cancel_transfer(
    transfer_id: str,
    svc: StockTransferService = Depends(get_stock_transfer_service),
):
    transfer = await svc.cancel_transfer(transfer_id, tenant_id_var.get(""))
    return Result.ok(data={"id": transfer.id, "status": transfer.status}, trace_id=trace_id_var.get(""))


@router.post("/fba-replenishment/generate", response_model=None, summary="生成FBA补货计划")
async def generate_fba_replenishment(
    req: FBAReplenishmentGenerateRequest,
    svc: FBAReplenishmentService = Depends(get_fba_replenishment_service),
):
    plan = await svc.generate_replenishment_plan(
        tenant_id_var.get(""), sku_id=req.sku_id,
        fba_warehouse_id=req.fba_warehouse_id, source_warehouse_id=req.source_warehouse_id,
        current_fba_qty=req.current_fba_qty, avg_daily_sales=req.avg_daily_sales,
        lead_time_days=req.lead_time_days, safety_stock_days=req.safety_stock_days,
        strategy=req.strategy, strategy_params=req.strategy_params,
    )
    return Result.ok(data=FBAReplenishmentResponse.model_validate(plan).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/fba-replenishment", response_model=None, summary="查询FBA补货计划列表")
async def list_fba_replenishment(
    sku_id: str = Query(default=""),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: FBAReplenishmentService = Depends(get_fba_replenishment_service),
):
    items, total = await svc.list_plans(
        tenant_id_var.get(""), sku_id=sku_id, status=status,
        page=page, page_size=page_size,
    )
    data = [FBAReplenishmentResponse.model_validate(p).model_dump() for p in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/fba-replenishment/{plan_id}/submit", response_model=None, summary="提交FBA补货计划")
async def submit_fba_replenishment(
    plan_id: str,
    svc: FBAReplenishmentService = Depends(get_fba_replenishment_service),
):
    plan = await svc.submit_plan(plan_id, tenant_id_var.get(""))
    return Result.ok(data={"id": plan.id, "status": plan.status}, trace_id=trace_id_var.get(""))


@router.post("/fba-replenishment/{plan_id}/approve", response_model=None, summary="审批FBA补货计划")
async def approve_fba_replenishment(
    plan_id: str,
    req: FBAReplenishmentApproveRequest,
    svc: FBAReplenishmentService = Depends(get_fba_replenishment_service),
):
    plan = await svc.approve_plan(plan_id, tenant_id_var.get(""), approved_qty=req.approved_qty)
    return Result.ok(data={"id": plan.id, "status": plan.status, "approved_qty": plan.approved_qty}, trace_id=trace_id_var.get(""))


@router.post("/inventory-snapshots/take", response_model=None, summary="生成库存快照")
async def take_inventory_snapshot(
    snapshot_date: str = Query(default=""),
    svc: InventorySnapshotService = Depends(get_inventory_snapshot_service),
):
    count = await svc.take_snapshot(tenant_id_var.get(""), snapshot_date=snapshot_date or None)
    return Result.ok(data={"snapshot_date": snapshot_date, "records": count}, trace_id=trace_id_var.get(""))


@router.get("/inventory-snapshots", response_model=None, summary="查询库存快照")
async def query_inventory_snapshot(
    snapshot_date: str = Query(..., min_length=1),
    warehouse_id: str = Query(default=""),
    sku_id: str = Query(default=""),
    svc: InventorySnapshotService = Depends(get_inventory_snapshot_service),
):
    snapshots = await svc.get_snapshot(
        tenant_id_var.get(""), snapshot_date=snapshot_date,
        warehouse_id=warehouse_id, sku_id=sku_id,
    )
    data = [InventorySnapshotResponse.model_validate(s).model_dump() for s in snapshots]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/alert-rules", response_model=None, summary="创建预警规则")
async def create_alert_rule(
    req: AlertRuleCreateRequest,
    svc: InventoryAlertService = Depends(get_inventory_alert_service),
):
    rule = await svc.create_alert_rule(
        tenant_id_var.get(""), rule_name=req.rule_name, alert_type=req.alert_type,
        severity=req.severity, condition=req.condition,
        warehouse_scope=req.warehouse_scope, sku_scope=req.sku_scope,
        category_scope=req.category_scope, cooldown_hours=req.cooldown_hours,
        notify_channels=req.notify_channels,
    )
    return Result.ok(data=AlertRuleResponse.model_validate(rule).model_dump(), trace_id=trace_id_var.get(""))


@router.get("/alert-rules", response_model=None, summary="查询预警规则列表")
async def list_alert_rules(
    svc: InventoryAlertService = Depends(get_inventory_alert_service),
):
    rules = await svc.list_rules(tenant_id_var.get(""))
    data = [AlertRuleResponse.model_validate(r).model_dump() for r in rules]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.patch("/alert-rules/{rule_id}", response_model=None, summary="更新预警规则")
async def update_alert_rule(
    rule_id: str,
    req: AlertRuleUpdateRequest,
    svc: InventoryAlertService = Depends(get_inventory_alert_service),
):
    update_data = req.model_dump(exclude_none=True)
    rule = await svc.update_rule(rule_id, tenant_id_var.get(""), **update_data)
    return Result.ok(data=AlertRuleResponse.model_validate(rule).model_dump(), trace_id=trace_id_var.get(""))


@router.post("/alerts/evaluate", response_model=None, summary="评估预警")
async def evaluate_alerts(
    svc: InventoryAlertService = Depends(get_inventory_alert_service),
):
    alerts = await svc.evaluate_alerts(tenant_id_var.get(""))
    data = [AlertResponse.model_validate(a).model_dump() for a in alerts]
    return Result.ok(data={"triggered_count": len(data), "alerts": data}, trace_id=trace_id_var.get(""))


@router.get("/alerts", response_model=None, summary="查询预警列表")
async def list_alerts(
    alert_type: str = Query(default=""),
    severity: str = Query(default=""),
    status: str = Query(default=""),
    warehouse_id: str = Query(default=""),
    sku_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: InventoryAlertService = Depends(get_inventory_alert_service),
):
    items, total = await svc.list_alerts(
        tenant_id_var.get(""), alert_type=alert_type, severity=severity,
        status=status, warehouse_id=warehouse_id, sku_id=sku_id,
        page=page, page_size=page_size,
    )
    data = [AlertResponse.model_validate(a).model_dump() for a in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/alerts/{alert_id}/acknowledge", response_model=None, summary="确认预警")
async def acknowledge_alert(
    alert_id: str,
    svc: InventoryAlertService = Depends(get_inventory_alert_service),
):
    alert = await svc.acknowledge_alert(alert_id, tenant_id_var.get(""))
    return Result.ok(data={"id": alert.id, "status": alert.status}, trace_id=trace_id_var.get(""))


@router.post("/alerts/{alert_id}/resolve", response_model=None, summary="解决预警")
async def resolve_alert(
    alert_id: str,
    resolution_note: str = Query(default=""),
    svc: InventoryAlertService = Depends(get_inventory_alert_service),
):
    alert = await svc.resolve_alert(alert_id, tenant_id_var.get(""), resolution_note=resolution_note)
    return Result.ok(data={"id": alert.id, "status": alert.status}, trace_id=trace_id_var.get(""))


@router.post("/alert-rules/init-defaults", response_model=None, summary="初始化默认预警规则")
async def init_default_alert_rules(
    svc: InventoryAlertService = Depends(get_inventory_alert_service),
):
    rules = await svc.init_default_rules(tenant_id_var.get(""))
    data = [AlertRuleResponse.model_validate(r).model_dump() for r in rules]
    return Result.ok(data={"created_count": len(data), "rules": data}, trace_id=trace_id_var.get(""))


@router.get("/statistics/overview", response_model=None, summary="WMS运营总览")
async def get_wms_overview(
    svc: WMSQueryService = Depends(get_wms_query_service),
):
    data = await svc.get_overview(tenant_id_var.get(""))
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/statistics/warehouses", response_model=None, summary="仓库统计")
async def get_warehouse_statistics(
    svc: WMSQueryService = Depends(get_wms_query_service),
):
    data = await svc.get_warehouse_statistics(tenant_id_var.get(""))
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/statistics/inventory", response_model=None, summary="库存统计")
async def get_inventory_statistics(
    warehouse_id: str = Query(default=""),
    svc: WMSQueryService = Depends(get_wms_query_service),
):
    data = await svc.get_inventory_statistics(tenant_id_var.get(""), warehouse_id=warehouse_id)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/statistics/inbound", response_model=None, summary="入库统计")
async def get_inbound_statistics(
    warehouse_id: str = Query(default=""),
    svc: WMSQueryService = Depends(get_wms_query_service),
):
    data = await svc.get_inbound_statistics(tenant_id_var.get(""), warehouse_id=warehouse_id)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/statistics/outbound", response_model=None, summary="出库统计")
async def get_outbound_statistics(
    warehouse_id: str = Query(default=""),
    svc: WMSQueryService = Depends(get_wms_query_service),
):
    data = await svc.get_outbound_statistics(tenant_id_var.get(""), warehouse_id=warehouse_id)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/statistics/stock-counts", response_model=None, summary="盘点统计")
async def get_stock_count_statistics(
    svc: WMSQueryService = Depends(get_wms_query_service),
):
    data = await svc.get_stock_count_statistics(tenant_id_var.get(""))
    return Result.ok(data=data, trace_id=trace_id_var.get(""))
