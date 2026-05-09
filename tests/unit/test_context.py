from erp.shared.context import PermissionContext, TenantContext


def test_tenant_context_current():
    ctx = TenantContext(tenant_id="t1", trace_id="tr1", actor_id="a1", actor_type="user")
    ctx.apply()
    current = TenantContext.current()
    assert current.tenant_id == "t1"
    assert current.trace_id == "tr1"
    assert current.actor_id == "a1"
    ctx.clear()
    current = TenantContext.current()
    assert current.tenant_id == ""


def test_tenant_context_clear():
    ctx = TenantContext(tenant_id="t1")
    ctx.apply()
    ctx.clear()
    current = TenantContext.current()
    assert current.tenant_id == ""


def test_permission_context():
    pc = PermissionContext(
        tenant_id="t1",
        store_ids=["s1", "s2"],
        warehouse_ids=["w1"],
        data_level="standard",
    )
    assert pc.tenant_id == "t1"
    assert len(pc.store_ids) == 2
    assert pc.data_level == "standard"
