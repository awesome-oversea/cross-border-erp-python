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

    from erp.modules.tms.domain.repositories import (
        LogisticsStrategyExecutionLogRepository,
        LogisticsStrategyRepository,
    )


class LogisticsStrategy(Base):
    __tablename__ = "logistics_strategy"
    __table_args__ = {"schema": "tms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    strategy_code: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(200), nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True,
                                                comment="warehouse_allocation/channel_matching/declaration/cost_optimization")
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


class LogisticsStrategyExecutionLog(Base):
    __tablename__ = "logistics_strategy_execution_log"
    __table_args__ = {"schema": "tms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    strategy_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    strategy_code: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    shipment_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    matched_conditions: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    action_taken: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="applied")
    result_detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LogisticsStrategyService:
    """
    物流策略应用服务

    编排物流策略的完整生命周期: 创建 → 更新 → 停用 → 评估 → 执行
    通过 LogisticsStrategyRepository + LogisticsStrategyExecutionLogRepository 操作数据。
    """

    def __init__(self, session: AsyncSession,
                 strategy_repo: LogisticsStrategyRepository | None = None,
                 strategy_log_repo: LogisticsStrategyExecutionLogRepository | None = None):
        self.session = session
        self._strategy_repo = strategy_repo
        self._strategy_log_repo = strategy_log_repo

    async def create_strategy(self, tenant_id: str, strategy_code: str, strategy_name: str,
                               strategy_type: str, description: str = "",
                               condition: dict | None = None, action: dict | None = None,
                               priority: int = 0, effective_from: datetime | None = None,
                               effective_to: datetime | None = None) -> LogisticsStrategy:
        """创建物流策略: 唯一性校验(code) → 持久化"""
        existing = await self._get_by_code(tenant_id, strategy_code)
        if existing:
            raise ValidationException(message=f"Strategy code '{strategy_code}' already exists")

        strategy = LogisticsStrategy(
            tenant_id=tenant_id, strategy_code=strategy_code,
            strategy_name=strategy_name, strategy_type=strategy_type,
            description=description,
            condition_json=json.dumps(condition or {}, default=str),
            action_json=json.dumps(action or {}, default=str),
            priority=priority, effective_from=effective_from,
            effective_to=effective_to,
            created_by=actor_id_var.get(""),
        )
        if self._strategy_repo:
            return await self._strategy_repo.create(strategy)
        self.session.add(strategy)
        await self.session.flush()
        return strategy

    async def update_strategy(self, strategy_id: str, tenant_id: str,
                               strategy_name: str | None = None,
                               description: str | None = None,
                               condition: dict | None = None,
                               action: dict | None = None,
                               priority: int | None = None) -> LogisticsStrategy:
        """更新物流策略: 字段更新 → 版本递增 → 持久化"""
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
        strategy.version += 1
        if self._strategy_repo:
            return await self._strategy_repo.update(strategy)
        await self.session.flush()
        return strategy

    async def deactivate_strategy(self, strategy_id: str, tenant_id: str) -> LogisticsStrategy:
        """停用物流策略"""
        strategy = await self._get_by_id(strategy_id, tenant_id)
        if not strategy:
            raise NotFoundException(message=f"Strategy '{strategy_id}' not found")
        strategy.is_active = False
        if self._strategy_repo:
            return await self._strategy_repo.update(strategy)
        await self.session.flush()
        return strategy

    async def activate_strategy(self, strategy_id: str, tenant_id: str) -> LogisticsStrategy:
        """激活物流策略"""
        strategy = await self._get_by_id(strategy_id, tenant_id)
        if not strategy:
            raise NotFoundException(message=f"Strategy '{strategy_id}' not found")
        strategy.is_active = True
        if self._strategy_repo:
            return await self._strategy_repo.update(strategy)
        await self.session.flush()
        return strategy

    async def evaluate_strategies(self, tenant_id: str, strategy_type: str,
                                   context: dict) -> list[dict]:
        now = datetime.now(UTC)
        stmt = select(LogisticsStrategy).where(
            LogisticsStrategy.tenant_id == tenant_id,
            LogisticsStrategy.strategy_type == strategy_type,
            LogisticsStrategy.is_active,
        ).order_by(LogisticsStrategy.priority.desc())
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
                                shipment_id: str = "", order_id: str = "",
                                context: dict | None = None) -> LogisticsStrategyExecutionLog:
        """执行物流策略: 获取策略 → 记录执行日志"""
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

        log = LogisticsStrategyExecutionLog(
            tenant_id=tenant_id, strategy_id=strategy.id,
            strategy_code=strategy.strategy_code, strategy_type=strategy.strategy_type,
            shipment_id=shipment_id, order_id=order_id,
            matched_conditions=json.dumps(matched_conditions, default=str),
            action_taken=json.dumps(action_taken, default=str),
            result="applied",
            trace_id=trace_id_var.get(""),
        )
        if self._strategy_log_repo:
            return await self._strategy_log_repo.create(log)
        self.session.add(log)
        await self.session.flush()
        return log

    async def list_strategies(self, tenant_id: str, strategy_type: str = "",
                               is_active: bool | None = None,
                               page: int = 1, page_size: int = 20) -> tuple[list[LogisticsStrategy], int]:
        """分页查询物流策略列表"""
        if self._strategy_repo:
            items, total = await self._strategy_repo.list_by_tenant(
                tenant_id, strategy_type=strategy_type, is_active=is_active,
                page=page, page_size=page_size,
            )
            return list(items), total
        conditions = [LogisticsStrategy.tenant_id == tenant_id]
        if strategy_type:
            conditions.append(LogisticsStrategy.strategy_type == strategy_type)
        if is_active is not None:
            conditions.append(LogisticsStrategy.is_active == is_active)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(LogisticsStrategy).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(LogisticsStrategy).where(*conditions).order_by(
            LogisticsStrategy.strategy_type, LogisticsStrategy.priority.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_execution_logs(self, tenant_id: str, strategy_type: str = "",
                                   order_id: str = "", page: int = 1,
                                   page_size: int = 20) -> tuple[list[LogisticsStrategyExecutionLog], int]:
        """分页查询策略执行日志"""
        if self._strategy_log_repo:
            items, total = await self._strategy_log_repo.list_by_tenant(
                tenant_id, strategy_type=strategy_type, order_id=order_id,
                page=page, page_size=page_size,
            )
            return list(items), total
        conditions = [LogisticsStrategyExecutionLog.tenant_id == tenant_id]
        if strategy_type:
            conditions.append(LogisticsStrategyExecutionLog.strategy_type == strategy_type)
        if order_id:
            conditions.append(LogisticsStrategyExecutionLog.order_id == order_id)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(LogisticsStrategyExecutionLog).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(LogisticsStrategyExecutionLog).where(*conditions).order_by(
            LogisticsStrategyExecutionLog.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def init_defaults(self, tenant_id: str):
        defaults = [
            ("warehouse_by_country", "按目的国分仓", "warehouse_allocation",
             {"destination_country": {"op": "in", "value": ["US"]}},
             {"preferred_warehouse": "us_warehouse", "fallback": "cn_warehouse"}, 100),
            ("warehouse_by_stock", "按库存分仓", "warehouse_allocation",
             {"has_local_stock": True},
             {"prefer_local_warehouse": True, "min_stock_days": 7}, 90),
            ("channel_express", "快递渠道匹配", "channel_matching",
             {"weight_kg": {"op": "lt", "value": 2}, "destination_country": {"op": "in", "value": ["US", "UK", "DE"]}},
             {"preferred_channel": "express", "max_delivery_days": 7}, 100),
            ("channel_sea", "海运渠道匹配", "channel_matching",
             {"weight_kg": {"op": "gte", "value": 20}},
             {"preferred_channel": "sea", "max_delivery_days": 45}, 50),
            ("channel_fba", "FBA渠道匹配", "channel_matching",
             {"fulfillment_type": "fba"},
             {"channel": "fba", "auto_create_shipment": True}, 200),
            ("declare_standard", "标准申报", "declaration",
             {"order_amount": {"op": "lt", "value": 800}},
             {"declare_method": "standard", "declare_value_cap": 800}, 100),
            ("declare_low_value", "低值申报", "declaration",
             {"destination_country": {"op": "in", "value": ["EU"]}, "order_amount": {"op": "lt", "value": 150}},
             {"declare_method": "low_value", "declare_value_cap": 22}, 150),
            ("cost_cheapest", "最低成本优化", "cost_optimization",
             {"priority": "cost"},
             {"optimization_target": "cheapest", "max_delivery_days": 30}, 100),
            ("cost_fastest", "最快时效优化", "cost_optimization",
             {"priority": "speed"},
             {"optimization_target": "fastest", "cost_tolerance_percent": 20}, 90),
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

    async def _get_by_code(self, tenant_id: str, strategy_code: str) -> LogisticsStrategy | None:
        if self._strategy_repo:
            return await self._strategy_repo.get_by_code(tenant_id, strategy_code)
        stmt = select(LogisticsStrategy).where(
            LogisticsStrategy.tenant_id == tenant_id,
            LogisticsStrategy.strategy_code == strategy_code,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _get_by_id(self, strategy_id: str, tenant_id: str) -> LogisticsStrategy | None:
        if self._strategy_repo:
            return await self._strategy_repo.get_by_id(strategy_id, tenant_id)
        stmt = select(LogisticsStrategy).where(
            LogisticsStrategy.id == strategy_id,
            LogisticsStrategy.tenant_id == tenant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, strategy_id: str, tenant_id: str) -> LogisticsStrategy:
        strategy = await self._get_by_id(strategy_id, tenant_id)
        if not strategy:
            from erp.shared.exceptions import NotFoundException
            raise NotFoundException(message=f"Strategy '{strategy_id}' not found")
        return strategy
