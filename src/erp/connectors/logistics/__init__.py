from __future__ import annotations

import uuid
from datetime import UTC, datetime

from erp.connectors.base import (
    CarrierConnector,
    ConnectorConfig,
    RateEstimateParams,
    RateOption,
    ShipmentCreate,
    ShipmentResult,
    TrackingInfo,
)


class YanwenConnector(CarrierConnector):
    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="yanwen",
            connector_name="Yanwen",
            connector_type="logistics",
            base_url="https://openapi.yanwen.com/api",
        ))

    async def estimate_rate(self, params: RateEstimateParams) -> list[RateOption]:
        base_rate = 8.0 + params.weight_kg * 12.0
        if params.destination_country == "US":
            base_rate *= 1.0
        elif params.destination_country == "GB":
            base_rate *= 1.1
        elif params.destination_country == "DE":
            base_rate *= 1.15
        return [
            RateOption(
                service_code="YANWEN_ECONOMY",
                service_name="Yanwen Economy",
                carrier="yanwen",
                cost=round(base_rate * 0.8, 2),
                currency="CNY",
                estimated_days_min=15,
                estimated_days_max=30,
                tracking_available=True,
            ),
            RateOption(
                service_code="YANWEN_STANDARD",
                service_name="Yanwen Standard",
                carrier="yanwen",
                cost=round(base_rate, 2),
                currency="CNY",
                estimated_days_min=7,
                estimated_days_max=15,
                tracking_available=True,
            ),
            RateOption(
                service_code="YANWEN_EXPRESS",
                service_name="Yanwen Express",
                carrier="yanwen",
                cost=round(base_rate * 1.5, 2),
                currency="CNY",
                estimated_days_min=3,
                estimated_days_max=7,
                tracking_available=True,
            ),
        ]

    async def create_shipment(self, shipment: ShipmentCreate) -> ShipmentResult:
        tracking = f"YW{uuid.uuid4().hex[:16].upper()}"
        return ShipmentResult(
            success=True,
            tracking_number=tracking,
            label_url=f"https://labels.yanwen.com/{tracking}.pdf",
            carrier="yanwen",
            cost=0.0,
            currency="CNY",
        )

    async def get_tracking(self, tracking_number: str) -> TrackingInfo:
        return TrackingInfo(
            tracking_number=tracking_number,
            carrier="yanwen",
            status="in_transit",
            events=[
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "location": "Shanghai, CN",
                    "description": "Package received by Yanwen",
                    "status": "picked_up",
                },
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "location": "Shanghai, CN",
                    "description": "Departed from origin facility",
                    "status": "in_transit",
                },
            ],
            estimated_delivery="",
        )

    async def cancel_shipment(self, tracking_number: str) -> bool:
        return True


class FourPXConnector(CarrierConnector):
    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="4px",
            connector_name="4PX",
            connector_type="logistics",
            base_url="https://open.4px.com/api",
        ))

    async def estimate_rate(self, params: RateEstimateParams) -> list[RateOption]:
        base_rate = 7.5 + params.weight_kg * 11.0
        return [
            RateOption(
                service_code="4PX_ECONOMY",
                service_name="4PX Economy",
                carrier="4px",
                cost=round(base_rate * 0.85, 2),
                currency="CNY",
                estimated_days_min=12,
                estimated_days_max=25,
                tracking_available=True,
            ),
            RateOption(
                service_code="4PX_STANDARD",
                service_name="4PX Standard",
                carrier="4px",
                cost=round(base_rate, 2),
                currency="CNY",
                estimated_days_min=7,
                estimated_days_max=14,
                tracking_available=True,
            ),
        ]

    async def create_shipment(self, shipment: ShipmentCreate) -> ShipmentResult:
        tracking = f"4PX{uuid.uuid4().hex[:14].upper()}"
        return ShipmentResult(
            success=True,
            tracking_number=tracking,
            label_url=f"https://labels.4px.com/{tracking}.pdf",
            carrier="4px",
            cost=0.0,
            currency="CNY",
        )

    async def get_tracking(self, tracking_number: str) -> TrackingInfo:
        return TrackingInfo(
            tracking_number=tracking_number,
            carrier="4px",
            status="in_transit",
            events=[
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "location": "Shenzhen, CN",
                    "description": "Package received by 4PX",
                    "status": "picked_up",
                },
            ],
            estimated_delivery="",
        )

    async def cancel_shipment(self, tracking_number: str) -> bool:
        return True


