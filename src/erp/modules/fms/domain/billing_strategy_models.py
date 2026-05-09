from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class BillingStrategy(Base):
    __tablename__ = "billing_strategy"
    __table_args__ = {"schema": "fms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    strategy_code: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(200), nullable=False)
    fee_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True,
                                           comment="platform_fee/logistics_fee/warehouse_fee/service_fee/other_fee")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    calculation_method: Mapped[str] = mapped_column(String(50), nullable=False, default="percentage",
                                                     comment="percentage/fixed/tiered/formula")
    condition_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    rate_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    tier_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    formula_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    min_fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    max_fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BillingCalculationLog(Base):
    __tablename__ = "billing_calculation_log"
    __table_args__ = {"schema": "fms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    strategy_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    strategy_code: Mapped[str] = mapped_column(String(100), nullable=False)
    fee_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    calculated_fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    calculation_detail: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BillingStrategyService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_strategy(self, tenant_id: str, strategy_code: str, strategy_name: str,
                               fee_type: str, description: str = "",
                               calculation_method: str = "percentage",
                               condition: dict | None = None, rate: dict | None = None,
                               tiers: list | None = None, formula: dict | None = None,
                               currency: str = "CNY", min_fee: float = 0, max_fee: float = 0,
                               priority: int = 0,
                               effective_from: datetime | None = None,
                               effective_to: datetime | None = None) -> BillingStrategy:
        existing = await self._get_by_code(tenant_id, strategy_code)
        if existing:
            raise ValidationException(message=f"Strategy code '{strategy_code}' already exists")

        strategy = BillingStrategy(
            tenant_id=tenant_id, strategy_code=strategy_code,
            strategy_name=strategy_name, fee_type=fee_type,
            description=description, calculation_method=calculation_method,
            condition_json=json.dumps(condition or {}, default=str),
            rate_json=json.dumps(rate or {}, default=str),
            tier_json=json.dumps(tiers or [], default=str),
            formula_json=json.dumps(formula or {}, default=str),
            currency=currency,
            min_fee=Decimal(str(min_fee)), max_fee=Decimal(str(max_fee)),
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
                               calculation_method: str | None = None,
                               condition: dict | None = None,
                               rate: dict | None = None,
                               tiers: list | None = None,
                               formula: dict | None = None,
                               min_fee: float | None = None,
                               max_fee: float | None = None) -> BillingStrategy:
        strategy = await self._get_by_id(strategy_id, tenant_id)
        if not strategy:
            raise NotFoundException(message=f"Strategy '{strategy_id}' not found")
        if strategy_name is not None:
            strategy.strategy_name = strategy_name
        if description is not None:
            strategy.description = description
        if calculation_method is not None:
            strategy.calculation_method = calculation_method
        if condition is not None:
            strategy.condition_json = json.dumps(condition, default=str)
        if rate is not None:
            strategy.rate_json = json.dumps(rate, default=str)
        if tiers is not None:
            strategy.tier_json = json.dumps(tiers, default=str)
        if formula is not None:
            strategy.formula_json = json.dumps(formula, default=str)
        if min_fee is not None:
            strategy.min_fee = Decimal(str(min_fee))
        if max_fee is not None:
            strategy.max_fee = Decimal(str(max_fee))
        strategy.version += 1
        await self.session.flush()
        return strategy

    async def deactivate_strategy(self, strategy_id: str, tenant_id: str) -> BillingStrategy:
        strategy = await self._get_by_id(strategy_id, tenant_id)
        if not strategy:
            raise NotFoundException(message=f"Strategy '{strategy_id}' not found")
        strategy.is_active = False
        await self.session.flush()
        return strategy

    async def calculate_fee(self, tenant_id: str, fee_type: str,
                             base_amount: Decimal, context: dict | None = None,
                             source_type: str = "", source_id: str = "",
                             order_id: str = "") -> BillingCalculationLog:
        now = datetime.now(UTC)
        ctx = context or {}

        stmt = select(BillingStrategy).where(
            BillingStrategy.tenant_id == tenant_id,
            BillingStrategy.fee_type == fee_type,
            BillingStrategy.is_active,
        ).order_by(BillingStrategy.priority.desc())
        result = await self.session.execute(stmt)
        strategies = list(result.scalars().all())

        matched_strategy = None
        for strategy in strategies:
            if strategy.effective_from and now < strategy.effective_from:
                continue
            if strategy.effective_to and now > strategy.effective_to:
                continue
            try:
                condition = json.loads(strategy.condition_json)
                if not condition or self._match_condition(condition, ctx):
                    matched_strategy = strategy
                    break
            except Exception:
                if not json.loads(strategy.condition_json):
                    matched_strategy = strategy
                    break

        if not matched_strategy:
            raise NotFoundException(message=f"No active billing strategy found for fee_type '{fee_type}'")

        calculated_fee = self._calculate(matched_strategy, base_amount, ctx)

        if matched_strategy.min_fee and calculated_fee < matched_strategy.min_fee:
            calculated_fee = matched_strategy.min_fee
        if matched_strategy.max_fee and matched_strategy.max_fee > 0 and calculated_fee > matched_strategy.max_fee:
            calculated_fee = matched_strategy.max_fee

        calculation_detail = {
            "method": matched_strategy.calculation_method,
            "base_amount": float(base_amount),
            "calculated_fee": float(calculated_fee),
            "min_fee": float(matched_strategy.min_fee),
            "max_fee": float(matched_strategy.max_fee),
        }

        log = BillingCalculationLog(
            tenant_id=tenant_id, strategy_id=matched_strategy.id,
            strategy_code=matched_strategy.strategy_code,
            fee_type=fee_type, source_type=source_type,
            source_id=source_id, order_id=order_id,
            base_amount=base_amount, calculated_fee=calculated_fee,
            currency=matched_strategy.currency,
            calculation_detail=json.dumps(calculation_detail, default=str),
            trace_id=trace_id_var.get(""),
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def list_strategies(self, tenant_id: str, fee_type: str = "",
                               is_active: bool | None = None,
                               page: int = 1, page_size: int = 20) -> tuple[list[BillingStrategy], int]:
        conditions = [BillingStrategy.tenant_id == tenant_id]
        if fee_type:
            conditions.append(BillingStrategy.fee_type == fee_type)
        if is_active is not None:
            conditions.append(BillingStrategy.is_active == is_active)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(BillingStrategy).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(BillingStrategy).where(*conditions).order_by(
            BillingStrategy.fee_type, BillingStrategy.priority.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_calculation_logs(self, tenant_id: str, fee_type: str = "",
                                     order_id: str = "", page: int = 1,
                                     page_size: int = 20) -> tuple[list[BillingCalculationLog], int]:
        conditions = [BillingCalculationLog.tenant_id == tenant_id]
        if fee_type:
            conditions.append(BillingCalculationLog.fee_type == fee_type)
        if order_id:
            conditions.append(BillingCalculationLog.order_id == order_id)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(BillingCalculationLog).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(BillingCalculationLog).where(*conditions).order_by(
            BillingCalculationLog.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def init_defaults(self, tenant_id: str):
        defaults = [
            ("amazon_commission", "Amazon销售佣金", "platform_fee", "percentage",
             {"platform": "amazon"},
             {"rate": 0.15}, [], {},
             "USD", 0, 0, 100),
            ("ebay_commission", "eBay销售佣金", "platform_fee", "percentage",
             {"platform": "ebay"},
             {"rate": 0.13}, [], {},
             "USD", 0, 0, 90),
            ("shopee_commission", "Shopee销售佣金", "platform_fee", "tiered",
             {"platform": "shopee"},
             {}, [
                 {"min_amount": 0, "max_amount": 1000, "rate": 0.06},
                 {"min_amount": 1000, "max_amount": 10000, "rate": 0.05},
                 {"min_amount": 10000, "max_amount": 0, "rate": 0.04},
             ], {},
             "CNY", 0, 0, 80),
            ("express_shipping", "快递物流费", "logistics_fee", "tiered",
             {"shipping_method": "express"},
             {}, [
                 {"min_weight": 0, "max_weight": 0.5, "fee": 30},
                 {"min_weight": 0.5, "max_weight": 2, "fee": 50},
                 {"min_weight": 2, "max_weight": 5, "fee": 80},
                 {"min_weight": 5, "max_weight": 0, "fee_per_kg": 15},
             ], {},
             "CNY", 0, 0, 100),
            ("sea_shipping", "海运物流费", "logistics_fee", "formula",
             {"shipping_method": "sea"},
             {}, [], {
                 "base_fee": 500, "per_cbm": 800, "min_cbm": 1,
                 "formula": "base_fee + max(volume_cbm, min_cbm) * per_cbm",
             },
             "CNY", 0, 0, 90),
            ("warehouse_storage", "仓储存储费", "warehouse_fee", "tiered",
             {},
             {}, [
                 {"min_days": 0, "max_days": 30, "rate_per_unit_per_day": 0.5},
                 {"min_days": 30, "max_days": 90, "rate_per_unit_per_day": 1.0},
                 {"min_days": 90, "max_days": 180, "rate_per_unit_per_day": 2.0},
                 {"min_days": 180, "max_days": 0, "rate_per_unit_per_day": 5.0},
             ], {},
             "CNY", 0, 0, 100),
            ("warehouse_operation", "仓储操作费", "warehouse_fee", "fixed",
             {},
             {"fee": 3}, [], {},
             "CNY", 0, 0, 90),
            ("packaging_fee", "包装服务费", "service_fee", "fixed",
             {},
             {"fee": 5}, [], {},
             "CNY", 0, 0, 80),
            ("return_processing", "退货处理费", "service_fee", "fixed",
             {},
             {"fee": 15}, [], {},
             "CNY", 0, 0, 70),
        ]
        for code, name, ftype, method, cond, rate, tiers, formula, cur, min_f, max_f, pri in defaults:
            existing = await self._get_by_code(tenant_id, code)
            if not existing:
                await self.create_strategy(
                    tenant_id, code, name, ftype,
                    calculation_method=method, condition=cond,
                    rate=rate, tiers=tiers, formula=formula,
                    currency=cur, min_fee=min_f, max_fee=max_f,
                    priority=pri,
                )

    def _calculate(self, strategy: BillingStrategy, base_amount: Decimal, context: dict) -> Decimal:
        method = strategy.calculation_method

        if method == "percentage":
            rate_data = json.loads(strategy.rate_json)
            rate = Decimal(str(rate_data.get("rate", 0)))
            return (base_amount * rate).quantize(Decimal("0.01"))

        elif method == "fixed":
            rate_data = json.loads(strategy.rate_json)
            fee = Decimal(str(rate_data.get("fee", 0)))
            return fee

        elif method == "tiered":
            tiers = json.loads(strategy.tier_json)
            for tier in tiers:
                if self._match_tier(tier, base_amount, context):
                    if "fee" in tier:
                        return Decimal(str(tier["fee"]))
                    elif "rate" in tier:
                        return (base_amount * Decimal(str(tier["rate"]))).quantize(Decimal("0.01"))
                    elif "fee_per_kg" in tier:
                        weight = Decimal(str(context.get("weight_kg", 0)))
                        return (weight * Decimal(str(tier["fee_per_kg"]))).quantize(Decimal("0.01"))
                    elif "rate_per_unit_per_day" in tier:
                        qty = Decimal(str(context.get("quantity", 1)))
                        days = Decimal(str(context.get("storage_days", 1)))
                        return (qty * days * Decimal(str(tier["rate_per_unit_per_day"]))).quantize(Decimal("0.01"))
            return Decimal("0")

        elif method == "formula":
            formula_data = json.loads(strategy.formula_json)
            base_fee = Decimal(str(formula_data.get("base_fee", 0)))
            return base_fee

        return Decimal("0")

    def _match_tier(self, tier: dict, base_amount: Decimal, context: dict) -> bool:
        if "min_amount" in tier and "max_amount" in tier:
            min_a = Decimal(str(tier.get("min_amount", 0)))
            max_a = Decimal(str(tier.get("max_amount", 0)))
            if base_amount >= min_a and (max_a == 0 or base_amount < max_a):
                return True
        if "min_weight" in tier and "max_weight" in tier:
            weight = Decimal(str(context.get("weight_kg", 0)))
            min_w = Decimal(str(tier.get("min_weight", 0)))
            max_w = Decimal(str(tier.get("max_weight", 0)))
            if weight >= min_w and (max_w == 0 or weight < max_w):
                return True
        if "min_days" in tier and "max_days" in tier:
            days = Decimal(str(context.get("storage_days", 0)))
            min_d = Decimal(str(tier.get("min_days", 0)))
            max_d = Decimal(str(tier.get("max_days", 0)))
            if days >= min_d and (max_d == 0 or days < max_d):
                return True
        return False

    def _match_condition(self, condition: dict, context: dict) -> bool:
        for key, expected in condition.items():
            actual = context.get(key)
            if isinstance(expected, dict):
                op = expected.get("op", "eq")
                val = expected.get("value")
                if (op == "eq" and actual != val) or (op == "ne" and actual == val) or (op == "in" and actual not in (val if isinstance(val, list) else [val])):
                    return False
            elif isinstance(expected, bool):
                if actual != expected:
                    return False
            else:
                if actual != expected:
                    return False
        return True

    async def _get_by_code(self, tenant_id: str, strategy_code: str) -> BillingStrategy | None:
        stmt = select(BillingStrategy).where(
            BillingStrategy.tenant_id == tenant_id,
            BillingStrategy.strategy_code == strategy_code,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _get_by_id(self, strategy_id: str, tenant_id: str) -> BillingStrategy | None:
        stmt = select(BillingStrategy).where(
            BillingStrategy.id == strategy_id,
            BillingStrategy.tenant_id == tenant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
