from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class OrderStrategy(Base):
    __tablename__ = "order_strategy"
    __table_args__ = {"schema": "oms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    strategy_code: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(200), nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True,
                                                comment="audit/split_merge/profit/risk_control")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    condition_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    action_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OrderStrategyExecutionLog(Base):
    __tablename__ = "order_strategy_execution_log"
    __table_args__ = {"schema": "oms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    strategy_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    strategy_code: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    order_no: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    matched_conditions: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    action_taken: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="applied")
    result_detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OrderStrategyService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_strategy(self, tenant_id: str, strategy_code: str, strategy_name: str,
                               strategy_type: str, description: str = "",
                               condition: dict | None = None, action: dict | None = None,
                               priority: int = 0, effective_from: datetime | None = None,
                               effective_to: datetime | None = None) -> OrderStrategy:
        existing = await self._get_by_code(tenant_id, strategy_code)
        if existing:
            raise ValidationException(message=f"Strategy code '{strategy_code}' already exists")

        strategy = OrderStrategy(
            tenant_id=tenant_id, strategy_code=strategy_code,
            strategy_name=strategy_name, strategy_type=strategy_type,
            description=description,
            condition_json=json.dumps(condition or {}, default=str),
            action_json=json.dumps(action or {}, default=str),
            priority=priority, effective_from=effective_from,
            effective_to=effective_to,
            created_by=actor_id_var.get(""),
        )
        self.session.add(strategy)
        await self.session.flush()
        return strategy

    async def update_strategy(self, strategy_id: str, tenant_id: str,
                               strategy_name: str | None = None,
                               description: str | None = None,
                               condition: dict | None = None,
                               action: dict | None = None,
                               priority: int | None = None,
                               effective_from: datetime | None = None,
                               effective_to: datetime | None = None) -> OrderStrategy:
        strategy = await self._get_by_id(strategy_id, tenant_id)
        if not strategy:
            raise NotFoundException(message=f"Strategy '{strategy_id}' not found")
        if strategy_name is not None:
            strategy.strategy_name = strategy_name
        if description is not None:
            strategy.description = description
        if condition is not None:
            strategy.condition_json = json.dumps(condition, default=str)
        if action is not None:
            strategy.action_json = json.dumps(action, default=str)
        if priority is not None:
            strategy.priority = priority
        if effective_from is not None:
            strategy.effective_from = effective_from
        if effective_to is not None:
            strategy.effective_to = effective_to
        strategy.version += 1
        await self.session.flush()
        return strategy

    async def deactivate_strategy(self, strategy_id: str, tenant_id: str) -> OrderStrategy:
        strategy = await self._get_by_id(strategy_id, tenant_id)
        if not strategy:
            raise NotFoundException(message=f"Strategy '{strategy_id}' not found")
        strategy.is_active = False
        await self.session.flush()
        return strategy

    async def evaluate_strategies(self, tenant_id: str, strategy_type: str,
                                   context: dict) -> list[dict]:
        now = datetime.now(UTC)
        stmt = select(OrderStrategy).where(
            OrderStrategy.tenant_id == tenant_id,
            OrderStrategy.strategy_type == strategy_type,
            OrderStrategy.is_active,
        ).order_by(OrderStrategy.priority.desc())
        result = await self.session.execute(stmt)
        strategies = list(result.scalars().all())

        matched = []
        for strategy in strategies:
            if strategy.effective_from and now < strategy.effective_from:
                continue
            if strategy.effective_to and now > strategy.effective_to:
                continue
            try:
                condition = json.loads(strategy.condition_json)
                if self._match_condition(condition, context):
                    action = json.loads(strategy.action_json)
                    matched.append({
                        "strategy_id": strategy.id,
                        "strategy_code": strategy.strategy_code,
                        "strategy_name": strategy.strategy_name,
                        "strategy_type": strategy.strategy_type,
                        "action": action,
                        "priority": strategy.priority,
                        "version": strategy.version,
                    })
            except (json.JSONDecodeError, Exception):
                continue
        return matched

    async def execute_strategy(self, tenant_id: str, strategy_id: str,
                                order_id: str, order_no: str = "",
                                context: dict | None = None) -> OrderStrategyExecutionLog:
        strategy = await self._get_by_id(strategy_id, tenant_id)
        if not strategy:
            raise NotFoundException(message=f"Strategy '{strategy_id}' not found")

        matched_conditions = {}
        action_taken = {}
        try:
            matched_conditions = json.loads(strategy.condition_json)
            action_taken = json.loads(strategy.action_json)
        except Exception:
            pass

        log = OrderStrategyExecutionLog(
            tenant_id=tenant_id, strategy_id=strategy.id,
            strategy_code=strategy.strategy_code, strategy_type=strategy.strategy_type,
            order_id=order_id, order_no=order_no,
            matched_conditions=json.dumps(matched_conditions, default=str),
            action_taken=json.dumps(action_taken, default=str),
            result="applied",
            trace_id=trace_id_var.get(""),
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def list_strategies(self, tenant_id: str, strategy_type: str = "",
                               is_active: bool | None = None,
                               page: int = 1, page_size: int = 20) -> tuple[list[OrderStrategy], int]:
        conditions = [OrderStrategy.tenant_id == tenant_id]
        if strategy_type:
            conditions.append(OrderStrategy.strategy_type == strategy_type)
        if is_active is not None:
            conditions.append(OrderStrategy.is_active == is_active)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(OrderStrategy).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(OrderStrategy).where(*conditions).order_by(
            OrderStrategy.strategy_type, OrderStrategy.priority.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_execution_logs(self, tenant_id: str, strategy_type: str = "",
                                   order_id: str = "", page: int = 1,
                                   page_size: int = 20) -> tuple[list[OrderStrategyExecutionLog], int]:
        conditions = [OrderStrategyExecutionLog.tenant_id == tenant_id]
        if strategy_type:
            conditions.append(OrderStrategyExecutionLog.strategy_type == strategy_type)
        if order_id:
            conditions.append(OrderStrategyExecutionLog.order_id == order_id)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(OrderStrategyExecutionLog).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(OrderStrategyExecutionLog).where(*conditions).order_by(
            OrderStrategyExecutionLog.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def init_defaults(self, tenant_id: str):
        defaults = [
            ("audit_auto_pass", "小额订单自动审核", "audit",
             {"order_amount": {"op": "lt", "value": 500}, "risk_level": {"op": "ne", "value": "high"}},
             {"action": "auto_approve", "reason": "小额低风险自动通过"}, 100),
            ("audit_blacklist", "黑名单买家拦截", "audit",
             {"buyer_id": {"op": "in", "value": "__blacklist__"}},
             {"action": "hold", "reason": "黑名单买家"}, 200),
            ("audit_low_profit", "低利润订单拦截", "audit",
             {"profit_margin": {"op": "lt", "value": 0.03}},
             {"action": "hold", "reason": "利润率低于3%"}, 150),
            ("audit_high_value", "大额订单审核", "audit",
             {"order_amount": {"op": "gte", "value": 10000}},
             {"action": "require_approval", "reason": "大额订单需审批"}, 180),
            ("split_multi_warehouse", "多仓拆单", "split_merge",
             {"items_from_warehouses": {"op": "gt", "value": 1}},
             {"action": "split_by_warehouse"}, 100),
            ("merge_same_buyer", "同买家合单", "split_merge",
             {"same_buyer_pending_orders": {"op": "gte", "value": 2}},
             {"action": "merge_orders"}, 50),
            ("profit_check", "利润保护策略", "profit",
             {"profit_margin": {"op": "lt", "value": 0}},
             {"action": "block", "reason": "负利润订单拦截"}, 200),
            ("risk_repeat_order", "重复下单检测", "risk_control",
             {"same_buyer_same_sku_24h": {"op": "gte", "value": 3}},
             {"action": "hold", "reason": "疑似重复下单"}, 190),
            ("risk_address_mismatch", "收货地址异常", "risk_control",
             {"billing_shipping_country_mismatch": True},
             {"action": "hold", "reason": "账单与收货地址不匹配"}, 180),
        ]
        for code, name, stype, condition, action, priority in defaults:
            existing = await self._get_by_code(tenant_id, code)
            if not existing:
                await self.create_strategy(tenant_id, code, name, stype,
                                           condition=condition, action=action,
                                           priority=priority)

    def _match_condition(self, condition: dict, context: dict) -> bool:
        for key, expected in condition.items():
            actual = context.get(key)
            if isinstance(expected, dict):
                op = expected.get("op", "eq")
                val = expected.get("value")
                if (op == "eq" and actual != val) or (op == "ne" and actual == val) or (op == "gt" and (actual is None or actual <= val)) or (op == "gte" and (actual is None or actual < val)) or (op == "lt" and (actual is None or actual >= val)) or (op == "lte" and (actual is None or actual > val)) or (op == "in" and actual not in (val if isinstance(val, list) else [val])) or (op == "contains" and (actual is None or val not in str(actual))):
                    return False
            elif isinstance(expected, bool):
                if actual != expected:
                    return False
            else:
                if actual != expected:
                    return False
        return True

    async def _get_by_code(self, tenant_id: str, strategy_code: str) -> OrderStrategy | None:
        stmt = select(OrderStrategy).where(
            OrderStrategy.tenant_id == tenant_id,
            OrderStrategy.strategy_code == strategy_code,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _get_by_id(self, strategy_id: str, tenant_id: str) -> OrderStrategy | None:
        stmt = select(OrderStrategy).where(
            OrderStrategy.id == strategy_id,
            OrderStrategy.tenant_id == tenant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
