from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.fms.domain.voucher_models import VoucherEngineService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/fms/v1/vouchers", tags=["FMS-VoucherEngine"])


class TemplateCreateRequest(BaseModel):
    template_code: str = Field(..., min_length=1, max_length=100)
    template_name: str = Field(..., min_length=1, max_length=200)
    voucher_type: str = Field(..., pattern=r"^(purchase|sales|inventory|adjustment|settlement|other)$")
    trigger_event: str = Field(default="")
    description: str = Field(default="")
    debit_rules: list = Field(default_factory=list)
    credit_rules: list = Field(default_factory=list)
    is_auto: bool = Field(default=True)


class TemplateUpdateRequest(BaseModel):
    template_name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    debit_rules: list | None = None
    credit_rules: list | None = None
    is_auto: bool | None = None


class VoucherGenerateRequest(BaseModel):
    template_code: str = Field(..., min_length=1)
    source_type: str = Field(..., min_length=1)
    source_id: str = Field(..., min_length=1)
    source_no: str = Field(default="")
    context: dict = Field(default_factory=dict)
    period: str = Field(default="")


class VoucherPushRequest(BaseModel):
    target: str = Field(default="kingdee")


@router.post("/templates", response_model=None)
async def create_template(req: TemplateCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = VoucherEngineService(session)
    template = await svc.create_template(
        tenant_id=tenant_id_var.get(""), template_code=req.template_code,
        template_name=req.template_name, voucher_type=req.voucher_type,
        trigger_event=req.trigger_event, description=req.description,
        debit_rules=req.debit_rules, credit_rules=req.credit_rules,
        is_auto=req.is_auto,
    )
    return Result.ok(
        data={"id": template.id, "template_code": template.template_code,
              "template_name": template.template_name, "voucher_type": template.voucher_type,
              "trigger_event": template.trigger_event, "is_auto": template.is_auto},
        trace_id=trace_id_var.get(""),
    )


@router.get("/templates", response_model=None)
async def list_templates(
    voucher_type: str = Query(default=""),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = VoucherEngineService(session)
    templates, total = await svc.list_templates(
        tenant_id_var.get(""), voucher_type=voucher_type,
        is_active=is_active, page=page, page_size=page_size,
    )
    data = [{
        "id": t.id, "template_code": t.template_code, "template_name": t.template_name,
        "voucher_type": t.voucher_type, "trigger_event": t.trigger_event,
        "description": t.description, "is_auto": t.is_auto,
        "is_active": t.is_active, "version": t.version,
        "debit_rules": json.loads(t.debit_rules_json),
        "credit_rules": json.loads(t.credit_rules_json),
    } for t in templates]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.put("/templates/{template_id}", response_model=None)
async def update_template(template_id: str, req: TemplateUpdateRequest,
                           session: AsyncSession = Depends(get_db_session)):
    svc = VoucherEngineService(session)
    template = await svc.update_template(
        template_id, tenant_id_var.get(""),
        template_name=req.template_name, description=req.description,
        debit_rules=req.debit_rules, credit_rules=req.credit_rules,
        is_auto=req.is_auto,
    )
    return Result.ok(data={"id": template.id, "version": template.version}, trace_id=trace_id_var.get(""))


@router.put("/templates/{template_id}/deactivate", response_model=None)
async def deactivate_template(template_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = VoucherEngineService(session)
    template = await svc.deactivate_template(template_id, tenant_id_var.get(""))
    return Result.ok(data={"id": template.id, "is_active": template.is_active}, trace_id=trace_id_var.get(""))


@router.post("/generate", response_model=None)
async def generate_voucher(req: VoucherGenerateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = VoucherEngineService(session)
    voucher = await svc.generate_voucher(
        tenant_id=tenant_id_var.get(""), template_code=req.template_code,
        source_type=req.source_type, source_id=req.source_id,
        source_no=req.source_no, context=req.context, period=req.period,
    )
    return Result.ok(
        data={"id": voucher.id, "voucher_no": voucher.voucher_no,
              "template_code": voucher.template_code, "voucher_type": voucher.voucher_type,
              "source_type": voucher.source_type, "source_id": voucher.source_id,
              "total_debit": float(voucher.total_debit), "total_credit": float(voucher.total_credit),
              "status": voucher.status, "entries": json.loads(voucher.entries_json)},
        trace_id=trace_id_var.get(""),
    )


@router.get("", response_model=None)
async def list_vouchers(
    voucher_type: str = Query(default=""),
    status: str = Query(default=""),
    source_type: str = Query(default=""),
    period: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = VoucherEngineService(session)
    vouchers, total = await svc.list_vouchers(
        tenant_id_var.get(""), voucher_type=voucher_type,
        status=status, source_type=source_type, period=period,
        page=page, page_size=page_size,
    )
    data = [{
        "id": v.id, "voucher_no": v.voucher_no,
        "template_code": v.template_code, "voucher_type": v.voucher_type,
        "source_type": v.source_type, "source_id": v.source_id,
        "source_no": v.source_no, "period": v.period,
        "total_debit": float(v.total_debit), "total_credit": float(v.total_credit),
        "currency": v.currency, "status": v.status,
        "is_auto_generated": v.is_auto_generated,
        "posted_at": v.posted_at.isoformat() if v.posted_at else None,
        "push_target": v.push_target, "push_status": v.push_status,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    } for v in vouchers]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/{voucher_id}", response_model=None)
async def get_voucher(voucher_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = VoucherEngineService(session)
    vouchers, _ = await svc.list_vouchers(tenant_id_var.get(""), page=1, page_size=1)
    voucher = next((v for v in vouchers if v.id == voucher_id), None)
    if not voucher:
        return Result.fail(code=404, message="Voucher not found", trace_id=trace_id_var.get(""))
    return Result.ok(
        data={
            "id": voucher.id, "voucher_no": voucher.voucher_no,
            "template_code": voucher.template_code, "voucher_type": voucher.voucher_type,
            "source_type": voucher.source_type, "source_id": voucher.source_id,
            "total_debit": float(voucher.total_debit), "total_credit": float(voucher.total_credit),
            "status": voucher.status,
            "entries": json.loads(voucher.entries_json),
            "is_auto_generated": voucher.is_auto_generated,
        },
        trace_id=trace_id_var.get(""),
    )


@router.put("/{voucher_id}/post", response_model=None)
async def post_voucher(voucher_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = VoucherEngineService(session)
    voucher = await svc.post_voucher(voucher_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": voucher.id, "voucher_no": voucher.voucher_no, "status": voucher.status},
        trace_id=trace_id_var.get(""),
    )


@router.put("/{voucher_id}/cancel", response_model=None)
async def cancel_voucher(voucher_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = VoucherEngineService(session)
    voucher = await svc.cancel_voucher(voucher_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": voucher.id, "voucher_no": voucher.voucher_no, "status": voucher.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/{voucher_id}/push", response_model=None)
async def push_voucher(voucher_id: str, req: VoucherPushRequest,
                        session: AsyncSession = Depends(get_db_session)):
    svc = VoucherEngineService(session)
    voucher = await svc.push_to_external(voucher_id, tenant_id_var.get(""), target=req.target)
    return Result.ok(
        data={"id": voucher.id, "voucher_no": voucher.voucher_no,
              "status": voucher.status, "push_target": voucher.push_target,
              "push_status": voucher.push_status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/init-defaults", response_model=None)
async def init_default_templates(session: AsyncSession = Depends(get_db_session)):
    svc = VoucherEngineService(session)
    await svc.init_defaults(tenant_id_var.get(""))
    return Result.ok(data={"message": "Default voucher templates initialized"}, trace_id=trace_id_var.get(""))
