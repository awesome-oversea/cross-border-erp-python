from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from erp.shared.context import trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/fms/out/v1", tags=["FMS-Outbound"])


class JournalEntryExportRequest(BaseModel):
    period_start: str = ""
    period_end: str = ""
    account_codes: list[str] = []


class KingdeePushRequest(BaseModel):
    period: str = ""
    warehouse_ids: list[str] = []


@router.get("/pms/cost/{asin}", response_model=None)
async def get_cost_for_pms(asin: str, session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"asin": asin, "cost_amount": 0.0, "currency": "CNY",
                           "cost_components": {"purchase": 0.0, "logistics": 0.0,
                                               "fba_fee": 0.0, "other": 0.0}},
                     trace_id=trace_id_var.get(""))


@router.get("/pms/profit/{asin}", response_model=None)
async def get_profit_for_pms(asin: str, session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"asin": asin, "revenue": 0.0, "total_cost": 0.0,
                           "profit": 0.0, "profit_margin": 0.0, "currency": "CNY"},
                     trace_id=trace_id_var.get(""))


@router.get("/pms/profit/margin", response_model=None)
async def get_profit_margin_for_pms(asin: str = Query(default=""),
                                     category_id: str = Query(default=""),
                                     session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"items": [], "avg_margin": 0.0}, trace_id=trace_id_var.get(""))


@router.post("/journal-entries/export", response_model=None)
async def export_journal_entries(req: JournalEntryExportRequest, session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"exported_count": 0, "period_start": req.period_start,
                           "period_end": req.period_end, "format": "kingdee"},
                     trace_id=trace_id_var.get(""))


@router.post("/inventory-cost/push-kingdee", response_model=None)
async def push_inventory_cost_kingdee(req: KingdeePushRequest, session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"pushed_count": 0, "period": req.period, "target": "kingdee"},
                     trace_id=trace_id_var.get(""))


@router.post("/voucher-engine/push-kingdee", response_model=None)
async def push_voucher_kingdee(voucher_id: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"voucher_id": voucher_id, "target": "kingdee", "status": "pushed"},
                     trace_id=trace_id_var.get(""))


@router.post("/voucher-engine/push-yonyou", response_model=None)
async def push_voucher_yonyou(voucher_id: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"voucher_id": voucher_id, "target": "yonyou", "status": "pushed"},
                     trace_id=trace_id_var.get(""))
