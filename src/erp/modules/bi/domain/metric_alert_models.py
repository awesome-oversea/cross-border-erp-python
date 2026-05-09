from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MetricDataType(StrEnum):
    NUMBER = "number"
    PERCENTAGE = "percentage"
    CURRENCY = "currency"
    RATIO = "ratio"
    INTEGER = "integer"


class MetricDimension(StrEnum):
    PLATFORM = "platform"
    STORE = "store"
    SKU = "sku"
    CATEGORY = "category"
    WAREHOUSE = "warehouse"
    SUPPLIER = "supplier"
    CHANNEL = "channel"
    TEAM = "team"
    PERSON = "person"
    COUNTRY = "country"


class MetricDefinition(Base):
    __tablename__ = "metric_definition"
    __table_args__ = {"schema": "bi"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    metric_name: Mapped[str] = mapped_column(String(200), nullable=False)
    metric_name_en: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sub_category: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    calculation_formula: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    calculation_sql_template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data_type: Mapped[str] = mapped_column(String(20), nullable=False, default="number")
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    supported_dimensions: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    source_tables: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    refresh_frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_kpi: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    kpi_target: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    kpi_target_direction: Mapped[str] = mapped_column(String(10), nullable=False, default="up")
    owner_domain: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BusinessAlert(Base):
    __tablename__ = "business_alert"
    __table_args__ = {"schema": "bi"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    alert_name: Mapped[str] = mapped_column(String(200), nullable=False)
    alert_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    condition_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    threshold_operator: Mapped[str] = mapped_column(String(10), nullable=False, default="lt")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    scope_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    notify_channels: Mapped[str] = mapped_column(Text, nullable=False, default='["in_app"]')
    notify_roles: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trigger_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BusinessAlertInstance(Base):
    __tablename__ = "business_alert_instance"
    __table_args__ = {"schema": "bi"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    alert_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    current_value: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    scope_info_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    suggested_action: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    acknowledged_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MetricDefinitionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_metric(self, metric_code: str, metric_name: str, category: str,
                             calculation_formula: str = "", data_type: str = "number",
                             unit: str = "", description: str = "",
                             supported_dimensions: list | None = None,
                             source_tables: list | None = None,
                             refresh_frequency: str = "daily",
                             is_kpi: bool = False, kpi_target: float = 0,
                             kpi_target_direction: str = "up",
                             owner_domain: str = "") -> MetricDefinition:
        existing = await self._get_by_code(metric_code)
        if existing:
            return existing

        metric = MetricDefinition(
            metric_code=metric_code, metric_name=metric_name,
            category=category, description=description,
            calculation_formula=calculation_formula,
            data_type=data_type, unit=unit,
            supported_dimensions=json.dumps(supported_dimensions or [], default=str),
            source_tables=json.dumps(source_tables or [], default=str),
            refresh_frequency=refresh_frequency,
            is_kpi=is_kpi, kpi_target=kpi_target,
            kpi_target_direction=kpi_target_direction,
            owner_domain=owner_domain, created_by=actor_id_var.get(""),
        )
        self.session.add(metric)
        await self.session.flush()
        return metric

    async def init_default_metrics(self) -> list[MetricDefinition]:
        defaults = [
            ("revenue_total", "总销售额", "sales", "SUM(order_amount)",
             "currency", "CNY", ["platform", "store", "sku", "category", "country"],
             ["oms.sales_order"], "daily", True, 0, "up", "oms"),
            ("revenue_net", "净销售额", "sales", "SUM(order_amount) - SUM(refund_amount)",
             "currency", "CNY", ["platform", "store", "sku"], ["oms.sales_order", "oms.refund"], "daily", True, 0, "up", "oms"),
            ("order_count", "订单数", "sales", "COUNT(DISTINCT order_id)",
             "integer", "", ["platform", "store", "sku", "country"],
             ["oms.sales_order"], "daily", True, 0, "up", "oms"),
            ("avg_order_value", "客单价", "sales", "revenue_total / order_count",
             "currency", "CNY", ["platform", "store"], ["oms.sales_order"], "daily", False, 0, "up", "oms"),
            ("refund_rate", "退款率", "sales", "refund_count / order_count * 100",
             "percentage", "%", ["platform", "store"], ["oms.refund", "oms.sales_order"], "daily", True, 5, "down", "oms"),
            ("gross_profit", "毛利润", "profit", "revenue_net - total_cost",
             "currency", "CNY", ["platform", "store", "sku", "category"],
             ["fms.profit_record"], "daily", True, 0, "up", "fms"),
            ("gross_margin", "毛利率", "profit", "gross_profit / revenue_net * 100",
             "percentage", "%", ["platform", "store", "sku"],
             ["fms.profit_record"], "daily", True, 30, "up", "fms"),
            ("net_profit", "净利润", "profit", "gross_profit - operating_expenses",
             "currency", "CNY", ["platform", "store"], ["fms.profit_record"], "monthly", False, 0, "up", "fms"),
            ("inventory_turnover", "库存周转率", "inventory", "COGS / avg_inventory_value",
             "ratio", "", ["warehouse", "sku", "category"],
             ["wms.inventory", "fms.cost_event"], "monthly", True, 6, "up", "wms"),
            ("inventory_days", "库存周转天数", "inventory", "365 / inventory_turnover",
             "integer", "天", ["warehouse", "sku", "category"],
             ["wms.inventory"], "monthly", True, 60, "down", "wms"),
            ("stockout_rate", "缺货率", "inventory", "stockout_sku_count / total_sku_count * 100",
             "percentage", "%", ["warehouse"], ["wms.inventory"], "daily", True, 2, "down", "wms"),
            ("fill_rate", "订单满足率", "inventory", "fulfilled_order_count / total_order_count * 100",
             "percentage", "%", ["warehouse"], ["wms.inventory", "oms.sales_order"], "daily", True, 98, "up", "wms"),
            ("acos", "ACoS", "ads", "ad_spend / ad_revenue * 100",
             "percentage", "%", ["campaign", "store", "sku"],
             ["ads.campaign", "ads.ad_report"], "daily", True, 25, "down", "ads"),
            ("roas", "ROAS", "ads", "ad_revenue / ad_spend",
             "ratio", "", ["campaign", "store"], ["ads.campaign", "ads.ad_report"], "daily", True, 4, "up", "ads"),
            ("ctr", "点击率", "ads", "clicks / impressions * 100",
             "percentage", "%", ["campaign", "keyword"], ["ads.ad_report"], "daily", False, 0, "up", "ads"),
            ("cr", "转化率", "ads", "orders / clicks * 100",
             "percentage", "%", ["campaign", "keyword"], ["ads.ad_report"], "daily", False, 0, "up", "ads"),
            ("cpc", "单次点击成本", "ads", "ad_spend / clicks",
             "currency", "USD", ["campaign", "keyword"], ["ads.ad_report"], "daily", False, 0, "down", "ads"),
            ("purchase_on_time_rate", "采购准时率", "scm", "on_time_po_count / total_po_count * 100",
             "percentage", "%", ["supplier"], ["scm.purchase_order"], "weekly", True, 95, "up", "scm"),
            ("supplier_defect_rate", "供应商次品率", "scm", "defective_qty / received_qty * 100",
             "percentage", "%", ["supplier"], ["scm.purchase_order", "wms.inbound_order"], "weekly", True, 1, "down", "scm"),
            ("cs_response_time_avg", "客服平均响应时间", "crm", "AVG(first_response_time)",
             "integer", "分钟", ["agent", "store"], ["crm.communication"], "daily", True, 30, "down", "crm"),
            ("cs_satisfaction_rate", "客户满意度", "crm", "satisfied_count / total_feedback_count * 100",
             "percentage", "%", ["agent", "store"], ["crm.communication"], "weekly", True, 90, "up", "crm"),
            ("logistics_on_time_rate", "物流准时率", "tms", "on_time_shipment_count / total_shipment_count * 100",
             "percentage", "%", ["carrier", "channel"], ["tms.shipment"], "weekly", True, 95, "up", "tms"),
            ("avg_delivery_days", "平均妥投天数", "tms", "AVG(delivery_days)",
             "integer", "天", ["carrier", "channel", "country"], ["tms.shipment"], "weekly", True, 7, "down", "tms"),
            ("cost_per_order", "单均成本", "fms", "total_cost / order_count",
             "currency", "CNY", ["platform", "store"], ["fms.cost_event", "oms.sales_order"], "daily", False, 0, "down", "fms"),
        ]
        metrics = []
        for d in defaults:
            m = await self.create_metric(
                metric_code=d[0], metric_name=d[1], category=d[2],
                calculation_formula=d[3], data_type=d[4], unit=d[5],
                supported_dimensions=d[6], source_tables=d[7],
                refresh_frequency=d[8], is_kpi=d[9], kpi_target=d[10],
                kpi_target_direction=d[11], owner_domain=d[12],
            )
            metrics.append(m)
        return metrics

    async def list_metrics(self, category: str = "", is_kpi: bool | None = None) -> list[MetricDefinition]:
        conditions = [MetricDefinition.is_active]
        if category:
            conditions.append(MetricDefinition.category == category)
        if is_kpi is not None:
            conditions.append(MetricDefinition.is_kpi == is_kpi)
        stmt = select(MetricDefinition).where(*conditions).order_by(MetricDefinition.category, MetricDefinition.metric_code)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_by_code(self, metric_code: str) -> MetricDefinition | None:
        stmt = select(MetricDefinition).where(MetricDefinition.metric_code == metric_code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class BusinessAlertService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_alert_rule(self, tenant_id: str, alert_name: str, alert_code: str,
                                 alert_type: str, category: str, metric_code: str,
                                 threshold_value: float, threshold_operator: str = "lt",
                                 severity: str = "warning", description: str = "",
                                 condition: dict | None = None, scope: dict | None = None,
                                 notify_channels: list | None = None,
                                 notify_roles: list | None = None,
                                 cooldown_minutes: int = 60) -> BusinessAlert:
        existing = await self._get_by_code(tenant_id, alert_code)
        if existing:
            raise ValidationException(message=f"Alert code '{alert_code}' already exists")

        alert = BusinessAlert(
            tenant_id=tenant_id, alert_name=alert_name, alert_code=alert_code,
            alert_type=alert_type, category=category, description=description,
            metric_code=metric_code, condition_json=json.dumps(condition or {}, default=str),
            threshold_value=threshold_value, threshold_operator=threshold_operator,
            severity=severity, scope_json=json.dumps(scope or {}, default=str),
            notify_channels=json.dumps(notify_channels or ["in_app"], default=str),
            notify_roles=json.dumps(notify_roles or [], default=str),
            cooldown_minutes=cooldown_minutes, created_by=actor_id_var.get(""),
        )
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def init_default_alerts(self, tenant_id: str) -> list[BusinessAlert]:
        defaults = [
            ("库存缺货预警", "stockout_warning", "stockout", "inventory",
             "stockout_rate", 5, "gte", "critical",
             {"warehouse_scope": []}, ["in_app", "sms"], ["warehouse_manager"]),
            ("低利润预警", "low_margin_warning", "low_margin", "profit",
             "gross_margin", 10, "lt", "warning",
             {"store_scope": []}, ["in_app"], ["finance_manager"]),
            ("物流异常预警", "logistics_anomaly", "logistics_anomaly", "logistics",
             "logistics_on_time_rate", 85, "lt", "warning",
             {"carrier_scope": []}, ["in_app"], ["logistics_manager"]),
            ("广告ACoS过高预警", "high_acos_warning", "high_acos", "ads",
             "acos", 35, "gt", "warning",
             {"store_scope": []}, ["in_app"], ["ads_manager"]),
            ("退款率过高预警", "high_refund_warning", "high_refund", "sales",
             "refund_rate", 8, "gt", "warning",
             {"store_scope": []}, ["in_app"], "sales_manager"),
            ("库存周转过慢预警", "slow_turnover_warning", "slow_turnover", "inventory",
             "inventory_days", 90, "gt", "warning",
             {"warehouse_scope": [], "category_scope": []}, ["in_app"], ["warehouse_manager"]),
            ("客服响应超时预警", "cs_slow_response", "cs_slow_response", "crm",
             "cs_response_time_avg", 60, "gt", "warning",
             {}, ["in_app"], ["cs_manager"]),
            ("采购延迟预警", "purchase_delay_warning", "purchase_delay", "scm",
             "purchase_on_time_rate", 80, "lt", "warning",
             {"supplier_scope": []}, ["in_app"], ["scm_manager"]),
        ]
        alerts = []
        for name, code, at, cat, mc, tv, to, sev, scope, nc, nr in defaults:
            try:
                a = await self.create_alert_rule(
                    tenant_id=tenant_id, alert_name=name, alert_code=code,
                    alert_type=at, category=cat, metric_code=mc,
                    threshold_value=tv, threshold_operator=to, severity=sev,
                    scope=scope, notify_channels=nc,
                    notify_roles=nr if isinstance(nr, list) else [nr],
                )
                alerts.append(a)
            except ValidationException:
                pass
        return alerts

    async def trigger_alert(self, tenant_id: str, alert_id: str,
                             current_value: float, title: str,
                             message: str = "", suggested_action: str = "",
                             scope_info: dict | None = None) -> BusinessAlertInstance:
        alert = await self._get_alert(alert_id, tenant_id)
        if not alert:
            raise NotFoundException(message=f"Alert rule '{alert_id}' not found")

        now = datetime.now(UTC)
        if alert.last_triggered_at:
            cooldown = timedelta(minutes=alert.cooldown_minutes)
            if now - alert.last_triggered_at < cooldown:
                raise ValidationException(message="Alert is in cooldown period")

        instance = BusinessAlertInstance(
            tenant_id=tenant_id, alert_id=alert_id,
            alert_type=alert.alert_type, severity=alert.severity,
            title=title, message=message,
            current_value=current_value, threshold_value=alert.threshold_value,
            metric_code=alert.metric_code,
            scope_info_json=json.dumps(scope_info or {}, default=str),
            suggested_action=suggested_action,
            trace_id=trace_id_var.get(""),
        )
        self.session.add(instance)

        alert.last_triggered_at = now
        alert.trigger_count += 1
        await self.session.flush()
        return instance

    async def acknowledge_alert(self, instance_id: str, tenant_id: str) -> BusinessAlertInstance:
        instance = await self._get_instance(instance_id, tenant_id)
        if not instance:
            raise NotFoundException(message=f"Alert instance '{instance_id}' not found")
        instance.status = "acknowledged"
        instance.acknowledged_by = actor_id_var.get("")
        instance.acknowledged_at = datetime.now(UTC)
        await self.session.flush()
        return instance

    async def resolve_alert(self, instance_id: str, tenant_id: str,
                             resolution_note: str = "") -> BusinessAlertInstance:
        instance = await self._get_instance(instance_id, tenant_id)
        if not instance:
            raise NotFoundException(message=f"Alert instance '{instance_id}' not found")
        instance.status = "resolved"
        instance.resolved_by = actor_id_var.get("")
        instance.resolved_at = datetime.now(UTC)
        instance.resolution_note = resolution_note
        await self.session.flush()
        return instance

    async def list_alert_rules(self, tenant_id: str, category: str = "",
                                alert_type: str = "") -> list[BusinessAlert]:
        conditions = [BusinessAlert.tenant_id == tenant_id]
        if category:
            conditions.append(BusinessAlert.category == category)
        if alert_type:
            conditions.append(BusinessAlert.alert_type == alert_type)
        stmt = select(BusinessAlert).where(*conditions).order_by(BusinessAlert.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_alert_instances(self, tenant_id: str, alert_type: str = "",
                                    status: str = "", severity: str = "",
                                    page: int = 1, page_size: int = 20) -> tuple[list[BusinessAlertInstance], int]:
        conditions = [BusinessAlertInstance.tenant_id == tenant_id]
        if alert_type:
            conditions.append(BusinessAlertInstance.alert_type == alert_type)
        if status:
            conditions.append(BusinessAlertInstance.status == status)
        if severity:
            conditions.append(BusinessAlertInstance.severity == severity)

        stmt = select(BusinessAlertInstance).where(*conditions).order_by(BusinessAlertInstance.created_at.desc())
        total_result = await self.session.execute(
            select(func.count()).select_from(BusinessAlertInstance).where(*conditions)
        )
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(stmt.offset(offset).limit(page_size))
        return list(result.scalars().all()), total

    async def _get_alert(self, alert_id: str, tenant_id: str) -> BusinessAlert | None:
        stmt = select(BusinessAlert).where(BusinessAlert.id == alert_id, BusinessAlert.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_instance(self, instance_id: str, tenant_id: str) -> BusinessAlertInstance | None:
        stmt = select(BusinessAlertInstance).where(
            BusinessAlertInstance.id == instance_id, BusinessAlertInstance.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_by_code(self, tenant_id: str, alert_code: str) -> BusinessAlert | None:
        stmt = select(BusinessAlert).where(BusinessAlert.tenant_id == tenant_id, BusinessAlert.alert_code == alert_code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
