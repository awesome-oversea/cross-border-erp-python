"""
Celery 异步任务定义

包含:
  - Outbox消息发布（每30秒）
  - CDC增量同步到ClickHouse（每60秒）
  - 库存预警检查（每5分钟）
  - 连接器健康检查（每10分钟）
  - 审计日志归档（每天）
"""
from __future__ import annotations

from erp.shared.observability.logging import get_logger
from erp.workers import app

logger = get_logger("erp.workers.tasks")


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def publish_outbox_messages(self):
    """发布待发送的Outbox消息到Kafka"""
    logger.info("outbox_publish_started")


@app.task(bind=True, max_retries=3, default_retry_delay=120)
def sync_cdc_to_clickhouse(self):
    """增量同步数据到ClickHouse"""
    logger.info("cdc_sync_started")


@app.task(bind=True, max_retries=2, default_retry_delay=300)
def check_inventory_alerts(self):
    """检查库存预警"""
    logger.info("inventory_alert_check_started")


@app.task(bind=True, max_retries=2, default_retry_delay=600)
def check_connector_health(self):
    """检查连接器健康状态"""
    logger.info("connector_health_check_started")


@app.task(bind=True, max_retries=2, default_retry_delay=3600)
def archive_audit_logs(self):
    """归档过期的审计日志"""
    logger.info("audit_archive_started")


@app.task(bind=True, max_retries=3, default_retry_delay=30)
def sync_platform_orders(self, platform: str, tenant_id: str, store_id: str):
    """同步平台订单（高优先级任务）"""
    logger.info("platform_order_sync_started", platform=platform, tenant=tenant_id)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_report(self, report_type: str, params: dict):
    """异步生成报表"""
    logger.info("report_generation_started", type=report_type)


@app.task(bind=True)
def send_notification(self, channel: str, recipients: list[str], title: str, content: str):
    """发送通知（邮件/短信/站内信）"""
    logger.info("notification_send_started", channel=channel)
