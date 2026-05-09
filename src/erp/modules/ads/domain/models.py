"""
ADS域 - 广告管理域 ORM模型

本模块定义了广告管理域的所有数据库实体映射，包含:
- AdCampaign: 广告活动表，支持Sponsored Products/Brands/Display三种类型
- AdGroup: 广告组表，活动下的投放单元，关联SKU与默认竞价
- AdKeyword: 关键词竞价表，广泛/词组/精准三种匹配，含CTR/CPC/ACOS等效果指标
- AdReport: 广告报表表，按日/周/月粒度聚合广告效果数据
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base


class AdCampaign(Base):
    """广告活动表 - 管理广告活动全生命周期，支持三种广告类型与PMS推荐"""
    __tablename__ = "ad_campaign"
    __table_args__ = {"schema": "ads"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    campaign_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="活动编号，租户内唯一")
    name: Mapped[str] = mapped_column(String(500), nullable=False, comment="活动名称")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="平台标识: amazon/walmart等")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="店铺ID")
    campaign_type: Mapped[str] = mapped_column(String(30), nullable=False, default="sponsored_products", comment="活动类型: sponsored_products/sponsored_brands/sponsored_display")
    targeting_type: Mapped[str] = mapped_column(String(30), nullable=False, default="manual", comment="投放类型: manual/auto")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True, comment="状态: draft/enabled/paused/archived")
    daily_budget: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="日预算")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD", comment="币种")
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="开始日期")
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="结束日期")
    total_spend: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="累计花费")
    total_sales: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="累计销售额")
    total_impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="累计曝光量")
    total_clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="累计点击量")
    total_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="累计订单量")
    acos: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="ACOS(广告销售成本比)，百分比")
    roas: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="ROAS(广告投入产出比)")
    platform_campaign_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="平台广告活动ID")
    is_pms_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否PMS推荐草稿")
    recommendation_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="PMS推荐ID")
    approval_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="审批流程实例ID")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class AdGroup(Base):
    """广告组表 - 活动下的投放单元，关联SKU与默认竞价"""
    __tablename__ = "ad_group"
    __table_args__ = {"schema": "ads"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    campaign_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="广告活动ID")
    name: Mapped[str] = mapped_column(String(500), nullable=False, comment="广告组名称")
    default_bid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="默认竞价金额")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="enabled", comment="状态: enabled/paused/archived")
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="关联SKU ID")
    listing_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="关联Listing ID")
    platform_ad_group_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="平台广告组ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class AdKeyword(Base):
    """关键词竞价表 - 广泛/词组/精准三种匹配，含CTR/CPC/转化率等效果指标"""
    __tablename__ = "ad_keyword"
    __table_args__ = {"schema": "ads"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    campaign_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="广告活动ID")
    ad_group_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="广告组ID")
    keyword_text: Mapped[str] = mapped_column(String(500), nullable=False, comment="关键词文本")
    match_type: Mapped[str] = mapped_column(String(20), nullable=False, default="broad", comment="匹配类型: broad/phrase/exact")
    bid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="竞价金额")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="enabled", comment="状态: enabled/paused/archived")
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="曝光量")
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="点击量")
    spend: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="花费")
    sales: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="销售额")
    orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="订单量")
    ctr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="点击率(CTR)")
    cpc: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="单次点击成本(CPC)")
    conversion_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="转化率")
    platform_keyword_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="平台关键词ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class AdReport(Base):
    """广告报表表 - 按日/周/月粒度聚合广告效果数据，含ACOS/ROAS等核心指标"""
    __tablename__ = "ad_report"
    __table_args__ = {"schema": "ads"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    campaign_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="广告活动ID")
    report_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True, comment="报表日期")
    granularity: Mapped[str] = mapped_column(String(20), nullable=False, default="daily", comment="粒度: daily/weekly/monthly")
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="曝光量")
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="点击量")
    spend: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="花费")
    sales: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="销售额")
    orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="订单量")
    units: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="销量(件数)")
    ctr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="点击率(CTR)")
    cpc: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="单次点击成本(CPC)")
    acos: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="广告销售成本比(ACOS)")
    roas: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="广告投入产出比(ROAS)")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD", comment="币种")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="店铺ID")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="平台标识")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
