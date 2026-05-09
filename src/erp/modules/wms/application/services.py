"""
WMS 应用服务层

编排仓储接口与领域服务，实现仓库、库位、库存、入库、出库、质检、盘点
等核心业务流程。每个服务通过构造函数注入所需的仓储接口。
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import select

from sqlalchemy import func as sa_func
from sqlalchemy import select

from erp.modules.wms.domain.models import (
    InboundOrder,
    Inventory,
    Location,
    OutboundOrder,
    QualityInspection,
    StockCount,
    StockMovement,
    StockTransfer,
    Warehouse,
)
from erp.modules.wms.domain.repositories import (
    InboundOrderRepository,
    InventoryRepository,
    LocationRepository,
    OutboundOrderRepository,
    QualityInspectionRepository,
    StockCountRepository,
    StockMovementRepository,
    WarehouseRepository,
)
from erp.modules.wms.domain.services import (
    QualityInspectionDomainService,
    StockCountDomainService,
)
from erp.shared.context import actor_id_var
from erp.shared.exceptions import DuplicateCodeException, NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.wms")


class WarehouseService:
    """
    仓库应用服务

    编排仓库的完整生命周期: 创建 → 更新 → 软删除
    通过 WarehouseRepository 操作数据。
    """

    def __init__(self, session: AsyncSession, warehouse_repo: WarehouseRepository):
        self._session = session
        self._warehouse_repo = warehouse_repo

    async def create(self, tenant_id: str, name: str, code: str, **kwargs) -> Warehouse:
        """创建仓库: 唯一性校验(code) → 持久化"""
        existing = await self._warehouse_repo.get_by_code(code, tenant_id)
        if existing:
            raise DuplicateCodeException(message=f"Warehouse code '{code}' already exists")
        wh = Warehouse(tenant_id=tenant_id, name=name, code=code, **kwargs)
        return await self._warehouse_repo.create(wh)

    async def get_by_id(self, wh_id: str, tenant_id: str) -> Warehouse | None:
        """根据ID获取仓库"""
        return await self._warehouse_repo.get_by_id(wh_id, tenant_id)

    async def get_or_raise(self, wh_id: str, tenant_id: str) -> Warehouse:
        """根据ID获取仓库，不存在则抛出 NotFoundException"""
        warehouse = await self.get_by_id(wh_id, tenant_id)
        if not warehouse:
            raise NotFoundException(message=f"Warehouse '{wh_id}' not found")
        return warehouse

    async def list_all(self, tenant_id: str, warehouse_type: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[Warehouse], int]:
        """分页查询仓库列表"""
        return await self._warehouse_repo.list_by_tenant(
            tenant_id, warehouse_type=warehouse_type, page=page, page_size=page_size
        )

    async def update(self, wh_id: str, tenant_id: str, **kwargs) -> Warehouse:
        """更新仓库: 查询 → 属性更新 → 持久化"""
        wh = await self._warehouse_repo.get_by_id(wh_id, tenant_id)
        if not wh:
            raise NotFoundException(message=f"Warehouse '{wh_id}' not found")
        for k, v in kwargs.items():
            if v is not None and hasattr(wh, k):
                setattr(wh, k, v)
        return await self._warehouse_repo.update(wh)

    async def soft_delete(self, wh_id: str, tenant_id: str) -> bool:
        """软删除仓库"""
        wh = await self._warehouse_repo.get_by_id(wh_id, tenant_id)
        if not wh:
            raise NotFoundException(message=f"Warehouse '{wh_id}' not found")
        return await self._warehouse_repo.soft_delete(wh_id, tenant_id)


class LocationService:
    """
    库位应用服务

    编排库位的完整生命周期: 创建 → 更新
    通过 LocationRepository 和 WarehouseRepository 操作数据。
    """

    VALID_LOCATION_TYPES = ["receiving", "storage", "picking", "packing", "shipping", "staging", "returns"]

    def __init__(self, session: AsyncSession, location_repo: LocationRepository | None = None,
                 warehouse_repo: WarehouseRepository | None = None):
        self._session = session
        self._location_repo = location_repo
        self._warehouse_repo = warehouse_repo

    async def create(self, tenant_id: str, warehouse_id: str, code: str, **kwargs) -> Location:
        """创建库位: 仓库校验 → 类型校验 → 持久化"""
        if self._warehouse_repo:
            wh = await self._warehouse_repo.get_by_id(warehouse_id, tenant_id)
        else:
            wh = await self._session.get(Warehouse, warehouse_id)
            if wh and wh.tenant_id != tenant_id:
                wh = None
        if not wh:
            raise NotFoundException(message=f"Warehouse '{warehouse_id}' not found")
        location_type = kwargs.get("location_type", "storage")
        if location_type not in self.VALID_LOCATION_TYPES:
            raise ValidationException(
                message=f"Invalid location type '{location_type}', allowed: {self.VALID_LOCATION_TYPES}"
            )
        loc = Location(tenant_id=tenant_id, warehouse_id=warehouse_id, code=code, **kwargs)
        if self._location_repo:
            return await self._location_repo.create(loc)
        self._session.add(loc)
        await self._session.flush()
        return loc

    async def list_by_warehouse(self, warehouse_id: str, tenant_id: str) -> Sequence[Location]:
        """按仓库查询库位列表"""
        return await self._location_repo.list_by_warehouse(warehouse_id, tenant_id)


class InventoryService:
    """
    库存应用服务

    编排库存的完整生命周期: 获取或创建 → 调整 → 查询 → 低库存检查
    通过 InventoryRepository 和 StockMovementRepository 操作数据。
    """

    def __init__(self, session: AsyncSession, inventory_repo: InventoryRepository | None = None,
                 movement_repo: StockMovementRepository | None = None):
        self._session = session
        self._inventory_repo = inventory_repo
        self._movement_repo = movement_repo

    async def get_or_create(self, tenant_id: str, warehouse_id: str, sku_id: str, **kwargs) -> Inventory:
        """获取或创建库存记录: 按仓库+SKU查找 → 不存在则创建"""
        if self._inventory_repo:
            inv = await self._inventory_repo.find_by_warehouse_sku(warehouse_id, sku_id, tenant_id)
        else:
            stmt = select(Inventory).where(Inventory.warehouse_id == warehouse_id, Inventory.sku_id == sku_id, Inventory.tenant_id == tenant_id)
            inv = (await self._session.execute(stmt)).scalar_one_or_none()
        if inv:
            return inv
        inv = Inventory(tenant_id=tenant_id, warehouse_id=warehouse_id, sku_id=sku_id, **kwargs)
        if self._inventory_repo:
            return await self._inventory_repo.create(inv)
        self._session.add(inv)
        await self._session.flush()
        return inv

    async def adjust_stock(self, tenant_id: str, warehouse_id: str, sku_id: str,
                           qty_change: int, movement_type: str, reference_type: str = "",
                           reference_id: str = "", remark: str = "") -> Inventory:
        """
        调整库存: 获取或创建 → 数量变更 → 可用量计算 → 记录流水

        参数:
            tenant_id: 租户ID
            warehouse_id: 仓库ID
            sku_id: SKU ID
            qty_change: 变更数量 (正数入库, 负数出库)
            movement_type: 移动类型 (inbound/outbound/transfer/adjustment)
            reference_type: 关联类型
            reference_id: 关联ID
            remark: 备注
        """
        if qty_change == 0:
            raise ValidationException(message="Quantity change cannot be zero")
        inv = await self.get_or_create(tenant_id, warehouse_id, sku_id)
        qty_before = inv.qty_on_hand
        inv.qty_on_hand += qty_change
        inv.qty_available = inv.qty_on_hand - inv.qty_reserved
        if inv.qty_on_hand < 0:
            raise ValidationException(message="Insufficient stock")
        if inv.qty_available < 0:
            raise ValidationException(message="Insufficient available stock (reserved items)")
        await self._inventory_repo.update(inv)

        movement = StockMovement(
            tenant_id=tenant_id, warehouse_id=warehouse_id, sku_id=sku_id,
            movement_type=movement_type, qty_change=qty_change,
            qty_before=qty_before, qty_after=inv.qty_on_hand,
            reference_type=reference_type, reference_id=reference_id,
            operator_id=actor_id_var.get(""), remark=remark,
        )
        await self._movement_repo.create(movement)
        return inv

    async def check_low_stock(self, tenant_id: str, warehouse_id: str = "") -> list[dict]:
        """检查低库存: 查询可用量 ≤ 安全库存的记录"""
        if self._inventory_repo:
            items = await self._inventory_repo.find_low_stock(tenant_id)
        else:
            stmt = select(Inventory).where(Inventory.tenant_id == tenant_id, Inventory.qty_available <= Inventory.safety_qty, Inventory.safety_qty > 0)
            items = (await self._session.execute(stmt)).scalars().all()
        if warehouse_id:
            items = [i for i in items if i.warehouse_id == warehouse_id]
        return [
            {"sku_id": i.sku_id, "warehouse_id": i.warehouse_id,
             "available": i.qty_available, "safety": i.safety_qty,
             "shortage": i.safety_qty - i.qty_available}
            for i in items
        ]

    async def reserve_stock(self, tenant_id: str, warehouse_id: str, sku_id: str,
                            reserve_qty: int, reference_type: str = "",
                            reference_id: str = "", remark: str = "") -> Inventory:
        """
        预留库存: 获取库存 → 可用量校验 → 增加预留量 → 减少可用量 → 记录流水

        参数:
            tenant_id: 租户ID
            warehouse_id: 仓库ID
            sku_id: SKU ID
            reserve_qty: 预留数量
            reference_type: 关联类型
            reference_id: 关联ID
            remark: 备注
        """
        if reserve_qty <= 0:
            raise ValidationException(message="Reserve quantity must be positive")
        inv = await self.get_or_create(tenant_id, warehouse_id, sku_id)
        if inv.qty_available < reserve_qty:
            raise ValidationException(
                message=f"Insufficient available stock: have {inv.qty_available}, need {reserve_qty}"
            )
        inv.qty_reserved += reserve_qty
        inv.qty_available = inv.qty_on_hand - inv.qty_reserved
        await self._inventory_repo.update(inv)

        movement = StockMovement(
            tenant_id=tenant_id, warehouse_id=warehouse_id, sku_id=sku_id,
            movement_type="hold", qty_change=0,
            qty_before=inv.qty_on_hand, qty_after=inv.qty_on_hand,
            reference_type=reference_type, reference_id=reference_id,
            operator_id=actor_id_var.get(""), remark=remark or f"Reserve {reserve_qty} units",
        )
        await self._movement_repo.create(movement)
        return inv

    async def unreserve_stock(self, tenant_id: str, warehouse_id: str, sku_id: str,
                              unreserve_qty: int, reference_type: str = "",
                              reference_id: str = "", remark: str = "") -> Inventory:
        """
        释放预留库存: 获取库存 → 预留量校验 → 减少预留量 → 增加可用量 → 记录流水

        参数:
            tenant_id: 租户ID
            warehouse_id: 仓库ID
            sku_id: SKU ID
            unreserve_qty: 释放数量
            reference_type: 关联类型
            reference_id: 关联ID
            remark: 备注
        """
        if unreserve_qty <= 0:
            raise ValidationException(message="Unreserve quantity must be positive")
        inv = await self.get_or_create(tenant_id, warehouse_id, sku_id)
        if inv.qty_reserved < unreserve_qty:
            raise ValidationException(
                message=f"Cannot unreserve {unreserve_qty}, only {inv.qty_reserved} reserved"
            )
        inv.qty_reserved -= unreserve_qty
        inv.qty_available = inv.qty_on_hand - inv.qty_reserved
        await self._inventory_repo.update(inv)

        movement = StockMovement(
            tenant_id=tenant_id, warehouse_id=warehouse_id, sku_id=sku_id,
            movement_type="release", qty_change=0,
            qty_before=inv.qty_on_hand, qty_after=inv.qty_on_hand,
            reference_type=reference_type, reference_id=reference_id,
            operator_id=actor_id_var.get(""), remark=remark or f"Unreserve {unreserve_qty} units",
        )
        await self._movement_repo.create(movement)
        return inv

    async def query_stock(self, tenant_id: str, warehouse_id: str = "", sku_id: str = "",
                          page: int = 1, page_size: int = 20) -> tuple[Sequence[Inventory], int]:
        """分页查询库存"""
        if warehouse_id:
            if self._inventory_repo:
                return await self._inventory_repo.list_by_warehouse(
                    warehouse_id, tenant_id, page=page, page_size=page_size
                )
            stmt = select(Inventory).where(
                Inventory.tenant_id == tenant_id, Inventory.warehouse_id == warehouse_id
            )
            all_inv = (await self._session.execute(stmt)).scalars().all()
            start = (page - 1) * page_size
            return all_inv[start:start + page_size], len(all_inv)
        if sku_id:
            if self._inventory_repo:
                all_inv = await self._inventory_repo.list_by_sku(sku_id, tenant_id)
            else:
                stmt = select(Inventory).where(
                    Inventory.tenant_id == tenant_id, Inventory.sku_id == sku_id
                )
                all_inv = (await self._session.execute(stmt)).scalars().all()
            start = (page - 1) * page_size
            return all_inv[start:start + page_size], len(all_inv)
        return [], 0

    async def get_stock_movements(self, tenant_id: str, sku_id: str = "",
                                  reference_type: str = "", reference_id: str = "",
                                  limit: int = 50) -> Sequence[StockMovement]:
        """查询库存流水"""
        if sku_id:
            return await self._movement_repo.list_by_sku(sku_id, tenant_id, limit=limit)
        if reference_type and reference_id:
            return await self._movement_repo.list_by_reference(reference_type, reference_id, tenant_id)
        return []


class InboundService:
    """
    入库应用服务

    编排入库单的完整生命周期: 创建 → 收货 → 库存调整
    通过 InboundOrder / Inventory / Movement 三个仓储操作数据。
    """

    def __init__(self, session: AsyncSession, inbound_repo: InboundOrderRepository,
                 inventory_repo: InventoryRepository, movement_repo: StockMovementRepository):
        self._session = session
        self._inbound_repo = inbound_repo
        self._inventory_repo = inventory_repo
        self._movement_repo = movement_repo

    async def create(self, tenant_id: str, inbound_no: str, warehouse_id: str,
                     inbound_type: str = "purchase", **kwargs) -> InboundOrder:
        """创建入库单: 持久化"""
        inbound = InboundOrder(
            tenant_id=tenant_id, inbound_no=inbound_no, warehouse_id=warehouse_id,
            inbound_type=inbound_type, created_by=actor_id_var.get(""), **kwargs,
        )
        return await self._inbound_repo.create(inbound)

    async def get_by_id(self, inbound_id: str, tenant_id: str) -> InboundOrder | None:
        """根据ID获取入库单"""
        return await self._inbound_repo.get_by_id(inbound_id, tenant_id)

    async def get_or_raise(self, inbound_id: str, tenant_id: str) -> InboundOrder:
        """根据ID获取入库单，不存在则抛出 NotFoundException"""
        inbound = await self.get_by_id(inbound_id, tenant_id)
        if not inbound:
            raise NotFoundException(message=f"Inbound order '{inbound_id}' not found")
        return inbound

    async def list_all(self, tenant_id: str, status: str = "", warehouse_id: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[InboundOrder], int]:
        """分页查询入库单列表"""
        return await self._inbound_repo.list_by_tenant(
            tenant_id, status=status, warehouse_id=warehouse_id,
            page=page, page_size=page_size,
        )

    async def cancel(self, inbound_id: str, tenant_id: str) -> InboundOrder:
        """取消入库单: 状态校验(pending) → 更新为 cancelled"""
        inbound = await self._inbound_repo.get_by_id(inbound_id, tenant_id)
        if not inbound:
            raise NotFoundException(message=f"Inbound order '{inbound_id}' not found")
        if inbound.status != "pending":
            raise ValidationException(message=f"Cannot cancel inbound order in '{inbound.status}' status")
        inbound.status = "cancelled"
        await self._inbound_repo.update(inbound)
        return inbound

    async def receive(self, inbound_id: str, tenant_id: str, received_items: list[dict]) -> InboundOrder:
        """
        收货: 查询入库单 → 逐项调整库存 → 更新状态

        参数:
            inbound_id: 入库单ID
            tenant_id: 租户ID
            received_items: 收货明细列表 [{sku_id, qty}, ...]
        """
        inbound = await self._inbound_repo.get_by_id(inbound_id, tenant_id)
        if not inbound:
            raise NotFoundException(message=f"Inbound order '{inbound_id}' not found")

        inv_svc = InventoryService(self._session, self._inventory_repo, self._movement_repo)
        for item in received_items:
            await inv_svc.adjust_stock(
                tenant_id=tenant_id, warehouse_id=inbound.warehouse_id, sku_id=item["sku_id"],
                qty_change=item["qty"], movement_type="inbound",
                reference_type="inbound_order", reference_id=inbound_id,
            )
        inbound.status = "received"
        inbound.received_json = json.dumps(received_items, default=str)
        await self._inbound_repo.update(inbound)
        return inbound


class OutboundService:
    """
    出库应用服务

    编排出库单的完整生命周期: 创建 → 发货 → 库存扣减
    通过 OutboundOrder / Inventory / Movement 三个仓储操作数据。
    """

    def __init__(self, session: AsyncSession, outbound_repo: OutboundOrderRepository,
                 inventory_repo: InventoryRepository, movement_repo: StockMovementRepository):
        self._session = session
        self._outbound_repo = outbound_repo
        self._inventory_repo = inventory_repo
        self._movement_repo = movement_repo

    async def create(self, tenant_id: str, outbound_no: str, warehouse_id: str,
                     outbound_type: str = "sales", **kwargs) -> OutboundOrder:
        """创建出库单: 持久化"""
        outbound = OutboundOrder(
            tenant_id=tenant_id, outbound_no=outbound_no, warehouse_id=warehouse_id,
            outbound_type=outbound_type, created_by=actor_id_var.get(""), **kwargs,
        )
        return await self._outbound_repo.create(outbound)

    async def get_by_id(self, outbound_id: str, tenant_id: str) -> OutboundOrder | None:
        """根据ID获取出库单"""
        return await self._outbound_repo.get_by_id(outbound_id, tenant_id)

    async def get_or_raise(self, outbound_id: str, tenant_id: str) -> OutboundOrder:
        """根据ID获取出库单，不存在则抛出 NotFoundException"""
        outbound = await self.get_by_id(outbound_id, tenant_id)
        if not outbound:
            raise NotFoundException(message=f"Outbound order '{outbound_id}' not found")
        return outbound

    async def list_all(self, tenant_id: str, status: str = "", warehouse_id: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[OutboundOrder], int]:
        """分页查询出库单列表"""
        return await self._outbound_repo.list_by_tenant(
            tenant_id, status=status, warehouse_id=warehouse_id,
            page=page, page_size=page_size,
        )

    async def cancel(self, outbound_id: str, tenant_id: str) -> OutboundOrder:
        """取消出库单: 状态校验(pending) → 更新为 cancelled"""
        outbound = await self._outbound_repo.get_by_id(outbound_id, tenant_id)
        if not outbound:
            raise NotFoundException(message=f"Outbound order '{outbound_id}' not found")
        if outbound.status != "pending":
            raise ValidationException(message=f"Cannot cancel outbound order in '{outbound.status}' status")
        outbound.status = "cancelled"
        await self._outbound_repo.update(outbound)
        return outbound

    async def ship(self, outbound_id: str, tenant_id: str, shipped_items: list[dict],
                   tracking_no: str = "", logistics_channel: str = "") -> OutboundOrder:
        """
        发货: 查询出库单 → 逐项扣减库存 → 更新状态

        参数:
            outbound_id: 出库单ID
            tenant_id: 租户ID
            shipped_items: 发货明细列表 [{sku_id, qty}, ...]
            tracking_no: 物流追踪号
            logistics_channel: 物流渠道
        """
        outbound = await self._outbound_repo.get_by_id(outbound_id, tenant_id)
        if not outbound:
            raise NotFoundException(message=f"Outbound order '{outbound_id}' not found")

        inv_svc = InventoryService(self._session, self._inventory_repo, self._movement_repo)
        for item in shipped_items:
            await inv_svc.adjust_stock(
                tenant_id=tenant_id, warehouse_id=outbound.warehouse_id, sku_id=item["sku_id"],
                qty_change=-item["qty"], movement_type="outbound",
                reference_type="outbound_order", reference_id=outbound_id,
            )
        outbound.status = "shipped"
        outbound.shipped_json = json.dumps(shipped_items, default=str)
        outbound.tracking_no = tracking_no
        outbound.logistics_channel = logistics_channel
        await self._outbound_repo.update(outbound)
        return outbound


class QualityInspectionService:
    """
    质检应用服务

    编排质检单的完整生命周期: 创建 → 完成 → 合格入库
    通过 QualityInspection / Inventory / Movement 三个仓储操作数据。
    """

    def __init__(self, session: AsyncSession, inspection_repo: QualityInspectionRepository,
                 inventory_repo: InventoryRepository, movement_repo: StockMovementRepository):
        self._session = session
        self._inspection_repo = inspection_repo
        self._inventory_repo = inventory_repo
        self._movement_repo = movement_repo

    async def create(self, tenant_id: str, inspection_no: str, warehouse_id: str,
                     sku_id: str, quantity_inspected: int, **kwargs) -> QualityInspection:
        """创建质检单: 数量校验 → 领域服务校验 → 确定结果 → 持久化"""
        if quantity_inspected <= 0:
            raise ValidationException(message="Inspected quantity must be positive")
        quantity_passed = kwargs.get("quantity_passed", 0)
        quantity_failed = kwargs.get("quantity_failed", 0)
        errors = QualityInspectionDomainService.validate_inspection(
            quantity_inspected, quantity_passed, quantity_failed
        )
        if errors:
            raise ValidationException(message="; ".join(errors))
        result = QualityInspectionDomainService.determine_result(
            quantity_inspected, quantity_passed, quantity_failed
        )
        inspection = QualityInspection(
            tenant_id=tenant_id, inspection_no=inspection_no,
            warehouse_id=warehouse_id, sku_id=sku_id,
            quantity_inspected=quantity_inspected,
            quantity_passed=quantity_passed, quantity_failed=quantity_failed,
            inspection_result=result,
            **{k: v for k, v in kwargs.items() if hasattr(QualityInspection, k)},
        )
        return await self._inspection_repo.create(inspection)

    async def get_by_id(self, inspection_id: str, tenant_id: str) -> QualityInspection | None:
        """根据ID获取质检单"""
        return await self._inspection_repo.get_by_id(inspection_id, tenant_id)

    async def list_by_warehouse(self, tenant_id: str, warehouse_id: str,
                                 result: str = "", offset: int = 0, limit: int = 20) -> list[QualityInspection]:
        """按仓库查询质检单列表"""
        items = await self._inspection_repo.list_by_warehouse(
            tenant_id, warehouse_id, result=result, offset=offset, limit=limit
        )
        return list(items)

    async def complete_inspection(self, inspection_id: str, tenant_id: str,
                                   quantity_passed: int, quantity_failed: int,
                                   defect_type: str = "", defect_description: str = "",
                                   inspector_id: str = "") -> QualityInspection:
        """
        完成质检: 查询质检单 → 状态校验 → 领域服务校验 → 更新结果 → 合格品入库

        参数:
            inspection_id: 质检单ID
            tenant_id: 租户ID
            quantity_passed: 合格数量
            quantity_failed: 不合格数量
            defect_type: 缺陷类型
            defect_description: 缺陷描述
            inspector_id: 质检员ID
        """
        inspection = await self._inspection_repo.get_by_id(inspection_id, tenant_id)
        if not inspection:
            raise NotFoundException(message=f"Inspection '{inspection_id}' not found")
        if inspection.inspection_result != "pending":
            raise ValidationException(message="Inspection already completed")
        errors = QualityInspectionDomainService.validate_inspection(
            inspection.quantity_inspected, quantity_passed, quantity_failed
        )
        if errors:
            raise ValidationException(message="; ".join(errors))
        inspection.quantity_passed = quantity_passed
        inspection.quantity_failed = quantity_failed
        inspection.inspection_result = QualityInspectionDomainService.determine_result(
            inspection.quantity_inspected, quantity_passed, quantity_failed
        )
        if defect_type:
            inspection.defect_type = defect_type
        if defect_description:
            inspection.defect_description = defect_description
        if inspector_id:
            inspection.inspector_id = inspector_id
        from datetime import UTC, datetime
        inspection.inspected_at = datetime.now(UTC)
        if inspection.inspection_result == "passed":
            inv_svc = InventoryService(self._session, self._inventory_repo, self._movement_repo)
            await inv_svc.adjust_stock(
                tenant_id=tenant_id, warehouse_id=inspection.warehouse_id,
                sku_id=inspection.sku_id, qty_change=quantity_passed,
                movement_type="inbound", reference_type="quality_inspection",
                reference_id=inspection_id,
            )
        await self._inspection_repo.update(inspection)
        return inspection

    async def get_pass_rate(self, tenant_id: str, warehouse_id: str = "",
                             start_date=None, end_date=None) -> dict:
        """获取质检合格率统计"""
        inspections = await self._inspection_repo.list_by_warehouse(
            tenant_id, warehouse_id, offset=0, limit=10000
        )
        if start_date:
            inspections = [i for i in inspections if i.inspected_at and i.inspected_at >= start_date]
        if end_date:
            inspections = [i for i in inspections if i.inspected_at and i.inspected_at <= end_date]
        total_inspected = sum(i.quantity_inspected for i in inspections)
        total_passed = sum(i.quantity_passed for i in inspections)
        return {
            "total_inspections": len(inspections),
            "total_inspected_qty": total_inspected,
            "total_passed_qty": total_passed,
            "pass_rate": QualityInspectionDomainService.calculate_pass_rate(total_inspected, total_passed),
        }


class StockCountService:
    """
    盘点应用服务

    编排盘点单的完整生命周期: 创建 → 开始 → 提交结果 → 差异调整
    通过 StockCount / Inventory / Movement 三个仓储操作数据。
    """

    def __init__(self, session: AsyncSession, count_repo: StockCountRepository,
                 inventory_repo: InventoryRepository, movement_repo: StockMovementRepository):
        self._session = session
        self._count_repo = count_repo
        self._inventory_repo = inventory_repo
        self._movement_repo = movement_repo

    async def create(self, tenant_id: str, count_no: str, warehouse_id: str,
                     count_type: str = "full", **kwargs) -> StockCount:
        """创建盘点单: 类型校验 → 持久化"""
        if count_type not in ("full", "cycle", "spot"):
            raise ValidationException(message="Count type must be 'full', 'cycle' or 'spot'")
        count = StockCount(
            tenant_id=tenant_id, count_no=count_no, warehouse_id=warehouse_id,
            count_type=count_type, created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(StockCount, k)},
        )
        return await self._count_repo.create(count)

    async def get_by_id(self, count_id: str, tenant_id: str) -> StockCount | None:
        """根据ID获取盘点单"""
        return await self._count_repo.get_by_id(count_id, tenant_id)

    async def get_or_raise(self, count_id: str, tenant_id: str) -> StockCount:
        """根据ID获取盘点单，不存在则抛出 NotFoundException"""
        count = await self.get_by_id(count_id, tenant_id)
        if not count:
            raise NotFoundException(message=f"Stock count '{count_id}' not found")
        return count

    async def list_all(self, tenant_id: str, warehouse_id: str = "", status: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[StockCount], int]:
        """分页查询盘点单列表"""
        return await self._count_repo.list_by_tenant(
            tenant_id, status=status, page=page, page_size=page_size
        )

    async def start_count(self, count_id: str, tenant_id: str) -> StockCount:
        """开始盘点: 状态校验 → 更新为 in_progress"""
        count = await self._count_repo.get_by_id(count_id, tenant_id)
        if not count:
            raise NotFoundException(message=f"Stock count '{count_id}' not found")
        if not StockCountDomainService.can_transition(count.status, "in_progress"):
            raise ValidationException(message=f"Cannot start count in '{count.status}' status")
        from datetime import UTC, datetime
        count.status = "in_progress"
        count.started_at = datetime.now(UTC)
        await self._count_repo.update(count)
        return count

    async def submit_count_result(self, count_id: str, tenant_id: str,
                                   count_items: list[dict]) -> StockCount:
        """
        提交盘点结果: 查询盘点单 → 状态校验 → 明细校验 → 差异计算 → 库存调整

        参数:
            count_id: 盘点单ID
            tenant_id: 租户ID
            count_items: 盘点明细 [{sku_id, counted_qty}, ...]
        """
        count = await self._count_repo.get_by_id(count_id, tenant_id)
        if not count:
            raise NotFoundException(message=f"Stock count '{count_id}' not found")
        if count.status != "in_progress":
            raise ValidationException(message="Count must be in 'in_progress' status")
        errors = StockCountDomainService.validate_count_items(count_items)
        if errors:
            raise ValidationException(message="; ".join(errors))
        inv_svc = InventoryService(self._session, self._inventory_repo, self._movement_repo)
        variances = []
        for item in count_items:
            sku_id = item.get("sku_id", "")
            counted_qty = item.get("counted_qty", 0)
            inv = await self._inventory_repo.find_by_warehouse_sku(
                count.warehouse_id, sku_id, tenant_id
            )
            system_qty = inv.qty_on_hand if inv else 0
            variance = StockCountDomainService.calculate_variance(system_qty, counted_qty)
            variances.append(variance)
            if inv and variance["variance"] != 0:
                await inv_svc.adjust_stock(
                    tenant_id=tenant_id, warehouse_id=count.warehouse_id,
                    sku_id=sku_id, qty_change=variance["variance"],
                    movement_type="adjustment", reference_type="stock_count",
                    reference_id=count_id, remark=f"Stock count adjustment: {variance['status']}",
                )
        from datetime import UTC, datetime
        count.result_json = json.dumps(variances, default=str)
        count.status = "completed"
        count.completed_at = datetime.now(UTC)
        await self._count_repo.update(count)
        return count


class WMSQueryService:
    """
    WMS 统计查询服务

    提供仓库运营数据聚合:
    - 仓库统计: 仓库数量、按类型分布
    - 库存统计: SKU数量、库存总值、低库存数
    - 入库统计: 入库单数量、按状态分布
    - 出库统计: 出库单数量、按状态分布
    - 盘点统计: 盘点单数量、差异率
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_warehouse_statistics(self, tenant_id: str) -> dict:
        """仓库统计概览: 仓库数量、按类型/状态分布"""
        stmt = select(Warehouse).where(Warehouse.tenant_id == tenant_id, Warehouse.deleted_at.is_(None))
        warehouses = (await self._session.execute(stmt)).scalars().all()
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for w in warehouses:
            by_type[w.warehouse_type] = by_type.get(w.warehouse_type, 0) + 1
            by_status[w.status] = by_status.get(w.status, 0) + 1
        return {
            "total_warehouses": len(warehouses),
            "by_type": by_type,
            "by_status": by_status,
        }

    async def get_inventory_statistics(self, tenant_id: str, warehouse_id: str = "") -> dict:
        """库存统计概览: SKU数量、库存总值、低库存数、次品数"""
        conditions = [Inventory.tenant_id == tenant_id]
        if warehouse_id:
            conditions.append(Inventory.warehouse_id == warehouse_id)
        stmt = select(Inventory).where(*conditions)
        inventories = (await self._session.execute(stmt)).scalars().all()

        total_skus = len(inventories)
        total_qty_on_hand = sum(i.qty_on_hand for i in inventories)
        total_qty_reserved = sum(i.qty_reserved for i in inventories)
        total_qty_available = sum(i.qty_available for i in inventories)
        total_value = sum(i.qty_on_hand * i.cost_price for i in inventories)
        low_stock_count = sum(1 for i in inventories if i.safety_qty > 0 and i.qty_available <= i.safety_qty)
        defective_count = sum(i.qty_defective for i in inventories)

        return {
            "total_skus": total_skus,
            "total_qty_on_hand": total_qty_on_hand,
            "total_qty_reserved": total_qty_reserved,
            "total_qty_available": total_qty_available,
            "total_stock_value": round(total_value, 2),
            "low_stock_count": low_stock_count,
            "total_defective_qty": defective_count,
        }

    async def get_inbound_statistics(self, tenant_id: str, warehouse_id: str = "") -> dict:
        """入库统计概览: 入库单数量、按状态/类型分布"""
        conditions = [InboundOrder.tenant_id == tenant_id]
        if warehouse_id:
            conditions.append(InboundOrder.warehouse_id == warehouse_id)
        stmt = select(InboundOrder).where(*conditions)
        orders = (await self._session.execute(stmt)).scalars().all()
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for o in orders:
            by_status[o.status] = by_status.get(o.status, 0) + 1
            by_type[o.inbound_type] = by_type.get(o.inbound_type, 0) + 1
        return {
            "total_inbound_orders": len(orders),
            "by_status": by_status,
            "by_type": by_type,
        }

    async def get_outbound_statistics(self, tenant_id: str, warehouse_id: str = "") -> dict:
        """出库统计概览: 出库单数量、按状态/类型分布"""
        conditions = [OutboundOrder.tenant_id == tenant_id]
        if warehouse_id:
            conditions.append(OutboundOrder.warehouse_id == warehouse_id)
        stmt = select(OutboundOrder).where(*conditions)
        orders = (await self._session.execute(stmt)).scalars().all()
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for o in orders:
            by_status[o.status] = by_status.get(o.status, 0) + 1
            by_type[o.outbound_type] = by_type.get(o.outbound_type, 0) + 1
        return {
            "total_outbound_orders": len(orders),
            "by_status": by_status,
            "by_type": by_type,
        }

    async def get_stock_count_statistics(self, tenant_id: str) -> dict:
        """盘点统计概览: 盘点单数量、按状态/类型分布"""
        stmt = select(StockCount).where(StockCount.tenant_id == tenant_id)
        counts = (await self._session.execute(stmt)).scalars().all()
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        completed_with_variance = 0
        for c in counts:
            by_status[c.status] = by_status.get(c.status, 0) + 1
            by_type[c.count_type] = by_type.get(c.count_type, 0) + 1
            if c.status == "completed" and c.result_json:
                result = json.loads(c.result_json) if isinstance(c.result_json, str) else c.result_json
                if any(item.get("variance", 0) != 0 for item in result):
                    completed_with_variance += 1
        return {
            "total_stock_counts": len(counts),
            "by_status": by_status,
            "by_type": by_type,
            "completed_with_variance": completed_with_variance,
        }

    async def get_overview(self, tenant_id: str) -> dict:
        """WMS 运营总览: 聚合仓库/库存/入库/出库/盘点/调拨统计"""
        wh_stats = await self.get_warehouse_statistics(tenant_id)
        inv_stats = await self.get_inventory_statistics(tenant_id)
        in_stats = await self.get_inbound_statistics(tenant_id)
        out_stats = await self.get_outbound_statistics(tenant_id)
        count_stats = await self.get_stock_count_statistics(tenant_id)
        transfer_stats = await self.get_transfer_statistics(tenant_id)
        return {
            "warehouse": wh_stats,
            "inventory": inv_stats,
            "inbound": in_stats,
            "outbound": out_stats,
            "stock_count": count_stats,
            "transfer": transfer_stats,
        }

    async def get_transfer_statistics(self, tenant_id: str) -> dict:
        conditions = [StockTransfer.tenant_id == tenant_id]
        stmt = select(StockTransfer).where(*conditions)
        transfers = (await self._session.execute(stmt)).scalars().all()
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for t in transfers:
            by_status[t.status] = by_status.get(t.status, 0) + 1
            by_type[t.transfer_type] = by_type.get(t.transfer_type, 0) + 1
        return {
            "total_transfers": len(transfers),
            "by_status": by_status,
            "by_type": by_type,
        }


