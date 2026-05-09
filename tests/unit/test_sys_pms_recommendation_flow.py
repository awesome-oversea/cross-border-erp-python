from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Header

from erp.modules.sys import interfaces as sys_interfaces
from erp.modules.sys.application.services import RecommendationService
from erp.shared.auth.pms_auth import verify_pms_read_request, verify_pms_request
from erp.shared.db.session import get_db_session

PMS_HEADERS = {
    "X-Tenant-ID": "tenant-00000000-0000-0000-0000-000000000001",
    "X-Actor-ID": "pms-client-001",
    "X-Actor-Type": "pms",
    "Authorization": "Bearer test-token",
    "X-Idempotency-Key": "idem-rec-001",
    "X-Source-System": "PMS",
    "X-Trace-ID": "trace-pms-001",
    "X-Scope": "selection",
    "X-Purpose": "acceptance-test",
}


@pytest.fixture(autouse=True)
def _override_pms_deps(app, monkeypatch):
    mock_session = AsyncMock()
    store: dict[str, SimpleNamespace] = {}
    idem_keys: set[str] = set()

    async def _write_auth(
        authorization: str = Header(default="Bearer test-token", alias="Authorization"),
        x_tenant_id: str = Header(default=PMS_HEADERS["X-Tenant-ID"], alias="X-Tenant-ID"),
        x_actor_type: str = Header(default="pms", alias="X-Actor-Type"),
        x_source_system: str = Header(default="PMS", alias="X-Source-System"),
        x_idempotency_key: str = Header(default="", alias="X-Idempotency-Key"),
        x_trace_id: str = Header(default="trace-pms-001", alias="X-Trace-ID"),
        x_scope: str = Header(default="selection", alias="X-Scope"),
        x_purpose: str = Header(default="acceptance-test", alias="X-Purpose"),
    ):
        return SimpleNamespace(
            service_account_id="pms-client-001",
            tenant_id=x_tenant_id,
            actor_type=x_actor_type,
            source_system=x_source_system,
            idempotency_key=x_idempotency_key,
            trace_id=x_trace_id,
            agent_id="agent-001",
            scope=x_scope,
            purpose=x_purpose,
        )

    async def _read_auth(
        authorization: str = Header(default="Bearer test-token", alias="Authorization"),
        x_tenant_id: str = Header(default=PMS_HEADERS["X-Tenant-ID"], alias="X-Tenant-ID"),
        x_actor_type: str = Header(default="pms", alias="X-Actor-Type"),
        x_source_system: str = Header(default="PMS", alias="X-Source-System"),
        x_trace_id: str = Header(default="trace-pms-001", alias="X-Trace-ID"),
        x_scope: str = Header(default="selection", alias="X-Scope"),
        x_purpose: str = Header(default="acceptance-test", alias="X-Purpose"),
    ):
        return SimpleNamespace(
            service_account_id="pms-client-001",
            tenant_id=x_tenant_id,
            actor_type=x_actor_type,
            source_system=x_source_system,
            idempotency_key="",
            trace_id=x_trace_id,
            agent_id="agent-001",
            scope=x_scope,
            purpose=x_purpose,
        )

    async def _receive_recommendation(
        self,
        tenant_id: str,
        recommendation_id: str,
        domain: str,
        recommendation_type: str,
        target_object_type: str = "",
        target_object_id: str = "",
        content: dict | None = None,
        score: float = 0.0,
        confidence: float = 0.0,
        evidence_chain_id: str = "",
        data_sources: list | None = None,
        risk_flags: list | None = None,
        explainability: str = "",
        requested_action: str = "",
        idempotency_key: str = "",
        actor_id: str = "",
        actor_type: str = "service_account",
        agent_id: str = "",
        scope: str = "",
        purpose: str = "",
    ):
        if idempotency_key and idempotency_key in idem_keys:
            from erp.shared.exceptions import IdempotencyConflictException
            raise IdempotencyConflictException(message="Duplicate recommendation request")
        if idempotency_key:
            idem_keys.add(idempotency_key)
        rec_id = f"erp-{recommendation_id.lower()}"
        rec = SimpleNamespace(
            id=rec_id,
            recommendation_id=recommendation_id,
            erp_reference_id=rec_id,
            tenant_id=tenant_id,
            domain=domain,
            recommendation_type=recommendation_type,
            target_object_type=target_object_type,
            target_object_id=target_object_id,
            content_json=__import__("json").dumps(content or {}, default=str),
            score=score,
            confidence=confidence,
            evidence_chain_id=evidence_chain_id,
            data_sources_json=__import__("json").dumps(data_sources or [], default=str),
            risk_flags_json=__import__("json").dumps(risk_flags or [], default=str),
            explainability=explainability,
            rejection_reason="",
            execution_result_json="{}",
            trace_id="trace-pms-001",
            status="submitted",
            created_at=None,
        )
        store[rec_id] = rec
        return rec

    async def _list_by_tenant(self, tenant_id: str, domain: str = "", status: str = "", page: int = 1, page_size: int = 20):
        items = [r for r in store.values() if r.tenant_id == tenant_id]
        if domain:
            items = [r for r in items if r.domain == domain]
        if status:
            items = [r for r in items if r.status == status]
        total = len(items)
        start = (page - 1) * page_size
        return items[start:start + page_size], total

    async def _get_or_raise(self, rec_id: str, tenant_id: str):
        from erp.shared.exceptions import NotFoundException
        rec = store.get(rec_id)
        if not rec or rec.tenant_id != tenant_id:
            raise NotFoundException(message=f"Recommendation '{rec_id}' not found")
        return rec

    async def _transition_status(self, rec_id: str, tenant_id: str, new_status: str, reason: str = "", execution_result: dict | None = None):
        from erp.modules.sys.application.services import RECOMMENDATION_STATE_TRANSITIONS
        from erp.shared.exceptions import NotFoundException, ValidationException
        rec = store.get(rec_id)
        if not rec or rec.tenant_id != tenant_id:
            raise NotFoundException(message=f"Recommendation '{rec_id}' not found")
        allowed = RECOMMENDATION_STATE_TRANSITIONS.get(rec.status, [])
        if new_status not in allowed:
            raise ValidationException(message=f"Cannot transition from '{rec.status}' to '{new_status}'. Allowed: {allowed}")
        rec.status = new_status
        if reason:
            rec.rejection_reason = reason
        if execution_result:
            rec.execution_result_json = __import__("json").dumps(execution_result, default=str)
        return rec

    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[verify_pms_request] = _write_auth
    app.dependency_overrides[verify_pms_read_request] = _read_auth
    monkeypatch.setattr(RecommendationService, "receive_recommendation", _receive_recommendation)
    monkeypatch.setattr(RecommendationService, "list_by_tenant", _list_by_tenant)
    monkeypatch.setattr(RecommendationService, "get_or_raise", _get_or_raise)
    monkeypatch.setattr(RecommendationService, "transition_status", _transition_status)
    yield
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(verify_pms_request, None)
    app.dependency_overrides.pop(verify_pms_read_request, None)


