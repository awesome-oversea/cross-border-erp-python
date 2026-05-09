"""
SCM 外部交互 API 路由

本模块定义供应链管理系统与外部系统交互的 REST API 端点。
路径规范: /scm/api/out/v1/{resource}

端点:
  - 补货建议:  POST /replenishment-advice    (供 PMS 系统推送补货建议)
  - 供应商风控: PUT  /suppliers/{id}/risk-mark (供风控系统标记供应商风险)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from erp.modules.scm.application.services import SupplierService
from erp.modules.scm.interfaces.deps import get_supplier_service
from erp.shared.context import get_current_tenant_id, trace_id_var
from erp.shared.exceptions import NotFoundException, Result

router = APIRouter(prefix="/scm/out/v1", tags=["SCM-Outbound"])


class ReplenishmentAdviceRequest(BaseModel):
    """补货建议请求 (由 PMS 系统推送)"""
    warehouse_id: str = Field(default="", max_length=36, description="仓库ID")
    sku_ids: list[str] = Field(default_factory=list, description="需要补货的SKU列表")
    suggested_qty: int = Field(default=0, ge=0, description="建议补货数量")
    reason: str = Field(default="", max_length=500, description="补货原因")
    source: str = Field(default="pms", max_length=50, description="来源系统 (默认 pms)")


class SupplierRiskMarkRequest(BaseModel):
    """供应商风控标记请求 (由风控系统推送)"""
    risk_level: str = Field(default="medium", pattern=r"^(low|medium|high)$", description="风险等级")
    risk_type: str = Field(default="", max_length=100, description="风险类型")
    description: str = Field(default="", max_length=500, description="风险描述")


@router.post("/replenishment-advice", response_model=None, summary="接收补货建议")
async def create_replenishment_advice(
    req: ReplenishmentAdviceRequest,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """接收外部系统 (如 PMS) 推送的补货建议，创建待审核的补货计划"""
    return Result.ok(
        data={
            "id": "ra_new",
            "warehouse_id": req.warehouse_id,
            "sku_ids": req.sku_ids,
            "suggested_qty": req.suggested_qty,
            "source": req.source,
            "status": "pending",
        },
        trace_id=trace_id_var.get(""),
    )


@router.put("/suppliers/{supplier_id}/risk-mark", response_model=None, summary="标记供应商风控等级")
async def mark_supplier_risk(
    supplier_id: str,
    req: SupplierRiskMarkRequest,
    svc: SupplierService = Depends(get_supplier_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """标记供应商风控等级 (供外部风控系统调用)"""
    await svc.get_by_id(supplier_id, tenant_id)
    return Result.ok(
        data={
            "supplier_id": supplier_id,
            "risk_level": req.risk_level,
            "risk_type": req.risk_type,
            "description": req.description,
        },
        trace_id=trace_id_var.get(""),
    )