TRANSFER_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["pending_approval", "cancelled"],
    "pending_approval": ["approved", "cancelled"],
    "approved": ["in_transit", "cancelled"],
    "in_transit": ["completed", "cancelled"],
    "completed": [],
    "cancelled": [],
}


class StockTransferService:
    """
    库存调拨应用服务

    编排调拨单的完整生命周期: 创建 → 审批 → 发货(扣减源仓库) → 收货(增加目标仓库)
    通过 Inventory / StockMovement 仓储操作数据。
    """

    def __init__(self, session: AsyncSession, inventory_repo: InventoryRepository,
                 movement_repo: StockMovementRepository):
        self._session = session
        self._inventory_repo = inventory_repo
        self._movement_repo = movement_repo

    async def create(self, tenant_id: str, transfer_no: str, from_warehouse_id: str,
                     to_warehouse_id: str, items: list[dict], **kwargs) -> StockTransfer:
        """
        创建调拨单

        流程: 唯一性校验(transfer_no) → 源≠目标校验 → 明细校验 → 持久化
        """
        existing = select(StockTransfer).where(
            StockTransfer.transfer_no == transfer_no,
            StockTransfer.tenant_id == tenant_id,
        )
        if (await self._session.execute(existing)).scalar_one_or_none():
            raise DuplicateCodeException(message=f"Transfer '{transfer_no}' already exists")
        if from_warehouse_id == to_warehouse_id:
            raise ValidationException(message="Source and target warehouse must be different")
        if not items:
            raise ValidationException(message="Transfer must have at least one item")
        for item in items:
            if not item.get("sku_id"):
                raise ValidationException(message="Each item must have a sku_id")
            if item.get("quantity", 0) <= 0:
                raise ValidationException(message="Each item quantity must be positive")
        transfer = StockTransfer(
            tenant_id=tenant_id, transfer_no=transfer_no,
            from_warehouse_id=from_warehouse_id, to_warehouse_id=to_warehouse_id,
            items_json=json.dumps(items, default=str),
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(StockTransfer, k)},
        )
        self._session.add(transfer)
        await self._session.flush()
        return transfer

    async def get_by_id(self, transfer_id: str, tenant_id: str) -> StockTransfer | None:
        stmt = select(StockTransfer).where(
            StockTransfer.id == transfer_id, StockTransfer.tenant_id == tenant_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, transfer_id: str, tenant_id: str) -> StockTransfer:
        transfer = await self.get_by_id(transfer_id, tenant_id)
        if not transfer:
            raise NotFoundException(message=f"Stock transfer '{transfer_id}' not found")
        return transfer

    async def list_all(self, tenant_id: str, status: str = "", from_warehouse_id: str = "",
                       to_warehouse_id: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[StockTransfer], int]:
        conditions = [StockTransfer.tenant_id == tenant_id]
        if status:
            conditions.append(StockTransfer.status == status)
        if from_warehouse_id:
            conditions.append(StockTransfer.from_warehouse_id == from_warehouse_id)
        if to_warehouse_id:
            conditions.append(StockTransfer.to_warehouse_id == to_warehouse_id)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(StockTransfer).where(*conditions)
        )).scalar() or 0
        stmt = select(StockTransfer).where(*conditions).order_by(
            StockTransfer.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = (await self._session.execute(stmt)).scalars().all()
        return items, total

    async def update_status(self, transfer_id: str, tenant_id: str, new_status: str) -> StockTransfer:
        """更新调拨单状态: 状态机校验 → 更新"""
        transfer = await self.get_or_raise(transfer_id, tenant_id)
        allowed = TRANSFER_STATUS_TRANSITIONS.get(transfer.status, [])
        if new_status not in allowed:
            raise ValidationException(
                message=f"Cannot transition transfer from '{transfer.status}' to '{new_status}'"
            )
        transfer.status = new_status
        await self._session.flush()
        return transfer

    async def ship(self, transfer_id: str, tenant_id: str) -> StockTransfer:
        """
        调拨发货: 校验状态 → 逐项扣减源仓库库存 → 更新状态为in_transit

        流程: 查询调拨单 → 状态校验(approved) → 解析明细 → 逐项扣减源仓库 → 记录流水
        """
        transfer = await self.get_or_raise(transfer_id, tenant_id)
        if transfer.status != "approved":
            raise ValidationException(message="Transfer must be in 'approved' status to ship")
        items = json.loads(transfer.items_json or "[]")
        inv_svc = InventoryService(self._session, self._inventory_repo, self._movement_repo)
        for item in items:
            await inv_svc.adjust_stock(
                tenant_id=tenant_id,
                warehouse_id=transfer.from_warehouse_id,
                sku_id=item["sku_id"],
                qty_change=-item["quantity"],
                movement_type="transfer_out",
                reference_type="stock_transfer",
                reference_id=transfer_id,
                remark=f"Transfer out to {transfer.to_warehouse_id}",
            )
        from datetime import UTC, datetime
        transfer.status = "in_transit"
        transfer.shipped_at = datetime.now(UTC)
        await self._session.flush()
        return transfer

    async def receive(self, transfer_id: str, tenant_id: str,
                      received_items: list[dict] | None = None) -> StockTransfer:
        """
        调拨收货: 校验状态 → 逐项增加目标仓库库存 → 更新状态为completed

        流程: 查询调拨单 → 状态校验(in_transit) → 解析明细 → 逐项增加目标仓库 → 记录流水
        """
        transfer = await self.get_or_raise(transfer_id, tenant_id)
        if transfer.status != "in_transit":
            raise ValidationException(message="Transfer must be in 'in_transit' status to receive")
        items = received_items or json.loads(transfer.items_json or "[]")
        inv_svc = InventoryService(self._session, self._inventory_repo, self._movement_repo)
        for item in items:
            await inv_svc.adjust_stock(
                tenant_id=tenant_id,
                warehouse_id=transfer.to_warehouse_id,
                sku_id=item["sku_id"],
                qty_change=item.get("quantity", 0),
                movement_type="transfer_in",
                reference_type="stock_transfer",
                reference_id=transfer_id,
                remark=f"Transfer in from {transfer.from_warehouse_id}",
            )
        from datetime import UTC, datetime
        transfer.status = "completed"
        transfer.received_at = datetime.now(UTC)
        await self._session.flush()
        return transfer

    async def cancel(self, transfer_id: str, tenant_id: str) -> StockTransfer:
        """取消调拨单: 状态校验(仅draft/pending_approval可取消) → 更新"""
        transfer = await self.get_or_raise(transfer_id, tenant_id)
        if transfer.status not in ("draft", "pending_approval"):
            raise ValidationException(
                message=f"Cannot cancel transfer in '{transfer.status}' status"
            )
        transfer.status = "cancelled"
        await self._session.flush()
        return transfer


class InventorySnapshotService:
    """
    库存快照应用服务

    编排库存快照的生成与查询: 按仓库生成全量快照 → 支持历史对比 → 成本核算基础
    """

    def __init__(self, session: AsyncSession, inventory_repo: InventoryRepository,
                 movement_repo: StockMovementRepository):
        self._session = session
        self._inventory_repo = inventory_repo
        self._movement_repo = movement_repo

    async def generate_snapshot(self, tenant_id: str, warehouse_id: str,
                                snapshot_type: str = "daily") -> dict:
        """
        生成库存快照

        流程: 查询仓库所有库存 → 聚合SKU/数量/成本 → 记录快照时间点
        """
        stmt = select(Inventory).where(
            Inventory.tenant_id == tenant_id,
            Inventory.warehouse_id == warehouse_id,
        )
        inventories = list((await self._session.execute(stmt)).scalars().all())
        from datetime import UTC, datetime
        snapshot_time = datetime.now(UTC)
        total_skus = len(inventories)
        total_qty = sum(inv.qty_on_hand for inv in inventories)
        total_reserved = sum(inv.qty_reserved for inv in inventories)
        total_available = sum(inv.qty_available for inv in inventories)
        items = []
        for inv in inventories:
            items.append({
                "sku_id": inv.sku_id, "qty_on_hand": inv.qty_on_hand,
                "qty_reserved": inv.qty_reserved, "qty_available": inv.qty_available,
                "warehouse_id": inv.warehouse_id,
            })
        snapshot_no = f"SNAP-{warehouse_id[:8]}-{snapshot_time.strftime('%Y%m%d%H%M%S')}"
        return {
            "snapshot_no": snapshot_no, "tenant_id": tenant_id,
            "warehouse_id": warehouse_id, "snapshot_type": snapshot_type,
            "snapshot_time": snapshot_time.isoformat(),
            "total_skus": total_skus, "total_qty": total_qty,
            "total_reserved": total_reserved, "total_available": total_available,
            "items": items,
        }

    async def compare_snapshots(self, tenant_id: str, warehouse_id: str,
                                current_items: list[dict],
                                previous_items: list[dict]) -> dict:
        """
        对比两次快照差异

        流程: 按SKU匹配 → 计算数量变化 → 标记新增/删除/变更SKU
        """
        current_map = {i["sku_id"]: i for i in current_items}
        previous_map = {i["sku_id"]: i for i in previous_items}
        all_sku_ids = set(current_map.keys()) | set(previous_map.keys())
        changes: list[dict] = []
        added_skus = []
        removed_skus = []
        for sku_id in all_sku_ids:
            curr = current_map.get(sku_id)
            prev = previous_map.get(sku_id)
            if curr and not prev:
                added_skus.append(sku_id)
                changes.append({"sku_id": sku_id, "change_type": "added",
                                "current_qty": curr.get("qty_on_hand", 0)})
            elif prev and not curr:
                removed_skus.append(sku_id)
                changes.append({"sku_id": sku_id, "change_type": "removed",
                                "previous_qty": prev.get("qty_on_hand", 0)})
            elif curr and prev:
                diff = curr.get("qty_on_hand", 0) - prev.get("qty_on_hand", 0)
                if diff != 0:
                    changes.append({
                        "sku_id": sku_id, "change_type": "changed",
                        "previous_qty": prev.get("qty_on_hand", 0),
                        "current_qty": curr.get("qty_on_hand", 0),
                        "difference": diff,
                    })
        return {
            "warehouse_id": warehouse_id, "total_changes": len(changes),
            "added_skus": added_skus, "removed_skus": removed_skus,
            "changed_skus": [c["sku_id"] for c in changes if c["change_type"] == "changed"],
            "changes": changes,
        }

    async def get_low_stock_forecast(self, tenant_id: str, warehouse_id: str = "",
                                     days_ahead: int = 7) -> list[dict]:
        """
        低库存预测

        基于近期出库速率，预测未来N天可能缺货的SKU
        """
        from datetime import timedelta
        inv_stmt = select(Inventory).where(Inventory.tenant_id == tenant_id)
        if warehouse_id:
            inv_stmt = inv_stmt.where(Inventory.warehouse_id == warehouse_id)
        inventories = list((await self._session.execute(inv_stmt)).scalars().all())
        from datetime import UTC, datetime
        cutoff = datetime.now(UTC) - timedelta(days=30)
        forecasts = []
        for inv in inventories:
            mvmt_stmt = select(sa_func.coalesce(sa_func.sum(StockMovement.quantity), 0)).where(
                StockMovement.tenant_id == tenant_id,
                StockMovement.warehouse_id == inv.warehouse_id,
                StockMovement.sku_id == inv.sku_id,
                StockMovement.movement_type.in_(["sale_out", "transfer_out", "adjustment"]),
                StockMovement.created_at >= cutoff,
            )
            total_out = (await self._session.execute(mvmt_stmt)).scalar() or 0
            daily_rate = total_out / 30.0 if total_out > 0 else 0
            if daily_rate > 0:
                days_of_stock = inv.qty_available / daily_rate if daily_rate > 0 else 999
                if days_of_stock <= days_ahead:
                    forecasts.append({
                        "warehouse_id": inv.warehouse_id, "sku_id": inv.sku_id,
                        "current_qty": inv.qty_on_hand, "available_qty": inv.qty_available,
                        "daily_out_rate": round(daily_rate, 2),
                        "days_of_stock": round(days_of_stock, 1),
                        "risk_level": "critical" if days_of_stock <= 2 else "warning",
                    })
        forecasts.sort(key=lambda x: x["days_of_stock"])
        return forecasts


class WavePickService:
    """
    波次拣货服务

    编排波次拣货流程: 订单分组 → 波次生成 → 拣货任务分配 → 拣货确认
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_wave(self, tenant_id: str, warehouse_id: str,
                           order_ids: list[str], wave_strategy: str = "time_window") -> dict:
        """
        创建拣货波次

        流程: 订单校验 → 按策略分组 → 生成波次 → 创建拣货任务
        """
        from erp.shared.cross_domain_query import OrderQueryService
        orders = []
        for oid in order_ids:
            order = (await self._session.execute(
                select(SalesOrder).where(SalesOrder.id == oid, SalesOrder.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if order and order.status in ("confirmed", "processing"):
                orders.append(order)
        if not orders:
            return {"wave_id": None, "message": "No eligible orders for wave picking"}
        pick_tasks = []
        sku_locations = await self._resolve_sku_locations(tenant_id, warehouse_id)
        for order in orders:
            items = (await self._session.execute(
                select(SalesOrderItem).where(SalesOrderItem.order_id == str(order.id))
            )).scalars().all()
            for item in items:
                location = sku_locations.get(item.sku_id, "unknown")
                pick_tasks.append({
                    "order_id": str(order.id), "order_no": order.order_no,
                    "sku_id": item.sku_id, "quantity": item.quantity,
                    "location": location, "status": "pending",
                })
        pick_tasks.sort(key=lambda x: x["location"])
        wave_no = f"WAVE-{warehouse_id[:8]}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        return {
            "wave_no": wave_no, "warehouse_id": warehouse_id,
            "strategy": wave_strategy, "order_count": len(orders),
            "pick_task_count": len(pick_tasks), "pick_tasks": pick_tasks,
        }

    async def confirm_pick(self, tenant_id: str, wave_no: str,
                            pick_results: list[dict]) -> dict:
        """确认拣货结果"""
        confirmed = 0
        shortages = []
        for result in pick_results:
            if result.get("picked_qty", 0) < result.get("required_qty", 0):
                shortages.append({
                    "sku_id": result.get("sku_id"),
                    "required": result.get("required_qty"),
                    "picked": result.get("picked_qty"),
                    "shortage": result.get("required_qty", 0) - result.get("picked_qty", 0),
                })
            confirmed += 1
        return {
            "wave_no": wave_no, "confirmed_count": confirmed,
            "shortage_count": len(shortages), "shortages": shortages,
        }

    async def _resolve_sku_locations(self, tenant_id: str, warehouse_id: str) -> dict:
        try:
            stmt = select(Inventory).where(
                Inventory.tenant_id == tenant_id, Inventory.warehouse_id == warehouse_id)
            inventories = (await self._session.execute(stmt)).scalars().all()
            return {inv.sku_id: inv.location_code or "default" for inv in inventories}
        except Exception:
            return {}


class InventoryAlertService:
    """
    库存预警服务

    多级预警: 缺货/低库存/超储/滞销/效期预警
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def scan_all_alerts(self, tenant_id: str, warehouse_id: str = "") -> dict:
        """扫描全部库存预警"""
        alerts = []
        alerts.extend(await self._scan_stockout(tenant_id, warehouse_id))
        alerts.extend(await self._scan_low_stock(tenant_id, warehouse_id))
        alerts.extend(await self._scan_overstock(tenant_id, warehouse_id))
        alerts.extend(await self._scan_dead_stock(tenant_id, warehouse_id))
        alerts.sort(key=lambda x: {"critical": 0, "warning": 1, "info": 2}.get(x["severity"], 3))
        return {
            "total_alerts": len(alerts),
            "critical_count": sum(1 for a in alerts if a["severity"] == "critical"),
            "warning_count": sum(1 for a in alerts if a["severity"] == "warning"),
            "info_count": sum(1 for a in alerts if a["severity"] == "info"),
            "alerts": alerts,
        }

    async def _scan_stockout(self, tenant_id: str, warehouse_id: str) -> list[dict]:
        conditions = [Inventory.tenant_id == tenant_id, Inventory.qty_available <= 0]
        if warehouse_id:
            conditions.append(Inventory.warehouse_id == warehouse_id)
        items = (await self._session.execute(
            select(Inventory).where(*conditions)
        )).scalars().all()
        return [{"type": "stockout", "severity": "critical", "sku_id": i.sku_id,
                 "warehouse_id": i.warehouse_id, "qty_available": i.qty_available} for i in items]

    async def _scan_low_stock(self, tenant_id: str, warehouse_id: str) -> list[dict]:
        conditions = [Inventory.tenant_id == tenant_id, Inventory.qty_available > 0, Inventory.qty_available <= 10]
        if warehouse_id:
            conditions.append(Inventory.warehouse_id == warehouse_id)
        items = (await self._session.execute(
            select(Inventory).where(*conditions)
        )).scalars().all()
        return [{"type": "low_stock", "severity": "warning", "sku_id": i.sku_id,
                 "warehouse_id": i.warehouse_id, "qty_available": i.qty_available} for i in items]

    async def _scan_overstock(self, tenant_id: str, warehouse_id: str) -> list[dict]:
        conditions = [Inventory.tenant_id == tenant_id, Inventory.qty_on_hand >= 1000]
        if warehouse_id:
            conditions.append(Inventory.warehouse_id == warehouse_id)
        items = (await self._session.execute(
            select(Inventory).where(*conditions)
        )).scalars().all()
        return [{"type": "overstock", "severity": "info", "sku_id": i.sku_id,
                 "warehouse_id": i.warehouse_id, "qty_on_hand": i.qty_on_hand} for i in items]

    async def _scan_dead_stock(self, tenant_id: str, warehouse_id: str) -> list[dict]:
        from datetime import timedelta
        conditions = [Inventory.tenant_id == tenant_id, Inventory.qty_on_hand > 0]
        if warehouse_id:
            conditions.append(Inventory.warehouse_id == warehouse_id)
        items = (await self._session.execute(
            select(Inventory).where(*conditions)
        )).scalars().all()
        alerts = []
        cutoff = datetime.now(UTC) - timedelta(days=90)
        for inv in items:
            last_out = (await self._session.execute(
                select(StockMovement).where(
                    StockMovement.tenant_id == tenant_id,
                    StockMovement.sku_id == inv.sku_id,
                    StockMovement.warehouse_id == inv.warehouse_id,
                    StockMovement.movement_type.in_(["sale_out", "transfer_out"]),
                ).order_by(StockMovement.created_at.desc()).limit(1)
            )).scalar_one_or_none()
            if not last_out or last_out.created_at < cutoff:
                alerts.append({"type": "dead_stock", "severity": "warning", "sku_id": inv.sku_id,
                               "warehouse_id": inv.warehouse_id, "qty_on_hand": inv.qty_on_hand,
                               "last_movement": str(last_out.created_at) if last_out else "never"})
        return alerts


class LocationOptimizationService:
    """
    库位优化服务

    基于出库频率和ABC分类优化库位分配: 高频SKU近出口/关联SKU相邻/重量分区
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def analyze_and_suggest(self, tenant_id: str, warehouse_id: str) -> dict:
        """
        分析库位并给出优化建议

        流程: ABC分类 → 出库频率统计 → 关联性分析 → 生成优化方案
        """
        abc_result = await self._abc_classification(tenant_id, warehouse_id)
        frequency_map = await self._calculate_pick_frequency(tenant_id, warehouse_id)
        suggestions = self._generate_suggestions(abc_result, frequency_map)
        return {
            "warehouse_id": warehouse_id,
            "abc_classification": abc_result,
            "high_frequency_skus": len([s for s in frequency_map if frequency_map[s] >= 10]),
            "suggestions": suggestions,
        }

    async def _abc_classification(self, tenant_id: str, warehouse_id: str) -> dict:
        from datetime import timedelta
        cutoff = datetime.now(UTC) - timedelta(days=90)
        stmt = select(Inventory).where(Inventory.tenant_id == tenant_id, Inventory.warehouse_id == warehouse_id)
        inventories = (await self._session.execute(stmt)).scalars().all()
        sku_values = []
        for inv in inventories:
            total_out = (await self._session.execute(
                select(sa_func.coalesce(sa_func.sum(StockMovement.quantity), 0)).where(
                    StockMovement.tenant_id == tenant_id,
                    StockMovement.sku_id == inv.sku_id,
                    StockMovement.warehouse_id == warehouse_id,
                    StockMovement.movement_type.in_(["sale_out", "transfer_out"]),
                    StockMovement.created_at >= cutoff,
                )
            )).scalar() or 0
            sku_values.append({"sku_id": inv.sku_id, "movement_count": total_out, "current_location": inv.location_code or ""})
        sku_values.sort(key=lambda x: x["movement_count"], reverse=True)
        total = len(sku_values) or 1
        a_count = max(1, int(total * 0.2))
        b_count = max(1, int(total * 0.3))
        return {
            "A": sku_values[:a_count],
            "B": sku_values[a_count:a_count + b_count],
            "C": sku_values[a_count + b_count:],
        }

    async def _calculate_pick_frequency(self, tenant_id: str, warehouse_id: str) -> dict:
        from datetime import timedelta
        cutoff = datetime.now(UTC) - timedelta(days=30)
        movements = (await self._session.execute(
            select(StockMovement.sku_id, sa_func.count()).where(
                StockMovement.tenant_id == tenant_id,
                StockMovement.warehouse_id == warehouse_id,
                StockMovement.movement_type.in_(["sale_out", "transfer_out"]),
                StockMovement.created_at >= cutoff,
            ).group_by(StockMovement.sku_id)
        )).all()
        return {r[0]: r[1] for r in movements}

    def _generate_suggestions(self, abc_result: dict, frequency_map: dict) -> list[dict]:
        suggestions = []
        for sku in abc_result.get("A", []):
            suggestions.append({
                "sku_id": sku["sku_id"], "current_location": sku["current_location"],
                "suggested_zone": "near_exit", "reason": "A类高频SKU，建议放置于出口附近",
                "priority": "high",
            })
        for sku in abc_result.get("C", []):
            if sku["current_location"] and "near" in sku["current_location"].lower():
                suggestions.append({
                    "sku_id": sku["sku_id"], "current_location": sku["current_location"],
                    "suggested_zone": "deep_storage", "reason": "C类低频SKU，建议移至深处存储区",
                    "priority": "low",
                })
        return suggestions


from datetime import UTC, datetime
