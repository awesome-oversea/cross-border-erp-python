from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from erp.modules.sys.application.services import RecommendationService
from erp.shared.events.publisher import get_event_publisher
from erp.shared.workflow.models import ApprovalAction, ApprovalActionRequest, ApprovalStatus, ApprovalSubmitRequest
from erp.shared.workflow.service import ApprovalService


class _FakeRecommendationRepository:
    def __init__(self, rec):
        self.rec = rec

    async def create(self, rec):
        return rec

    async def get_by_id(self, rec_id: str, tenant_id: str):
        if self.rec.id == rec_id and self.rec.tenant_id == tenant_id:
            return self.rec
        return None

    async def get_by_recommendation_id(self, recommendation_id: str, tenant_id: str):
        return None

    async def list_by_domain(self, tenant_id: str, domain: str = "", status: str = "", page: int = 1, page_size: int = 20):
        return [self.rec], 1

    async def update_status(self, rec_id: str, tenant_id: str, status: str, **kwargs):
        if self.rec.id != rec_id or self.rec.tenant_id != tenant_id:
            return None
        self.rec.status = status
        for key, value in kwargs.items():
            setattr(self.rec, key, value)
        return self.rec

    async def check_idempotency(self, idempotency_key: str, tenant_id: str):
        return None


@pytest.fixture(autouse=True)
def _clear_event_outbox():
    publisher = get_event_publisher()
    publisher.clear_outbox()
    yield
    publisher.clear_outbox()


class TestRecommendationApprovalOrchestration:
    @pytest.mark.asyncio
    async def test_transition_to_pending_approval_submits_approval_instance(self, monkeypatch):
        rec = SimpleNamespace(
            id="rec-001",
            tenant_id="tenant-001",
            recommendation_id="REC-001",
            domain="oms",
            status="accepted",
            rejection_reason="",
            execution_result_json="{}",
        )
        repo = _FakeRecommendationRepository(rec)
        session = SimpleNamespace(add=lambda _: None, flush=AsyncMock())
        captured = {}

        async def _submit(self, tenant_id: str, req: ApprovalSubmitRequest, submitted_by: str = ""):
            captured["tenant_id"] = tenant_id
            captured["req"] = req
            captured["submitted_by"] = submitted_by
            return SimpleNamespace(id="appr-001", status=ApprovalStatus.PENDING)

        monkeypatch.setattr(ApprovalService, "submit", _submit)

        svc = RecommendationService(session, rec_repo=repo)
        result = await svc.transition_status("rec-001", "tenant-001", "pending_approval")

        assert result.status == "pending_approval"
        assert captured["tenant_id"] == "tenant-001"
        assert captured["req"].flow_code == "pms_recommendation_approval"
        assert captured["req"].target_type == "pms_recommendation"
        assert captured["req"].target_id == "rec-001"
        assert "REC-001" in captured["req"].title


