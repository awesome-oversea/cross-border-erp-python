"""
SCM 内部域 API 路由

本模块定义供应链管理系统内部域的所有 REST API 端点。
路径规范: /scm/api/v1/{resource}

端点分组:
  - 供应商:         /suppliers
  - 采购订单:       /purchase-orders
  - 补货计划:       /replenishment-plans
  - 询价:           /inquiries
  - 加工订单:       /processing-orders
  - 供应商评价:     /suppliers/{id}/rate, /suppliers/statistics
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from erp.modules.scm.application.dtos import (
    InquiryCreateRequest,
    InquiryQuoteRequest,
    POCreateRequest,
    POItemRequest,
    POStatusRequest,
    ProcessingOrderCreateRequest,
    PurchaseOrderCreateRequest,
    PurchaseOrderItemRequest,
    PurchaseOrderStatusRequest,
    ReplenishmentPlanCreateRequest,
    ReplenishmentPlanRequest,
    SupplierBatchEvaluateRequest,
    SupplierCreateRequest,
    SupplierRatingRequest,
    SupplierUpdateRequest,
)
from erp.modules.scm.application.services import (
    InquiryService,
    PO_STATUS_TRANSITIONS,
    PurchaseOrderService,
    ReplenishmentPlanService,
    SCMQueryService,
    SupplierEvaluationService,
    SupplierService,
)
from erp.modules.scm.interfaces.deps import (
    get_inquiry_service,
    get_purchase_order_service,
    get_replenishment_plan_service,
    get_scm_query_service,
    get_supplier_evaluation_service,
    get_supplier_service,
)
from erp.shared.context import get_current_tenant_id, tenant_id_var, trace_id_var
from erp.shared.exceptions import Result

router = APIRouter(prefix="/scm/v1", tags=["SCM"])


# ---------------------------------------------------------------------------
# 供应商端点
# ---------------------------------------------------------------------------

@router.post("/suppliers", response_model=None, summary="创建供应商")
async def create_supplier(
    req: SupplierCreateRequest,
    svc: SupplierService = Depends(get_supplier_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建供应商: 唯一性校验(code) → 持久化"""
    supplier = await svc.create(
        tenant_id=tenant_id, name=req.name, code=req.code, short_name=req.short_name,
        contact_person=req.contact_person, contact_phone=req.contact_phone,
        contact_email=req.contact_email, address=req.address, region=req.region,
        supplier_type=req.supplier_type, cooperation_level=req.cooperation_level,
        payment_terms=req.payment_terms, lead_time_days=req.lead_time_days,
        min_order_qty=req.min_order_qty, org_id=req.org_id,
    )
    return Result.ok(data={"id": supplier.id, "code": supplier.code}, trace_id=trace_id_var.get(""))


