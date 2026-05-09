from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.sys.domain.param_models import SysParamService
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import NotFoundException, Result

router = APIRouter(prefix="/sys/v1/params", tags=["SYS-Param"])


class ParamSetRequest(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)
    param_key: str = Field(..., min_length=1, max_length=200)
    param_value: str = Field(default="")
    value_type: str = Field(default="string")
    description: str = Field(default="")
    is_encrypted: bool = Field(default=False)
    sort_order: int = Field(default=0)


class ParamInitRequest(BaseModel):
    pass


@router.post("", response_model=None)
async def set_param(req: ParamSetRequest, session: AsyncSession = Depends(get_db_session)):
    svc = SysParamService(session)
    param = await svc.set_param(
        tenant_id=tenant_id_var.get(""), category=req.category, param_key=req.param_key,
        param_value=req.param_value, value_type=req.value_type,
        description=req.description, is_encrypted=req.is_encrypted,
        sort_order=req.sort_order,
    )
    return Result.ok(
        data={"id": param.id, "category": param.category, "param_key": param.param_key,
              "param_value": "***" if param.is_encrypted else param.param_value,
              "value_type": param.value_type},
        trace_id=trace_id_var.get(""),
    )


@router.get("", response_model=None)
async def list_params(category: str | None = Query(default=None),
                      session: AsyncSession = Depends(get_db_session)):
    svc = SysParamService(session)
    params = await svc.list_by_category(tenant_id=tenant_id_var.get(""), category=category)
    return Result.ok(
        data=[{"id": p.id, "category": p.category, "param_key": p.param_key,
               "param_value": "***" if p.is_encrypted else p.param_value,
               "value_type": p.value_type, "description": p.description,
               "is_system": p.is_system, "sort_order": p.sort_order} for p in params],
        trace_id=trace_id_var.get(""),
    )


@router.get("/{category}/{param_key}", response_model=None)
async def get_param(category: str, param_key: str,
                    session: AsyncSession = Depends(get_db_session)):
    svc = SysParamService(session)
    param = await svc.get_param_or_raise(tenant_id=tenant_id_var.get(""), category=category, param_key=param_key)
    return Result.ok(
        data={"id": param.id, "category": param.category, "param_key": param.param_key,
              "param_value": "***" if param.is_encrypted else param.param_value,
              "value_type": param.value_type, "description": param.description,
              "is_system": param.is_system},
        trace_id=trace_id_var.get(""),
    )


@router.delete("/{category}/{param_key}", response_model=None)
async def delete_param(category: str, param_key: str,
                       session: AsyncSession = Depends(get_db_session)):
    svc = SysParamService(session)
    await svc.delete_param(tenant_id=tenant_id_var.get(""), category=category, param_key=param_key)
    return Result.ok(data=None, trace_id=trace_id_var.get(""))


@router.post("/init-defaults", response_model=None)
async def init_defaults(session: AsyncSession = Depends(get_db_session)):
    svc = SysParamService(session)
    await svc.init_defaults(tenant_id=tenant_id_var.get(""))
    return Result.ok(data={"message": "Default params initialized"}, trace_id=trace_id_var.get(""))
