"""
TMS 应用服务层

编排仓储接口与领域服务，实现物流商、发货单、配送方式、
运费模板、物流追踪等核心业务流程。
每个服务通过构造函数注入所需的仓储接口。
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy import select

from erp.modules.tms.domain.models import FreightTemplate, LogisticsProvider, ShippingBatch, ShippingMethod, Shipment
from erp.modules.tms.domain.repositories import (
    FreightTemplateRepository,
    LogisticsProviderRepository,
    ShipmentRepository,
    ShippingBatchRepository,
    ShippingMethodRepository,
)
from erp.modules.tms.domain.services import FreightEstimationDomainService, ShippingMethodDomainService, TrackingDomainService
from erp.shared.exceptions import DuplicateCodeException, NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.tms")

SHIPMENT_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["picked_up", "cancelled"],
    "picked_up": ["in_transit", "cancelled"],
    "in_transit": ["out_for_delivery", "exception"],
    "out_for_delivery": ["delivered", "exception"],
    "delivered": ["completed"],
    "exception": ["in_transit", "returned", "cancelled"],
    "returned": [],
    "completed": [],
    "cancelled": [],
}

SHIPPING_COST_LIMITS = {
    "max_cost_per_shipment": 100000.0,
    "max_weight_kg": 1000.0,
}


class LogisticsProviderService:
    """
    物流商应用服务

    编排物流商的完整生命周期: 创建 → 查询 → 更新状态 → 软删除
    通过 LogisticsProviderRepository 操作数据。
    """

    def __init__(self, session: AsyncSession, provider_repo: LogisticsProviderRepository):
        self._session = session
        self._provider_repo = provider_repo

    async def create(self, tenant_id: str, name: str, code: str, **kwargs) -> LogisticsProvider:
        """创建物流商: 唯一性校验(code) → 持久化"""
        existing = await self._provider_repo.get_by_code(code, tenant_id)
        if existing:
            raise DuplicateCodeException(message=f"Provider code '{code}' already exists")
        provider = LogisticsProvider(tenant_id=tenant_id, name=name, code=code, **kwargs)
        return await self._provider_repo.create(provider)

    async def get_by_id(self, provider_id: str, tenant_id: str) -> LogisticsProvider | None:
        """根据ID获取物流商"""
        return await self._provider_repo.get_by_id(provider_id, tenant_id)

    async def get_or_raise(self, provider_id: str, tenant_id: str) -> LogisticsProvider:
        """根据ID获取物流商，不存在则抛出 NotFoundException"""
        provider = await self.get_by_id(provider_id, tenant_id)
        if not provider:
            raise NotFoundException(message=f"Provider '{provider_id}' not found")
        return provider

    async def list_all(self, tenant_id: str, page: int = 1, page_size: int = 20) -> tuple[Sequence[LogisticsProvider], int]:
        """分页查询物流商列表"""
        return await self._provider_repo.list_by_tenant(tenant_id, page=page, page_size=page_size)

    async def update_status(self, provider_id: str, tenant_id: str, status: str) -> LogisticsProvider:
        """更新物流商状态"""
        provider = await self._provider_repo.get_by_id(provider_id, tenant_id)
        if not provider:
            raise NotFoundException(message=f"Provider '{provider_id}' not found")
        provider.status = status
        return await self._provider_repo.update(provider)

    async def update(self, provider_id: str, tenant_id: str, **kwargs) -> LogisticsProvider:
        """更新物流商信息"""
        provider = await self._provider_repo.get_by_id(provider_id, tenant_id)
        if not provider:
            raise NotFoundException(message=f"Provider '{provider_id}' not found")
        for field in ("name", "code", "provider_type", "api_endpoint", "api_key_encrypted", "supported_regions"):
            if field in kwargs and kwargs[field] is not None:
                setattr(provider, field, kwargs[field])
        return await self._provider_repo.update(provider)

    async def soft_delete(self, provider_id: str, tenant_id: str) -> LogisticsProvider:
        """软删除物流商"""
        provider = await self._provider_repo.get_by_id(provider_id, tenant_id)
        if not provider:
            raise NotFoundException(message=f"Provider '{provider_id}' not found")
        provider.status = "disabled"
        await self._provider_repo.soft_delete(provider_id, tenant_id)
        return provider


class ShipmentService:
    """
    发货单应用服务

    编排发货单的完整生命周期: 创建 → 更新追踪 → 状态流转 → 列表查询
    通过 ShipmentRepository 操作数据。
    """

    def __init__(self, session: AsyncSession, shipment_repo: ShipmentRepository | None = None):
        self._session = session
        self._shipment_repo = shipment_repo

    async def create(self, tenant_id: str, shipment_no: str, order_id: str,
                     warehouse_id: str, provider_id: str, shipping_method_id: str, **kwargs) -> Shipment:
        """创建发货单: 运费/重量校验 → 持久化"""
        shipping_cost = kwargs.get("shipping_cost", 0.0)
        if shipping_cost < 0:
            raise ValidationException(message="Shipping cost cannot be negative")
        if shipping_cost > SHIPPING_COST_LIMITS["max_cost_per_shipment"]:
            raise ValidationException(
                message=f"Shipping cost {shipping_cost} exceeds maximum {SHIPPING_COST_LIMITS['max_cost_per_shipment']}"
            )
        weight = kwargs.get("weight", 0.0)
        if weight < 0:
            raise ValidationException(message="Weight cannot be negative")
        if weight > SHIPPING_COST_LIMITS["max_weight_kg"]:
            raise ValidationException(
                message=f"Weight {weight}kg exceeds maximum {SHIPPING_COST_LIMITS['max_weight_kg']}kg"
            )
        shipment = Shipment(
            tenant_id=tenant_id, shipment_no=shipment_no, order_id=order_id,
            warehouse_id=warehouse_id, provider_id=provider_id,
            shipping_method_id=shipping_method_id, **kwargs,
        )
        if self._shipment_repo:
            return await self._shipment_repo.create(shipment)
        self._session.add(shipment)
        await self._session.flush()
        return shipment

    async def get_by_id(self, shipment_id: str, tenant_id: str) -> Shipment | None:
        """根据ID获取发货单"""
        if self._shipment_repo:
            return await self._shipment_repo.get_by_id(shipment_id, tenant_id)
        stmt = select(Shipment).where(Shipment.id == shipment_id, Shipment.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, shipment_id: str, tenant_id: str) -> Shipment:
        """根据ID获取发货单，不存在则抛出 NotFoundException"""
        shipment = await self.get_by_id(shipment_id, tenant_id)
        if not shipment:
            raise NotFoundException(message=f"Shipment '{shipment_id}' not found")
        return shipment

    async def update_tracking(self, shipment_id: str, tenant_id: str, tracking_no: str, events: list | None = None) -> Shipment:
        """更新发货单追踪信息"""
        shipment = await self._shipment_repo.get_by_id(shipment_id, tenant_id)
        if not shipment:
            raise NotFoundException(message=f"Shipment '{shipment_id}' not found")
        shipment.tracking_no = tracking_no
        if events:
            shipment.tracking_events_json = json.dumps(events, default=str)
        return await self._shipment_repo.update(shipment)

    async def update_status(self, shipment_id: str, tenant_id: str, new_status: str) -> Shipment:
        """更新发货单状态: 状态机校验 → 状态变更"""
        shipment = await self.get_by_id(shipment_id, tenant_id)
        if not shipment:
            raise NotFoundException(message=f"Shipment '{shipment_id}' not found")
        allowed = SHIPMENT_STATUS_TRANSITIONS.get(shipment.status, [])
        if new_status not in allowed:
            raise ValidationException(message=f"Cannot transition shipment from '{shipment.status}' to '{new_status}'")
        shipment.status = new_status
        if new_status == "delivered":
            shipment.delivered_at = datetime.now(UTC)
        if self._shipment_repo:
            return await self._shipment_repo.update(shipment)
        await self._session.flush()
        return shipment

    async def list_all(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[Shipment], int]:
        """分页查询发货单列表"""
        return await self._shipment_repo.list_by_tenant(tenant_id, status=status, page=page, page_size=page_size)

    async def search(self, tenant_id: str, order_id: str = "", status: str = "",
                     provider_id: str = "", tracking_no: str = "",
                     recipient_country: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[Shipment], int]:
        """多条件搜索发货单"""
        conditions = [Shipment.tenant_id == tenant_id]
        if order_id:
            conditions.append(Shipment.order_id == order_id)
        if status:
            conditions.append(Shipment.status == status)
        if provider_id:
            conditions.append(Shipment.provider_id == provider_id)
        if tracking_no:
            conditions.append(Shipment.tracking_no == tracking_no)
        if recipient_country:
            conditions.append(Shipment.recipient_country == recipient_country)

        count_stmt = select(sa_func.count()).select_from(Shipment).where(*conditions)
        total = (await self._session.execute(count_stmt)).scalar() or 0

        stmt = select(Shipment).where(*conditions).order_by(
            Shipment.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = (await self._session.execute(stmt)).scalars().all()
        return items, total

    async def batch_update_status(self, tenant_id: str, shipment_ids: list[str], new_status: str) -> list[dict]:
        """批量更新发货单状态"""
        results = []
        for sid in shipment_ids:
            try:
                shipment = await self.update_status(sid, tenant_id, new_status)
                results.append({"shipment_id": sid, "status": shipment.status, "success": True})
            except Exception as e:
                results.append({"shipment_id": sid, "error": str(e), "success": False})
        return results

    async def get_by_order_id(self, tenant_id: str, order_id: str) -> list[Shipment]:
        """根据订单ID查询发货单列表"""
        stmt = select(Shipment).where(
            Shipment.tenant_id == tenant_id,
            Shipment.order_id == order_id,
        ).order_by(Shipment.created_at.desc())
        return list((await self._session.execute(stmt)).scalars().all())


class ShippingMethodService:
    """
    配送方式应用服务

    编排配送方式的完整生命周期: 创建 → 查询 → 运费计算 → 方式对比
    通过 ShippingMethodRepository 操作数据。
    """

    def __init__(self, session: AsyncSession, method_repo: ShippingMethodRepository):
        self._session = session
        self._method_repo = method_repo

    async def create(self, tenant_id: str, provider_id: str, name: str, code: str,
                     shipping_type: str = "standard", first_weight: float = 0.1,
                     first_weight_price: float = 0.0, additional_weight: float = 0.1,
                     additional_weight_price: float = 0.0, **kwargs) -> ShippingMethod:
        """创建配送方式: 领域校验 → 唯一性校验(code) → 持久化"""
        errors = ShippingMethodDomainService.validate_shipping_method(
            name, shipping_type, first_weight, first_weight_price, additional_weight, additional_weight_price
        )
        if errors:
            raise ValidationException(message="; ".join(errors))
        existing = await self._method_repo.get_by_code(code, tenant_id)
        if existing:
            raise DuplicateCodeException(message=f"Shipping method code '{code}' already exists")
        method = ShippingMethod(
            tenant_id=tenant_id, provider_id=provider_id, name=name, code=code,
            shipping_type=shipping_type, first_weight=first_weight,
            first_weight_price=first_weight_price, additional_weight=additional_weight,
            additional_weight_price=additional_weight_price,
            **{k: v for k, v in kwargs.items() if hasattr(ShippingMethod, k)},
        )
        return await self._method_repo.create(method)

    async def get_by_id(self, method_id: str, tenant_id: str) -> ShippingMethod | None:
        """根据ID获取配送方式"""
        return await self._method_repo.get_by_id(method_id, tenant_id)

    async def get_or_raise(self, method_id: str, tenant_id: str) -> ShippingMethod:
        """根据ID获取配送方式，不存在则抛出 NotFoundException"""
        method = await self.get_by_id(method_id, tenant_id)
        if not method:
            raise NotFoundException(message=f"Shipping method '{method_id}' not found")
        return method

    async def list_all(self, tenant_id: str, provider_id: str = "", shipping_type: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[ShippingMethod], int]:
        """分页查询配送方式列表"""
        return await self._method_repo.list_by_tenant(
            tenant_id, status="active" if not shipping_type else "", page=page, page_size=page_size
        )

    async def calculate_freight(self, method_id: str, tenant_id: str,
                                 weight: float, **kwargs) -> dict:
        """计算运费: 获取配送方式 → 调用领域服务估算"""
        method = await self._method_repo.get_by_id(method_id, tenant_id)
        if not method:
            raise NotFoundException(message=f"Shipping method '{method_id}' not found")
        method_data = {
            "id": str(method.id), "name": method.name,
            "calculation_type": "by_weight",
            "first_weight": method.first_weight, "first_weight_price": method.first_weight_price,
            "additional_weight": method.additional_weight, "additional_weight_price": method.additional_weight_price,
            "min_price": method.min_price, "currency": method.currency,
            "estimated_days_min": method.estimated_days_min, "estimated_days_max": method.estimated_days_max,
        }


class SmartChannelSelectionService:
    """
    智能选渠道服务

    根据订单特征自动推荐最优物流渠道:
    目的地/重量/时效要求/成本/可靠性 → 多维度评分 → 推荐Top3
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def recommend_channels(self, tenant_id: str, destination_country: str,
                                  weight_kg: float, declared_value: float = 0.0,
                                  urgency: str = "normal",
                                  required_delivery_days: int | None = None) -> dict:
        """
        推荐物流渠道

        流程: 查询可用渠道 → 多维评分 → 排序 → 返回Top3
        """
        methods = (await self._session.execute(
            select(ShippingMethod).where(
                ShippingMethod.tenant_id == tenant_id, ShippingMethod.status == "active")
        )).scalars().all()
        if not methods:
            return {"recommendations": [], "message": "No active shipping methods found"}
        scored = []
        for method in methods:
            score = await self._score_method(method, destination_country, weight_kg,
                                              declared_value, urgency, required_delivery_days)
            if score["eligible"]:
                scored.append(score)
        scored.sort(key=lambda x: x["total_score"], reverse=True)
        top3 = scored[:3]
        return {
            "destination_country": destination_country, "weight_kg": weight_kg,
            "urgency": urgency, "recommendation_count": len(top3),
            "recommendations": top3,
        }

    async def _score_method(self, method: ShippingMethod, destination: str,
                             weight: float, value: float, urgency: str,
                             required_days: int | None) -> dict:
        cost_score = 0.5
        speed_score = 0.5
        reliability_score = 0.5
        coverage_score = 0.0
        if hasattr(method, "supported_countries") and method.supported_countries:
            if destination in (method.supported_countries or ""):
                coverage_score = 1.0
        else:
            coverage_score = 0.5
        estimated_cost = (method.base_price or 0) + weight * (method.per_kg_price or 0)
        if urgency == "urgent":
            speed_score = 1.0 if (method.estimated_days or 30) <= 5 else 0.3
        elif urgency == "normal":
            speed_score = 0.7
        else:
            speed_score = 0.5
        if required_days and (method.estimated_days or 30) > required_days:
            return {"method_id": str(method.id), "method_name": method.method_name,
                    "eligible": False, "reason": f"Exceeds required {required_days} days"}
        total_score = (cost_score * 0.35 + speed_score * 0.30 +
                       reliability_score * 0.20 + coverage_score * 0.15)
        return {
            "method_id": str(method.id), "method_name": method.method_name,
            "eligible": True, "estimated_cost": round(estimated_cost, 2),
            "estimated_days": method.estimated_days,
            "cost_score": round(cost_score, 3), "speed_score": round(speed_score, 3),
            "reliability_score": round(reliability_score, 3),
            "coverage_score": round(coverage_score, 3),
            "total_score": round(total_score, 3),
        }


