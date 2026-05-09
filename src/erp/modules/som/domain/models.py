"""
SOM域 - 销售运营管理域 ORM模型

本模块定义了销售运营管理域的所有数据库实体映射，包含:
- Store: 店铺表，管理多平台店铺信息与授权状态
- Listing: 刊登表，SKU级别的多平台商品刊登，支持批量操作与优化
- PriceRule: 售价规则表，加价/降价/固定/竞争四种定价策略
- ListingBatchJob: 刊登批量任务表，刊登/更新/改价/库存同步四类批量操作
- OperationMonitor: 运营监控表，销售/流量/转化/广告花费四类指标监控
- ListingOptimization: Listing优化表，标题/关键词/图片/卖点/描述/全量六类优化
- AlertRule: 告警规则表，支持6类指标+6种条件+4级严重度的灵活告警
- AlertRecord: 告警记录表，告警触发/确认/解决全生命周期追踪
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base


class Store(Base):
    """店铺表 - 管理多平台店铺信息、授权状态与区域配置"""
    __tablename__ = "store"
    __table_args__ = {"schema": "som"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="店铺名称")
    code: Mapped[str] = mapped_column(String(100), nullable=False, comment="店铺编码，租户内唯一")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="平台标识: amazon/shopee/lazada/...")
    region: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="区域编码，如US/UK/DE/JP")
    store_id_on_platform: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="平台侧店铺ID")
    seller_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="卖家ID(MerchantID)")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD", comment="默认币种")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True, comment="状态: active/disabled")
    auth_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unauthorized", comment="授权状态: unauthorized/authorized/expired/revoked")
    auth_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="加密授权令牌")
    auth_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="授权过期时间")
    org_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="所属组织ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class Listing(Base):
    """刊登表 - SKU级别的多平台商品刊登，支持批量操作、优化与PMS推荐"""
    __tablename__ = "listing"
    __table_args__ = {"schema": "som"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="店铺ID")
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="SKU ID")
    channel_sku: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="渠道SKU编码(平台侧)")
    platform_listing_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", index=True, comment="平台Listing ID")
    title: Mapped[str] = mapped_column(String(1000), nullable=False, default="", comment="商品标题(本地语言)")
    title_en: Mapped[str] = mapped_column(String(1000), nullable=False, default="", comment="英文标题")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="商品描述")
    bullet_points_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="卖点列表JSON，最多5条")
    search_terms: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="后台搜索关键词")
    main_image: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="主图URL")
    images_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="图片列表JSON，含主图+附图")
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="售价")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD", comment="币种")
    msrp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="建议零售价(MSRP)")
    sale_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="促销价")
    sale_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="促销开始时间")
    sale_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="促销结束时间")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="可售库存数量")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True, comment="状态: draft/pending/published/unpublished/archived")
    listing_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_listed", index=True, comment="刊登状态: not_listed/active/inactive/suppressed")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="平台标识")
    category_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="平台类目ID")
    is_pms_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否PMS推荐草稿")
    recommendation_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="PMS推荐ID")
    approval_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="审批流程实例ID")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="首次刊登时间")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class PriceRule(Base):
    """售价规则表 - 加价/降价/固定/竞争四种定价策略，支持多维度匹配"""
    __tablename__ = "price_rule"
    __table_args__ = {"schema": "som"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="规则名称")
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="规则类型: markup/markdown/fixed/competitive")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="适用平台")
    region: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="适用区域")
    category_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="适用类目ID")
    formula_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="定价公式JSON，如{type:'percentage',value:30}")
    min_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="最低限价")
    max_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="最高限价")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD", comment="币种")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="优先级，数字越大优先级越高")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class ListingBatchJob(Base):
    """刊登批量任务表 - 刊登/更新/改价/库存同步四类批量操作，记录执行进度与结果"""
    __tablename__ = "listing_batch_job"
    __table_args__ = {"schema": "som"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="任务类型: publish/update/price_change/stock_sync")
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="总记录数")
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="成功数")
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="失败数")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True, comment="状态: pending/running/completed/failed/cancelled")
    result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="执行结果JSON，含成功/失败明细")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class OperationMonitor(Base):
    """运营监控表 - 销售/流量/转化/广告花费四类指标按日聚合监控"""
    __tablename__ = "operation_monitor"
    __table_args__ = {"schema": "som"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="店铺ID")
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="指标类型: sales/traffic/conversion/ads_spend")
    metric_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True, comment="指标日期")
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="指标明细JSON，含各子指标值")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")


class ListingOptimization(Base):
    """Listing优化表 - 标题/关键词/图片/卖点/描述/全量六类优化，记录优化前后评分"""
    __tablename__ = "listing_optimization"
    __table_args__ = {"schema": "som"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    listing_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="Listing ID")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="店铺ID")
    opt_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="优化类型: title/keyword/image/bullet_point/description/full")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True, comment="状态: pending/in_progress/completed/failed")
    score_before: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="优化前评分")
    score_after: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="优化后评分")
    suggestions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="优化建议列表JSON")
    applied_suggestions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="已采纳建议列表JSON")
    snapshot_before_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="优化前快照JSON")
    snapshot_after_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="优化后快照JSON")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class AlertRule(Base):
    """告警规则表 - 支持6类指标+6种条件+4级严重度的灵活告警，含冷却期与通知渠道"""
    __tablename__ = "alert_rule"
    __table_args__ = {"schema": "som"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="规则名称")
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="指标类型: sales/traffic/conversion/ads_spend/inventory/listing")
    condition_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="条件类型: gt/lt/eq/gte/lte/between/change_rate")
    threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="阈值下限")
    threshold_max: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="阈值上限(between条件时使用)")
    time_window: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="时间窗口(小时)")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning", comment="严重程度: info/warning/critical")
    notify_channels: Mapped[str] = mapped_column(String(200), nullable=False, default="email", comment="通知渠道: email/sms/feishu/dingtalk/wechat")
    notify_targets_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="通知目标列表JSON，含用户ID/群组ID")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="适用平台")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="适用店铺ID，空表示全部")
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60, comment="冷却期(分钟)，防止重复告警")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True, comment="状态: active/disabled")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class AlertRecord(Base):
    """告警记录表 - 告警触发/确认/解决全生命周期追踪，含通知与确认信息"""
    __tablename__ = "alert_record"
    __table_args__ = {"schema": "som"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    rule_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="告警规则ID")
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="规则名称(冗余)")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="店铺ID")
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="指标类型")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning", comment="严重程度: info/warning/critical")
    actual_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="实际值")
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="阈值")
    message: Mapped[str] = mapped_column(String(1000), nullable=False, default="", comment="告警消息")
    detail_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="告警详情JSON")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="firing", index=True, comment="状态: firing/acknowledged/resolved")
    notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否已通知")
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="通知时间")
    acknowledged_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="确认人ID")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="确认时间")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="解决时间")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
