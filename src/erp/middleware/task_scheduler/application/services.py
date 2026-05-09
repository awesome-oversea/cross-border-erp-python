from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.task_scheduler.domain.engine import TaskSchedulerEngine
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.task_scheduler")

_engine_instance = TaskSchedulerEngine()


class TaskSchedulerService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = _engine_instance

    async def create_job(self, tenant_id: str, job_name: str, job_group: str, cron_expression: str,
                          handler_class: str, handler_params: dict | None = None,
                          max_retries: int = 3, timeout_seconds: int = 300,
                          description: str = "") -> dict:
        job = self._engine.create_job(tenant_id, job_name, job_group, cron_expression,
                                       handler_class, handler_params, max_retries, timeout_seconds, description)
        return self._job_to_dict(job)

    async def list_jobs(self, tenant_id: str, job_group: str = "", status: str = "") -> list[dict]:
        jobs = self._engine.list_jobs(tenant_id, job_group, status)
        return [self._job_to_dict(j) for j in jobs]

    async def pause_job(self, tenant_id: str, job_id: str) -> dict:
        return self._engine.pause_job(job_id)

    async def resume_job(self, tenant_id: str, job_id: str) -> dict:
        return self._engine.resume_job(job_id)

    async def delete_job(self, tenant_id: str, job_id: str) -> dict:
        return self._engine.delete_job(job_id)

    async def execute_job(self, tenant_id: str, job_id: str) -> dict:
        log = self._engine.execute_job(job_id)
        return {"log_id": log.log_id, "status": log.status, "started_at": log.started_at,
                "finished_at": log.finished_at, "duration_ms": log.duration_ms,
                "result_message": log.result_message}

    async def get_job_logs(self, tenant_id: str, job_id: str, limit: int = 50) -> list[dict]:
        logs = self._engine.get_job_logs(job_id, limit)
        return [self._log_to_dict(log) for log in logs]

    def _job_to_dict(self, job) -> dict:
        return {"job_id": job.job_id, "job_name": job.job_name, "job_group": job.job_group,
                "cron_expression": job.cron_expression, "handler_class": job.handler_class,
                "status": job.status, "max_retries": job.max_retries,
                "timeout_seconds": job.timeout_seconds, "description": job.description,
                "last_executed_at": job.last_executed_at, "created_at": job.created_at}

    def _log_to_dict(self, log) -> dict:
        return {"log_id": log.log_id, "job_id": log.job_id, "status": log.status,
                "started_at": log.started_at, "finished_at": log.finished_at,
                "duration_ms": log.duration_ms, "result_message": log.result_message,
                "error_message": log.error_message, "retry_attempt": log.retry_attempt}