class FreightComparisonService:
    """
    运费比价服务

    多物流商运费实时比价: 批量查询 → 综合比较 → 最优推荐
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def compare_freight(self, tenant_id: str, shipments: list[dict]) -> dict:
        """
        批量运费比价

        流程: 遍历货件 → 查询各渠道报价 → 综合比较 → 推荐最优
        """
        comparisons = []
        for shipment in shipments:
            result = await self._compare_single(tenant_id, shipment)
            comparisons.append(result)
        total_savings = sum(c.get("potential_savings", 0) for c in comparisons)
        return {
            "total_shipments": len(shipments),
            "total_potential_savings": round(total_savings, 2),
            "comparisons": comparisons,
        }

    async def _compare_single(self, tenant_id: str, shipment: dict) -> dict:
        methods = (await self._session.execute(
            select(ShippingMethod).where(
                ShippingMethod.tenant_id == tenant_id, ShippingMethod.status == "active")
        )).scalars().all()
        quotes = []
        for method in methods:
            weight = shipment.get("weight_kg", 1.0)
            cost = (method.base_price or 0) + weight * (method.per_kg_price or 0)
            quotes.append({
                "method_id": str(method.id), "method_name": method.method_name,
                "carrier_id": method.carrier_id, "estimated_cost": round(cost, 2),
                "estimated_days": method.estimated_days,
            })
        quotes.sort(key=lambda x: x["estimated_cost"])
        best = quotes[0] if quotes else None
        current_cost = shipment.get("current_cost", 0)
        potential_savings = current_cost - best["estimated_cost"] if best and current_cost > 0 else 0
        return {
            "shipment_no": shipment.get("shipment_no", ""),
            "current_cost": current_cost,
            "best_quote": best, "potential_savings": round(potential_savings, 2),
            "all_quotes": quotes,
        }


class LogisticsTrackingAggregator:
    """
    物流追踪聚合服务

    聚合多物流商追踪信息: 统一查询 → 状态映射 → 事件时间线
    """

    STATUS_MAPPING = {
        "pending": "pending", "info_received": "pending",
        "picked_up": "picked_up", "collected": "picked_up",
        "in_transit": "in_transit", "transit": "in_transit", "departed": "in_transit",
        "arrived_at_hub": "in_transit", "customs_clearance": "in_transit",
        "out_for_delivery": "out_for_delivery", "dispatched": "out_for_delivery",
        "delivered": "delivered", "signed": "delivered", "completed": "delivered",
        "returned": "returned", "exception": "exception", "failed_delivery": "exception",
    }

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_unified_tracking(self, tenant_id: str, tracking_no: str) -> dict:
        """
        获取统一追踪信息

        流程: 查询物流单 → 映射状态 → 构建时间线
        """
        shipment = (await self._session.execute(
            select(Shipment).where(
                Shipment.tenant_id == tenant_id, Shipment.tracking_no == tracking_no)
        )).scalar_one_or_none()
        if not shipment:
            return {"tracking_no": tracking_no, "found": False}
        unified_status = self.STATUS_MAPPING.get(shipment.status, shipment.status)
        timeline = await self._build_timeline(shipment)
        return {
            "tracking_no": tracking_no, "found": True,
            "shipment_no": shipment.shipment_no,
            "carrier_id": shipment.carrier_id,
            "unified_status": unified_status,
            "original_status": shipment.status,
            "timeline": timeline,
        }

    async def batch_track(self, tenant_id: str, tracking_nos: list[str]) -> list[dict]:
        """批量追踪"""
        results = []
        for tn in tracking_nos:
            result = await self.get_unified_tracking(tenant_id, tn)
            results.append(result)
        return results

    async def _build_timeline(self, shipment: Shipment) -> list[dict]:
        timeline = []
        if shipment.created_at:
            timeline.append({"event": "order_created", "time": shipment.created_at.isoformat(), "location": ""})
        if shipment.shipped_at:
            timeline.append({"event": "shipped", "time": shipment.shipped_at.isoformat(), "location": ""})
        if shipment.delivered_at:
            timeline.append({"event": "delivered", "time": shipment.delivered_at.isoformat(), "location": ""})
        return timeline
        volume = kwargs.get("volume", 0.0)
        quantity = kwargs.get("quantity", 1)
        return FreightEstimationDomainService.estimate_freight(weight, volume, quantity, method_data)

    async def compare_methods(self, tenant_id: str, weight: float,
                               volume: float = 0.0, quantity: int = 1,
                               provider_id: str = "", destination_country: str = "") -> list[dict]:
        """对比多种配送方式的运费"""
        conditions = [ShippingMethod.tenant_id == tenant_id, ShippingMethod.status == "active"]
        if provider_id:
            conditions.append(ShippingMethod.provider_id == provider_id)
        methods = (await self._session.execute(select(ShippingMethod).where(*conditions))).scalars().all()
        method_data_list = [
            {
                "id": str(m.id), "name": m.name, "calculation_type": "by_weight",
                "first_weight": m.first_weight, "first_weight_price": m.first_weight_price,
                "additional_weight": m.additional_weight, "additional_weight_price": m.additional_weight_price,
                "min_price": m.min_price, "currency": m.currency,
                "estimated_days_min": m.estimated_days_min, "estimated_days_max": m.estimated_days_max,
            }
            for m in methods
        ]
        return FreightEstimationDomainService.compare_shipping_methods(
            weight, volume, quantity, method_data_list, destination_country,
        )

    async def update(self, method_id: str, tenant_id: str, **kwargs) -> ShippingMethod:
        """更新配送方式"""
        method = await self._method_repo.get_by_id(method_id, tenant_id)
        if not method:
            raise NotFoundException(message=f"Shipping method '{method_id}' not found")
        for field in ("name", "shipping_type", "estimated_days_min", "estimated_days_max",
                       "first_weight", "first_weight_price", "additional_weight",
                       "additional_weight_price", "min_price", "currency", "status"):
            if field in kwargs and kwargs[field] is not None:
                setattr(method, field, kwargs[field])
        return await self._method_repo.update(method)

    async def soft_delete(self, method_id: str, tenant_id: str) -> ShippingMethod:
        """软删除配送方式"""
        method = await self._method_repo.get_by_id(method_id, tenant_id)
        if not method:
            raise NotFoundException(message=f"Shipping method '{method_id}' not found")
        method.status = "disabled"
        return await self._method_repo.update(method)


class FreightTemplateService:
    """
    运费模板应用服务

    编排运费模板的完整生命周期: 创建 → 列表查询
    通过 FreightTemplateRepository 操作数据。
    """

    def __init__(self, session: AsyncSession, template_repo: FreightTemplateRepository):
        self._session = session
        self._template_repo = template_repo

    async def create(self, tenant_id: str, name: str, calculation_type: str = "by_weight",
                     rules: list | None = None, **kwargs) -> FreightTemplate:
        """创建运费模板: 计算类型校验 → 持久化"""
        if calculation_type not in ("by_weight", "by_volume", "by_item", "by_fixed"):
            raise ValidationException(message=f"Invalid calculation type '{calculation_type}'")
        template = FreightTemplate(
            tenant_id=tenant_id, name=name, calculation_type=calculation_type,
            rules_json=json.dumps(rules or [], default=str),
            **{k: v for k, v in kwargs.items() if hasattr(FreightTemplate, k)},
        )
        return await self._template_repo.create(template)

    async def list_all(self, tenant_id: str, page: int = 1, page_size: int = 20) -> tuple[Sequence[FreightTemplate], int]:
        """分页查询运费模板列表"""
        return await self._template_repo.list_by_tenant(tenant_id, status="active", page=page, page_size=page_size)

    async def get_by_id(self, template_id: str, tenant_id: str) -> FreightTemplate | None:
        """根据ID获取运费模板"""
        return await self._template_repo.get_by_id(template_id, tenant_id)

    async def get_or_raise(self, template_id: str, tenant_id: str) -> FreightTemplate:
        """根据ID获取运费模板，不存在则抛出 NotFoundException"""
        template = await self.get_by_id(template_id, tenant_id)
        if not template:
            raise NotFoundException(message=f"Freight template '{template_id}' not found")
        return template

    async def update(self, template_id: str, tenant_id: str, **kwargs) -> FreightTemplate:
        """更新运费模板"""
        template = await self._template_repo.get_by_id(template_id, tenant_id)
        if not template:
            raise NotFoundException(message=f"Freight template '{template_id}' not found")
        if "name" in kwargs and kwargs["name"] is not None:
            template.name = kwargs["name"]
        if "calculation_type" in kwargs and kwargs["calculation_type"] is not None:
            ct = kwargs["calculation_type"]
            if ct not in ("by_weight", "by_volume", "by_item", "by_fixed"):
                raise ValidationException(message=f"Invalid calculation type '{ct}'")
            template.calculation_type = ct
        if "rules" in kwargs and kwargs["rules"] is not None:
            template.rules_json = json.dumps(kwargs["rules"], default=str)
        if "status" in kwargs and kwargs["status"] is not None:
            template.status = kwargs["status"]
        return await self._template_repo.update(template)

    async def soft_delete(self, template_id: str, tenant_id: str) -> FreightTemplate:
        """软删除运费模板"""
        template = await self._template_repo.get_by_id(template_id, tenant_id)
        if not template:
            raise NotFoundException(message=f"Freight template '{template_id}' not found")
        template.status = "disabled"
        return await self._template_repo.update(template)


class TrackingService:
    """
    物流追踪应用服务

    编排物流追踪的完整流程: 查询追踪 → 添加事件 → 批量追踪 → 异常查询
    通过 ShipmentRepository 操作数据。
    """

    def __init__(self, session: AsyncSession, shipment_repo: ShipmentRepository):
        self._session = session
        self._shipment_repo = shipment_repo

    async def get_tracking_info(self, shipment_id: str, tenant_id: str) -> dict:
        """获取发货单的追踪信息: 解析事件 → 获取最新状态 → 检测异常"""
        shipment = await self._shipment_repo.get_by_id(shipment_id, tenant_id)
        if not shipment:
            raise NotFoundException(message=f"Shipment '{shipment_id}' not found")
        events = json.loads(shipment.tracking_events_json or "[]")
        parsed = TrackingDomainService.parse_tracking_events(events)
        latest = TrackingDomainService.get_latest_status(events)
        exception = TrackingDomainService.detect_exception(events)
        return {
            "shipment_id": str(shipment.id), "shipment_no": shipment.shipment_no,
            "tracking_no": shipment.tracking_no, "status": shipment.status,
            "latest_event": latest, "all_events": parsed,
            "exception": exception,
            "is_delivered": TrackingDomainService.is_delivered(events),
        }

    async def add_tracking_event(self, shipment_id: str, tenant_id: str,
                                  event: dict) -> Shipment:
        """添加追踪事件: 解析已有事件 → 追加新事件 → 状态映射 → 持久化"""
        shipment = await self._shipment_repo.get_by_id(shipment_id, tenant_id)
        if not shipment:
            raise NotFoundException(message=f"Shipment '{shipment_id}' not found")
        events = json.loads(shipment.tracking_events_json or "[]")
        events.append(event)
        shipment.tracking_events_json = json.dumps(events, default=str)
        event_status = event.get("status", "").lower()
        status_mapping = {
            "picked_up": "picked_up", "in_transit": "in_transit",
            "out_for_delivery": "out_for_delivery", "delivered": "delivered",
            "signed": "delivered", "exception": "exception",
            "customs_hold": "exception", "returned": "returned",
        }
        if event_status in status_mapping:
            new_status = status_mapping[event_status]
            allowed = SHIPMENT_STATUS_TRANSITIONS.get(shipment.status, [])
            if new_status in allowed:
                shipment.status = new_status
                if new_status == "delivered":
                    shipment.delivered_at = datetime.now(UTC)
        return await self._shipment_repo.update(shipment)

    async def batch_track(self, tenant_id: str, shipment_ids: list[str]) -> list[dict]:
        """批量查询追踪信息"""
        results = []
        for sid in shipment_ids:
            try:
                info = await self.get_tracking_info(sid, tenant_id)
                results.append(info)
            except NotFoundException:
                results.append({"shipment_id": sid, "error": "not found"})
        return results

    async def get_exceptions(self, tenant_id: str, page: int = 1, page_size: int = 20) -> list[dict]:
        """查询异常发货单"""
        shipments, _ = await self._shipment_repo.list_by_status(
            tenant_id, status="exception", page=page, page_size=page_size
        )
        exceptions = []
        for s in shipments:
            events = json.loads(s.tracking_events_json or "[]")
            exc = TrackingDomainService.detect_exception(events)
            exceptions.append({
                "shipment_id": str(s.id), "shipment_no": s.shipment_no,
                "tracking_no": s.tracking_no, "exception": exc,
            })
        return exceptions

    async def get_by_tracking_no(self, tracking_no: str, tenant_id: str) -> tuple | None:
        """根据追踪号查询发货单及其追踪信息"""
        stmt = select(Shipment).where(
            Shipment.tracking_no == tracking_no,
            Shipment.tenant_id == tenant_id,
        )
        shipment = (await self._session.execute(stmt)).scalar_one_or_none()
        if not shipment:
            return None
        tracking_info = await self.get_tracking_info(str(shipment.id), tenant_id)
        return (shipment, tracking_info)


BATCH_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "created": ["picking", "cancelled"],
    "picking": ["shipped", "cancelled"],
    "shipped": ["completed"],
    "completed": [],
    "cancelled": [],
}


class BatchService:
    """
    发货批次应用服务

    编排发货批次的完整生命周期: 创建 → 拣货 → 发货 → 完成/取消
    通过 ShippingBatchRepository + ShipmentRepository 操作数据。
    """

    def __init__(self, session: AsyncSession, batch_repo: ShippingBatchRepository,
                 shipment_repo: ShipmentRepository):
        self._session = session
        self._batch_repo = batch_repo
        self._shipment_repo = shipment_repo

    async def create(self, tenant_id: str, carrier_id: str, shipment_ids: list[str],
                     remark: str = "") -> ShippingBatch:
        """创建发货批次: 校验发货单 → 汇总重量/运费 → 持久化"""
        total_weight = 0.0
        total_cost = 0.0
        currency = "CNY"
        for sid in shipment_ids:
            shipment = await self._shipment_repo.get_by_id(sid, tenant_id)
            if shipment:
                total_weight += shipment.weight or 0.0
                total_cost += shipment.shipping_cost or 0.0
                if shipment.currency:
                    currency = shipment.currency
        now_str = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        batch_no = f"BATCH-{now_str}"
        batch = ShippingBatch(
            tenant_id=tenant_id, batch_no=batch_no,
            carrier_id=carrier_id, shipment_count=len(shipment_ids),
            total_weight=round(total_weight, 2), total_cost=round(total_cost, 2),
            currency=currency, status="created",
            shipment_ids_json=json.dumps(shipment_ids, default=str),
            remark=remark,
        )
        return await self._batch_repo.create(batch)

    async def get_by_id(self, batch_id: str, tenant_id: str) -> ShippingBatch | None:
        """根据ID获取发货批次"""
        return await self._batch_repo.get_by_id(batch_id, tenant_id)

    async def get_or_raise(self, batch_id: str, tenant_id: str) -> ShippingBatch:
        """根据ID获取发货批次，不存在则抛出 NotFoundException"""
        batch = await self.get_by_id(batch_id, tenant_id)
        if not batch:
            raise NotFoundException(message=f"Shipping batch '{batch_id}' not found")
        return batch

    async def list_all(self, tenant_id: str, status: str = "", carrier_id: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[ShippingBatch], int]:
        """分页查询发货批次列表"""
        return await self._batch_repo.list_by_tenant(
            tenant_id, status=status, carrier_id=carrier_id, page=page, page_size=page_size
        )

    async def update_status(self, batch_id: str, tenant_id: str, new_status: str) -> ShippingBatch:
        """更新批次状态: 状态机校验 → 状态变更"""
        batch = await self._batch_repo.get_by_id(batch_id, tenant_id)
        if not batch:
            raise NotFoundException(message=f"Batch '{batch_id}' not found")
        allowed = BATCH_STATUS_TRANSITIONS.get(batch.status, [])
        if new_status not in allowed:
            raise ValidationException(message=f"Cannot transition batch from '{batch.status}' to '{new_status}'")
        batch.status = new_status
        if new_status == "shipped":
            batch.shipped_at = datetime.now(UTC)
        elif new_status == "completed":
            batch.completed_at = datetime.now(UTC)
        return await self._batch_repo.update(batch)


class CarrierPerformanceService:
    """
    物流商绩效应用服务

    通过聚合发货单数据计算物流商的送达率、平均时效、平均运费等绩效指标。
    """

    def __init__(self, session: AsyncSession, shipment_repo: ShipmentRepository,
                 provider_repo: LogisticsProviderRepository):
        self._session = session
        self._shipment_repo = shipment_repo
        self._provider_repo = provider_repo

    async def get_performance(self, tenant_id: str, carrier_id: str = "") -> list[dict]:
        """查询物流商绩效统计: 按物流商聚合发货单数据"""
        providers, _ = await self._provider_repo.list_by_tenant(tenant_id, page=1, page_size=100)
        if carrier_id:
            providers = [p for p in providers if str(p.id) == carrier_id]
        results = []
        for provider in providers:
            pid = str(provider.id)
            stmt = select(Shipment).where(
                Shipment.tenant_id == tenant_id,
                Shipment.provider_id == pid,
            )
            shipments = (await self._session.execute(stmt)).scalars().all()
            total = len(shipments)
            if total == 0:
                results.append({
                    "carrier_id": pid, "carrier_name": provider.name,
                    "total_shipments": 0, "delivered": 0,
                    "delivery_rate_pct": 0.0, "avg_delivery_days": 0.0, "avg_cost": 0.0,
                })
                continue
            delivered = [s for s in shipments if s.status in ("delivered", "completed")]
            delivery_days = []
            for s in delivered:
                if s.shipped_at and s.delivered_at:
                    delta = (s.delivered_at - s.shipped_at).total_seconds() / 86400
                    delivery_days.append(delta)
            total_cost = sum(s.shipping_cost or 0.0 for s in shipments)
            results.append({
                "carrier_id": pid, "carrier_name": provider.name,
                "total_shipments": total, "delivered": len(delivered),
                "delivery_rate_pct": round(len(delivered) / total * 100, 1) if total else 0.0,
                "avg_delivery_days": round(sum(delivery_days) / len(delivery_days), 1) if delivery_days else 0.0,
                "avg_cost": round(total_cost / total, 2) if total else 0.0,
            })
        return results

    async def get_timeliness(self, tenant_id: str, carrier_id: str = "") -> list[dict]:
        """查询物流商时效统计: 按目的国聚合时效数据"""
        providers, _ = await self._provider_repo.list_by_tenant(tenant_id, page=1, page_size=100)
        if carrier_id:
            providers = [p for p in providers if str(p.id) == carrier_id]
        results = []
        for provider in providers:
            pid = str(provider.id)
            stmt = select(Shipment).where(
                Shipment.tenant_id == tenant_id,
                Shipment.provider_id == pid,
                Shipment.status.in_(["delivered", "completed"]),
            )
            shipments = (await self._session.execute(stmt)).scalars().all()
            country_groups: dict[str, list[float]] = {}
            for s in shipments:
                country = s.recipient_country or "unknown"
                if s.shipped_at and s.delivered_at:
                    delta = (s.delivered_at - s.shipped_at).total_seconds() / 86400
                    country_groups.setdefault(country, []).append(delta)
            for country, days_list in country_groups.items():
                on_time = [d for d in days_list if d <= 15]
                results.append({
                    "carrier_id": pid, "carrier_name": provider.name,
                    "avg_delivery_days": round(sum(days_list) / len(days_list), 1),
                    "on_time_rate_pct": round(len(on_time) / len(days_list) * 100, 1),
                    "region": country,
                })
        return results


class TMSQueryService:
    """
    TMS 统计查询服务

    提供运输管理模块的运营数据聚合:
    - 物流商统计: 物流商数量、按类型/状态分布
    - 发货单统计: 发货单数量、按状态分布、总运费
    - 批次统计: 批次数量、按状态分布
    - 配送方式统计: 配送方式数量
    - 策略统计: 策略数量、活跃策略数
    - 连接器统计: 连接器数量、健康状态分布
    - 时效统计: 平均送达天数
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_statistics(self, tenant_id: str) -> dict:
        """TMS 运营统计概览"""
        providers = (await self._session.execute(
            select(LogisticsProvider).where(LogisticsProvider.tenant_id == tenant_id, LogisticsProvider.deleted_at.is_(None))
        )).scalars().all()

        shipments = (await self._session.execute(
            select(Shipment).where(Shipment.tenant_id == tenant_id)
        )).scalars().all()

        batches = (await self._session.execute(
            select(ShippingBatch).where(ShippingBatch.tenant_id == tenant_id)
        )).scalars().all()

        methods = (await self._session.execute(
            select(ShippingMethod).where(ShippingMethod.tenant_id == tenant_id)
        )).scalars().all()

        from erp.modules.tms.domain.strategy_models import LogisticsStrategy
        strategies = (await self._session.execute(
            select(LogisticsStrategy).where(LogisticsStrategy.tenant_id == tenant_id)
        )).scalars().all()

        from erp.modules.tms.domain.logistics_connector_models import LogisticsConnector
        connectors = (await self._session.execute(
            select(LogisticsConnector).where(LogisticsConnector.tenant_id == tenant_id)
        )).scalars().all()

        shipment_by_status: dict[str, int] = {}
        total_cost = 0.0
        delivery_days = []
        for s in shipments:
            shipment_by_status[s.status] = shipment_by_status.get(s.status, 0) + 1
            total_cost += s.shipping_cost or 0.0
            if s.shipped_at and s.delivered_at:
                delta = (s.delivered_at - s.shipped_at).total_seconds() / 86400
                delivery_days.append(delta)

        batch_by_status: dict[str, int] = {}
        for b in batches:
            batch_by_status[b.status] = batch_by_status.get(b.status, 0) + 1

        active_batches = sum(1 for b in batches if b.status in ("created", "picking", "shipped"))

        return {
            "provider_count": len(providers),
            "active_provider_count": sum(1 for p in providers if p.status == "active"),
            "provider_by_type": {t: sum(1 for p in providers if p.provider_type == t) for t in set(p.provider_type for p in providers)},
            "shipment_count": len(shipments),
            "pending_shipment_count": shipment_by_status.get("pending", 0),
            "in_transit_count": shipment_by_status.get("in_transit", 0) + shipment_by_status.get("picked_up", 0) + shipment_by_status.get("out_for_delivery", 0),
            "delivered_count": shipment_by_status.get("delivered", 0) + shipment_by_status.get("completed", 0),
            "exception_count": shipment_by_status.get("exception", 0),
            "shipment_by_status": shipment_by_status,
            "total_shipping_cost": round(total_cost, 2),
            "avg_delivery_days": round(sum(delivery_days) / len(delivery_days), 1) if delivery_days else 0.0,
            "batch_count": len(batches),
            "active_batch_count": active_batches,
            "batch_by_status": batch_by_status,
            "method_count": len(methods),
            "active_method_count": sum(1 for m in methods if m.status == "active"),
            "strategy_count": len(strategies),
            "active_strategy_count": sum(1 for s in strategies if s.is_active),
            "connector_count": len(connectors),
            "active_connector_count": sum(1 for c in connectors if c.is_active),
        }


