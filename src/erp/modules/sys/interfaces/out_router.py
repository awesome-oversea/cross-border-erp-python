from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from erp.shared.context import trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/out/v1", tags=["SYS-Outbound"])


class NotificationSendRequest(BaseModel):
    channel: str = "email"
    recipients: list[str] = []
    subject: str = ""
    content: str = ""
    priority: str = "normal"
    template_code: str = ""
    template_params: dict = {}


@router.post("/notification/send", response_model=None)
async def send_notification(req: NotificationSendRequest, session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"channel": req.channel, "recipients_count": len(req.recipients),
                           "status": "sent", "subject": req.subject},
                     trace_id=trace_id_var.get(""))
