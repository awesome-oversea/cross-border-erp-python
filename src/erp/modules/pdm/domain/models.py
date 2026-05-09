"""
PDM域 - 产品开发域 ORM模型

本模块定义了产品开发域的所有数据库实体映射，包含:
- Category: 产品分类表，树形结构
- Brand: 品牌表
- SPU: 标准产品单元，商品主体
- SKU: 库存单元，最小可售单位
- ChannelSKUMapping: 渠道SKU映射表
- ProductProject: 产品开发项目表，从选品到上架全流程
- BundleProduct: 组合产品(Bundle)明细表(V4新增)
- TitleLibrary: 标题库(V4新增)，Listing标题模板与优化参考
- ImageLibrary: 图片库(V4新增)，产品图片统一管理
- ProductIssue: 产品问题记录表(V4新增)，质量问题跟踪
- QualityStandard: 质量标准表
- IPRecord: 知识产权记录表
- SensitiveWord: 敏感词表
- UPCPool: UPC条码池
- ProductCollection: 选品采集表，竞品/货源采集

技术栈: SQLAlchemy 2.x + async + PostgreSQL
主键策略: UUID由应用层生成
多租户: 所有业务表包含tenant_id字段实现隔离
软删除: deleted_at字段，非物理删除
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base


class Category(Base):
    """产品分类表 - 树形结构，使用物化路径加速查询"""
    __tablename__ = "category"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="父分类ID，顶级为NULL")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="分类名称")
    code: Mapped[str] = mapped_column(String(100), nullable=False, comment="分类编码")
    path: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="物化路径，如/root/child1/child2")
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="层级深度，从1开始")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序序号")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class Brand(Base):
    """品牌表 - 产品品牌管理"""
    __tablename__ = "brand"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="品牌名称(中文)")
    name_en: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="品牌名称(英文)")
    code: Mapped[str] = mapped_column(String(100), nullable=False, comment="品牌编码")
    logo_url: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="品牌Logo地址")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class SPU(Base):
    """标准产品单元(SPU) - 商品主体，一个SPU可包含多个SKU"""
    __tablename__ = "spu"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    name: Mapped[str] = mapped_column(String(500), nullable=False, comment="产品名称(中文)")
    name_en: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="产品名称(英文)")
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, comment="SPU编码，全局唯一")
    category_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="分类ID")
    brand_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="品牌ID")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="产品描述(中文)")
    description_en: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="产品描述(英文)")
    main_image: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="主图地址")
    images_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="图片列表JSON")
    attributes_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="产品属性JSON")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True, comment="状态: draft/active/discontinued")
    spu_type: Mapped[str] = mapped_column(String(30), nullable=False, default="normal", comment="产品类型: normal/bundle/virtual")
    origin_country: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="原产国")
    hs_code: Mapped[str] = mapped_column(String(30), nullable=False, default="", comment="海关编码")
    declared_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="申报价值")
    declared_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY", comment="申报币种")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class SKU(Base):
    """库存单元(SKU) - 最小可售单位，包含规格、尺寸、成本等信息"""
    __tablename__ = "sku"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    spu_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="所属SPU ID")
    sku_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="SKU编码")
    barcode: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="条形码")
    name: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="SKU名称")
    variant_attrs_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="变体属性JSON，如颜色/尺码")
    spec_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="规格参数JSON")
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="重量(kg)")
    length: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="长度(cm)")
    width: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="宽度(cm)")
    height: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="高度(cm)")
    cost_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="成本价")
    cost_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY", comment="成本币种")
    purchase_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="采购价")
    supplier_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="默认供应商ID")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True, comment="状态: active/discontinued")
    image: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="SKU图片地址")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class ChannelSKUMapping(Base):
    """渠道SKU映射表 - ERP SKU与平台渠道SKU的映射关系"""
    __tablename__ = "channel_sku_mapping"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="ERP SKU ID")
    channel: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="渠道: amazon/shopify/ebay/...")
    channel_sku: Mapped[str] = mapped_column(String(200), nullable=False, comment="渠道侧SKU编码")
    channel_product_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="渠道侧产品ID")
    store_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="店铺ID")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class ProductProject(Base):
    """产品开发项目表 - 从选品到上架全流程管理，6阶段流转"""
    __tablename__ = "product_project"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    name: Mapped[str] = mapped_column(String(500), nullable=False, comment="项目名称")
    code: Mapped[str] = mapped_column(String(100), nullable=False, comment="项目编码")
    category_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="目标分类ID")
    stage: Mapped[str] = mapped_column(String(30), nullable=False, default="proposing", index=True, comment="阶段: proposing/researching/designing/sourcing/sampling/producing/listing")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", comment="优先级: critical/high/medium/low")
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="负责人ID")
    team_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="团队成员JSON")
    target_market: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="目标市场")
    target_platform: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="目标平台")
    research_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="市场调研数据JSON")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True, comment="状态: draft/in_progress/completed/cancelled")
    approval_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="审批实例ID")
    recommendation_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="PMS推荐ID")
    spu_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="审批通过后生成的SPU ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class BundleProduct(Base):
    """组合产品(Bundle)明细表(V4新增) - 组合产品的子SKU组成关系"""
    __tablename__ = "bundle_product"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    spu_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="组合产品SPU ID")
    component_sku_id: Mapped[str] = mapped_column(String(36), nullable=False, comment="子组件SKU ID")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="子组件数量")
    discount_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="组合折扣百分比，0-100")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序序号")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class TitleLibrary(Base):
    """标题库(V4新增) - Listing标题模板与优化参考，支持多语言多平台"""
    __tablename__ = "title_library"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    category_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="分类ID")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="适用平台: amazon/shopify/ebay/...")
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en", comment="语言: en/de/fr/es/ja/...")
    title: Mapped[str] = mapped_column(String(1000), nullable=False, comment="标题内容")
    keywords_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="关键词列表JSON")
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="使用次数")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="SEO评分")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class ImageLibrary(Base):
    """图片库(V4新增) - 产品图片统一管理，支持多平台多类型"""
    __tablename__ = "image_library"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    sku_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="关联SKU ID")
    spu_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="关联SPU ID")
    image_type: Mapped[str] = mapped_column(String(30), nullable=False, default="main", comment="图片类型: main/detail/lifestyle/infographic/size_chart")
    url: Mapped[str] = mapped_column(String(1000), nullable=False, comment="图片URL")
    thumbnail_url: Mapped[str] = mapped_column(String(1000), nullable=False, default="", comment="缩略图URL")
    alt_text: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="替代文本")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="标签列表JSON")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="适用平台")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="上传人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class ProductIssue(Base):
    """产品问题记录表(V4新增) - 质量问题跟踪与处理"""
    __tablename__ = "product_issue"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    sku_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="关联SKU ID")
    spu_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="关联SPU ID")
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="问题类型: quality/packaging/labeling/safety/compliance")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", comment="严重程度: critical/high/medium/low")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="问题描述")
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="证据附件JSON")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", comment="状态: open/in_progress/resolved/closed")
    assigned_to: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="处理人ID")
    resolution: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="解决方案")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="解决时间")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="报告人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class QualityStandard(Base):
    """质量标准表 - 产品质量检验标准与包装规范"""
    __tablename__ = "quality_standard"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    category_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="分类ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="标准名称")
    standard_type: Mapped[str] = mapped_column(String(50), nullable=False, default="general", comment="标准类型: general/electrical/textile/food/...")
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="检验项目列表JSON")
    logistics_attrs_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="物流属性JSON")
    packaging_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="包装成本")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class IPRecord(Base):
    """知识产权记录表 - 商标/专利/版权的IP风险管理"""
    __tablename__ = "ip_record"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    sku_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="关联SKU ID")
    spu_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="关联SPU ID")
    ip_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="IP类型: trademark/patent/copyright")
    ip_number: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="IP编号")
    ip_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="IP名称")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/expired/revoked")
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="none", comment="风险等级: none/low/medium/high")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class SensitiveWord(Base):
    """敏感词表 - 平台违禁词与商标词管理"""
    __tablename__ = "sensitive_word"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    word: Mapped[str] = mapped_column(String(200), nullable=False, comment="敏感词")
    word_type: Mapped[str] = mapped_column(String(30), nullable=False, default="general", comment="类型: general/trademark/prohibited")
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en", comment="语言")
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="适用平台")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")


class UPCPool(Base):
    """UPC条码池 - 条码的分配与回收管理"""
    __tablename__ = "upc_pool"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    upc_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="UPC条码，全局唯一")
    sku_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="已分配的SKU ID")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available", index=True, comment="状态: available/allocated/recycled")
    allocated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="分配时间")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")


class ProductCollection(Base):
    """选品采集表 - 竞品/货源采集，支持手动与自动采集"""
    __tablename__ = "product_collection"
    __table_args__ = {"schema": "pdm"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    source_platform: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="来源平台: amazon/shopify/1688/alibaba/other")
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False, default="", comment="来源URL")
    source_product_id: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="来源平台产品ID")
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="产品标题")
    title_en: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="产品标题(英文)")
    main_image: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="主图地址")
    images_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="图片列表JSON")
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="价格")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD", comment="币种")
    category_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="分类名称")
    attributes_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="属性JSON")
    variants_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="变体列表JSON")
    seller_info_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="卖家信息JSON")
    sales_data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="销售数据JSON")
    review_data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="评价数据JSON")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="collected", index=True, comment="状态: collected/analyzing/converted/discarded")
    collection_type: Mapped[str] = mapped_column(String(30), nullable=False, default="manual", comment="采集方式: manual/keyword/category_url/monitor")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="标签JSON")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="选品评分")
    converted_spu_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="转化后的SPU ID")
    collected_by: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="采集人ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