class FreightSettlementService:
    """
    运费核算应用服务

    编排运费核算流程: 账单生成 → 核对 → 差异处理 → 结算确认
    支持按物流商/批次维度核算。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def generate_carrier_bill(self, tenant_id: str, carrier_id: str,
                                    period_start: str, period_end: str) -> dict:
        """
        生成物流商账单

        流程: 查询周期内发货单 → 汇总运费 → 生成账单摘要
        """
        from datetime import datetime as dt
        start = dt.fromisoformat(period_start)
        end = dt.fromisoformat(period_end)
        stmt = select(Shipment).where(
            Shipment.tenant_id == tenant_id,
            Shipment.provider_id == carrier_id,
            Shipment.shipped_at >= start,
            Shipment.shipped_at <= end,
        )
        shipments = list((await self._session.execute(stmt)).scalars().all())
        total_cost = sum(s.shipping_cost for s in shipments)
        total_weight = sum(s.weight for s in shipments)
        shipment_count = len(shipments)
        bill_no = f"FREIGHT-{carrier_id[:8]}-{period_start.replace('-', '')}"
        return {
            "bill_no": bill_no, "tenant_id": tenant_id,
            "carrier_id": carrier_id,
            "period_start": period_start, "period_end": period_end,
            "shipment_count": shipment_count,
            "total_weight": round(total_weight, 2),
            "total_cost": round(total_cost, 2),
            "currency": "CNY",
            "shipments": [{"shipment_no": s.shipment_no, "tracking_no": s.tracking_no,
                           "weight": s.weight, "cost": s.shipping_cost,
                           "status": s.status} for s in shipments],
        }

    async def compare_with_quotation(self, tenant_id: str, carrier_id: str,
                                     actual_shipments: list[dict],
                                     quoted_rates: list[dict]) -> dict:
        """
        对比实际运费与报价

        流程: 按配送方式匹配报价 → 逐单计算差异 → 汇总差异报告
        """
        differences: list[dict] = []
        total_actual = 0.0
        total_quoted = 0.0
        for s in actual_shipments:
            method_id = s.get("shipping_method_id", "")
            actual_cost = s.get("shipping_cost", 0)
            weight = s.get("weight", 0)
            total_actual += actual_cost
            quoted_cost = 0.0
            for rate in quoted_rates:
                if rate.get("method_id") == method_id:
                    base_fee = rate.get("base_fee", 0)
                    per_kg = rate.get("per_kg_rate", 0)
                    quoted_cost = base_fee + weight * per_kg
                    break
            total_quoted += quoted_cost
            diff = actual_cost - quoted_cost
            if abs(diff) > 0.01:
                differences.append({
                    "shipment_no": s.get("shipment_no", ""),
                    "method_id": method_id, "weight": weight,
                    "actual_cost": actual_cost, "quoted_cost": round(quoted_cost, 2),
                    "difference": round(diff, 2),
                    "diff_pct": round(diff / quoted_cost * 100, 1) if quoted_cost > 0 else 0,
                })
        return {
            "carrier_id": carrier_id,
            "total_actual": round(total_actual, 2),
            "total_quoted": round(total_quoted, 2),
            "total_difference": round(total_actual - total_quoted, 2),
            "difference_count": len(differences),
            "differences": differences,
        }

    async def confirm_settlement(self, tenant_id: str, carrier_id: str,
                                 bill_no: str, confirmed_amount: float,
                                 remark: str = "") -> dict:
        """确认运费结算"""
        return {
            "bill_no": bill_no, "carrier_id": carrier_id,
            "confirmed_amount": confirmed_amount, "remark": remark,
            "status": "settled", "settled_at": datetime.now(UTC).isoformat(),
        }


class ShippingExceptionService:
    """
    物流异常处理应用服务

    编排物流异常的完整生命周期: 检测 → 登记 → 处理 → 关闭
    支持自动检测(超时/滞留)和手动登记。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def auto_detect_exceptions(self, tenant_id: str) -> list[dict]:
        """
        自动检测物流异常

        检测规则:
        1. 超时未签收: 超过预计时效仍未delivered
        2. 滞留异常: in_transit状态超过7天无更新
        3. 退回异常: 状态为returned
        """
        from datetime import timedelta
        now = datetime.now(UTC)
        cutoff_7d = now - timedelta(days=7)
        cutoff_14d = now - timedelta(days=14)
        exceptions: list[dict] = []
        in_transit_stmt = select(Shipment).where(
            Shipment.tenant_id == tenant_id,
            Shipment.status.in_(("in_transit", "shipped", "picked_up", "out_for_delivery")),
        )
        in_transit = list((await self._session.execute(in_transit_stmt)).scalars().all())
        for s in in_transit:
            shipped = s.shipped_at or s.created_at
            days_in_transit = (now - shipped).days if shipped else 0
            if days_in_transit > 14:
                exceptions.append({
                    "shipment_id": str(s.id), "shipment_no": s.shipment_no,
                    "tracking_no": s.tracking_no, "exception_type": "overdue",
                    "severity": "critical", "days_in_transit": days_in_transit,
                    "message": f"Shipment overdue {days_in_transit} days",
                })
            elif days_in_transit > 7:
                exceptions.append({
                    "shipment_id": str(s.id), "shipment_no": s.shipment_no,
                    "tracking_no": s.tracking_no, "exception_type": "delayed",
                    "severity": "warning", "days_in_transit": days_in_transit,
                    "message": f"Shipment delayed {days_in_transit} days",
                })
        returned_stmt = select(Shipment).where(
            Shipment.tenant_id == tenant_id, Shipment.status == "returned",
        )
        returned = list((await self._session.execute(returned_stmt)).scalars().all())
        for s in returned:
            exceptions.append({
                "shipment_id": str(s.id), "shipment_no": s.shipment_no,
                "tracking_no": s.tracking_no, "exception_type": "returned",
                "severity": "high",
                "message": f"Shipment returned: {s.shipment_no}",
            })
        return exceptions

    async def register_exception(self, tenant_id: str, shipment_id: str,
                                 exception_type: str, description: str,
                                 severity: str = "medium") -> dict:
        """手动登记物流异常"""
        if exception_type not in ("overdue", "delayed", "damaged", "lost", "returned", "wrong_address", "other"):
            raise ValidationException(message=f"Invalid exception type '{exception_type}'")
        if severity not in ("low", "medium", "high", "critical"):
            raise ValidationException(message=f"Invalid severity '{severity}'")
        shipment = (await self._session.execute(
            select(Shipment).where(Shipment.id == shipment_id, Shipment.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not shipment:
            raise NotFoundException(message=f"Shipment '{shipment_id}' not found")
        exception_no = f"EXC-TMS-{shipment_id[:8]}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        return {
            "exception_no": exception_no, "tenant_id": tenant_id,
            "shipment_id": shipment_id, "shipment_no": shipment.shipment_no,
            "tracking_no": shipment.tracking_no,
            "exception_type": exception_type, "severity": severity,
            "description": description, "status": "open",
            "created_at": datetime.now(UTC).isoformat(),
        }

    async def resolve_exception(self, tenant_id: str, exception_no: str,
                                resolution: str, action_taken: str = "") -> dict:
        """解决物流异常"""
        if not resolution.strip():
            raise ValidationException(message="Resolution cannot be empty")
        return {
            "exception_no": exception_no, "status": "resolved",
            "resolution": resolution, "action_taken": action_taken,
            "resolved_at": datetime.now(UTC).isoformat(),
        }
