"""
WMS 调拨与FBA补货路由

内部域路径规范: /wms/api/v1/{resource}
涵盖: 调拨单、FBA补货计划
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from erp.modules.wms.application.dtos import (
    FBAReplenishmentApproveRequest,
    FBAReplenishmentGenerateRequest,
    FBAReplenishmentResponse,
    TransferCreateRequest,
    TransferResponse,
)
from erp.modules.wms.domain.transfer_replenishment_models import (
    FBAReplenishmentService,
    StockTransferService,
)
from erp.modules.wms.interfaces.deps import (
    get_fba_replenishment_service,
    get_stock_transfer_service,
)
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import Result

router = APIRouter(prefix="/wms/v1", tags=["WMS-Transfer&Replenishment"])


@router.post("/stock-transfers", response_model=None)
async def create_transfer(
    req: TransferCreateRequest,
    svc: StockTransferService = Depends(get_stock_transfer_service),
):
    transfer = await svc.create_transfer(
        tenant_id_var.get(""), from_warehouse_id=req.from_warehouse_id,
        to_warehouse_id=req.to_warehouse_id, items=req.items, reason=req.reason,
    )
    return Result.ok(
        data=TransferResponse.model_validate(transfer).model_dump(),
        trace_id=trace_id_var.get(""),
    )


@router.get("/stock-transfers", response_model=None)
async def list_transfers(
    status: str = Query(default=""),
    from_warehouse_id: str = Query(default=""),
    to_warehouse_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: StockTransferService = Depends(get_stock_transfer_service),
):
    transfers, total = await svc.list_transfers(
        tenant_id_var.get(""), status=status,
        from_warehouse_id=from_warehouse_id, to_warehouse_id=to_warehouse_id,
        page=page, page_size=page_size,
    )
    data = [TransferResponse.model_validate(t).model_dump() for t in transfers]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/stock-transfers/{transfer_id}/submit", response_model=None)
async def submit_transfer(
    transfer_id: str,
    svc: StockTransferService = Depends(get_stock_transfer_service),
):
    transfer = await svc.submit_transfer(transfer_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": transfer.id, "status": transfer.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/stock-transfers/{transfer_id}/ship", response_model=None)
async def ship_transfer(
    transfer_id: str,
    svc: StockTransferService = Depends(get_stock_transfer_service),
):
    transfer = await svc.ship_transfer(transfer_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": transfer.id, "status": transfer.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/stock-transfers/{transfer_id}/receive", response_model=None)
async def receive_transfer(
    transfer_id: str,
    svc: StockTransferService = Depends(get_stock_transfer_service),
):
    transfer = await svc.receive_transfer(transfer_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": transfer.id, "status": transfer.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/stock-transfers/{transfer_id}/cancel", response_model=None)
async def cancel_transfer(
    transfer_id: str,
    svc: StockTransferService = Depends(get_stock_transfer_service),
):
    transfer = await svc.cancel_transfer(transfer_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": transfer.id, "status": transfer.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/fba-replenishment", response_model=None)
async def generate_replenishment(
    req: FBAReplenishmentGenerateRequest,
    svc: FBAReplenishmentService = Depends(get_fba_replenishment_service),
):
    plan = await svc.generate_replenishment_plan(
        tenant_id_var.get(""), sku_id=req.sku_id,
        fba_warehouse_id=req.fba_warehouse_id,
        source_warehouse_id=req.source_warehouse_id,
        current_fba_qty=req.current_fba_qty, avg_daily_sales=req.avg_daily_sales,
        lead_time_days=req.lead_time_days, safety_stock_days=req.safety_stock_days,
        strategy=req.strategy, strategy_params=req.strategy_params,
    )
    return Result.ok(
        data=FBAReplenishmentResponse.model_validate(plan).model_dump(),
        trace_id=trace_id_var.get(""),
    )


@router.get("/fba-replenishment", response_model=None)
async def list_replenishment_plans(
    sku_id: str = Query(default=""),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: FBAReplenishmentService = Depends(get_fba_replenishment_service),
):
    plans, total = await svc.list_plans(
        tenant_id_var.get(""), sku_id=sku_id, status=status,
        page=page, page_size=page_size,
    )
    data = [FBAReplenishmentResponse.model_validate(p).model_dump() for p in plans]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/fba-replenishment/{plan_id}/submit", response_model=None)
async def submit_replenishment(
    plan_id: str,
    svc: FBAReplenishmentService = Depends(get_fba_replenishment_service),
):
    plan = await svc.submit_plan(plan_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": plan.id, "status": plan.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/fba-replenishment/{plan_id}/approve", response_model=None)
async def approve_replenishment(
    plan_id: str,
    req: FBAReplenishmentApproveRequest,
    svc: FBAReplenishmentService = Depends(get_fba_replenishment_service),
):
    plan = await svc.approve_plan(plan_id, tenant_id_var.get(""), approved_qty=req.approved_qty)
    return Result.ok(
        data={"id": plan.id, "status": plan.status, "approved_qty": plan.approved_qty},
        trace_id=trace_id_var.get(""),
    )
