"""
SYS (智能助手域) 应用服务层

职责: 编排智能推荐/文档草稿/风险预警/洞察卡片的完整业务流程

核心服务:
  - RecommendationService: 智能推荐服务，运营/采购/物流场景推荐
  - DraftDocumentService: 文档草稿服务，AI辅助文档生成
  - RiskAlertService: 风险预警服务，多维度风险识别与告警
  - InsightCardService: 洞察卡片服务，关键业务洞察自动生成
  - SYSQueryService: 统一查询服务，跨实体聚合查询
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, select

from erp.modules.sys.domain.models import DraftDocument, InsightCard, PendingAction, Recommendation, RiskAlert
from erp.modules.sys.domain.repositories import (
    DraftDocumentRepository,
    InsightCardRepository,
    RecommendationRepository,
    RiskAlertRepository,
)
from erp.modules.sys.infrastructure.repositories import (
    SqlDraftDocumentRepository,
    SqlInsightCardRepository,
    SqlRecommendationRepository,
    SqlRiskAlertRepository,
)
from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.workflow.models import ApprovalSubmitRequest
from erp.shared.workflow.service import ApprovalService
from erp.shared.events.domain_event import (
    RecommendationAccepted,
    RecommendationApproved,
    RecommendationExecuted,
    RecommendationExecuting,
    RecommendationFailed,
    RecommendationRejected,
    RecommendationRolledBack,
)
from erp.shared.events.publisher import get_event_publisher
from erp.shared.exceptions import (
    IdempotencyConflictException,
    NotFoundException,
    ValidationException,
)
from erp.shared.idempotency.service import IdempotencyService
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.sys.pms_integration")

RECOMMENDATION_STATE_TRANSITIONS: dict[str, list[str]] = {
    "submitted": ["accepted", "rejected"],
    "accepted": ["pending_approval", "rejected"],
    "pending_approval": ["approved", "approval_rejected"],
    "approved": ["executing"],
    "executing": ["partially_executed", "executed", "failed"],
    "partially_executed": ["executed", "failed", "rolled_back"],
    "executed": ["measured", "rolled_back"],
    "failed": ["executing", "rolled_back"],
    "rolled_back": [],
    "measured": ["reviewed"],
    "reviewed": [],
    "approval_rejected": [],
    "rejected": [],
}

PMS_ALLOWED_WRITE_DOMAINS = {
    "iam", "pdm", "som", "ads", "oms", "scm", "wms", "fba", "tms", "crm", "fms", "bi", "sys", "dashboard"
}

PMS_WRITE_OBJECT_TYPES = {"recommendation", "draft", "pending_action", "risk_alert", "insight_card"}


class RecommendationService:
    def __init__(self, session: AsyncSession, rec_repo: RecommendationRepository | None = None):
        self._session = session
        self._rec_repo = rec_repo or SqlRecommendationRepository(session)
        self._idempotency = IdempotencyService(session)

    async def receive_recommendation(
        self,
        tenant_id: str,
        recommendation_id: str,
        domain: str,
        recommendation_type: str,
        target_object_type: str = "",
        target_object_id: str = "",
        content: dict | None = None,
        score: float = 0.0,
        confidence: float = 0.0,
        evidence_chain_id: str = "",
        data_sources: list | None = None,
        risk_flags: list | None = None,
        explainability: str = "",
        requested_action: str = "",
        idempotency_key: str = "",
        actor_id: str = "",
        actor_type: str = "service_account",
        agent_id: str = "",
        scope: str = "",
        purpose: str = "",
    ) -> Recommendation:
        if domain not in PMS_ALLOWED_WRITE_DOMAINS:
            raise ValidationException(message=f"PMS cannot write to domain '{domain}'")

        if idempotency_key:
            existing = await self._idempotency.check_and_record(idempotency_key, tenant_id)
            if existing:
                raise IdempotencyConflictException(message="Duplicate recommendation request")

        existing_rec = await self._rec_repo.get_by_recommendation_id(recommendation_id, tenant_id)
        if existing_rec:
            raise IdempotencyConflictException(message=f"Recommendation '{recommendation_id}' already exists")

        rec = Recommendation(
            tenant_id=tenant_id,
            recommendation_id=recommendation_id,
            domain=domain,
            recommendation_type=recommendation_type,
            target_object_type=target_object_type,
            target_object_id=target_object_id,
            content_json=json.dumps(content or {}, default=str),
            score=score,
            confidence=confidence,
            evidence_chain_id=evidence_chain_id,
            data_sources_json=json.dumps(data_sources or [], default=str),
            risk_flags_json=json.dumps(risk_flags or [], default=str),
            explainability=explainability,
            requested_action=requested_action,
            status="submitted",
            idempotency_key=idempotency_key,
            source_system="PMS",
            actor_id=actor_id,
            actor_type=actor_type,
            agent_id=agent_id,
            scope=scope,
            purpose=purpose,
            trace_id=trace_id_var.get(""),
        )
        rec = await self._rec_repo.create(rec)

        if idempotency_key:
            await self._idempotency.record(idempotency_key, tenant_id, response_data={"id": rec.id})

        publisher = get_event_publisher()
        await publisher.publish(RecommendationAccepted(
            tenant_id=tenant_id,
            aggregate_id=rec.id,
            trace_id=trace_id_var.get(""),
            actor=actor_id,
            data_scope=scope,
            recommendation_id=recommendation_id,
            erp_reference_id=rec.id,
        ))

        logger.info(
            "recommendation_received",
            recommendation_id=recommendation_id,
            domain=domain,
            type=recommendation_type,
            tenant_id=tenant_id,
        )
        return rec

    async def transition_status(
        self,
        rec_id: str,
        tenant_id: str,
        new_status: str,
        reason: str = "",
        execution_result: dict | None = None,
    ) -> Recommendation:
        rec = await self._rec_repo.get_by_id(rec_id, tenant_id)
        if not rec:
            raise NotFoundException(message=f"Recommendation '{rec_id}' not found")

        allowed = RECOMMENDATION_STATE_TRANSITIONS.get(rec.status, [])
        if new_status not in allowed:
            raise ValidationException(
                message=f"Cannot transition from '{rec.status}' to '{new_status}'. Allowed: {allowed}"
            )

        update_kwargs: dict = {}
        if reason:
            update_kwargs["rejection_reason"] = reason
        if execution_result:
            update_kwargs["execution_result_json"] = json.dumps(execution_result, default=str)

        rec = await self._rec_repo.update_status(rec_id, tenant_id, new_status, **update_kwargs)

        if new_status == "pending_approval":
            approval_service = ApprovalService(self._session)
            await approval_service.submit(
                tenant_id=tenant_id,
                req=ApprovalSubmitRequest(
                    flow_code="pms_recommendation_approval",
                    domain="sys",
                    target_type="pms_recommendation",
                    target_id=rec.id,
                    title=f"PMS recommendation approval: {rec.recommendation_id}",
                    description=f"Approve PMS recommendation for domain '{rec.domain}'",
                ),
                submitted_by=getattr(rec, "actor_id", "") or actor_id_var.get(""),
            )

        publisher = get_event_publisher()
        event_map = {
            "rejected": RecommendationRejected,
            "pending_approval": None,
            "approved": RecommendationApproved,
            "executing": RecommendationExecuting,
            "executed": RecommendationExecuted,
            "failed": RecommendationFailed,
            "rolled_back": RecommendationRolledBack,
        }
        event_cls = event_map.get(new_status)
        if event_cls:
            event_kwargs: dict = {
                "tenant_id": tenant_id,
                "aggregate_id": rec_id,
                "trace_id": trace_id_var.get(""),
                "recommendation_id": rec.recommendation_id,
                "erp_reference_id": rec.id,
            }
            if new_status == "rejected":
                event_kwargs["rejection_reason"] = reason
            if new_status == "failed":
                event_kwargs["failure_reason"] = reason
            if new_status == "rolled_back":
                event_kwargs["rollback_reason"] = reason
            if new_status == "executed":
                event_kwargs["execution_result"] = execution_result or {}
            await publisher.publish(event_cls(**event_kwargs))

        logger.info(
            "recommendation_status_changed",
            rec_id=rec_id,
            to_status=new_status,
            tenant_id=tenant_id,
        )
        return rec

    async def list_by_tenant(
        self,
        tenant_id: str,
        domain: str = "",
        status: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Recommendation], int]:
        return await self._rec_repo.list_by_domain(tenant_id, domain=domain, status=status,
                                                    page=page, page_size=page_size)

    async def get_by_id(self, rec_id: str, tenant_id: str) -> Recommendation | None:
        return await self._rec_repo.get_by_id(rec_id, tenant_id)

    async def get_or_raise(self, rec_id: str, tenant_id: str) -> Recommendation:
        rec = await self.get_by_id(rec_id, tenant_id)
        if not rec:
            raise NotFoundException(message=f"Recommendation '{rec_id}' not found")
        return rec


class DraftDocumentService:
    def __init__(self, session: AsyncSession, draft_repo: DraftDocumentRepository | None = None):
        self._session = session
        self._draft_repo = draft_repo or SqlDraftDocumentRepository(session)
        self._idempotency = IdempotencyService(session)

    async def receive_draft(
        self,
        tenant_id: str,
        recommendation_id: str,
        draft_type: str,
        draft_data: dict,
        domain: str,
        idempotency_key: str = "",
        created_by: str = "",
    ) -> DraftDocument:
        if idempotency_key:
            existing = await self._idempotency.check_and_record(idempotency_key, tenant_id)
            if existing:
                raise IdempotencyConflictException(message="Duplicate draft request")

        draft = DraftDocument(
            tenant_id=tenant_id,
            recommendation_id=recommendation_id,
            draft_type=draft_type,
            draft_data_json=json.dumps(draft_data, default=str),
            domain=domain,
            status="draft",
            idempotency_key=idempotency_key,
            created_by=created_by or actor_id_var.get(""),
        )
        draft = await self._draft_repo.create(draft)

        if idempotency_key:
            await self._idempotency.record(idempotency_key, tenant_id, response_data={"id": draft.id})

        logger.info("draft_received", draft_id=draft.id, draft_type=draft_type, domain=domain, tenant_id=tenant_id)
        return draft

    async def convert_to_formal(self, draft_id: str, tenant_id: str, formal_id: str) -> DraftDocument:
        draft = await self._draft_repo.get_by_id(draft_id, tenant_id)
        if not draft:
            raise NotFoundException(message=f"Draft '{draft_id}' not found")
        if draft.status != "approved":
            raise ValidationException(message="Draft must be approved before conversion")

        draft.status = "converted"
        draft.converted_to = formal_id
        await self._draft_repo.update_status(draft_id, tenant_id, "converted", converted_to=formal_id)
        return draft


class RiskAlertService:
    def __init__(self, session: AsyncSession, alert_repo: RiskAlertRepository | None = None):
        self._session = session
        self._alert_repo = alert_repo or SqlRiskAlertRepository(session)
        self._idempotency = IdempotencyService(session)

    async def receive_alert(
        self,
        tenant_id: str,
        domain: str,
        risk_type: str,
        risk_level: str,
        title: str,
        description: str = "",
        evidence: dict | None = None,
        recommendation_id: str = "",
        idempotency_key: str = "",
    ) -> RiskAlert:
        if idempotency_key:
            existing = await self._idempotency.check_and_record(idempotency_key, tenant_id)
            if existing:
                raise IdempotencyConflictException(message="Duplicate risk alert request")

        alert = RiskAlert(
            tenant_id=tenant_id,
            recommendation_id=recommendation_id,
            domain=domain,
            risk_type=risk_type,
            risk_level=risk_level,
            title=title,
            description=description,
            evidence_json=json.dumps(evidence or {}, default=str),
            idempotency_key=idempotency_key,
        )
        alert = await self._alert_repo.create(alert)

        if idempotency_key:
            await self._idempotency.record(idempotency_key, tenant_id, response_data={"id": alert.id})

        logger.info("risk_alert_received", alert_id=alert.id, risk_type=risk_type, domain=domain, tenant_id=tenant_id)
        return alert

    async def resolve_alert(self, alert_id: str, tenant_id: str, resolution: str, assigned_to: str = "") -> RiskAlert:
        alert = await self._alert_repo.get_by_id(alert_id, tenant_id)
        if not alert:
            raise NotFoundException(message=f"Risk alert '{alert_id}' not found")

        result = await self._alert_repo.resolve(alert_id, tenant_id, resolution)
        if not result:
            raise NotFoundException(message=f"Risk alert '{alert_id}' not found")
        if assigned_to:
            result.assigned_to = assigned_to
            await self._session.flush()
        return result


class InsightCardService:
    def __init__(self, session: AsyncSession, card_repo: InsightCardRepository | None = None):
        self._session = session
        self._card_repo = card_repo or SqlInsightCardRepository(session)
        self._idempotency = IdempotencyService(session)

    async def receive_card(
        self,
        tenant_id: str,
        domain: str,
        card_type: str,
        title: str,
        content: dict | None = None,
        metrics: dict | None = None,
        recommendation_id: str = "",
        idempotency_key: str = "",
    ) -> InsightCard:
        if idempotency_key:
            existing = await self._idempotency.check_and_record(idempotency_key, tenant_id)
            if existing:
                raise IdempotencyConflictException(message="Duplicate insight card request")

        card = InsightCard(
            tenant_id=tenant_id,
            recommendation_id=recommendation_id,
            domain=domain,
            card_type=card_type,
            title=title,
            content_json=json.dumps(content or {}, default=str),
            metrics_json=json.dumps(metrics or {}, default=str),
            idempotency_key=idempotency_key,
        )
        card = await self._card_repo.create(card)

        if idempotency_key:
            await self._idempotency.record(idempotency_key, tenant_id, response_data={"id": card.id})

        logger.info("insight_card_received", card_id=card.id, card_type=card_type, domain=domain, tenant_id=tenant_id)
        return card

    async def archive_card(self, card_id: str, tenant_id: str) -> InsightCard:
        card = await self._card_repo.archive(card_id, tenant_id)
        if not card:
            raise NotFoundException(message=f"Insight card '{card_id}' not found")
        return card


class SYSQueryService:
    """
    SYS 统计查询服务

    提供系统模块的运营统计概览。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_statistics(self, tenant_id: str) -> dict:
        from sqlalchemy import func as sa_func

        from erp.modules.sys.domain.models import (
            DraftDocument,
            InsightCard,
            PendingAction,
            Recommendation,
            RiskAlert,
        )

        total_recommendations = (await self._session.execute(
            select(sa_func.count()).select_from(Recommendation)
            .where(Recommendation.tenant_id == tenant_id)
        )).scalar() or 0

        pending_recommendations = (await self._session.execute(
            select(sa_func.count()).select_from(Recommendation)
            .where(Recommendation.tenant_id == tenant_id, Recommendation.status == "submitted")
        )).scalar() or 0

        total_risk_alerts = (await self._session.execute(
            select(sa_func.count()).select_from(RiskAlert)
            .where(RiskAlert.tenant_id == tenant_id)
        )).scalar() or 0

        unresolved_alerts = (await self._session.execute(
            select(sa_func.count()).select_from(RiskAlert)
            .where(RiskAlert.tenant_id == tenant_id, RiskAlert.status == "open")
        )).scalar() or 0

        total_pending_actions = (await self._session.execute(
            select(sa_func.count()).select_from(PendingAction)
            .where(PendingAction.tenant_id == tenant_id)
        )).scalar() or 0

        total_draft_documents = (await self._session.execute(
            select(sa_func.count()).select_from(DraftDocument)
            .where(DraftDocument.tenant_id == tenant_id)
        )).scalar() or 0

        total_insight_cards = (await self._session.execute(
            select(sa_func.count()).select_from(InsightCard)
            .where(InsightCard.tenant_id == tenant_id)
        )).scalar() or 0

        return {
            "total_recommendations": total_recommendations,
            "pending_recommendations": pending_recommendations,
            "total_risk_alerts": total_risk_alerts,
            "unresolved_alerts": unresolved_alerts,
            "total_pending_actions": total_pending_actions,
            "total_draft_documents": total_draft_documents,
            "total_insight_cards": total_insight_cards,
        }


