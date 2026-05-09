from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from erp.connectors.base import BaseConnector, ConnectorConfig, ConnectorStatus
from erp.shared.observability.logging import get_logger

logger = get_logger("erp.connector_manager")


class ConnectorInstance:
    def __init__(self, connector: BaseConnector, created_at: datetime | None = None):
        self.connector = connector
        self.created_at = created_at or datetime.now(UTC)
        self.last_used_at: datetime | None = None
        self.request_count = 0
        self.error_count = 0
        self.last_error: str | None = None
        self.last_error_at: datetime | None = None

    def record_request(self) -> None:
        self.last_used_at = datetime.now(UTC)
        self.request_count += 1

    def record_error(self, error: str) -> None:
        self.error_count += 1
        self.last_error = error
        self.last_error_at = datetime.now(UTC)

    @property
    def is_healthy(self) -> bool:
        return self.connector.status == ConnectorStatus.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        return {
            "connector_id": self.connector.config.connector_id,
            "connector_name": self.connector.connector_name,
            "connector_type": self.connector.connector_type,
            "status": self.connector.status,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "last_error_at": self.last_error_at.isoformat() if self.last_error_at else None,
            "is_healthy": self.is_healthy,
        }


class ConnectorManager:
    def __init__(self):
        self._instances: dict[str, ConnectorInstance] = {}
        self._factories: dict[str, type[BaseConnector]] = {}
        self._configs: dict[str, ConnectorConfig] = {}
        self._health_check_interval = 60
        self._last_health_check: float = 0

    def register(self, connector_id: str, factory: type[BaseConnector], config: ConnectorConfig | None = None) -> None:
        self._factories[connector_id] = factory
        if config:
            self._configs[connector_id] = config
        logger.info("connector_registered", connector_id=connector_id, connector_type=factory.__name__)

    def get(self, connector_id: str) -> BaseConnector:
        if connector_id in self._instances:
            instance = self._instances[connector_id]
            instance.record_request()
            return instance.connector

        if connector_id not in self._factories:
            raise ValueError(f"Unknown connector: {connector_id}")

        factory = self._factories[connector_id]
        config = self._configs.get(connector_id)
        connector = factory(config)
        self._instances[connector_id] = ConnectorInstance(connector)
        self._instances[connector_id].record_request()
        logger.info("connector_instantiated", connector_id=connector_id)
        return connector

    def get_instance_info(self, connector_id: str) -> dict[str, Any] | None:
        if connector_id not in self._instances:
            return None
        return self._instances[connector_id].to_dict()

    def list_all(self) -> list[dict[str, Any]]:
        result = []
        for connector_id, factory in self._factories.items():
            if connector_id in self._instances:
                result.append(self._instances[connector_id].to_dict())
            else:
                config = self._configs.get(connector_id)
                temp = factory(config)
                result.append({
                    "connector_id": connector_id,
                    "connector_name": temp.connector_name,
                    "connector_type": temp.connector_type,
                    "status": "not_initialized",
                    "is_healthy": False,
                })
        return result

    async def health_check_all(self) -> dict[str, bool]:
        results = {}
        now = time.time()
        if now - self._last_health_check < self._health_check_interval:
            return {cid: inst.is_healthy for cid, inst in self._instances.items()}

        self._last_health_check = now
        for connector_id, instance in self._instances.items():
            try:
                healthy = await instance.connector.health_check()
                results[connector_id] = healthy
                if not healthy:
                    logger.warning("connector_unhealthy", connector_id=connector_id)
            except Exception as e:
                results[connector_id] = False
                instance.record_error(str(e))
                logger.error("connector_health_check_failed", connector_id=connector_id, error=str(e))
        return results

    def remove(self, connector_id: str) -> bool:
        if connector_id in self._instances:
            del self._instances[connector_id]
            logger.info("connector_removed", connector_id=connector_id)
            return True
        return False

    def reset(self, connector_id: str) -> BaseConnector:
        if connector_id not in self._factories:
            raise ValueError(f"Unknown connector: {connector_id}")
        self.remove(connector_id)
        return self.get(connector_id)

    def get_by_type(self, connector_type: str) -> list[BaseConnector]:
        connectors = []
        for connector_id, factory in self._factories.items():
            if connector_id in self._instances:
                connector = self._instances[connector_id].connector
                if connector.connector_type == connector_type:
                    connectors.append(connector)
            else:
                config = self._configs.get(connector_id)
                temp = factory(config)
                if temp.connector_type == connector_type:
                    connectors.append(temp)
        return connectors

    @property
    def count(self) -> int:
        return len(self._factories)

    @property
    def active_count(self) -> int:
        return sum(1 for inst in self._instances.values() if inst.is_healthy)


_manager: ConnectorManager | None = None


def get_connector_manager() -> ConnectorManager:
    global _manager
    if _manager is None:
        _manager = ConnectorManager()
        _register_default_connectors(_manager)
    return _manager


def _register_default_connectors(manager: ConnectorManager) -> None:
    """
    注册预置连接器

    说明: 各平台连接器实现尚未就绪，当前函数为空实现。
          连接器代码就绪后在此完成注册即可自动启用。
    """
    from erp.shared.observability.logging import get_logger
    logger = get_logger("erp.connectors.manager")
    logger.info("connectors_not_implemented", message="Platform connectors not yet implemented")
    # TODO: 连接器实现就绪后取消注释
    # from erp.connectors.amazon import AmazonConnector
    # from erp.connectors.logistics import DHLConnector, FedExConnector, FourPXConnector, UPSConnector, YanwenConnector
    # from erp.connectors.payment import AlipayConnector, PayPalConnector, StripeConnector
    # from erp.connectors.procurement import Alibaba1688Connector, AlibabaGlobalConnector
    # from erp.connectors.shopify import ShopifyConnector
    # from erp.connectors.tiktok_shop import TikTokShopConnector
    # from erp.connectors.warehouse import FBAConnector, ShipBobConnector
    # from erp.connectors.tax import EuVatConnector, UsTaxConnector
