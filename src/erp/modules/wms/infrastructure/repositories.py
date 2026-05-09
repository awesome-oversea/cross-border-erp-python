from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.wms.domain.inventory_alert_models import (
    InventoryAlert,
    InventoryAlertRule,
    InventorySnapshot,
)
from erp.modules.wms.domain.models import (
    InboundOrder,
    Inventory,
    Location,
    OutboundOrder,
    QualityInspection,
    StockCount,
    StockMovement,
    Warehouse,
)
from erp.modules.wms.domain.repositories import (
    FBAReplenishmentPlanRepository,
    InboundOrderRepository,
    InventoryAlertRepository,
    InventoryAlertRuleRepository,
    InventoryRepository,
    InventorySnapshotRepository,
    LocationRepository,
    OutboundOrderRepository,
    QualityInspectionRepository,
    StockCountRepository,
    StockMovementRepository,
    StockTransferOrderRepository,
    WarehouseRepository,
)
from erp.modules.wms.domain.transfer_replenishment_models import (
    FBAReplenishmentPlan,
    StockTransferOrder,
)


class SqlWarehouseRepository(WarehouseRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, warehouse_id: str, tenant_id: str) -> Warehouse | None:
        stmt = select(Warehouse).where(Warehouse.id == warehouse_id, Warehouse.tenant_id == tenant_id, Warehouse.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, code: str, tenant_id: str) -> Warehouse | None:
        stmt = select(Warehouse).where(Warehouse.code == code, Warehouse.tenant_id == tenant_id, Warehouse.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, warehouse_type: str = "", status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Warehouse], int]:
        conditions = [Warehouse.tenant_id == tenant_id, Warehouse.deleted_at.is_(None)]
        if warehouse_type:
            conditions.append(Warehouse.warehouse_type == warehouse_type)
        if status:
            conditions.append(Warehouse.status == status)
        total = (await self._session.execute(select(func.count()).select_from(Warehouse).where(*conditions))).scalar() or 0
        stmt = select(Warehouse).where(*conditions).order_by(Warehouse.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, warehouse: Warehouse) -> Warehouse:
        self._session.add(warehouse)
        await self._session.flush()
        return warehouse

    async def update(self, warehouse: Warehouse) -> Warehouse:
        await self._session.flush()
        return warehouse

    async def soft_delete(self, warehouse_id: str, tenant_id: str) -> bool:
        stmt = update(Warehouse).where(Warehouse.id == warehouse_id, Warehouse.tenant_id == tenant_id).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlLocationRepository(LocationRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, location_id: str, tenant_id: str) -> Location | None:
        stmt = select(Location).where(Location.id == location_id, Location.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_warehouse(self, warehouse_id: str, tenant_id: str, location_type: str = "") -> Sequence[Location]:
        conditions = [Location.warehouse_id == warehouse_id, Location.tenant_id == tenant_id]
        if location_type:
            conditions.append(Location.location_type == location_type)
        stmt = select(Location).where(*conditions).order_by(Location.code)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, location: Location) -> Location:
        self._session.add(location)
        await self._session.flush()
        return location

    async def update(self, location: Location) -> Location:
        await self._session.flush()
        return location


