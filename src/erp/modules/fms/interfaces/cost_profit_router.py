from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.fms.domain.cost_models import CostAggregationService
from erp.modules.fms.domain.profit_models import ProfitEngine
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import NotFoundException, Result

router = APIRouter(prefix="/fms/v1", tags=["FMS-CostProfit"])


class CostRecordRequest(BaseModel):
    cost_type: str = Field(..., min_length=1)
    amount: str = Field(..., min_length=1)
    currency: str = Field(default="CNY")
    exchange_rate: str = Field(default="1")
    source_type: str = Field(default="")
    source_id: str = Field(default="")
    order_id: str = Field(default="")
    order_item_id: str = Field(default="")
    sku_id: str = Field(default="")
    store_id: str = Field(default="")
    quantity: int = Field(default=0)
    allocation_rule: str = Field(default="direct")
    cost_category: str = Field(default="")


class ProfitCalcRequest(BaseModel):
    order_id: str = Field(..., min_length=1)
    revenue_cny: str = Field(default="0")


@router.post("/cost-events", response_model=None)
async def record_cost(req: CostRecordRequest, session: AsyncSession = Depends(get_db_session)):
    svc = CostAggregationService(session)
    event = await svc.record_cost(
        tenant_id=tenant_id_var.get(""), cost_type=req.cost_type,
        amount=Decimal(req.amount), currency=req.currency,
        exchange_rate=Decimal(req.exchange_rate),
        source_type=req.source_type, source_id=req.source_id,
        order_id=req.order_id, order_item_id=req.order_item_id,
        sku_id=req.sku_id, store_id=req.store_id,
        quantity=req.quantity, allocation_rule=req.allocation_rule,
        cost_category=req.cost_category,
    )
    return Result.ok(
        data={"id": event.id, "cost_type": event.cost_type,
              "amount_cny": str(event.amount_cny), "order_id": event.order_id,
              "sku_id": event.sku_id},
        trace_id=trace_id_var.get(""),
    )


@router.get("/cost-events/order/{order_id}", response_model=None)
async def get_order_costs(order_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = CostAggregationService(session)
    summary = await svc.aggregate_order_cost(tenant_id=tenant_id_var.get(""), order_id=order_id)
    return Result.ok(data=summary, trace_id=trace_id_var.get(""))


@router.get("/cost-events/sku/{sku_id}", response_model=None)
async def get_sku_costs(sku_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = CostAggregationService(session)
    summary = await svc.aggregate_sku_cost(tenant_id=tenant_id_var.get(""), sku_id=sku_id)
    return Result.ok(data=summary, trace_id=trace_id_var.get(""))


@router.post("/profit/calculate", response_model=None)
async def calculate_profit(req: ProfitCalcRequest, session: AsyncSession = Depends(get_db_session)):
    engine = ProfitEngine(session)
    record = await engine.calculate_order_profit(
        tenant_id=tenant_id_var.get(""), order_id=req.order_id,
        revenue_cny=Decimal(req.revenue_cny),
    )
    return Result.ok(
        data={"id": record.id, "order_id": record.order_id,
              "revenue_cny": str(record.revenue_cny),
              "total_cost_cny": str(record.total_cost_cny),
              "gross_profit_cny": str(record.gross_profit_cny),
              "gross_margin": str(record.gross_margin),
              "net_profit_cny": str(record.net_profit_cny),
              "net_margin": str(record.net_margin)},
        trace_id=trace_id_var.get(""),
    )


@router.get("/profit/order/{order_id}", response_model=None)
async def get_order_profit(order_id: str, session: AsyncSession = Depends(get_db_session)):
    engine = ProfitEngine(session)
    record = await engine.get_profit_by_order_or_raise(tenant_id=tenant_id_var.get(""), order_id=order_id)
    return Result.ok(
        data={"id": record.id, "order_id": record.order_id,
              "revenue_cny": str(record.revenue_cny),
              "cost_purchase_cny": str(record.cost_purchase_cny),
              "cost_logistics_cny": str(record.cost_logistics_cny),
              "cost_platform_cny": str(record.cost_platform_cny),
              "cost_advertising_cny": str(record.cost_advertising_cny),
              "total_cost_cny": str(record.total_cost_cny),
              "gross_profit_cny": str(record.gross_profit_cny),
              "gross_margin": str(record.gross_margin),
              "net_profit_cny": str(record.net_profit_cny),
              "net_margin": str(record.net_margin)},
        trace_id=trace_id_var.get(""),
    )


@router.get("/profit/aggregate", response_model=None)
async def aggregate_profit(dimension_type: str = Query(...),
                            dimension_id: str | None = Query(default=None),
                            start_date: str | None = Query(default=None),
                            end_date: str | None = Query(default=None),
                            session: AsyncSession = Depends(get_db_session)):
    engine = ProfitEngine(session)
    result = await engine.aggregate_profit(
        tenant_id=tenant_id_var.get(""), dimension_type=dimension_type,
        dimension_id=dimension_id, start_date=start_date, end_date=end_date,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
