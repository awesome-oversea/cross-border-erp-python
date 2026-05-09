from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.sys.domain.dict_models import DataDictService
from erp.modules.sys.domain.doc_number_models import DocNumberService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

router = APIRouter(prefix="/sys/v1", tags=["SYS-BizCenter"])


class DocNumberRuleRequest(BaseModel):
    doc_type: str = Field(..., min_length=1, max_length=100)
    prefix: str = Field(default="")
    date_format: str = Field(default="%Y%m%d")
    seq_length: int = Field(default=4, ge=1, le=10)
    reset_rule: str = Field(default="daily")
    separator: str = Field(default="-")


class DocNumberGenerateRequest(BaseModel):
    doc_type: str = Field(..., min_length=1)


class DictUpsertRequest(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)
    dict_key: str = Field(..., min_length=1, max_length=200)
    dict_value: str = Field(default="")
    label: str = Field(default="")
    label_en: str = Field(default="")
    parent_key: str = Field(default="")
    sort_order: int = Field(default=0)
    is_active: bool = Field(default=True)
    remark: str = Field(default="")


@router.post("/doc-number-rules", response_model=None)
async def define_doc_number_rule(req: DocNumberRuleRequest,
                                  session: AsyncSession = Depends(get_db_session)):
    svc = DocNumberService(session)
    rule = await svc.define_rule(
        tenant_id=tenant_id_var.get(""), doc_type=req.doc_type, prefix=req.prefix,
        date_format=req.date_format, seq_length=req.seq_length,
        reset_rule=req.reset_rule, separator=req.separator,
    )
    return Result.ok(
        data={"id": rule.id, "doc_type": rule.doc_type, "prefix": rule.prefix},
        trace_id=trace_id_var.get(""),
    )


@router.get("/doc-number-rules", response_model=None)
async def list_doc_number_rules(session: AsyncSession = Depends(get_db_session)):
    svc = DocNumberService(session)
    rules = await svc.list_rules(tenant_id=tenant_id_var.get(""))
    return Result.ok(
        data=[{"id": r.id, "doc_type": r.doc_type, "prefix": r.prefix,
               "date_format": r.date_format, "seq_length": r.seq_length,
               "reset_rule": r.reset_rule, "current_seq": r.current_seq} for r in rules],
        trace_id=trace_id_var.get(""),
    )


@router.post("/doc-numbers/generate", response_model=None)
async def generate_doc_number(req: DocNumberGenerateRequest,
                               session: AsyncSession = Depends(get_db_session)):
    svc = DocNumberService(session)
    doc_number = await svc.generate(tenant_id=tenant_id_var.get(""), doc_type=req.doc_type)
    return Result.ok(data={"doc_type": req.doc_type, "doc_number": doc_number}, trace_id=trace_id_var.get(""))


@router.post("/doc-number-rules/init-defaults", response_model=None)
async def init_doc_number_defaults(session: AsyncSession = Depends(get_db_session)):
    svc = DocNumberService(session)
    await svc.init_defaults(tenant_id=tenant_id_var.get(""))
    return Result.ok(data={"message": "Default doc number rules initialized"}, trace_id=trace_id_var.get(""))


@router.post("/dicts", response_model=None)
async def upsert_dict(req: DictUpsertRequest, session: AsyncSession = Depends(get_db_session)):
    svc = DataDictService(session)
    item = await svc.upsert(
        tenant_id=tenant_id_var.get(""), category=req.category, dict_key=req.dict_key,
        dict_value=req.dict_value, label=req.label, label_en=req.label_en,
        parent_key=req.parent_key, sort_order=req.sort_order,
        is_active=req.is_active, remark=req.remark,
    )
    return Result.ok(
        data={"id": item.id, "category": item.category, "dict_key": item.dict_key,
              "dict_value": item.dict_value, "label": item.label},
        trace_id=trace_id_var.get(""),
    )


@router.get("/dicts/{category}", response_model=None)
async def list_dicts(category: str, parent_key: str | None = Query(default=None),
                     is_active: bool | None = Query(default=None),
                     session: AsyncSession = Depends(get_db_session)):
    svc = DataDictService(session)
    items = await svc.list_by_category(
        tenant_id=tenant_id_var.get(""), category=category,
        parent_key=parent_key, is_active=is_active,
    )
    return Result.ok(
        data=[{"id": i.id, "category": i.category, "dict_key": i.dict_key,
               "dict_value": i.dict_value, "label": i.label, "label_en": i.label_en,
               "parent_key": i.parent_key, "sort_order": i.sort_order, "is_active": i.is_active} for i in items],
        trace_id=trace_id_var.get(""),
    )


@router.delete("/dicts/{category}/{dict_key}", response_model=None)
async def delete_dict(category: str, dict_key: str, session: AsyncSession = Depends(get_db_session)):
    svc = DataDictService(session)
    await svc.delete_item(tenant_id=tenant_id_var.get(""), category=category, dict_key=dict_key)
    return Result.ok(data=None, trace_id=trace_id_var.get(""))


@router.post("/dicts/init-defaults", response_model=None)
async def init_dict_defaults(session: AsyncSession = Depends(get_db_session)):
    svc = DataDictService(session)
    await svc.init_defaults(tenant_id=tenant_id_var.get(""))
    return Result.ok(data={"message": "Default dicts initialized"}, trace_id=trace_id_var.get(""))
