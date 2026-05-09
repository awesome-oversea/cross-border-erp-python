from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func as sa_func
from sqlalchemy import select

from erp.shared.context import actor_id_var, tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import NotFoundException, Result, ValidationException
from erp.shared.workflow.entities import ApprovalFlowDefinitionEntity, ApprovalInstanceEntity
from erp.shared.workflow.models import ApprovalAction, ApprovalActionRequest, ApprovalNodeConfig, ApprovalSubmitRequest
from erp.shared.workflow.service import ApprovalService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/approval", tags=["SYS-Approval"])


class FlowDefinitionRequest(BaseModel):
    flow_code: str = Field(..., min_length=1, max_length=100)
    flow_name: str = Field(..., min_length=1, max_length=200)
    domain: str = Field(..., min_length=1, max_length=50)
    target_type: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="")
    nodes: list[ApprovalNodeConfig] = Field(..., min_length=1)


class FlowUpdateRequest(BaseModel):
    flow_name: str = Field(default="", max_length=200)
    description: str = Field(default="")
    nodes: list[ApprovalNodeConfig] | None = None


class SubmitApprovalRequest(BaseModel):
    flow_code: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    target_type: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = Field(default="")


class ActionApprovalRequest(BaseModel):
    action: str = Field(..., pattern=r"^(approve|reject|cancel|withdraw|delegate)$")
    comment: str = Field(default="")
    delegate_to: str = Field(default="")


BUSINESS_DEFAULT_FLOWS = [
    {
        "flow_code": "purchase_approval",
        "flow_name": "采购审批流程",
        "domain": "scm",
        "target_type": "purchase_order",
        "description": "采购单多级审批流程",
        "nodes": [
            {"node_id": "n1", "node_name": "采购主管审批", "node_type": "role",
             "approver_role_codes": ["purchase_manager"], "min_approvals": 1, "sort_order": 0},
            {"node_id": "n2", "node_name": "财务审批", "node_type": "role",
             "approver_role_codes": ["finance_manager"], "min_approvals": 1, "sort_order": 1},
            {"node_id": "n3", "node_name": "总经理审批", "node_type": "role",
             "approver_role_codes": ["general_manager"], "min_approvals": 1, "sort_order": 2},
        ],
    },
    {
        "flow_code": "payment_approval",
        "flow_name": "付款审批流程",
        "domain": "fms",
        "target_type": "payment_request",
        "description": "付款申请多级审批流程",
        "nodes": [
            {"node_id": "n1", "node_name": "部门主管审批", "node_type": "role",
             "approver_role_codes": ["dept_manager"], "min_approvals": 1, "sort_order": 0},
            {"node_id": "n2", "node_name": "财务经理审批", "node_type": "role",
             "approver_role_codes": ["finance_manager"], "min_approvals": 1, "sort_order": 1},
            {"node_id": "n3", "node_name": "出纳确认", "node_type": "role",
             "approver_role_codes": ["cashier"], "min_approvals": 1, "sort_order": 2},
        ],
    },
    {
        "flow_code": "refund_approval",
        "flow_name": "退款/售后审批流程",
        "domain": "crm",
        "target_type": "after_sale_order",
        "description": "退款和售后单审批流程",
        "nodes": [
            {"node_id": "n1", "node_name": "客服主管审批", "node_type": "role",
             "approver_role_codes": ["cs_manager"], "min_approvals": 1, "sort_order": 0},
            {"node_id": "n2", "node_name": "财务确认退款", "node_type": "role",
             "approver_role_codes": ["finance_staff"], "min_approvals": 1, "sort_order": 1},
        ],
    },
    {
        "flow_code": "pms_recommendation_approval",
        "flow_name": "PMS建议审批流程",
        "domain": "sys",
        "target_type": "pms_recommendation",
        "description": "AI建议审批执行流程",
        "nodes": [
            {"node_id": "n1", "node_name": "业务负责人确认", "node_type": "role",
             "approver_role_codes": ["biz_owner"], "min_approvals": 1, "sort_order": 0},
            {"node_id": "n2", "node_name": "主管审批执行", "node_type": "role",
             "approver_role_codes": ["manager"], "min_approvals": 1, "sort_order": 1},
        ],
    },
    {
        "flow_code": "listing_approval",
        "flow_name": "Listing刊登审批流程",
        "domain": "som",
        "target_type": "listing",
        "description": "Listing刊登内容审核流程",
        "nodes": [
            {"node_id": "n1", "node_name": "运营主管审核", "node_type": "role",
             "approver_role_codes": ["ops_manager"], "min_approvals": 1, "sort_order": 0},
        ],
    },
    {
        "flow_code": "inventory_adjustment_approval",
        "flow_name": "库存调整审批流程",
        "domain": "wms",
        "target_type": "inventory_adjustment",
        "description": "库存盘点调整审批流程",
        "nodes": [
            {"node_id": "n1", "node_name": "仓库主管审批", "node_type": "role",
             "approver_role_codes": ["warehouse_manager"], "min_approvals": 1, "sort_order": 0},
            {"node_id": "n2", "node_name": "财务确认", "node_type": "role",
             "approver_role_codes": ["finance_staff"], "min_approvals": 1, "sort_order": 1},
        ],
    },
]


