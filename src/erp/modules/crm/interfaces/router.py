from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from erp.modules.crm.application.dtos import (
    ComplaintCreateRequest,
    ComplaintResolveRequest,
    CommunicationCreateRequest,
    CustomerCreateRequest,
    CustomerSearchRequest,
    CustomerTagCreateRequest,
    CustomerTagRequest,
    MessageReplyRequest,
    ReplyTemplateCreateRequest,
    ReturnProcessRequest,
    ReturnRefundCreateRequest,
    ReviewCreateRequest,
    ReviewReplyRequest,
    ReviewStatusRequest,
    SentimentAnalysisRequest,
    ServiceTicketCreateRequest,
    TicketAssignRequest,
    TicketResolveRequest,
    TicketSearchRequest,
)
from erp.modules.crm.application.services import (
    CRMQueryService,
    CommunicationService,
    ComplaintService,
    CustomerService,
    CustomerTagService,
    ReturnRefundService,
    ReviewReplyTemplateService,
    ReviewService,
    ServiceTicketService,
)
from erp.modules.crm.interfaces.deps import (
    get_crm_query_service,
    get_complaint_service,
    get_communication_service,
    get_customer_service,
    get_customer_tag_service,
    get_return_refund_service,
    get_review_reply_template_service,
    get_review_service,
    get_ticket_service,
)
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import NotFoundException, Result

router = APIRouter(prefix="/crm/v1", tags=["CRM - 客户关系管理"])


@router.post("/customers", response_model=None)
async def create_customer(req: CustomerCreateRequest,
                          svc: CustomerService = Depends(get_customer_service)):
    customer = await svc.create(tenant_id_var.get(""), **req.model_dump())
    return Result.ok(data={"id": customer.id, "customer_no": customer.customer_no}, trace_id=trace_id_var.get(""))


