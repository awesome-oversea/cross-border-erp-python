from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.sys.domain.import_models import ImportService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/imports", tags=["SYS-Import"])


class CreateTemplateRequest(BaseModel):
    template_name: str = Field(..., min_length=1, max_length=200)
    import_type: str = Field(..., min_length=1, max_length=50)
    columns: list[dict] = Field(..., min_length=1)
    required_columns: list[str] = Field(default_factory=list)
    validation_rules: dict = Field(default_factory=dict)
    description: str = Field(default="", max_length=500)


class CreateImportJobRequest(BaseModel):
    import_type: str = Field(..., min_length=1, max_length=50)
    template_id: str = Field(default="")
    file_name: str = Field(default="")
    file_url: str = Field(default="")
    import_options: dict = Field(default_factory=dict)


class ValidateCsvRequest(BaseModel):
    csv_content: str = Field(..., min_length=1)


class CompleteImportRequest(BaseModel):
    imported_rows: int = Field(default=0, ge=0)
    failed_rows: int = Field(default=0, ge=0)
    error_file_url: str = Field(default="")


@router.post("/templates", response_model=None)
async def create_template(req: CreateTemplateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ImportService(session)
    t = await svc.create_template(
        tenant_id=tenant_id_var.get(""), template_name=req.template_name,
        import_type=req.import_type, columns=req.columns,
        required_columns=req.required_columns, validation_rules=req.validation_rules,
        description=req.description,
    )
    return Result.ok(
        data={"id": t.id, "template_name": t.template_name, "import_type": t.import_type},
        trace_id=trace_id_var.get(""),
    )


@router.get("/templates", response_model=None)
async def list_templates(import_type: str = Query(default=""),
                          session: AsyncSession = Depends(get_db_session)):
    svc = ImportService(session)
    templates = await svc.list_templates(tenant_id_var.get(""), import_type=import_type)
    import json
    data = [{
        "id": t.id, "template_name": t.template_name, "import_type": t.import_type,
        "description": t.description, "columns": json.loads(t.columns_json),
        "required_columns": json.loads(t.required_columns),
        "is_system": t.is_system,
    } for t in templates]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/templates/init-defaults", response_model=None)
async def init_default_templates(session: AsyncSession = Depends(get_db_session)):
    svc = ImportService(session)
    templates = await svc.init_default_templates(tenant_id_var.get(""))
    return Result.ok(
        data={"created_count": len(templates),
              "types": [t.import_type for t in templates]},
        trace_id=trace_id_var.get(""),
    )


@router.post("/jobs", response_model=None)
async def create_import_job(req: CreateImportJobRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ImportService(session)
    job = await svc.create_import_job(
        tenant_id=tenant_id_var.get(""), import_type=req.import_type,
        template_id=req.template_id, file_name=req.file_name,
        file_url=req.file_url, import_options=req.import_options,
    )
    return Result.ok(
        data={"id": job.id, "job_no": job.job_no, "status": job.status},
        trace_id=trace_id_var.get(""),
    )


@router.get("/jobs", response_model=None)
async def list_import_jobs(
    import_type: str = Query(default=""),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = ImportService(session)
    items, total = await svc.list_import_jobs(
        tenant_id_var.get(""), import_type=import_type, status=status,
        page=page, page_size=page_size,
    )
    data = [{
        "id": j.id, "job_no": j.job_no, "import_type": j.import_type,
        "file_name": j.file_name, "total_rows": j.total_rows,
        "valid_rows": j.valid_rows, "invalid_rows": j.invalid_rows,
        "imported_rows": j.imported_rows, "failed_rows": j.failed_rows,
        "status": j.status,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        "created_at": j.created_at.isoformat() if j.created_at else None,
    } for j in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/jobs/{job_id}/validate", response_model=None)
async def validate_csv(job_id: str, req: ValidateCsvRequest,
                        session: AsyncSession = Depends(get_db_session)):
    svc = ImportService(session)
    job = await svc.validate_csv(job_id, tenant_id_var.get(""), csv_content=req.csv_content)
    return Result.ok(
        data={"id": job.id, "job_no": job.job_no, "status": job.status,
              "total_rows": job.total_rows, "valid_rows": job.valid_rows,
              "invalid_rows": job.invalid_rows},
        trace_id=trace_id_var.get(""),
    )


@router.post("/jobs/{job_id}/complete", response_model=None)
async def complete_import(job_id: str, req: CompleteImportRequest,
                           session: AsyncSession = Depends(get_db_session)):
    svc = ImportService(session)
    job = await svc.complete_import(
        job_id, tenant_id_var.get(""),
        imported_rows=req.imported_rows, failed_rows=req.failed_rows,
        error_file_url=req.error_file_url,
    )
    return Result.ok(
        data={"id": job.id, "status": job.status,
              "imported_rows": job.imported_rows, "failed_rows": job.failed_rows},
        trace_id=trace_id_var.get(""),
    )


@router.post("/jobs/{job_id}/cancel", response_model=None)
async def cancel_import(job_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = ImportService(session)
    job = await svc.cancel_import(job_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": job.id, "status": job.status},
        trace_id=trace_id_var.get(""),
    )


@router.get("/jobs/{job_id}/errors", response_model=None)
async def get_import_errors(
    job_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
):
    svc = ImportService(session)
    items, total = await svc.get_import_errors(job_id, tenant_id_var.get(""), page=page, page_size=page_size)
    data = [{
        "id": e.id, "row_number": e.row_number, "row_data": e.row_data,
        "error_type": e.error_type, "error_message": e.error_message,
        "field_name": e.field_name,
    } for e in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))
