from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.sys.domain.connector_models import (
    ConnectorService,
    ConnectorSyncService,
)
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import NotFoundException, Result

router = APIRouter(prefix="/sys/v1/connectors", tags=["SYS-Connector"])


class ConnectorCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=100)
    connector_type: str = Field(..., min_length=1)
    platform: str = Field(default="")
    description: str = Field(default="")
    config_json: str = Field(default="{}")
    credentials_json: str = Field(default="{}")
    endpoint_url: str = Field(default="")
    sync_interval_seconds: int = Field(default=300)
    max_retries: int = Field(default=3)
    is_auto_sync: bool = Field(default=False)


class ConnectorUpdateConfigRequest(BaseModel):
    config_json: str = Field(default="{}")
    credentials_json: str = Field(default="{}")


class ConnectorUpdateStatusRequest(BaseModel):
    status: str = Field(..., min_length=1)


class SyncLogCreateRequest(BaseModel):
    connector_id: str = Field(..., min_length=1)
    sync_type: str = Field(default="full")


@router.post("", response_model=None)
async def create_connector(req: ConnectorCreateRequest,
                           session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorService(session)
    connector = await svc.create(
        tenant_id=tenant_id_var.get(""), name=req.name, code=req.code,
        connector_type=req.connector_type, platform=req.platform,
        description=req.description, config_json=req.config_json,
        credentials_json=req.credentials_json, endpoint_url=req.endpoint_url,
        sync_interval_seconds=req.sync_interval_seconds, max_retries=req.max_retries,
        is_auto_sync=req.is_auto_sync,
    )
    return Result.ok(
        data={"id": connector.id, "name": connector.name, "code": connector.code,
              "connector_type": connector.connector_type, "status": connector.status},
        trace_id=trace_id_var.get(""),
    )


@router.get("", response_model=None)
async def list_connectors(connector_type: str | None = Query(default=None),
                          status: str | None = Query(default=None),
                          session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorService(session)
    connectors = await svc.list_by_tenant(
        tenant_id=tenant_id_var.get(""), connector_type=connector_type, status=status,
    )
    return Result.ok(
        data=[{"id": c.id, "name": c.name, "code": c.code,
               "connector_type": c.connector_type, "platform": c.platform,
               "status": c.status, "last_sync_at": str(c.last_sync_at) if c.last_sync_at else None,
               "is_auto_sync": c.is_auto_sync} for c in connectors],
        trace_id=trace_id_var.get(""),
    )


@router.get("/{connector_id}", response_model=None)
async def get_connector(connector_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorService(session)
    connector = await svc.get_or_raise(connector_id)
    return Result.ok(
        data={"id": connector.id, "name": connector.name, "code": connector.code,
              "connector_type": connector.connector_type, "platform": connector.platform,
              "version": connector.version, "description": connector.description,
              "config_json": connector.config_json, "endpoint_url": connector.endpoint_url,
              "status": connector.status, "last_sync_at": str(connector.last_sync_at) if connector.last_sync_at else None,
              "last_sync_status": connector.last_sync_status,
              "sync_interval_seconds": connector.sync_interval_seconds,
              "is_auto_sync": connector.is_auto_sync},
        trace_id=trace_id_var.get(""),
    )


@router.put("/{connector_id}/status", response_model=None)
async def update_connector_status(connector_id: str, req: ConnectorUpdateStatusRequest,
                                   session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorService(session)
    connector = await svc.update_status(connector_id, req.status)
    return Result.ok(
        data={"id": connector.id, "status": connector.status},
        trace_id=trace_id_var.get(""),
    )


@router.put("/{connector_id}/config", response_model=None)
async def update_connector_config(connector_id: str, req: ConnectorUpdateConfigRequest,
                                   session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorService(session)
    connector = await svc.update_config(
        connector_id, config_json=req.config_json, credentials_json=req.credentials_json,
    )
    return Result.ok(
        data={"id": connector.id, "status": connector.status},
        trace_id=trace_id_var.get(""),
    )


@router.delete("/{connector_id}", response_model=None)
async def delete_connector(connector_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorService(session)
    await svc.delete(connector_id)
    return Result.ok(data=None, trace_id=trace_id_var.get(""))


@router.post("/sync-logs", response_model=None)
async def create_sync_log(req: SyncLogCreateRequest,
                           session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorSyncService(session)
    log = await svc.create_log(
        tenant_id=tenant_id_var.get(""), connector_id=req.connector_id,
        sync_type=req.sync_type,
    )
    return Result.ok(
        data={"id": log.id, "connector_id": log.connector_id, "status": log.status},
        trace_id=trace_id_var.get(""),
    )


@router.get("/sync-logs", response_model=None)
async def list_sync_logs(connector_id: str | None = Query(default=None),
                          limit: int = Query(default=50, ge=1, le=200),
                          session: AsyncSession = Depends(get_db_session)):
    svc = ConnectorSyncService(session)
    logs = await svc.list_logs(
        tenant_id=tenant_id_var.get(""), connector_id=connector_id, limit=limit,
    )
    return Result.ok(
        data=[{"id": log.id, "connector_id": log.connector_id, "sync_type": log.sync_type,
               "status": log.status, "records_total": log.records_total,
               "records_success": log.records_success, "records_failed": log.records_failed,
               "started_at": str(log.started_at) if log.started_at else None,
               "finished_at": str(log.finished_at) if log.finished_at else None} for log in logs],
        trace_id=trace_id_var.get(""),
    )
