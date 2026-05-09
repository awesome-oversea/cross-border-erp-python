from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.iam.domain.auth import validate_access_token
from erp.shared.context import actor_id_var, actor_type_var, tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import ForbiddenException, Result, UnauthorizedException, ValidationException

router = APIRouter(tags=["PMS-Auth"])


class PMSAuthContext:
    def __init__(
        self,
        service_account_id: str,
        tenant_id: str,
        actor_type: str,
        source_system: str,
        idempotency_key: str,
        trace_id: str,
        agent_id: str = "",
        scope: str = "",
        purpose: str = "",
    ):
        self.service_account_id = service_account_id
        self.tenant_id = tenant_id
        self.actor_type = actor_type
        self.source_system = source_system
        self.idempotency_key = idempotency_key
        self.trace_id = trace_id
        self.agent_id = agent_id
        self.scope = scope
        self.purpose = purpose


async def verify_pms_request(
    authorization: str = Header(..., alias="Authorization"),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_actor_type: str = Header(default="service_account", alias="X-Actor-Type"),
    x_source_system: str = Header(default="PMS", alias="X-Source-System"),
    x_idempotency_key: str = Header(default="", alias="X-Idempotency-Key"),
    x_trace_id: str = Header(default="", alias="X-Trace-ID"),
    x_agent_id: str = Header(default="", alias="X-Agent-ID"),
    x_scope: str = Header(default="", alias="X-Scope"),
    x_purpose: str = Header(default="", alias="X-Purpose"),
    session: AsyncSession = Depends(get_db_session),
) -> PMSAuthContext:
    if not authorization.startswith("Bearer "):
        raise UnauthorizedException(message="Invalid authorization header")
    token = authorization[7:]
    payload = validate_access_token(token)

    if payload.get("tenant_id") != x_tenant_id:
        raise ForbiddenException(message="Token tenant does not match X-Tenant-ID")

    tenant_id_var.set(x_tenant_id)
    actor_id_var.set(payload.get("sub", ""))
    actor_type_var.set(x_actor_type)
    if x_trace_id:
        trace_id_var.set(x_trace_id)

    if not x_idempotency_key:
        raise ValidationException(message="X-Idempotency-Key is required for PMS write requests")

    return PMSAuthContext(
        service_account_id=payload.get("sub", ""),
        tenant_id=x_tenant_id,
        actor_type=x_actor_type,
        source_system=x_source_system,
        idempotency_key=x_idempotency_key,
        trace_id=x_trace_id,
        agent_id=x_agent_id,
        scope=x_scope,
        purpose=x_purpose,
    )


async def verify_pms_read_request(
    authorization: str = Header(..., alias="Authorization"),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_actor_type: str = Header(default="service_account", alias="X-Actor-Type"),
    x_source_system: str = Header(default="PMS", alias="X-Source-System"),
    x_trace_id: str = Header(default="", alias="X-Trace-ID"),
    x_scope: str = Header(default="", alias="X-Scope"),
    x_purpose: str = Header(default="", alias="X-Purpose"),
    session: AsyncSession = Depends(get_db_session),
) -> PMSAuthContext:
    if not authorization.startswith("Bearer "):
        raise UnauthorizedException(message="Invalid authorization header")
    token = authorization[7:]
    payload = validate_access_token(token)

    if payload.get("tenant_id") != x_tenant_id:
        raise ForbiddenException(message="Token tenant does not match X-Tenant-ID")

    tenant_id_var.set(x_tenant_id)
    actor_id_var.set(payload.get("sub", ""))
    actor_type_var.set(x_actor_type)
    if x_trace_id:
        trace_id_var.set(x_trace_id)

    return PMSAuthContext(
        service_account_id=payload.get("sub", ""),
        tenant_id=x_tenant_id,
        actor_type=x_actor_type,
        source_system=x_source_system,
        idempotency_key="",
        trace_id=x_trace_id,
        scope=x_scope,
        purpose=x_purpose,
    )


@router.get("/api/internal/v1/health", response_model=None)
async def internal_health():
    return Result.ok(data={"status": "UP", "layer": "internal"}, trace_id=trace_id_var.get(""))


@router.get("/api/pms/v1/health", response_model=None)
async def pms_health():
    return Result.ok(data={"status": "UP", "layer": "pms"}, trace_id=trace_id_var.get(""))
