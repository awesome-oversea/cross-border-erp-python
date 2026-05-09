from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.task_scheduler.application.services import TaskSchedulerService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/scheduler", tags=["Task Scheduler - 任务调度中心"])


class JobCreateRequest(BaseModel):
    job_name: str = Field(min_length=1, max_length=128)
    job_group: str = Field(min_length=1, max_length=64)
    cron_expression: str = Field(min_length=9, max_length=64)
    handler_class: str = Field(min_length=1, max_length=256)
    handler_params: dict = Field(default_factory=dict)
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=300, ge=10, le=3600)
    description: str = Field(default="")


@router.post("/jobs", response_model=None)
async def create_job(req: JobCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = TaskSchedulerService(session)
    result = await svc.create_job(tenant_id_var.get(""), req.job_name, req.job_group,
                                   req.cron_expression, req.handler_class, req.handler_params,
                                   req.max_retries, req.timeout_seconds, req.description)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/jobs", response_model=None)
async def list_jobs(job_group: str = Query(default=""), status: str = Query(default=""),
                     session: AsyncSession = Depends(get_db_session)):
    svc = TaskSchedulerService(session)
    result = await svc.list_jobs(tenant_id_var.get(""), job_group, status)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.put("/jobs/{job_id}/pause", response_model=None)
async def pause_job(job_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = TaskSchedulerService(session)
    result = await svc.pause_job(tenant_id_var.get(""), job_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.put("/jobs/{job_id}/resume", response_model=None)
async def resume_job(job_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = TaskSchedulerService(session)
    result = await svc.resume_job(tenant_id_var.get(""), job_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.delete("/jobs/{job_id}", response_model=None)
async def delete_job(job_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = TaskSchedulerService(session)
    result = await svc.delete_job(tenant_id_var.get(""), job_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/jobs/{job_id}/execute", response_model=None)
async def execute_job(job_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = TaskSchedulerService(session)
    result = await svc.execute_job(tenant_id_var.get(""), job_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/jobs/{job_id}/logs", response_model=None)
async def get_job_logs(job_id: str, limit: int = Query(default=50, ge=1, le=200),
                        session: AsyncSession = Depends(get_db_session)):
    svc = TaskSchedulerService(session)
    result = await svc.get_job_logs(tenant_id_var.get(""), job_id, limit)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