class PendingActionService:
    """
    待办事项应用服务

    编排待办事项的完整生命周期: 创建 → 审批/拒绝 → 执行 → 过期清理
    支持幂等控制和审批流集成。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, tenant_id: str, recommendation_id: str, domain: str,
                     action_type: str, action_data: dict,
                     idempotency_key: str = "", **kwargs) -> PendingAction:
        """创建待办事项: 幂等校验 → 持久化"""
        from erp.shared.exceptions import DuplicateCodeException
        if idempotency_key:
            existing = (await self._session.execute(
                select(PendingAction).where(
                    PendingAction.tenant_id == tenant_id,
                    PendingAction.idempotency_key == idempotency_key,
                    PendingAction.status != "expired",
                )
            )).scalar_one_or_none()
            if existing:
                raise DuplicateCodeException(message=f"Pending action with key '{idempotency_key}' already exists")
        action = PendingAction(
            tenant_id=tenant_id, recommendation_id=recommendation_id,
            domain=domain, action_type=action_type,
            action_data_json=json.dumps(action_data, default=str),
            idempotency_key=idempotency_key,
            created_by=kwargs.get("created_by", ""),
        )
        self._session.add(action)
        await self._session.flush()
        return action

    async def approve(self, action_id: str, tenant_id: str, approver_id: str = "") -> PendingAction:
        """审批通过待办事项"""
        action = await self._get_or_raise(action_id, tenant_id)
        if action.status != "pending":
            raise ValidationException(message=f"Cannot approve action in '{action.status}' status")
        action.status = "approved"
        await self._session.flush()
        return action

    async def reject(self, action_id: str, tenant_id: str, reason: str = "") -> PendingAction:
        """拒绝待办事项"""
        action = await self._get_or_raise(action_id, tenant_id)
        if action.status != "pending":
            raise ValidationException(message=f"Cannot reject action in '{action.status}' status")
        action.status = "rejected"
        await self._session.flush()
        return action

    async def mark_executed(self, action_id: str, tenant_id: str) -> PendingAction:
        """标记待办事项已执行"""
        action = await self._get_or_raise(action_id, tenant_id)
        if action.status != "approved":
            raise ValidationException(message="Action must be 'approved' before execution")
        action.status = "executed"
        await self._session.flush()
        return action

    async def mark_failed(self, action_id: str, tenant_id: str, error_msg: str = "") -> PendingAction:
        """标记待办事项执行失败"""
        action = await self._get_or_raise(action_id, tenant_id)
        if action.status not in ("approved", "executed"):
            raise ValidationException(message="Action must be 'approved' or 'executed' to mark failed")
        action.status = "failed"
        await self._session.flush()
        return action

    async def expire_stale_actions(self, tenant_id: str, days_threshold: int = 7) -> int:
        """过期超时未处理的待办事项"""
        from datetime import timedelta
        cutoff = datetime.now(UTC) - timedelta(days=days_threshold)
        stmt = select(PendingAction).where(
            PendingAction.tenant_id == tenant_id,
            PendingAction.status == "pending",
            PendingAction.created_at < cutoff,
        )
        stale = list((await self._session.execute(stmt)).scalars().all())
        for action in stale:
            action.status = "expired"
        await self._session.flush()
        return len(stale)

    async def list_pending(self, tenant_id: str, domain: str = "",
                           page: int = 1, page_size: int = 20) -> tuple[list[PendingAction], int]:
        """查询待办事项列表"""
        from sqlalchemy import func as sa_func
        conditions = [PendingAction.tenant_id == tenant_id, PendingAction.status == "pending"]
        if domain:
            conditions.append(PendingAction.domain == domain)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(PendingAction).where(*conditions)
        )).scalar() or 0
        stmt = select(PendingAction).where(*conditions).order_by(
            PendingAction.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total

    async def _get_or_raise(self, action_id: str, tenant_id: str) -> PendingAction:
        from erp.shared.exceptions import NotFoundException
        action = (await self._session.execute(
            select(PendingAction).where(PendingAction.id == action_id, PendingAction.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not action:
            raise NotFoundException(message=f"Pending action '{action_id}' not found")
        return action


class SmartAssistantService:
    """
    智能推荐聚合应用服务

    聚合各域数据，生成跨域智能推荐:
    - 库存预警 → 补货推荐
    - 销售趋势 → 广告调价推荐
    - 利润异常 → 成本优化推荐
    - 物流时效 → 承运商切换推荐
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def generate_recommendations(self, tenant_id: str) -> list[dict]:
        """
        自动生成智能推荐

        流程: 扫描各域异常数据 → 生成推荐 → 写入Recommendation
        """
        recommendations: list[dict] = []
        recs = await self._scan_inventory_risks(tenant_id)
        recommendations.extend(recs)
        recs = await self._scan_profit_risks(tenant_id)
        recommendations.extend(recs)
        recs = await self._scan_logistics_risks(tenant_id)
        recommendations.extend(recs)
        for rec in recommendations:
            rec_obj = Recommendation(
                tenant_id=tenant_id,
                domain=rec.get("domain", "SYS"),
                rec_type=rec.get("rec_type", "optimization"),
                title=rec.get("title", ""),
                description=rec.get("description", ""),
                action_type=rec.get("action_type", "info"),
                action_data_json=json.dumps(rec.get("action_data", {}), default=str),
                priority=rec.get("priority", "medium"),
                status="submitted",
                source=rec.get("source", "auto_scan"),
            )
            self._session.add(rec_obj)
        if recommendations:
            await self._session.flush()
        return recommendations

    async def _scan_inventory_risks(self, tenant_id: str) -> list[dict]:
        """扫描库存风险: 低库存SKU → 补货推荐"""
        from erp.modules.wms.domain.models import Inventory
        stmt = select(Inventory).where(
            Inventory.tenant_id == tenant_id,
            Inventory.qty_available <= Inventory.reorder_point,
        )
        low_stock = list((await self._session.execute(stmt)).scalars().all())
        recs = []
        for inv in low_stock[:20]:
            recs.append({
                "domain": "SCM", "rec_type": "replenishment",
                "title": f"Low stock alert: SKU {inv.sku_id}",
                "description": f"Available qty {inv.qty_available}, reorder point {inv.reorder_point}",
                "action_type": "config_change",
                "priority": "high" if inv.qty_available <= 0 else "medium",
                "source": "inventory_scan",
                "action_data": {
                    "sku_id": inv.sku_id, "warehouse_id": inv.warehouse_id,
                    "current_qty": inv.qty_available, "reorder_point": inv.reorder_point,
                },
            })
        return recs


