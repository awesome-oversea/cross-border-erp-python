from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.inventory_voucher.application.services import InventoryVoucherService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/wms/v1/voucher", tags=["Inventory Voucher - 进销存凭证中台"])


class VoucherCreateRequest(BaseModel):
    voucher_type: str = Field(pattern="^(purchase_in|purchase_return|sales_out|sales_return|transfer_in|transfer_out|adjustment_in|adjustment_out|fba_ship_out|damage_write_off)$")
    warehouse_id: str = Field(min_length=1)
    lines: list[dict]
    reference_type: str = Field(default="")
    reference_id: str = Field(default="")
    operator_id: str = Field(default="")
    remark: str = Field(default="")


class PurchaseGenerateRequest(BaseModel):
    id: str = ""
    warehouse_id: str = ""
    operator_id: str = ""
    items: list[dict] = Field(default_factory=list)


class SalesGenerateRequest(BaseModel):
    id: str = ""
    warehouse_id: str = ""
    operator_id: str = ""
    items: list[dict] = Field(default_factory=list)


@router.post("/create", response_model=None)
async def create_voucher(req: VoucherCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = InventoryVoucherService(session)
    result = await svc.create_voucher(
        tenant_id_var.get(""), voucher_type=req.voucher_type, warehouse_id=req.warehouse_id,
        lines=req.lines, reference_type=req.reference_type, reference_id=req.reference_id,
        operator_id=req.operator_id, remark=req.remark,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.put("/{voucher_no}/post", response_model=None)
async def post_voucher(voucher_no: str, session: AsyncSession = Depends(get_db_session)):
    svc = InventoryVoucherService(session)
    result = await svc.post_voucher(tenant_id_var.get(""), voucher_no)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.put("/{voucher_no}/cancel", response_model=None)
async def cancel_voucher(voucher_no: str, reason: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    svc = InventoryVoucherService(session)
    result = await svc.cancel_voucher(tenant_id_var.get(""), voucher_no, reason)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/generate/purchase", response_model=None)
async def generate_from_purchase(req: PurchaseGenerateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = InventoryVoucherService(session)
    result = await svc.generate_from_purchase(tenant_id_var.get(""), req.model_dump())
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/generate/sales", response_model=None)
async def generate_from_sales(req: SalesGenerateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = InventoryVoucherService(session)
    result = await svc.generate_from_sales(tenant_id_var.get(""), req.model_dump())
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
