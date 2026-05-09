"""
Dashboard域 - 工作台/看板域 ORM模型

本模块定义了工作台/看板域的所有数据库实体映射，包含:
- Dashboard: 看板表，自定义工作台看板，支持布局与分享
- DashboardComponent: 看板组件表，指标卡/图表/待办等组件配置
- DashboardShare: 看板分享表，用户/组级权限分享
- TodoItem: 待办事项表，多来源待办聚合，支持优先级排序与SLA
- KpiMetric: KPI指标表，核心运营指标实时展示，含环比/同比
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base


class Dashboard(Base):
    """看板表 - 自定义工作台看板，支持灵活布局与分享"""
    __tablename__ = "dashboard"
    __table_args__ = {"schema": "dashboard"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="看板名称")
    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="看板编码，租户内唯一")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="看板描述")
    layout_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="布局配置JSON，含行列/栅格等")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否默认看板")
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否公开")
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="所有者ID")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序序号")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True, comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class DashboardComponent(Base):
    """看板组件表 - 指标卡/图表/待办等组件配置，支持数据源绑定与样式定制"""
    __tablename__ = "dashboard_component"
    __table_args__ = {"schema": "dashboard"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    dashboard_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="所属看板ID")
    component_type: Mapped[str] = mapped_column(String(50), nullable=False, default="metric_card", comment="组件类型: metric_card指标卡/chart图表/todo_list待办/table数据表/text文本")
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="组件标题")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="组件描述")
    data_source: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="数据源标识，如kpi://orders_today或api://sales/summary")
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="组件配置JSON，含查询参数/筛选条件/展示选项等")
    layout_config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="布局配置JSON，含位置x/y/宽高w/h/栅格信息")
    style_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="样式配置JSON，含颜色/字体/边框等视觉定制")
    refresh_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=300, comment="自动刷新间隔(秒)，0=不自动刷新")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序序号，同看板内组件排列顺序")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class DashboardShare(Base):
    """看板分享表 - 用户/组级权限分享，支持查看/编辑两种权限"""
    __tablename__ = "dashboard_share"
    __table_args__ = {"schema": "dashboard"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    dashboard_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="看板ID")
    share_type: Mapped[str] = mapped_column(String(30), nullable=False, default="user", comment="分享类型: user用户/group组/role角色")
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="分享目标ID，对应用户ID/组ID/角色ID")
    permission: Mapped[str] = mapped_column(String(20), nullable=False, default="view", comment="权限: view查看/edit编辑")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")


class TodoItem(Base):
    """待办事项表 - 多来源待办聚合(订单/库存/客服/审批)，支持优先级排序与SLA"""
    __tablename__ = "dashboard_todo_item"
    __table_args__ = {"schema": "dashboard"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="待办归属用户ID")
    todo_type: Mapped[str] = mapped_column(String(50), nullable=False, default="general", index=True, comment="待办类型: order订单/inventory库存/cs客服/approval审批/general通用")
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="待办标题")
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="", comment="待办描述")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", index=True, comment="优先级: critical紧急/high高/medium中/low低")
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False, default=50, comment="优先级评分，0-100，用于排序(越高越优先)")
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="来源域: oms/wms/crm/scm/fms/sys")
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="来源单据ID，关联原始业务对象")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True, comment="状态: pending待办/in_progress进行中/completed已完成/cancelled已取消/dismissed已忽略")
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="截止时间(SLA)")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="完成时间")
    completed_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="完成人ID")
    assigned_to: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="指派人ID")
    extra_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="扩展信息JSON，含来源系统附加数据")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class KpiMetric(Base):
    """KPI指标表 - 核心运营指标实时展示，含环比变化率与目标达成"""
    __tablename__ = "dashboard_kpi_metric"
    __table_args__ = {"schema": "dashboard"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="指标编码，如orders_today/sales_total/inventory_turnover等")
    metric_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="指标名称，如今日订单量/销售总额/库存周转率等")
    metric_group: Mapped[str] = mapped_column(String(50), nullable=False, default="general", index=True, comment="指标分组: orders订单/sales销售/inventory库存/finance财务/logistics物流/cs客服")
    current_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="当前值")
    previous_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="对比期值(环比/同比)")
    change_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="变化率(%)，(current-previous)/previous*100")
    direction: Mapped[str] = mapped_column(String(10), nullable=False, default="stable", comment="变化方向: up上升/down下降/stable持平")
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="", comment="单位: count数量/amount金额/percent百分比")
    target_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="目标值，用于达成率计算")
    data_source: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="数据源标识，含API路径或SQL查询标识")
    refresh_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=300, comment="刷新间隔(秒)")
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最后刷新时间")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True, comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
