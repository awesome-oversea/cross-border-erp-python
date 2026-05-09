from __future__ import annotations

import pytest

from erp.connectors.base import BaseConnector, ConnectorConfig, ConnectorType
from erp.connectors.manager import ConnectorInstance, ConnectorManager, get_connector_manager


class FakeConnector(BaseConnector):
    def __init__(self, config=None):
        super().__init__(config or ConnectorConfig(
            connector_id="fake",
            connector_name="Fake Connector",
            connector_type="platform",
            base_url="https://fake.example.com",
        ))

    @property
    def connector_type(self) -> str:
        return ConnectorType.PLATFORM.value


class AnotherFakeConnector(BaseConnector):
    def __init__(self, config=None):
        super().__init__(config or ConnectorConfig(
            connector_id="another_fake",
            connector_name="Another Fake",
            connector_type="logistics",
            base_url="https://another.example.com",
        ))

    @property
    def connector_type(self) -> str:
        return ConnectorType.LOGISTICS.value


class TestConnectorInstance:
    def test_create_instance(self):
        connector = FakeConnector()
        instance = ConnectorInstance(connector)
        assert instance.connector is connector
        assert instance.request_count == 0
        assert instance.error_count == 0
        assert instance.is_healthy is True

    def test_record_request(self):
        connector = FakeConnector()
        instance = ConnectorInstance(connector)
        instance.record_request()
        instance.record_request()
        assert instance.request_count == 2
        assert instance.last_used_at is not None

    def test_record_error(self):
        connector = FakeConnector()
        instance = ConnectorInstance(connector)
        instance.record_error("timeout")
        assert instance.error_count == 1
        assert instance.last_error == "timeout"
        assert instance.last_error_at is not None

    def test_is_healthy_active(self):
        connector = FakeConnector()
        instance = ConnectorInstance(connector)
        assert instance.is_healthy is True

    def test_is_healthy_error(self):
        connector = FakeConnector()
        connector.mark_error()
        instance = ConnectorInstance(connector)
        assert instance.is_healthy is False

    def test_to_dict(self):
        connector = FakeConnector()
        instance = ConnectorInstance(connector)
        d = instance.to_dict()
        assert d["connector_id"] == "fake"
        assert d["connector_name"] == "Fake Connector"
        assert d["connector_type"] == "platform"
        assert d["status"] == "active"
        assert d["is_healthy"] is True
        assert d["request_count"] == 0


class TestConnectorManager:
    def test_register_connector(self):
        manager = ConnectorManager()
        manager.register("fake", FakeConnector)
        assert manager.count == 1

    def test_register_multiple(self):
        manager = ConnectorManager()
        manager.register("fake", FakeConnector)
        manager.register("another", AnotherFakeConnector)
        assert manager.count == 2

    def test_get_connector_creates_instance(self):
        manager = ConnectorManager()
        manager.register("fake", FakeConnector)
        connector = manager.get("fake")
        assert isinstance(connector, FakeConnector)
        assert connector.config.connector_id == "fake"

    def test_get_connector_reuses_instance(self):
        manager = ConnectorManager()
        manager.register("fake", FakeConnector)
        c1 = manager.get("fake")
        c2 = manager.get("fake")
        assert c1 is c2

    def test_get_unknown_connector_raises(self):
        manager = ConnectorManager()
        with pytest.raises(ValueError, match="Unknown connector"):
            manager.get("nonexistent")

    def test_get_instance_info(self):
        manager = ConnectorManager()
        manager.register("fake", FakeConnector)
        manager.get("fake")
        info = manager.get_instance_info("fake")
        assert info is not None
        assert info["connector_id"] == "fake"
        assert info["request_count"] == 1

    def test_get_instance_info_not_initialized(self):
        manager = ConnectorManager()
        manager.register("fake", FakeConnector)
        info = manager.get_instance_info("fake")
        assert info is None

    def test_list_all_with_initialized(self):
        manager = ConnectorManager()
        manager.register("fake", FakeConnector)
        manager.get("fake")
        result = manager.list_all()
        assert len(result) == 1
        assert result[0]["connector_id"] == "fake"
        assert result[0]["status"] == "active"

    def test_list_all_without_initialized(self):
        manager = ConnectorManager()
        manager.register("fake", FakeConnector)
        result = manager.list_all()
        assert len(result) == 1
        assert result[0]["status"] == "not_initialized"

    @pytest.mark.asyncio
    async def test_health_check_all(self):
        manager = ConnectorManager()
        manager.register("fake", FakeConnector)
        manager.get("fake")
        results = await manager.health_check_all()
        assert "fake" in results
        assert results["fake"] is True

    def test_remove_connector(self):
        manager = ConnectorManager()
        manager.register("fake", FakeConnector)
        manager.get("fake")
        assert manager.remove("fake") is True
        assert manager.get_instance_info("fake") is None

    def test_remove_nonexistent(self):
        manager = ConnectorManager()
        assert manager.remove("nonexistent") is False

    def test_reset_connector(self):
        manager = ConnectorManager()
        manager.register("fake", FakeConnector)
        c1 = manager.get("fake")
        c2 = manager.reset("fake")
        assert c1 is not c2

    def test_reset_unknown_raises(self):
        manager = ConnectorManager()
        with pytest.raises(ValueError, match="Unknown connector"):
            manager.reset("nonexistent")

    def test_get_by_type(self):
        manager = ConnectorManager()
        manager.register("fake", FakeConnector)
        manager.register("another", AnotherFakeConnector)
        manager.get("fake")
        manager.get("another")
        platform_connectors = manager.get_by_type("platform")
        logistics_connectors = manager.get_by_type("logistics")
        assert len(platform_connectors) == 1
        assert len(logistics_connectors) == 1

    def test_get_by_type_not_initialized(self):
        manager = ConnectorManager()
        manager.register("fake", FakeConnector)
        platform_connectors = manager.get_by_type("platform")
        assert len(platform_connectors) == 1

    def test_active_count(self):
        manager = ConnectorManager()
        manager.register("fake", FakeConnector)
        manager.get("fake")
        assert manager.active_count == 1

    def test_active_count_zero(self):
        manager = ConnectorManager()
        assert manager.active_count == 0

    def test_register_with_config(self):
        manager = ConnectorManager()
        config = ConnectorConfig(
            connector_id="fake",
            connector_name="Fake",
            connector_type="platform",
            base_url="https://custom.example.com",
            store_id="store-001",
        )
        manager.register("fake", FakeConnector, config)
        connector = manager.get("fake")
        assert connector.config.store_id == "store-001"

    def test_request_count_increments(self):
        manager = ConnectorManager()
        manager.register("fake", FakeConnector)
        manager.get("fake")
        manager.get("fake")
        manager.get("fake")
        info = manager.get_instance_info("fake")
        assert info["request_count"] == 3


class TestGetConnectorManager:
    def test_get_connector_manager_returns_instance(self):
        manager = get_connector_manager()
        assert isinstance(manager, ConnectorManager)

    def test_get_connector_manager_singleton(self):
        m1 = get_connector_manager()
        m2 = get_connector_manager()
        assert m1 is m2

    def test_default_connectors_registered(self):
        manager = get_connector_manager()
        assert manager.count >= 17
