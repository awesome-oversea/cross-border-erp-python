"""
PDM 外部交互路由 - 产品域与外部系统（如PMS）交互的API端点

路径规范：/{service}/api/{direction}/v1/{resource}
direction: out（对外输出）/ in（接收外部输入）
所有端点通过依赖注入获取服务实例。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from erp.modules.pdm.application.services import ProductProjectService, SPUService
from erp.modules.pdm.interfaces.deps import get_product_project_service, get_spu_service
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import NotFoundException, Result

router = APIRouter(prefix="/pdm/out/v1", tags=["PDM-Outbound - 产品域外部交互"])


class SuggestionCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    category_id: str = ""
    market: str = ""
    platform: str = ""
    data_json: str = "{}"
    source: str = "pms"


class ProductUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    attributes_json: str | None = None


class AIRecommendationReceiveRequest(BaseModel):
    recommendation_id: str = Field(..., min_length=1)
    recommendation_type: str = "product_selection"
    source: str = "pms"
    confidence: float = 0.0
    data: dict = Field(default_factory=dict)
    reason: str = ""


class AIRecommendationExecuteRequest(BaseModel):
    recommendation_id: str = Field(..., min_length=1)
    action: str = "accept"
    remark: str = ""


class AIRecommendationFeedbackRequest(BaseModel):
    recommendation_id: str = Field(..., min_length=1)
    feedback_type: str = "positive"
    actual_result: str = ""
    remark: str = ""


@router.post("/suggestions", response_model=None)
async def create_suggestion(req: SuggestionCreateRequest,
                            svc: ProductProjectService = Depends(get_product_project_service)):
    project = await svc.create(
        tenant_id_var.get(""), name=f"SUG-{req.title}",
        code=f"SUG-{req.source}-{req.category_id}",
        category_id=req.category_id or None,
        target_market=req.market, target_platform=req.platform,
    )
    return Result.ok(data={"id": project.id, "title": req.title, "category_id": req.category_id,
                           "market": req.market, "source": req.source, "status": "pending"},
                     trace_id=trace_id_var.get(""))


@router.put("/products/{product_id}", response_model=None)
async def update_product_for_pms(product_id: str, req: ProductUpdateRequest,
                                  svc: SPUService = Depends(get_spu_service)):
    tenant_id = tenant_id_var.get("")
    if req.status is not None:
        await svc.update_status(product_id, tenant_id, status=req.status)
    else:
        spu = await svc.get_by_id(product_id, tenant_id)
        if spu is not None:
            if req.name is not None:
                spu.name = req.name
            if req.description is not None:
                spu.description = req.description
            if req.attributes_json is not None:
                spu.attributes_json = req.attributes_json
            await svc.update(spu)
    return Result.ok(data={"id": product_id, "updated": True}, trace_id=trace_id_var.get(""))


@router.post("/ai-recommendations/receive", response_model=None)
async def receive_ai_recommendation(req: AIRecommendationReceiveRequest,
                                     svc: ProductProjectService = Depends(get_product_project_service)):
    project = await svc.create(
        tenant_id_var.get(""), name=f"AI-{req.recommendation_type}-{req.recommendation_id}",
        code=f"AI-{req.recommendation_id}", category_id=None, priority="high",
        owner_id="", target_market=req.data.get("target_market", ""),
        target_platform=req.data.get("target_platform", ""),
        recommendation_id=req.recommendation_id,
    )
    return Result.ok(data={"id": project.id, "recommendation_id": req.recommendation_id,
                           "recommendation_type": req.recommendation_type, "confidence": req.confidence,
                           "status": "received"}, trace_id=trace_id_var.get(""))


@router.post("/ai-recommendations/execute", response_model=None)
async def execute_ai_recommendation(req: AIRecommendationExecuteRequest,
                                     svc: ProductProjectService = Depends(get_product_project_service)):
    new_stage = "accepted" if req.action == "accept" else "rejected"
    project = await svc.get_by_recommendation_id(req.recommendation_id, tenant_id_var.get(""))
    if not project:
        raise NotFoundException(message=f"Recommendation project '{req.recommendation_id}' not found")
    project = await svc.update_stage(str(project.id), tenant_id_var.get(""), stage=new_stage)
    return Result.ok(data={"id": project.id, "recommendation_id": req.recommendation_id,
                           "action": req.action, "stage": project.stage}, trace_id=trace_id_var.get(""))


@router.post("/ai-recommendations/feedback", response_model=None)
async def feedback_ai_recommendation(req: AIRecommendationFeedbackRequest):
    return Result.ok(data={"recommendation_id": req.recommendation_id, "feedback_type": req.feedback_type,
                           "actual_result": req.actual_result, "status": "feedback_recorded"}, trace_id=trace_id_var.get(""))
