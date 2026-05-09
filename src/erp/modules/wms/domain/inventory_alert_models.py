"""
WMS 库存快照与预警领域模型 + 服务

包含:
- InventorySnapshot: 库存快照实体
- InventoryAlertRule: 预警规则实体
- InventoryAlert: 预警记录实体
- InventorySnapshotService: 快照服务 (使用仓储接口)
- InventoryAlertService: 预警服务 (使用仓储接口)
"""
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
from erp.shared.exceptions import NotFoundException

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from erp.modules.wms.domain.repositories import (
        InventoryAlertRepository,
        InventoryAlertRuleRepository,
        InventoryRepository,
        InventorySnapshotRepository,
    )


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class AlertType(StrEnum):
    LOW_STOCK = "low_stock"
    OVERSTOCK = "overstock"
    STOCKOUT = "stockout"
    SLOW_MOVING = "slow_moving"
    DEAD_STOCK = "dead_stock"
    REPLENISHMENT_NEEDED = "replenishment_needed"
    INBOUND_DELAYED = "inbound_delayed"
    DEFECTIVE_HIGH = "defective_high"


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshot"
    __table_args__ = {"schema": "wms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    snapshot_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    qty_on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_inbound: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_outbound: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_defective: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    daily_out_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_daily_out_7d: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_daily_out_30d: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    days_of_supply: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InventoryAlertRule(Base):
    __tablename__ = "inventory_alert_rule"
    __table_args__ = {"schema": "wms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    condition_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    warehouse_scope: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    sku_scope: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    category_scope: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    cooldown_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    notify_channels: Mapped[str] = mapped_column(Text, nullable=False, default='["in_app"]')
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class InventoryAlert(Base):
    __tablename__ = "inventory_alert"
    __table_args__ = {"schema": "wms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    current_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    detail_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    resolved_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class InventorySnapshotService:
    """
    库存快照服务

    编排快照的生成与查询:
    - take_snapshot: 按日期对全量库存生成快照 (存在则更新)
    - get_snapshot: 按日期 + 仓库/SKU 查询快照
    通过 InventorySnapshotRepository 和 InventoryRepository 操作数据。
    """

    def __init__(self, session: AsyncSession, snapshot_repo: InventorySnapshotRepository,
                 inventory_repo: InventoryRepository):
        self._session = session
        self._snapshot_repo = snapshot_repo
        self._inventory_repo = inventory_repo

    async def take_snapshot(self, tenant_id: str, snapshot_date: str | None = None) -> int:
        """
        生成库存快照: 查询全量库存 → 逐条创建或更新快照

        参数:
            tenant_id: 租户ID
            snapshot_date: 快照日期 (默认当天)

        返回:
            快照记录数
        """
        if not snapshot_date:
            snapshot_date = datetime.now(UTC).strftime("%Y-%m-%d")

        inventories = await self._inventory_repo.list_by_sku("", tenant_id)
        if not inventories:
            from erp.modules.wms.domain.models import Inventory
            inv_list = await self._inventory_repo.find_low_stock(tenant_id)
            inventories = []
            from sqlalchemy import select as sa_select
            from erp.modules.wms.domain.models import Inventory as InvModel
            stmt = sa_select(InvModel).where(InvModel.tenant_id == tenant_id)
            from erp.shared.db.session import async_session_factory
            async with async_session_factory() as tmp_session:
                result = await tmp_session.execute(stmt)
                inventories = list(result.scalars().all())

        count = 0
        for inv in inventories:
            existing = await self._snapshot_repo.get_by_key(
                tenant_id, snapshot_date, inv.warehouse_id, inv.sku_id
            )
            if existing:
                existing.qty_on_hand = inv.qty_on_hand
                existing.qty_reserved = inv.qty_reserved
                existing.qty_available = inv.qty_available
                existing.qty_inbound = inv.qty_inbound
                existing.qty_outbound = inv.qty_outbound
                existing.qty_defective = inv.qty_defective
                existing.cost_price = inv.cost_price
                existing.cost_currency = inv.cost_currency
                await self._snapshot_repo.update(existing)
            else:
                snapshot = InventorySnapshot(
                    tenant_id=tenant_id, snapshot_date=snapshot_date,
                    warehouse_id=inv.warehouse_id, sku_id=inv.sku_id,
                    qty_on_hand=inv.qty_on_hand, qty_reserved=inv.qty_reserved,
                    qty_available=inv.qty_available, qty_inbound=inv.qty_inbound,
                    qty_outbound=inv.qty_outbound, qty_defective=inv.qty_defective,
                    cost_price=inv.cost_price, cost_currency=inv.cost_currency,
                )
                await self._snapshot_repo.create(snapshot)
            count += 1

        return count

    async def get_snapshot(self, tenant_id: str, snapshot_date: str,
                            warehouse_id: str = "", sku_id: str = "") -> Sequence[InventorySnapshot]:
        """查询快照: 按日期 + 可选仓库/SKU 过滤"""
        return await self._snapshot_repo.list_by_date(
            tenant_id, snapshot_date, warehouse_id=warehouse_id, sku_id=sku_id
        )


class InventoryAlertService:
    """
    库存预警服务

    编排预警的完整生命周期: 创建规则 → 评估预警 → 确认 → 解决
    通过 InventoryAlertRepository / AlertRuleRepository / InventoryRepository 操作数据。
    """

    def __init__(self, session: AsyncSession, alert_repo: InventoryAlertRepository,
                 alert_rule_repo: InventoryAlertRuleRepository,
                 inventory_repo: InventoryRepository):
        self._session = session
        self._alert_repo = alert_repo
        self._alert_rule_repo = alert_rule_repo
        self._inventory_repo = inventory_repo

    async def create_alert_rule(self, tenant_id: str, rule_name: str, alert_type: str,
                                 severity: str = "warning", condition: dict | None = None,
                                 warehouse_scope: list | None = None,
                                 sku_scope: list | None = None,
                                 category_scope: list | None = None,
                                 cooldown_hours: int = 24,
                                 notify_channels: list | None = None) -> InventoryAlertRule:
        """
        创建预警规则: 参数封装 → 持久化

        参数:
            tenant_id: 租户ID
            rule_name: 规则名称
            alert_type: 预警类型 (low_stock/overstock/stockout/...)
            severity: 严重程度 (info/warning/critical)
            condition: 触发条件
            warehouse_scope: 仓库范围 (空=全部)
            sku_scope: SKU范围 (空=全部)
            category_scope: 品类范围 (空=全部)
            cooldown_hours: 冷却时间(小时)
            notify_channels: 通知渠道
        """
        rule = InventoryAlertRule(
            tenant_id=tenant_id, rule_name=rule_name, alert_type=alert_type,
            severity=severity, condition_json=json.dumps(condition or {}, default=str),
            warehouse_scope=json.dumps(warehouse_scope or [], default=str),
            sku_scope=json.dumps(sku_scope or [], default=str),
            category_scope=json.dumps(category_scope or [], default=str),
            cooldown_hours=cooldown_hours,
            notify_channels=json.dumps(notify_channels or ["in_app"], default=str),
            created_by=actor_id_var.get(""),
        )
        return await self._alert_rule_repo.create(rule)

    async def evaluate_alerts(self, tenant_id: str) -> list[InventoryAlert]:
        """
        评估预警: 查询活跃规则 → 遍历库存 → 条件匹配 → 冷却检查 → 生成预警

        返回:
            新生成的预警列表
        """
        rules = await self._alert_rule_repo.list_active(tenant_id)

        inventories = await self._inventory_repo.find_low_stock(tenant_id)
        if not inventories:
            from erp.modules.wms.domain.models import Inventory
            from sqlalchemy import select as sa_select
            stmt = sa_select(Inventory).where(Inventory.tenant_id == tenant_id)
            from erp.shared.db.session import async_session_factory
            async with async_session_factory() as tmp_session:
                result = await tmp_session.execute(stmt)
                inventories = list(result.scalars().all())

        alerts = []
        for rule in rules:
            condition = json.loads(rule.condition_json)
            warehouse_scope = json.loads(rule.warehouse_scope)
            sku_scope = json.loads(rule.sku_scope)

            for inv in inventories:
                if warehouse_scope and inv.warehouse_id not in warehouse_scope:
                    continue
                if sku_scope and inv.sku_id not in sku_scope:
                    continue

                triggered, message = self._evaluate_condition(rule.alert_type, condition, inv)
                if triggered:
                    cutoff = datetime.now(UTC) - timedelta(hours=rule.cooldown_hours)
                    existing = await self._alert_repo.find_active_in_cooldown(
                        tenant_id, rule.id, rule.alert_type,
                        inv.warehouse_id, inv.sku_id, cutoff,
                    )
                    if existing:
                        continue

                    alert = InventoryAlert(
                        tenant_id=tenant_id, rule_id=rule.id,
                        alert_type=rule.alert_type, severity=rule.severity,
                        warehouse_id=inv.warehouse_id, sku_id=inv.sku_id,
                        current_value=self._get_current_value(rule.alert_type, inv),
                        threshold_value=self._get_threshold_value(rule.alert_type, condition),
                        message=message,
                        detail_json=json.dumps({
                            "qty_on_hand": inv.qty_on_hand,
                            "qty_available": inv.qty_available,
                            "qty_reserved": inv.qty_reserved,
                            "qty_inbound": inv.qty_inbound,
                            "qty_defective": inv.qty_defective,
                        }, default=str),
                        trace_id=trace_id_var.get(""),
                    )
                    await self._alert_repo.create(alert)
                    alerts.append(alert)

        return alerts

    async def acknowledge_alert(self, alert_id: str, tenant_id: str) -> InventoryAlert:
        """确认预警: 状态更新为 acknowledged"""
        alert = await self._alert_repo.get_by_id(alert_id, tenant_id)
        if not alert:
            raise NotFoundException(message=f"Alert '{alert_id}' not found")
        alert.status = "acknowledged"
        await self._alert_repo.update(alert)
        return alert

    async def resolve_alert(self, alert_id: str, tenant_id: str,
                             resolution_note: str = "") -> InventoryAlert:
        """解决预警: 状态更新为 resolved + 记录解决信息"""
        alert = await self._alert_repo.get_by_id(alert_id, tenant_id)
        if not alert:
            raise NotFoundException(message=f"Alert '{alert_id}' not found")
        alert.status = "resolved"
        alert.resolved_by = actor_id_var.get("")
        alert.resolved_at = datetime.now(UTC)
        alert.resolution_note = resolution_note
        await self._alert_repo.update(alert)
        return alert

    async def list_alerts(self, tenant_id: str, alert_type: str = "",
                           severity: str = "", status: str = "",
                           warehouse_id: str = "", sku_id: str = "",
                           page: int = 1, page_size: int = 20) -> tuple[Sequence[InventoryAlert], int]:
        """分页查询预警列表"""
        return await self._alert_repo.list_by_tenant(
            tenant_id, alert_type=alert_type, severity=severity,
            status=status, warehouse_id=warehouse_id, sku_id=sku_id,
            page=page, page_size=page_size,
        )

    async def init_default_rules(self, tenant_id: str) -> list[InventoryAlertRule]:
        """初始化默认预警规则: 低库存/缺货/积压/滞销/死库存/次品率"""
        defaults = [
            ("低库存预警", "low_stock", "warning",
             {"qty_available_lte": 10, "days_of_supply_lte": 7}, 24),
            ("缺货预警", "stockout", "critical",
             {"qty_available_eq": 0}, 4),
            ("库存积压预警", "overstock", "warning",
             {"days_of_supply_gte": 90, "qty_on_hand_gte": 100}, 168),
            ("滞销品预警", "slow_moving", "info",
             {"avg_daily_out_30d_lte": 0.5, "qty_on_hand_gte": 20}, 168),
            ("死库存预警", "dead_stock", "warning",
             {"avg_daily_out_30d_eq": 0, "qty_on_hand_gte": 10}, 336),
            ("次品率过高预警", "defective_high", "warning",
             {"defective_rate_gte": 0.1, "qty_on_hand_gte": 50}, 24),
        ]
        rules = []
        for name, alert_type, severity, condition, cooldown in defaults:
            rule = await self.create_alert_rule(
                tenant_id=tenant_id, rule_name=name, alert_type=alert_type,
                severity=severity, condition=condition, cooldown_hours=cooldown,
            )
            rules.append(rule)
        return rules

    async def list_rules(self, tenant_id: str) -> list[InventoryAlertRule]:
        """获取租户的所有预警规则"""
        return await self._alert_rule_repo.list_active(tenant_id)

    async def get_rule(self, rule_id: str, tenant_id: str) -> InventoryAlertRule | None:
        """获取单个预警规则"""
        return await self._alert_rule_repo.get_by_id(rule_id, tenant_id)

    async def update_rule(self, rule_id: str, tenant_id: str, **kwargs) -> InventoryAlertRule:
        """更新预警规则"""
        rule = await self._alert_rule_repo.get_by_id(rule_id, tenant_id)
        if not rule:
            raise ValueError(f"Alert rule '{rule_id}' not found")
        if "condition" in kwargs:
            rule.condition_json = json.dumps(kwargs.pop("condition"), default=str)
        if "notify_channels" in kwargs:
            rule.notify_channels = json.dumps(kwargs.pop("notify_channels"), default=str)
        for k, v in kwargs.items():
            if hasattr(rule, k):
                setattr(rule, k, v)
        return await self._alert_rule_repo.update(rule)

    def _evaluate_condition(self, alert_type: str, condition: dict, inventory) -> tuple[bool, str]:
        """
        评估预警条件: 根据预警类型和条件判断是否触发

        参数:
            alert_type: 预警类型
            condition: 触发条件字典
            inventory: 库存实体

        返回:
            (是否触发, 预警消息)
        """
        qty_available = inventory.qty_available
        qty_on_hand = inventory.qty_on_hand
        qty_defective = inventory.qty_defective

        if alert_type == "low_stock":
            threshold = condition.get("qty_available_lte", 10)
            if qty_available <= threshold:
                return True, f"可用库存 {qty_available} ≤ 阈值 {threshold}"
        elif alert_type == "stockout":
            if qty_available == 0:
                return True, "SKU已缺货，可用库存为0"
        elif alert_type == "overstock":
            threshold = condition.get("qty_on_hand_gte", 100)
            if qty_on_hand >= threshold:
                return True, f"在库库存 {qty_on_hand} ≥ 阈值 {threshold}"
        elif alert_type == "slow_moving":
            threshold = condition.get("avg_daily_out_30d_lte", 0.5)
            if qty_on_hand >= condition.get("qty_on_hand_gte", 20):
                return True, f"滞销品，在库 {qty_on_hand}"
        elif alert_type == "dead_stock":
            if qty_on_hand >= condition.get("qty_on_hand_gte", 10):
                return True, f"死库存，在库 {qty_on_hand}"
        elif alert_type == "defective_high":
            rate = qty_defective / qty_on_hand if qty_on_hand > 0 else 0
            threshold = condition.get("defective_rate_gte", 0.1)
            if rate >= threshold:
                return True, f"次品率 {rate:.1%} ≥ 阈值 {threshold:.1%}"
        return False, ""

    def _get_current_value(self, alert_type: str, inventory) -> float:
        """根据预警类型获取当前值"""
        if alert_type in ("low_stock", "stockout"):
            return float(inventory.qty_available)
        elif alert_type == "overstock":
            return float(inventory.qty_on_hand)
        elif alert_type == "defective_high":
            return float(inventory.qty_defective)
        return float(inventory.qty_on_hand)

    def _get_threshold_value(self, alert_type: str, condition: dict) -> float:
        """根据预警类型获取阈值"""
        if alert_type in ("low_stock",):
            return float(condition.get("qty_available_lte", 10))
        elif alert_type == "stockout":
            return 0.0
        elif alert_type == "overstock":
            return float(condition.get("qty_on_hand_gte", 100))
        elif alert_type == "defective_high":
            return float(condition.get("defective_rate_gte", 0.1))
        return 0.0