class SqlInventoryRepository(InventoryRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, inventory_id: str, tenant_id: str) -> Inventory | None:
        stmt = select(Inventory).where(Inventory.id == inventory_id, Inventory.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_by_warehouse_sku(self, warehouse_id: str, sku_id: str, tenant_id: str) -> Inventory | None:
        stmt = select(Inventory).where(Inventory.warehouse_id == warehouse_id, Inventory.sku_id == sku_id, Inventory.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_warehouse(self, warehouse_id: str, tenant_id: str, page: int = 1, page_size: int = 20) -> tuple[Sequence[Inventory], int]:
        conditions = [Inventory.warehouse_id == warehouse_id, Inventory.tenant_id == tenant_id]
        total = (await self._session.execute(select(func.count()).select_from(Inventory).where(*conditions))).scalar() or 0
        stmt = select(Inventory).where(*conditions).order_by(Inventory.sku_id).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def list_by_sku(self, sku_id: str, tenant_id: str) -> Sequence[Inventory]:
        stmt = select(Inventory).where(Inventory.sku_id == sku_id, Inventory.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def find_low_stock(self, tenant_id: str) -> Sequence[Inventory]:
        stmt = select(Inventory).where(Inventory.tenant_id == tenant_id, Inventory.qty_available <= Inventory.safety_qty, Inventory.safety_qty > 0)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, inventory: Inventory) -> Inventory:
        self._session.add(inventory)
        await self._session.flush()
        return inventory

    async def update(self, inventory: Inventory) -> Inventory:
        await self._session.flush()
        return inventory


class SqlInboundOrderRepository(InboundOrderRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, inbound_id: str, tenant_id: str) -> InboundOrder | None:
        stmt = select(InboundOrder).where(InboundOrder.id == inbound_id, InboundOrder.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_inbound_no(self, inbound_no: str, tenant_id: str) -> InboundOrder | None:
        stmt = select(InboundOrder).where(InboundOrder.inbound_no == inbound_no, InboundOrder.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "", warehouse_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[InboundOrder], int]:
        conditions = [InboundOrder.tenant_id == tenant_id]
        if status:
            conditions.append(InboundOrder.status == status)
        if warehouse_id:
            conditions.append(InboundOrder.warehouse_id == warehouse_id)
        total = (await self._session.execute(select(func.count()).select_from(InboundOrder).where(*conditions))).scalar() or 0
        stmt = select(InboundOrder).where(*conditions).order_by(InboundOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, order: InboundOrder) -> InboundOrder:
        self._session.add(order)
        await self._session.flush()
        return order

    async def update(self, order: InboundOrder) -> InboundOrder:
        await self._session.flush()
        return order


class SqlOutboundOrderRepository(OutboundOrderRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, outbound_id: str, tenant_id: str) -> OutboundOrder | None:
        stmt = select(OutboundOrder).where(OutboundOrder.id == outbound_id, OutboundOrder.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_outbound_no(self, outbound_no: str, tenant_id: str) -> OutboundOrder | None:
        stmt = select(OutboundOrder).where(OutboundOrder.outbound_no == outbound_no, OutboundOrder.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "", warehouse_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[OutboundOrder], int]:
        conditions = [OutboundOrder.tenant_id == tenant_id]
        if status:
            conditions.append(OutboundOrder.status == status)
        if warehouse_id:
            conditions.append(OutboundOrder.warehouse_id == warehouse_id)
        total = (await self._session.execute(select(func.count()).select_from(OutboundOrder).where(*conditions))).scalar() or 0
        stmt = select(OutboundOrder).where(*conditions).order_by(OutboundOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, order: OutboundOrder) -> OutboundOrder:
        self._session.add(order)
        await self._session.flush()
        return order

    async def update(self, order: OutboundOrder) -> OutboundOrder:
        await self._session.flush()
        return order


class SqlStockMovementRepository(StockMovementRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, movement: StockMovement) -> StockMovement:
        self._session.add(movement)
        await self._session.flush()
        return movement

    async def list_by_sku(self, sku_id: str, tenant_id: str, limit: int = 50) -> Sequence[StockMovement]:
        stmt = select(StockMovement).where(StockMovement.sku_id == sku_id, StockMovement.tenant_id == tenant_id).order_by(StockMovement.created_at.desc()).limit(limit)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_reference(self, reference_type: str, reference_id: str, tenant_id: str) -> Sequence[StockMovement]:
        stmt = select(StockMovement).where(StockMovement.reference_type == reference_type, StockMovement.reference_id == reference_id, StockMovement.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()


class SqlStockCountRepository(StockCountRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, count_id: str, tenant_id: str) -> StockCount | None:
        stmt = select(StockCount).where(StockCount.id == count_id, StockCount.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[StockCount], int]:
        conditions = [StockCount.tenant_id == tenant_id]
        if status:
            conditions.append(StockCount.status == status)
        total = (await self._session.execute(select(func.count()).select_from(StockCount).where(*conditions))).scalar() or 0
        stmt = select(StockCount).where(*conditions).order_by(StockCount.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, count: StockCount) -> StockCount:
        self._session.add(count)
        await self._session.flush()
        return count

    async def update(self, count: StockCount) -> StockCount:
        await self._session.flush()
        return count


class SqlQualityInspectionRepository(QualityInspectionRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, inspection_id: str, tenant_id: str) -> QualityInspection | None:
        stmt = select(QualityInspection).where(
            QualityInspection.id == inspection_id, QualityInspection.tenant_id == tenant_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_warehouse(self, tenant_id: str, warehouse_id: str,
                                 result: str = "", offset: int = 0, limit: int = 20) -> Sequence[QualityInspection]:
        conditions = [QualityInspection.tenant_id == tenant_id, QualityInspection.warehouse_id == warehouse_id]
        if result:
            conditions.append(QualityInspection.inspection_result == result)
        stmt = select(QualityInspection).where(*conditions).order_by(
            QualityInspection.created_at.desc()
        ).offset(offset).limit(limit)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, inspection: QualityInspection) -> QualityInspection:
        self._session.add(inspection)
        await self._session.flush()
        return inspection

    async def update(self, inspection: QualityInspection) -> QualityInspection:
        await self._session.flush()
        return inspection


class SqlStockTransferOrderRepository(StockTransferOrderRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, transfer_id: str, tenant_id: str) -> StockTransferOrder | None:
        stmt = select(StockTransferOrder).where(
            StockTransferOrder.id == transfer_id, StockTransferOrder.tenant_id == tenant_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "",
                              from_warehouse_id: str = "", to_warehouse_id: str = "",
                              page: int = 1, page_size: int = 20) -> tuple[Sequence[StockTransferOrder], int]:
        conditions = [StockTransferOrder.tenant_id == tenant_id]
        if status:
            conditions.append(StockTransferOrder.status == status)
        if from_warehouse_id:
            conditions.append(StockTransferOrder.from_warehouse_id == from_warehouse_id)
        if to_warehouse_id:
            conditions.append(StockTransferOrder.to_warehouse_id == to_warehouse_id)
        total = (await self._session.execute(
            select(func.count()).select_from(StockTransferOrder).where(*conditions)
        )).scalar() or 0
        stmt = select(StockTransferOrder).where(*conditions).order_by(
            StockTransferOrder.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, transfer: StockTransferOrder) -> StockTransferOrder:
        self._session.add(transfer)
        await self._session.flush()
        return transfer

    async def update(self, transfer: StockTransferOrder) -> StockTransferOrder:
        await self._session.flush()
        return transfer


class SqlFBAReplenishmentPlanRepository(FBAReplenishmentPlanRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, plan_id: str, tenant_id: str) -> FBAReplenishmentPlan | None:
        stmt = select(FBAReplenishmentPlan).where(
            FBAReplenishmentPlan.id == plan_id, FBAReplenishmentPlan.tenant_id == tenant_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, sku_id: str = "", status: str = "",
                              page: int = 1, page_size: int = 20) -> tuple[Sequence[FBAReplenishmentPlan], int]:
        conditions = [FBAReplenishmentPlan.tenant_id == tenant_id]
        if sku_id:
            conditions.append(FBAReplenishmentPlan.sku_id == sku_id)
        if status:
            conditions.append(FBAReplenishmentPlan.status == status)
        total = (await self._session.execute(
            select(func.count()).select_from(FBAReplenishmentPlan).where(*conditions)
        )).scalar() or 0
        stmt = select(FBAReplenishmentPlan).where(*conditions).order_by(
            FBAReplenishmentPlan.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, plan: FBAReplenishmentPlan) -> FBAReplenishmentPlan:
        self._session.add(plan)
        await self._session.flush()
        return plan

    async def update(self, plan: FBAReplenishmentPlan) -> FBAReplenishmentPlan:
        await self._session.flush()
        return plan


class SqlInventorySnapshotRepository(InventorySnapshotRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_key(self, tenant_id: str, snapshot_date: str,
                          warehouse_id: str, sku_id: str) -> InventorySnapshot | None:
        stmt = select(InventorySnapshot).where(
            InventorySnapshot.tenant_id == tenant_id,
            InventorySnapshot.snapshot_date == snapshot_date,
            InventorySnapshot.warehouse_id == warehouse_id,
            InventorySnapshot.sku_id == sku_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_date(self, tenant_id: str, snapshot_date: str,
                            warehouse_id: str = "", sku_id: str = "") -> Sequence[InventorySnapshot]:
        conditions = [
            InventorySnapshot.tenant_id == tenant_id,
            InventorySnapshot.snapshot_date == snapshot_date,
        ]
        if warehouse_id:
            conditions.append(InventorySnapshot.warehouse_id == warehouse_id)
        if sku_id:
            conditions.append(InventorySnapshot.sku_id == sku_id)
        stmt = select(InventorySnapshot).where(*conditions)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, snapshot: InventorySnapshot) -> InventorySnapshot:
        self._session.add(snapshot)
        await self._session.flush()
        return snapshot

    async def update(self, snapshot: InventorySnapshot) -> InventorySnapshot:
        await self._session.flush()
        return snapshot


class SqlInventoryAlertRuleRepository(InventoryAlertRuleRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, rule_id: str, tenant_id: str) -> InventoryAlertRule | None:
        stmt = select(InventoryAlertRule).where(
            InventoryAlertRule.id == rule_id, InventoryAlertRule.tenant_id == tenant_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_active(self, tenant_id: str) -> Sequence[InventoryAlertRule]:
        stmt = select(InventoryAlertRule).where(
            InventoryAlertRule.tenant_id == tenant_id, InventoryAlertRule.is_active
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, rule: InventoryAlertRule) -> InventoryAlertRule:
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def update(self, rule: InventoryAlertRule) -> InventoryAlertRule:
        await self._session.flush()
        return rule


class SqlInventoryAlertRepository(InventoryAlertRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, alert_id: str, tenant_id: str) -> InventoryAlert | None:
        stmt = select(InventoryAlert).where(
            InventoryAlert.id == alert_id, InventoryAlert.tenant_id == tenant_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_active_in_cooldown(self, tenant_id: str, rule_id: str, alert_type: str,
                                       warehouse_id: str, sku_id: str,
                                       cutoff_time) -> InventoryAlert | None:
        stmt = select(InventoryAlert).where(
            InventoryAlert.tenant_id == tenant_id,
            InventoryAlert.rule_id == rule_id,
            InventoryAlert.alert_type == alert_type,
            InventoryAlert.warehouse_id == warehouse_id,
            InventoryAlert.sku_id == sku_id,
            InventoryAlert.status.in_(["pending", "acknowledged"]),
            InventoryAlert.created_at >= cutoff_time,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, alert_type: str = "",
                              severity: str = "", status: str = "",
                              warehouse_id: str = "", sku_id: str = "",
                              page: int = 1, page_size: int = 20) -> tuple[Sequence[InventoryAlert], int]:
        conditions = [InventoryAlert.tenant_id == tenant_id]
        if alert_type:
            conditions.append(InventoryAlert.alert_type == alert_type)
        if severity:
            conditions.append(InventoryAlert.severity == severity)
        if status:
            conditions.append(InventoryAlert.status == status)
        if warehouse_id:
            conditions.append(InventoryAlert.warehouse_id == warehouse_id)
        if sku_id:
            conditions.append(InventoryAlert.sku_id == sku_id)
        total = (await self._session.execute(
            select(func.count()).select_from(InventoryAlert).where(*conditions)
        )).scalar() or 0
        stmt = select(InventoryAlert).where(*conditions).order_by(
            InventoryAlert.severity.desc(), InventoryAlert.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, alert: InventoryAlert) -> InventoryAlert:
        self._session.add(alert)
        await self._session.flush()
        return alert

    async def update(self, alert: InventoryAlert) -> InventoryAlert:
        await self._session.flush()
        return alert
