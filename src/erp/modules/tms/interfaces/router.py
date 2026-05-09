"""
TMS 模块主路由

提供物流商、发货单、配送方式、运费计算、面单、批次等核心接口。
内部域路径规范: /tms/api/v1/{resource}
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from erp.modules.tms.application.dtos import (
    BatchCreateRequest,
    ConnectorCreateRequest,
    ConnectorUpdateRequest,
    DispatchCancelRequest,
    DispatchCreateRequest,
    FreightCalculateRequest,
    FreightQuoteRequest,
    FreightTemplateCreateRequest,
    FreightTemplateUpdateRequest,
    LabelApplyRequest,
    LabelRequest,
    ProviderCreateRequest,
    RateEstimateRequest,
    ShipmentBatchStatusRequest,
    ShipmentCreateRequest,
    ShipmentSearchRequest,
    ShippingMethodCreateRequest,
    ShippingMethodUpdateRequest,
    StrategyCreateRequest,
    StrategyExecutionRequest,
    StrategyUpdateRequest,
    TrackingQueryRequest,
    TrackingUpdateRequest,
)
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
from erp.modules.tms.domain.strategy_models import LogisticsStrategyService
from erp.modules.tms.interfaces.deps import (
    get_batch_service,
    get_carrier_performance_service,
    get_freight_template_service,
    get_logistics_connector_service,
    get_logistics_provider_service,
    get_logistics_strategy_service,
    get_shipping_method_service,
    get_shipment_service,
    get_tms_query_service,
    get_tracking_service,
)
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import Result

router = APIRouter(prefix="/tms/v1", tags=["TMS"])


@router.post("/providers", response_model=None)
async def create_provider(
    req: ProviderCreateRequest,
    svc: LogisticsProviderService = Depends(get_logistics_provider_service),
):
    provider = await svc.create(
        tenant_id_var.get(""), name=req.name, code=req.code,
        provider_type=req.provider_type, api_endpoint=req.api_endpoint,
        supported_regions=req.supported_regions,
    )
    return Result.ok(data={"id": provider.id, "code": provider.code}, trace_id=trace_id_var.get(""))


@router.get("/providers", response_model=None)
async def list_providers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: LogisticsProviderService = Depends(get_logistics_provider_service),
):
    items, total = await svc.list_all(tenant_id_var.get(""), page=page, page_size=page_size)
    data = [
        {"id": p.id, "name": p.name, "code": p.code, "provider_type": p.provider_type, "status": p.status}
        for p in items
    ]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/providers/{provider_id}", response_model=None)
async def get_provider(
    provider_id: str,
    svc: LogisticsProviderService = Depends(get_logistics_provider_service),
):
    provider = await svc.get_or_raise(provider_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": provider.id, "name": provider.name, "code": provider.code,
              "provider_type": provider.provider_type, "status": provider.status,
              "api_endpoint": provider.api_endpoint, "supported_regions": provider.supported_regions},
        trace_id=trace_id_var.get(""),
    )


@router.put("/providers/{provider_id}", response_model=None)
async def update_provider(
    provider_id: str,
    req: ProviderCreateRequest,
    svc: LogisticsProviderService = Depends(get_logistics_provider_service),
):
    provider = await svc.update(
        provider_id, tenant_id_var.get(""),
        name=req.name, code=req.code, provider_type=req.provider_type,
        api_endpoint=req.api_endpoint, supported_regions=req.supported_regions,
    )
    return Result.ok(data={"id": provider.id, "name": provider.name, "code": provider.code}, trace_id=trace_id_var.get(""))


@router.put("/providers/{provider_id}/status", response_model=None)
async def update_provider_status(
    provider_id: str,
    status: str = Query(..., min_length=1),
    svc: LogisticsProviderService = Depends(get_logistics_provider_service),
):
    provider = await svc.update_status(provider_id, tenant_id_var.get(""), status)
    return Result.ok(data={"id": provider.id, "name": provider.name, "status": provider.status}, trace_id=trace_id_var.get(""))


@router.delete("/providers/{provider_id}", response_model=None)
async def delete_provider(
    provider_id: str,
    svc: LogisticsProviderService = Depends(get_logistics_provider_service),
):
    provider = await svc.soft_delete(provider_id, tenant_id_var.get(""))
    return Result.ok(data={"id": provider_id, "status": "disabled"}, trace_id=trace_id_var.get(""))


@router.post("/shipments", response_model=None)
async def create_shipment(
    req: ShipmentCreateRequest,
    svc: ShipmentService = Depends(get_shipment_service),
):
    shipment = await svc.create(
        tenant_id_var.get(""), shipment_no=req.shipment_no, order_id=req.order_id,
        warehouse_id=req.warehouse_id, provider_id=req.provider_id,
        shipping_method_id=req.shipping_method_id, weight=req.weight,
        shipping_cost=req.shipping_cost, currency=req.currency,
        recipient_name=req.recipient_name, recipient_phone=req.recipient_phone,
        recipient_address=req.recipient_address, recipient_country=req.recipient_country,
    )
    return Result.ok(
        data={"id": shipment.id, "shipment_no": shipment.shipment_no, "status": shipment.status},
        trace_id=trace_id_var.get(""),
    )


@router.get("/shipments", response_model=None)
async def list_shipments(
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: ShipmentService = Depends(get_shipment_service),
):
    items, total = await svc.list_all(tenant_id_var.get(""), status=status, page=page, page_size=page_size)
    data = [
        {"id": s.id, "shipment_no": s.shipment_no, "order_id": s.order_id,
         "tracking_no": s.tracking_no, "status": s.status, "shipping_cost": s.shipping_cost}
        for s in items
    ]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/shipments/{shipment_id}", response_model=None)
async def get_shipment(
    shipment_id: str,
    svc: ShipmentService = Depends(get_shipment_service),
):
    shipment = await svc.get_or_raise(shipment_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": shipment.id, "shipment_no": shipment.shipment_no, "order_id": shipment.order_id,
              "tracking_no": shipment.tracking_no, "status": shipment.status,
              "shipping_cost": shipment.shipping_cost, "weight": shipment.weight,
              "provider_id": shipment.provider_id, "shipping_method_id": shipment.shipping_method_id,
              "recipient_name": shipment.recipient_name, "recipient_country": shipment.recipient_country,
              "currency": shipment.currency},
        trace_id=trace_id_var.get(""),
    )


@router.put("/shipments/{shipment_id}/tracking", response_model=None)
async def update_tracking(
    shipment_id: str,
    req: TrackingUpdateRequest,
    svc: ShipmentService = Depends(get_shipment_service),
):
    shipment = await svc.update_tracking(
        shipment_id, tenant_id_var.get(""), tracking_no=req.tracking_no, events=req.events,
    )
    return Result.ok(data={"id": shipment.id, "tracking_no": shipment.tracking_no}, trace_id=trace_id_var.get(""))


@router.put("/shipments/{shipment_id}/ship", response_model=None)
async def confirm_shipment(
    shipment_id: str,
    svc: ShipmentService = Depends(get_shipment_service),
):
    shipment = await svc.update_status(shipment_id, tenant_id_var.get(""), "picked_up")
    return Result.ok(
        data={"id": shipment.id, "shipment_no": shipment.shipment_no, "status": shipment.status},
        trace_id=trace_id_var.get(""),
    )


@router.put("/shipments/{shipment_id}/cancel", response_model=None)
async def cancel_shipment(
    shipment_id: str,
    svc: ShipmentService = Depends(get_shipment_service),
):
    shipment = await svc.update_status(shipment_id, tenant_id_var.get(""), "cancelled")
    return Result.ok(
        data={"id": shipment.id, "shipment_no": shipment.shipment_no, "status": shipment.status},
        trace_id=trace_id_var.get(""),
    )


@router.get("/shipments/{shipment_id}/cost", response_model=None)
async def get_shipment_cost(
    shipment_id: str,
    svc: ShipmentService = Depends(get_shipment_service),
):
    shipment = await svc.get_or_raise(shipment_id, tenant_id_var.get(""))
    from erp.modules.tms.domain.services import ShipmentDomainService
    cost_per_kg = ShipmentDomainService.calculate_cost_per_kg(shipment.weight or 0, shipment.shipping_cost or 0)
    return Result.ok(
        data={"shipment_id": shipment_id, "shipping_cost": shipment.shipping_cost,
              "weight": shipment.weight, "cost_per_kg": cost_per_kg, "currency": shipment.currency or "CNY"},
        trace_id=trace_id_var.get(""),
    )


@router.get("/shipping-methods", response_model=None)
async def list_shipping_methods(
    carrier_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: ShippingMethodService = Depends(get_shipping_method_service),
):
    items, total = await svc.list_all(
        tenant_id_var.get(""), provider_id=carrier_id, page=page, page_size=page_size,
    )
    data = [
        {"id": m.id, "name": m.name, "code": m.code, "provider_id": m.provider_id,
         "shipping_type": m.shipping_type, "status": m.status,
         "estimated_days_min": m.estimated_days_min, "estimated_days_max": m.estimated_days_max,
         "first_weight": m.first_weight, "first_weight_price": m.first_weight_price,
         "currency": m.currency}
        for m in items
    ]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/shipping-methods", response_model=None)
async def create_shipping_method(
    req: ShippingMethodCreateRequest,
    svc: ShippingMethodService = Depends(get_shipping_method_service),
):
    method = await svc.create(
        tenant_id_var.get(""), provider_id=req.provider_id, name=req.name,
        code=req.code, shipping_type=req.shipping_type,
        estimated_days_min=req.estimated_days_min, estimated_days_max=req.estimated_days_max,
        first_weight=req.first_weight, first_weight_price=req.first_weight_price,
        additional_weight=req.additional_weight, additional_weight_price=req.additional_weight_price,
        min_price=req.min_price, currency=req.currency,
    )
    return Result.ok(
        data={"id": method.id, "name": method.name, "code": method.code, "status": method.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/shipping-rates/estimate", response_model=None)
async def estimate_shipping_rate(
    req: RateEstimateRequest,
    svc: ShippingMethodService = Depends(get_shipping_method_service),
):
    estimates = await svc.compare_methods(
        tenant_id_var.get(""), weight=req.weight,
        destination_country=req.destination,
    )
    return Result.ok(
        data={"origin": req.origin, "destination": req.destination, "weight": req.weight, "estimates": estimates},
        trace_id=trace_id_var.get(""),
    )


@router.get("/trackings/{tracking_no}", response_model=None)
async def query_tracking(
    tracking_no: str,
    tracking_svc: TrackingService = Depends(get_tracking_service),
):
    result = await tracking_svc.get_by_tracking_no(tracking_no, tenant_id_var.get(""))
    if result:
        shipment, tracking_info = result
        return Result.ok(
            data={"tracking_no": tracking_no, "status": tracking_info["status"],
                  "shipment_id": tracking_info["shipment_id"],
                  "carrier_id": shipment.provider_id,
                  "latest_event": tracking_info.get("latest_event"),
                  "all_events": tracking_info.get("all_events", []),
                  "exception": tracking_info.get("exception")},
            trace_id=trace_id_var.get(""),
        )
    return Result.ok(data={"tracking_no": tracking_no, "status": "unknown", "events": []}, trace_id=trace_id_var.get(""))


@router.post("/freight/calculate", response_model=None)
async def calculate_freight(
    req: FreightCalculateRequest,
    method_svc: ShippingMethodService = Depends(get_shipping_method_service),
):
    from erp.modules.tms.domain.services import ShipmentDomainService
    volumetric_weight = 0.0
    if req.length_cm > 0 and req.width_cm > 0 and req.height_cm > 0:
        volumetric_weight = (req.length_cm * req.width_cm * req.height_cm) / 6000.0
    chargeable_weight = max(req.weight_kg, volumetric_weight)
    volume = (req.length_cm * req.width_cm * req.height_cm / 1000000.0) if req.length_cm > 0 else 0.0

    if req.shipping_method_id:
        result = await method_svc.calculate_freight(
            req.shipping_method_id, tenant_id_var.get(""), weight=req.weight_kg,
            volume=volume,
        )
        cost_errors = ShipmentDomainService.validate_shipping_cost(chargeable_weight, result.get("estimated_cost", 0.0))
        return Result.ok(data={
            "origin_country": req.origin_country,
            "destination_country": req.destination_country,
            "weight_kg": req.weight_kg,
            "volumetric_weight": round(volumetric_weight, 2),
            "chargeable_weight": round(chargeable_weight, 2),
            "total_cost": result.get("estimated_cost", 0.0),
            "currency": result.get("currency", "CNY"),
            "estimated_days": result.get("estimated_days", ""),
            "calculation_type": result.get("calculation_type", "by_weight"),
            "validation_errors": cost_errors,
        }, trace_id=trace_id_var.get(""))

    estimates = await method_svc.compare_methods(
        tenant_id_var.get(""), weight=req.weight_kg, volume=volume,
        destination_country=req.destination_country,
    )
    best = estimates[0] if estimates else None
    total_cost = best.get("estimated_cost", 0.0) if best else 0.0
    cost_errors = ShipmentDomainService.validate_shipping_cost(chargeable_weight, total_cost)
    return Result.ok(data={
        "origin_country": req.origin_country,
        "destination_country": req.destination_country,
        "weight_kg": req.weight_kg,
        "volumetric_weight": round(volumetric_weight, 2),
        "chargeable_weight": round(chargeable_weight, 2),
        "total_cost": total_cost,
        "currency": best.get("currency", "CNY") if best else "CNY",
        "estimated_days": best.get("estimated_days", "") if best else "",
        "all_estimates": estimates,
        "validation_errors": cost_errors,
    }, trace_id=trace_id_var.get(""))


@router.post("/labels", response_model=None)
async def request_label(
    req: LabelRequest,
    connector_svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
    shipment_svc: ShipmentService = Depends(get_shipment_service),
):
    shipment = await shipment_svc.get_or_raise(req.shipment_id, tenant_id_var.get(""))
    label = await connector_svc.request_label(
        tenant_id=tenant_id_var.get(""), connector_id=req.carrier_id,
        shipment_id=req.shipment_id, service_code=shipment.shipping_method_id,
        label_format=req.label_format.lower(),
    )
    return Result.ok(data={
        "shipment_id": req.shipment_id,
        "carrier_id": req.carrier_id,
        "tracking_no": label.tracking_number or shipment.tracking_no or "",
        "label_url": label.label_url,
        "label_format": label.label_format,
        "label_status": label.label_status,
        "connector_id": label.connector_id,
    }, trace_id=trace_id_var.get(""))


@router.post("/shipping-batches", response_model=None)
async def create_shipping_batch(
    req: BatchCreateRequest,
    svc: BatchService = Depends(get_batch_service),
):
    batch = await svc.create(
        tenant_id_var.get(""), carrier_id=req.carrier_id,
        shipment_ids=req.shipment_ids, remark=req.remark,
    )
    return Result.ok(
        data={"id": batch.id, "batch_no": batch.batch_no, "carrier_id": batch.carrier_id,
              "shipment_count": batch.shipment_count, "status": batch.status,
              "total_weight": batch.total_weight, "total_cost": batch.total_cost},
        trace_id=trace_id_var.get(""),
    )


@router.get("/batches", response_model=None)
async def list_batches(
    status: str = Query(default=""),
    carrier_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: BatchService = Depends(get_batch_service),
):
    items, total = await svc.list_all(
        tenant_id_var.get(""), status=status, carrier_id=carrier_id,
        page=page, page_size=page_size,
    )
    data = [{
        "id": b.id, "batch_no": b.batch_no, "carrier_id": b.carrier_id,
        "carrier_name": b.carrier_name, "shipment_count": b.shipment_count,
        "status": b.status, "total_weight": b.total_weight, "total_cost": b.total_cost,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    } for b in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/batches/{batch_id}", response_model=None)
async def get_batch(
    batch_id: str,
    svc: BatchService = Depends(get_batch_service),
):
    batch = await svc.get_or_raise(batch_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": batch.id, "batch_no": batch.batch_no, "carrier_id": batch.carrier_id,
              "carrier_name": batch.carrier_name, "shipment_count": batch.shipment_count,
              "status": batch.status, "total_weight": batch.total_weight, "total_cost": batch.total_cost,
              "shipment_ids": batch.shipment_ids_json, "remark": batch.remark,
              "created_at": batch.created_at.isoformat() if batch.created_at else None},
        trace_id=trace_id_var.get(""),
    )


@router.put("/batches/{batch_id}/status", response_model=None)
async def update_batch_status(
    batch_id: str,
    status: str = Query(..., min_length=1),
    svc: BatchService = Depends(get_batch_service),
):
    batch = await svc.update_status(batch_id, tenant_id_var.get(""), status)
    return Result.ok(
        data={"id": batch.id, "batch_no": batch.batch_no, "status": batch.status},
        trace_id=trace_id_var.get(""),
    )


@router.get("/carrier-performance", response_model=None)
async def carrier_performance(
    carrier_id: str = Query(default=""),
    svc: CarrierPerformanceService = Depends(get_carrier_performance_service),
):
    data = await svc.get_performance(tenant_id_var.get(""), carrier_id=carrier_id)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/pms/performance/timeliness", response_model=None)
async def pms_timeliness(
    carrier_id: str = Query(default=""),
    svc: CarrierPerformanceService = Depends(get_carrier_performance_service),
):
    data = await svc.get_timeliness(tenant_id_var.get(""), carrier_id=carrier_id)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/pms/freight/calculate", response_model=None)
async def pms_freight_calculate(
    req: FreightCalculateRequest,
    method_svc: ShippingMethodService = Depends(get_shipping_method_service),
):
    volume = (req.length_cm * req.width_cm * req.height_cm / 1000000.0) if req.length_cm > 0 else 0.0
    if req.shipping_method_id:
        result = await method_svc.calculate_freight(
            req.shipping_method_id, tenant_id_var.get(""), weight=req.weight_kg,
            volume=volume,
        )
        return Result.ok(
            data={"origin": req.origin_country, "destination": req.destination_country,
                  "weight_kg": req.weight_kg,
                  "total_cost": result.get("estimated_cost", 0.0),
                  "currency": result.get("currency", "CNY"),
                  "estimated_days": result.get("estimated_days", "")},
            trace_id=trace_id_var.get(""),
        )
    estimates = await method_svc.compare_methods(
        tenant_id_var.get(""), weight=req.weight_kg, volume=volume,
        destination_country=req.destination_country,
    )
    best = estimates[0] if estimates else None
    return Result.ok(
        data={"origin": req.origin_country, "destination": req.destination_country,
              "weight_kg": req.weight_kg,
              "total_cost": best.get("estimated_cost", 0.0) if best else 0.0,
              "currency": best.get("currency", "CNY") if best else "CNY",
              "estimated_days": best.get("estimated_days", "") if best else "",
              "all_estimates": estimates},
        trace_id=trace_id_var.get(""),
    )


@router.post("/connectors", response_model=None)
async def create_connector(
    req: ConnectorCreateRequest,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    connector = await svc.create_connector(
        tenant_id_var.get(""), connector_name=req.connector_name, connector_code=req.connector_code,
        carrier_name=req.carrier_name, carrier_code=req.carrier_code,
        connector_type=req.connector_type, api_base_url=req.api_base_url,
        auth_type=req.auth_type, auth_config=req.auth_config,
        supported_services=req.supported_services,
        supported_label_formats=req.supported_label_formats,
        supported_origins=req.supported_origins,
        supported_destinations=req.supported_destinations,
        rate_limit_per_minute=req.rate_limit_per_minute,
        timeout_seconds=req.timeout_seconds, max_retries=req.max_retries,
        description=req.description,
    )
    return Result.ok(
        data={"id": connector.id, "connector_code": connector.connector_code,
              "carrier_name": connector.carrier_name, "connector_type": connector.connector_type,
              "is_active": connector.is_active},
        trace_id=trace_id_var.get(""),
    )


@router.post("/connectors/init-defaults", response_model=None)
async def init_default_connectors(
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    connectors = await svc.init_default_connectors(tenant_id_var.get(""))
    return Result.ok(
        data={"count": len(connectors), "connector_codes": [c.connector_code for c in connectors]},
        trace_id=trace_id_var.get(""),
    )


@router.post("/connectors/{connector_id}/labels", response_model=None)
async def apply_label_via_connector(
    connector_id: str,
    req: LabelApplyRequest,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    label = await svc.request_label(
        tenant_id=tenant_id_var.get(""), connector_id=connector_id,
        shipment_id=req.shipment_id, service_code=req.service_code,
        label_format=req.label_format, shipper=req.shipper,
        recipient=req.recipient, packages=req.packages,
        request_params=req.request_params,
    )
    return Result.ok(
        data={"id": label.id, "shipment_id": label.shipment_id,
              "tracking_number": label.tracking_number, "carrier_code": label.carrier_code,
              "label_url": label.label_url, "label_format": label.label_format,
              "label_status": label.label_status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/connectors/{connector_id}/tracking", response_model=None)
async def query_tracking_via_connector(
    connector_id: str,
    req: TrackingQueryRequest,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    record = await svc.query_tracking(
        tenant_id=tenant_id_var.get(""), connector_id=connector_id,
        tracking_number=req.tracking_number, shipment_id=req.shipment_id,
        carrier_code=req.carrier_code,
    )
    return Result.ok(
        data={"tracking_number": record.tracking_number, "carrier_code": record.carrier_code,
              "current_status": record.current_status, "sync_count": record.sync_count,
              "events": record.events_json},
        trace_id=trace_id_var.get(""),
    )


@router.post("/connectors/{connector_id}/quotes", response_model=None)
async def request_freight_quote(
    connector_id: str,
    req: FreightQuoteRequest,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    quote = await svc.request_freight_quote(
        tenant_id=tenant_id_var.get(""), connector_id=connector_id,
        origin_country=req.origin_country, destination_country=req.destination_country,
        weight_grams=req.weight_grams, dimensions=req.dimensions,
        origin_zip=req.origin_zip, destination_zip=req.destination_zip,
        service_code=req.service_code,
    )
    return Result.ok(
        data={"id": quote.id, "quote_request_id": quote.quote_request_id,
              "service_name": quote.service_name, "carrier_code": quote.carrier_code,
              "total_amount": quote.total_amount, "currency": quote.currency,
              "estimated_days_min": quote.estimated_days_min,
              "estimated_days_max": quote.estimated_days_max},
        trace_id=trace_id_var.get(""),
    )


@router.post("/connectors/{connector_id}/dispatch", response_model=None)
async def create_dispatch(
    connector_id: str,
    req: DispatchCreateRequest,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    dispatch = await svc.create_dispatch(
        tenant_id=tenant_id_var.get(""), connector_id=connector_id,
        shipment_id=req.shipment_id, service_code=req.service_code,
        packages=req.packages, request_params=req.request_params,
    )
    return Result.ok(
        data={"id": dispatch.id, "shipment_id": dispatch.shipment_id,
              "tracking_number": dispatch.tracking_number, "carrier_code": dispatch.carrier_code,
              "dispatch_status": dispatch.dispatch_status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/connectors/{connector_id}/dispatch/{dispatch_id}/cancel", response_model=None)
async def cancel_dispatch(
    connector_id: str,
    dispatch_id: str,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    dispatch = await svc.cancel_dispatch(dispatch_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": dispatch.id, "dispatch_status": dispatch.dispatch_status,
              "cancel_at": dispatch.cancel_at.isoformat() if dispatch.cancel_at else None},
        trace_id=trace_id_var.get(""),
    )


@router.post("/strategies", response_model=None)
async def create_strategy(
    req: StrategyCreateRequest,
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    strategy = await svc.create_strategy(
        tenant_id_var.get(""), strategy_code=req.strategy_code,
        strategy_name=req.strategy_name, strategy_type=req.strategy_type,
        description=req.description, condition=req.condition,
        action=req.action, priority=req.priority,
        effective_from=req.effective_from, effective_to=req.effective_to,
    )
    return Result.ok(
        data={"id": strategy.id, "strategy_code": strategy.strategy_code,
              "strategy_name": strategy.strategy_name, "strategy_type": strategy.strategy_type,
              "priority": strategy.priority, "is_active": strategy.is_active},
        trace_id=trace_id_var.get(""),
    )


@router.put("/strategies/{strategy_id}", response_model=None)
async def update_strategy(
    strategy_id: str,
    req: StrategyUpdateRequest,
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    strategy = await svc.update_strategy(
        strategy_id, tenant_id_var.get(""),
        strategy_name=req.strategy_name, description=req.description,
        condition=req.condition, action=req.action, priority=req.priority,
    )
    return Result.ok(
        data={"id": strategy.id, "strategy_code": strategy.strategy_code,
              "strategy_name": strategy.strategy_name, "version": strategy.version},
        trace_id=trace_id_var.get(""),
    )


@router.put("/strategies/{strategy_id}/deactivate", response_model=None)
async def deactivate_strategy(
    strategy_id: str,
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    strategy = await svc.deactivate_strategy(strategy_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": strategy.id, "strategy_code": strategy.strategy_code, "is_active": strategy.is_active},
        trace_id=trace_id_var.get(""),
    )


@router.post("/strategies/evaluate", response_model=None)
async def evaluate_strategies(
    req: StrategyExecutionRequest,
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    matched = await svc.evaluate_strategies(
        tenant_id_var.get(""), strategy_type=req.context.get("strategy_type", "") if req.context else "",
        context=req.context or {},
    )
    return Result.ok(data={"matched_strategies": matched}, trace_id=trace_id_var.get(""))


@router.post("/strategies/{strategy_id}/execute", response_model=None)
async def execute_strategy(
    strategy_id: str,
    req: StrategyExecutionRequest,
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    log = await svc.execute_strategy(
        tenant_id_var.get(""), strategy_id=strategy_id,
        shipment_id=req.shipment_id, order_id=req.order_id,
        context=req.context,
    )
    return Result.ok(
        data={"id": log.id, "strategy_code": log.strategy_code,
              "result": log.result, "action_taken": log.action_taken},
        trace_id=trace_id_var.get(""),
    )


@router.get("/strategies", response_model=None)
async def list_strategies(
    strategy_type: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    items, total = await svc.list_strategies(
        tenant_id_var.get(""), strategy_type=strategy_type, page=page, page_size=page_size,
    )
    data = [
        {"id": s.id, "strategy_code": s.strategy_code, "strategy_name": s.strategy_name,
         "strategy_type": s.strategy_type, "priority": s.priority, "is_active": s.is_active,
         "version": s.version}
        for s in items
    ]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/strategies/{strategy_id}/execution-logs", response_model=None)
async def list_strategy_execution_logs(
    strategy_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    items, total = await svc.list_execution_logs(
        tenant_id_var.get(""), strategy_type="", page=page, page_size=page_size,
    )
    data = [
        {"id": l.id, "strategy_code": l.strategy_code, "strategy_type": l.strategy_type,
         "shipment_id": l.shipment_id, "order_id": l.order_id,
         "result": l.result, "created_at": l.created_at.isoformat() if l.created_at else None}
        for l in items
    ]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/strategies/init-defaults", response_model=None)
async def init_default_strategies(
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    await svc.init_defaults(tenant_id_var.get(""))
    return Result.ok(data={"message": "Default strategies initialized"}, trace_id=trace_id_var.get(""))


@router.get("/statistics", response_model=None, summary="TMS运营统计概览")
async def get_tms_statistics(
    svc: TMSQueryService = Depends(get_tms_query_service),
):
    data = await svc.get_statistics(tenant_id_var.get(""))
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/freight-templates", response_model=None, summary="创建运费模板")
async def create_freight_template(
    req: FreightTemplateCreateRequest,
    svc: FreightTemplateService = Depends(get_freight_template_service),
):
    template = await svc.create(
        tenant_id_var.get(""), name=req.name,
        calculation_type=req.calculation_type, rules=req.rules,
    )
    return Result.ok(
        data={"id": template.id, "name": template.name,
              "calculation_type": template.calculation_type, "status": template.status},
        trace_id=trace_id_var.get(""),
    )


@router.get("/freight-templates", response_model=None, summary="查询运费模板列表")
async def list_freight_templates(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: FreightTemplateService = Depends(get_freight_template_service),
):
    items, total = await svc.list_all(tenant_id_var.get(""), page=page, page_size=page_size)
    data = [
        {"id": t.id, "name": t.name, "calculation_type": t.calculation_type,
         "status": t.status, "created_at": t.created_at.isoformat() if t.created_at else None}
        for t in items
    ]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/freight-templates/{template_id}", response_model=None, summary="获取运费模板详情")
async def get_freight_template(
    template_id: str,
    svc: FreightTemplateService = Depends(get_freight_template_service),
):
    template = await svc.get_or_raise(template_id, tenant_id_var.get(""))
    import json
    rules = json.loads(template.rules_json) if template.rules_json else []
    return Result.ok(
        data={"id": template.id, "name": template.name,
              "calculation_type": template.calculation_type,
              "rules": rules, "status": template.status,
              "created_at": template.created_at.isoformat() if template.created_at else None},
        trace_id=trace_id_var.get(""),
    )


@router.put("/freight-templates/{template_id}", response_model=None, summary="更新运费模板")
async def update_freight_template(
    template_id: str,
    req: FreightTemplateUpdateRequest,
    svc: FreightTemplateService = Depends(get_freight_template_service),
):
    template = await svc.update(
        template_id, tenant_id_var.get(""),
        name=req.name, calculation_type=req.calculation_type,
        rules=req.rules, status=req.status,
    )
    return Result.ok(
        data={"id": template.id, "name": template.name,
              "calculation_type": template.calculation_type, "status": template.status},
        trace_id=trace_id_var.get(""),
    )


@router.delete("/freight-templates/{template_id}", response_model=None, summary="删除运费模板")
async def delete_freight_template(
    template_id: str,
    svc: FreightTemplateService = Depends(get_freight_template_service),
):
    template = await svc.soft_delete(template_id, tenant_id_var.get(""))
    return Result.ok(data={"id": template_id, "status": "disabled"}, trace_id=trace_id_var.get(""))


@router.get("/shipping-methods/{method_id}", response_model=None, summary="获取配送方式详情")
async def get_shipping_method(
    method_id: str,
    svc: ShippingMethodService = Depends(get_shipping_method_service),
):
    method = await svc.get_or_raise(method_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": method.id, "name": method.name, "code": method.code,
              "provider_id": method.provider_id, "shipping_type": method.shipping_type,
              "estimated_days_min": method.estimated_days_min,
              "estimated_days_max": method.estimated_days_max,
              "first_weight": method.first_weight, "first_weight_price": method.first_weight_price,
              "additional_weight": method.additional_weight,
              "additional_weight_price": method.additional_weight_price,
              "min_price": method.min_price, "currency": method.currency,
              "status": method.status},
        trace_id=trace_id_var.get(""),
    )


@router.put("/shipping-methods/{method_id}", response_model=None, summary="更新配送方式")
async def update_shipping_method(
    method_id: str,
    req: ShippingMethodUpdateRequest,
    svc: ShippingMethodService = Depends(get_shipping_method_service),
):
    method = await svc.update(
        method_id, tenant_id_var.get(""),
        name=req.name, shipping_type=req.shipping_type,
        estimated_days_min=req.estimated_days_min,
        estimated_days_max=req.estimated_days_max,
        first_weight=req.first_weight, first_weight_price=req.first_weight_price,
        additional_weight=req.additional_weight,
        additional_weight_price=req.additional_weight_price,
        min_price=req.min_price, currency=req.currency, status=req.status,
    )
    return Result.ok(
        data={"id": method.id, "name": method.name, "code": method.code, "status": method.status},
        trace_id=trace_id_var.get(""),
    )


@router.delete("/shipping-methods/{method_id}", response_model=None, summary="删除配送方式")
async def delete_shipping_method(
    method_id: str,
    svc: ShippingMethodService = Depends(get_shipping_method_service),
):
    method = await svc.soft_delete(method_id, tenant_id_var.get(""))
    return Result.ok(data={"id": method_id, "status": "disabled"}, trace_id=trace_id_var.get(""))


@router.post("/shipments/search", response_model=None, summary="多条件搜索发货单")
async def search_shipments(
    req: ShipmentSearchRequest,
    svc: ShipmentService = Depends(get_shipment_service),
):
    items, total = await svc.search(
        tenant_id_var.get(""), order_id=req.order_id, status=req.status,
        provider_id=req.provider_id, tracking_no=req.tracking_no,
        recipient_country=req.recipient_country,
        page=req.page, page_size=req.page_size,
    )
    data = [
        {"id": s.id, "shipment_no": s.shipment_no, "order_id": s.order_id,
         "tracking_no": s.tracking_no, "status": s.status,
         "shipping_cost": s.shipping_cost, "recipient_country": s.recipient_country}
        for s in items
    ]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


@router.post("/shipments/batch-status", response_model=None, summary="批量更新发货单状态")
async def batch_update_shipment_status(
    req: ShipmentBatchStatusRequest,
    svc: ShipmentService = Depends(get_shipment_service),
):
    results = await svc.batch_update_status(
        tenant_id_var.get(""), shipment_ids=req.shipment_ids, new_status=req.status,
    )
    success_count = sum(1 for r in results if r.get("success"))
    return Result.ok(
        data={"total": len(results), "success_count": success_count, "results": results},
        trace_id=trace_id_var.get(""),
    )


@router.get("/shipments/by-order/{order_id}", response_model=None, summary="根据订单ID查询发货单")
async def get_shipments_by_order(
    order_id: str,
    svc: ShipmentService = Depends(get_shipment_service),
):
    shipments = await svc.get_by_order_id(tenant_id_var.get(""), order_id)
    data = [
        {"id": s.id, "shipment_no": s.shipment_no, "status": s.status,
         "tracking_no": s.tracking_no, "shipping_cost": s.shipping_cost}
        for s in shipments
    ]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/connectors", response_model=None, summary="查询物流连接器列表")
async def list_connectors(
    connector_type: str = Query(default=""),
    carrier_code: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    items, total = await svc.list_connectors(
        tenant_id_var.get(""), connector_type=connector_type,
        carrier_code=carrier_code, page=page, page_size=page_size,
    )
    data = [
        {"id": c.id, "connector_name": c.connector_name, "connector_code": c.connector_code,
         "carrier_name": c.carrier_name, "carrier_code": c.carrier_code,
         "connector_type": c.connector_type, "is_active": c.is_active,
         "health_status": c.health_status}
        for c in items
    ]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/connectors/{connector_id}", response_model=None, summary="获取物流连接器详情")
async def get_connector(
    connector_id: str,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    connector = await svc.get_connector_or_raise(connector_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": connector.id, "connector_name": connector.connector_name,
              "connector_code": connector.connector_code,
              "carrier_name": connector.carrier_name, "carrier_code": connector.carrier_code,
              "connector_type": connector.connector_type,
              "api_base_url": connector.api_base_url,
              "auth_type": connector.auth_type,
              "is_active": connector.is_active,
              "health_status": connector.health_status,
              "description": connector.description},
        trace_id=trace_id_var.get(""),
    )


@router.put("/connectors/{connector_id}", response_model=None, summary="更新物流连接器")
async def update_connector(
    connector_id: str,
    req: ConnectorUpdateRequest,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    connector = await svc.update_connector(
        connector_id, tenant_id_var.get(""),
        connector_name=req.connector_name, api_base_url=req.api_base_url,
        auth_type=req.auth_type, auth_config=req.auth_config,
        rate_limit_per_minute=req.rate_limit_per_minute,
        timeout_seconds=req.timeout_seconds, max_retries=req.max_retries,
        description=req.description, is_active=req.is_active,
    )
    return Result.ok(
        data={"id": connector.id, "connector_code": connector.connector_code,
              "is_active": connector.is_active},
        trace_id=trace_id_var.get(""),
    )


@router.put("/connectors/{connector_id}/activate", response_model=None, summary="激活物流连接器")
async def activate_connector(
    connector_id: str,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    connector = await svc.update_connector(
        connector_id, tenant_id_var.get(""), is_active=True,
    )
    return Result.ok(
        data={"id": connector.id, "is_active": connector.is_active},
        trace_id=trace_id_var.get(""),
    )


@router.put("/connectors/{connector_id}/deactivate", response_model=None, summary="停用物流连接器")
async def deactivate_connector(
    connector_id: str,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    connector = await svc.update_connector(
        connector_id, tenant_id_var.get(""), is_active=False,
    )
    return Result.ok(
        data={"id": connector.id, "is_active": connector.is_active},
        trace_id=trace_id_var.get(""),
    )


@router.post("/connectors/{connector_id}/health-check", response_model=None, summary="物流连接器健康检查")
async def health_check_connector(
    connector_id: str,
    svc: LogisticsConnectorService = Depends(get_logistics_connector_service),
):
    result = await svc.health_check(connector_id, tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.put("/strategies/{strategy_id}/activate", response_model=None, summary="激活物流策略")
async def activate_strategy(
    strategy_id: str,
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    strategy = await svc.activate_strategy(strategy_id, tenant_id_var.get(""))
    return Result.ok(
        data={"id": strategy.id, "strategy_code": strategy.strategy_code, "is_active": strategy.is_active},
        trace_id=trace_id_var.get(""),
    )


@router.get("/strategies/{strategy_id}", response_model=None, summary="获取物流策略详情")
async def get_strategy(
    strategy_id: str,
    svc: LogisticsStrategyService = Depends(get_logistics_strategy_service),
):
    import json as _json
    strategy = await svc.get_by_id(strategy_id, tenant_id_var.get(""))
    condition = _json.loads(strategy.condition_json) if strategy.condition_json else {}
    action = _json.loads(strategy.action_json) if strategy.action_json else {}
    return Result.ok(
        data={"id": strategy.id, "strategy_code": strategy.strategy_code,
              "strategy_name": strategy.strategy_name,
              "strategy_type": strategy.strategy_type,
              "description": strategy.description,
              "condition": condition, "action": action,
              "priority": strategy.priority, "is_active": strategy.is_active,
              "effective_from": strategy.effective_from.isoformat() if strategy.effective_from else None,
              "effective_to": strategy.effective_to.isoformat() if strategy.effective_to else None,
              "version": strategy.version},
        trace_id=trace_id_var.get(""),
    )


@router.get("/providers/statistics", response_model=None, summary="物流商统计")
async def provider_statistics(
    svc: TMSQueryService = Depends(get_tms_query_service),
):
    data = await svc.get_statistics(tenant_id_var.get(""))
    return Result.ok(
        data={
            "provider_count": data["provider_count"],
            "active_provider_count": data["active_provider_count"],
            "provider_by_type": data["provider_by_type"],
        },
        trace_id=trace_id_var.get(""),
    )


@router.get("/shipments/statistics", response_model=None, summary="发货单统计")
async def shipment_statistics(
    svc: TMSQueryService = Depends(get_tms_query_service),
):
    data = await svc.get_statistics(tenant_id_var.get(""))
    return Result.ok(
        data={
            "shipment_count": data["shipment_count"],
            "pending_shipment_count": data["pending_shipment_count"],
            "in_transit_count": data["in_transit_count"],
            "delivered_count": data["delivered_count"],
            "exception_count": data["exception_count"],
            "shipment_by_status": data["shipment_by_status"],
            "total_shipping_cost": data["total_shipping_cost"],
            "avg_delivery_days": data["avg_delivery_days"],
        },
        trace_id=trace_id_var.get(""),
    )
