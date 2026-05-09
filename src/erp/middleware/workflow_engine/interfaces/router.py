from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.middleware.workflow_engine.application.services import WorkflowEngineService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/workflow", tags=["Workflow Engine - 工作流引擎"])


class DefinitionCreateRequest(BaseModel):
    flow_code: str = Field(min_length=1, max_length=64)
    flow_name: str = Field(min_length=1, max_length=128)
    domain: str = Field(min_length=1, max_length=32)
    target_type: str = Field(min_length=1, max_length=64)
    nodes: list[dict]
    description: str = Field(default="")


class InstanceStartRequest(BaseModel):
    flow_code: str = Field(min_length=1)
    business_id: str = Field(min_length=1)
    business_type: str = Field(min_length=1)
    initiator_id: str = Field(min_length=1)


class TaskCompleteRequest(BaseModel):
    action: str = Field(pattern="^(approved|rejected|cancelled)$")
    comment: str = Field(default="")


@router.post("/definitions", response_model=None)
async def create_definition(req: DefinitionCreateRequest, session: AsyncSession = Depends(get_db_session)):
    svc = WorkflowEngineService(session)
    result = await svc.create_definition(tenant_id_var.get(""), req.flow_code, req.flow_name,
                                          req.domain, req.target_type, req.nodes, req.description)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/definitions", response_model=None)
async def list_definitions(domain: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    svc = WorkflowEngineService(session)
    result = await svc.list_definitions(tenant_id_var.get(""), domain)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/instances", response_model=None)
async def start_instance(req: InstanceStartRequest, session: AsyncSession = Depends(get_db_session)):
    svc = WorkflowEngineService(session)
    result = await svc.start_instance(tenant_id_var.get(""), req.flow_code, req.business_id,
                                       req.business_type, req.initiator_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/instances/{instance_id}", response_model=None)
async def get_instance(instance_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = WorkflowEngineService(session)
    result = await svc.get_instance(tenant_id_var.get(""), instance_id)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/tasks/{task_id}/complete", response_model=None)
async def complete_task(task_id: str, req: TaskCompleteRequest, session: AsyncSession = Depends(get_db_session)):
    svc = WorkflowEngineService(session)
    result = await svc.complete_task(tenant_id_var.get(""), task_id, req.action, req.comment)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
