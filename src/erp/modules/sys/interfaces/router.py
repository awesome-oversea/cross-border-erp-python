from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.sys.application.services import (
    DraftDocumentService,
    InsightCardService,
    RecommendationService,
    RiskAlertService,
    SYSQueryService,
)
from erp.modules.sys.interfaces.deps import (
    get_draft_service,
    get_insight_card_service,
    get_recommendation_service,
    get_risk_alert_service,
)
from erp.shared.context import actor_id_var, tenant_id_var, trace_id_var
from erp.shared.db.session import get_db_session
from erp.shared.exceptions import NotFoundException, Result
from erp.shared.workflow import ApprovalActionRequest, ApprovalNodeConfig, ApprovalService, ApprovalSubmitRequest

router = APIRouter(prefix="/sys/v1", tags=["SYS - 系统域"])


class DefineFlowRequest(BaseModel):
    flow_code: str = Field(..., min_length=1)
    flow_name: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    target_type: str = Field(..., min_length=1)
    description: str = Field(default="")
    nodes: list[ApprovalNodeConfig] = Field(default_factory=list)


@router.post("/approval-flows", response_model=None)
async def define_approval_flow(
    req: DefineFlowRequest,
    tid: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    svc = ApprovalService(session)
    flow = await svc.define_flow(
        tenant_id=tid or tenant_id_var.get(""),
        flow_code=req.flow_code,
        flow_name=req.flow_name,
        domain=req.domain,
        target_type=req.target_type,
        nodes=req.nodes,
        description=req.description,
    )
    return Result.ok(data={"id": flow.id, "flow_code": flow.flow_code}, trace_id=trace_id_var.get(""))


@router.post("/approval-instances", response_model=None)
async def submit_approval(
    req: ApprovalSubmitRequest,
    tid: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    svc = ApprovalService(session)
    instance = await svc.submit(
        tenant_id=tid or tenant_id_var.get(""),
        req=req,
        submitted_by=actor_id_var.get(""),
    )
    return Result.ok(
        data={"id": instance.id, "status": instance.status.value, "flow_code": instance.flow_code},
        trace_id=trace_id_var.get(""),
    )


@router.post("/approval-tasks/{task_id}/action", response_model=None)
async def process_approval_task(
    task_id: str,
    req: ApprovalActionRequest,
    tid: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    svc = ApprovalService(session)
    instance = await svc.approve(
        task_id=task_id,
        tenant_id=tid or tenant_id_var.get(""),
        req=req,
        actor_id=actor_id_var.get(""),
    )
    return Result.ok(
        data={"id": instance.id, "status": instance.status.value},
        trace_id=trace_id_var.get(""),
    )


@router.get("/approval-tasks/pending", response_model=None)
async def list_pending_tasks(
    assignee_id: str = Query(default=""),
    tid: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    svc = ApprovalService(session)
    tasks = await svc.get_pending_tasks(
        tenant_id=tid or tenant_id_var.get(""),
        assignee_id=assignee_id or actor_id_var.get(""),
    )
    return Result.ok(data=[t.model_dump() for t in tasks], trace_id=trace_id_var.get(""))


@router.get("/approval-instances/{instance_id}", response_model=None)
async def get_approval_instance(
    instance_id: str,
    tid: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    svc = ApprovalService(session)
    instance = await svc.get_instance_or_raise(instance_id, tid or tenant_id_var.get(""))
    return Result.ok(data=instance.model_dump(), trace_id=trace_id_var.get(""))


class ParameterUpdateRequest(BaseModel):
    value: str = Field(..., min_length=1)
    description: str = ""


class ConnectorConfigCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    connector_type: str = Field(..., min_length=1)
    config_json: str = "{}"
    is_active: bool = True


class ConnectorConfigUpdateRequest(BaseModel):
    name: str | None = None
    config_json: str | None = None
    is_active: bool | None = None


class LogisticsRuleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    rule_type: str = "channel_mapping"
    priority: int = 0
    conditions_json: str = "{}"
    actions_json: str = "{}"
    is_active: bool = True


class AiFeatureToggleUpdateRequest(BaseModel):
    is_enabled: bool
    config_json: str = "{}"


class PmsSuggestionCreateRequest(BaseModel):
    suggestion_type: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = ""
    confidence: float = 0.0
    data_json: str = "{}"
    priority: str = "normal"
    source_suggestion_id: str = ""


class PmsSuggestionExecuteRequest(BaseModel):
    executed_by: str = ""
    execution_note: str = ""


class PmsSuggestionRejectRequest(BaseModel):
    rejected_by: str = ""
    reject_reason: str = ""


class PmsFeedbackRequest(BaseModel):
    suggestion_id: str = Field(..., min_length=1)
    execution_result: str = Field(..., min_length=1)
    actual_outcome: str = ""
    metrics_json: str = "{}"
    feedback_by: str = ""


class PmsDataQueryRequest(BaseModel):
    query_type: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    filters_json: str = "{}"
    fields: list[str] = Field(default_factory=list)


class PmsEventSubscribeRequest(BaseModel):
    event_type: str = Field(..., min_length=1)
    callback_url: str = Field(..., min_length=1)
    domain: str = ""
    filters_json: str = "{}"


class PmsReplenishmentAdviceRequest(BaseModel):
    sku_id: str = Field(..., min_length=1)
    suggested_qty: int = Field(..., ge=1)
    reason: str = ""
    confidence: float = 0.0
    warehouse_id: str = ""
    days_of_supply: int = 30


@router.get("/parameters", response_model=None)
async def list_parameters(group: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data=[], trace_id=trace_id_var.get(""))


@router.put("/parameters/{key}", response_model=None)
async def update_parameter(key: str, req: ParameterUpdateRequest, session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"key": key, "value": req.value, "updated": True}, trace_id=trace_id_var.get(""))


@router.get("/connector-configs", response_model=None)
async def list_connector_configs(connector_type: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data=[], trace_id=trace_id_var.get(""))


@router.post("/connector-configs", response_model=None)
async def create_connector_config(req: ConnectorConfigCreateRequest, session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"name": req.name, "connector_type": req.connector_type,
                           "is_active": req.is_active, "status": "created"}, trace_id=trace_id_var.get(""))


@router.put("/connector-configs/{config_id}", response_model=None)
async def update_connector_config(config_id: str, req: ConnectorConfigUpdateRequest, session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"config_id": config_id, "updated": True}, trace_id=trace_id_var.get(""))


@router.get("/logistics-rules", response_model=None)
async def list_logistics_rules(rule_type: str = Query(default=""), session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data=[], trace_id=trace_id_var.get(""))


@router.post("/logistics-rules", response_model=None)
async def create_logistics_rule(req: LogisticsRuleCreateRequest, session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"name": req.name, "rule_type": req.rule_type,
                           "priority": req.priority, "is_active": req.is_active,
                           "status": "created"}, trace_id=trace_id_var.get(""))


@router.get("/ai-feature-toggles", response_model=None)
async def list_ai_feature_toggles(session: AsyncSession = Depends(get_db_session)):
    toggles = [
        {"id": "ai_selection", "name": "AI选品推荐", "is_enabled": True, "domain": "pdm"},
        {"id": "ai_replenishment", "name": "AI补货建议", "is_enabled": True, "domain": "scm"},
        {"id": "ai_ad_optimization", "name": "AI广告优化", "is_enabled": False, "domain": "ads"},
        {"id": "ai_risk_control", "name": "AI风控检测", "is_enabled": True, "domain": "oms"},
        {"id": "ai_sentiment", "name": "AI情感分析", "is_enabled": False, "domain": "crm"},
        {"id": "ai_cost_allocation", "name": "AI成本归集", "is_enabled": True, "domain": "fms"},
        {"id": "ai_inventory_predict", "name": "AI库存预测", "is_enabled": False, "domain": "wms"},
    ]
    return Result.ok(data=toggles, trace_id=trace_id_var.get(""))


@router.put("/ai-feature-toggles/{toggle_id}", response_model=None)
async def update_ai_feature_toggle(toggle_id: str, req: AiFeatureToggleUpdateRequest, session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"id": toggle_id, "is_enabled": req.is_enabled, "updated": True}, trace_id=trace_id_var.get(""))


