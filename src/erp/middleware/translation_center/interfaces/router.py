from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.translation_center.application.services import TranslationCenterService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/translation", tags=["Translation Center - 多语言翻译中心"])


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1)
    source_lang: str = Field(min_length=2, max_length=10)
    target_lang: str = Field(min_length=2, max_length=10)
    domain: str = Field(default="general", max_length=32)


class BatchTranslateRequest(BaseModel):
    texts: list[str] = Field(min_length=1)
    source_lang: str = Field(min_length=2, max_length=10)
    target_lang: str = Field(min_length=2, max_length=10)
    domain: str = Field(default="general", max_length=32)


class GlossaryAddRequest(BaseModel):
    domain: str = Field(min_length=1, max_length=32)
    key: str = Field(min_length=1, max_length=64)
    translations: dict[str, str]


@router.post("/translate", response_model=None)
async def translate(req: TranslateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = TranslationCenterService(session)
    result = await svc.translate(tenant_id_var.get(""), req.text, req.source_lang, req.target_lang, req.domain)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/batch-translate", response_model=None)
async def batch_translate(req: BatchTranslateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = TranslationCenterService(session)
    result = await svc.batch_translate(tenant_id_var.get(""), req.texts, req.source_lang, req.target_lang, req.domain)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/languages", response_model=None)
async def get_languages(session: AsyncSession = Depends(get_db_session)):
    svc = TranslationCenterService(session)
    result = await svc.get_languages(tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/glossary", response_model=None)
async def get_glossary(domain: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    svc = TranslationCenterService(session)
    result = await svc.get_glossary(tenant_id_var.get(""), domain)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/glossary", response_model=None)
async def add_glossary(req: GlossaryAddRequest, session: AsyncSession = Depends(get_db_session)):
    svc = TranslationCenterService(session)
    result = await svc.add_glossary(tenant_id_var.get(""), req.domain, req.key, req.translations)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
