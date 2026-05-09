"""
FBA 模块依赖注入工厂 - 提供所有应用服务的 FastAPI Depends 工厂函数

本模块将仓储接口的创建与服务的组装集中管理，
路由层通过 Depends(get_xxx_service) 获取已注入仓储的服务实例，
实现控制反转（IoC）和依赖倒置（DIP）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends

from erp.modules.fba.application.services import (
    FBAQueryService,
    FbaBoxLabelService,
    FbaFeeService,
    FbaInboundPlanService,
    FbaInventoryService,
    FbaReplenishmentPlanService,
    FbaShipmentService,
)
from erp.modules.fba.domain.repositories import (
    FbaBoxLabelRepository,
    FbaFeeRepository,
    FbaInboundPlanRepository,
    FbaInventoryRepository,
    FbaReplenishmentPlanRepository,
    FbaShipmentRepository,
)
from erp.modules.fba.infrastructure.repositories import (
    SqlFbaBoxLabelRepository,
    SqlFbaFeeRepository,
    SqlFbaInboundPlanRepository,
    SqlFbaInventoryRepository,
    SqlFbaReplenishmentPlanRepository,
    SqlFbaShipmentRepository,
)
from erp.shared.db.session import get_db_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _get_shipment_repo(session: AsyncSession) -> FbaShipmentRepository:
    return SqlFbaShipmentRepository(session)


def _get_inventory_repo(session: AsyncSession) -> FbaInventoryRepository:
    return SqlFbaInventoryRepository(session)


def _get_fee_repo(session: AsyncSession) -> FbaFeeRepository:
    return SqlFbaFeeRepository(session)


def _get_box_label_repo(session: AsyncSession) -> FbaBoxLabelRepository:
    return SqlFbaBoxLabelRepository(session)


def _get_replenishment_repo(session: AsyncSession) -> FbaReplenishmentPlanRepository:
    return SqlFbaReplenishmentPlanRepository(session)


def _get_inbound_plan_repo(session: AsyncSession) -> FbaInboundPlanRepository:
    return SqlFbaInboundPlanRepository(session)


async def get_shipment_service(session: AsyncSession = Depends(get_db_session)) -> FbaShipmentService:
    return FbaShipmentService(session=session, shipment_repo=_get_shipment_repo(session))


async def get_inventory_service(session: AsyncSession = Depends(get_db_session)) -> FbaInventoryService:
    return FbaInventoryService(session=session, inventory_repo=_get_inventory_repo(session))


async def get_fee_service(session: AsyncSession = Depends(get_db_session)) -> FbaFeeService:
    return FbaFeeService(session=session, fee_repo=_get_fee_repo(session))


async def get_box_label_service(session: AsyncSession = Depends(get_db_session)) -> FbaBoxLabelService:
    return FbaBoxLabelService(session=session, box_label_repo=_get_box_label_repo(session))


async def get_replenishment_service(session: AsyncSession = Depends(get_db_session)) -> FbaReplenishmentPlanService:
    return FbaReplenishmentPlanService(session=session, replenishment_repo=_get_replenishment_repo(session))


async def get_inbound_plan_service(session: AsyncSession = Depends(get_db_session)) -> FbaInboundPlanService:
    return FbaInboundPlanService(session=session, inbound_plan_repo=_get_inbound_plan_repo(session))


async def get_fba_query_service(session: AsyncSession = Depends(get_db_session)) -> FBAQueryService:
    return FBAQueryService(session=session)
