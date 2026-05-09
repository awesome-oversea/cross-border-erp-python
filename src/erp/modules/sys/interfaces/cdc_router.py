from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.sys.domain.cdc_models import CDCEvent, CDCIngestionService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/cdc", tags=["SYS-CDC"])


class IngestEventRequest(BaseModel):
    source_schema: str = Field(..., min_length=1, max_length=50)
    source_table: str = Field(..., min_length=1, max_length=100)
    operation: str = Field(..., min_length=1, max_length=5)
    before_data: dict = Field(default_factory=dict)
    after_data: dict = Field(default_factory=dict)
    changed_columns: list = Field(default_factory=list)
    tenant_id: str = Field(default="")
    timestamp: str = Field(default="")
    lsn: str = Field(default="")
    transaction_id: str = Field(default="")


class CreatePipelineRequest(BaseModel):
    pipeline_name: str = Field(..., min_length=1, max_length=200)
    pipeline_code: str = Field(..., min_length=1, max_length=100)
    source_schema: str = Field(..., min_length=1, max_length=50)
    source_table: str = Field(..., min_length=1, max_length=100)
    handler_type: str = Field(default="kafka", max_length=50)
    handler_config: dict = Field(default_factory=dict)
    topic_name: str = Field(default="", max_length=200)
    filter_condition: dict = Field(default_factory=dict)
    transform_config: dict = Field(default_factory=dict)
    batch_size: int = Field(default=100, ge=1, le=1000)
    max_retries: int = Field(default=3, ge=0, le=10)
    description: str = Field(default="", max_length=500)


@router.post("/events", response_model=None)
async def ingest_event(req: IngestEventRequest, session: AsyncSession = Depends(get_db_session)):
    svc = CDCIngestionService(session)
    event = CDCEvent(
        source_schema=req.source_schema,
        source_table=req.source_table,
        operation=req.operation,
        before_data=req.before_data,
        after_data=req.after_data,
        changed_columns=req.changed_columns,
        tenant_id=req.tenant_id or tenant_id_var.get(""),
        timestamp=req.timestamp,
        lsn=req.lsn,
        transaction_id=req.transaction_id,
    )
    record = await svc.ingest_event(event)
    return Result.ok(
        data={"id": record.id, "source": f"{record.source_schema}.{record.source_table}",
              "operation": record.operation, "status": record.status},
        trace_id=trace_id_var.get(""),
    )


@router.post("/events/process", response_model=None)
async def process_pending_events(
    batch_size: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db_session),
):
    svc = CDCIngestionService(session)
    result = await svc.process_pending_events(tenant_id=tenant_id_var.get(""), batch_size=batch_size)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/events/retry", response_model=None)
async def retry_failed_events(
    batch_size: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    svc = CDCIngestionService(session)
    result = await svc.retry_failed_events(tenant_id=tenant_id_var.get(""), batch_size=batch_size)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/events/stats", response_model=None)
async def get_event_stats(
    source_schema: str = Query(default=""),
    hours: int = Query(default=24, ge=1, le=720),
    session: AsyncSession = Depends(get_db_session),
):
    svc = CDCIngestionService(session)
    stats = await svc.get_event_stats(
        tenant_id=tenant_id_var.get(""), source_schema=source_schema, hours=hours,
    )
    return Result.ok(data=stats, trace_id=trace_id_var.get(""))


@router.post("/pipelines", response_model=None)
async def create_pipeline(req: CreatePipelineRequest, session: AsyncSession = Depends(get_db_session)):
    svc = CDCIngestionService(session)
    pipeline = await svc.create_pipeline(
        tenant_id=tenant_id_var.get(""), pipeline_name=req.pipeline_name,
        pipeline_code=req.pipeline_code, source_schema=req.source_schema,
        source_table=req.source_table, handler_type=req.handler_type,
        handler_config=req.handler_config, topic_name=req.topic_name,
        filter_condition=req.filter_condition, transform_config=req.transform_config,
        batch_size=req.batch_size, max_retries=req.max_retries,
        description=req.description,
    )
    return Result.ok(
        data={"id": pipeline.id, "pipeline_code": pipeline.pipeline_code,
              "source": f"{pipeline.source_schema}.{pipeline.source_table}",
              "topic_name": pipeline.topic_name, "is_active": pipeline.is_active},
        trace_id=trace_id_var.get(""),
    )


@router.get("/pipelines", response_model=None)
async def list_pipelines(
    source_schema: str = Query(default=""),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    svc = CDCIngestionService(session)
    pipelines, total = await svc.list_pipelines(
        tenant_id=tenant_id_var.get(""), source_schema=source_schema,
        is_active=is_active, page=page, page_size=page_size,
    )
    items = [
        {"id": p.id, "pipeline_name": p.pipeline_name, "pipeline_code": p.pipeline_code,
         "source": f"{p.source_schema}.{p.source_table}", "handler_type": p.handler_type,
         "topic_name": p.topic_name, "is_active": p.is_active, "batch_size": p.batch_size}
        for p in pipelines
    ]
    return Result.paginate(items=items, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/init-defaults", response_model=None)
async def init_default_pipelines(session: AsyncSession = Depends(get_db_session)):
    svc = CDCIngestionService(session)
    pipelines = await svc.init_default_pipelines(tenant_id_var.get(""))
    return Result.ok(
        data={"initialized_count": len(pipelines)},
        trace_id=trace_id_var.get(""),
    )
