from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi import File as FastAPIFile

from erp.middleware.file_processor.application.services import FileProcessorService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/file", tags=["File Processor - 文件处理中心"])


@router.post("/upload", response_model=None)
async def upload_file(domain: str = Query(default="general"), file: UploadFile = FastAPIFile(...),
                       session: AsyncSession = Depends(get_db_session)):
    svc = FileProcessorService(session)
    content = await file.read()
    result = await svc.upload(tenant_id_var.get(""), file.filename or "unknown", content, domain)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/{file_id}/download", response_model=None)
async def download_file(file_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = FileProcessorService(session)
    result = await svc.get_file(tenant_id_var.get(""), file_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/{file_id}/preview", response_model=None)
async def preview_file(file_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = FileProcessorService(session)
    result = await svc.preview(tenant_id_var.get(""), file_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.delete("/{file_id}", response_model=None)
async def delete_file(file_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = FileProcessorService(session)
    result = await svc.delete_file(tenant_id_var.get(""), file_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("", response_model=None)
async def list_files(domain: str = Query(default=""), extension: str = Query(default=""),
                      limit: int = Query(default=50, ge=1, le=200),
                      offset: int = Query(default=0, ge=0),
                      session: AsyncSession = Depends(get_db_session)):
    svc = FileProcessorService(session)
    result = await svc.list_files(tenant_id_var.get(""), domain, extension, limit, offset)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/{file_id}/convert", response_model=None)
async def convert_file(file_id: str, target_format: str = Query(...),
                        session: AsyncSession = Depends(get_db_session)):
    svc = FileProcessorService(session)
    result = await svc.convert(tenant_id_var.get(""), file_id, target_format)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