class DHLConnector(CarrierConnector):
    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="dhl",
            connector_name="DHL",
            connector_type="logistics",
            base_url="https://api.dhl.com",
        ))

    async def estimate_rate(self, params: RateEstimateParams) -> list[RateOption]:
        base_rate = 15.0 + params.weight_kg * 20.0
        return [
            RateOption(
                service_code="DHL_EXPRESS_WORLDWIDE",
                service_name="DHL Express Worldwide",
                carrier="dhl",
                cost=round(base_rate, 2),
                currency="USD",
                estimated_days_min=2,
                estimated_days_max=5,
                tracking_available=True,
            ),
            RateOption(
                service_code="DHL_ECOMMERCE",
                service_name="DHL eCommerce",
                carrier="dhl",
                cost=round(base_rate * 0.6, 2),
                currency="USD",
                estimated_days_min=10,
                estimated_days_max=20,
                tracking_available=True,
            ),
        ]

    async def create_shipment(self, shipment: ShipmentCreate) -> ShipmentResult:
        tracking = f"DHL{uuid.uuid4().hex[:12].upper()}"
        return ShipmentResult(
            success=True,
            tracking_number=tracking,
            label_url=f"https://labels.dhl.com/{tracking}.pdf",
            carrier="dhl",
            cost=0.0,
            currency="USD",
        )

    async def get_tracking(self, tracking_number: str) -> TrackingInfo:
        return TrackingInfo(
            tracking_number=tracking_number,
            carrier="dhl",
            status="in_transit",
            events=[
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "location": "Leipzig, DE",
                    "description": "Shipment processed at DHL hub",
                    "status": "in_transit",
                },
            ],
            estimated_delivery="",
        )

    async def cancel_shipment(self, tracking_number: str) -> bool:
        return True


class FedExConnector(CarrierConnector):
    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="fedex",
            connector_name="FedEx",
            connector_type="logistics",
            base_url="https://apis.fedex.com",
        ))

    async def estimate_rate(self, params: RateEstimateParams) -> list[RateOption]:
        base_rate = 18.0 + params.weight_kg * 22.0
        return [
            RateOption(
                service_code="FEDEX_INTERNATIONAL_PRIORITY",
                service_name="FedEx International Priority",
                carrier="fedex",
                cost=round(base_rate, 2),
                currency="USD",
                estimated_days_min=1,
                estimated_days_max=3,
                tracking_available=True,
            ),
            RateOption(
                service_code="FEDEX_INTERNATIONAL_ECONOMY",
                service_name="FedEx International Economy",
                carrier="fedex",
                cost=round(base_rate * 0.7, 2),
                currency="USD",
                estimated_days_min=5,
                estimated_days_max=10,
                tracking_available=True,
            ),
        ]

    async def create_shipment(self, shipment: ShipmentCreate) -> ShipmentResult:
        tracking = f"FX{uuid.uuid4().hex[:14].upper()}"
        return ShipmentResult(
            success=True,
            tracking_number=tracking,
            label_url=f"https://labels.fedex.com/{tracking}.pdf",
            carrier="fedex",
            cost=0.0,
            currency="USD",
        )

    async def get_tracking(self, tracking_number: str) -> TrackingInfo:
        return TrackingInfo(
            tracking_number=tracking_number,
            carrier="fedex",
            status="in_transit",
            events=[
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "location": "Memphis, TN, US",
                    "description": "Package in transit",
                    "status": "in_transit",
                },
            ],
            estimated_delivery="",
        )

    async def cancel_shipment(self, tracking_number: str) -> bool:
        return True


class UPSConnector(CarrierConnector):
    def __init__(self, config: ConnectorConfig | None = None):
        super().__init__(config or ConnectorConfig(
            connector_id="ups",
            connector_name="UPS",
            connector_type="logistics",
            base_url="https://onlinetools.ups.com/api",
        ))

    async def estimate_rate(self, params: RateEstimateParams) -> list[RateOption]:
        base_rate = 16.0 + params.weight_kg * 21.0
        return [
            RateOption(
                service_code="UPS_WORLDWIDE_EXPRESS",
                service_name="UPS Worldwide Express",
                carrier="ups",
                cost=round(base_rate, 2),
                currency="USD",
                estimated_days_min=1,
                estimated_days_max=3,
                tracking_available=True,
            ),
            RateOption(
                service_code="UPS_WORLDWIDE_EXPEDITED",
                service_name="UPS Worldwide Expedited",
                carrier="ups",
                cost=round(base_rate * 0.75, 2),
                currency="USD",
                estimated_days_min=3,
                estimated_days_max=7,
                tracking_available=True,
            ),
        ]

    async def create_shipment(self, shipment: ShipmentCreate) -> ShipmentResult:
        tracking = f"1Z{uuid.uuid4().hex[:14].upper()}"
        return ShipmentResult(
            success=True,
            tracking_number=tracking,
            label_url=f"https://labels.ups.com/{tracking}.pdf",
            carrier="ups",
            cost=0.0,
            currency="USD",
        )

    async def get_tracking(self, tracking_number: str) -> TrackingInfo:
        return TrackingInfo(
            tracking_number=tracking_number,
            carrier="ups",
            status="in_transit",
            events=[
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "location": "Louisville, KY, US",
                    "description": "Package in transit",
                    "status": "in_transit",
                },
            ],
            estimated_delivery="",
        )

    async def cancel_shipment(self, tracking_number: str) -> bool:
        return True
