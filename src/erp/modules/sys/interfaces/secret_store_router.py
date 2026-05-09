from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.sys.domain.secret_store_models import SecretStoreService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import Result

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/sys/v1/secrets", tags=["SYS-SecretStore"])


class StoreSecretRequest(BaseModel):
    owner_type: str = Field(..., min_length=1, max_length=50)
    owner_id: str = Field(..., min_length=1, max_length=36)
    secret_type: str = Field(..., min_length=1, max_length=30)
    secret_name: str = Field(..., min_length=1, max_length=100)
    plaintext: str = Field(..., min_length=1)


class UpdateSecretRequest(BaseModel):
    plaintext: str = Field(..., min_length=1)


@router.post("", response_model=None)
async def store_secret(req: StoreSecretRequest, session: AsyncSession = Depends(get_db_session)):
    svc = SecretStoreService(session)
    secret = await svc.store_secret(
        tenant_id=tenant_id_var.get(""), owner_type=req.owner_type,
        owner_id=req.owner_id, secret_type=req.secret_type,
        secret_name=req.secret_name, plaintext=req.plaintext,
    )
    return Result.ok(
        data={"id": secret.id, "owner_type": secret.owner_type,
              "owner_id": secret.owner_id, "secret_name": secret.secret_name},
        trace_id=trace_id_var.get(""),
    )


@router.get("", response_model=None)
async def list_secrets(
    owner_type: str = Query(default=""),
    owner_id: str = Query(default=""),
    secret_type: str = Query(default=""),
    session: AsyncSession = Depends(get_db_session),
):
    svc = SecretStoreService(session)
    data = await svc.list_secrets(
        tenant_id_var.get(""), owner_type=owner_type,
        owner_id=owner_id, secret_type=secret_type,
    )
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/{secret_id}", response_model=None)
async def get_masked_secret(secret_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = SecretStoreService(session)
    data = await svc.get_masked_secret(secret_id, tenant_id_var.get(""))
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.put("/{secret_id}", response_model=None)
async def update_secret(secret_id: str, req: UpdateSecretRequest,
                         session: AsyncSession = Depends(get_db_session)):
    svc = SecretStoreService(session)
    secret = await svc.update_secret(secret_id, tenant_id_var.get(""), plaintext=req.plaintext)
    return Result.ok(
        data={"id": secret.id, "key_version": secret.key_version},
        trace_id=trace_id_var.get(""),
    )


@router.delete("/{secret_id}", response_model=None)
async def deactivate_secret(secret_id: str, session: AsyncSession = Depends(get_db_session)):
    svc = SecretStoreService(session)
    await svc.deactivate_secret(secret_id, tenant_id_var.get(""))
    return Result.ok(data=None, trace_id=trace_id_var.get(""))
