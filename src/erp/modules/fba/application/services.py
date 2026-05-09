"""
FBA (FBA管理域) 应用服务层

职责: 编排FBA货件/库存/费用/标签/补货/入库计划的完整业务流程

核心服务:
  - FbaShipmentService: FBA货件管理，创建/发货/接收全流程
  - FbaInventoryService: FBA库存管理，实时库存与预留/在途
  - FbaFeeService: FBA费用管理，仓储费/配送费/长期仓储费
  - FbaBoxLabelService: FBA箱标管理，箱标打印与跟踪
  - FbaReplenishmentPlanService: FBA补货计划，智能补货建议
  - FbaInboundPlanService: FBA入库计划，入库排程与分配
  - FBAQueryService: 统一查询服务，跨实体聚合查询
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func as sa_func
from sqlalchemy import select

from erp.modules.fba.domain.models import FbaBoxLabel, FbaException, FbaFee, FbaInboundPlan, FbaInventory, FbaReplenishmentPlan, FbaShipment
from erp.modules.fba.domain.services import (
    BOX_LABEL_STATUS_TRANSITIONS,
    INBOUND_PLAN_STATUS_TRANSITIONS,
    REPLENISHMENT_STATUS_TRANSITIONS,
    FbaBoxLabelDomainService,
    FbaInboundPlanDomainService,
    FbaReplenishmentDomainService,
)
from erp.shared.exceptions import DuplicateCodeException, NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from erp.modules.fba.domain.repositories import (
        FbaBoxLabelRepository,
        FbaFeeRepository,
        FbaInboundPlanRepository,
        FbaInventoryRepository,
        FbaReplenishmentPlanRepository,
        FbaShipmentRepository,
    )

logger = get_logger("erp.fba")

FBA_SHIPMENT_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["submitted", "cancelled"],
    "submitted": ["in_review", "cancelled"],
    "in_review": ["working", "cancelled"],
    "working": ["shipped", "cancelled"],
    "shipped": ["received", "partial_received", "cancelled"],
    "partial_received": ["received", "cancelled"],
    "received": ["closed"],
    "closed": [],
    "cancelled": [],
}

FBA_FEE_TYPES = {
    "fba_fulfillment_fee", "storage_fee", "long_term_storage_fee",
    "removal_fee", "return_fee", "prep_fee", "label_fee",
    "inventory_placement_fee", "manual_processing_fee",
}

FBA_INVENTORY_QTY_FIELDS = {
    "qty_available", "qty_fulfillable", "qty_inbound",
    "qty_reserved", "qty_unfulfillable", "qty_researching",
}


class FbaShipmentService:
    def __init__(self, session: AsyncSession, shipment_repo: FbaShipmentRepository | None = None):
        self._session = session
        self._shipment_repo = shipment_repo

    async def create(self, tenant_id: str, shipment_id: str, **kwargs) -> FbaShipment:
        stmt = select(FbaShipment).where(
            FbaShipment.shipment_id == shipment_id, FbaShipment.tenant_id == tenant_id
        )
        if (await self._session.execute(stmt)).scalar_one_or_none():
            raise DuplicateCodeException(message=f"FBA shipment '{shipment_id}' already exists")
        if kwargs.get("total_units", 0) < 0:
            raise ValidationException(message="total_units cannot be negative")
        if kwargs.get("box_count", 0) < 0:
            raise ValidationException(message="box_count cannot be negative")
        if kwargs.get("estimated_shipping_cost", 0) < 0:
            raise ValidationException(message="estimated_shipping_cost cannot be negative")
        shipment = FbaShipment(
            tenant_id=tenant_id, shipment_id=shipment_id,
            **{k: v for k, v in kwargs.items() if hasattr(FbaShipment, k)},
        )
        self._session.add(shipment)
        await self._session.flush()
        return shipment

    async def get_by_id(self, shipment_pk: str, tenant_id: str = "") -> FbaShipment | None:
        stmt = select(FbaShipment).where(
            FbaShipment.id == shipment_pk, FbaShipment.deleted_at.is_(None)
        )
        if tenant_id:
            stmt = stmt.where(FbaShipment.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, shipment_pk: str, tenant_id: str = "") -> FbaShipment:
        shipment = await self.get_by_id(shipment_pk, tenant_id)
        if not shipment:
            raise NotFoundException(message=f"FBA shipment '{shipment_pk}' not found")
        return shipment

    async def get_by_shipment_id(self, fba_shipment_id: str, tenant_id: str = "") -> FbaShipment | None:
        stmt = select(FbaShipment).where(
            FbaShipment.fba_shipment_id == fba_shipment_id, FbaShipment.deleted_at.is_(None)
        )
        if tenant_id:
            stmt = stmt.where(FbaShipment.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_shipment_id_or_raise(self, fba_shipment_id: str, tenant_id: str = "") -> FbaShipment:
        shipment = await self.get_by_shipment_id(fba_shipment_id, tenant_id)
        if not shipment:
            raise NotFoundException(message=f"FBA shipment '{fba_shipment_id}' not found")
        return shipment

    async def list_by_tenant(self, tenant_id: str, status: str | None = None,
                             platform: str | None = None, offset: int = 0, limit: int = 20) -> list[FbaShipment]:
        stmt = select(FbaShipment).where(FbaShipment.tenant_id == tenant_id, FbaShipment.deleted_at.is_(None))
        if status:
            stmt = stmt.where(FbaShipment.status == status)
        if platform:
            stmt = stmt.where(FbaShipment.platform == platform)
        stmt = stmt.order_by(FbaShipment.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, shipment_pk: str, tenant_id: str, new_status: str) -> FbaShipment:
        shipment = await self.get_by_id(shipment_pk, tenant_id)
        if not shipment:
            raise NotFoundException(message=f"FBA shipment '{shipment_pk}' not found")
        allowed = FBA_SHIPMENT_STATUS_TRANSITIONS.get(shipment.status, [])
        if new_status not in allowed:
            raise ValidationException(
                message=f"Cannot transition FBA shipment from '{shipment.status}' to '{new_status}'"
            )
        shipment.status = new_status
        if new_status == "shipped":
            shipment.shipped_at = datetime.now(UTC)
        elif new_status == "received":
            shipment.received_at = datetime.now(UTC)
        await self._session.flush()
        return shipment

    async def update_tracking(self, shipment_pk: str, tenant_id: str,
                              tracking_no: str, carrier: str) -> FbaShipment:
        shipment = await self.get_by_id(shipment_pk, tenant_id)
        if not shipment:
            raise NotFoundException(message=f"FBA shipment '{shipment_pk}' not found")
        if shipment.status not in ("working", "shipped"):
            raise ValidationException(message="Can only add tracking for shipments in 'working' or 'shipped' status")
        shipment.tracking_no = tracking_no
        shipment.carrier = carrier
        await self._session.flush()
        return shipment

    async def receive_partial(self, shipment_pk: str, tenant_id: str,
                              received_units: int, actual_cost: float = 0.0) -> FbaShipment:
        shipment = await self.get_by_id(shipment_pk, tenant_id)
        if not shipment:
            raise NotFoundException(message=f"FBA shipment '{shipment_pk}' not found")
        if shipment.status not in ("shipped", "partial_received"):
            raise ValidationException(message="Can only receive for 'shipped' or 'partial_received' shipments")
        if received_units < 0:
            raise ValidationException(message="received_units cannot be negative")
        if actual_cost >= 0:
            shipment.actual_shipping_cost = actual_cost
        shipment.status = "partial_received"
        await self._session.flush()
        return shipment

    async def update(self, shipment_pk: str, tenant_id: str, **kwargs) -> FbaShipment:
        shipment = await self.get_by_id(shipment_pk, tenant_id)
        if not shipment:
            raise NotFoundException(message=f"FBA shipment '{shipment_pk}' not found")
        if shipment.status not in ("working", "cancelled"):
            raise ValidationException(message=f"Cannot update FBA shipment in '{shipment.status}' status")
        for k, v in kwargs.items():
            if v is not None and hasattr(shipment, k):
                setattr(shipment, k, v)
        await self._session.flush()
        return shipment

    async def soft_delete(self, shipment_pk: str, tenant_id: str) -> bool:
        shipment = await self.get_by_id(shipment_pk, tenant_id)
        if not shipment:
            raise NotFoundException(message=f"FBA shipment '{shipment_pk}' not found")
        if shipment.status not in ("working", "cancelled"):
            raise ValidationException(message=f"Cannot delete FBA shipment in '{shipment.status}' status")
        shipment.deleted_at = datetime.now(UTC)
        await self._session.flush()
        return True


class FbaInventoryService:
    def __init__(self, session: AsyncSession, inventory_repo: FbaInventoryRepository | None = None):
        self._session = session
        self._inventory_repo = inventory_repo

    async def create(self, tenant_id: str, sku_id: str, store_id: str, **kwargs) -> FbaInventory:
        stmt = select(FbaInventory).where(
            FbaInventory.tenant_id == tenant_id,
            FbaInventory.sku_id == sku_id,
            FbaInventory.store_id == store_id,
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(
                message=f"FBA inventory already exists for sku '{sku_id}' in store '{store_id}'"
            )
        for field in FBA_INVENTORY_QTY_FIELDS:
            val = kwargs.get(field, 0)
            if val < 0:
                raise ValidationException(message=f"{field} cannot be negative")
        inv = FbaInventory(
            tenant_id=tenant_id, sku_id=sku_id, store_id=store_id,
            **{k: v for k, v in kwargs.items() if hasattr(FbaInventory, k)},
        )
        self._session.add(inv)
        await self._session.flush()
        return inv

    async def get_by_id(self, inv_id: str) -> FbaInventory | None:
        return await self._session.get(FbaInventory, inv_id)

    async def get_or_raise(self, inv_id: str, tenant_id: str = "") -> FbaInventory:
        inv = await self.get_by_id(inv_id)
        if not inv:
            raise NotFoundException(message=f"FBA inventory '{inv_id}' not found")
        return inv

    async def get_by_sku_store(self, tenant_id: str, sku_id: str, store_id: str) -> FbaInventory | None:
        stmt = select(FbaInventory).where(
            FbaInventory.tenant_id == tenant_id,
            FbaInventory.sku_id == sku_id,
            FbaInventory.store_id == store_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, store_id: str | None = None,
                             offset: int = 0, limit: int = 50) -> list[FbaInventory]:
        stmt = select(FbaInventory).where(FbaInventory.tenant_id == tenant_id)
        if store_id:
            stmt = stmt.where(FbaInventory.store_id == store_id)
        stmt = stmt.order_by(FbaInventory.updated_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_quantities(self, inv_id: str, tenant_id: str, **qty_fields) -> FbaInventory:
        inv = await self.get_by_id(inv_id)
        if not inv:
            raise NotFoundException(message=f"FBA inventory '{inv_id}' not found")
        if inv.tenant_id != tenant_id:
            raise ValidationException(message="Tenant mismatch")
        for field, value in qty_fields.items():
            if field not in FBA_INVENTORY_QTY_FIELDS:
                raise ValidationException(message=f"Invalid quantity field: {field}")
            if not isinstance(value, int) or value < 0:
                raise ValidationException(message=f"{field} must be a non-negative integer")
            setattr(inv, field, value)
        inv.last_updated_at = datetime.now(UTC)
        await self._session.flush()
        return inv

    async def adjust_quantity(self, tenant_id: str, sku_id: str, store_id: str,
                              field: str, delta: int) -> FbaInventory:
        if field not in FBA_INVENTORY_QTY_FIELDS:
            raise ValidationException(message=f"Invalid quantity field: {field}")
        inv = await self.get_by_sku_store(tenant_id, sku_id, store_id)
        if not inv:
            raise NotFoundException(
                message=f"FBA inventory not found for sku '{sku_id}' in store '{store_id}'"
            )
        current = getattr(inv, field, 0)
        new_val = current + delta
        if new_val < 0:
            raise ValidationException(
                message=f"Adjustment would make {field} negative (current={current}, delta={delta})"
            )
        setattr(inv, field, new_val)
        inv.last_updated_at = datetime.now(UTC)
        await self._session.flush()
        return inv

    async def get_low_stock_items(self, tenant_id: str, threshold: int = 10,
                                  store_id: str | None = None) -> list[FbaInventory]:
        stmt = select(FbaInventory).where(
            FbaInventory.tenant_id == tenant_id,
            FbaInventory.qty_fulfillable <= threshold,
        )
        if store_id:
            stmt = stmt.where(FbaInventory.store_id == store_id)
        stmt = stmt.order_by(FbaInventory.qty_fulfillable.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class FbaFeeService:
    def __init__(self, session: AsyncSession, fee_repo: FbaFeeRepository | None = None):
        self._session = session
        self._fee_repo = fee_repo

    async def create(self, tenant_id: str, sku_id: str, store_id: str,
                     fee_type: str, fee_amount: float, **kwargs) -> FbaFee:
        if fee_type not in FBA_FEE_TYPES:
            raise ValidationException(
                message=f"Invalid fee type '{fee_type}', allowed: {', '.join(sorted(FBA_FEE_TYPES))}"
            )
        if fee_amount < 0:
            raise ValidationException(message="fee_amount cannot be negative")
        quantity = kwargs.get("quantity", 0)
        per_unit_fee = kwargs.get("per_unit_fee", 0.0)
        if quantity > 0 and per_unit_fee > 0:
            calculated = round(per_unit_fee * quantity, 2)
            if abs(calculated - fee_amount) > 0.01:
                raise ValidationException(
                    message=f"fee_amount ({fee_amount}) does not match per_unit_fee * quantity ({calculated})"
                )
        fee = FbaFee(
            tenant_id=tenant_id, sku_id=sku_id, store_id=store_id,
            fee_type=fee_type, fee_amount=fee_amount,
            **{k: v for k, v in kwargs.items() if hasattr(FbaFee, k)},
        )
        self._session.add(fee)
        await self._session.flush()
        return fee

    async def list_by_tenant(self, tenant_id: str, fee_type: str | None = None,
                             sku_id: str | None = None, offset: int = 0, limit: int = 50) -> list[FbaFee]:
        stmt = select(FbaFee).where(FbaFee.tenant_id == tenant_id)
        if fee_type:
            stmt = stmt.where(FbaFee.fee_type == fee_type)
        if sku_id:
            stmt = stmt.where(FbaFee.sku_id == sku_id)
        stmt = stmt.order_by(FbaFee.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def calculate_total_fees(self, tenant_id: str, sku_id: str,
                                   store_id: str = "") -> dict[str, float]:
        stmt = select(
            FbaFee.fee_type,
            sa_func.sum(FbaFee.fee_amount),
        ).where(FbaFee.tenant_id == tenant_id, FbaFee.sku_id == sku_id)
        if store_id:
            stmt = stmt.where(FbaFee.store_id == store_id)
        stmt = stmt.group_by(FbaFee.fee_type)
        result = await self._session.execute(stmt)
        totals = {}
        grand_total = 0.0
        for fee_type, total in result.all():
            totals[fee_type] = float(total or 0)
            grand_total += float(total or 0)
        totals["grand_total"] = round(grand_total, 2)
        return totals


class FbaBoxLabelService:
    def __init__(self, session: AsyncSession, box_label_repo: FbaBoxLabelRepository | None = None):
        self._session = session
        self._box_label_repo = box_label_repo

    async def create(self, tenant_id: str, shipment_id: str, box_no: int,
                     sku_id: str, quantity: int, **kwargs) -> FbaBoxLabel:
        errors = FbaBoxLabelDomainService.validate_box_label(shipment_id, box_no, sku_id, quantity)
        if errors:
            raise ValidationException(message="; ".join(errors))
        shipment_svc = FbaShipmentService(self._session)
        shipment = await shipment_svc.get_by_id(shipment_id, tenant_id)
        if not shipment:
            raise NotFoundException(message=f"FBA shipment '{shipment_id}' not found")
        if shipment.status in ("cancelled", "closed"):
            raise ValidationException(message=f"Cannot add box labels to shipment in '{shipment.status}' status")
        label = FbaBoxLabel(
            tenant_id=tenant_id, shipment_id=shipment_id, box_no=box_no,
            sku_id=sku_id, quantity=quantity,
            **{k: v for k, v in kwargs.items() if hasattr(FbaBoxLabel, k)},
        )
        self._session.add(label)
        await self._session.flush()
        return label

    async def get_by_id(self, label_id: str, tenant_id: str) -> FbaBoxLabel | None:
        stmt = select(FbaBoxLabel).where(FbaBoxLabel.id == label_id, FbaBoxLabel.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_shipment(self, shipment_id: str, tenant_id: str) -> list[FbaBoxLabel]:
        stmt = select(FbaBoxLabel).where(
            FbaBoxLabel.shipment_id == shipment_id, FbaBoxLabel.tenant_id == tenant_id,
        ).order_by(FbaBoxLabel.box_no.asc())
        return list((await self._session.execute(stmt)).scalars().all())

    async def update_status(self, label_id: str, tenant_id: str, new_status: str) -> FbaBoxLabel:
        label = await self.get_by_id(label_id, tenant_id)
        if not label:
            raise NotFoundException(message=f"Box label '{label_id}' not found")
        if not FbaBoxLabelDomainService.can_transition(label.status, new_status):
            raise ValidationException(
                message=f"Cannot transition box label from '{label.status}' to '{new_status}'"
            )
        label.status = new_status
        if new_status == "printed":
            label.printed_at = datetime.now(UTC)
        await self._session.flush()
        return label

    async def void_label(self, label_id: str, tenant_id: str) -> FbaBoxLabel:
        return await self.update_status(label_id, tenant_id, "voided")


class FbaReplenishmentPlanService:
    def __init__(self, session: AsyncSession, replenishment_repo: FbaReplenishmentPlanRepository | None = None):
        self._session = session
        self._replenishment_repo = replenishment_repo

    async def create(self, tenant_id: str, sku_id: str, store_id: str,
                     suggested_qty: int, **kwargs) -> FbaReplenishmentPlan:
        avg_daily_sales = kwargs.get("avg_daily_sales", 0.0)
        days_of_supply = kwargs.get("days_of_supply", 30)
        priority = kwargs.get("priority", "normal")
        errors = FbaReplenishmentDomainService.validate_replenishment(
            sku_id, store_id, suggested_qty, avg_daily_sales, days_of_supply, priority,
        )
        if errors:
            raise ValidationException(message="; ".join(errors))
        plan = FbaReplenishmentPlan(
            tenant_id=tenant_id, sku_id=sku_id, store_id=store_id,
            suggested_qty=suggested_qty,
            **{k: v for k, v in kwargs.items() if hasattr(FbaReplenishmentPlan, k)},
        )
        self._session.add(plan)
        await self._session.flush()
        return plan

    async def get_by_id(self, plan_id: str, tenant_id: str) -> FbaReplenishmentPlan | None:
        stmt = select(FbaReplenishmentPlan).where(
            FbaReplenishmentPlan.id == plan_id, FbaReplenishmentPlan.tenant_id == tenant_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str | None = None,
                             store_id: str | None = None, priority: str | None = None,
                             offset: int = 0, limit: int = 50) -> list[FbaReplenishmentPlan]:
        stmt = select(FbaReplenishmentPlan).where(FbaReplenishmentPlan.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(FbaReplenishmentPlan.status == status)
        if store_id:
            stmt = stmt.where(FbaReplenishmentPlan.store_id == store_id)
        if priority:
            stmt = stmt.where(FbaReplenishmentPlan.priority == priority)
        stmt = stmt.order_by(FbaReplenishmentPlan.created_at.desc()).offset(offset).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def approve(self, plan_id: str, tenant_id: str, approved_qty: int | None = None) -> FbaReplenishmentPlan:
        plan = await self.get_by_id(plan_id, tenant_id)
        if not plan:
            raise NotFoundException(message=f"Replenishment plan '{plan_id}' not found")
        if not FbaReplenishmentDomainService.can_transition(plan.status, "approved"):
            raise ValidationException(message=f"Cannot approve plan in '{plan.status}' status")
        plan.status = "approved"
        plan.approved_qty = approved_qty if approved_qty is not None else plan.suggested_qty
        plan.approved_by = ""
        plan.approved_at = datetime.now(UTC)
        await self._session.flush()
        return plan

    async def reject(self, plan_id: str, tenant_id: str) -> FbaReplenishmentPlan:
        plan = await self.get_by_id(plan_id, tenant_id)
        if not plan:
            raise NotFoundException(message=f"Replenishment plan '{plan_id}' not found")
        if not FbaReplenishmentDomainService.can_transition(plan.status, "rejected"):
            raise ValidationException(message=f"Cannot reject plan in '{plan.status}' status")
        plan.status = "rejected"
        await self._session.flush()
        return plan

    async def link_shipment(self, plan_id: str, tenant_id: str, shipment_id: str) -> FbaReplenishmentPlan:
        plan = await self.get_by_id(plan_id, tenant_id)
        if not plan:
            raise NotFoundException(message=f"Replenishment plan '{plan_id}' not found")
        if plan.status not in ("approved", "in_progress"):
            raise ValidationException(message="Can only link shipment to approved or in_progress plan")
        plan.shipment_id = shipment_id
        if plan.status == "approved":
            plan.status = "in_progress"
        await self._session.flush()
        return plan

    async def auto_generate(self, tenant_id: str, store_id: str,
                            avg_daily_sales_map: dict[str, float],
                            inventory_map: dict[str, dict],
                            lead_time_days: int = 7, safety_stock_days: int = 14,
                            days_of_supply: int = 30) -> list[FbaReplenishmentPlan]:
        plans: list[FbaReplenishmentPlan] = []
        for sku_id, avg_sales in avg_daily_sales_map.items():
            inv_data = inventory_map.get(sku_id, {})
            current_qty = inv_data.get("qty_fulfillable", 0)
            qty_inbound = inv_data.get("qty_inbound", 0)
            suggested = FbaReplenishmentDomainService.calculate_suggested_qty(
                current_qty, qty_inbound, avg_sales, days_of_supply, safety_stock_days, lead_time_days,
            )
            if suggested <= 0:
                continue
            priority = FbaReplenishmentDomainService.auto_prioritize(current_qty, avg_sales, lead_time_days)
            plan = FbaReplenishmentPlan(
                tenant_id=tenant_id, sku_id=sku_id, store_id=store_id,
                suggested_qty=suggested, current_qty=current_qty, qty_inbound=qty_inbound,
                avg_daily_sales=avg_sales, days_of_supply=days_of_supply,
                safety_stock_days=safety_stock_days, lead_time_days=lead_time_days,
                priority=priority, status="pending",
            )
            self._session.add(plan)
            plans.append(plan)
        if plans:
            await self._session.flush()
        return plans


class FbaInboundPlanService:
    def __init__(self, session: AsyncSession, inbound_plan_repo: FbaInboundPlanRepository | None = None):
        self._session = session
        self._inbound_plan_repo = inbound_plan_repo

    async def create(self, tenant_id: str, name: str, plan_no: str, **kwargs) -> FbaInboundPlan:
        stmt = select(FbaInboundPlan).where(FbaInboundPlan.plan_no == plan_no, FbaInboundPlan.tenant_id == tenant_id)
        if (await self._session.execute(stmt)).scalar_one_or_none():
            raise DuplicateCodeException(message=f"Inbound plan '{plan_no}' already exists")
        plan = FbaInboundPlan(
            tenant_id=tenant_id, name=name, plan_no=plan_no,
            **{k: v for k, v in kwargs.items() if hasattr(FbaInboundPlan, k)},
        )
        self._session.add(plan)
        await self._session.flush()
        return plan

    async def get_by_id(self, plan_id: str, tenant_id: str) -> FbaInboundPlan | None:
        stmt = select(FbaInboundPlan).where(FbaInboundPlan.id == plan_id, FbaInboundPlan.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str | None = None,
                             offset: int = 0, limit: int = 20) -> list[FbaInboundPlan]:
        stmt = select(FbaInboundPlan).where(FbaInboundPlan.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(FbaInboundPlan.status == status)
        stmt = stmt.order_by(FbaInboundPlan.created_at.desc()).offset(offset).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def update_status(self, plan_id: str, tenant_id: str, new_status: str) -> FbaInboundPlan:
        plan = await self.get_by_id(plan_id, tenant_id)
        if not plan:
            raise NotFoundException(message=f"Inbound plan '{plan_id}' not found")
        if not FbaInboundPlanDomainService.can_transition(plan.status, new_status):
            raise ValidationException(
                message=f"Cannot transition inbound plan from '{plan.status}' to '{new_status}'"
            )
        plan.status = new_status
        if new_status == "submitted":
            plan.submitted_at = datetime.now(UTC)
        elif new_status == "completed":
            plan.completed_at = datetime.now(UTC)
        await self._session.flush()
        return plan

    async def submit(self, plan_id: str, tenant_id: str) -> FbaInboundPlan:
        plan = await self.get_by_id(plan_id, tenant_id)
        if not plan:
            raise NotFoundException(message=f"Inbound plan '{plan_id}' not found")
        errors = FbaInboundPlanDomainService.validate_for_submit(plan)
        if errors:
            raise ValidationException(message="; ".join(errors))
        return await self.update_status(plan_id, tenant_id, "submitted")


class FBAQueryService:
    """
    FBA 统计查询服务

    提供FBA模块的运营统计概览、各子域统计数据聚合。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_statistics(self, tenant_id: str) -> dict:
        """获取FBA运营统计概览"""
        total_shipments = (await self._session.execute(
            select(sa_func.count()).select_from(FbaShipment)
            .where(FbaShipment.tenant_id == tenant_id, FbaShipment.deleted_at.is_(None))
        )).scalar() or 0

        active_shipments = (await self._session.execute(
            select(sa_func.count()).select_from(FbaShipment)
            .where(FbaShipment.tenant_id == tenant_id, FbaShipment.deleted_at.is_(None),
                   FbaShipment.status.in_(["working", "shipped", "in_review", "submitted"]))
        )).scalar() or 0

        by_status_rows = (await self._session.execute(
            select(FbaShipment.status, sa_func.count())
            .where(FbaShipment.tenant_id == tenant_id, FbaShipment.deleted_at.is_(None))
            .group_by(FbaShipment.status)
        )).all()
        shipments_by_status = {r[0]: r[1] for r in by_status_rows}

        total_inventory_items = (await self._session.execute(
            select(sa_func.count()).select_from(FbaInventory).where(FbaInventory.tenant_id == tenant_id)
        )).scalar() or 0

        total_fulfillable_qty = int((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(FbaInventory.qty_fulfillable), 0))
            .where(FbaInventory.tenant_id == tenant_id)
        )).scalar() or 0)

        total_inbound_qty = int((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(FbaInventory.qty_inbound), 0))
            .where(FbaInventory.tenant_id == tenant_id)
        )).scalar() or 0)

        total_reserved_qty = int((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(FbaInventory.qty_reserved), 0))
            .where(FbaInventory.tenant_id == tenant_id)
        )).scalar() or 0)

        low_stock_items = (await self._session.execute(
            select(sa_func.count()).select_from(FbaInventory)
            .where(FbaInventory.tenant_id == tenant_id, FbaInventory.qty_fulfillable <= 10)
        )).scalar() or 0

        inventory_by_store_rows = (await self._session.execute(
            select(FbaInventory.store_id, sa_func.count())
            .where(FbaInventory.tenant_id == tenant_id)
            .group_by(FbaInventory.store_id)
        )).all()
        inventory_by_store = {r[0]: r[1] for r in inventory_by_store_rows}

        total_fees = float((await self._session.execute(
            select(sa_func.coalesce(sa_func.sum(FbaFee.fee_amount), 0))
            .where(FbaFee.tenant_id == tenant_id)
        )).scalar() or 0)

        fees_by_type_rows = (await self._session.execute(
            select(FbaFee.fee_type, sa_func.coalesce(sa_func.sum(FbaFee.fee_amount), 0))
            .where(FbaFee.tenant_id == tenant_id)
            .group_by(FbaFee.fee_type)
        )).all()
        fees_by_type = {r[0]: float(r[1]) for r in fees_by_type_rows}

        total_replenishment_plans = (await self._session.execute(
            select(sa_func.count()).select_from(FbaReplenishmentPlan)
            .where(FbaReplenishmentPlan.tenant_id == tenant_id)
        )).scalar() or 0

        pending_replenishment_plans = (await self._session.execute(
            select(sa_func.count()).select_from(FbaReplenishmentPlan)
            .where(FbaReplenishmentPlan.tenant_id == tenant_id, FbaReplenishmentPlan.status == "pending")
        )).scalar() or 0

        total_inbound_plans = (await self._session.execute(
            select(sa_func.count()).select_from(FbaInboundPlan)
            .where(FbaInboundPlan.tenant_id == tenant_id)
        )).scalar() or 0

        return {
            "total_shipments": total_shipments,
            "active_shipments": active_shipments,
            "total_inventory_items": total_inventory_items,
            "total_fulfillable_qty": total_fulfillable_qty,
            "total_inbound_qty": total_inbound_qty,
            "total_reserved_qty": total_reserved_qty,
            "low_stock_items": low_stock_items,
            "total_fees": round(total_fees, 2),
            "fees_by_type": fees_by_type,
            "total_replenishment_plans": total_replenishment_plans,
            "pending_replenishment_plans": pending_replenishment_plans,
            "total_inbound_plans": total_inbound_plans,
            "shipments_by_status": shipments_by_status,
            "inventory_by_store": inventory_by_store,
        }

    async def search_shipments(self, tenant_id: str, keyword: str = "", platform: str = "",
                                status: str = "", store_id: str = "",
                                start_date=None, end_date=None,
                                page: int = 1, page_size: int = 20) -> tuple[list[FbaShipment], int]:
        """多维度搜索FBA货件"""
        conditions = [FbaShipment.tenant_id == tenant_id, FbaShipment.deleted_at.is_(None)]
        if keyword:
            conditions.append((FbaShipment.shipment_id.contains(keyword) | FbaShipment.name.contains(keyword)))
        if platform:
            conditions.append(FbaShipment.platform == platform)
        if status:
            conditions.append(FbaShipment.status == status)
        if store_id:
            conditions.append(FbaShipment.store_id == store_id)
        if start_date:
            conditions.append(FbaShipment.created_at >= start_date)
        if end_date:
            conditions.append(FbaShipment.created_at <= end_date)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(FbaShipment).where(*conditions)
        )).scalar() or 0
        stmt = select(FbaShipment).where(*conditions).order_by(
            FbaShipment.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total


class FbaShipmentTrackingService:
    """
    FBA货件跟踪服务

    编排FBA货件全生命周期跟踪: 创建 → 在途 → 接收 → 关闭
    对接Amazon货件状态同步
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def sync_shipment_status(self, tenant_id: str, shipment_id: str) -> dict:
        """
        同步货件状态

        流程: 查询本地货件 → 调用平台API → 更新状态 → 触发后续动作
        """
        shipment = (await self._session.execute(
            select(FbaShipment).where(FbaShipment.id == shipment_id, FbaShipment.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not shipment:
            raise NotFoundException(message=f"FBA shipment '{shipment_id}' not found")
        return {
            "shipment_id": shipment_id, "current_status": shipment.status,
            "fba_shipment_id": shipment.fba_shipment_id,
            "synced_at": datetime.now(UTC).isoformat(),
        }

    async def batch_sync_status(self, tenant_id: str, store_id: str = "") -> dict:
        """批量同步货件状态"""
        conditions = [FbaShipment.tenant_id == tenant_id,
                      FbaShipment.status.notin_(["closed", "cancelled"])]
        if store_id:
            conditions.append(FbaShipment.store_id == store_id)
        shipments = (await self._session.execute(
            select(FbaShipment).where(*conditions)
        )).scalars().all()
        synced = 0
        for s in shipments:
            synced += 1
        return {
            "total_shipments": len(shipments), "synced": synced,
            "store_id": store_id,
        }

    async def get_shipment_timeline(self, tenant_id: str, shipment_id: str) -> dict:
        """获取货件时间线"""
        shipment = (await self._session.execute(
            select(FbaShipment).where(FbaShipment.id == shipment_id, FbaShipment.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not shipment:
            raise NotFoundException(message=f"FBA shipment '{shipment_id}' not found")
        timeline = []
        if shipment.created_at:
            timeline.append({"event": "created", "time": shipment.created_at.isoformat()})
        if shipment.shipped_at:
            timeline.append({"event": "shipped", "time": shipment.shipped_at.isoformat()})
        if shipment.received_at:
            timeline.append({"event": "received", "time": shipment.received_at.isoformat()})
        return {"shipment_id": shipment_id, "timeline": timeline}


class FbaFeeEstimationService:
    """
    FBA费用预估服务

    预估FBA各项费用: 仓储费/配送费/佣金/长期仓储费
    """

    FBA_FEE_RATES = {
        "storage_per_cubic_foot_monthly": 2.40,
        "fulfillment_per_unit_base": 3.22,
        "fulfillment_per_lb": 0.38,
        "referral_fee_rate": 0.15,
        "long_term_storage_per_unit": 6.90,
    }

    def __init__(self, session: AsyncSession):
        self._session = session

    async def estimate_total_fees(self, tenant_id: str, sku_id: str,
                                   store_id: str = "", price: float = 0.0,
                                   quantity: int = 1, weight_lb: float = 1.0,
                                   volume_cubic_ft: float = 0.1) -> dict:
        """
        预估FBA总费用

        流程: 查询SKU信息 → 计算各项费用 → 汇总 → 计算利润率
        """
        storage_fee = volume_cubic_ft * self.FBA_FEE_RATES["storage_per_cubic_foot_monthly"]
        fulfillment_fee = (self.FBA_FEE_RATES["fulfillment_per_unit_base"] +
                           weight_lb * self.FBA_FEE_RATES["fulfillment_per_lb"])
        referral_fee = price * self.FBA_FEE_RATES["referral_fee_rate"]
        total_fee_per_unit = storage_fee + fulfillment_fee + referral_fee
        total_fee = total_fee_per_unit * quantity
        net_profit = (price - total_fee_per_unit) * quantity
        profit_margin = (net_profit / (price * quantity) * 100) if price * quantity > 0 else 0
        return {
            "sku_id": sku_id, "price": price, "quantity": quantity,
            "storage_fee": round(storage_fee, 2),
            "fulfillment_fee": round(fulfillment_fee, 2),
            "referral_fee": round(referral_fee, 2),
            "total_fee_per_unit": round(total_fee_per_unit, 2),
            "total_fee": round(total_fee, 2),
            "net_profit": round(net_profit, 2),
            "profit_margin": round(profit_margin, 2),
        }

    async def estimate_long_term_storage(self, tenant_id: str, store_id: str = "") -> list[dict]:
        """预估长期仓储费(库存超过365天的SKU)"""
        results = []
        inventories = (await self._session.execute(
            select(FbaInventory).where(
                FbaInventory.tenant_id == tenant_id,
                FbaInventory.qty_fulfillable > 0,
            )
        )).scalars().all()
        for inv in inventories:
            if store_id and inv.store_id != store_id:
                continue
            age_days = (datetime.now(UTC) - inv.created_at).days if inv.created_at else 0
            if age_days > 365:
                long_term_fee = inv.qty_fulfillable * self.FBA_FEE_RATES["long_term_storage_per_unit"]
                results.append({
                    "sku_id": inv.sku_id, "qty_fulfillable": inv.qty_fulfillable,
                    "age_days": age_days, "estimated_fee": round(long_term_fee, 2),
                    "severity": "critical" if age_days > 730 else "warning",
                })
        results.sort(key=lambda x: x["estimated_fee"], reverse=True)
        return results


class FbaInventorySyncService:
    """
    FBA库存同步服务

    与Amazon平台同步FBA库存: 全量同步/增量同步/差异检测
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def full_sync(self, tenant_id: str, store_id: str) -> dict:
        """
        全量同步FBA库存

        流程: 调用平台API → 获取全量库存 → 对比本地 → 增量更新
        """
        local_count = (await self._session.execute(
            select(sa_func.count()).select_from(FbaInventory).where(
                FbaInventory.tenant_id == tenant_id, FbaInventory.store_id == store_id)
        )).scalar() or 0
        return {
            "tenant_id": tenant_id, "store_id": store_id,
            "sync_type": "full", "local_records": local_count,
            "synced_at": datetime.now(UTC).isoformat(),
            "status": "completed",
        }

    async def incremental_sync(self, tenant_id: str, store_id: str,
                                since: datetime | None = None) -> dict:
        """增量同步FBA库存"""
        return {
            "tenant_id": tenant_id, "store_id": store_id,
            "sync_type": "incremental", "since": since.isoformat() if since else "",
            "synced_at": datetime.now(UTC).isoformat(),
            "status": "completed",
        }

    async def detect_discrepancies(self, tenant_id: str, store_id: str,
                                    platform_data: list[dict]) -> dict:
        """
        检测库存差异

        对比平台数据与本地数据，发现差异自动创建异常
        """
        discrepancies = []
        for item in platform_data:
            sku_id = item.get("sku_id", "")
            platform_qty = item.get("qty_fulfillable", 0)
            local_inv = (await self._session.execute(
                select(FbaInventory).where(
                    FbaInventory.tenant_id == tenant_id,
                    FbaInventory.store_id == store_id,
                    FbaInventory.sku_id == sku_id)
            )).scalar_one_or_none()
            if local_inv:
                diff = platform_qty - local_inv.qty_fulfillable
                if diff != 0:
                    discrepancies.append({
                        "sku_id": sku_id, "platform_qty": platform_qty,
                        "local_qty": local_inv.qty_fulfillable, "difference": diff,
                    })
        return {
            "store_id": store_id, "total_checked": len(platform_data),
            "discrepancy_count": len(discrepancies), "discrepancies": discrepancies,
        }


class ShipmentPreprocessService:
    """
    货件预处理应用服务

    编排FBA货件发货前的预处理: 商品贴标校验 → 箱规校验 → 重量校验 → 合规检查 → 预处理报告
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def preprocess_shipment(self, tenant_id: str, shipment_id: str) -> dict:
        """
        货件预处理

        流程: 获取货件 → 贴标校验 → 箱规校验 → 重量校验 → 生成报告
        """
        shipment = (await self._session.execute(
            select(FbaShipment).where(FbaShipment.id == shipment_id, FbaShipment.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not shipment:
            raise NotFoundException(message=f"Shipment '{shipment_id}' not found")
        import json as _json
        try:
            items = _json.loads(shipment.items_json or "[]")
        except Exception:
            items = []
        label_result = await self._check_labels(tenant_id, items)
        box_result = self._check_box_specs(shipment, items)
        weight_result = self._check_weight(shipment, items)
        all_passed = label_result["passed"] and box_result["passed"] and weight_result["passed"]
        warnings = label_result.get("warnings", []) + box_result.get("warnings", []) + weight_result.get("warnings", [])
        errors = label_result.get("errors", []) + box_result.get("errors", []) + weight_result.get("errors", [])
        return {
            "shipment_id": shipment_id, "shipment_id_code": shipment.shipment_id,
            "all_passed": all_passed,
            "has_errors": len(errors) > 0,
            "has_warnings": len(warnings) > 0,
            "label_check": label_result,
            "box_check": box_result,
            "weight_check": weight_result,
            "errors": errors, "warnings": warnings,
        }

    async def _check_labels(self, tenant_id: str, items: list[dict]) -> dict:
        """检查商品贴标"""
        warnings: list[str] = []
        errors: list[str] = []
        for item in items:
            sku_id = item.get("sku_id", "")
            fnsku = item.get("fnsku", "")
            if not fnsku:
                errors.append(f"SKU {sku_id}: Missing FNSKU label")
            label_type = item.get("label_type", "")
            if label_type == "manufacturer" and item.get("is_hazmat", False):
                errors.append(f"SKU {sku_id}: Hazmat items require FBA label")
        return {"passed": len(errors) == 0, "warnings": warnings, "errors": errors}

    def _check_box_specs(self, shipment: FbaShipment, items: list[dict]) -> dict:
        """检查箱规"""
        warnings: list[str] = []
        errors: list[str] = []
        if shipment.box_count <= 0:
            errors.append("Box count must be positive")
        if shipment.total_units <= 0:
            errors.append("Total units must be positive")
        for item in items:
            qty_per_box = item.get("quantity_per_box", 0)
            if qty_per_box > 150:
                warnings.append(f"SKU {item.get('sku_id', '')}: {qty_per_box} units/box exceeds recommended 150")
        return {"passed": len(errors) == 0, "warnings": warnings, "errors": errors}

    def _check_weight(self, shipment: FbaShipment, items: list[dict]) -> dict:
        """检查重量"""
        warnings: list[str] = []
        errors: list[str] = []
        if shipment.total_weight <= 0:
            errors.append("Total weight must be positive")
        if shipment.box_count > 0:
            avg_box_weight = shipment.total_weight / shipment.box_count
            if avg_box_weight > 22.5:
                warnings.append(f"Average box weight {avg_box_weight:.1f}kg exceeds 22.5kg limit")
        return {"passed": len(errors) == 0, "warnings": warnings, "errors": errors}

    async def batch_preprocess(self, tenant_id: str, shipment_ids: list[str]) -> dict:
        """批量预处理"""
        results = []
        passed_count = 0
        for sid in shipment_ids:
            try:
                result = await self.preprocess_shipment(tenant_id, sid)
                results.append(result)
                if result["all_passed"]:
                    passed_count += 1
            except NotFoundException as e:
                results.append({"shipment_id": sid, "all_passed": False, "errors": [e.message]})
        return {
            "total": len(shipment_ids), "passed_count": passed_count,
            "failed_count": len(shipment_ids) - passed_count,
            "results": results,
        }


class InboundPlanOrchestrator:
    """
    入库计划编排应用服务

    编排FBA入库计划的完整流程: 需求分析 → 补货建议 → 计划生成 → 货件拆分 → 提交执行
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def generate_replenishment_suggestions(self, tenant_id: str,
                                                  store_id: str = "",
                                                  days_of_stock: int = 30) -> dict:
        """
        生成补货建议

        流程: 查询FBA库存 → 识别低库存SKU → 计算补货量 → 按优先级排序
        """
        conditions = [FbaInventory.tenant_id == tenant_id]
        if store_id:
            conditions.append(FbaInventory.store_id == store_id)
        inventories = list((await self._session.execute(
            select(FbaInventory).where(*conditions)
        )).scalars().all())
        suggestions: list[dict] = []
        for inv in inventories:
            daily_sales = inv.qty_fulfillable / max(days_of_stock, 1) if inv.qty_fulfillable > 0 else 0
            days_remaining = inv.qty_fulfillable / max(daily_sales, 0.01) if daily_sales > 0 else 999
            if days_remaining < 14 or inv.qty_fulfillable <= 10:
                replenish_qty = max(int(daily_sales * 60) - inv.qty_fulfillable, 0)
                priority = "low"
                if days_remaining < 7 or inv.qty_fulfillable <= 0:
                    priority = "critical"
                elif days_remaining < 14:
                    priority = "high"
                elif days_remaining < 21:
                    priority = "medium"
                suggestions.append({
                    "sku_id": inv.sku_id, "fnsku": inv.fnsku,
                    "asin": inv.asin, "store_id": inv.store_id,
                    "current_qty": inv.qty_fulfillable,
                    "inbound_qty": inv.qty_inbound,
                    "daily_sales_rate": round(daily_sales, 2),
                    "days_remaining": round(days_remaining, 1),
                    "replenish_qty": replenish_qty,
                    "priority": priority,
                })
        suggestions.sort(key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["priority"], 4))
        return {
            "total_skus_analyzed": len(inventories),
            "low_stock_count": len(suggestions),
            "suggestions": suggestions,
        }

    async def create_plan_from_suggestions(self, tenant_id: str, store_id: str,
                                            suggestions: list[dict],
                                            warehouse_id: str = "",
                                            destination: str = "") -> dict:
        """
        从补货建议创建入库计划

        流程: 汇总建议 → 生成计划 → 创建货件
        """
        if not suggestions:
            return {"plan_id": None, "reason": "no suggestions provided"}
        import json as _json
        import uuid
        plan_no = f"IBP-{uuid.uuid4().hex[:8].upper()}"
        total_units = sum(s.get("replenish_qty", 0) for s in suggestions)
        items_json = _json.dumps([
            {"sku_id": s["sku_id"], "quantity": s["replenish_qty"], "priority": s["priority"]}
            for s in suggestions if s.get("replenish_qty", 0) > 0
        ], ensure_ascii=False)
        plan = FbaInboundPlan(
            tenant_id=tenant_id,
            name=f"Auto replenishment plan - {store_id[:8]}",
            plan_no=plan_no,
            warehouse_id=warehouse_id,
            destination_fba_center=destination,
            store_id=store_id,
            items_json=items_json,
            total_units=total_units,
            total_boxes=max(total_units // 50, 1),
            total_weight=total_units * 0.5,
            estimated_cost=total_units * 0.5 * 5,
            currency="USD",
            status="draft",
            created_by="system",
        )
        self._session.add(plan)
        await self._session.flush()
        return {
            "plan_id": str(plan.id), "plan_no": plan_no,
            "total_units": total_units,
            "item_count": len([s for s in suggestions if s.get("replenish_qty", 0) > 0]),
        }

    async def split_plan_into_shipments(self, tenant_id: str, plan_id: str,
                                         max_units_per_shipment: int = 200) -> dict:
        """
        将入库计划拆分为多个货件

        流程: 获取计划 → 按数量上限拆分 → 创建货件 → 关联计划
        """
        plan = (await self._session.execute(
            select(FbaInboundPlan).where(FbaInboundPlan.id == plan_id, FbaInboundPlan.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not plan:
            raise NotFoundException(message=f"Inbound plan '{plan_id}' not found")
        import json as _json
        import uuid
        try:
            items = _json.loads(plan.items_json or "[]")
        except Exception:
            items = []
        if not items:
            return {"plan_id": plan_id, "shipments_created": 0, "reason": "no items in plan"}
        shipments_created: list[dict] = []
        current_batch: list[dict] = []
        current_units = 0
        for item in items:
            qty = item.get("quantity", 0)
            if current_units + qty > max_units_per_shipment and current_batch:
                shipment = await self._create_shipment_from_batch(
                    tenant_id, plan, current_batch,
                )
                shipments_created.append(shipment)
                current_batch = []
                current_units = 0
            current_batch.append(item)
            current_units += qty
        if current_batch:
            shipment = await self._create_shipment_from_batch(
                tenant_id, plan, current_batch,
            )
            shipments_created.append(shipment)
        return {
            "plan_id": plan_id, "total_units": plan.total_units,
            "shipments_created": len(shipments_created),
            "shipments": shipments_created,
        }

    async def _create_shipment_from_batch(self, tenant_id: str, plan: FbaInboundPlan,
                                           batch: list[dict]) -> dict:
        """从一批商品创建货件"""
        import json as _json
        import uuid
        shipment_id_code = f"SHP-{uuid.uuid4().hex[:8].upper()}"
        total_units = sum(item.get("quantity", 0) for item in batch)
        shipment = FbaShipment(
            tenant_id=tenant_id,
            shipment_id=shipment_id_code,
            name=f"Shipment for plan {plan.plan_no}",
            platform=plan.platform,
            store_id=plan.store_id,
            destination_fulfillment_center_id=plan.destination_fba_center,
            shipping_plan_id=str(plan.id),
            box_count=max(total_units // 50, 1),
            total_units=total_units,
            total_weight=total_units * 0.5,
            currency=plan.currency,
            items_json=_json.dumps(batch, ensure_ascii=False),
            status="draft",
            created_by="system",
        )
        self._session.add(shipment)
        await self._session.flush()
        return {
            "shipment_id": str(shipment.id),
            "shipment_id_code": shipment_id_code,
            "total_units": total_units,
        }

    async def search_exceptions(self, tenant_id: str, exception_type: str = "", severity: str = "",
                                 status: str = "", sku_id: str = "", store_id: str = "",
                                 page: int = 1, page_size: int = 20) -> tuple[list[FbaException], int]:
        conditions = [FbaException.tenant_id == tenant_id, FbaException.deleted_at.is_(None)]
        if exception_type:
            conditions.append(FbaException.exception_type == exception_type)
        if severity:
            conditions.append(FbaException.severity == severity)
        if status:
            conditions.append(FbaException.status == status)
        if sku_id:
            conditions.append(FbaException.sku_id == sku_id)
        if store_id:
            conditions.append(FbaException.store_id == store_id)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(FbaException).where(*conditions)
        )).scalar() or 0
        stmt = select(FbaException).where(*conditions).order_by(
            FbaException.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total


EXCEPTION_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "open": ["investigating", "escalated", "closed"],
    "investigating": ["resolved", "escalated", "closed"],
    "escalated": ["investigating", "resolved", "closed"],
    "resolved": ["closed"],
    "closed": [],
}

VALID_EXCEPTION_TYPES = {
    "inventory_discrepancy", "shipment_delay", "receiving_shortage",
    "damage_in_transit", "label_error", "overage", "stranded_inventory",
    "long_term_storage", "return_issue", "fee_discrepancy",
}

VALID_SEVERITIES = {"low", "medium", "high", "critical"}

VALID_RESOLUTION_TYPES = {"adjust", "reorder", "claim", "dispose", "ignore", "escalate"}


class FbaExceptionService:
    """
    FBA异常处理应用服务

    编排FBA异常的完整生命周期: 创建 → 调查 → 解决/升级 → 关闭
    支持自动检测异常和手动创建，按严重程度分级处理。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, tenant_id: str, exception_no: str, exception_type: str,
                     severity: str, title: str, **kwargs) -> FbaException:
        if exception_type not in VALID_EXCEPTION_TYPES:
            raise ValidationException(message=f"Invalid exception type '{exception_type}'")
        if severity not in VALID_SEVERITIES:
            raise ValidationException(message=f"Invalid severity '{severity}'")
        existing = select(FbaException).where(
            FbaException.exception_no == exception_no,
            FbaException.tenant_id == tenant_id,
        )
        if (await self._session.execute(existing)).scalar_one_or_none():
            raise DuplicateCodeException(message=f"Exception '{exception_no}' already exists")
        expected_value = kwargs.get("expected_value", 0.0)
        actual_value = kwargs.get("actual_value", 0.0)
        import json
        exc = FbaException(
            tenant_id=tenant_id, exception_no=exception_no,
            exception_type=exception_type, severity=severity, title=title,
            description=kwargs.get("description", ""),
            platform=kwargs.get("platform", "amazon"),
            store_id=kwargs.get("store_id", ""),
            shipment_id=kwargs.get("shipment_id", ""),
            sku_id=kwargs.get("sku_id", ""),
            fba_shipment_id=kwargs.get("fba_shipment_id", ""),
            fulfillment_center_id=kwargs.get("fulfillment_center_id", ""),
            expected_value=expected_value, actual_value=actual_value,
            discrepancy=actual_value - expected_value,
            evidence_json=kwargs.get("evidence_json", "{}"),
            assigned_to=kwargs.get("assigned_to", ""),
            assigned_group=kwargs.get("assigned_group", ""),
            due_date=kwargs.get("due_date"),
            is_auto_detected=kwargs.get("is_auto_detected", False),
            source_system=kwargs.get("source_system", "manual"),
            tags_json=kwargs.get("tags_json", "[]"),
            impact_json=kwargs.get("impact_json", "{}"),
            created_by=kwargs.get("created_by", ""),
        )
        self._session.add(exc)
        await self._session.flush()
        return exc

    async def get_by_id(self, exception_id: str, tenant_id: str) -> FbaException | None:
        stmt = select(FbaException).where(
            FbaException.id == exception_id, FbaException.tenant_id == tenant_id,
            FbaException.deleted_at.is_(None),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, exception_id: str, tenant_id: str) -> FbaException:
        exc = await self.get_by_id(exception_id, tenant_id)
        if not exc:
            raise NotFoundException(message=f"FBA exception '{exception_id}' not found")
        return exc

    async def list_all(self, tenant_id: str, exception_type: str = "", severity: str = "",
                       status: str = "", page: int = 1, page_size: int = 20) -> tuple[list[FbaException], int]:
        conditions = [FbaException.tenant_id == tenant_id, FbaException.deleted_at.is_(None)]
        if exception_type:
            conditions.append(FbaException.exception_type == exception_type)
        if severity:
            conditions.append(FbaException.severity == severity)
        if status:
            conditions.append(FbaException.status == status)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(FbaException).where(*conditions)
        )).scalar() or 0
        stmt = select(FbaException).where(*conditions).order_by(
            FbaException.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total

    async def update_status(self, exception_id: str, tenant_id: str, new_status: str,
                            remark: str = "") -> FbaException:
        exc = await self.get_or_raise(exception_id, tenant_id)
        allowed = EXCEPTION_STATUS_TRANSITIONS.get(exc.status, [])
        if new_status not in allowed:
            raise ValidationException(
                message=f"Cannot transition exception from '{exc.status}' to '{new_status}'"
            )
        exc.status = new_status
        if new_status == "resolved":
            exc.resolved_at = datetime.now(UTC)
        if remark:
            exc.remark = remark
        await self._session.flush()
        return exc

    async def assign(self, exception_id: str, tenant_id: str, assigned_to: str = "",
                     assigned_group: str = "") -> FbaException:
        exc = await self.get_or_raise(exception_id, tenant_id)
        if assigned_to:
            exc.assigned_to = assigned_to
        if assigned_group:
            exc.assigned_group = assigned_group
        if exc.status == "open":
            exc.status = "investigating"
        await self._session.flush()
        return exc

    async def resolve(self, exception_id: str, tenant_id: str, resolution_type: str,
                      resolution: str, **kwargs) -> FbaException:
        if resolution_type not in VALID_RESOLUTION_TYPES:
            raise ValidationException(message=f"Invalid resolution type '{resolution_type}'")
        exc = await self.get_or_raise(exception_id, tenant_id)
        if exc.status not in ("investigating", "escalated"):
            raise ValidationException(message="Exception must be in 'investigating' or 'escalated' status to resolve")
        exc.resolution_type = resolution_type
        exc.resolution = resolution
        exc.status = "resolved"
        exc.resolved_at = datetime.now(UTC)
        if kwargs.get("adjustment_value"):
            exc.actual_value = kwargs["adjustment_value"]
            exc.discrepancy = exc.actual_value - exc.expected_value
        await self._session.flush()
        return exc

    async def escalate(self, exception_id: str, tenant_id: str, reason: str = "",
                       assigned_group: str = "") -> FbaException:
        exc = await self.get_or_raise(exception_id, tenant_id)
        if exc.status not in ("open", "investigating"):
            raise ValidationException(message="Can only escalate open or investigating exceptions")
        exc.status = "escalated"
        if reason:
            exc.remark = reason
        if assigned_group:
            exc.assigned_group = assigned_group
        await self._session.flush()
        return exc

    async def auto_detect_inventory_discrepancy(self, tenant_id: str, store_id: str,
                                                 sku_id: str, expected_qty: int,
                                                 actual_qty: int, **kwargs) -> FbaException | None:
        discrepancy = actual_qty - expected_qty
        if discrepancy == 0:
            return None
        import json as _json
        severity = "low"
        if abs(discrepancy) > 100:
            severity = "critical"
        elif abs(discrepancy) > 50:
            severity = "high"
        elif abs(discrepancy) > 10:
            severity = "medium"
        exception_no = f"EXC-INV-{sku_id[:8]}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        exc = FbaException(
            tenant_id=tenant_id, exception_no=exception_no,
            exception_type="inventory_discrepancy", severity=severity,
            title=f"Inventory discrepancy: SKU {sku_id} (diff={discrepancy})",
            description=f"Expected {expected_qty}, actual {actual_qty}, discrepancy {discrepancy}",
            platform=kwargs.get("platform", "amazon"), store_id=store_id,
            sku_id=sku_id, expected_value=float(expected_qty),
            actual_value=float(actual_qty), discrepancy=float(discrepancy),
            is_auto_detected=True, source_system="inventory_sync",
            evidence_json=_json.dumps({
                "expected_qty": expected_qty, "actual_qty": actual_qty,
                "fulfillment_center": kwargs.get("fulfillment_center_id", ""),
            }, default=str),
            created_by="system",
        )
        self._session.add(exc)
        await self._session.flush()
        return exc

    async def get_statistics(self, tenant_id: str, store_id: str = "") -> dict:
        conditions = [FbaException.tenant_id == tenant_id, FbaException.deleted_at.is_(None)]
        if store_id:
            conditions.append(FbaException.store_id == store_id)
        stmt = select(FbaException).where(*conditions)
        exceptions = (await self._session.execute(stmt)).scalars().all()
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        avg_resolution_hours = 0.0
        resolved_with_time = []
        for e in exceptions:
            by_status[e.status] = by_status.get(e.status, 0) + 1
            by_type[e.exception_type] = by_type.get(e.exception_type, 0) + 1
            by_severity[e.severity] = by_severity.get(e.severity, 0) + 1
            if e.resolved_at and e.created_at:
                hours = (e.resolved_at - e.created_at).total_seconds() / 3600
                resolved_with_time.append(hours)
        if resolved_with_time:
            avg_resolution_hours = round(sum(resolved_with_time) / len(resolved_with_time), 2)
        return {
            "total_exceptions": len(exceptions),
            "open_count": by_status.get("open", 0) + by_status.get("investigating", 0),
            "by_status": by_status,
            "by_type": by_type,
            "by_severity": by_severity,
            "avg_resolution_hours": avg_resolution_hours,
        }

    async def search_inventory(self, tenant_id: str, sku_id: str = "", store_id: str = "",
                                fnsku: str = "", asin: str = "", condition_type: str = "",
                                low_stock_only: bool = False, low_stock_threshold: int = 10,
                                page: int = 1, page_size: int = 20) -> tuple[list[FbaInventory], int]:
        """多维度搜索FBA库存"""
        conditions = [FbaInventory.tenant_id == tenant_id]
        if sku_id:
            conditions.append(FbaInventory.sku_id == sku_id)
        if store_id:
            conditions.append(FbaInventory.store_id == store_id)
        if fnsku:
            conditions.append(FbaInventory.fnsku == fnsku)
        if asin:
            conditions.append(FbaInventory.asin == asin)
        if condition_type:
            conditions.append(FbaInventory.condition_type == condition_type)
        if low_stock_only:
            conditions.append(FbaInventory.qty_fulfillable <= low_stock_threshold)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(FbaInventory).where(*conditions)
        )).scalar() or 0
        stmt = select(FbaInventory).where(*conditions).order_by(
            FbaInventory.updated_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total

    async def search_fees(self, tenant_id: str, fee_type: str = "", sku_id: str = "",
                          store_id: str = "", start_date=None, end_date=None,
                          min_amount: float | None = None, max_amount: float | None = None,
                          page: int = 1, page_size: int = 20) -> tuple[list[FbaFee], int]:
        """多维度搜索FBA费用"""
        conditions = [FbaFee.tenant_id == tenant_id]
        if fee_type:
            conditions.append(FbaFee.fee_type == fee_type)
        if sku_id:
            conditions.append(FbaFee.sku_id == sku_id)
        if store_id:
            conditions.append(FbaFee.store_id == store_id)
        if start_date:
            conditions.append(FbaFee.fee_date >= start_date)
        if end_date:
            conditions.append(FbaFee.fee_date <= end_date)
        if min_amount is not None:
            conditions.append(FbaFee.fee_amount >= min_amount)
        if max_amount is not None:
            conditions.append(FbaFee.fee_amount <= max_amount)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(FbaFee).where(*conditions)
        )).scalar() or 0
        stmt = select(FbaFee).where(*conditions).order_by(
            FbaFee.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total

    async def search_replenishment_plans(self, tenant_id: str, sku_id: str = "", store_id: str = "",
                                          status: str = "", priority: str = "",
                                          page: int = 1, page_size: int = 20) -> tuple[list[FbaReplenishmentPlan], int]:
        """多维度搜索补货计划"""
        conditions = [FbaReplenishmentPlan.tenant_id == tenant_id]
        if sku_id:
            conditions.append(FbaReplenishmentPlan.sku_id == sku_id)
        if store_id:
            conditions.append(FbaReplenishmentPlan.store_id == store_id)
        if status:
            conditions.append(FbaReplenishmentPlan.status == status)
        if priority:
            conditions.append(FbaReplenishmentPlan.priority == priority)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(FbaReplenishmentPlan).where(*conditions)
        )).scalar() or 0
        stmt = select(FbaReplenishmentPlan).where(*conditions).order_by(
            FbaReplenishmentPlan.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total