@router.get("/suppliers", response_model=None, summary="查询供应商列表")
async def list_suppliers(
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: SupplierService = Depends(get_supplier_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """分页查询供应商列表"""
    items, total = await svc.list_all(tenant_id, status=status, page=page, page_size=page_size)
    data = [{"id": s.id, "name": s.name, "code": s.code, "supplier_type": s.supplier_type, "status": s.status, "quality_score": s.quality_score} for s in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.put("/suppliers/{supplier_id}", response_model=None, summary="更新供应商")
async def update_supplier(
    supplier_id: str,
    req: SupplierUpdateRequest,
    svc: SupplierService = Depends(get_supplier_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """更新供应商信息"""
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    supplier = await svc.update(supplier_id, tenant_id, **update_data)
    return Result.ok(data={"id": supplier_id, "updated": True}, trace_id=trace_id_var.get(""))


@router.delete("/suppliers/{supplier_id}", response_model=None, summary="删除供应商")
async def delete_supplier(
    supplier_id: str,
    svc: SupplierService = Depends(get_supplier_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """软删除供应商"""
    deleted = await svc.soft_delete(supplier_id, tenant_id)
    return Result.ok(data={"id": supplier_id, "deleted": deleted}, trace_id=trace_id_var.get(""))


@router.post("/suppliers/{supplier_id}/rate", response_model=None, summary="供应商评分")
async def rate_supplier(
    supplier_id: str,
    req: SupplierRatingRequest,
    eval_svc: SupplierEvaluationService = Depends(get_supplier_evaluation_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """供应商评分: 计算综合评分 → 记录评价历史 → 更新供应商等级"""
    from datetime import datetime
    period = datetime.now().strftime("%Y-%m")
    evaluation = await eval_svc.create(
        tenant_id=tenant_id, supplier_id=supplier_id, period=period,
        quality_score=req.quality_score, delivery_score=req.delivery_score,
        price_score=req.price_score, service_score=req.service_score,
    )
    return Result.ok(
        data={"supplier_id": supplier_id, "overall_score": evaluation.overall_score, "period": period},
        trace_id=trace_id_var.get(""),
    )


@router.get("/suppliers/{supplier_id}/rating-history", response_model=None, summary="供应商评分历史")
async def get_supplier_rating_history(
    supplier_id: str,
    eval_svc: SupplierEvaluationService = Depends(get_supplier_evaluation_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询供应商评分历史"""
    evaluations = await eval_svc.list_by_supplier(supplier_id, tenant_id)
    history = [
        {
            "period": e.period, "overall_score": e.overall_score,
            "quality_score": e.quality_score, "delivery_score": e.delivery_score,
            "price_score": e.price_score, "service_score": e.service_score,
        }
        for e in evaluations
    ]
    return Result.ok(data={"supplier_id": supplier_id, "history": history}, trace_id=trace_id_var.get(""))


@router.get("/suppliers/{supplier_id}/latest-evaluation", response_model=None, summary="供应商最新评价")
async def get_supplier_latest_evaluation(
    supplier_id: str,
    eval_svc: SupplierEvaluationService = Depends(get_supplier_evaluation_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询供应商最新评价"""
    evaluation = await eval_svc.get_latest(supplier_id, tenant_id)
    if not evaluation:
        return Result.ok(data=None, trace_id=trace_id_var.get(""))
    return Result.ok(data={
        "supplier_id": supplier_id, "period": evaluation.period,
        "overall_score": evaluation.overall_score,
        "quality_score": evaluation.quality_score,
        "delivery_score": evaluation.delivery_score,
        "price_score": evaluation.price_score,
        "service_score": evaluation.service_score,
    }, trace_id=trace_id_var.get(""))


@router.get("/suppliers/statistics", response_model=None, summary="供应商统计")
async def supplier_statistics(
    svc: SupplierService = Depends(get_supplier_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """供应商统计: 按类型/等级分组 + 平均评分"""
    items, total = await svc.list_all(tenant_id, status="", page=1, page_size=1000)
    stats = {"total_suppliers": total, "by_type": {}, "by_level": {}, "avg_quality_score": 0.0}
    scores = []
    for s in items:
        stats["by_type"][s.supplier_type] = stats["by_type"].get(s.supplier_type, 0) + 1
        stats["by_level"][s.cooperation_level] = stats["by_level"].get(s.cooperation_level, 0) + 1
        if s.quality_score:
            scores.append(s.quality_score)
    if scores:
        stats["avg_quality_score"] = sum(scores) / len(scores)
    return Result.ok(data=stats, trace_id=trace_id_var.get(""))


# ---------------------------------------------------------------------------
# 采购订单端点
# ---------------------------------------------------------------------------

@router.post("/purchase-orders", response_model=None, summary="创建采购订单")
async def create_po(
    req: PurchaseOrderCreateRequest,
    svc: PurchaseOrderService = Depends(get_purchase_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建采购订单: 唯一性校验(po_no) → 供应商校验 → 持久化"""
    kwargs = {}
    if req.expected_delivery_date:
        kwargs["expected_delivery_date"] = req.expected_delivery_date
    po = await svc.create(
        tenant_id=tenant_id, po_no=req.po_no, supplier_id=req.supplier_id,
        warehouse_id=req.warehouse_id, po_type=req.po_type, currency=req.currency,
        remark=req.remark, **kwargs,
    )
    return Result.ok(data={"id": po.id, "po_no": po.po_no, "status": po.status}, trace_id=trace_id_var.get(""))


@router.get("/purchase-orders", response_model=None, summary="查询采购订单列表")
async def list_pos(
    status: str = Query(default=""),
    supplier_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: PurchaseOrderService = Depends(get_purchase_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """分页查询采购订单列表"""
    items, total = await svc.list_all(tenant_id, status=status, supplier_id=supplier_id, page=page, page_size=page_size)
    data = [{"id": p.id, "po_no": p.po_no, "supplier_id": p.supplier_id, "status": p.status, "total_amount": p.total_amount} for p in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/purchase-orders/{po_id}", response_model=None, summary="查询采购订单详情")
async def get_po(
    po_id: str,
    svc: PurchaseOrderService = Depends(get_purchase_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """查询采购订单详情 (含明细)"""
    po = await svc.get_or_raise(po_id, tenant_id)
    items = await svc.get_items(po_id, tenant_id)
    return Result.ok(data={
        "id": po.id, "po_no": po.po_no, "supplier_id": po.supplier_id,
        "warehouse_id": po.warehouse_id, "status": po.status, "total_amount": po.total_amount,
        "items": [{"sku_id": i.sku_id, "quantity": i.quantity, "unit_price": i.unit_price, "received_qty": i.received_qty, "status": i.status} for i in items],
    }, trace_id=trace_id_var.get(""))


@router.put("/purchase-orders/{po_id}/status", response_model=None, summary="更新采购订单状态")
async def update_po_status(
    po_id: str,
    req: PurchaseOrderStatusRequest,
    svc: PurchaseOrderService = Depends(get_purchase_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """更新采购订单状态: 状态机校验"""
    po = await svc.update_status(po_id, tenant_id, new_status=req.status)
    return Result.ok(data={"id": po.id, "status": po.status}, trace_id=trace_id_var.get(""))


@router.post("/purchase-orders/{po_id}/items", response_model=None, summary="添加采购明细")
async def add_po_item(
    po_id: str,
    req: PurchaseOrderItemRequest,
    svc: PurchaseOrderService = Depends(get_purchase_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """添加采购明细: 状态校验 → 数量/价格校验 → 持久化"""
    kwargs = {}
    if req.expected_date:
        kwargs["expected_date"] = req.expected_date
    item = await svc.add_item(
        tenant_id=tenant_id, po_id=po_id, sku_id=req.sku_id,
        quantity=req.quantity, unit_price=req.unit_price, **kwargs,
    )
    return Result.ok(data={"id": item.id, "item_total": item.item_total}, trace_id=trace_id_var.get(""))


@router.post("/purchase-orders/{po_id}/confirm", response_model=None, summary="确认采购订单")
async def confirm_po(
    po_id: str,
    svc: PurchaseOrderService = Depends(get_purchase_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """确认采购订单: draft → pending_approval"""
    po = await svc.update_status(po_id, tenant_id, new_status="pending_approval")
    return Result.ok(data={"id": po.id, "status": po.status}, trace_id=trace_id_var.get(""))


@router.put("/purchase-orders/{po_id}/approve", response_model=None, summary="审批采购订单")
async def approve_po(
    po_id: str,
    action: str = Query(default="approved"),
    remark: str = Query(default=""),
    svc: PurchaseOrderService = Depends(get_purchase_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """审批采购订单: approved / rejected"""
    new_status = "approved" if action == "approved" else "rejected"
    po = await svc.update_status(po_id, tenant_id, new_status=new_status)
    return Result.ok(data={"id": po.id, "status": po.status, "action": action, "remark": remark}, trace_id=trace_id_var.get(""))


@router.post("/purchase-orders/{po_id}/receive", response_model=None, summary="收货")
async def receive_po(
    po_id: str,
    sku_id: str = Query(default=""),
    received_qty: int = Query(default=0, ge=0),
    svc: PurchaseOrderService = Depends(get_purchase_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """采购订单收货: ordered → partial_received / received"""
    new_status = "partial_received" if received_qty > 0 else "received"
    po = await svc.update_status(po_id, tenant_id, new_status=new_status)
    return Result.ok(data={"id": po.id, "status": po.status, "received_qty": received_qty}, trace_id=trace_id_var.get(""))


@router.post("/purchase-orders/{po_id}/cancel", response_model=None, summary="取消采购订单")
async def cancel_po(
    po_id: str,
    reason: str = Query(default=""),
    svc: PurchaseOrderService = Depends(get_purchase_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """取消采购订单"""
    po = await svc.update_status(po_id, tenant_id, new_status="cancelled")
    return Result.ok(data={"id": po.id, "status": po.status}, trace_id=trace_id_var.get(""))


@router.put("/purchase-orders/{po_id}", response_model=None, summary="更新采购订单")
async def update_po(
    po_id: str,
    warehouse_id: str = Query(default=""),
    expected_date: str = Query(default=""),
    remark: str = Query(default=""),
    svc: PurchaseOrderService = Depends(get_purchase_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """更新采购订单信息(仅草稿/待审批状态)"""
    kwargs = {}
    if warehouse_id:
        kwargs["warehouse_id"] = warehouse_id
    if expected_date:
        kwargs["expected_date"] = expected_date
    if remark:
        kwargs["remark"] = remark
    po = await svc.update(po_id, tenant_id, **kwargs)
    return Result.ok(data={"id": po.id, "updated": True}, trace_id=trace_id_var.get(""))


@router.delete("/purchase-orders/{po_id}", response_model=None, summary="删除采购订单")
async def delete_po(
    po_id: str,
    svc: PurchaseOrderService = Depends(get_purchase_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """软删除采购订单(仅草稿/已取消状态可删)"""
    deleted = await svc.soft_delete(po_id, tenant_id)
    return Result.ok(data={"id": po_id, "deleted": deleted}, trace_id=trace_id_var.get(""))

@router.post("/replenishment-plans", response_model=None, summary="创建补货计划")
async def create_replenishment_plan(
    req: ReplenishmentPlanCreateRequest,
    svc: ReplenishmentPlanService = Depends(get_replenishment_plan_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建补货计划"""
    import json
    plan = await svc.create(
        tenant_id=tenant_id, plan_no=req.plan_no, warehouse_id=req.warehouse_id,
        plan_type=req.plan_type, items_json=json.dumps(req.items, default=str),
    )
    return Result.ok(data={"id": plan.id, "plan_no": plan.plan_no, "status": plan.status}, trace_id=trace_id_var.get(""))


# ---------------------------------------------------------------------------
# 询价端点
# ---------------------------------------------------------------------------

@router.post("/inquiries", response_model=None, summary="创建询价单")
async def create_inquiry(
    req: InquiryCreateRequest,
    svc: InquiryService = Depends(get_inquiry_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建询价单: 唯一性校验(inquiry_no) → 持久化"""
    inquiry = await svc.create(
        tenant_id=tenant_id, inquiry_no=req.inquiry_no, title=req.inquiry_no,
    )
    return Result.ok(data={"id": inquiry.id, "inquiry_no": req.inquiry_no, "status": inquiry.status}, trace_id=trace_id_var.get(""))


@router.get("/inquiries", response_model=None, summary="查询询价单列表")
async def list_inquiries(
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: InquiryService = Depends(get_inquiry_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """分页查询询价单列表"""
    items, total = await svc.list_all(tenant_id, status=status, page=page, page_size=page_size)
    data = [{"id": i.id, "inquiry_no": i.inquiry_no, "title": i.title, "status": i.status} for i in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/inquiries/{inquiry_id}/quote", response_model=None, summary="提交询价报价")
async def submit_inquiry_quote(
    inquiry_id: str,
    req: InquiryQuoteRequest,
    svc: InquiryService = Depends(get_inquiry_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """提交询价报价"""
    quote = await svc.add_quote(
        tenant_id=tenant_id, inquiry_id=inquiry_id, supplier_id=req.supplier_id,
        quote_items=[{"unit_price": req.unit_price, "min_order_qty": req.min_order_qty}],
        total_amount=req.unit_price, lead_time_days=req.lead_time_days, remark=req.remark,
    )
    return Result.ok(data={"id": quote.id, "supplier_id": req.supplier_id, "unit_price": req.unit_price}, trace_id=trace_id_var.get(""))


@router.post("/inquiries/{inquiry_id}/select-supplier", response_model=None, summary="选定供应商")
async def select_inquiry_supplier(
    inquiry_id: str,
    supplier_id: str = Query(default=""),
    svc: InquiryService = Depends(get_inquiry_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """选定供应商: evaluating → awarded"""
    inquiry = await svc.update_status(inquiry_id, tenant_id, new_status="evaluating")
    return Result.ok(data={"id": inquiry.id, "selected_supplier_id": supplier_id}, trace_id=trace_id_var.get(""))


# ---------------------------------------------------------------------------
# 加工订单端点
# ---------------------------------------------------------------------------

@router.post("/processing-orders", response_model=None, summary="创建加工订单")
async def create_processing_order(
    req: ProcessingOrderCreateRequest,
    svc: PurchaseOrderService = Depends(get_purchase_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """创建加工订单 (复用采购订单，po_type=processing)"""
    kwargs = {}
    if req.expected_completion_date:
        kwargs["expected_delivery_date"] = datetime.fromisoformat(req.expected_completion_date)
    po = await svc.create(
        tenant_id=tenant_id, po_no=req.order_no, supplier_id=req.supplier_id,
        warehouse_id="", po_type="processing", currency=req.currency,
        total_amount=req.unit_price * req.quantity, remark=req.remark, **kwargs,
    )
    return Result.ok(data={"id": po.id, "order_no": req.order_no, "status": po.status}, trace_id=trace_id_var.get(""))


@router.get("/processing-orders", response_model=None, summary="查询加工订单列表")
async def list_processing_orders(
    status: str = Query(default=""),
    supplier_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: PurchaseOrderService = Depends(get_purchase_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """分页查询加工订单列表"""
    items, total = await svc.list_all(tenant_id, status=status, supplier_id=supplier_id, page=page, page_size=page_size)
    data = [{"id": p.id, "po_no": p.po_no, "supplier_id": p.supplier_id, "status": p.status, "total_amount": p.total_amount} for p in items if p.po_type == "processing"]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.put("/processing-orders/{order_id}/status", response_model=None, summary="更新加工订单状态")
async def update_processing_order_status(
    order_id: str,
    req: POStatusRequest,
    svc: PurchaseOrderService = Depends(get_purchase_order_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """更新加工订单状态"""
    po = await svc.update_status(order_id, tenant_id, new_status=req.status)
    return Result.ok(data={"id": po.id, "status": po.status}, trace_id=trace_id_var.get(""))


# ---------------------------------------------------------------------------
# 供应商详情端点
# ---------------------------------------------------------------------------

@router.get("/suppliers/{supplier_id}", response_model=None, summary="查询供应商详情")
async def get_supplier(
    supplier_id: str,
    svc: SupplierService = Depends(get_supplier_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    supplier = await svc.get_or_raise(supplier_id, tenant_id)
    return Result.ok(data={
        "id": supplier.id, "name": supplier.name, "code": supplier.code,
        "short_name": supplier.short_name, "contact_person": supplier.contact_person,
        "contact_phone": supplier.contact_phone, "contact_email": supplier.contact_email,
        "address": supplier.address, "region": supplier.region,
        "supplier_type": supplier.supplier_type, "cooperation_level": supplier.cooperation_level,
        "payment_terms": supplier.payment_terms, "lead_time_days": supplier.lead_time_days,
        "min_order_qty": supplier.min_order_qty, "quality_score": supplier.quality_score,
        "delivery_score": supplier.delivery_score, "status": supplier.status,
        "org_id": supplier.org_id, "created_at": str(supplier.created_at),
    }, trace_id=trace_id_var.get(""))


# ---------------------------------------------------------------------------
# 采购订单统计端点
# ---------------------------------------------------------------------------

@router.get("/purchase-orders/statistics/overview", response_model=None, summary="采购订单统计概览")
async def po_statistics_overview(
    supplier_id: str = Query(default=""),
    svc: SCMQueryService = Depends(get_scm_query_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    data = await svc.get_po_statistics(tenant_id, supplier_id=supplier_id)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


# ---------------------------------------------------------------------------
# 供应商统计优化端点
# ---------------------------------------------------------------------------

@router.get("/suppliers/statistics/overview", response_model=None, summary="供应商统计概览")
async def supplier_statistics_overview(
    svc: SCMQueryService = Depends(get_scm_query_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    data = await svc.get_supplier_statistics(tenant_id)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


# ---------------------------------------------------------------------------
# 补货计划详情端点
# ---------------------------------------------------------------------------

@router.get("/replenishment-plans", response_model=None, summary="查询补货计划列表")
async def list_replenishment_plans(
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: ReplenishmentPlanService = Depends(get_replenishment_plan_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    items, total = await svc.list_all(tenant_id, status=status, page=page, page_size=page_size)
    data = [{"id": p.id, "plan_no": p.plan_no, "warehouse_id": p.warehouse_id,
             "plan_type": p.plan_type, "status": p.status,
             "created_at": str(p.created_at) if p.created_at else None} for p in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


# ---------------------------------------------------------------------------
# 询价详情和比价端点
# ---------------------------------------------------------------------------

@router.get("/inquiries/{inquiry_id}", response_model=None, summary="查询询价单详情")
async def get_inquiry(
    inquiry_id: str,
    svc: InquiryService = Depends(get_inquiry_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    inquiry = await svc.get_or_raise(inquiry_id, tenant_id)
    return Result.ok(data={
        "id": inquiry.id, "inquiry_no": inquiry.inquiry_no, "title": inquiry.title,
        "status": inquiry.status, "deadline": str(inquiry.deadline) if inquiry.deadline else None,
        "created_at": str(inquiry.created_at) if inquiry.created_at else None,
    }, trace_id=trace_id_var.get(""))


@router.post("/inquiries/{inquiry_id}/compare", response_model=None, summary="询价比价")
async def compare_inquiry_quotes(
    inquiry_id: str,
    svc: InquiryService = Depends(get_inquiry_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    result = await svc.compare_quotes(inquiry_id, tenant_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/inquiries/{inquiry_id}/award/{quote_id}", response_model=None, summary="询价定标")
async def award_inquiry_quote(
    inquiry_id: str,
    quote_id: str,
    svc: InquiryService = Depends(get_inquiry_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    quote = await svc.award_quote(inquiry_id, quote_id, tenant_id)
    return Result.ok(data={"id": quote.id, "is_winner": True, "inquiry_id": inquiry_id}, trace_id=trace_id_var.get(""))


# ---------------------------------------------------------------------------
# 供应商评价批量端点
# ---------------------------------------------------------------------------

@router.post("/suppliers/batch-evaluate", response_model=None, summary="批量评价供应商")
async def batch_evaluate_suppliers(
    req: SupplierBatchEvaluateRequest,
    eval_svc: SupplierEvaluationService = Depends(get_supplier_evaluation_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    result = await eval_svc.batch_evaluate(tenant_id, req.evaluations)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


# ---------------------------------------------------------------------------
# 状态机查询端点
# ---------------------------------------------------------------------------

@router.get("/purchase-orders/status-transitions", response_model=None, summary="查询采购订单状态机")
async def get_po_status_transitions():
    return Result.ok(data=PO_STATUS_TRANSITIONS, trace_id=trace_id_var.get(""))
