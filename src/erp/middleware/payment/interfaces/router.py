from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.payment.application.services import PaymentAggregationService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/fms/v1/payment", tags=["Payment - 支付聚合中心"])


class PayRequest(BaseModel):
    channel: str = Field(default="mock", max_length=32)
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", max_length=10)
    payment_type: str = Field(default="payment")
    counterparty_id: str = Field(default="")
    counterparty_name: str = Field(default="")
    reference_type: str = Field(default="")
    reference_id: str = Field(default="")


class RefundRequest(BaseModel):
    channel: str = Field(default="mock", max_length=32)
    original_transaction_id: str = Field(min_length=1)
    refund_amount: float = Field(gt=0)
    currency: str = Field(default="USD", max_length=10)
    reason: str = Field(default="")


class BatchPayItem(BaseModel):
    channel: str = "mock"
    amount: float = 0
    currency: str = "USD"
    payment_type: str = "payment"
    counterparty_id: str = ""
    counterparty_name: str = ""
    reference_type: str = ""
    reference_id: str = ""


class BatchPayRequest(BaseModel):
    items: list[BatchPayItem]


class WithdrawRequest(BaseModel):
    channel: str = Field(default="mock", max_length=32)
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", max_length=10)
    target_account: str = Field(default="")


class AmazonClaimRequest(BaseModel):
    order_id: str = Field(min_length=1)
    claim_type: str = Field(default="reimbursement")
    claim_amount: float = Field(gt=0)
    currency: str = Field(default="USD", max_length=10)


@router.post("/pay", response_model=None)
async def pay(req: PayRequest, session: AsyncSession = Depends(get_db_session)):
    svc = PaymentAggregationService(session)
    result = await svc.pay(
        tenant_id_var.get(""), channel=req.channel, amount=req.amount,
        currency=req.currency, payment_type=req.payment_type,
        counterparty_id=req.counterparty_id, counterparty_name=req.counterparty_name,
        reference_type=req.reference_type, reference_id=req.reference_id,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/refund", response_model=None)
async def refund(req: RefundRequest, session: AsyncSession = Depends(get_db_session)):
    svc = PaymentAggregationService(session)
    result = await svc.refund(
        tenant_id_var.get(""), channel=req.channel,
        original_transaction_id=req.original_transaction_id,
        refund_amount=req.refund_amount, currency=req.currency, reason=req.reason,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/batch-pay", response_model=None)
async def batch_pay(req: BatchPayRequest, session: AsyncSession = Depends(get_db_session)):
    svc = PaymentAggregationService(session)
    results = await svc.batch_pay(tenant_id_var.get(""), [i.model_dump() for i in req.items])
    return Result.ok(data=results, trace_id=trace_id_var.get(""))


@router.get("/channels", response_model=None)
async def get_channels(session: AsyncSession = Depends(get_db_session)):
    svc = PaymentAggregationService(session)
    channels = await svc.get_channels()
    return Result.ok(data=channels, trace_id=trace_id_var.get(""))


@router.get("/balance", response_model=None)
async def get_balance(channel: str = Query(default="mock"), currency: str = Query(default="USD"),
                      session: AsyncSession = Depends(get_db_session)):
    svc = PaymentAggregationService(session)
    balance = await svc.get_balance(tenant_id_var.get(""), channel, currency)
    return Result.ok(data=balance, trace_id=trace_id_var.get(""))


@router.post("/settlement/withdraw", response_model=None)
async def settlement_withdraw(req: WithdrawRequest, session: AsyncSession = Depends(get_db_session)):
    svc = PaymentAggregationService(session)
    result = await svc.settlement_withdraw(
        tenant_id_var.get(""), channel=req.channel, amount=req.amount,
        currency=req.currency, target_account=req.target_account,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/amazon-claim", response_model=None)
async def amazon_claim(req: AmazonClaimRequest, session: AsyncSession = Depends(get_db_session)):
    svc = PaymentAggregationService(session)
    result = await svc.amazon_claim(
        tenant_id_var.get(""), order_id=req.order_id, claim_type=req.claim_type,
        claim_amount=req.claim_amount, currency=req.currency,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
