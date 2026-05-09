"""
WMS 模块依赖注入工厂

提供 FastAPI Depends() 可用的仓储 / 服务工厂函数，
实现「请求 → Session → 仓储 → 服务」的完整注入链路。
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.wms.application.services import (
    InboundService,
    InventoryService,
    LocationService,
    OutboundService,
    QualityInspectionService,
    StockCountService,
    WMSQueryService,
    WarehouseService,
)
from erp.modules.wms.domain.inventory_alert_models import (
    InventoryAlertService,
    InventorySnapshotService,
)
from erp.modules.wms.domain.transfer_replenishment_models import (
    FBAReplenishmentService,
    StockTransferService,
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
from erp.modules.wms.infrastructure.repositories import (
    SqlFBAReplenishmentPlanRepository,
    SqlInboundOrderRepository,
    SqlInventoryAlertRepository,
    SqlInventoryAlertRuleRepository,
    SqlInventoryRepository,
    SqlInventorySnapshotRepository,
    SqlLocationRepository,
    SqlOutboundOrderRepository,
    SqlQualityInspectionRepository,
    SqlStockCountRepository,
    SqlStockMovementRepository,
    SqlStockTransferOrderRepository,
    SqlWarehouseRepository,
)
from erp.shared.context import get_current_tenant_id
from erp.shared.db.session import get_db_session


def _warehouse_repo(session: AsyncSession = Depends(get_db_session)) -> WarehouseRepository:
    return SqlWarehouseRepository(session)


def _location_repo(session: AsyncSession = Depends(get_db_session)) -> LocationRepository:
    return SqlLocationRepository(session)


def _inventory_repo(session: AsyncSession = Depends(get_db_session)) -> InventoryRepository:
    return SqlInventoryRepository(session)


def _inbound_order_repo(session: AsyncSession = Depends(get_db_session)) -> InboundOrderRepository:
    return SqlInboundOrderRepository(session)


def _outbound_order_repo(session: AsyncSession = Depends(get_db_session)) -> OutboundOrderRepository:
    return SqlOutboundOrderRepository(session)


def _stock_movement_repo(session: AsyncSession = Depends(get_db_session)) -> StockMovementRepository:
    return SqlStockMovementRepository(session)


def _stock_count_repo(session: AsyncSession = Depends(get_db_session)) -> StockCountRepository:
    return SqlStockCountRepository(session)


def _quality_inspection_repo(session: AsyncSession = Depends(get_db_session)) -> QualityInspectionRepository:
    return SqlQualityInspectionRepository(session)


def _stock_transfer_repo(session: AsyncSession = Depends(get_db_session)) -> StockTransferOrderRepository:
    return SqlStockTransferOrderRepository(session)


def _fba_replenishment_repo(session: AsyncSession = Depends(get_db_session)) -> FBAReplenishmentPlanRepository:
    return SqlFBAReplenishmentPlanRepository(session)


def _snapshot_repo(session: AsyncSession = Depends(get_db_session)) -> InventorySnapshotRepository:
    return SqlInventorySnapshotRepository(session)


def _alert_rule_repo(session: AsyncSession = Depends(get_db_session)) -> InventoryAlertRuleRepository:
    return SqlInventoryAlertRuleRepository(session)


def _alert_repo(session: AsyncSession = Depends(get_db_session)) -> InventoryAlertRepository:
    return SqlInventoryAlertRepository(session)


def get_warehouse_service(
    session: AsyncSession = Depends(get_db_session),
    warehouse_repo: WarehouseRepository = Depends(_warehouse_repo),
) -> WarehouseService:
    """获取仓库服务实例 — 注入 WarehouseRepository"""
    return WarehouseService(session=session, warehouse_repo=warehouse_repo)


def get_location_service(
    session: AsyncSession = Depends(get_db_session),
    location_repo: LocationRepository = Depends(_location_repo),
    warehouse_repo: WarehouseRepository = Depends(_warehouse_repo),
) -> LocationService:
    """获取库位服务实例 — 注入 Location / Warehouse 两个仓储"""
    return LocationService(session=session, location_repo=location_repo, warehouse_repo=warehouse_repo)


def get_inventory_service(
    session: AsyncSession = Depends(get_db_session),
    inventory_repo: InventoryRepository = Depends(_inventory_repo),
    movement_repo: StockMovementRepository = Depends(_stock_movement_repo),
) -> InventoryService:
    """获取库存服务实例 — 注入 Inventory / StockMovement 两个仓储"""
    return InventoryService(session=session, inventory_repo=inventory_repo, movement_repo=movement_repo)


def get_inbound_service(
    session: AsyncSession = Depends(get_db_session),
    inbound_repo: InboundOrderRepository = Depends(_inbound_order_repo),
    inventory_repo: InventoryRepository = Depends(_inventory_repo),
    movement_repo: StockMovementRepository = Depends(_stock_movement_repo),
) -> InboundService:
    """获取入库服务实例 — 注入 Inbound / Inventory / Movement 三个仓储"""
    return InboundService(
        session=session, inbound_repo=inbound_repo,
        inventory_repo=inventory_repo, movement_repo=movement_repo,
    )


def get_outbound_service(
    session: AsyncSession = Depends(get_db_session),
    outbound_repo: OutboundOrderRepository = Depends(_outbound_order_repo),
    inventory_repo: InventoryRepository = Depends(_inventory_repo),
    movement_repo: StockMovementRepository = Depends(_stock_movement_repo),
) -> OutboundService:
    """获取出库服务实例 — 注入 Outbound / Inventory / Movement 三个仓储"""
    return OutboundService(
        session=session, outbound_repo=outbound_repo,
        inventory_repo=inventory_repo, movement_repo=movement_repo,
    )


def get_quality_inspection_service(
    session: AsyncSession = Depends(get_db_session),
    inspection_repo: QualityInspectionRepository = Depends(_quality_inspection_repo),
    inventory_repo: InventoryRepository = Depends(_inventory_repo),
    movement_repo: StockMovementRepository = Depends(_stock_movement_repo),
) -> QualityInspectionService:
    """获取质检服务实例 — 注入 Inspection / Inventory / Movement 三个仓储"""
    return QualityInspectionService(
        session=session, inspection_repo=inspection_repo,
        inventory_repo=inventory_repo, movement_repo=movement_repo,
    )


def get_stock_count_service(
    session: AsyncSession = Depends(get_db_session),
    count_repo: StockCountRepository = Depends(_stock_count_repo),
    inventory_repo: InventoryRepository = Depends(_inventory_repo),
    movement_repo: StockMovementRepository = Depends(_stock_movement_repo),
) -> StockCountService:
    """获取盘点服务实例 — 注入 StockCount / Inventory / Movement 三个仓储"""
    return StockCountService(
        session=session, count_repo=count_repo,
        inventory_repo=inventory_repo, movement_repo=movement_repo,
    )


def get_stock_transfer_service(
    session: AsyncSession = Depends(get_db_session),
    transfer_repo: StockTransferOrderRepository = Depends(_stock_transfer_repo),
) -> StockTransferService:
    """获取调拨服务实例 — 注入 StockTransferOrder 仓储"""
    return StockTransferService(session=session, transfer_repo=transfer_repo)


def get_fba_replenishment_service(
    session: AsyncSession = Depends(get_db_session),
    plan_repo: FBAReplenishmentPlanRepository = Depends(_fba_replenishment_repo),
) -> FBAReplenishmentService:
    """获取FBA补货服务实例 — 注入 FBAReplenishmentPlan 仓储"""
    return FBAReplenishmentService(session=session, plan_repo=plan_repo)


def get_inventory_snapshot_service(
    session: AsyncSession = Depends(get_db_session),
    snapshot_repo: InventorySnapshotRepository = Depends(_snapshot_repo),
    inventory_repo: InventoryRepository = Depends(_inventory_repo),
) -> InventorySnapshotService:
    """获取库存快照服务实例 — 注入 Snapshot / Inventory 两个仓储"""
    return InventorySnapshotService(session=session, snapshot_repo=snapshot_repo, inventory_repo=inventory_repo)


def get_inventory_alert_service(
    session: AsyncSession = Depends(get_db_session),
    alert_repo: InventoryAlertRepository = Depends(_alert_repo),
    alert_rule_repo: InventoryAlertRuleRepository = Depends(_alert_rule_repo),
    inventory_repo: InventoryRepository = Depends(_inventory_repo),
) -> InventoryAlertService:
    """获取库存预警服务实例 — 注入 Alert / AlertRule / Inventory 三个仓储"""
    return InventoryAlertService(
        session=session, alert_repo=alert_repo,
        alert_rule_repo=alert_rule_repo, inventory_repo=inventory_repo,
    )


def get_wms_query_service(
    session: AsyncSession = Depends(get_db_session),
) -> WMSQueryService:
    """获取WMS统计查询服务实例 — 仅注入 Session"""
    return WMSQueryService(session=session)
