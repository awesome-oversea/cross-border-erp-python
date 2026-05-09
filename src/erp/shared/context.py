from contextvars import ContextVar
from dataclasses import dataclass, field

tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
actor_id_var: ContextVar[str] = ContextVar("actor_id", default="")
actor_type_var: ContextVar[str] = ContextVar("actor_type", default="user")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


@dataclass
class TenantContext:
    tenant_id: str = ""
    trace_id: str = ""
    actor_id: str = ""
    actor_type: str = "user"

    @staticmethod
    def current() -> "TenantContext":
        return TenantContext(
            tenant_id=tenant_id_var.get(""),
            trace_id=trace_id_var.get(""),
            actor_id=actor_id_var.get(""),
            actor_type=actor_type_var.get("user"),
        )

    def apply(self) -> None:
        tenant_id_var.set(self.tenant_id)
        trace_id_var.set(self.trace_id)
        actor_id_var.set(self.actor_id)
        actor_type_var.set(self.actor_type)

    def clear(self) -> None:
        tenant_id_var.set("")
        trace_id_var.set("")
        actor_id_var.set("")
        actor_type_var.set("user")


@dataclass
class PermissionContext:
    tenant_id: str = ""
    org_id: str = ""
    department_id: str = ""
    store_ids: list[str] = field(default_factory=list)
    marketplace: str = ""
    channel: str = ""
    warehouse_ids: list[str] = field(default_factory=list)
    supplier_ids: list[str] = field(default_factory=list)
    category_ids: list[str] = field(default_factory=list)
    data_level: str = "standard"

    @staticmethod
    def current() -> "PermissionContext":
        return PermissionContext(tenant_id=tenant_id_var.get(""))


def get_current_tenant_id() -> str:
    return tenant_id_var.get("")