@router.post("/flows", response_model=None)
async def define_flow(req: FlowDefinitionRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ApprovalService(session)
    flow = await svc.define_flow(
        tenant_id=tenant_id_var.get(""),
        flow_code=req.flow_code,
        flow_name=req.flow_name,
        domain=req.domain,
        target_type=req.target_type,
        nodes=req.nodes,
        description=req.description,
    )
    return Result.ok(
        data={"id": flow.id, "flow_code": flow.flow_code, "flow_name": flow.flow_name,
              "domain": flow.domain, "target_type": flow.target_type,
              "node_count": len(flow.nodes)},
        trace_id=trace_id_var.get(""),
    )


@router.get("/flows", response_model=None)
async def list_flows(
    domain: str = Query(default=""),
    target_type: str = Query(default=""),
    session: AsyncSession = Depends(get_db_session),
):
    conditions = [ApprovalFlowDefinitionEntity.tenant_id == tenant_id_var.get("")]
    if domain:
        conditions.append(ApprovalFlowDefinitionEntity.domain == domain)
    if target_type:
        conditions.append(ApprovalFlowDefinitionEntity.target_type == target_type)

    stmt = select(ApprovalFlowDefinitionEntity).where(
        *conditions
    ).order_by(ApprovalFlowDefinitionEntity.domain, ApprovalFlowDefinitionEntity.flow_code)
    result = await session.execute(stmt)
    flows = result.scalars().all()

    data = []
    for f in flows:
        nodes = []
        with contextlib.suppress(Exception):
            nodes = json.loads(f.nodes_json) if f.nodes_json else []
        data.append({
            "id": f.id, "flow_code": f.flow_code, "flow_name": f.flow_name,
            "domain": f.domain, "target_type": f.target_type,
            "description": f.description, "status": f.status,
            "version": f.version, "node_count": len(nodes),
        })
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/flows/{flow_id}", response_model=None)
async def get_flow(flow_id: str, session: AsyncSession = Depends(get_db_session)):
    stmt = select(ApprovalFlowDefinitionEntity).where(
        ApprovalFlowDefinitionEntity.id == flow_id,
        ApprovalFlowDefinitionEntity.tenant_id == tenant_id_var.get(""),
    )
    result = await session.execute(stmt)
    flow = result.scalar_one_or_none()
    if not flow:
        return Result.fail(code=404, message="Flow not found", trace_id=trace_id_var.get(""))

    nodes = []
    with contextlib.suppress(Exception):
        nodes = json.loads(flow.nodes_json) if flow.nodes_json else []
    return Result.ok(
        data={
            "id": flow.id, "flow_code": flow.flow_code, "flow_name": flow.flow_name,
            "domain": flow.domain, "target_type": flow.target_type,
            "description": flow.description, "status": flow.status,
            "version": flow.version, "nodes": nodes,
            "created_at": flow.created_at.isoformat() if flow.created_at else None,
            "updated_at": flow.updated_at.isoformat() if flow.updated_at else None,
        },
        trace_id=trace_id_var.get(""),
    )


@router.put("/flows/{flow_id}", response_model=None)
async def update_flow(flow_id: str, req: FlowUpdateRequest, session: AsyncSession = Depends(get_db_session)):
    stmt = select(ApprovalFlowDefinitionEntity).where(
        ApprovalFlowDefinitionEntity.id == flow_id,
        ApprovalFlowDefinitionEntity.tenant_id == tenant_id_var.get(""),
    )
    result = await session.execute(stmt)
    flow = result.scalar_one_or_none()
    if not flow:
        raise NotFoundException(message=f"Flow '{flow_id}' not found")

    if req.flow_name:
        flow.flow_name = req.flow_name
    if req.description:
        flow.description = req.description
    if req.nodes is not None:
        flow.nodes_json = json.dumps([n.model_dump() for n in req.nodes], default=str)
        flow.version += 1
    await session.flush()

    return Result.ok(
        data={"id": flow.id, "flow_code": flow.flow_code, "version": flow.version},
        trace_id=trace_id_var.get(""),
    )


@router.put("/flows/{flow_id}/deactivate", response_model=None)
async def deactivate_flow(flow_id: str, session: AsyncSession = Depends(get_db_session)):
    stmt = select(ApprovalFlowDefinitionEntity).where(
        ApprovalFlowDefinitionEntity.id == flow_id,
        ApprovalFlowDefinitionEntity.tenant_id == tenant_id_var.get(""),
    )
    result = await session.execute(stmt)
    flow = result.scalar_one_or_none()
    if not flow:
        raise NotFoundException(message=f"Flow '{flow_id}' not found")
    flow.status = "inactive"
    await session.flush()
    return Result.ok(data={"id": flow.id, "status": flow.status}, trace_id=trace_id_var.get(""))


@router.put("/flows/{flow_id}/activate", response_model=None)
async def activate_flow(flow_id: str, session: AsyncSession = Depends(get_db_session)):
    stmt = select(ApprovalFlowDefinitionEntity).where(
        ApprovalFlowDefinitionEntity.id == flow_id,
        ApprovalFlowDefinitionEntity.tenant_id == tenant_id_var.get(""),
    )
    result = await session.execute(stmt)
    flow = result.scalar_one_or_none()
    if not flow:
        raise NotFoundException(message=f"Flow '{flow_id}' not found")
    flow.status = "active"
    await session.flush()
    return Result.ok(data={"id": flow.id, "status": flow.status}, trace_id=trace_id_var.get(""))


@router.post("/submit", response_model=None)
async def submit_approval(req: SubmitApprovalRequest, session: AsyncSession = Depends(get_db_session)):
    svc = ApprovalService(session)
    instance = await svc.submit(
        tenant_id=tenant_id_var.get(""),
        req=ApprovalSubmitRequest(
            flow_code=req.flow_code, domain=req.domain,
            target_type=req.target_type, target_id=req.target_id,
            title=req.title, description=req.description,
        ),
        submitted_by=actor_id_var.get(""),
    )
    return Result.ok(
        data={"id": instance.id, "flow_code": instance.flow_code,
              "status": instance.status.value, "target_id": instance.target_id},
        trace_id=trace_id_var.get(""),
    )


@router.put("/tasks/{task_id}/action", response_model=None)
async def action_approval(task_id: str, req: ActionApprovalRequest, session: AsyncSession = Depends(get_db_session)):
    action_map = {
        "approve": ApprovalAction.APPROVE, "reject": ApprovalAction.REJECT,
        "cancel": ApprovalAction.CANCEL, "withdraw": ApprovalAction.WITHDRAW,
        "delegate": ApprovalAction.DELEGATE,
    }
    action_enum = action_map.get(req.action)
    if not action_enum:
        raise ValidationException(message=f"Invalid action: {req.action}")

    svc = ApprovalService(session)
    instance = await svc.approve(
        task_id=task_id,
        tenant_id=tenant_id_var.get(""),
        req=ApprovalActionRequest(action=action_enum, comment=req.comment),
        actor_id=actor_id_var.get(""),
    )
    return Result.ok(
        data={"instance_id": instance.id, "status": instance.status.value},
        trace_id=trace_id_var.get(""),
    )


@router.get("/instances", response_model=None)
async def list_instances(
    domain: str = Query(default=""),
    target_type: str = Query(default=""),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    conditions = [ApprovalInstanceEntity.tenant_id == tenant_id_var.get("")]
    if domain:
        conditions.append(ApprovalInstanceEntity.domain == domain)
    if target_type:
        conditions.append(ApprovalInstanceEntity.target_type == target_type)
    if status:
        conditions.append(ApprovalInstanceEntity.status == status)

    count_stmt = select(sa_func.count()).select_from(ApprovalInstanceEntity).where(*conditions)
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = select(ApprovalInstanceEntity).where(*conditions).order_by(
        ApprovalInstanceEntity.created_at.desc()
    ).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    instances = result.scalars().all()

    data = [{
        "id": i.id, "flow_code": i.flow_code, "domain": i.domain,
        "target_type": i.target_type, "target_id": i.target_id,
        "title": i.title, "status": i.status,
        "submitted_by": i.submitted_by,
        "submitted_at": i.submitted_at.isoformat() if i.submitted_at else None,
        "completed_at": i.completed_at.isoformat() if i.completed_at else None,
    } for i in instances]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/instances/{instance_id}", response_model=None)
async def get_instance(instance_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = ApprovalService(session)
    instance = await svc.get_instance_or_raise(instance_id, tenant_id_var.get(""))
    tasks = await svc.get_instance_tasks(instance_id, tenant_id_var.get(""))
    return Result.ok(
        data={
            "id": instance.id, "flow_code": instance.flow_code,
            "domain": instance.domain, "target_type": instance.target_type,
            "target_id": instance.target_id, "title": instance.title,
            "description": instance.description, "status": instance.status,
            "submitted_by": instance.submitted_by,
            "submitted_at": instance.submitted_at.isoformat() if instance.submitted_at else None,
            "completed_at": instance.completed_at.isoformat() if instance.completed_at else None,
            "tasks": [{
                "id": t.id, "node_name": t.node_name, "assignee_id": t.assignee_id,
                "action": t.action, "comment": t.comment, "status": t.status,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            } for t in tasks],
        },
        trace_id=trace_id_var.get(""),
    )


@router.get("/pending-tasks", response_model=None)
async def get_my_pending_tasks(
    assignee_id: str = Query(default=""),
    session: AsyncSession = Depends(get_db_session),
):
    svc = ApprovalService(session)
    aid = assignee_id or actor_id_var.get("")
    tasks = await svc.get_pending_tasks(tenant_id_var.get(""), assignee_id=aid)
    data = [{
        "id": t.id, "instance_id": t.instance_id, "node_name": t.node_name,
        "assignee_id": t.assignee_id, "status": t.status,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    } for t in tasks]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/init-defaults", response_model=None)
async def init_default_flows(session: AsyncSession = Depends(get_db_session)):
    svc = ApprovalService(session)
    tenant_id = tenant_id_var.get("")
    created = []
    for flow_def in BUSINESS_DEFAULT_FLOWS:
        nodes = [ApprovalNodeConfig(**n) for n in flow_def["nodes"]]
        try:
            flow = await svc.define_flow(
                tenant_id=tenant_id,
                flow_code=flow_def["flow_code"],
                flow_name=flow_def["flow_name"],
                domain=flow_def["domain"],
                target_type=flow_def["target_type"],
                nodes=nodes,
                description=flow_def.get("description", ""),
            )
            created.append(flow.flow_code)
        except Exception:
            continue
    return Result.ok(data={"created_flows": created, "count": len(created)}, trace_id=trace_id_var.get(""))
