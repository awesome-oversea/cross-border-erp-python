from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.iam.application.services import AuditLogService
from erp.modules.iam.infrastructure.repositories import SqlAuditLogRepository
from erp.modules.iam.interfaces.deps import get_current_user
from erp.shared.context import trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

router = APIRouter(prefix="/iam/v1/audit-logs", tags=["IAM-AuditLog"])


def _audit_service(session: AsyncSession = Depends(get_db_session)) -> AuditLogService:
    return AuditLogService(SqlAuditLogRepository(session))


@router.get("", response_model=None)
async def list_audit_logs(
    module: str = Query(default=""),
    action: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current: dict = Depends(get_current_user),
    svc: AuditLogService = Depends(_audit_service),
):
    tid = current["tenant_id"]
    items, total = await svc.list_logs(tid, module=module, action=action, page=page, page_size=page_size)
    return Result.paginate(
        items=[i.model_dump() for i in items], total=total, page=page, page_size=page_size, trace_id=trace_id_var.get("")
    )


@router.get("/stats", response_model=None)
async def get_audit_stats(
    days: int = Query(default=30, ge=1, le=365),
    current: dict = Depends(get_current_user),
    svc: AuditLogService = Depends(_audit_service),
):
    tid = current["tenant_id"]
    data = await svc.get_stats(tid, days=days)
    return Result.ok(data=data.model_dump(), trace_id=trace_id_var.get(""))
