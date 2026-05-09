from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class ChannelType(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"


@dataclass
class NotificationTemplate:
    code: str = ""
    title_template: str = ""
    body_template: str = ""
    channel: str = "in_app"
    is_active: bool = True


@dataclass
class NotificationMessage:
    id: str = ""
    tenant_id: str = ""
    template_code: str = ""
    channel: str = "in_app"
    recipient_id: str = ""
    recipient_address: str = ""
    title: str = ""
    body: str = ""
    status: str = "pending"
    variables: dict = field(default_factory=dict)
    created_at: str = ""
    sent_at: str = ""
    read_at: str = ""
    error_message: str = ""


class NotificationEngine:
    def __init__(self):
        self._templates: dict[str, NotificationTemplate] = {}
        self._messages: list[NotificationMessage] = []
        self._register_default_templates()

    def _register_default_templates(self):
        defaults = [
            ("order.created", "新订单通知", "订单 {{order_no}} 已创建，金额 {{amount}}", "in_app"),
            ("order.risk", "订单风险预警", "订单 {{order_no}} 存在风险：{{risk_type}}", "in_app"),
            ("inventory.low_stock", "库存不足预警", "SKU {{sku_code}} 库存不足，当前可用 {{available_qty}}", "in_app"),
            ("purchase.approval", "采购审批待办", "采购单 {{po_no}} 待您审批，金额 {{amount}}", "in_app"),
            ("payment.approval", "付款审批待办", "付款申请 {{payment_no}} 待您审批，金额 {{amount}}", "in_app"),
            ("shipment.delivered", "货物签收通知", "货件 {{shipment_no}} 已签收", "in_app"),
            ("ad.budget_low", "广告预算不足", "广告活动 {{campaign_name}} 预算不足，剩余 {{remaining}}", "in_app"),
        ]
        for code, title, body, channel in defaults:
            self._templates[code] = NotificationTemplate(code=code, title_template=title, body_template=body, channel=channel)

    def register_template(self, code: str, title_template: str, body_template: str, channel: str = "in_app") -> NotificationTemplate:
        template = NotificationTemplate(code=code, title_template=title_template, body_template=body_template, channel=channel)
        self._templates[code] = template
        return template

    def get_templates(self) -> list[NotificationTemplate]:
        return list(self._templates.values())

    def render_template(self, code: str, variables: dict[str, Any]) -> dict[str, str] | None:
        template = self._templates.get(code)
        if not template:
            return None
        title = template.title_template
        body = template.body_template
        for key, value in variables.items():
            title = title.replace(f"{{{{{key}}}}}", str(value))
            body = body.replace(f"{{{{{key}}}}}", str(value))
        return {"title": title, "body": body, "channel": template.channel}

    def send(self, tenant_id: str, template_code: str, recipient_id: str,
             variables: dict[str, Any] | None = None, channel: str = "",
             recipient_address: str = "") -> NotificationMessage:
        variables = variables or {}
        rendered = self.render_template(template_code, variables)
        if not rendered:
            msg = NotificationMessage(
                id=str(uuid.uuid4()), tenant_id=tenant_id, template_code=template_code,
                recipient_id=recipient_id, status="failed", error_message=f"Template '{template_code}' not found",
                created_at=datetime.now(UTC).isoformat(),
            )
            self._messages.append(msg)
            return msg

        target_channel = channel or rendered["channel"]
        msg = NotificationMessage(
            id=str(uuid.uuid4()), tenant_id=tenant_id, template_code=template_code,
            channel=target_channel, recipient_id=recipient_id,
            recipient_address=recipient_address, title=rendered["title"], body=rendered["body"],
            variables=variables, status="sent",
            created_at=datetime.now(UTC).isoformat(),
            sent_at=datetime.now(UTC).isoformat(),
        )
        self._messages.append(msg)
        return msg

    def get_history(self, tenant_id: str, recipient_id: str = "", channel: str = "",
                     status: str = "", limit: int = 50) -> list[NotificationMessage]:
        results = [m for m in self._messages if m.tenant_id == tenant_id]
        if recipient_id:
            results = [m for m in results if m.recipient_id == recipient_id]
        if channel:
            results = [m for m in results if m.channel == channel]
        if status:
            results = [m for m in results if m.status == status]
        return results[:limit]

    def mark_read(self, message_id: str) -> NotificationMessage | None:
        for msg in self._messages:
            if msg.id == message_id:
                msg.status = "read"
                msg.read_at = datetime.now(UTC).isoformat()
                return msg
        return None
