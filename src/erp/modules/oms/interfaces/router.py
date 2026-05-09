"""
OMS (订单域) 路由层 — 内部域

职责: 接收HTTP请求 → 参数校验(DTO) → 调用应用服务 → 返回统一响应
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query

from erp.modules.oms.application.dtos import (
    AuditLogResponse,
    OrderAllocateRequest,
    OrderBatchStatusRequest,
    OrderCancelRequest,
    OrderCreateRequest,
    OrderItemCreateRequest,
    OrderMergeRequest,
    OrderRemarkRequest,
    OrderResponse,
    OrderSearchRequest,
    OrderShipRequest,
    OrderSplitRequest,
    OrderSplitRuleCreateRequest,
    OrderSplitRuleResponse,
    OrderStatusRequest,
    OrderStatisticsResponse,
    OrderSyncRequest,
    PromotionCreateRequest,
    PromotionDiscountRequest,
    PromotionResponse,
    PromotionStatusRequest,
    RefundApproveRequest,
    RefundBatchApproveRequest,
    RefundCreateRequest,
    RefundResponse,
    RefundStatisticsResponse,
    RefundStatusRequest,
    RiskCheckRequest,
    SplitRuleUpdateRequest,
)
from erp.modules.oms.application.services import (
    OrderAuditQueryService,
    OrderSplitRuleService,
    PromotionService,
    RefundOrderService,
    RefundQueryService,
    SalesOrderQueryService,
    SalesOrderService,
)
from erp.modules.oms.domain.services import (
    ORDER_STATUS_TRANSITIONS,
    PROMO_STATUS_TRANSITIONS,
    REFUND_STATUS_TRANSITIONS,
    OrderDomainService,
)
from erp.modules.oms.domain.validators import OrderRiskValidator
from erp.modules.oms.interfaces.deps import (
    get_current_tenant_id,
    get_order_audit_query_service,
    get_order_split_rule_service,
    get_promotion_service,
    get_refund_order_service,
    get_refund_query_service,
    get_sales_order_query_service,
    get_sales_order_service,
)
from erp.shared.context import trace_id_var
from erp.shared.exceptions import Result, ValidationException

router = APIRouter(prefix="/oms/v1", tags=["OMS"])


# ============================================================
# 销售订单路由
# ============================================================

@router.post("/orders", response_model=None, summary="创建销售订单")
async def create_order(
    req: OrderCreateRequest,
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    kwargs = {}
    if req.order_time:
        kwargs["order_time"] = req.order_time
    kwargs["raw_data_json"] = json.dumps(req.raw_data, default=str)
    if req.tags:
        kwargs["tags_json"] = json.dumps(req.tags, default=str)
    if req.risk_flags:
        kwargs["risk_flags_json"] = json.dumps(req.risk_flags, default=str)
    order = await svc.create(
        tenant_id=tenant_id, order_no=req.order_no, platform=req.platform, store_id=req.store_id,
        platform_order_id=req.platform_order_id, order_type=req.order_type,
        buyer_id=req.buyer_id, buyer_name=req.buyer_name,
        recipient_name=req.recipient_name, recipient_phone=req.recipient_phone,
        recipient_address=req.recipient_address, recipient_city=req.recipient_city,
        recipient_state=req.recipient_state, recipient_country=req.recipient_country,
        recipient_zip=req.recipient_zip, currency=req.currency,
        item_subtotal=req.item_subtotal, shipping_fee=req.shipping_fee,
        discount_amount=req.discount_amount, tax_amount=req.tax_amount,
        total_amount=req.total_amount, warehouse_id=req.warehouse_id, remark=req.remark,
        **kwargs,
    )
    return Result.ok(
        data=OrderResponse.model_validate(order).model_dump(),
        trace_id=trace_id_var.get(""),
    )


@router.get("/orders", response_model=None, summary="查询订单列表")
async def list_orders(
    platform: str = Query(default=""), store_id: str = Query(default=""),
    status: str = Query(default=""), page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    items, total = await svc.list_all(tenant_id, platform=platform, store_id=store_id, status=status, page=page, page_size=page_size)
    data = [OrderResponse.model_validate(o).model_dump() for o in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/orders/{order_id}", response_model=None, summary="查询订单详情")
async def get_order(
    order_id: str,
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    order = await svc.get_or_raise(order_id, tenant_id)
    items = await svc.get_items(order_id, tenant_id)
    order_data = OrderResponse.model_validate(order).model_dump()
    order_data["items"] = [
        {"sku_id": i.sku_id, "quantity": i.quantity, "unit_price": i.unit_price, "item_total": i.item_total}
        for i in items
    ]
    return Result.ok(data=order_data, trace_id=trace_id_var.get(""))


@router.put("/orders/{order_id}/status", response_model=None, summary="更新订单状态")
async def update_order_status(
    order_id: str, req: OrderStatusRequest,
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    order = await svc.update_status(order_id, tenant_id, new_status=req.status, remark=req.remark)
    return Result.ok(data={"id": order.id, "status": order.status}, trace_id=trace_id_var.get(""))


@router.put("/orders/{order_id}/audit", response_model=None, summary="审核订单")
async def audit_order(
    order_id: str, action: str = Query(default="approved"), remark: str = Query(default=""),
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    order = await svc.get_or_raise(order_id, tenant_id)
    if not OrderDomainService.is_cancellable(order) and action == "rejected":
        raise ValidationException(message="Order cannot be rejected in current status")
    new_status = "confirmed" if action == "approved" else "cancelled"
    order = await svc.update_status(order_id, tenant_id, new_status=new_status, remark=f"Audit {action}: {remark}")
    return Result.ok(data={"id": order.id, "status": order.status, "audit_action": action}, trace_id=trace_id_var.get(""))


@router.post("/orders/{order_id}/items", response_model=None, summary="添加订单明细")
async def add_order_item(
    order_id: str, req: OrderItemCreateRequest,
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    item = await svc.add_item(
        tenant_id, order_id=order_id, sku_id=req.sku_id,
        quantity=req.quantity, unit_price=req.unit_price,
        channel_sku=req.channel_sku, product_name=req.product_name,
        platform_item_id=req.platform_item_id,
    )
    return Result.ok(data={"id": item.id, "item_total": item.item_total}, trace_id=trace_id_var.get(""))


@router.post("/orders/sync", response_model=None, summary="同步平台订单")
async def sync_orders(
    req: OrderSyncRequest,
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    result = await svc.sync_from_platform(
        tenant_id, platform=req.platform, store_id=req.store_id,
        platform_order_ids=req.platform_order_ids, sync_type=req.sync_type,
        start_time=req.start_time, end_time=req.end_time,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/orders/allocate", response_model=None, summary="分配仓库")
async def allocate_orders(
    req: OrderAllocateRequest,
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    results = []
    for oid in req.order_ids:
        order = await svc.update_status(oid, tenant_id, new_status="confirmed", remark=f"Allocated to warehouse: {req.warehouse_id}")
        results.append({"id": order.id, "status": order.status})
    return Result.ok(data=results, trace_id=trace_id_var.get(""))


@router.post("/orders/ship", response_model=None, summary="订单发货")
async def ship_order(
    req: OrderShipRequest,
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    order = await svc.update_status(req.order_id, tenant_id, new_status="shipped", remark=f"Tracking: {req.tracking_number}, Carrier: {req.carrier}")
    return Result.ok(data={"id": order.id, "status": order.status, "tracking_number": req.tracking_number}, trace_id=trace_id_var.get(""))


@router.post("/orders/{order_id}/cancel", response_model=None, summary="取消订单")
async def cancel_order(
    order_id: str, req: OrderCancelRequest,
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    order = await svc.get_or_raise(order_id, tenant_id)
    if not OrderDomainService.is_cancellable(order):
        raise ValidationException(message=f"Order in '{order.status}' status cannot be cancelled")
    order = await svc.update_status(order_id, tenant_id, new_status="cancelled", remark=f"Cancel type: {req.cancel_type}, Reason: {req.reason}")
    return Result.ok(data={"id": order.id, "status": order.status}, trace_id=trace_id_var.get(""))


@router.post("/orders/risk-check", response_model=None, summary="订单风控检查")
async def risk_check_order(req: RiskCheckRequest):
    validator = OrderRiskValidator()
    result = validator.validate(req.order_id, check_types=req.check_types)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/orders/split", response_model=None, summary="拆分订单")
async def split_order(
    req: OrderSplitRequest,
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    split_orders = await svc.split_order(tenant_id, req.order_id, req.split_rules)
    return Result.ok(data={"original_order_id": req.order_id, "split_orders": split_orders}, trace_id=trace_id_var.get(""))


@router.post("/orders/merge", response_model=None, summary="合并订单")
async def merge_orders(
    req: OrderMergeRequest,
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    result = await svc.merge_orders(tenant_id, req.order_ids)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.put("/orders/{order_id}/remark", response_model=None, summary="更新订单备注")
async def update_order_remark(
    order_id: str, req: OrderRemarkRequest,
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    order = await svc.get_or_raise(order_id, tenant_id)
    order.remark = req.remark
    if req.tags:
        order.tags_json = json.dumps(req.tags, default=str)
    await svc.update_status(order_id, tenant_id, new_status=order.status, remark="Updated remark/tags")
    return Result.ok(data={"id": order.id, "remark": order.remark}, trace_id=trace_id_var.get(""))


@router.get("/orders/statistics", response_model=None, summary="订单统计")
async def order_statistics(
    platform: str = Query(default=""), store_id: str = Query(default=""),
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    items, total = await svc.list_all(tenant_id, platform=platform, store_id=store_id, status="", page=1, page_size=1000)
    stats = {"total_orders": total, "total_amount": sum(o.total_amount for o in items), "by_status": {}}
    for o in items:
        stats["by_status"][o.status] = stats["by_status"].get(o.status, 0) + 1
    return Result.ok(data=stats, trace_id=trace_id_var.get(""))


@router.get("/orders/pending", response_model=None, summary="待处理订单")
async def list_pending_orders(
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    items, total = await svc.list_all(tenant_id, platform="", store_id="", status="pending", page=page, page_size=page_size)
    data = [
        {"id": o.id, "order_no": o.order_no, "platform": o.platform, "total_amount": o.total_amount, "created_at": str(o.created_at) if o.created_at else None}
        for o in items
    ]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


# ============================================================
# 退款单路由
# ============================================================

@router.post("/refunds", response_model=None, summary="创建退款单")
async def create_refund(
    req: RefundCreateRequest,
    svc: RefundOrderService = Depends(get_refund_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    refund = await svc.create(
        tenant_id, refund_no=req.refund_no, original_order_id=req.original_order_id,
        refund_type=req.refund_type, refund_amount=req.refund_amount,
        reason=req.reason, currency=req.currency, platform_refund_id=req.platform_refund_id,
        items_json=json.dumps(req.items, default=str),
    )
    return Result.ok(
        data=RefundResponse.model_validate(refund).model_dump(),
        trace_id=trace_id_var.get(""),
    )


@router.get("/refunds", response_model=None, summary="查询退款单列表")
async def list_refunds(
    status: str = Query(default=""), page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: RefundOrderService = Depends(get_refund_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    items, total = await svc.list_all(tenant_id, status=status, page=page, page_size=page_size)
    data = [RefundResponse.model_validate(r).model_dump() for r in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/refunds/{refund_id}", response_model=None, summary="查询退款单详情")
async def get_refund(
    refund_id: str,
    svc: RefundOrderService = Depends(get_refund_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    refund = await svc.get_or_raise(refund_id, tenant_id)
    return Result.ok(data=RefundResponse.model_validate(refund).model_dump(), trace_id=trace_id_var.get(""))


@router.put("/refunds/{refund_id}/status", response_model=None, summary="更新退款单状态")
async def update_refund_status(
    refund_id: str, req: RefundStatusRequest,
    svc: RefundOrderService = Depends(get_refund_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    refund = await svc.update_status(refund_id, tenant_id, status=req.status)
    return Result.ok(data={"id": refund.id, "status": refund.status}, trace_id=trace_id_var.get(""))


@router.post("/refunds/{refund_id}/approve", response_model=None, summary="审批退款")
async def approve_refund(
    refund_id: str, req: RefundApproveRequest,
    svc: RefundOrderService = Depends(get_refund_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    new_status = "approved" if req.action == "approve" else "rejected"
    refund = await svc.update_status(refund_id, tenant_id, status=new_status, remark=req.remark)
    return Result.ok(data={"id": refund.id, "status": refund.status}, trace_id=trace_id_var.get(""))


# ============================================================
# 促销活动路由
# ============================================================

@router.post("/promotions", response_model=None, summary="创建促销活动")
async def create_promotion(
    req: PromotionCreateRequest,
    svc: PromotionService = Depends(get_promotion_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    promo = await svc.create(
        tenant_id, promo_no=req.promo_no, name=req.name, promo_type=req.promo_type,
        discount_type=req.discount_type, discount_value=req.discount_value,
        min_purchase_amount=req.min_purchase_amount, max_discount_amount=req.max_discount_amount,
        usage_limit=req.usage_limit, per_customer_limit=req.per_customer_limit,
        platform=req.platform, store_id=req.store_id,
        start_time=req.start_time, end_time=req.end_time,
        applicable_skus_json=json.dumps(req.applicable_skus),
        applicable_categories_json=json.dumps(req.applicable_categories),
        conditions_json=json.dumps(req.conditions),
        priority=req.priority, can_stack=req.can_stack,
    )
    return Result.ok(
        data=PromotionResponse.model_validate(promo).model_dump(),
        trace_id=trace_id_var.get(""),
    )


@router.get("/promotions", response_model=None, summary="查询促销活动列表")
async def list_promotions(
    status: str = Query(default=""), promo_type: str = Query(default=""),
    platform: str = Query(default=""), page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: PromotionService = Depends(get_promotion_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    items, total = await svc.list_all(tenant_id, status=status, promo_type=promo_type, platform=platform, page=page, page_size=page_size)
    data = [PromotionResponse.model_validate(p).model_dump() for p in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/promotions/{promo_id}", response_model=None, summary="查询促销活动详情")
async def get_promotion(
    promo_id: str,
    svc: PromotionService = Depends(get_promotion_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    promo = await svc.get_or_raise(promo_id, tenant_id)
    return Result.ok(data=PromotionResponse.model_validate(promo).model_dump(), trace_id=trace_id_var.get(""))


@router.put("/promotions/{promo_id}/status", response_model=None, summary="更新促销活动状态")
async def update_promotion_status(
    promo_id: str, req: PromotionStatusRequest,
    svc: PromotionService = Depends(get_promotion_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    promo = await svc.update_status(promo_id, tenant_id, req.status)
    return Result.ok(data={"id": promo.id, "status": promo.status}, trace_id=trace_id_var.get(""))


@router.post("/promotions/calculate-discount", response_model=None, summary="计算订单折扣")
async def calculate_discount(
    req: PromotionDiscountRequest,
    svc: PromotionService = Depends(get_promotion_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    result = await svc.calculate_order_discount(
        tenant_id, order_amount=req.order_amount, sku_id=req.sku_id,
        category_id=req.category_id, platform=req.platform, store_id=req.store_id,
    )
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.delete("/promotions/{promo_id}", response_model=None, summary="删除促销活动")
async def delete_promotion(
    promo_id: str,
    svc: PromotionService = Depends(get_promotion_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    deleted = await svc.soft_delete(promo_id, tenant_id)
    return Result.ok(data={"id": promo_id, "deleted": deleted}, trace_id=trace_id_var.get(""))


# ============================================================
# 订单搜索路由
# ============================================================

@router.post("/orders/search", response_model=None, summary="高级搜索订单")
async def search_orders(
    req: OrderSearchRequest,
    svc: SalesOrderQueryService = Depends(get_sales_order_query_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    items, total = await svc.search(
        tenant_id, keyword=req.keyword, platform=req.platform, store_id=req.store_id,
        status=req.status, order_type=req.order_type,
        start_date=req.start_date, end_date=req.end_date,
        min_amount=req.min_amount, max_amount=req.max_amount,
        page=req.page, page_size=req.page_size,
    )
    data = [{"id": o.id, "order_no": o.order_no, "platform": o.platform,
             "store_id": o.store_id, "status": o.status, "order_type": o.order_type,
             "total_amount": o.total_amount, "buyer_name": o.buyer_name,
             "created_at": str(o.created_at) if o.created_at else None} for o in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


# ============================================================
# 订单统计路由
# ============================================================

@router.get("/orders/statistics/overview", response_model=None, summary="订单统计概览")
async def order_statistics_overview(
    platform: str = Query(default=""), store_id: str = Query(default=""),
    svc: SalesOrderQueryService = Depends(get_sales_order_query_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    data = await svc.get_statistics(tenant_id, platform=platform, store_id=store_id)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


# ============================================================
# 批量操作路由
# ============================================================

@router.post("/orders/batch-status", response_model=None, summary="批量更新订单状态")
async def batch_update_order_status(
    req: OrderBatchStatusRequest,
    svc: SalesOrderService = Depends(get_sales_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    results = []
    for oid in req.order_ids:
        try:
            order = await svc.update_status(oid, tenant_id, new_status=req.status, remark=req.remark)
            results.append({"id": oid, "status": order.status, "success": True})
        except Exception as e:
            results.append({"id": oid, "error": str(e), "success": False})
    return Result.ok(data=results, trace_id=trace_id_var.get(""))


# ============================================================
# 退款统计路由
# ============================================================

@router.get("/refunds/statistics/overview", response_model=None, summary="退款统计概览")
async def refund_statistics_overview(
    svc: RefundQueryService = Depends(get_refund_query_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    data = await svc.get_statistics(tenant_id)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/refunds/by-order/{order_id}", response_model=None, summary="查询订单关联退款")
async def list_refunds_by_order(
    order_id: str,
    svc: RefundQueryService = Depends(get_refund_query_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    refunds = await svc.list_by_order(order_id, tenant_id)
    data = [RefundResponse.model_validate(r).model_dump() for r in refunds]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/refunds/batch-approve", response_model=None, summary="批量审批退款")
async def batch_approve_refunds(
    req: RefundBatchApproveRequest,
    svc: RefundOrderService = Depends(get_refund_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    results = []
    new_status = "approved" if req.action == "approve" else "rejected"
    for rid in req.refund_ids:
        try:
            refund = await svc.update_status(rid, tenant_id, status=new_status, remark=req.remark)
            results.append({"id": rid, "status": refund.status, "success": True})
        except Exception as e:
            results.append({"id": rid, "error": str(e), "success": False})
    return Result.ok(data=results, trace_id=trace_id_var.get(""))


# ============================================================
# 拆单规则路由
# ============================================================

@router.get("/split-rules", response_model=None, summary="查询拆单规则列表")
async def list_split_rules(
    status: str = Query(default=""),
    svc: OrderSplitRuleService = Depends(get_order_split_rule_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    rules = await svc.list_all(tenant_id, status=status)
    data = [OrderSplitRuleResponse.model_validate(r).model_dump() for r in rules]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/split-rules", response_model=None, summary="创建拆单规则")
async def create_split_rule(
    req: OrderSplitRuleCreateRequest,
    svc: OrderSplitRuleService = Depends(get_order_split_rule_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    rule = await svc.create(
        tenant_id, name=req.name, rule_type=req.rule_type,
        conditions_json=json.dumps(req.conditions), priority=req.priority,
    )
    return Result.ok(data=OrderSplitRuleResponse.model_validate(rule).model_dump(), trace_id=trace_id_var.get(""))


@router.put("/split-rules/{rule_id}", response_model=None, summary="更新拆单规则")
async def update_split_rule(
    rule_id: str, req: SplitRuleUpdateRequest,
    svc: OrderSplitRuleService = Depends(get_order_split_rule_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    kwargs = {}
    if req.name is not None:
        kwargs["name"] = req.name
    if req.conditions is not None:
        kwargs["conditions_json"] = json.dumps(req.conditions)
    if req.priority is not None:
        kwargs["priority"] = req.priority
    if req.status is not None:
        kwargs["status"] = req.status
    rule = await svc.update(rule_id, tenant_id, **kwargs)
    return Result.ok(data={"id": rule.id, "name": rule.name, "status": rule.status}, trace_id=trace_id_var.get(""))


# ============================================================
# 审计日志路由
# ============================================================

@router.get("/orders/{order_id}/audit-logs", response_model=None, summary="查询订单审计日志")
async def list_order_audit_logs(
    order_id: str,
    svc: OrderAuditQueryService = Depends(get_order_audit_query_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    logs = await svc.list_by_order(order_id, tenant_id)
    data = [AuditLogResponse.model_validate(log).model_dump() for log in logs]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/orders/{order_id}/timeline", response_model=None, summary="查询订单时间线")
async def get_order_timeline(
    order_id: str,
    svc: OrderAuditQueryService = Depends(get_order_audit_query_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    timeline = await svc.get_order_timeline(order_id, tenant_id)
    return Result.ok(data=timeline, trace_id=trace_id_var.get(""))


# ============================================================
# 状态机查询路由
# ============================================================

@router.get("/orders/status-transitions", response_model=None, summary="查询订单状态机")
async def get_order_status_transitions():
    return Result.ok(data=ORDER_STATUS_TRANSITIONS, trace_id=trace_id_var.get(""))


@router.get("/refunds/status-transitions", response_model=None, summary="查询退款状态机")
async def get_refund_status_transitions():
    return Result.ok(data=REFUND_STATUS_TRANSITIONS, trace_id=trace_id_var.get(""))


@router.get("/promotions/status-transitions", response_model=None, summary="查询促销状态机")
async def get_promotion_status_transitions():
    return Result.ok(data=PROMO_STATUS_TRANSITIONS, trace_id=trace_id_var.get(""))
