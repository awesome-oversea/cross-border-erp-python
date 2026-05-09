from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock

from erp.modules.sys.domain.pms_integration_models import PMSFeedbackService
from erp.shared.db.session import get_db_session

HEADERS = {
    "X-Tenant-ID": "tenant-00000000-0000-0000-0000-000000000001",
    "X-Actor-ID": "user-00000000-0000-0000-0000-000000000001",
    "X-Actor-Type": "user",
}


@pytest.fixture(autouse=True)
def _override_feedback_service(app, monkeypatch):
    store: dict[str, SimpleNamespace] = {}
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    async def _submit_feedback(
        self,
        tenant_id: str,
        recommendation_id: str,
        erp_reference_id: str,
        domain: str,
        feedback_type: str,
        feedback_reason: str = "",
        feedback_detail: dict | None = None,
        effect_metrics: dict | None = None,
        operator_id: str = "",
        operator_type: str = "user",
    ):
        record_id = f"fb-{len(store) + 1}"
        record = SimpleNamespace(
            id=record_id,
            tenant_id=tenant_id,
            recommendation_id=recommendation_id,
            erp_reference_id=erp_reference_id,
            domain=domain,
            feedback_type=feedback_type,
            feedback_reason=feedback_reason,
            feedback_detail=__import__("json").dumps(feedback_detail or {}, default=str),
            effect_metrics=__import__("json").dumps(effect_metrics or {}, default=str),
            operator_id=operator_id or HEADERS["X-Actor-ID"],
            operator_type=operator_type,
            trace_id="trace-feedback-001",
            created_at=datetime.now(UTC),
        )
        store[record_id] = record
        return record

    async def _list_feedback(
        self,
        tenant_id: str,
        recommendation_id: str = "",
        domain: str = "",
        feedback_type: str = "",
        page: int = 1,
        page_size: int = 20,
    ):
        items = [r for r in store.values() if r.tenant_id == tenant_id]
        if recommendation_id:
            items = [r for r in items if r.recommendation_id == recommendation_id]
        if domain:
            items = [r for r in items if r.domain == domain]
        if feedback_type:
            items = [r for r in items if r.feedback_type == feedback_type]
        total = len(items)
        start = (page - 1) * page_size
        return items[start:start + page_size], total

    async def _replay_feedback(self, feedback_id: str, tenant_id: str):
        from erp.shared.exceptions import NotFoundException

        record = store.get(feedback_id)
        if not record or record.tenant_id != tenant_id:
            raise NotFoundException(message=f"Feedback '{feedback_id}' not found")
        return record

    monkeypatch.setattr(PMSFeedbackService, "submit_feedback", _submit_feedback)
    monkeypatch.setattr(PMSFeedbackService, "list_feedback", _list_feedback)
    monkeypatch.setattr(PMSFeedbackService, "replay_feedback", _replay_feedback, raising=False)


class TestSysPmsFeedbackFlow:
    @pytest.mark.asyncio
    async def test_submit_feedback_via_acceptance_path(self, client):
        resp = await client.post(
            "/api/sys/api/out/v1/pms/feedback",
            json={
                "recommendation_id": "REC-FB-001",
                "erp_reference_id": "ERP-REC-001",
                "domain": "oms",
                "feedback_type": "executed",
                "feedback_reason": "execution finished",
                "feedback_detail": {"result": "success", "order_id": "ORD-001"},
                "effect_metrics": {"cost_saved": 12.5},
                "operator_id": "user-001",
                "operator_type": "user",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["feedback_type"] == "executed"
        assert body["data"]["domain"] == "oms"

    @pytest.mark.asyncio
    async def test_list_feedback_via_acceptance_path(self, client):
        await client.post(
            "/api/sys/api/out/v1/pms/feedback",
            json={
                "recommendation_id": "REC-FB-002",
                "erp_reference_id": "ERP-REC-002",
                "domain": "scm",
                "feedback_type": "failed",
                "feedback_reason": "downstream timeout",
                "feedback_detail": {"reason": "timeout"},
                "effect_metrics": {},
            },
            headers=HEADERS,
        )

        resp = await client.get(
            "/api/sys/api/out/v1/pms/feedback?domain=scm&feedback_type=failed&page=1&page_size=20",
            headers=HEADERS,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["total"] >= 1
        assert body["data"]["items"][0]["feedback_type"] == "failed"

    @pytest.mark.asyncio
    async def test_replay_failed_feedback_via_compensation_path(self, client):
        create_resp = await client.post(
            "/api/sys/api/out/v1/pms/feedback",
            json={
                "recommendation_id": "REC-FB-003",
                "erp_reference_id": "ERP-REC-003",
                "domain": "pdm",
                "feedback_type": "failed",
                "feedback_reason": "pms unavailable",
                "feedback_detail": {"reason": "503"},
                "effect_metrics": {},
            },
            headers=HEADERS,
        )
        assert create_resp.status_code == 200, create_resp.text
        feedback_id = create_resp.json()["data"]["id"]

        resp = await client.post(
            f"/api/sys/api/out/v1/pms/feedback/{feedback_id}/replay",
            headers=HEADERS,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["id"] == feedback_id
        assert body["data"]["feedback_type"] == "failed"
        assert body["data"]["replayed"] is True
