from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.notification_center.domain.engine import NotificationEngine
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.notification_center")

_engine_instance = NotificationEngine()


class NotificationCenterService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = _engine_instance

    async def send(self, tenant_id: str, template_code: str, recipient_id: str,
                    variables: dict | None = None, channel: str = "",
                    recipient_address: str = "") -> dict:
        msg = self._engine.send(tenant_id, template_code, recipient_id, variables, channel, recipient_address)
        return {"id": msg.id, "status": msg.status, "title": msg.title, "channel": msg.channel,
                "error_message": msg.error_message}

    async def get_templates(self, tenant_id: str) -> list[dict]:
        templates = self._engine.get_templates()
        return [{"code": t.code, "title_template": t.title_template, "body_template": t.body_template,
                 "channel": t.channel, "is_active": t.is_active} for t in templates]

    async def create_template(self, tenant_id: str, code: str, title_template: str,
                               body_template: str, channel: str = "in_app") -> dict:
        template = self._engine.register_template(code, title_template, body_template, channel)
        return {"code": template.code, "title_template": template.title_template,
                "body_template": template.body_template, "channel": template.channel}

    async def get_history(self, tenant_id: str, recipient_id: str = "", channel: str = "",
                           status: str = "", limit: int = 50) -> list[dict]:
        messages = self._engine.get_history(tenant_id, recipient_id, channel, status, limit)
        return [{"id": m.id, "template_code": m.template_code, "channel": m.channel,
                 "recipient_id": m.recipient_id, "title": m.title, "status": m.status,
                 "created_at": m.created_at, "sent_at": m.sent_at} for m in messages]

    async def mark_read(self, tenant_id: str, message_id: str) -> dict:
        msg = self._engine.mark_read(message_id)
        if not msg:
            return {"success": False, "error": "Message not found"}
        return {"id": msg.id, "status": msg.status, "read_at": msg.read_at}
