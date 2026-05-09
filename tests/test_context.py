from __future__ import annotations

from erp.shared.context import actor_id_var, actor_type_var, tenant_id_var, trace_id_var


class TestContextVars:
    def test_tenant_id_set_get(self):
        tenant_id_var.set("tenant-123")
        assert tenant_id_var.get("tenant-123") == "tenant-123"
        tenant_id_var.set("")

    def test_trace_id_set_get(self):
        trace_id_var.set("trace-456")
        assert trace_id_var.get("") == "trace-456"
        trace_id_var.set("")

    def test_actor_id_set_get(self):
        actor_id_var.set("user-789")
        assert actor_id_var.get("") == "user-789"
        actor_id_var.set("")

    def test_actor_type_set_get(self):
        actor_type_var.set("pms")
        assert actor_type_var.get("user") == "pms"
        actor_type_var.set("user")
