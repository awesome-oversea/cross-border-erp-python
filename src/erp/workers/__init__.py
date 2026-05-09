"""
Celery Worker - 异步任务与定时任务入口

启动:
  celery -A erp.workers.worker worker -l info -Q default,high_priority
  celery -A erp.workers.worker beat -l info
"""
from __future__ import annotations

from celery import Celery

from erp.bootstrap.config import get_settings

settings = get_settings()

# Celery应用实例: 管理所有异步任务和定时调度
app = Celery(
    "erp",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
    include=["erp.workers.tasks"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "high_priority": {"exchange": "high_priority", "routing_key": "high_priority"},
    },
    beat_schedule={
        "outbox-publish-every-30s": {
            "task": "erp.workers.tasks.publish_outbox_messages",
            "schedule": 30.0, "options": {"queue": "default"},
        },
        "cdc-sync-every-60s": {
            "task": "erp.workers.tasks.sync_cdc_to_clickhouse",
            "schedule": 60.0, "options": {"queue": "default"},
        },
        "inventory-alert-every-5min": {
            "task": "erp.workers.tasks.check_inventory_alerts",
            "schedule": 300.0, "options": {"queue": "high_priority"},
        },
        "connector-health-every-10min": {
            "task": "erp.workers.tasks.check_connector_health",
            "schedule": 600.0, "options": {"queue": "default"},
        },
        "archive-audit-logs-daily": {
            "task": "erp.workers.tasks.archive_audit_logs",
            "schedule": 86400.0, "options": {"queue": "default"},
        },
    },
)

if __name__ == "__main__":
    app.start()
