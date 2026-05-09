"""
SYS域 - 智能中枢域(PMS) ORM模型

本模块定义了智能中枢域的所有数据库实体映射，包含:
- Recommendation: 推荐决策表，PMS核心输出，支持6类推荐(选品/定价/广告/补货/风控/洞察)
- DraftDocument: 草稿文档表，PMS推荐转正式单据前的中间态，支持审批流
- PendingAction: 待执行动作表，需要人工确认或授权的PMS动作，含幂等控制
- RiskAlert: 风险告警表，4级风险等级+多域风险类型，支持证据链与处置追踪
- InsightCard: 洞察卡片表，趋势/摘要/对比/异常四类洞察，含指标与归档管理

设计要点:
    - 所有模型支持多租户隔离(tenant_id)
    - 推荐决策全生命周期: submitted→approved→executing→measuring→completed/rejected
    - 幂等控制(idempotency_key)确保推荐/动作的精确一次语义
    - 审计追踪(actor_id/actor_type/agent_id)记录操作主体
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base


class Recommendation(Base):
    """推荐决策表 - PMS核心输出，6类推荐+全生命周期管理，含置信度与证据链"""
    __tablename__ = "recommendation"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    recommendation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="PMS推荐ID，全局唯一标识")
    erp_reference_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="ERP关联单据ID，如采购单/刊登ID等")
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="所属域: PDM/SOM/ADS/OMS/SCM/WMS/FBA/TMS/CRM/FMS/BI/SYS/IAM/DASHBOARD")
    recommendation_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="推荐类型: selection选品/pricing定价/advertising广告/replenishment补货/risk风控/insight洞察")
    target_object_type: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="目标对象类型，如SKU/Listing/PurchaseOrder等")
    target_object_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="目标对象ID")
    content_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="推荐内容JSON，含具体建议与参数")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="推荐评分，0-100，越高越优")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="置信度，0-1，越高越可信")
    evidence_chain_id: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="证据链ID，关联数据溯源")
    data_sources_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="数据来源列表JSON，记录推荐依据的数据源")
    risk_flags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="风险标记列表JSON，含风险类型与描述")
    explainability: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="可解释性描述，推荐理由的自然语言说明")
    requested_action: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="请求执行的动作，如create_po/update_price/publish_listing等")
    approval_policy: Mapped[str] = mapped_column(String(50), nullable=False, default="manual", comment="审批策略: manual手动/auto自动/conditional条件自动")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="submitted", index=True, comment="状态: submitted/approved/rejected/executing/completed/failed/measuring")
    rejection_reason: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="拒绝原因，status=rejected时填写")
    execution_result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="执行结果JSON，含成功/失败详情与返回数据")
    measured_result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="度量结果JSON，含KPI变化与效果评估")
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, default="", index=True, comment="幂等键，确保同一推荐不重复处理")
    source_system: Mapped[str] = mapped_column(String(30), nullable=False, default="PMS", comment="来源系统标识: PMS/MANUAL/API")
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="操作主体ID，用户或服务账号")
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False, default="service_account", comment="操作主体类型: user/service_account/agent")
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="代理ID，AI代理操作时记录")
    scope: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="作用域，推荐生效范围描述")
    purpose: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="目的说明，推荐的业务目标")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="链路追踪ID，用于分布式追踪")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class DraftDocument(Base):
    """草稿文档表 - PMS推荐转正式单据前的中间态，支持审批流与幂等控制"""
    __tablename__ = "draft_document"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    recommendation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="关联推荐ID")
    draft_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="草稿类型: listing刊登/purchase_order采购/inbound_plan入库/replenishment补货等")
    draft_data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="草稿数据JSON，含待转正式单据的完整内容")
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="所属域: PDM/SOM/SCM/WMS/FBA等")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True, comment="状态: draft/pending_approval/approved/converted/rejected/cancelled")
    approval_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="审批流程实例ID")
    converted_to: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="转正式后的单据ID")
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, default="", index=True, comment="幂等键，确保同一草稿不重复创建")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class PendingAction(Base):
    """待执行动作表 - 需要人工确认或授权的PMS动作，含审批流与幂等控制"""
    __tablename__ = "pending_action"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    recommendation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="关联推荐ID")
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="所属域: PDM/SOM/SCM/WMS/FBA等")
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="动作类型: config_change配置变更/authorization_request授权请求/data_access数据访问等")
    action_data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="动作数据JSON，含待执行动作的详细参数")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True, comment="状态: pending/approved/rejected/executed/failed/expired")
    approval_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="审批流程实例ID")
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, default="", index=True, comment="幂等键，确保同一动作不重复执行")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class RiskAlert(Base):
    """风险告警表 - 4级风险等级+多域风险类型，支持证据链与处置追踪"""
    __tablename__ = "risk_alert"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    recommendation_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="关联推荐ID，可为空(非推荐触发的风险)")
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="所属域: OMS/SCM/WMS/FMS等")
    risk_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="风险类型: order_risk订单风险/profit_risk利润风险/supply_risk供应风险/inventory_risk库存风险/compliance_risk合规风险")
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", comment="风险等级: low低/medium中/high高/critical严重")
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="风险标题")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="风险详细描述")
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="风险证据JSON，含数据快照/指标/阈值等")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True, comment="状态: open/investigating/mitigated/closed/escalated")
    assigned_to: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="处理人ID")
    resolution: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="处置方案描述")
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, default="", index=True, comment="幂等键，确保同一风险不重复告警")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class InsightCard(Base):
    """洞察卡片表 - 趋势/摘要/对比/异常四类洞察，含指标数据与归档管理"""
    __tablename__ = "insight_card"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    recommendation_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="关联推荐ID，可为空")
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="所属域: PDM/SOM/OMS/SCM/WMS/FMS等")
    card_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="卡片类型: trend趋势/summary摘要/comparison对比/anomaly异常")
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="洞察标题")
    content_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="洞察内容JSON，含文字描述/图表数据/关键发现")
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="指标数据JSON，含关键指标名称/值/变化率")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True, comment="状态: active/archived/dismissed")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="归档时间")
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, default="", index=True, comment="幂等键，确保同一洞察不重复生成")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
