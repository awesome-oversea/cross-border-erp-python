from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.invoice_tax.application.services import InvoiceTaxService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/fms/v1", tags=["Invoice & Tax - 发票税务中台"])


class InvoiceGenerateRequest(BaseModel):
    invoice_type: str = Field(default="sales", pattern="^(purchase|sales|credit_note|proforma)$")
    items: list[dict] = Field(default_factory=list)
    counterparty: dict = Field(default_factory=dict)
    country_code: str = Field(default="DE", max_length=10)


class TaxCalculateRequest(BaseModel):
    amount: float = Field(gt=0)
    country_code: str = Field(default="DE", max_length=10)
    tax_type: str = Field(default="vat")
    is_b2b: bool = Field(default=False)
    tax_inclusive: bool = Field(default=False)


@router.post("/invoice/generate", response_model=None)
async def generate_invoice(req: InvoiceGenerateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = InvoiceTaxService(session)
    result = await svc.generate_invoice(tenant_id_var.get(""), req.invoice_type, req.items, req.counterparty, req.country_code)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/invoice/tax-rates", response_model=None)
async def get_tax_rates(country_code: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    svc = InvoiceTaxService(session)
    rates = await svc.get_tax_rates(country_code)
    return Result.ok(data=rates, trace_id=trace_id_var.get(""))


@router.put("/invoice/{invoice_id}/void", response_model=None)
async def void_invoice(invoice_id: str, reason: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    svc = InvoiceTaxService(session)
    result = await svc.void_invoice(tenant_id_var.get(""), invoice_id, reason)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/invoice/{invoice_id}/red-flush", response_model=None)
async def red_flush_invoice(invoice_id: str, reason: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    svc = InvoiceTaxService(session)
    result = await svc.red_flush_invoice(tenant_id_var.get(""), invoice_id, reason)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/tax/calculate", response_model=None)
async def calculate_tax(req: TaxCalculateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = InvoiceTaxService(session)
    result = await svc.calculate_tax(req.amount, req.country_code, req.tax_type, req.is_b2b, req.tax_inclusive)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/tax/filing-data", response_model=None)
async def get_filing_data(period_start: str = Query(...), period_end: str = Query(...),
                           country_code: str = Query(default="DE"), session: AsyncSession = Depends(get_db_session)):
    svc = InvoiceTaxService(session)
    result = await svc.get_filing_data(tenant_id_var.get(""), period_start, period_end, country_code)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
