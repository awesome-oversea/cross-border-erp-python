"""
BI域 - 商业智能域 ORM模型

本模块定义了商业智能域的所有数据库实体映射，包含:
- BiMetric: 指标定义表，管理BI指标元数据与计算逻辑
- BiMetricValue: 指标值表，按日/周/月存储指标数值，支持多维度切片
- BiReport: 报表定义表，支持表格/图表/透视表等多种报表类型
- BiDashboardWidget: 看板组件表，指标卡/图表/报表等组件配置
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base


class BiMetric(Base):
    """指标定义表 - 管理BI指标元数据、计算SQL与刷新频率"""
    __tablename__ = "bi_metric"
    __table_args__ = {"schema": "bi"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="指标编码，租户内唯一")
    metric_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="指标名称")
    metric_category: Mapped[str] = mapped_column(String(50), nullable=False, default="general", index=True, comment="指标分类: sales/inventory/finance/logistics/customer/general")
    metric_unit: Mapped[str] = mapped_column(String(30), nullable=False, default="", comment="指标单位: count/amount/percent/ratio")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="指标描述")
    calculation_sql: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="计算SQL模板")
    data_source: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="数据源标识")
    refresh_frequency: Mapped[str] = mapped_column(String(30), nullable=False, default="daily", comment="刷新频率: hourly/daily/weekly/monthly")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class BiMetricValue(Base):
    """指标值表 - 按日/周/月存储指标数值，支持多维度切片与平台/店铺下钻"""
    __tablename__ = "bi_metric_value"
    __table_args__ = {"schema": "bi"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    metric_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="指标ID")
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="指标编码(冗余)")
    period_type: Mapped[str] = mapped_column(String(20), nullable=False, default="daily", comment="周期类型: daily/weekly/monthly")
    period_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True, comment="周期日期")
    numeric_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="数值")
    text_value: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="文本值(用于标签型指标)")
    dimension_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="维度JSON，如{region:'US',category:'Electronics'}")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="店铺ID")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="平台标识")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")


class BiReport(Base):
    """报表定义表 - 支持表格/图表/透视表等多种报表类型，含查询与筛选配置"""
    __tablename__ = "bi_report"
    __table_args__ = {"schema": "bi"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    report_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="报表编码，租户内唯一")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="报表名称")
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, default="table", comment="报表类型: table/chart/pivot")
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general", index=True, comment="报表分类: sales/inventory/finance/logistics/general")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="报表描述")
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="报表配置JSON，含样式/格式等")
    query_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="查询定义JSON，含SQL/参数映射")
    columns_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="列定义JSON，含列名/类型/格式")
    filters_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="筛选器定义JSON，含筛选字段/类型/默认值")
    is_public: Mapped[bool] = mapped_column(default=True, comment="是否公开")
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="所有者ID")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class BiDashboardWidget(Base):
    """看板组件表 - 指标卡/图表/报表等组件配置，支持灵活布局"""
    __tablename__ = "bi_dashboard_widget"
    __table_args__ = {"schema": "bi"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    dashboard_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="看板ID")
    widget_type: Mapped[str] = mapped_column(String(50), nullable=False, default="metric_card", comment="组件类型: metric_card/chart/table/pivot/text")
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="组件标题")
    metric_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="关联指标ID")
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="关联指标编码")
    report_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="关联报表ID")
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="组件配置JSON，含图表类型/颜色/阈值等")
    layout_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="布局配置JSON，含位置/尺寸等")
    refresh_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=300, comment="刷新间隔(秒)")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序序号")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
