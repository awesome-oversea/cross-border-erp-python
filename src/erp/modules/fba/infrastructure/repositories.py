from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.fba.domain.models import FbaBoxLabel, FbaFee, FbaInboundPlan, FbaInventory, FbaReplenishmentPlan, FbaShipment
from erp.modules.fba.domain.repositories import (
    FbaBoxLabelRepository,
    FbaFeeRepository,
    FbaInboundPlanRepository,
    FbaInventoryRepository,
    FbaReplenishmentPlanRepository,
    FbaShipmentRepository,
)


class SqlFbaShipmentRepository(FbaShipmentRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, shipment_id: str, tenant_id: str) -> FbaShipment | None:
        stmt = select(FbaShipment).where(FbaShipment.id == shipment_id, FbaShipment.tenant_id == tenant_id, FbaShipment.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_shipment_id(self, shipment_id_field: str, tenant_id: str) -> FbaShipment | None:
        stmt = select(FbaShipment).where(FbaShipment.shipment_id == shipment_id_field, FbaShipment.tenant_id == tenant_id, FbaShipment.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "", store_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[FbaShipment], int]:
        conditions = [FbaShipment.tenant_id == tenant_id, FbaShipment.deleted_at.is_(None)]
        if status:
            conditions.append(FbaShipment.status == status)
        if store_id:
            conditions.append(FbaShipment.store_id == store_id)
        total = (await self._session.execute(select(func.count()).select_from(FbaShipment).where(*conditions))).scalar() or 0
        stmt = select(FbaShipment).where(*conditions).order_by(FbaShipment.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, shipment: FbaShipment) -> FbaShipment:
        self._session.add(shipment)
        await self._session.flush()
        return shipment

    async def update(self, shipment: FbaShipment) -> FbaShipment:
        await self._session.flush()
        return shipment

    async def soft_delete(self, shipment_id: str, tenant_id: str) -> bool:
        stmt = update(FbaShipment).where(FbaShipment.id == shipment_id, FbaShipment.tenant_id == tenant_id).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlFbaInventoryRepository(FbaInventoryRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, inventory_id: str, tenant_id: str) -> FbaInventory | None:
        stmt = select(FbaInventory).where(FbaInventory.id == inventory_id, FbaInventory.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_by_sku_store(self, sku_id: str, store_id: str, tenant_id: str) -> FbaInventory | None:
        stmt = select(FbaInventory).where(FbaInventory.sku_id == sku_id, FbaInventory.store_id == store_id, FbaInventory.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, store_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[FbaInventory], int]:
        conditions = [FbaInventory.tenant_id == tenant_id]
        if store_id:
            conditions.append(FbaInventory.store_id == store_id)
        total = (await self._session.execute(select(func.count()).select_from(FbaInventory).where(*conditions))).scalar() or 0
        stmt = select(FbaInventory).where(*conditions).order_by(FbaInventory.sku_id).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, inventory: FbaInventory) -> FbaInventory:
        self._session.add(inventory)
        await self._session.flush()
        return inventory

    async def update(self, inventory: FbaInventory) -> FbaInventory:
        await self._session.flush()
        return inventory


class SqlFbaFeeRepository(FbaFeeRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_sku(self, sku_id: str, tenant_id: str, fee_type: str = "",
                          start_date: datetime | None = None, end_date: datetime | None = None) -> Sequence[FbaFee]:
        conditions = [FbaFee.sku_id == sku_id, FbaFee.tenant_id == tenant_id]
        if fee_type:
            conditions.append(FbaFee.fee_type == fee_type)
        if start_date:
            conditions.append(FbaFee.fee_date >= start_date)
        if end_date:
            conditions.append(FbaFee.fee_date <= end_date)
        stmt = select(FbaFee).where(*conditions).order_by(FbaFee.fee_date.desc())
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_store(self, store_id: str, tenant_id: str, fee_type: str = "",
                            start_date: datetime | None = None, end_date: datetime | None = None) -> Sequence[FbaFee]:
        conditions = [FbaFee.store_id == store_id, FbaFee.tenant_id == tenant_id]
        if fee_type:
            conditions.append(FbaFee.fee_type == fee_type)
        if start_date:
            conditions.append(FbaFee.fee_date >= start_date)
        if end_date:
            conditions.append(FbaFee.fee_date <= end_date)
        stmt = select(FbaFee).where(*conditions).order_by(FbaFee.fee_date.desc())
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, fee: FbaFee) -> FbaFee:
        self._session.add(fee)
        await self._session.flush()
        return fee


class SqlFbaBoxLabelRepository(FbaBoxLabelRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, label_id: str, tenant_id: str) -> FbaBoxLabel | None:
        stmt = select(FbaBoxLabel).where(FbaBoxLabel.id == label_id, FbaBoxLabel.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_shipment(self, shipment_id: str, tenant_id: str) -> Sequence[FbaBoxLabel]:
        stmt = select(FbaBoxLabel).where(
            FbaBoxLabel.shipment_id == shipment_id, FbaBoxLabel.tenant_id == tenant_id,
        ).order_by(FbaBoxLabel.box_no.asc())
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, label: FbaBoxLabel) -> FbaBoxLabel:
        self._session.add(label)
        await self._session.flush()
        return label

    async def update(self, label: FbaBoxLabel) -> FbaBoxLabel:
        await self._session.flush()
        return label


class SqlFbaReplenishmentPlanRepository(FbaReplenishmentPlanRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, plan_id: str, tenant_id: str) -> FbaReplenishmentPlan | None:
        stmt = select(FbaReplenishmentPlan).where(
            FbaReplenishmentPlan.id == plan_id, FbaReplenishmentPlan.tenant_id == tenant_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "", store_id: str = "",
                             priority: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[FbaReplenishmentPlan], int]:
        conditions = [FbaReplenishmentPlan.tenant_id == tenant_id]
        if status:
            conditions.append(FbaReplenishmentPlan.status == status)
        if store_id:
            conditions.append(FbaReplenishmentPlan.store_id == store_id)
        if priority:
            conditions.append(FbaReplenishmentPlan.priority == priority)
        total = (await self._session.execute(select(func.count()).select_from(FbaReplenishmentPlan).where(*conditions))).scalar() or 0
        stmt = select(FbaReplenishmentPlan).where(*conditions).order_by(FbaReplenishmentPlan.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, plan: FbaReplenishmentPlan) -> FbaReplenishmentPlan:
        self._session.add(plan)
        await self._session.flush()
        return plan

    async def update(self, plan: FbaReplenishmentPlan) -> FbaReplenishmentPlan:
        await self._session.flush()
        return plan


class SqlFbaInboundPlanRepository(FbaInboundPlanRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, plan_id: str, tenant_id: str) -> FbaInboundPlan | None:
        stmt = select(FbaInboundPlan).where(FbaInboundPlan.id == plan_id, FbaInboundPlan.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[FbaInboundPlan], int]:
        conditions = [FbaInboundPlan.tenant_id == tenant_id]
        if status:
            conditions.append(FbaInboundPlan.status == status)
        total = (await self._session.execute(select(func.count()).select_from(FbaInboundPlan).where(*conditions))).scalar() or 0
        stmt = select(FbaInboundPlan).where(*conditions).order_by(FbaInboundPlan.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, plan: FbaInboundPlan) -> FbaInboundPlan:
        self._session.add(plan)
        await self._session.flush()
        return plan

    async def update(self, plan: FbaInboundPlan) -> FbaInboundPlan:
        await self._session.flush()
        return plan
