"""
WMS 调拨与FBA补货领域模型 + 服务

包含:
- StockTransferOrder: 调拨单实体
- FBAReplenishmentPlan: FBA补货计划实体
- StockTransferService: 调拨应用服务 (使用仓储接口)
- FBAReplenishmentService: FBA补货应用服务 (使用仓储接口)
"""
from __future__ import annotations

import json
import math
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from erp.modules.wms.domain.repositories import (
        FBAReplenishmentPlanRepository,
        StockTransferOrderRepository,
    )


class TransferStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class ReplenishmentStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    SHIPPED = "shipped"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class StockTransferOrder(Base):
    __tablename__ = "stock_transfer_order"
    __table_args__ = {"schema": "wms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    transfer_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    from_warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    to_warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    total_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FBAReplenishmentPlan(Base):
    __tablename__ = "fba_replenishment_plan"
    __table_args__ = {"schema": "wms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    plan_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    fba_warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    current_fba_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_daily_sales: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    days_of_supply: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    suggested_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approved_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    strategy_params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    min_replenishment_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_replenishment_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    safety_stock_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StockTransferService:
    """
    调拨应用服务

    编排调拨单的完整生命周期: 创建 → 提交 → 发货 → 收货 / 取消
    通过 StockTransferOrderRepository 操作数据。
    """

    def __init__(self, session: AsyncSession, transfer_repo: StockTransferOrderRepository):
        self._session = session
        self._transfer_repo = transfer_repo

    async def create_transfer(self, tenant_id: str, from_warehouse_id: str, to_warehouse_id: str,
                               items: list[dict], reason: str = "") -> StockTransferOrder:
        """创建调拨单: 仓库校验 → 生成编号 → 持久化"""
        if from_warehouse_id == to_warehouse_id:
            raise ValidationException(message="Source and target warehouse cannot be the same")

        total_qty = sum(item.get("qty", 0) for item in items)
        transfer_no = f"ST-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"

        transfer = StockTransferOrder(
            tenant_id=tenant_id, transfer_no=transfer_no,
            from_warehouse_id=from_warehouse_id, to_warehouse_id=to_warehouse_id,
            reason=reason, items_json=json.dumps(items, default=str),
            total_qty=total_qty, trace_id=trace_id_var.get(""),
            created_by=actor_id_var.get(""),
        )
        return await self._transfer_repo.create(transfer)

    async def submit_transfer(self, transfer_id: str, tenant_id: str) -> StockTransferOrder:
        """提交调拨单: 状态校验(draft) → 更新为 submitted"""
        transfer = await self._transfer_repo.get_by_id(transfer_id, tenant_id)
        if not transfer:
            raise NotFoundException(message=f"Transfer '{transfer_id}' not found")
        if transfer.status != "draft":
            raise ValidationException(message=f"Cannot submit transfer in status '{transfer.status}'")
        transfer.status = "submitted"
        await self._transfer_repo.update(transfer)
        return transfer

    async def ship_transfer(self, transfer_id: str, tenant_id: str) -> StockTransferOrder:
        """发货调拨单: 状态校验(submitted) → 更新为 in_transit"""
        transfer = await self._transfer_repo.get_by_id(transfer_id, tenant_id)
        if not transfer:
            raise NotFoundException(message=f"Transfer '{transfer_id}' not found")
        if transfer.status != "submitted":
            raise ValidationException(message=f"Cannot ship transfer in status '{transfer.status}'")
        transfer.status = "in_transit"
        transfer.shipped_at = datetime.now(UTC)
        await self._transfer_repo.update(transfer)
        return transfer

    async def receive_transfer(self, transfer_id: str, tenant_id: str) -> StockTransferOrder:
        """收货调拨单: 状态校验(in_transit) → 更新为 received"""
        transfer = await self._transfer_repo.get_by_id(transfer_id, tenant_id)
        if not transfer:
            raise NotFoundException(message=f"Transfer '{transfer_id}' not found")
        if transfer.status != "in_transit":
            raise ValidationException(message=f"Cannot receive transfer in status '{transfer.status}'")
        transfer.status = "received"
        transfer.received_at = datetime.now(UTC)
        await self._transfer_repo.update(transfer)
        return transfer

    async def cancel_transfer(self, transfer_id: str, tenant_id: str) -> StockTransferOrder:
        """取消调拨单: 状态校验(非 received/cancelled) → 更新为 cancelled"""
        transfer = await self._transfer_repo.get_by_id(transfer_id, tenant_id)
        if not transfer:
            raise NotFoundException(message=f"Transfer '{transfer_id}' not found")
        if transfer.status in ("received", "cancelled"):
            raise ValidationException(message=f"Cannot cancel transfer in status '{transfer.status}'")
        transfer.status = "cancelled"
        await self._transfer_repo.update(transfer)
        return transfer

    async def list_transfers(self, tenant_id: str, status: str = "",
                              from_warehouse_id: str = "", to_warehouse_id: str = "",
                              page: int = 1, page_size: int = 20) -> tuple[Sequence[StockTransferOrder], int]:
        """分页查询调拨单列表"""
        return await self._transfer_repo.list_by_tenant(
            tenant_id, status=status,
            from_warehouse_id=from_warehouse_id, to_warehouse_id=to_warehouse_id,
            page=page, page_size=page_size,
        )


class FBAReplenishmentService:
    """
    FBA补货应用服务

    编排FBA补货计划的完整生命周期: 生成 → 提交 → 审批
    通过 FBAReplenishmentPlanRepository 操作数据。
    """

    def __init__(self, session: AsyncSession, plan_repo: FBAReplenishmentPlanRepository):
        self._session = session
        self._plan_repo = plan_repo

    async def generate_replenishment_plan(self, tenant_id: str, sku_id: str,
                                           fba_warehouse_id: str, source_warehouse_id: str,
                                           current_fba_qty: int = 0,
                                           avg_daily_sales: float = 0.0,
                                           lead_time_days: int = 14,
                                           safety_stock_days: int = 7,
                                           strategy: str = "min_max",
                                           strategy_params: dict | None = None) -> FBAReplenishmentPlan:
        """
        生成FBA补货计划: 计算供应天数 → 计算建议补货量 → 持久化

        参数:
            tenant_id: 租户ID
            sku_id: SKU ID
            fba_warehouse_id: FBA仓库ID
            source_warehouse_id: 补货来源仓库ID
            current_fba_qty: FBA当前库存
            avg_daily_sales: 日均销量
            lead_time_days: 补货提前期(天)
            safety_stock_days: 安全库存天数
            strategy: 补货策略 (min_max/fixed_quantity/eoq/reorder_point)
            strategy_params: 策略参数
        """
        days_of_supply = current_fba_qty / avg_daily_sales if avg_daily_sales > 0 else 999
        suggested_qty = self._calculate_suggested_qty(
            strategy, current_fba_qty, avg_daily_sales,
            lead_time_days, safety_stock_days, strategy_params or {},
        )

        if suggested_qty <= 0:
            raise ValidationException(message="No replenishment needed based on current parameters")

        plan_no = f"FBA-RP-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"

        params = strategy_params or {}
        plan = FBAReplenishmentPlan(
            tenant_id=tenant_id, plan_no=plan_no,
            sku_id=sku_id, fba_warehouse_id=fba_warehouse_id,
            source_warehouse_id=source_warehouse_id,
            current_fba_qty=current_fba_qty, avg_daily_sales=avg_daily_sales,
            days_of_supply=days_of_supply, suggested_qty=suggested_qty,
            strategy_name=strategy,
            strategy_params_json=json.dumps(params, default=str),
            min_replenishment_qty=params.get("min_qty", 10),
            max_replenishment_qty=params.get("max_qty", 1000),
            lead_time_days=lead_time_days, safety_stock_days=safety_stock_days,
            trace_id=trace_id_var.get(""), created_by=actor_id_var.get(""),
        )
        return await self._plan_repo.create(plan)

    async def approve_plan(self, plan_id: str, tenant_id: str,
                            approved_qty: int | None = None) -> FBAReplenishmentPlan:
        """审批补货计划: 状态校验(submitted) → 更新为 approved"""
        plan = await self._plan_repo.get_by_id(plan_id, tenant_id)
        if not plan:
            raise NotFoundException(message=f"Replenishment plan '{plan_id}' not found")
        if plan.status != "submitted":
            raise ValidationException(message=f"Cannot approve plan in status '{plan.status}'")

        plan.approved_qty = approved_qty or plan.suggested_qty
        plan.status = "approved"
        await self._plan_repo.update(plan)
        return plan

    async def submit_plan(self, plan_id: str, tenant_id: str) -> FBAReplenishmentPlan:
        """提交补货计划: 状态校验(draft) → 更新为 submitted"""
        plan = await self._plan_repo.get_by_id(plan_id, tenant_id)
        if not plan:
            raise NotFoundException(message=f"Replenishment plan '{plan_id}' not found")
        if plan.status != "draft":
            raise ValidationException(message=f"Cannot submit plan in status '{plan.status}'")
        plan.status = "submitted"
        await self._plan_repo.update(plan)
        return plan

    async def list_plans(self, tenant_id: str, sku_id: str = "", status: str = "",
                          page: int = 1, page_size: int = 20) -> tuple[Sequence[FBAReplenishmentPlan], int]:
        """分页查询补货计划列表"""
        return await self._plan_repo.list_by_tenant(
            tenant_id, sku_id=sku_id, status=status,
            page=page, page_size=page_size,
        )

    def _calculate_suggested_qty(self, strategy: str, current_qty: int,
                                  avg_daily_sales: float, lead_time_days: int,
                                  safety_stock_days: int, params: dict) -> int:
        """
        根据策略计算建议补货量

        支持策略:
        - min_max: 最小最大库存策略，低于最小值时补到最大值
        - fixed_quantity: 固定订货量策略，低于订货点时按固定量补货
        - eoq: 经济订货量策略，基于EOQ公式计算最优订货量
        - reorder_point: 订货点策略，低于订货点时补到安全库存水平
        """
        if strategy == "min_max":
            min_stock = params.get("min_stock", int(avg_daily_sales * (lead_time_days + safety_stock_days)))
            max_stock = params.get("max_stock", int(avg_daily_sales * (lead_time_days + safety_stock_days) * 2))
            if current_qty <= min_stock:
                return max_stock - current_qty
            return 0
        elif strategy == "fixed_quantity":
            reorder_point = int(avg_daily_sales * (lead_time_days + safety_stock_days))
            if current_qty <= reorder_point:
                return params.get("order_qty", int(avg_daily_sales * 30))
            return 0
        elif strategy == "eoq":
            ordering_cost = params.get("ordering_cost", 50.0)
            holding_cost = params.get("holding_cost", 0.1)
            annual_demand = avg_daily_sales * 365
            if annual_demand <= 0 or holding_cost <= 0:
                return 0
            eoq = math.sqrt(2 * annual_demand * ordering_cost / holding_cost)
            reorder_point = int(avg_daily_sales * (lead_time_days + safety_stock_days))
            if current_qty <= reorder_point:
                return int(eoq)
            return 0
        else:
            reorder_point = int(avg_daily_sales * (lead_time_days + safety_stock_days))
            if current_qty <= reorder_point:
                return reorder_point - current_qty + int(avg_daily_sales * safety_stock_days)
            return 0
