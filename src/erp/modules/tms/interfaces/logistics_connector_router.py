"""
TMS 物流连接器路由

提供物流连接器的创建、面单申请、轨迹查询、运费报价、
发货调度、健康检查等接口。
内部域路径规范: /tms/api/v1/logistics-connectors
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from erp.modules.tms.application.dtos import (
    ConnectorCreateRequest,
    DispatchCreateRequest,
    FreightQuoteRequest,
    LabelApplyRequest,
    TrackingQueryRequest,
)
from erp.modules.tms.domain.logistics_connector_models import LogisticsConnectorService
from erp.modules.tms.interfaces.deps import get_logistics_connector_service
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import Result

router = APIRouter(prefix="/tms/v1/logistics-connectors", tags=["TMS-LogisticsConnector"])


@router.post("/connectors", response_model=None)
async def create_connector(
    req: ConnectorCreateRequest,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    """创建物流连接器"""
    c = await svc.create_connector(
        tenant_id=tenant_id_var.get(""), connector_name=req.connector_name,
        connector_code=req.connector_code, carrier_name=req.carrier_name,
        carrier_code=req.carrier_code, connector_type=req.connector_type,
        api_base_url=req.api_base_url, auth_type=req.auth_type,
        auth_config=req.auth_config, supported_services=req.supported_services,
        supported_label_formats=req.supported_label_formats,
        supported_origins=req.supported_origins,
        supported_destinations=req.supported_destinations,
        rate_limit_per_minute=req.rate_limit_per_minute,
        timeout_seconds=req.timeout_seconds, max_retries=req.max_retries,
        description=req.description,
    )
    return Result.ok(
        data={"id": c.id, "connector_name": c.connector_name, "connector_code": c.connector_code,
              "carrier_name": c.carrier_name, "carrier_code": c.carrier_code,
              "connector_type": c.connector_type, "is_active": c.is_active},
        trace_id=trace_id_var.get(""),
    )


@router.get("/connectors", response_model=None)
async def list_connectors(
    connector_type: str = Query(default=""),
    carrier_code: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    """分页查询物流连接器列表"""
    connectors, total = await svc.list_connectors(
        tenant_id_var.get(""), connector_type=connector_type,
        carrier_code=carrier_code, page=page, page_size=page_size,
    )
    items = [
        {"id": c.id, "connector_name": c.connector_name, "connector_code": c.connector_code,
         "carrier_name": c.carrier_name, "carrier_code": c.carrier_code,
         "connector_type": c.connector_type, "is_active": c.is_active,
         "health_status": c.health_status,
         "supported_services": c.supported_services_json,
         "supported_label_formats": c.supported_label_formats_json,
         "supported_destinations": c.supported_destinations_json,
         "description": c.description}
        for c in connectors
    ]
    return Result.paginate(items=items, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/labels", response_model=None)
async def request_label(
    req: LabelApplyRequest,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    """申请面单 (通过连接器)"""
    label = await svc.request_label(
        tenant_id=tenant_id_var.get(""), connector_id=req.connector_id,
        shipment_id=req.shipment_id, service_code=req.service_code,
        label_format=req.label_format, shipper=req.shipper,
        recipient=req.recipient, packages=req.packages,
        request_params=req.request_params,
    )
    return Result.ok(
        data={"id": label.id, "shipment_id": label.shipment_id,
              "tracking_number": label.tracking_number, "label_status": label.label_status,
              "label_format": label.label_format, "carrier_code": label.carrier_code},
        trace_id=trace_id_var.get(""),
    )


@router.post("/tracking", response_model=None)
async def query_tracking(
    req: TrackingQueryRequest,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    """查询物流轨迹 (通过连接器)"""
    record = await svc.query_tracking(
        tenant_id=tenant_id_var.get(""), connector_id=req.connector_id,
        tracking_number=req.tracking_number, shipment_id=req.shipment_id,
        carrier_code=req.carrier_code,
    )
    return Result.ok(
        data={"id": record.id, "tracking_number": record.tracking_number,
              "current_status": record.current_status, "carrier_code": record.carrier_code,
              "events": record.events_json, "sync_count": record.sync_count},
        trace_id=trace_id_var.get(""),
    )


@router.post("/freight-quotes", response_model=None)
async def request_freight_quote(
    req: FreightQuoteRequest,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    """请求运费报价 (通过连接器)"""
    quote = await svc.request_freight_quote(
        tenant_id=tenant_id_var.get(""), connector_id=req.connector_id,
        origin_country=req.origin_country, destination_country=req.destination_country,
        weight_grams=req.weight_grams, dimensions=req.dimensions,
        origin_zip=req.origin_zip, destination_zip=req.destination_zip,
        service_code=req.service_code,
    )
    return Result.ok(
        data={"id": quote.id, "quote_request_id": quote.quote_request_id,
              "carrier_code": quote.carrier_code, "service_code": quote.service_code,
              "total_amount": quote.total_amount, "currency": quote.currency,
              "estimated_days_min": quote.estimated_days_min,
              "estimated_days_max": quote.estimated_days_max},
        trace_id=trace_id_var.get(""),
    )


@router.post("/dispatches", response_model=None)
async def create_dispatch(
    req: DispatchCreateRequest,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    """创建发货调度 (通过连接器)"""
    dispatch = await svc.create_dispatch(
        tenant_id=tenant_id_var.get(""), connector_id=req.connector_id,
        shipment_id=req.shipment_id, service_code=req.service_code,
        packages=req.packages, request_params=req.request_params,
    )
    return Result.ok(
        data={"id": dispatch.id, "shipment_id": dispatch.shipment_id,
              "tracking_number": dispatch.tracking_number,
              "dispatch_status": dispatch.dispatch_status,
              "carrier_code": dispatch.carrier_code},
        trace_id=trace_id_var.get(""),
    )


@router.post("/dispatches/{dispatch_id}/cancel", response_model=None)
async def cancel_dispatch(
    dispatch_id: str,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    """取消发货调度"""
    dispatch = await svc.cancel_dispatch(dispatch_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": dispatch.id, "dispatch_status": dispatch.dispatch_status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/connectors/{connector_id}/health-check", response_model=None)
async def health_check(
    connector_id: str,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    """连接器健康检查"""
    result = await svc.health_check(connector_id, tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/init-defaults", response_model=None)
async def init_defaults(
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    """初始化默认物流连接器"""
    connectors = await svc.init_default_connectors(tenant_id_var.get(""))
    return Result.ok(
        data={"initialized_count": len(connectors)},
        trace_id=trace_id_var.get(""),
    )