class TestApprovalServiceEvents:
    @pytest.mark.asyncio
    async def test_submit_publishes_approval_submitted_event(self, monkeypatch):
        session = SimpleNamespace(add=lambda _: None, flush=AsyncMock())
        flow = SimpleNamespace(
            id="flow-001",
            nodes_json=json.dumps([
                {
                    "node_id": "n1",
                    "node_name": "业务负责人确认",
                    "node_type": "role",
                    "approver_role_codes": ["biz_owner"],
                    "min_approvals": 1,
                    "sort_order": 0,
                }
            ]),
        )

        async def _get_flow_by_code(self, flow_code: str, tenant_id: str):
            return flow

        monkeypatch.setattr(ApprovalService, "_get_flow_by_code", _get_flow_by_code)

        svc = ApprovalService(session)
        instance = await svc.submit(
            tenant_id="tenant-001",
            req=ApprovalSubmitRequest(
                flow_code="pms_recommendation_approval",
                domain="sys",
                target_type="pms_recommendation",
                target_id="rec-001",
                title="PMS recommendation REC-001",
                description="approval required",
            ),
            submitted_by="user-001",
        )

        entries = get_event_publisher().peek_outbox_entries()
        assert instance.status == ApprovalStatus.PENDING
        assert len(entries) == 1
        assert entries[0]["event_type"] == "erp.sys.approval.submitted.v1"
        assert entries[0]["aggregate_id"] == instance.id
        assert entries[0]["payload"]["approval_type"] == "pms_recommendation"
        assert entries[0]["payload"]["business_id"] == "rec-001"
        assert entries[0]["payload"]["submitter_id"] == "user-001"

    @pytest.mark.asyncio
    async def test_final_approve_publishes_approval_completed_event(self, monkeypatch):
        session = SimpleNamespace(add=lambda _: None, flush=AsyncMock())
        task = SimpleNamespace(
            id="task-001",
            instance_id="appr-001",
            tenant_id="tenant-001",
            status="pending",
            action=None,
            comment="",
            completed_at=None,
        )
        instance = SimpleNamespace(
            id="appr-001",
            tenant_id="tenant-001",
            flow_id="flow-001",
            flow_code="pms_recommendation_approval",
            domain="sys",
            target_type="pms_recommendation",
            target_id="rec-001",
            title="PMS recommendation REC-001",
            description="approval required",
            current_node_index=0,
            status=ApprovalStatus.PENDING.value,
            submitted_by="user-001",
            submitted_at=None,
            completed_at=None,
        )
        flow = SimpleNamespace(
            id="flow-001",
            nodes_json=json.dumps([
                {
                    "node_id": "n1",
                    "node_name": "业务负责人确认",
                    "node_type": "role",
                    "approver_role_codes": ["biz_owner"],
                    "min_approvals": 1,
                    "sort_order": 0,
                }
            ]),
        )

        async def _get_task(self, task_id: str, tenant_id: str):
            return task

        async def _get_instance(self, instance_id: str, tenant_id: str):
            return instance

        async def _get_flow_by_id(self, flow_id: str, tenant_id: str):
            return flow

        monkeypatch.setattr(ApprovalService, "_get_task", _get_task)
        monkeypatch.setattr(ApprovalService, "_get_instance", _get_instance)
        monkeypatch.setattr(ApprovalService, "_get_flow_by_id", _get_flow_by_id)

        svc = ApprovalService(session)
        result = await svc.approve(
            task_id="task-001",
            tenant_id="tenant-001",
            req=ApprovalActionRequest(action=ApprovalAction.APPROVE, comment="looks good"),
            actor_id="manager-001",
        )

        entries = get_event_publisher().peek_outbox_entries()
        assert result.status == ApprovalStatus.APPROVED
        assert len(entries) == 1
        assert entries[0]["event_type"] == "erp.sys.approval.completed.v1"
        assert entries[0]["aggregate_id"] == "appr-001"
        assert entries[0]["payload"]["result"] == "approved"
        assert entries[0]["payload"]["business_id"] == "rec-001"
        assert entries[0]["payload"]["approval_type"] == "pms_recommendation"

    @pytest.mark.asyncio
    async def test_reject_publishes_approval_completed_event(self, monkeypatch):
        session = SimpleNamespace(add=lambda _: None, flush=AsyncMock())
        task = SimpleNamespace(
            id="task-002",
            instance_id="appr-002",
            tenant_id="tenant-001",
            status="pending",
            action=None,
            comment="",
            completed_at=None,
        )
        instance = SimpleNamespace(
            id="appr-002",
            tenant_id="tenant-001",
            flow_id="flow-001",
            flow_code="pms_recommendation_approval",
            domain="sys",
            target_type="pms_recommendation",
            target_id="rec-002",
            title="PMS recommendation REC-002",
            description="approval required",
            current_node_index=0,
            status=ApprovalStatus.PENDING.value,
            submitted_by="user-001",
            submitted_at=None,
            completed_at=None,
        )

        async def _get_task(self, task_id: str, tenant_id: str):
            return task

        async def _get_instance(self, instance_id: str, tenant_id: str):
            return instance

        monkeypatch.setattr(ApprovalService, "_get_task", _get_task)
        monkeypatch.setattr(ApprovalService, "_get_instance", _get_instance)

        svc = ApprovalService(session)
        result = await svc.approve(
            task_id="task-002",
            tenant_id="tenant-001",
            req=ApprovalActionRequest(action=ApprovalAction.REJECT, comment="blocked"),
            actor_id="manager-001",
        )

        entries = get_event_publisher().peek_outbox_entries()
        assert result.status == ApprovalStatus.REJECTED
        assert len(entries) == 1
        assert entries[0]["event_type"] == "erp.sys.approval.completed.v1"
        assert entries[0]["aggregate_id"] == "appr-002"
        assert entries[0]["payload"]["result"] == "rejected"
        assert entries[0]["payload"]["business_id"] == "rec-002"
