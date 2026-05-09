"""
SOM 模块依赖注入工厂 - 提供所有应用服务的 FastAPI Depends 工厂函数

本模块将仓储接口的创建与服务的组装集中管理，
路由层通过 Depends(get_xxx_service) 获取已注入仓储的服务实例，
实现控制反转（IoC）和依赖倒置（DIP）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends

from erp.modules.som.application.services import (
    AlertRecordService,
    AlertRuleService,
    ListingBatchJobService,
    ListingOptimizationService,
    ListingService,
    OperationMonitorService,
    PriceRuleService,
    StoreService,
)
from erp.modules.som.domain.repositories import (
    AlertRecordRepository,
    AlertRuleRepository,
    ListingBatchJobRepository,
    ListingOptimizationRepository,
    ListingRepository,
    OperationMonitorRepository,
    PriceRuleRepository,
    StoreRepository,
)
from erp.modules.som.infrastructure.repositories import (
    SqlAlertRecordRepository,
    SqlAlertRuleRepository,
    SqlListingBatchJobRepository,
    SqlListingOptimizationRepository,
    SqlListingRepository,
    SqlOperationMonitorRepository,
    SqlPriceRuleRepository,
    SqlStoreRepository,
)
from erp.shared.db.session import get_db_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _get_store_repo(session: AsyncSession) -> StoreRepository:
    return SqlStoreRepository(session)


def _get_listing_repo(session: AsyncSession) -> ListingRepository:
    return SqlListingRepository(session)


def _get_price_rule_repo(session: AsyncSession) -> PriceRuleRepository:
    return SqlPriceRuleRepository(session)


def _get_batch_job_repo(session: AsyncSession) -> ListingBatchJobRepository:
    return SqlListingBatchJobRepository(session)


def _get_monitor_repo(session: AsyncSession) -> OperationMonitorRepository:
    return SqlOperationMonitorRepository(session)


def _get_optimization_repo(session: AsyncSession) -> ListingOptimizationRepository:
    return SqlListingOptimizationRepository(session)


def _get_alert_rule_repo(session: AsyncSession) -> AlertRuleRepository:
    return SqlAlertRuleRepository(session)


def _get_alert_record_repo(session: AsyncSession) -> AlertRecordRepository:
    return SqlAlertRecordRepository(session)


async def get_store_service(session: AsyncSession = Depends(get_db_session)) -> StoreService:
    return StoreService(session=session, store_repo=_get_store_repo(session))


async def get_listing_service(session: AsyncSession = Depends(get_db_session)) -> ListingService:
    return ListingService(session=session, listing_repo=_get_listing_repo(session),
                          store_repo=_get_store_repo(session), price_rule_repo=_get_price_rule_repo(session))


async def get_price_rule_service(session: AsyncSession = Depends(get_db_session)) -> PriceRuleService:
    return PriceRuleService(session=session, price_rule_repo=_get_price_rule_repo(session),
                            listing_repo=_get_listing_repo(session))


async def get_batch_job_service(session: AsyncSession = Depends(get_db_session)) -> ListingBatchJobService:
    return ListingBatchJobService(session=session, batch_job_repo=_get_batch_job_repo(session),
                                   listing_repo=_get_listing_repo(session))


async def get_operation_monitor_service(session: AsyncSession = Depends(get_db_session)) -> OperationMonitorService:
    return OperationMonitorService(session=session, monitor_repo=_get_monitor_repo(session))


async def get_optimization_service(session: AsyncSession = Depends(get_db_session)) -> ListingOptimizationService:
    return ListingOptimizationService(session=session, optimization_repo=_get_optimization_repo(session),
                                       listing_repo=_get_listing_repo(session))


async def get_alert_rule_service(session: AsyncSession = Depends(get_db_session)) -> AlertRuleService:
    return AlertRuleService(session=session, alert_rule_repo=_get_alert_rule_repo(session),
                             alert_record_repo=_get_alert_record_repo(session))


async def get_alert_record_service(session: AsyncSession = Depends(get_db_session)) -> AlertRecordService:
    return AlertRecordService(session=session, alert_record_repo=_get_alert_record_repo(session),
                               alert_rule_repo=_get_alert_rule_repo(session))
