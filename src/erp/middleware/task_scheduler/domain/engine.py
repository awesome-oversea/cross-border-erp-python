from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class JobStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class LogStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    RUNNING = "running"


@dataclass
class ScheduledJob:
    job_id: str = ""
    tenant_id: str = ""
    job_name: str = ""
    job_group: str = ""
    cron_expression: str = ""
    handler_class: str = ""
    handler_params: dict = field(default_factory=dict)
    status: str = "active"
    max_retries: int = 3
    retry_count: int = 0
    timeout_seconds: int = 300
    last_executed_at: str = ""
    next_execute_at: str = ""
    description: str = ""
    created_at: str = ""


@dataclass
class JobExecutionLog:
    log_id: str = ""
    job_id: str = ""
    tenant_id: str = ""
    status: str = "running"
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0
    result_message: str = ""
    error_message: str = ""
    retry_attempt: int = 0


class TaskSchedulerEngine:
    def __init__(self):
        self._jobs: dict[str, ScheduledJob] = {}
        self._logs: list[JobExecutionLog] = []

    def create_job(self, tenant_id: str, job_name: str, job_group: str, cron_expression: str,
                    handler_class: str, handler_params: dict | None = None,
                    max_retries: int = 3, timeout_seconds: int = 300,
                    description: str = "") -> ScheduledJob:
        job = ScheduledJob(
            job_id=str(uuid.uuid4()), tenant_id=tenant_id, job_name=job_name,
            job_group=job_group, cron_expression=cron_expression,
            handler_class=handler_class, handler_params=handler_params or {},
            status="active", max_retries=max_retries, timeout_seconds=timeout_seconds,
            description=description, created_at=datetime.now(UTC).isoformat(),
        )
        self._jobs[job.job_id] = job
        return job

    def get_job(self, job_id: str) -> ScheduledJob | None:
        return self._jobs.get(job_id)

    def list_jobs(self, tenant_id: str, job_group: str = "", status: str = "") -> list[ScheduledJob]:
        results = [j for j in self._jobs.values() if j.tenant_id == tenant_id]
        if job_group:
            results = [j for j in results if j.job_group == job_group]
        if status:
            results = [j for j in results if j.status == status]
        return results

    def pause_job(self, job_id: str) -> dict:
        job = self._jobs.get(job_id)
        if not job:
            return {"success": False, "error": "Job not found"}
        if job.status != "active":
            return {"success": False, "error": f"Job is '{job.status}', cannot pause"}
        job.status = "paused"
        return {"success": True, "job_id": job_id, "status": "paused"}

    def resume_job(self, job_id: str) -> dict:
        job = self._jobs.get(job_id)
        if not job:
            return {"success": False, "error": "Job not found"}
        if job.status != "paused":
            return {"success": False, "error": f"Job is '{job.status}', cannot resume"}
        job.status = "active"
        return {"success": True, "job_id": job_id, "status": "active"}

    def delete_job(self, job_id: str) -> dict:
        job = self._jobs.pop(job_id, None)
        if not job:
            return {"success": False, "error": "Job not found"}
        return {"success": True, "job_id": job_id}

    def execute_job(self, job_id: str) -> JobExecutionLog:
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError("Job not found")
        if job.status != "active":
            raise ValueError(f"Job is '{job.status}', cannot execute")

        log = JobExecutionLog(
            log_id=str(uuid.uuid4()), job_id=job_id, tenant_id=job.tenant_id,
            status="success", started_at=datetime.now(UTC).isoformat(),
            finished_at=datetime.now(UTC).isoformat(), duration_ms=150,
            result_message=f"Mock execution of {job.handler_class}",
        )
        job.last_executed_at = log.started_at
        self._logs.append(log)
        return log

    def get_job_logs(self, job_id: str, limit: int = 50) -> list[JobExecutionLog]:
        return [log for log in self._logs if log.job_id == job_id][-limit:]

    def get_all_logs(self, tenant_id: str, status: str = "", limit: int = 50) -> list[JobExecutionLog]:
        results = [log for log in self._logs if log.tenant_id == tenant_id]
        if status:
            results = [log for log in results if log.status == status]
        return results[-limit:]