@router.post("/pms/suggestions", response_model=None)
async def receive_pms_suggestion(req: PmsSuggestionCreateRequest, session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"id": "sug_new", "suggestion_type": req.suggestion_type, "domain": req.domain,
                           "title": req.title, "confidence": req.confidence, "priority": req.priority,
                           "status": "pending", "source_suggestion_id": req.source_suggestion_id},
                     trace_id=trace_id_var.get(""))


@router.get("/pms/suggestions", response_model=None)
async def list_pms_suggestions(suggestion_type: str = Query(default=""), domain: str = Query(default=""),
                                status: str = Query(default=""), page: int = Query(default=1, ge=1),
                                page_size: int = Query(default=20, ge=1, le=100),
                                session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data=[], trace_id=trace_id_var.get(""))


@router.put("/pms/suggestions/{suggestion_id}/execute", response_model=None)
async def execute_pms_suggestion(suggestion_id: str, req: PmsSuggestionExecuteRequest,
                                  session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"id": suggestion_id, "status": "executed", "executed_by": req.executed_by,
                           "execution_note": req.execution_note}, trace_id=trace_id_var.get(""))


@router.put("/pms/suggestions/{suggestion_id}/reject", response_model=None)
async def reject_pms_suggestion(suggestion_id: str, req: PmsSuggestionRejectRequest,
                                 session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"id": suggestion_id, "status": "rejected", "rejected_by": req.rejected_by,
                           "reject_reason": req.reject_reason}, trace_id=trace_id_var.get(""))


