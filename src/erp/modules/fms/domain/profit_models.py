from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Numeric, String, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ProfitRecord(Base):
    __tablename__ = "profit_record"
    __table_args__ = {"schema": "fms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    order_item_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    dimension_type: Mapped[str] = mapped_column(String(50), nullable=False, default="order")
    dimension_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    revenue_cny: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    cost_purchase_cny: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    cost_logistics_cny: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    cost_warehouse_cny: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    cost_platform_cny: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    cost_advertising_cny: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    cost_other_cny: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    total_cost_cny: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    gross_profit_cny: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    gross_margin: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=Decimal("0"))
    net_profit_cny: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    net_margin: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    period_date: Mapped[str] = mapped_column(String(10), nullable=False, default="", index=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProfitEngine:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def calculate_order_profit(self, tenant_id: str, order_id: str,
                                      revenue_cny: Decimal = Decimal("0")) -> ProfitRecord:
        from erp.modules.fms.domain.cost_models import CostAggregationService
        cost_svc = CostAggregationService(self.session)
        cost_summary = await cost_svc.aggregate_order_cost(tenant_id, order_id)

        cost_by_type = cost_summary.get("cost_by_type", {})
        cost_purchase = Decimal(cost_by_type.get("purchase", "0"))
        cost_logistics = Decimal(cost_by_type.get("logistics", "0"))
        cost_warehouse = Decimal(cost_by_type.get("warehouse", "0"))
        cost_platform = Decimal(cost_by_type.get("platform_fee", "0"))
        cost_advertising = Decimal(cost_by_type.get("advertising", "0"))
        cost_other = Decimal(cost_by_type.get("other", "0"))
        cost_return = Decimal(cost_by_type.get("return", "0"))
        cost_other += cost_return

        total_cost = cost_purchase + cost_logistics + cost_warehouse + cost_platform + cost_advertising + cost_other
        gross_profit = revenue_cny - cost_purchase
        gross_margin = (gross_profit / revenue_cny * 100) if revenue_cny > 0 else Decimal("0")
        net_profit = revenue_cny - total_cost
        net_margin = (net_profit / revenue_cny * 100) if revenue_cny > 0 else Decimal("0")

        record = ProfitRecord(
            tenant_id=tenant_id, order_id=order_id,
            dimension_type="order", dimension_id=order_id,
            revenue_cny=revenue_cny,
            cost_purchase_cny=cost_purchase,
            cost_logistics_cny=cost_logistics,
            cost_warehouse_cny=cost_warehouse,
            cost_platform_cny=cost_platform,
            cost_advertising_cny=cost_advertising,
            cost_other_cny=cost_other,
            total_cost_cny=total_cost,
            gross_profit_cny=gross_profit,
            gross_margin=gross_margin,
            net_profit_cny=net_profit,
            net_margin=net_margin,
            period_date=datetime.now().strftime("%Y-%m-%d"),
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_profit_by_order(self, tenant_id: str, order_id: str) -> ProfitRecord | None:
        stmt = select(ProfitRecord).where(
            ProfitRecord.tenant_id == tenant_id,
            ProfitRecord.order_id == order_id,
        ).order_by(ProfitRecord.calculated_at.desc())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_profit_by_order_or_raise(self, tenant_id: str, order_id: str) -> ProfitRecord:
        record = await self.get_profit_by_order(tenant_id, order_id)
        if not record:
            raise NotFoundException(message=f"Profit record for order '{order_id}' not found")
        return record

    async def get_profit_by_sku(self, tenant_id: str, sku_id: str,
                                 start_date: str | None = None,
                                 end_date: str | None = None) -> list[ProfitRecord]:
        stmt = select(ProfitRecord).where(
            ProfitRecord.tenant_id == tenant_id,
            ProfitRecord.sku_id == sku_id,
        )
        if start_date:
            stmt = stmt.where(ProfitRecord.period_date >= start_date)
        if end_date:
            stmt = stmt.where(ProfitRecord.period_date <= end_date)
        stmt = stmt.order_by(ProfitRecord.period_date.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def aggregate_profit(self, tenant_id: str, dimension_type: str,
                                dimension_id: str | None = None,
                                start_date: str | None = None,
                                end_date: str | None = None) -> dict:
        stmt = select(ProfitRecord).where(
            ProfitRecord.tenant_id == tenant_id,
            ProfitRecord.dimension_type == dimension_type,
        )
        if dimension_id:
            stmt = stmt.where(ProfitRecord.dimension_id == dimension_id)
        if start_date:
            stmt = stmt.where(ProfitRecord.period_date >= start_date)
        if end_date:
            stmt = stmt.where(ProfitRecord.period_date <= end_date)
        result = await self.session.execute(stmt)
        records = list(result.scalars().all())

        total_revenue = sum(r.revenue_cny for r in records)
        total_cost = sum(r.total_cost_cny for r in records)
        total_gross_profit = sum(r.gross_profit_cny for r in records)
        total_net_profit = sum(r.net_profit_cny for r in records)
        avg_gross_margin = (total_gross_profit / total_revenue * 100) if total_revenue > 0 else Decimal("0")
        avg_net_margin = (total_net_profit / total_revenue * 100) if total_revenue > 0 else Decimal("0")

        return {
            "dimension_type": dimension_type,
            "dimension_id": dimension_id,
            "period": f"{start_date or '*'}~{end_date or '*'}",
            "record_count": len(records),
            "total_revenue_cny": str(total_revenue),
            "total_cost_cny": str(total_cost),
            "total_gross_profit_cny": str(total_gross_profit),
            "total_net_profit_cny": str(total_net_profit),
            "avg_gross_margin": str(round(avg_gross_margin, 2)),
            "avg_net_margin": str(round(avg_net_margin, 2)),
        }
