"""
CRM 外部交互 API 路由

本模块定义客户关系管理系统与外部系统交互的 REST API 端点。
路径规范: /crm/out/v1/{resource}

端点:
  - 客户同步:   POST /customers/sync          (供 OMS 系统同步客户数据)
  - 评价推送:   POST /reviews/push             (供 SOM 系统推送评价)
  - 退货通知:   POST /returns/notify           (供 OMS 系统通知退货)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from erp.modules.crm.application.services import CustomerService, ReviewService, ReturnRefundService
from erp.modules.crm.interfaces.deps import get_customer_service, get_review_service, get_return_refund_service
from erp.shared.context import get_current_tenant_id, trace_id_var
from erp.shared.exceptions import Result

router = APIRouter(prefix="/crm/out/v1", tags=["CRM-Outbound"])


class CustomerSyncRequest(BaseModel):
    platform: str = Field(..., min_length=1, description="平台")
    platform_customer_id: str = Field(default="", description="平台客户ID")
    name: str = Field(default="", description="客户名称")
    email: str = Field(default="", description="邮箱")
    phone: str = Field(default="", description="电话")
    country: str = Field(default="", description="国家")
    order_amount: float = Field(default=0.0, description="订单金额")
    source: str = Field(default="oms", description="来源系统")


class ReviewPushRequest(BaseModel):
    platform: str = Field(..., min_length=1, description="平台")
    store_id: str = Field(default="", description="店铺ID")
    sku_id: str = Field(default="", description="SKU ID")
    rating: int = Field(default=5, ge=1, le=5, description="评分")
    content: str = Field(default="", description="评价内容")
    reviewer: str = Field(default="", description="评价人")
    source: str = Field(default="som", description="来源系统")


class ReturnNotifyRequest(BaseModel):
    order_id: str = Field(..., min_length=1, description="关联订单ID")
    return_type: str = Field(default="refund_only", description="退货类型")
    reason: str = Field(default="", description="退货原因")
    amount: float = Field(default=0.0, ge=0, description="退款金额")
    currency: str = Field(default="CNY", description="币种")
    source: str = Field(default="oms", description="来源系统")


@router.post("/customers/sync", response_model=None, summary="客户数据同步(外部)")
async def sync_customer(
    req: CustomerSyncRequest,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """供外部系统 (OMS) 同步客户数据"""
    return Result.ok(data={
        "platform": req.platform, "name": req.name,
        "status": "synced", "source": req.source,
    }, trace_id=trace_id_var.get(""))


@router.post("/reviews/push", response_model=None, summary="评价推送(外部)")
async def push_review(
    req: ReviewPushRequest,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """供外部系统 (SOM) 推送评价数据"""
    return Result.ok(data={
        "platform": req.platform, "sku_id": req.sku_id,
        "rating": req.rating, "status": "received",
    }, trace_id=trace_id_var.get(""))


@router.post("/returns/notify", response_model=None, summary="退货通知(外部)")
async def notify_return(
    req: ReturnNotifyRequest,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """供外部系统 (OMS) 通知退货"""
    return Result.ok(data={
        "order_id": req.order_id, "return_type": req.return_type,
        "amount": req.amount, "currency": req.currency,
        "status": "notified",
    }, trace_id=trace_id_var.get(""))
