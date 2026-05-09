from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from erp.shared.observability.logging import get_logger

logger = get_logger("erp.notification")


class NotificationChannel(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"


class NotificationTemplate:
    _templates: dict[str, dict[str, str]] = {}

    @classmethod
    def register(cls, code: str, title_template: str, body_template: str, channel: str = "in_app") -> None:
        cls._templates[code] = {
            "title_template": title_template,
            "body_template": body_template,
            "channel": channel,
        }

    @classmethod
    def get(cls, code: str) -> dict[str, str] | None:
        return cls._templates.get(code)

    @classmethod
    def render(cls, code: str, variables: dict[str, Any]) -> dict[str, str] | None:
        template = cls._templates.get(code)
        if not template:
            return None
        title = template["title_template"]
        body = template["body_template"]
        for key, value in variables.items():
            title = title.replace(f"{{{{{key}}}}}", str(value))
            body = body.replace(f"{{{{{key}}}}}", str(value))
        return {"title": title, "body": body, "channel": template["channel"]}


NotificationTemplate.register("order.created", "新订单通知", "订单 {{order_no}} 已创建，金额 {{amount}}")
NotificationTemplate.register("order.risk", "订单风险预警", "订单 {{order_no}} 存在风险：{{risk_type}}")
NotificationTemplate.register("inventory.low_stock", "库存不足预警", "SKU {{sku_code}} 库存不足，当前可用 {{available_qty}}")
NotificationTemplate.register("purchase.approval", "采购审批待办", "采购单 {{po_no}} 待您审批，金额 {{amount}}")
NotificationTemplate.register("payment.approval", "付款审批待办", "付款申请 {{payment_no}} 待您审批，金额 {{amount}}")
NotificationTemplate.register("pms.suggestion", "AI建议通知", "收到新的AI建议：{{suggestion_title}}")
NotificationTemplate.register("shipment.dispatched", "发货通知", "订单 {{order_no}} 已发货，追踪号 {{tracking_no}}")
NotificationTemplate.register("system.maintenance", "系统维护通知", "{{message}}")


class NotificationService:
    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._store: list[dict] = []

    async def send(
        self,
        tenant_id: str,
        recipient_id: str,
        template_code: str,
        variables: dict[str, Any] | None = None,
        channel: str = "in_app",
        priority: str = "normal",
    ) -> dict[str, Any]:
        rendered = NotificationTemplate.render(template_code, variables or {})
        if not rendered:
            logger.warning("notification_template_not_found", code=template_code)
            return {"status": "failed", "reason": "template_not_found"}

        notification = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "recipient_id": recipient_id,
            "template_code": template_code,
            "title": rendered["title"],
            "body": rendered["body"],
            "channel": channel or rendered["channel"],
            "priority": priority,
            "status": NotificationStatus.SENT.value,
            "created_at": datetime.now(UTC).isoformat(),
        }

        self._store.append(notification)

        if self._redis:
            try:
                key = f"erp:notifications:{tenant_id}:{recipient_id}"
                await self._redis.lpush(key, json.dumps(notification, default=str))
                await self._redis.ltrim(key, 0, 99)
            except Exception as e:
                logger.warning("notification_redis_failed", error=str(e))

        logger.info(
            "notification_sent",
            notification_id=notification["id"],
            tenant_id=tenant_id,
            recipient=recipient_id,
            template=template_code,
            channel=notification["channel"],
        )
        return notification

    async def send_batch(
        self,
        tenant_id: str,
        recipient_ids: list[str],
        template_code: str,
        variables: dict[str, Any] | None = None,
        channel: str = "in_app",
    ) -> list[dict[str, Any]]:
        results = []
        for rid in recipient_ids:
            result = await self.send(tenant_id, rid, template_code, variables, channel)
            results.append(result)
        return results

    async def list_notifications(
        self,
        tenant_id: str,
        recipient_id: str,
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False,
    ) -> dict[str, Any]:
        items = [
            n for n in self._store
            if n["tenant_id"] == tenant_id and n["recipient_id"] == recipient_id
        ]
        if unread_only:
            items = [n for n in items if n["status"] != NotificationStatus.READ.value]
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "total": total,
            "items": items[start:end],
            "page": page,
            "page_size": page_size,
        }

    async def mark_read(self, tenant_id: str, recipient_id: str, notification_id: str) -> bool:
        for n in self._store:
            if (
                n["id"] == notification_id
                and n["tenant_id"] == tenant_id
                and n["recipient_id"] == recipient_id
            ):
                n["status"] = NotificationStatus.READ.value
                return True
        return False

    async def mark_all_read(self, tenant_id: str, recipient_id: str) -> int:
        count = 0
        for n in self._store:
            if n["tenant_id"] == tenant_id and n["recipient_id"] == recipient_id and n["status"] != NotificationStatus.READ.value:
                n["status"] = NotificationStatus.READ.value
                count += 1
        return count

    async def get_unread_count(self, tenant_id: str, recipient_id: str) -> int:
        return sum(
            1 for n in self._store
            if n["tenant_id"] == tenant_id
            and n["recipient_id"] == recipient_id
            and n["status"] != NotificationStatus.READ.value
        )