@router.post("/pms/feedback", response_model=None)
async def submit_pms_feedback(req: PmsFeedbackRequest, session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"suggestion_id": req.suggestion_id, "execution_result": req.execution_result,
                           "actual_outcome": req.actual_outcome, "status": "feedback_submitted"},
                     trace_id=trace_id_var.get(""))


@router.post("/pms/data-query", response_model=None)
async def pms_data_query(req: PmsDataQueryRequest, session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"query_type": req.query_type, "domain": req.domain, "results": []},
                     trace_id=trace_id_var.get(""))


@router.post("/pms/events/subscribe", response_model=None)
async def subscribe_pms_event(req: PmsEventSubscribeRequest, session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"event_type": req.event_type, "callback_url": req.callback_url,
                           "domain": req.domain, "status": "subscribed"}, trace_id=trace_id_var.get(""))


@router.get("/pms/selection-recommendations", response_model=None)
async def get_pms_selection_recommendations(category_id: str = Query(default=""), market: str = Query(default=""),
                                             limit: int = Query(default=20, ge=1, le=100),
                                             session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data=[], trace_id=trace_id_var.get(""))


@router.post("/pms/replenishment-advice", response_model=None)
async def receive_pms_replenishment_advice(req: PmsReplenishmentAdviceRequest,
                                            session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data={"sku_id": req.sku_id, "suggested_qty": req.suggested_qty,
                           "warehouse_id": req.warehouse_id, "days_of_supply": req.days_of_supply,
                           "confidence": req.confidence, "reason": req.reason, "status": "received"},
                     trace_id=trace_id_var.get(""))


@router.get("/pms/risk-alerts", response_model=None)
async def get_pms_risk_alerts(domain: str = Query(default=""), severity: str = Query(default=""),
                               limit: int = Query(default=20, ge=1, le=100),
                               session: AsyncSession = Depends(get_db_session)):
    return Result.ok(data=[], trace_id=trace_id_var.get(""))


@router.get("/statistics", response_model=None, tags=["SYS-Statistics"], summary="SYS运营统计概览")
async def get_sys_statistics(session: AsyncSession = Depends(get_db_session)):
    """获取SYS运营统计概览: 连接器/Webhook/规则/参数/字典/推荐/风险等核心指标"""
    svc = SYSQueryService(session=session)
    result = await svc.get_statistics(tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))
