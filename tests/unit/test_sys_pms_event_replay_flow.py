from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from erp.modules.sys.domain.pms_integration_models import PMSEventSubscriptionService
from erp.shared.db.session import get_db_session
from erp.shared.events.publisher import get_event_publisher

HEADERS = {
    "X-Tenant-ID": "tenant-00000000-0000-0000-0000-000000000001",
    "X-Actor-ID": "user-00000000-0000-0000-0000-000000000001",
    "X-Actor-Type": "user",
}


@pytest.fixture(autouse=True)
def _override_subscription_service(app, monkeypatch):
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()
    store: dict[str, SimpleNamespace] = {}

    async def _create_subscription(
        self,
        tenant_id: str,
        subscriber_name: str,
        subscriber_type: str = "pms",
        event_types: list | None = None,
        domains: list | None = None,
        callback_url: str = "",
        secret_key: str = "",
        retry_policy: dict | None = None,
    ):
        sub_id = f"sub-{len(store) + 1}"
        sub = SimpleNamespace(
            id=sub_id,
            tenant_id=tenant_id,
            subscriber_name=subscriber_name,
            subscriber_type=subscriber_type,
            event_types=__import__("json").dumps(event_types or [], default=str),
            domains=__import__("json").dumps(domains or [], default=str),
            callback_url=callback_url,
            secret_key=secret_key,
            retry_policy=__import__("json").dumps(retry_policy or {}, default=str),
            is_active=True,
            failure_count=0,
            last_event_at=None,
        )
        store[sub_id] = sub
        return sub

    async def _list_subscriptions(self, tenant_id: str, subscriber_type: str = "", is_active: bool | None = None):
        items = [s for s in store.values() if s.tenant_id == tenant_id]
        if subscriber_type:
            items = [s for s in items if s.subscriber_type == subscriber_type]
        if is_active is not None:
            items = [s for s in items if s.is_active == is_active]
        return items

    async def _replay_events(self, tenant_id: str, subscription_id: str, event_type: str = "", domain: str = ""):
        sub = store[subscription_id]
        publisher = get_event_publisher()
        entries = publisher.peek_outbox_entries()
        matched = []
        sub_events = __import__("json").loads(sub.event_types)
        sub_domains = __import__("json").loads(sub.domains)
        for entry in entries:
            if entry.get("tenant_id") != tenant_id:
                continue
            if event_type and entry.get("event_type") != event_type:
                continue
            if domain and entry.get("domain") != domain:
                continue
            event_match = not sub_events or entry.get("event_type") in sub_events or any(
                str(entry.get("event_type", "")).startswith(e.replace("*", "")) for e in sub_events if "*" in e
            )
            domain_match = not sub_domains or entry.get("domain") in sub_domains
            if event_match and domain_match:
                matched.append(entry)
        return matched

    monkeypatch.setattr(PMSEventSubscriptionService, "create_subscription", _create_subscription)
    monkeypatch.setattr(PMSEventSubscriptionService, "list_subscriptions", _list_subscriptions)
    monkeypatch.setattr(PMSEventSubscriptionService, "replay_events", _replay_events)
    yield
    app.dependency_overrides.pop(get_db_session, None)
    get_event_publisher().clear_outbox()


class TestSysPmsEventReplayFlow:
    @pytest.mark.asyncio
    async def test_create_subscription_via_outbound_path(self, client):
        resp = await client.post(
            "/api/sys/api/out/v1/pms/subscriptions",
            json={
                "subscriber_name": "PMS Event Client",
                "subscriber_type": "pms",
                "event_types": ["erp.recommendation.executed.v1"],
                "domains": ["pms_integration"],
                "callback_url": "https://pms.example.com/events",
                "retry_policy": {"max_retries": 3},
            },
            headers=HEADERS,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["subscriber_name"] == "PMS Event Client"

    @pytest.mark.asyncio
    async def test_list_subscriptions_via_outbound_path(self, client):
        await client.post(
            "/api/sys/api/out/v1/pms/subscriptions",
            json={
                "subscriber_name": "PMS Replay Client",
                "subscriber_type": "pms",
                "event_types": ["erp.recommendation.failed.v1"],
                "domains": ["pms_integration"],
                "callback_url": "https://pms.example.com/replay",
            },
            headers=HEADERS,
        )
        resp = await client.get(
            "/api/sys/api/out/v1/pms/subscriptions?subscriber_type=pms",
            headers=HEADERS,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        assert len(body["data"]) >= 1

    @pytest.mark.asyncio
    async def test_replay_subscription_events_via_compensation_path(self, client):
        publisher = get_event_publisher()
        await publisher.publish(
            SimpleNamespace(
                event_id="evt-001",
                event_type="erp.recommendation.executed.v1",
                event_version="v1",
                occurred_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                published_at=None,
                tenant_id=HEADERS["X-Tenant-ID"],
                domain="pms_integration",
                aggregate_type="recommendation",
                aggregate_id="ERP-REC-100",
                trace_id="trace-evt-001",
                actor="user-001",
                data_scope="",
                payload={"result": "ok"},
                payload_hash="",
                to_dict=lambda: {
                    "event_id": "evt-001",
                    "event_type": "erp.recommendation.executed.v1",
                    "event_version": "v1",
                    "occurred_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                    "published_at": None,
                    "tenant_id": HEADERS["X-Tenant-ID"],
                    "domain": "pms_integration",
                    "aggregate_type": "recommendation",
                    "aggregate_id": "ERP-REC-100",
                    "trace_id": "trace-evt-001",
                    "actor": "user-001",
                    "data_scope": "",
                    "payload": {"result": "ok"},
                    "payload_hash": "",
                },
            )
        )

        create_resp = await client.post(
            "/api/sys/api/out/v1/pms/subscriptions",
            json={
                "subscriber_name": "Replay Client",
                "subscriber_type": "pms",
                "event_types": ["erp.recommendation.executed.v1"],
                "domains": ["pms_integration"],
                "callback_url": "https://pms.example.com/replay",
            },
            headers=HEADERS,
        )
        assert create_resp.status_code == 200, create_resp.text
        sub_id = create_resp.json()["data"]["id"]

        resp = await client.post(
            f"/api/sys/api/out/v1/pms/subscriptions/{sub_id}/replay",
            json={"event_type": "erp.recommendation.executed.v1", "domain": "pms_integration"},
            headers=HEADERS,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["subscription_id"] == sub_id
        assert body["data"]["replayed_count"] == 1
        assert body["data"]["events"][0]["event_type"] == "erp.recommendation.executed.v1"
