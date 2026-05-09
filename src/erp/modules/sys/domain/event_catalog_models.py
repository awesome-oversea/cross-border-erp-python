from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var
from erp.shared.db.base import Base

if TYPE_CHECKING:

    from sqlalchemy.ext.asyncio import AsyncSession


class BusinessEventCatalog(Base):
    __tablename__ = "business_event_catalog"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    event_name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_action: Mapped[str] = mapped_column(String(50), nullable=False, default="created")
    event_version: Mapped[str] = mapped_column(String(10), nullable=False, default="v1")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    payload_schema_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    consumer_domains: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class EventSubscriptionRecord(Base):
    __tablename__ = "event_subscription_record"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    subscriber_domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    subscriber_name: Mapped[str] = mapped_column(String(200), nullable=False)
    callback_type: Mapped[str] = mapped_column(String(50), nullable=False, default="async",
                                                comment="sync/async/webhook")
    callback_endpoint: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BusinessEventCatalogService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def register_event(self, event_type: str, event_name: str, domain: str,
                              aggregate_type: str, aggregate_action: str = "created",
                              event_version: str = "v1", description: str = "",
                              payload_schema: dict | None = None,
                              consumer_domains: list | None = None) -> BusinessEventCatalog:
        existing = await self._get_by_event_type(event_type)
        if existing:
            return existing

        catalog = BusinessEventCatalog(
            event_type=event_type, event_name=event_name,
            domain=domain, aggregate_type=aggregate_type,
            aggregate_action=aggregate_action, event_version=event_version,
            description=description,
            payload_schema_json=json.dumps(payload_schema or {}, default=str),
            consumer_domains=json.dumps(consumer_domains or [], default=str),
            created_by=actor_id_var.get(""),
        )
        self.session.add(catalog)
        await self.session.flush()
        return catalog

    async def list_events(self, domain: str = "", is_active: bool | None = None) -> list[BusinessEventCatalog]:
        conditions = []
        if domain:
            conditions.append(BusinessEventCatalog.domain == domain)
        if is_active is not None:
            conditions.append(BusinessEventCatalog.is_active == is_active)
        stmt = select(BusinessEventCatalog).where(*conditions if conditions else True).order_by(
            BusinessEventCatalog.domain, BusinessEventCatalog.aggregate_type
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def subscribe_event(self, tenant_id: str, event_type: str, subscriber_domain: str,
                               subscriber_name: str, callback_type: str = "async",
                               callback_endpoint: str = "") -> EventSubscriptionRecord:
        sub = EventSubscriptionRecord(
            tenant_id=tenant_id, event_type=event_type,
            subscriber_domain=subscriber_domain, subscriber_name=subscriber_name,
            callback_type=callback_type, callback_endpoint=callback_endpoint,
            created_by=actor_id_var.get(""),
        )
        self.session.add(sub)
        await self.session.flush()
        return sub

    async def list_subscriptions(self, tenant_id: str, event_type: str = "",
                                  subscriber_domain: str = "") -> list[EventSubscriptionRecord]:
        conditions = [EventSubscriptionRecord.tenant_id == tenant_id]
        if event_type:
            conditions.append(EventSubscriptionRecord.event_type == event_type)
        if subscriber_domain:
            conditions.append(EventSubscriptionRecord.subscriber_domain == subscriber_domain)
        stmt = select(EventSubscriptionRecord).where(*conditions).order_by(
            EventSubscriptionRecord.event_type
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def init_defaults(self) -> None:
        defaults = [
            ("erp.oms.order.created.v1", "订单创建", "oms", "order", "created",
             ["scm", "wms", "fms", "bi"]),
            ("erp.oms.order.confirmed.v1", "订单确认", "oms", "order", "confirmed",
             ["wms", "tms", "fms"]),
            ("erp.oms.order.shipped.v1", "订单发货", "oms", "order", "shipped",
             ["crm", "fms", "bi"]),
            ("erp.oms.order.cancelled.v1", "订单取消", "oms", "order", "cancelled",
             ["wms", "fms"]),
            ("erp.oms.refund.created.v1", "退款创建", "oms", "refund", "created",
             ["wms", "fms", "crm"]),
            ("erp.pdm.product.published.v1", "产品发布", "pdm", "product", "published",
             ["som", "bi"]),
            ("erp.pdm.sku.created.v1", "SKU创建", "pdm", "sku", "created",
             ["wms", "scm", "fms"]),
            ("erp.som.listing.published.v1", "Listing刊登", "som", "listing", "published",
             ["ads", "bi"]),
            ("erp.som.price.updated.v1", "价格更新", "som", "price", "updated",
             ["oms", "bi"]),
            ("erp.scm.purchase_order.created.v1", "采购单创建", "scm", "purchase_order", "created",
             ["wms", "fms"]),
            ("erp.scm.purchase_order.received.v1", "采购收货", "scm", "purchase_order", "received",
             ["wms", "fms"]),
            ("erp.wms.inventory.adjusted.v1", "库存调整", "wms", "inventory", "adjusted",
             ["oms", "scm", "fms", "bi"]),
            ("erp.wms.inbound.completed.v1", "入库完成", "wms", "inbound_order", "completed",
             ["scm", "fms"]),
            ("erp.wms.outbound.completed.v1", "出库完成", "wms", "outbound_order", "completed",
             ["oms", "tms", "fms"]),
            ("erp.tms.shipment.created.v1", "发货单创建", "tms", "shipment", "created",
             ["oms", "fms"]),
            ("erp.tms.shipment.delivered.v1", "物流签收", "tms", "shipment", "delivered",
             ["oms", "crm", "bi"]),
            ("erp.fms.cost_event.created.v1", "成本事件创建", "fms", "cost_event", "created",
             ["bi"]),
            ("erp.fms.settlement.confirmed.v1", "结算确认", "fms", "settlement", "confirmed",
             ["bi"]),
            ("erp.ads.campaign.created.v1", "广告活动创建", "ads", "campaign", "created",
             ["bi"]),
            ("erp.crm.communication.created.v1", "客户沟通创建", "crm", "communication", "created",
             ["bi"]),
            ("erp.bi.metric.calculated.v1", "指标计算完成", "bi", "metric_value", "calculated",
             ["dashboard"]),
            ("erp.recommendation.submitted.v1", "AI建议提交", "pms_integration", "recommendation", "submitted",
             ["sys"]),
            ("erp.recommendation.accepted.v1", "AI建议接受", "pms_integration", "recommendation", "accepted",
             ["pms_integration"]),
            ("erp.recommendation.rejected.v1", "AI建议拒绝", "pms_integration", "recommendation", "rejected",
             ["pms_integration"]),
            ("erp.recommendation.executed.v1", "AI建议执行", "pms_integration", "recommendation", "executed",
             ["pms_integration", "bi"]),
            ("erp.recommendation.rolled_back.v1", "AI建议回滚", "pms_integration", "recommendation", "rolled_back",
             ["pms_integration"]),
        ]
        for event_type, name, domain, agg_type, action, consumers in defaults:
            await self.register_event(
                event_type=event_type, event_name=name, domain=domain,
                aggregate_type=agg_type, aggregate_action=action,
                consumer_domains=consumers,
            )

    async def _get_by_event_type(self, event_type: str) -> BusinessEventCatalog | None:
        stmt = select(BusinessEventCatalog).where(BusinessEventCatalog.event_type == event_type)
        return (await self.session.execute(stmt)).scalar_one_or_none()