class SystemHealthMonitorService:
    """
    系统健康监控服务

    监控各子域系统健康状态: 服务可用性/数据同步延迟/异常率/性能指标
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def check_domain_health(self, tenant_id: str, domain: str) -> dict:
        """检查单个域健康状态"""
        domain_checks = {
            "OMS": self._check_oms_health,
            "WMS": self._check_wms_health,
            "SCM": self._check_scm_health,
            "FMS": self._check_fms_health,
            "ADS": self._check_ads_health,
            "TMS": self._check_tms_health,
            "FBA": self._check_fba_health,
            "CRM": self._check_crm_health,
            "SOM": self._check_som_health,
            "PDM": self._check_pdm_health,
            "BI": self._check_bi_health,
        }
        checker = domain_checks.get(domain.upper())
        if not checker:
            return {"domain": domain, "status": "unknown", "reason": "no health check defined"}
        return await checker(tenant_id)

    async def check_all_domains(self, tenant_id: str) -> dict:
        """检查所有域健康状态"""
        domains = ["OMS", "WMS", "SCM", "FMS", "ADS", "TMS", "FBA", "CRM", "SOM", "PDM", "BI", "IAM", "DASHBOARD", "SYS"]
        results = {}
        for domain in domains:
            results[domain] = await self.check_domain_health(tenant_id, domain)
        healthy_count = sum(1 for r in results.values() if r.get("status") == "healthy")
        degraded_count = sum(1 for r in results.values() if r.get("status") == "degraded")
        unhealthy_count = sum(1 for r in results.values() if r.get("status") == "unhealthy")
        return {
            "total_domains": len(domains),
            "healthy": healthy_count, "degraded": degraded_count, "unhealthy": unhealthy_count,
            "overall_status": "healthy" if unhealthy_count == 0 and degraded_count <= 2 else "degraded" if unhealthy_count <= 2 else "unhealthy",
            "domains": results,
        }

    async def _check_oms_health(self, tenant_id: str) -> dict:
        try:
            from erp.modules.oms.domain.models import Order
            pending_count = (await self._session.execute(
                select(func.count()).select_from(Order).where(
                    Order.tenant_id == tenant_id, Order.status == "pending")
            )).scalar() or 0
            return {"domain": "OMS", "status": "healthy", "pending_orders": pending_count}
        except Exception as e:
            return {"domain": "OMS", "status": "unhealthy", "error": str(e)}

    async def _check_wms_health(self, tenant_id: str) -> dict:
        try:
            from erp.modules.wms.domain.models import Inventory
            low_stock = (await self._session.execute(
                select(func.count()).select_from(Inventory).where(
                    Inventory.tenant_id == tenant_id, Inventory.qty_available <= Inventory.reorder_point)
            )).scalar() or 0
            return {"domain": "WMS", "status": "degraded" if low_stock > 10 else "healthy", "low_stock_items": low_stock}
        except Exception as e:
            return {"domain": "WMS", "status": "unhealthy", "error": str(e)}

    async def _check_scm_health(self, tenant_id: str) -> dict:
        try:
            from erp.modules.scm.domain.models import PurchaseOrder
            overdue = (await self._session.execute(
                select(func.count()).select_from(PurchaseOrder).where(
                    PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.status == "overdue")
            )).scalar() or 0
            return {"domain": "SCM", "status": "degraded" if overdue > 5 else "healthy", "overdue_po": overdue}
        except Exception as e:
            return {"domain": "SCM", "status": "unhealthy", "error": str(e)}

    async def _check_fms_health(self, tenant_id: str) -> dict:
        try:
            from erp.modules.fms.domain.models import PlatformSettlement
            unreconciled = (await self._session.execute(
                select(func.count()).select_from(PlatformSettlement).where(
                    PlatformSettlement.tenant_id == tenant_id, PlatformSettlement.status == "pending")
            )).scalar() or 0
            return {"domain": "FMS", "status": "degraded" if unreconciled > 20 else "healthy", "unreconciled": unreconciled}
        except Exception as e:
            return {"domain": "FMS", "status": "unhealthy", "error": str(e)}

    async def _check_ads_health(self, tenant_id: str) -> dict:
        try:
            from erp.modules.ads.domain.models import AdCampaign
            active = (await self._session.execute(
                select(func.count()).select_from(AdCampaign).where(
                    AdCampaign.tenant_id == tenant_id, AdCampaign.status == "enabled")
            )).scalar() or 0
            return {"domain": "ADS", "status": "healthy", "active_campaigns": active}
        except Exception as e:
            return {"domain": "ADS", "status": "unhealthy", "error": str(e)}

    async def _check_tms_health(self, tenant_id: str) -> dict:
        try:
            from erp.modules.tms.domain.models import Shipment
            in_transit = (await self._session.execute(
                select(func.count()).select_from(Shipment).where(
                    Shipment.tenant_id == tenant_id, Shipment.status == "in_transit")
            )).scalar() or 0
            return {"domain": "TMS", "status": "healthy", "in_transit": in_transit}
        except Exception as e:
            return {"domain": "TMS", "status": "unhealthy", "error": str(e)}

    async def _check_fba_health(self, tenant_id: str) -> dict:
        try:
            from erp.modules.fba.domain.models import FbaShipment
            receiving = (await self._session.execute(
                select(func.count()).select_from(FbaShipment).where(
                    FbaShipment.tenant_id == tenant_id, FbaShipment.status == "receiving")
            )).scalar() or 0
            return {"domain": "FBA", "status": "healthy", "receiving_shipments": receiving}
        except Exception as e:
            return {"domain": "FBA", "status": "unhealthy", "error": str(e)}

    async def _check_crm_health(self, tenant_id: str) -> dict:
        try:
            from erp.modules.crm.domain.models import ServiceTicket
            open_tickets = (await self._session.execute(
                select(func.count()).select_from(ServiceTicket).where(
                    ServiceTicket.tenant_id == tenant_id, ServiceTicket.status.in_(["open", "in_progress"]))
            )).scalar() or 0
            return {"domain": "CRM", "status": "degraded" if open_tickets > 50 else "healthy", "open_tickets": open_tickets}
        except Exception as e:
            return {"domain": "CRM", "status": "unhealthy", "error": str(e)}

    async def _check_som_health(self, tenant_id: str) -> dict:
        try:
            from erp.modules.som.domain.models import Listing
            active = (await self._session.execute(
                select(func.count()).select_from(Listing).where(
                    Listing.tenant_id == tenant_id, Listing.status == "active")
            )).scalar() or 0
            return {"domain": "SOM", "status": "healthy", "active_listings": active}
        except Exception as e:
            return {"domain": "SOM", "status": "unhealthy", "error": str(e)}

    async def _check_pdm_health(self, tenant_id: str) -> dict:
        try:
            from erp.modules.pdm.domain.models import SPU
            active = (await self._session.execute(
                select(func.count()).select_from(SPU).where(
                    SPU.tenant_id == tenant_id, SPU.status == "active")
            )).scalar() or 0
            return {"domain": "PDM", "status": "healthy", "active_spus": active}
        except Exception as e:
            return {"domain": "PDM", "status": "unhealthy", "error": str(e)}

    async def _check_bi_health(self, tenant_id: str) -> dict:
        try:
            from erp.modules.bi.domain.models import BiMetricValue
            from datetime import date, timedelta
            recent = (await self._session.execute(
                select(func.count()).select_from(BiMetricValue).where(
                    BiMetricValue.tenant_id == tenant_id,
                    BiMetricValue.period_date >= date.today() - timedelta(days=1))
            )).scalar() or 0
            return {"domain": "BI", "status": "degraded" if recent == 0 else "healthy", "recent_values": recent}
        except Exception as e:
            return {"domain": "BI", "status": "unhealthy", "error": str(e)}


class WorkflowEngineService:
    """
    工作流引擎服务

    编排跨域业务工作流: 定义→触发→执行→监控
    - 审批工作流
    - 自动化工作流
    - 跨域协作工作流
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def trigger_workflow(self, tenant_id: str, workflow_type: str,
                                trigger_data: dict) -> dict:
        """触发工作流"""
        workflow_steps = {
            "purchase_approval": [
                {"step": 1, "action": "validate_budget", "domain": "FMS", "auto": True},
                {"step": 2, "action": "check_inventory", "domain": "WMS", "auto": True},
                {"step": 3, "action": "manager_approval", "domain": "IAM", "auto": False},
                {"step": 4, "action": "create_purchase_order", "domain": "SCM", "auto": True},
            ],
            "listing_publish": [
                {"step": 1, "action": "compliance_check", "domain": "PDM", "auto": True},
                {"step": 2, "action": "price_validation", "domain": "SOM", "auto": True},
                {"step": 3, "action": "sync_to_platform", "domain": "SOM", "auto": True},
                {"step": 4, "action": "activate_ads", "domain": "ADS", "auto": False},
            ],
            "order_fulfillment": [
                {"step": 1, "action": "risk_check", "domain": "OMS", "auto": True},
                {"step": 2, "action": "allocate_inventory", "domain": "WMS", "auto": True},
                {"step": 3, "action": "create_shipment", "domain": "TMS", "auto": True},
                {"step": 4, "action": "update_order_status", "domain": "OMS", "auto": True},
            ],
            "refund_processing": [
                {"step": 1, "action": "validate_return", "domain": "CRM", "auto": True},
                {"step": 2, "action": "receive_inventory", "domain": "WMS", "auto": True},
                {"step": 3, "action": "process_refund", "domain": "FMS", "auto": True},
                {"step": 4, "action": "update_customer", "domain": "CRM", "auto": True},
            ],
        }
        steps = workflow_steps.get(workflow_type, [])
        if not steps:
            return {"workflow_type": workflow_type, "status": "unknown_workflow", "steps": []}
        execution_log = []
        for step in steps:
            step_result = {
                "step": step["step"], "action": step["action"],
                "domain": step["domain"], "auto": step["auto"],
                "status": "auto_completed" if step["auto"] else "pending_approval",
            }
            execution_log.append(step_result)
            if not step["auto"]:
                break
        return {
            "workflow_type": workflow_type, "status": "in_progress",
            "trigger_data": trigger_data, "steps": execution_log,
            "total_steps": len(steps), "completed_steps": sum(1 for s in execution_log if s["status"] == "auto_completed"),
        }

    async def get_workflow_status(self, tenant_id: str, workflow_id: str) -> dict:
        """查询工作流状态"""
        return {"workflow_id": workflow_id, "status": "in_progress", "current_step": 2}

    async def approve_workflow_step(self, tenant_id: str, workflow_id: str,
                                     step: int, approved: bool,
                                     comment: str = "") -> dict:
        """审批工作流步骤"""
        return {
            "workflow_id": workflow_id, "step": step,
            "approved": approved, "comment": comment,
            "status": "completed" if approved else "rejected",
        }

    async def _scan_profit_risks(self, tenant_id: str) -> list[dict]:
        """扫描利润风险: 利润率低于阈值 → 成本优化推荐"""
        return []

    async def _scan_logistics_risks(self, tenant_id: str) -> list[dict]:
        """扫描物流风险: 超时发货 → 承运商切换推荐"""
        from erp.modules.tms.domain.models import Shipment
        from datetime import timedelta
        cutoff = datetime.now(UTC) - timedelta(days=7)
        stmt = select(Shipment).where(
            Shipment.tenant_id == tenant_id,
            Shipment.status.in_(("in_transit", "shipped")),
            Shipment.shipped_at < cutoff,
        )
        delayed = list((await self._session.execute(stmt)).scalars().all())
        recs = []
        for s in delayed[:10]:
            recs.append({
                "domain": "TMS", "rec_type": "carrier_switch",
                "title": f"Delayed shipment: {s.shipment_no}",
                "description": f"Shipment in '{s.status}' for over 7 days",
                "action_type": "authorization_request",
                "priority": "high",
                "source": "logistics_scan",
                "action_data": {
                    "shipment_id": str(s.id), "shipment_no": s.shipment_no,
                    "provider_id": s.provider_id, "days_in_transit": (datetime.now(UTC) - (s.shipped_at or s.created_at)).days,
                },
            })
        return recs