class TestSysPmsRecommendationFlow:
    @pytest.mark.asyncio
    async def test_receive_recommendation_via_acceptance_path(self, client):
        resp = await client.post(
            "/api/sys/api/in/v1/pms/recommendations",
            json={
                "recommendation_id": "REC-001",
                "domain": "pdm",
                "recommendation_type": "product_selection",
                "target_object_type": "sku",
                "target_object_id": "SKU-001",
                "content": {"sku": "SKU-001", "action": "select"},
                "score": 0.92,
                "confidence": 0.88,
                "data_sources": ["pms", "bi"],
                "risk_flags": ["low-margin"],
                "requested_action": "create_draft",
            },
            headers=PMS_HEADERS,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["recommendation_id"] == "REC-001"
        assert body["data"]["status"] == "submitted"

    @pytest.mark.asyncio
    async def test_list_recommendations_via_acceptance_path(self, client):
        resp = await client.get(
            "/api/sys/api/in/v1/pms/recommendations?domain=pdm&status=submitted&page=1&page_size=20",
            headers={k: v for k, v in PMS_HEADERS.items() if k != "X-Idempotency-Key"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        assert isinstance(body["data"]["items"], list)
        assert "total" in body["data"]

    @pytest.mark.asyncio
    async def test_get_recommendation_detail_via_acceptance_path(self, client):
        create_resp = await client.post(
            "/api/sys/api/in/v1/pms/recommendations",
            json={
                "recommendation_id": "REC-DETAIL-001",
                "domain": "scm",
                "recommendation_type": "replenishment",
                "content": {"warehouse_id": "wh-001", "sku_ids": ["sku-1"]},
            },
            headers={**PMS_HEADERS, "X-Idempotency-Key": "idem-detail-001"},
        )
        assert create_resp.status_code == 200, create_resp.text
        rec_id = create_resp.json()["data"]["erp_reference_id"]

        resp = await client.get(
            f"/api/sys/api/in/v1/pms/recommendations/{rec_id}",
            headers={k: v for k, v in PMS_HEADERS.items() if k != "X-Idempotency-Key"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["recommendation_id"] == "REC-DETAIL-001"
        assert body["data"]["domain"] == "scm"

    @pytest.mark.asyncio
    async def test_transition_recommendation_status_through_approval_and_execution(self, client):
        create_resp = await client.post(
            "/api/sys/api/in/v1/pms/recommendations",
            json={
                "recommendation_id": "REC-FLOW-001",
                "domain": "oms",
                "recommendation_type": "order_risk",
                "content": {"order_id": "ORD-001", "risk_level": "high"},
            },
            headers={**PMS_HEADERS, "X-Idempotency-Key": "idem-flow-001"},
        )
        assert create_resp.status_code == 200, create_resp.text
        rec_id = create_resp.json()["data"]["erp_reference_id"]

        for status in ["accepted", "pending_approval", "approved", "executing", "executed"]:
            resp = await client.put(
                f"/api/sys/api/in/v1/pms/recommendations/{rec_id}/status",
                json={
                    "status": status,
                    "reason": "acceptance-flow",
                    "execution_result": {"step": status},
                },
                headers={**PMS_HEADERS, "X-Idempotency-Key": f"idem-{status}-001"},
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["code"] == 0
            assert body["data"]["status"] == status

    @pytest.mark.asyncio
    async def test_duplicate_idempotency_key_returns_business_error(self, client):
        payload = {
            "recommendation_id": "REC-IDEM-001",
            "domain": "pdm",
            "recommendation_type": "product_selection",
            "content": {"sku": "SKU-002"},
        }
        resp1 = await client.post(
            "/api/sys/api/in/v1/pms/recommendations",
            json=payload,
            headers={**PMS_HEADERS, "X-Idempotency-Key": "idem-dup-001"},
        )
        assert resp1.status_code == 200, resp1.text

        resp2 = await client.post(
            "/api/sys/api/in/v1/pms/recommendations",
            json={**payload, "recommendation_id": "REC-IDEM-002"},
            headers={**PMS_HEADERS, "X-Idempotency-Key": "idem-dup-001"},
        )
        assert resp2.status_code == 200, resp2.text
        body = resp2.json()
        assert body["code"] == 1002