@router.get("/customers", response_model=None)
async def list_customers(platform: str | None = None, segment: str | None = None,
                         page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                         svc: CustomerService = Depends(get_customer_service)):
    offset = (page - 1) * page_size
    customers = await svc.list_by_tenant(tenant_id_var.get(""), platform=platform,
                                          segment=segment, offset=offset, limit=page_size)
    items = [{"id": c.id, "customer_no": c.customer_no, "name": c.name, "email": c.email,
              "platform": c.platform, "total_orders": c.total_orders, "total_amount": c.total_amount,
              "segment": c.segment} for c in customers]
    return Result.paginate(items=items, total=len(items), page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/customers/{customer_id}", response_model=None)
async def get_customer(customer_id: str, svc: CustomerService = Depends(get_customer_service)):
    customer = await svc.get_or_raise(customer_id, tenant_id_var.get(""))
    return Result.ok(data={"id": customer.id, "customer_no": customer.customer_no,
                           "name": customer.name, "email": customer.email,
                           "platform": customer.platform, "segment": customer.segment,
                           "total_orders": customer.total_orders, "total_amount": customer.total_amount},
                     trace_id=trace_id_var.get(""))


@router.put("/customers/{customer_id}", response_model=None, summary="更新客户信息")
async def update_customer(customer_id: str, name: str = "", email: str = "", phone: str = "",
                          segment: str = "",
                          svc: CustomerService = Depends(get_customer_service)):
    kwargs = {}
    if name:
        kwargs["name"] = name
    if email:
        kwargs["email"] = email
    if phone:
        kwargs["phone"] = phone
    if segment:
        kwargs["segment"] = segment
    customer = await svc.update(customer_id, tenant_id_var.get(""), **kwargs)
    return Result.ok(data={"id": customer.id, "name": customer.name}, trace_id=trace_id_var.get(""))


@router.delete("/customers/{customer_id}", response_model=None, summary="删除客户")
async def delete_customer(customer_id: str, svc: CustomerService = Depends(get_customer_service)):
    deleted = await svc.soft_delete(customer_id, tenant_id_var.get(""))
    return Result.ok(data={"id": customer_id, "deleted": deleted}, trace_id=trace_id_var.get(""))


@router.post("/customers/{customer_id}/tags", response_model=None)
async def add_customer_tags(customer_id: str, req: CustomerTagRequest,
                             svc: CustomerService = Depends(get_customer_service)):
    customer = await svc.add_tags(customer_id, req.tags)
    if not customer:
        raise NotFoundException(message=f"Customer '{customer_id}' not found")
    return Result.ok(data={"id": customer.id, "tags_json": customer.tags_json}, trace_id=trace_id_var.get(""))


@router.post("/customers/{customer_id}/classify-segment", response_model=None)
async def classify_segment(customer_id: str, svc: CustomerService = Depends(get_customer_service)):
    customer = await svc.auto_classify_segment(customer_id)
    if not customer:
        raise NotFoundException(message=f"Customer '{customer_id}' not found")
    return Result.ok(data={"id": customer.id, "segment": customer.segment}, trace_id=trace_id_var.get(""))


@router.post("/customers/batch-classify", response_model=None)
async def batch_classify(svc: CustomerService = Depends(get_customer_service)):
    count = await svc.batch_classify_segments(tenant_id_var.get(""))
    return Result.ok(data={"updated_count": count}, trace_id=trace_id_var.get(""))


@router.post("/tags", response_model=None)
async def create_tag(req: CustomerTagCreateRequest,
                     svc: CustomerTagService = Depends(get_customer_tag_service)):
    tag = await svc.create(tenant_id_var.get(""), name=req.name, color=req.color, tag_type=req.tag_type)
    return Result.ok(data={"id": tag.id, "name": tag.name}, trace_id=trace_id_var.get(""))


@router.get("/tags", response_model=None)
async def list_tags(svc: CustomerTagService = Depends(get_customer_tag_service)):
    tags = await svc.list_by_tenant(tenant_id_var.get(""))
    items = [{"id": t.id, "name": t.name, "color": t.color, "customer_count": t.customer_count} for t in tags]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.post("/communications", response_model=None)
async def create_communication(req: CommunicationCreateRequest,
                                svc: CommunicationService = Depends(get_communication_service)):
    comm = await svc.create(tenant_id_var.get(""), customer_id=req.customer_id,
                             channel=req.channel, direction=req.direction,
                             subject=req.subject, content=req.content, order_id=req.order_id)
    return Result.ok(data={"id": comm.id, "channel": comm.channel, "direction": comm.direction},
                     trace_id=trace_id_var.get(""))


@router.get("/customers/{customer_id}/communications", response_model=None)
async def list_communications(customer_id: str,
                               svc: CommunicationService = Depends(get_communication_service)):
    comms = await svc.list_by_customer(customer_id)
    items = [{"id": c.id, "channel": c.channel, "direction": c.direction, "subject": c.subject,
              "status": c.status, "created_at": c.created_at.isoformat() if c.created_at else ""}
             for c in comms]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.post("/reviews", response_model=None)
async def create_review(req: ReviewCreateRequest, svc: ReviewService = Depends(get_review_service)):
    review = await svc.create(tenant_id_var.get(""), platform=req.platform, store_id=req.store_id,
                               rating=req.rating, title=req.title, content=req.content,
                               sku_id=req.sku_id, order_id=req.order_id,
                               platform_review_id=req.platform_review_id)
    return Result.ok(data={"id": review.id, "rating": review.rating, "is_negative": review.is_negative},
                     trace_id=trace_id_var.get(""))


@router.get("/reviews", response_model=None)
async def list_reviews(platform: str | None = None, status: str | None = None,
                       is_negative: bool | None = None,
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       svc: ReviewService = Depends(get_review_service)):
    offset = (page - 1) * page_size
    reviews = await svc.list_by_tenant(tenant_id_var.get(""), platform=platform, status=status,
                                        is_negative=is_negative, offset=offset, limit=page_size)
    items = [{"id": r.id, "platform": r.platform, "rating": r.rating, "title": r.title,
              "is_negative": r.is_negative, "status": r.status,
              "review_date": r.review_date.isoformat() if r.review_date else ""}
             for r in reviews]
    return Result.paginate(items=items, total=len(items), page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.put("/reviews/{review_id}/status", response_model=None)
async def update_review_status(review_id: str, req: ReviewStatusRequest,
                                svc: ReviewService = Depends(get_review_service)):
    review = await svc.update_status(review_id, tenant_id_var.get(""), req.status)
    return Result.ok(data={"id": review.id, "status": review.status}, trace_id=trace_id_var.get(""))


@router.post("/reviews/{review_id}/reply", response_model=None)
async def reply_review(review_id: str, req: ReviewReplyRequest,
                        svc: ReviewService = Depends(get_review_service)):
    review = await svc.reply(review_id, tenant_id_var.get(""), req.reply, req.replied_by)
    return Result.ok(data={"id": review.id, "status": review.status}, trace_id=trace_id_var.get(""))


@router.get("/reviews/negative-unreplied", response_model=None)
async def get_negative_unreplied(limit: int = Query(50, ge=1, le=200),
                                  svc: ReviewService = Depends(get_review_service)):
    reviews = await svc.get_negative_unreplied(tenant_id_var.get(""), limit=limit)
    items = [{"id": r.id, "platform": r.platform, "rating": r.rating, "title": r.title,
              "status": r.status, "created_at": r.created_at.isoformat() if r.created_at else ""}
             for r in reviews]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.post("/tickets", response_model=None)
async def create_ticket(req: ServiceTicketCreateRequest,
                        svc: ServiceTicketService = Depends(get_ticket_service)):
    ticket = await svc.create(
        tenant_id_var.get(""), ticket_no=req.ticket_no, customer_id=req.customer_id,
        ticket_type=req.ticket_type, priority=req.priority, subject=req.subject,
        description=req.description, channel=req.channel, platform=req.platform,
        store_id=req.store_id, order_id=req.order_id,
    )
    return Result.ok(data={"id": ticket.id, "ticket_no": ticket.ticket_no, "status": ticket.status,
                           "priority": ticket.priority, "sla_due_at": ticket.sla_due_at.isoformat() if ticket.sla_due_at else ""},
                     trace_id=trace_id_var.get(""))


@router.get("/tickets", response_model=None)
async def list_tickets(status: str | None = None, ticket_type: str | None = None,
                       priority: str | None = None, assigned_to: str | None = None,
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       svc: ServiceTicketService = Depends(get_ticket_service)):
    offset = (page - 1) * page_size
    tickets = await svc.list_by_tenant(tenant_id_var.get(""), status=status, ticket_type=ticket_type,
                                        priority=priority, assigned_to=assigned_to,
                                        offset=offset, limit=page_size)
    items = [{"id": t.id, "ticket_no": t.ticket_no, "customer_id": t.customer_id,
              "ticket_type": t.ticket_type, "priority": t.priority, "status": t.status,
              "subject": t.subject, "assigned_to": t.assigned_to,
              "sla_due_at": t.sla_due_at.isoformat() if t.sla_due_at else ""}
             for t in tickets]
    return Result.paginate(items=items, total=len(items), page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.put("/tickets/{ticket_id}/status", response_model=None)
async def update_ticket_status(ticket_id: str, req: ReviewStatusRequest,
                                svc: ServiceTicketService = Depends(get_ticket_service)):
    ticket = await svc.update_status(ticket_id, tenant_id_var.get(""), req.status)
    return Result.ok(data={"id": ticket.id, "ticket_no": ticket.ticket_no, "status": ticket.status},
                     trace_id=trace_id_var.get(""))


@router.post("/tickets/{ticket_id}/assign", response_model=None)
async def assign_ticket(ticket_id: str, req: TicketAssignRequest,
                         svc: ServiceTicketService = Depends(get_ticket_service)):
    ticket = await svc.assign(ticket_id, tenant_id_var.get(""), req.assigned_to, req.assigned_group)
    return Result.ok(data={"id": ticket.id, "assigned_to": ticket.assigned_to, "status": ticket.status},
                     trace_id=trace_id_var.get(""))


@router.post("/tickets/{ticket_id}/resolve", response_model=None)
async def resolve_ticket(ticket_id: str, req: TicketResolveRequest,
                          svc: ServiceTicketService = Depends(get_ticket_service)):
    ticket = await svc.resolve(ticket_id, tenant_id_var.get(""), req.resolution, req.satisfaction_score)
    return Result.ok(data={"id": ticket.id, "status": ticket.status, "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else ""},
                     trace_id=trace_id_var.get(""))


@router.get("/tickets/overdue", response_model=None)
async def get_overdue_tickets(svc: ServiceTicketService = Depends(get_ticket_service)):
    tickets = await svc.get_overdue_tickets(tenant_id_var.get(""))
    items = [{"id": t.id, "ticket_no": t.ticket_no, "priority": t.priority, "status": t.status,
              "sla_due_at": t.sla_due_at.isoformat() if t.sla_due_at else ""}
             for t in tickets]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.post("/returns", response_model=None)
async def create_return(req: ReturnRefundCreateRequest,
                        svc: ReturnRefundService = Depends(get_return_refund_service)):
    rr = await svc.create(
        tenant_id_var.get(""), return_no=req.return_no, order_id=req.order_id,
        customer_id=req.customer_id, sku_id=req.sku_id, return_type=req.return_type,
        reason=req.reason, reason_code=req.reason_code, quantity=req.quantity,
        refund_amount=req.refund_amount, currency=req.currency,
        platform=req.platform, store_id=req.store_id, ticket_id=req.ticket_id,
    )
    return Result.ok(data={"id": rr.id, "return_no": rr.return_no, "status": rr.status},
                     trace_id=trace_id_var.get(""))


@router.get("/returns", response_model=None)
async def list_returns(status: str | None = None, order_id: str | None = None,
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       svc: ReturnRefundService = Depends(get_return_refund_service)):
    offset = (page - 1) * page_size
    returns = await svc.list_by_tenant(tenant_id_var.get(""), status=status, order_id=order_id,
                                        offset=offset, limit=page_size)
    items = [{"id": r.id, "return_no": r.return_no, "order_id": r.order_id, "return_type": r.return_type,
              "quantity": r.quantity, "refund_amount": r.refund_amount, "status": r.status}
             for r in returns]
    return Result.paginate(items=items, total=len(items), page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.put("/returns/{rr_id}/status", response_model=None)
async def update_return_status(rr_id: str, req: ReviewStatusRequest,
                                svc: ReturnRefundService = Depends(get_return_refund_service)):
    rr = await svc.update_status(rr_id, tenant_id_var.get(""), req.status)
    return Result.ok(data={"id": rr.id, "return_no": rr.return_no, "status": rr.status},
                     trace_id=trace_id_var.get(""))


@router.put("/returns/{rr_id}/process", response_model=None)
async def process_return(rr_id: str, req: ReturnProcessRequest,
                          svc: ReturnRefundService = Depends(get_return_refund_service)):
    new_status = "approved" if req.action == "approve" else "rejected"
    await svc.update_status(rr_id, tenant_id_var.get(""), new_status)
    return Result.ok(data={"id": rr_id, "action": req.action, "new_status": new_status,
                           "refund_amount": req.refund_amount, "remark": req.remark},
                     trace_id=trace_id_var.get(""))


@router.post("/complaints", response_model=None)
async def create_complaint(req: ComplaintCreateRequest,
                           svc: ComplaintService = Depends(get_complaint_service)):
    complaint = await svc.create(
        tenant_id_var.get(""), complaint_no=f"CP-{req.customer_id[:8]}",
        customer_id=req.customer_id, complaint_type=req.complaint_type,
        subject=req.subject, description=req.description,
        channel=req.channel, platform=req.platform, store_id=req.store_id,
        order_id=req.order_id,
    )
    return Result.ok(data={"id": complaint.id, "complaint_no": complaint.complaint_no,
                           "status": complaint.status, "complaint_type": complaint.complaint_type},
                     trace_id=trace_id_var.get(""))


@router.get("/complaints", response_model=None)
async def list_complaints(status: str | None = None, priority: str | None = None,
                           page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                           svc: ComplaintService = Depends(get_complaint_service)):
    complaints, total = await svc.list_all(tenant_id_var.get(""), status=status or "",
                                            page=page, page_size=page_size)
    items = [{"id": c.id, "complaint_no": c.complaint_no, "customer_id": c.customer_id,
              "complaint_type": c.complaint_type, "severity": c.severity,
              "status": c.status, "subject": c.subject}
             for c in complaints]
    return Result.paginate(items=items, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.put("/complaints/{complaint_id}/resolve", response_model=None)
async def resolve_complaint(complaint_id: str, req: ComplaintResolveRequest,
                             svc: ComplaintService = Depends(get_complaint_service)):
    complaint = await svc.resolve(complaint_id, tenant_id_var.get(""), req.resolution, "other")
    return Result.ok(data={"id": complaint.id, "status": complaint.status,
                           "resolved_at": complaint.resolved_at.isoformat() if complaint.resolved_at else ""},
                     trace_id=trace_id_var.get(""))


@router.get("/messages", response_model=None)
async def list_messages(customer_id: str | None = None, channel: str | None = None,
                         status: str | None = None,
                         page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                         svc: CommunicationService = Depends(get_communication_service)):
    if customer_id:
        comms = await svc.list_by_customer(customer_id)
    else:
        comms = []
    items = [{"id": c.id, "channel": c.channel, "direction": c.direction,
              "subject": c.subject, "status": c.status,
              "created_at": c.created_at.isoformat() if c.created_at else ""}
             for c in comms]
    return Result.paginate(items=items, total=len(items), page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/messages/{message_id}/reply", response_model=None)
async def reply_message(message_id: str, req: MessageReplyRequest,
                         svc: CommunicationService = Depends(get_communication_service)):
    original = await svc.get_by_id(message_id)
    customer_id = original.customer_id if original else ""
    channel = original.channel if original else "email"
    comm = await svc.create(tenant_id_var.get(""), customer_id=customer_id,
                             channel=channel, direction="outbound",
                             subject=f"Re: {original.subject}" if original and original.subject else "",
                             content=req.content, order_id=original.order_id if original else "")
    return Result.ok(data={"id": comm.id, "direction": "outbound", "status": comm.status,
                           "in_reply_to": message_id},
                     trace_id=trace_id_var.get(""))


@router.get("/customers/{customer_id}/returns", response_model=None)
async def list_customer_returns(customer_id: str,
                                 svc: ReturnRefundService = Depends(get_return_refund_service)):
    returns = await svc.list_by_customer(customer_id, tenant_id_var.get(""))
    items = [{"id": r.id, "return_no": r.return_no, "return_type": r.return_type,
              "quantity": r.quantity, "refund_amount": r.refund_amount, "status": r.status}
             for r in returns]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


# ──── 统计与搜索端点 ────


@router.get("/statistics", response_model=None, summary="CRM运营统计概览")
async def get_crm_statistics(
    svc: CRMQueryService = Depends(get_crm_query_service),
):
    """获取CRM运营统计概览: 客户/工单/退货/评价/投诉等核心指标"""
    result = await svc.get_statistics(tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/customers/search", response_model=None, summary="搜索客户")
async def search_customers(
    req: CustomerSearchRequest,
    svc: CRMQueryService = Depends(get_crm_query_service),
):
    """多维度搜索客户: 关键词/平台/分群/状态/国家"""
    items, total = await svc.search_customers(
        tenant_id_var.get(""), keyword=req.keyword, platform=req.platform,
        segment=req.segment, status=req.status, country=req.country,
        page=req.page, page_size=req.page_size,
    )
    data = [{"id": c.id, "customer_no": c.customer_no, "name": c.name, "email": c.email,
             "platform": c.platform, "segment": c.segment, "total_orders": c.total_orders,
             "total_amount": c.total_amount, "status": c.status} for c in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


@router.post("/tickets/search", response_model=None, summary="搜索工单")
async def search_tickets(
    req: TicketSearchRequest,
    svc: CRMQueryService = Depends(get_crm_query_service),
):
    """多维度搜索工单: 关键词/状态/类型/优先级/处理人"""
    items, total = await svc.search_tickets(
        tenant_id_var.get(""), keyword=req.keyword, status=req.status,
        ticket_type=req.ticket_type, priority=req.priority, assigned_to=req.assigned_to,
        page=req.page, page_size=req.page_size,
    )
    data = [{"id": t.id, "ticket_no": t.ticket_no, "customer_id": t.customer_id,
             "ticket_type": t.ticket_type, "priority": t.priority, "status": t.status,
             "subject": t.subject, "assigned_to": t.assigned_to} for t in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


@router.get("/refunds", response_model=None)
async def list_refunds(status: str | None = None, order_id: str | None = None,
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       svc: ReturnRefundService = Depends(get_return_refund_service)):
    offset = (page - 1) * page_size
    returns = await svc.list_by_tenant(tenant_id_var.get(""), status=status, order_id=order_id,
                                        offset=offset, limit=page_size)
    items = [{"id": r.id, "return_no": r.return_no, "refund_amount": r.refund_amount,
              "currency": r.currency, "status": r.status}
             for r in returns if r.return_type in ("refund", "return")]
    return Result.paginate(items=items, total=len(items), page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/reply-templates", response_model=None)
async def list_reply_templates(channel: str = Query(default=""), category: str = Query(default=""),
                                svc: ReviewReplyTemplateService = Depends(get_review_reply_template_service)):
    templates, total = await svc.list_all(tenant_id_var.get(""), category=category)
    items = [{"id": t.id, "name": t.name, "channel": t.platform, "language": t.language,
              "category": t.category, "content": t.content_template}
             for t in templates]
    if channel:
        items = [t for t in items if t["channel"] == channel]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@router.post("/reply-templates", response_model=None)
async def create_reply_template(req: ReplyTemplateCreateRequest,
                                 svc: ReviewReplyTemplateService = Depends(get_review_reply_template_service)):
    template = await svc.create(
        tenant_id_var.get(""), name=req.name, category=req.category,
        content_template=req.template_content, language=req.language, platform=req.channel,
    )
    return Result.ok(data={"id": template.id, "name": template.name, "category": template.category},
                     trace_id=trace_id_var.get(""))


pms_router = APIRouter(prefix="/crm/out/v1", tags=["CRM-Out - 外部交互"])


@pms_router.get("/reviews/{asin}", response_model=None)
async def pms_reviews_by_asin(asin: str, svc: ReviewService = Depends(get_review_service)):
    reviews = await svc.list_by_tenant(tenant_id_var.get(""), offset=0, limit=100)
    matched = [r for r in reviews if r.sku_id == asin]
    items = [{"id": r.id, "rating": r.rating, "title": r.title, "content": r.content,
              "is_negative": r.is_negative, "status": r.status} for r in matched]
    return Result.ok(data={"asin": asin, "reviews": items, "total": len(items)}, trace_id=trace_id_var.get(""))


@pms_router.get("/complaints", response_model=None)
async def pms_complaints(asin: str = Query(default=""),
                          svc: ComplaintService = Depends(get_complaint_service)):
    complaints, total = await svc.list_all(tenant_id_var.get(""), page=1, page_size=100)
    items = [{"id": c.id, "complaint_no": c.complaint_no, "subject": c.subject,
              "status": c.status, "severity": c.severity, "complaint_type": c.complaint_type}
             for c in complaints]
    return Result.ok(data=items, trace_id=trace_id_var.get(""))


@pms_router.post("/sentiment-analysis", response_model=None)
async def receive_sentiment_analysis(req: SentimentAnalysisRequest,
                                      svc: ReviewService = Depends(get_review_service)):
    review = await svc.get_or_raise(req.review_id, tenant_id_var.get(""))
    new_status = "acknowledged" if review.status == "pending" else review.status
    await svc.update_status(req.review_id, tenant_id_var.get(""), new_status)
    return Result.ok(data={"review_id": req.review_id, "sentiment_score": req.sentiment_score,
                           "sentiment_label": req.sentiment_label, "status": new_status},
                     trace_id=trace_id_var.get(""))
