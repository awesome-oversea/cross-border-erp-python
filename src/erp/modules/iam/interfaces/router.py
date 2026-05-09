from fastapi import APIRouter, Depends

from erp.modules.iam.application.services import IAMQueryService
from erp.modules.iam.interfaces.audit_router import router as audit_router
from erp.modules.iam.interfaces.auth_router import router as auth_router
from erp.modules.iam.interfaces.deps import get_iam_query_service
from erp.modules.iam.interfaces.org_router import router as org_router
from erp.modules.iam.interfaces.perm_ext_router import router as perm_ext_router
from erp.modules.iam.interfaces.position_router import router as position_router
from erp.modules.iam.interfaces.role_router import router as role_router
from erp.modules.iam.interfaces.tenant_router import router as tenant_router
from erp.modules.iam.interfaces.user_router import router as user_router
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import Result

iam_router = APIRouter()

iam_router.include_router(auth_router)
iam_router.include_router(tenant_router)
iam_router.include_router(org_router)
iam_router.include_router(user_router)
iam_router.include_router(role_router)
iam_router.include_router(audit_router)
iam_router.include_router(position_router)
iam_router.include_router(perm_ext_router)


@iam_router.get("/iam/v1/statistics", response_model=None, tags=["IAM-Statistics"], summary="IAM运营统计概览")
async def get_iam_statistics(
    svc: IAMQueryService = Depends(get_iam_query_service),
):
    """获取IAM运营统计概览: 租户/用户/角色/权限/组织等核心指标"""
    result = await svc.get_statistics(tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
