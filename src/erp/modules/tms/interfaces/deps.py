"""
TMS 模块依赖注入工厂

提供 FastAPI Depends() 可用的仓储 / 服务工厂函数，
实现「请求 → Session → 仓储 → 服务」的完整注入链路。
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.tms.application.services import (
    BatchService,
    CarrierPerformanceService,
    FreightTemplateService,
    LogisticsProviderService,
    ShipmentService,
    ShippingMethodService,
    TMSQueryService,
    TrackingService,
)
from erp.modules.tms.domain.logistics_connector_models import LogisticsConnectorService
from erp.modules.tms.domain.repositories import (
    DispatchRecordRepository,
    FreightQuoteRepository,
    FreightTemplateRepository,
    LogisticsConnectorRepository,
    LogisticsProviderRepository,
    LogisticsStrategyExecutionLogRepository,
    LogisticsStrategyRepository,
    ShipmentLabelRepository,
    ShipmentRepository,
    ShippingBatchRepository,
    ShippingMethodRepository,
    TrackingRecordRepository,
)
from erp.modules.tms.domain.strategy_models import LogisticsStrategyService
from erp.modules.tms.infrastructure.repositories import (
    SqlDispatchRecordRepository,
    SqlFreightQuoteRepository,
    SqlFreightTemplateRepository,
    SqlLogisticsConnectorRepository,
    SqlLogisticsProviderRepository,
    SqlLogisticsStrategyExecutionLogRepository,
    SqlLogisticsStrategyRepository,
    SqlShipmentLabelRepository,
    SqlShipmentRepository,
    SqlShippingBatchRepository,
    SqlShippingMethodRepository,
    SqlTrackingRecordRepository,
)
from erp.shared.db.session import get_db_session


def _provider_repo(session: AsyncSession = Depends(get_db_session)) -> LogisticsProviderRepository:
    return SqlLogisticsProviderRepository(session)


def _method_repo(session: AsyncSession = Depends(get_db_session)) -> ShippingMethodRepository:
    return SqlShippingMethodRepository(session)


def _shipment_repo(session: AsyncSession = Depends(get_db_session)) -> ShipmentRepository:
    return SqlShipmentRepository(session)


def _template_repo(session: AsyncSession = Depends(get_db_session)) -> FreightTemplateRepository:
    return SqlFreightTemplateRepository(session)


def _strategy_repo(session: AsyncSession = Depends(get_db_session)) -> LogisticsStrategyRepository:
    return SqlLogisticsStrategyRepository(session)


def _strategy_log_repo(session: AsyncSession = Depends(get_db_session)) -> LogisticsStrategyExecutionLogRepository:
    return SqlLogisticsStrategyExecutionLogRepository(session)


def _connector_repo(session: AsyncSession = Depends(get_db_session)) -> LogisticsConnectorRepository:
    return SqlLogisticsConnectorRepository(session)


def _label_repo(session: AsyncSession = Depends(get_db_session)) -> ShipmentLabelRepository:
    return SqlShipmentLabelRepository(session)


def _tracking_record_repo(session: AsyncSession = Depends(get_db_session)) -> TrackingRecordRepository:
    return SqlTrackingRecordRepository(session)


def _quote_repo(session: AsyncSession = Depends(get_db_session)) -> FreightQuoteRepository:
    return SqlFreightQuoteRepository(session)


def _dispatch_repo(session: AsyncSession = Depends(get_db_session)) -> DispatchRecordRepository:
    return SqlDispatchRecordRepository(session)


def _batch_repo(session: AsyncSession = Depends(get_db_session)) -> ShippingBatchRepository:
    return SqlShippingBatchRepository(session)


def get_logistics_provider_service(
    session: AsyncSession = Depends(get_db_session),
    provider_repo: LogisticsProviderRepository = Depends(_provider_repo),
) -> LogisticsProviderService:
    """获取物流商服务实例 — 注入 LogisticsProviderRepository"""
    return LogisticsProviderService(session=session, provider_repo=provider_repo)


def get_shipment_service(
    session: AsyncSession = Depends(get_db_session),
    shipment_repo: ShipmentRepository = Depends(_shipment_repo),
) -> ShipmentService:
    """获取发货单服务实例 — 注入 ShipmentRepository"""
    return ShipmentService(session=session, shipment_repo=shipment_repo)


def get_shipping_method_service(
    session: AsyncSession = Depends(get_db_session),
    method_repo: ShippingMethodRepository = Depends(_method_repo),
) -> ShippingMethodService:
    """获取配送方式服务实例 — 注入 ShippingMethodRepository"""
    return ShippingMethodService(session=session, method_repo=method_repo)


def get_freight_template_service(
    session: AsyncSession = Depends(get_db_session),
    template_repo: FreightTemplateRepository = Depends(_template_repo),
) -> FreightTemplateService:
    """获取运费模板服务实例 — 注入 FreightTemplateRepository"""
    return FreightTemplateService(session=session, template_repo=template_repo)


def get_tracking_service(
    session: AsyncSession = Depends(get_db_session),
    shipment_repo: ShipmentRepository = Depends(_shipment_repo),
) -> TrackingService:
    """获取物流追踪服务实例 — 注入 ShipmentRepository"""
    return TrackingService(session=session, shipment_repo=shipment_repo)


def get_logistics_strategy_service(
    session: AsyncSession = Depends(get_db_session),
    strategy_repo: LogisticsStrategyRepository = Depends(_strategy_repo),
    strategy_log_repo: LogisticsStrategyExecutionLogRepository = Depends(_strategy_log_repo),
) -> LogisticsStrategyService:
    """获取物流策略服务实例 — 注入 Strategy + ExecutionLog 两个仓储"""
    return LogisticsStrategyService(
        session=session,
        strategy_repo=strategy_repo,
        strategy_log_repo=strategy_log_repo,
    )


def get_logistics_connector_service(
    session: AsyncSession = Depends(get_db_session),
    connector_repo: LogisticsConnectorRepository = Depends(_connector_repo),
    label_repo: ShipmentLabelRepository = Depends(_label_repo),
    tracking_record_repo: TrackingRecordRepository = Depends(_tracking_record_repo),
    quote_repo: FreightQuoteRepository = Depends(_quote_repo),
    dispatch_repo: DispatchRecordRepository = Depends(_dispatch_repo),
) -> LogisticsConnectorService:
    """获取物流连接器服务实例 — 注入 Connector / Label / Tracking / Quote / Dispatch 五个仓储"""
    return LogisticsConnectorService(
        session=session,
        connector_repo=connector_repo,
        label_repo=label_repo,
        tracking_record_repo=tracking_record_repo,
        quote_repo=quote_repo,
        dispatch_repo=dispatch_repo,
    )


def get_batch_service(
    session: AsyncSession = Depends(get_db_session),
    batch_repo: ShippingBatchRepository = Depends(_batch_repo),
    shipment_repo: ShipmentRepository = Depends(_shipment_repo),
) -> BatchService:
    """获取发货批次服务实例 — 注入 Batch + Shipment 两个仓储"""
    return BatchService(session=session, batch_repo=batch_repo, shipment_repo=shipment_repo)


def get_carrier_performance_service(
    session: AsyncSession = Depends(get_db_session),
    shipment_repo: ShipmentRepository = Depends(_shipment_repo),
    provider_repo: LogisticsProviderRepository = Depends(_provider_repo),
) -> CarrierPerformanceService:
    """获取物流商绩效服务实例 — 注入 Shipment + Provider 两个仓储"""
    return CarrierPerformanceService(session=session, shipment_repo=shipment_repo, provider_repo=provider_repo)


def get_tms_query_service(
    session: AsyncSession = Depends(get_db_session),
) -> TMSQueryService:
    """获取TMS统计查询服务实例"""
    return TMSQueryService(session=session)
