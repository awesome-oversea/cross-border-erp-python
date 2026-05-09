-- ============================================================
-- 跨境电商ERP系统 - 数据库初始化脚本
-- 版本: V1.0
-- 基于需求规格说明书V4 & 详细设计说明书V11
-- 技术栈: PostgreSQL 15+ / SQLAlchemy 2.x async
-- ============================================================
-- 说明:
--   1. 本脚本为项目首次部署的完整建表脚本，不包含迁移逻辑
--   2. 所有表按领域(Domain)分Schema组织
--   3. 主键统一使用UUID，由应用层生成
--   4. 所有业务表包含 tenant_id 实现多租户隔离
--   5. 软删除字段 deleted_at，非物理删除
--   6. 乐观锁字段 version，防止并发覆盖
--   7. 审计字段 created_at / updated_at 自动维护
-- ============================================================

-- ============================================================
-- 0. 扩展与Schema
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE SCHEMA IF NOT EXISTS iam;
CREATE SCHEMA IF NOT EXISTS pdm;
CREATE SCHEMA IF NOT EXISTS som;
CREATE SCHEMA IF NOT EXISTS ads;
CREATE SCHEMA IF NOT EXISTS oms;
CREATE SCHEMA IF NOT EXISTS scm;
CREATE SCHEMA IF NOT EXISTS wms;
CREATE SCHEMA IF NOT EXISTS fba;
CREATE SCHEMA IF NOT EXISTS tms;
CREATE SCHEMA IF NOT EXISTS crm;
CREATE SCHEMA IF NOT EXISTS fms;
CREATE SCHEMA IF NOT EXISTS bi;
CREATE SCHEMA IF NOT EXISTS sys;
CREATE SCHEMA IF NOT EXISTS dashboard;

-- ============================================================
-- 1. IAM域 - 组织权限域
-- 包含: 租户、组织、用户、岗位、角色、权限、用户角色、角色权限、
--       对象级权限、数据权限规则、审计日志
-- ============================================================

CREATE TABLE IF NOT EXISTS iam.tenant (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL,
    code            VARCHAR(50)     NOT NULL UNIQUE,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    plan            VARCHAR(30)     NOT NULL DEFAULT 'free',
    max_users       INT             NOT NULL DEFAULT 10,
    max_stores      INT             NOT NULL DEFAULT 5,
    expires_at      TIMESTAMPTZ     NULL,
    contact_name    VARCHAR(100)    NOT NULL DEFAULT '',
    contact_email   VARCHAR(200)    NOT NULL DEFAULT '',
    contact_phone   VARCHAR(30)     NOT NULL DEFAULT '',
    logo_url        VARCHAR(500)    NOT NULL DEFAULT '',
    config_json     TEXT            NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ     NULL
);
COMMENT ON TABLE iam.tenant IS '租户表 - 多租户隔离的顶层实体';
COMMENT ON COLUMN iam.tenant.status IS '租户状态: active/suspended/deleted';
COMMENT ON COLUMN iam.tenant.plan IS '套餐: free/pro/enterprise';

CREATE TABLE IF NOT EXISTS iam.organization (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    parent_id       VARCHAR(36)     NULL,
    name            VARCHAR(100)    NOT NULL,
    code            VARCHAR(50)     NOT NULL,
    org_type        VARCHAR(30)     NOT NULL DEFAULT 'company',
    path            VARCHAR(500)    NOT NULL DEFAULT '',
    level           INT             NOT NULL DEFAULT 1,
    sort_order      INT             NOT NULL DEFAULT 0,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    leader_id       VARCHAR(36)     NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ     NULL
);
COMMENT ON TABLE iam.organization IS '组织架构表 - 支持公司/部门/团队三级';
COMMENT ON COLUMN iam.organization.org_type IS '组织类型: company/department/team';
COMMENT ON COLUMN iam.organization.path IS '物化路径, 如 /root/child1/child2';

CREATE INDEX idx_org_tenant ON iam.organization(tenant_id);
CREATE INDEX idx_org_parent ON iam.organization(parent_id);

CREATE TABLE IF NOT EXISTS iam.user (
    id                  VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id           VARCHAR(36)     NOT NULL,
    org_id              VARCHAR(36)     NULL,
    username            VARCHAR(80)     NOT NULL,
    email               VARCHAR(200)    NOT NULL DEFAULT '',
    phone               VARCHAR(30)     NOT NULL DEFAULT '',
    password_hash       VARCHAR(200)    NOT NULL,
    display_name        VARCHAR(100)    NOT NULL DEFAULT '',
    avatar_url          VARCHAR(500)    NOT NULL DEFAULT '',
    status              VARCHAR(20)     NOT NULL DEFAULT 'active',
    user_type           VARCHAR(20)     NOT NULL DEFAULT 'internal',
    last_login_at       TIMESTAMPTZ     NULL,
    last_login_ip       VARCHAR(50)     NOT NULL DEFAULT '',
    login_fail_count    INT             NOT NULL DEFAULT 0,
    must_change_pwd     BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ     NULL,
    version             INT             NOT NULL DEFAULT 1
);
COMMENT ON TABLE iam.user IS '用户表 - 系统登录与操作主体';
COMMENT ON COLUMN iam.user.user_type IS '用户类型: internal/external';
COMMENT ON COLUMN iam.user.must_change_pwd IS '是否需要强制修改密码';

CREATE INDEX idx_user_tenant ON iam.user(tenant_id);
CREATE INDEX idx_user_org ON iam.user(org_id);
CREATE UNIQUE INDEX idx_user_tenant_username ON iam.user(tenant_id, username) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS iam.position (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    org_id          VARCHAR(36)     NOT NULL,
    name            VARCHAR(100)    NOT NULL,
    code            VARCHAR(50)     NOT NULL,
    level           INT             NOT NULL DEFAULT 1,
    sort_order      INT             NOT NULL DEFAULT 0,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ     NULL
);
COMMENT ON TABLE iam.position IS '岗位表 - V4新增，组织下的岗位管理';
COMMENT ON COLUMN iam.position.org_id IS '所属组织ID';
COMMENT ON COLUMN iam.position.name IS '岗位名称';
COMMENT ON COLUMN iam.position.code IS '岗位编码，租户内唯一';
COMMENT ON COLUMN iam.position.level IS '岗位层级，数字越大级别越高';
COMMENT ON COLUMN iam.position.sort_order IS '排序序号';
COMMENT ON COLUMN iam.position.status IS '状态: active/disabled';

CREATE INDEX idx_position_tenant ON iam.position(tenant_id);
CREATE INDEX idx_position_org ON iam.position(org_id);
CREATE UNIQUE INDEX idx_position_tenant_code ON iam.position(tenant_id, code) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS iam.user_position (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    user_id         VARCHAR(36)     NOT NULL,
    position_id     VARCHAR(36)     NOT NULL,
    is_primary      BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE iam.user_position IS '用户岗位关联表 - 一个用户可兼多岗';
COMMENT ON COLUMN iam.user_position.is_primary IS '是否主岗: true=主岗, false=兼职';

CREATE INDEX idx_userpos_tenant ON iam.user_position(tenant_id);
CREATE INDEX idx_userpos_user ON iam.user_position(user_id);
CREATE INDEX idx_userpos_position ON iam.user_position(position_id);

CREATE TABLE IF NOT EXISTS iam.role (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    name            VARCHAR(80)     NOT NULL,
    code            VARCHAR(80)     NOT NULL,
    description     VARCHAR(500)    NOT NULL DEFAULT '',
    role_type       VARCHAR(20)     NOT NULL DEFAULT 'custom',
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    sort_order      INT             NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ     NULL
);
COMMENT ON TABLE iam.role IS '角色表 - 功能权限载体';
COMMENT ON COLUMN iam.role.role_type IS '角色类型: system/custom';

CREATE INDEX idx_role_tenant ON iam.role(tenant_id);

CREATE TABLE IF NOT EXISTS iam.permission (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    parent_id       VARCHAR(36)     NULL,
    name            VARCHAR(100)    NOT NULL,
    code            VARCHAR(100)    NOT NULL UNIQUE,
    perm_type       VARCHAR(20)     NOT NULL,
    resource        VARCHAR(200)    NOT NULL DEFAULT '',
    action          VARCHAR(50)     NOT NULL DEFAULT '',
    path            VARCHAR(500)    NOT NULL DEFAULT '',
    level           INT             NOT NULL DEFAULT 1,
    sort_order      INT             NOT NULL DEFAULT 0,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    icon            VARCHAR(100)    NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE iam.permission IS '权限表 - 菜单/按钮/API/数据四级权限';
COMMENT ON COLUMN iam.permission.perm_type IS '权限类型: menu/button/api/data';
COMMENT ON COLUMN iam.permission.action IS '操作: read/write/delete/approve';

CREATE INDEX idx_perm_parent ON iam.permission(parent_id);

CREATE TABLE IF NOT EXISTS iam.user_role (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    user_id         VARCHAR(36)     NOT NULL,
    role_id         VARCHAR(36)     NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE iam.user_role IS '用户角色关联表';

CREATE INDEX idx_userrole_tenant ON iam.user_role(tenant_id);
CREATE INDEX idx_userrole_user ON iam.user_role(user_id);
CREATE INDEX idx_userrole_role ON iam.user_role(role_id);

CREATE TABLE IF NOT EXISTS iam.role_permission (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    role_id         VARCHAR(36)     NOT NULL,
    permission_id   VARCHAR(36)     NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE iam.role_permission IS '角色权限关联表';

CREATE INDEX idx_roleperm_role ON iam.role_permission(role_id);
CREATE INDEX idx_roleperm_perm ON iam.role_permission(permission_id);

CREATE TABLE IF NOT EXISTS iam.object_permission (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    subject_type    VARCHAR(20)     NOT NULL,
    subject_id      VARCHAR(36)     NOT NULL,
    resource_type   VARCHAR(50)     NOT NULL,
    resource_id     VARCHAR(36)     NOT NULL,
    action          VARCHAR(50)     NOT NULL DEFAULT 'read',
    effect          VARCHAR(20)     NOT NULL DEFAULT 'allow',
    conditions_json TEXT            NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE iam.object_permission IS '对象级权限表 - V4新增，支持行级权限控制';
COMMENT ON COLUMN iam.object_permission.subject_type IS '主体类型: user/role/position/org';
COMMENT ON COLUMN iam.object_permission.subject_id IS '主体ID';
COMMENT ON COLUMN iam.object_permission.resource_type IS '资源类型: order/product/customer/...';
COMMENT ON COLUMN iam.object_permission.resource_id IS '资源实例ID';
COMMENT ON COLUMN iam.object_permission.action IS '操作类型: read/write/delete/approve';
COMMENT ON COLUMN iam.object_permission.effect IS '效果: allow/deny';
COMMENT ON COLUMN iam.object_permission.conditions_json IS '附加条件JSON，用于动态权限判断';

CREATE INDEX idx_objperm_tenant ON iam.object_permission(tenant_id);
CREATE INDEX idx_objperm_subject ON iam.object_permission(subject_type, subject_id);
CREATE INDEX idx_objperm_resource ON iam.object_permission(resource_type, resource_id);

CREATE TABLE IF NOT EXISTS iam.data_permission_rule (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    role_id         VARCHAR(36)     NULL,
    user_id         VARCHAR(36)     NULL,
    dimension       VARCHAR(30)     NOT NULL,
    allowed_values_json TEXT        NOT NULL DEFAULT '[]',
    priority        INT             NOT NULL DEFAULT 0,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE iam.data_permission_rule IS '数据权限规则表 - 10维度数据隔离';
COMMENT ON COLUMN iam.data_permission_rule.dimension IS '维度: tenant/org/department/store/marketplace/channel/warehouse/supplier/category/data_level';
COMMENT ON COLUMN iam.data_permission_rule.allowed_values_json IS '允许值列表JSON，如["store_001","store_002"]';
COMMENT ON COLUMN iam.data_permission_rule.priority IS '优先级，数字越大优先级越高';
COMMENT ON COLUMN iam.data_permission_rule.status IS '状态: active/disabled';

CREATE INDEX idx_dataperm_tenant ON iam.data_permission_rule(tenant_id);
CREATE INDEX idx_dataperm_role ON iam.data_permission_rule(role_id);
CREATE INDEX idx_dataperm_user ON iam.data_permission_rule(user_id);

CREATE TABLE IF NOT EXISTS iam.audit_log (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    user_id         VARCHAR(36)     NOT NULL,
    user_name       VARCHAR(100)    NOT NULL DEFAULT '',
    action          VARCHAR(50)     NOT NULL,
    module          VARCHAR(50)     NOT NULL,
    target_type     VARCHAR(50)     NOT NULL,
    target_id       VARCHAR(36)     NOT NULL DEFAULT '',
    detail          TEXT            NOT NULL DEFAULT '',
    ip              VARCHAR(50)     NOT NULL DEFAULT '',
    trace_id        VARCHAR(36)     NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE iam.audit_log IS '审计日志表 - 全操作留痕';

CREATE INDEX idx_audit_tenant ON iam.audit_log(tenant_id);
CREATE INDEX idx_audit_user ON iam.audit_log(user_id);
CREATE INDEX idx_audit_module ON iam.audit_log(module);
CREATE INDEX idx_audit_created ON iam.audit_log(created_at);

-- ============================================================
-- 2. PDM域 - 产品开发域
-- 包含: 分类、品牌、SPU、SKU、渠道SKU映射、产品项目、质量标准、
--       知识产权、敏感词、UPC池、选品采集、组合产品(Bundle)、
--       标题库、图片库、产品问题记录
-- ============================================================

CREATE TABLE IF NOT EXISTS pdm.category (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    parent_id       VARCHAR(36)     NULL,
    name            VARCHAR(200)    NOT NULL,
    code            VARCHAR(100)    NOT NULL,
    path            VARCHAR(500)    NOT NULL DEFAULT '',
    level           INT             NOT NULL DEFAULT 1,
    sort_order      INT             NOT NULL DEFAULT 0,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ     NULL
);
COMMENT ON TABLE pdm.category IS '产品分类表 - 支持多级树形结构';

CREATE INDEX idx_cat_tenant ON pdm.category(tenant_id);
CREATE INDEX idx_cat_parent ON pdm.category(parent_id);

CREATE TABLE IF NOT EXISTS pdm.brand (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    name            VARCHAR(200)    NOT NULL,
    name_en         VARCHAR(200)    NOT NULL DEFAULT '',
    code            VARCHAR(100)    NOT NULL,
    logo_url        VARCHAR(500)    NOT NULL DEFAULT '',
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ     NULL
);
COMMENT ON TABLE pdm.brand IS '品牌表';

CREATE INDEX idx_brand_tenant ON pdm.brand(tenant_id);

CREATE TABLE IF NOT EXISTS pdm.spu (
    id                  VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id           VARCHAR(36)     NOT NULL,
    name                VARCHAR(500)    NOT NULL,
    name_en             VARCHAR(500)    NOT NULL DEFAULT '',
    code                VARCHAR(100)    NOT NULL UNIQUE,
    category_id         VARCHAR(36)     NULL,
    brand_id            VARCHAR(36)     NULL,
    description         TEXT            NOT NULL DEFAULT '',
    description_en      TEXT            NOT NULL DEFAULT '',
    main_image          VARCHAR(500)    NOT NULL DEFAULT '',
    images_json         TEXT            NOT NULL DEFAULT '[]',
    attributes_json     TEXT            NOT NULL DEFAULT '{}',
    status              VARCHAR(20)     NOT NULL DEFAULT 'draft',
    spu_type            VARCHAR(30)     NOT NULL DEFAULT 'normal',
    origin_country      VARCHAR(50)     NOT NULL DEFAULT '',
    hs_code             VARCHAR(30)     NOT NULL DEFAULT '',
    declared_value      FLOAT           NOT NULL DEFAULT 0.0,
    declared_currency   VARCHAR(10)     NOT NULL DEFAULT 'CNY',
    created_by          VARCHAR(36)     NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ     NULL,
    version             INT             NOT NULL DEFAULT 1
);
COMMENT ON TABLE pdm.spu IS '标准产品单元表 - 产品主数据';
COMMENT ON COLUMN pdm.spu.spu_type IS 'SPU类型: normal/bundle/composite';

CREATE INDEX idx_spu_tenant ON pdm.spu(tenant_id);
CREATE INDEX idx_spu_category ON pdm.spu(category_id);
CREATE INDEX idx_spu_brand ON pdm.spu(brand_id);
CREATE INDEX idx_spu_status ON pdm.spu(status);

CREATE TABLE IF NOT EXISTS pdm.sku (
    id                  VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id           VARCHAR(36)     NOT NULL,
    spu_id              VARCHAR(36)     NOT NULL,
    sku_code            VARCHAR(100)    NOT NULL,
    barcode             VARCHAR(50)     NOT NULL DEFAULT '',
    name                VARCHAR(500)    NOT NULL DEFAULT '',
    variant_attrs_json  TEXT            NOT NULL DEFAULT '{}',
    spec_json           TEXT            NOT NULL DEFAULT '{}',
    weight              FLOAT           NOT NULL DEFAULT 0.0,
    length              FLOAT           NOT NULL DEFAULT 0.0,
    width               FLOAT           NOT NULL DEFAULT 0.0,
    height              FLOAT           NOT NULL DEFAULT 0.0,
    cost_price          FLOAT           NOT NULL DEFAULT 0.0,
    cost_currency       VARCHAR(10)     NOT NULL DEFAULT 'CNY',
    purchase_price      FLOAT           NOT NULL DEFAULT 0.0,
    supplier_id         VARCHAR(36)     NULL,
    status              VARCHAR(20)     NOT NULL DEFAULT 'active',
    image               VARCHAR(500)    NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ     NULL,
    version             INT             NOT NULL DEFAULT 1
);
COMMENT ON TABLE pdm.sku IS '库存单元表 - 最小可售单元';
COMMENT ON COLUMN pdm.sku.weight IS '重量(kg)';
COMMENT ON COLUMN pdm.sku.length IS '长度(cm)';

CREATE INDEX idx_sku_tenant ON pdm.sku(tenant_id);
CREATE INDEX idx_sku_spu ON pdm.sku(spu_id);
CREATE INDEX idx_sku_code ON pdm.sku(sku_code);

CREATE TABLE IF NOT EXISTS pdm.channel_sku_mapping (
    id                  VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id           VARCHAR(36)     NOT NULL,
    sku_id              VARCHAR(36)     NOT NULL,
    channel             VARCHAR(50)     NOT NULL,
    channel_sku         VARCHAR(200)    NOT NULL,
    channel_product_id  VARCHAR(200)    NOT NULL DEFAULT '',
    store_id            VARCHAR(36)     NOT NULL DEFAULT '',
    status              VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE pdm.channel_sku_mapping IS '渠道SKU映射表 - 内部SKU与平台SKU的对应关系';

CREATE INDEX idx_chskumap_tenant ON pdm.channel_sku_mapping(tenant_id);
CREATE INDEX idx_chskumap_sku ON pdm.channel_sku_mapping(sku_id);
CREATE INDEX idx_chskumap_channel ON pdm.channel_sku_mapping(channel);

CREATE TABLE IF NOT EXISTS pdm.product_project (
    id                  VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id           VARCHAR(36)     NOT NULL,
    name                VARCHAR(500)    NOT NULL,
    code                VARCHAR(100)    NOT NULL,
    category_id         VARCHAR(36)     NULL,
    stage               VARCHAR(30)     NOT NULL DEFAULT 'proposing',
    priority            VARCHAR(20)     NOT NULL DEFAULT 'medium',
    owner_id            VARCHAR(36)     NOT NULL DEFAULT '',
    team_json           TEXT            NOT NULL DEFAULT '[]',
    target_market       VARCHAR(200)    NOT NULL DEFAULT '',
    target_platform     VARCHAR(200)    NOT NULL DEFAULT '',
    research_json       TEXT            NOT NULL DEFAULT '{}',
    status              VARCHAR(20)     NOT NULL DEFAULT 'draft',
    approval_instance_id VARCHAR(36)    NOT NULL DEFAULT '',
    recommendation_id   VARCHAR(36)     NOT NULL DEFAULT '',
    spu_id              VARCHAR(36)     NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ     NULL
);
COMMENT ON TABLE pdm.product_project IS '产品开发项目表 - 从选品到上架全流程';
COMMENT ON COLUMN pdm.product_project.stage IS '阶段: proposing/researching/designing/sourcing/sampling/producing/listing';

CREATE INDEX idx_proj_tenant ON pdm.product_project(tenant_id);
CREATE INDEX idx_proj_status ON pdm.product_project(status);

CREATE TABLE IF NOT EXISTS pdm.bundle_product (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    spu_id          VARCHAR(36)     NOT NULL,
    component_sku_id VARCHAR(36)   NOT NULL,
    quantity        INT             NOT NULL DEFAULT 1,
    discount_pct    FLOAT           NOT NULL DEFAULT 0.0,
    sort_order      INT             NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE pdm.bundle_product IS '组合产品(Bundle)明细表 - V4新增';
COMMENT ON COLUMN pdm.bundle_product.spu_id IS '组合产品SPU ID';
COMMENT ON COLUMN pdm.bundle_product.component_sku_id IS '子组件SKU ID';
COMMENT ON COLUMN pdm.bundle_product.quantity IS '子组件数量';
COMMENT ON COLUMN pdm.bundle_product.discount_pct IS '组合折扣百分比，0-100';
COMMENT ON COLUMN pdm.bundle_product.sort_order IS '排序序号';

CREATE INDEX idx_bundle_tenant ON pdm.bundle_product(tenant_id);
CREATE INDEX idx_bundle_spu ON pdm.bundle_product(spu_id);

CREATE TABLE IF NOT EXISTS pdm.title_library (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    category_id     VARCHAR(36)     NULL,
    platform        VARCHAR(50)     NOT NULL DEFAULT '',
    language        VARCHAR(10)     NOT NULL DEFAULT 'en',
    title           VARCHAR(1000)   NOT NULL,
    keywords_json   TEXT            NOT NULL DEFAULT '[]',
    usage_count     INT             NOT NULL DEFAULT 0,
    score           FLOAT           NOT NULL DEFAULT 0.0,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_by      VARCHAR(36)     NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE pdm.title_library IS '标题库 - V4新增，Listing标题模板与优化参考';
COMMENT ON COLUMN pdm.title_library.platform IS '适用平台: amazon/shopify/ebay/...';
COMMENT ON COLUMN pdm.title_library.language IS '语言: en/de/fr/es/ja/...';
COMMENT ON COLUMN pdm.title_library.keywords_json IS '关键词列表JSON';
COMMENT ON COLUMN pdm.title_library.usage_count IS '使用次数';
COMMENT ON COLUMN pdm.title_library.score IS 'SEO评分';

CREATE INDEX idx_titlelib_tenant ON pdm.title_library(tenant_id);
CREATE INDEX idx_titlelib_category ON pdm.title_library(category_id);

CREATE TABLE IF NOT EXISTS pdm.image_library (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    sku_id          VARCHAR(36)     NULL,
    spu_id          VARCHAR(36)     NULL,
    image_type      VARCHAR(30)     NOT NULL DEFAULT 'main',
    url             VARCHAR(1000)   NOT NULL,
    thumbnail_url   VARCHAR(1000)   NOT NULL DEFAULT '',
    alt_text        VARCHAR(500)    NOT NULL DEFAULT '',
    tags_json       TEXT            NOT NULL DEFAULT '[]',
    platform        VARCHAR(50)     NOT NULL DEFAULT '',
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_by      VARCHAR(36)     NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE pdm.image_library IS '图片库 - V4新增，产品图片统一管理';
COMMENT ON COLUMN pdm.image_library.image_type IS '图片类型: main/detail/lifestyle/infographic/size_chart';
COMMENT ON COLUMN pdm.image_library.url IS '图片URL';
COMMENT ON COLUMN pdm.image_library.thumbnail_url IS '缩略图URL';
COMMENT ON COLUMN pdm.image_library.tags_json IS '标签列表JSON';

CREATE INDEX idx_imglib_tenant ON pdm.image_library(tenant_id);
CREATE INDEX idx_imglib_sku ON pdm.image_library(sku_id);

CREATE TABLE IF NOT EXISTS pdm.product_issue (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    sku_id          VARCHAR(36)     NULL,
    spu_id          VARCHAR(36)     NULL,
    issue_type      VARCHAR(50)     NOT NULL,
    severity        VARCHAR(20)     NOT NULL DEFAULT 'medium',
    description     TEXT            NOT NULL DEFAULT '',
    evidence_json   TEXT            NOT NULL DEFAULT '[]',
    status          VARCHAR(20)     NOT NULL DEFAULT 'open',
    assigned_to     VARCHAR(36)     NOT NULL DEFAULT '',
    resolution      TEXT            NOT NULL DEFAULT '',
    resolved_at     TIMESTAMPTZ     NULL,
    created_by      VARCHAR(36)     NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE pdm.product_issue IS '产品问题记录表 - V4新增，质量问题跟踪';
COMMENT ON COLUMN pdm.product_issue.issue_type IS '问题类型: quality/packaging/labeling/safety/compliance';
COMMENT ON COLUMN pdm.product_issue.severity IS '严重程度: critical/high/medium/low';
COMMENT ON COLUMN pdm.product_issue.status IS '状态: open/in_progress/resolved/closed';
COMMENT ON COLUMN pdm.product_issue.assigned_to IS '处理人ID';
COMMENT ON COLUMN pdm.product_issue.resolution IS '解决方案';

CREATE INDEX idx_prodissue_tenant ON pdm.product_issue(tenant_id);
CREATE INDEX idx_prodissue_sku ON pdm.product_issue(sku_id);
CREATE INDEX idx_prodissue_status ON pdm.product_issue(status);

CREATE TABLE IF NOT EXISTS pdm.quality_standard (
    id                  VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id           VARCHAR(36)     NOT NULL,
    category_id         VARCHAR(36)     NULL,
    name                VARCHAR(200)    NOT NULL,
    standard_type       VARCHAR(50)     NOT NULL DEFAULT 'general',
    items_json          TEXT            NOT NULL DEFAULT '[]',
    logistics_attrs_json TEXT           NOT NULL DEFAULT '{}',
    packaging_cost      FLOAT           NOT NULL DEFAULT 0.0,
    status              VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE pdm.quality_standard IS '质量标准表';

CREATE TABLE IF NOT EXISTS pdm.ip_record (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    sku_id          VARCHAR(36)     NULL,
    spu_id          VARCHAR(36)     NULL,
    ip_type         VARCHAR(30)     NOT NULL,
    ip_number       VARCHAR(100)    NOT NULL DEFAULT '',
    ip_name         VARCHAR(200)    NOT NULL DEFAULT '',
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    risk_level      VARCHAR(20)     NOT NULL DEFAULT 'none',
    notes           TEXT            NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE pdm.ip_record IS '知识产权记录表';
COMMENT ON COLUMN pdm.ip_record.ip_type IS 'IP类型: trademark/patent/copyright';

CREATE INDEX idx_iprecord_tenant ON pdm.ip_record(tenant_id);
CREATE INDEX idx_iprecord_sku ON pdm.ip_record(sku_id);

CREATE TABLE IF NOT EXISTS pdm.sensitive_word (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    word            VARCHAR(200)    NOT NULL,
    word_type       VARCHAR(30)     NOT NULL DEFAULT 'general',
    language        VARCHAR(10)     NOT NULL DEFAULT 'en',
    platform        VARCHAR(50)     NOT NULL DEFAULT '',
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE pdm.sensitive_word IS '敏感词表';
COMMENT ON COLUMN pdm.sensitive_word.word_type IS '类型: general/trademark/prohibited';

CREATE TABLE IF NOT EXISTS pdm.upc_pool (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    upc_code        VARCHAR(50)     NOT NULL UNIQUE,
    sku_id          VARCHAR(36)     NULL,
    status          VARCHAR(20)     NOT NULL DEFAULT 'available',
    allocated_at    TIMESTAMPTZ     NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE pdm.upc_pool IS 'UPC条码池';

CREATE INDEX idx_upc_tenant ON pdm.upc_pool(tenant_id);
CREATE INDEX idx_upc_status ON pdm.upc_pool(status);

CREATE TABLE IF NOT EXISTS pdm.product_collection (
    id                  VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id           VARCHAR(36)     NOT NULL,
    source_platform     VARCHAR(50)     NOT NULL DEFAULT '',
    source_url          VARCHAR(1000)   NOT NULL DEFAULT '',
    source_product_id   VARCHAR(200)    NOT NULL DEFAULT '',
    title               VARCHAR(500)    NOT NULL DEFAULT '',
    title_en            VARCHAR(500)    NOT NULL DEFAULT '',
    main_image          VARCHAR(500)    NOT NULL DEFAULT '',
    images_json         TEXT            NOT NULL DEFAULT '[]',
    price               FLOAT           NOT NULL DEFAULT 0.0,
    currency            VARCHAR(10)     NOT NULL DEFAULT 'USD',
    category_name       VARCHAR(200)    NOT NULL DEFAULT '',
    attributes_json     TEXT            NOT NULL DEFAULT '{}',
    variants_json       TEXT            NOT NULL DEFAULT '[]',
    seller_info_json    TEXT            NOT NULL DEFAULT '{}',
    sales_data_json     TEXT            NOT NULL DEFAULT '{}',
    review_data_json    TEXT            NOT NULL DEFAULT '{}',
    status              VARCHAR(20)     NOT NULL DEFAULT 'collected',
    collection_type     VARCHAR(30)     NOT NULL DEFAULT 'manual',
    tags_json           TEXT            NOT NULL DEFAULT '[]',
    score               FLOAT           NOT NULL DEFAULT 0.0,
    converted_spu_id    VARCHAR(36)     NULL,
    collected_by        VARCHAR(36)     NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE pdm.product_collection IS '选品采集表 - 竞品/货源采集';
COMMENT ON COLUMN pdm.product_collection.collection_type IS '采集方式: manual/keyword/category_url/monitor';

CREATE INDEX idx_collect_tenant ON pdm.product_collection(tenant_id);
CREATE INDEX idx_collect_status ON pdm.product_collection(status);

-- ============================================================
-- 3. SOM域 - 销售运营域
-- ============================================================

CREATE TABLE IF NOT EXISTS som.store (
    id                      VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id               VARCHAR(36)     NOT NULL,
    name                    VARCHAR(200)    NOT NULL,
    code                    VARCHAR(100)    NOT NULL,
    platform                VARCHAR(50)     NOT NULL,
    region                  VARCHAR(50)     NOT NULL DEFAULT '',
    store_id_on_platform    VARCHAR(200)    NOT NULL DEFAULT '',
    seller_id               VARCHAR(200)    NOT NULL DEFAULT '',
    currency                VARCHAR(10)     NOT NULL DEFAULT 'USD',
    status                  VARCHAR(20)     NOT NULL DEFAULT 'active',
    auth_status             VARCHAR(20)     NOT NULL DEFAULT 'unauthorized',
    auth_token_encrypted    TEXT            NOT NULL DEFAULT '',
    auth_expires_at         TIMESTAMPTZ     NULL,
    org_id                  VARCHAR(36)     NULL,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at              TIMESTAMPTZ     NULL
);
COMMENT ON TABLE som.store IS '店铺表 - 跨境电商平台店铺';

CREATE INDEX idx_store_tenant ON som.store(tenant_id);
CREATE INDEX idx_store_platform ON som.store(platform);

CREATE TABLE IF NOT EXISTS som.listing (
    id                      VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id               VARCHAR(36)     NOT NULL,
    store_id                VARCHAR(36)     NOT NULL,
    sku_id                  VARCHAR(36)     NOT NULL,
    channel_sku             VARCHAR(200)    NOT NULL DEFAULT '',
    platform_listing_id     VARCHAR(200)    NOT NULL DEFAULT '',
    title                   VARCHAR(1000)   NOT NULL DEFAULT '',
    title_en                VARCHAR(1000)   NOT NULL DEFAULT '',
    description             TEXT            NOT NULL DEFAULT '',
    bullet_points_json      TEXT            NOT NULL DEFAULT '[]',
    search_terms            VARCHAR(500)    NOT NULL DEFAULT '',
    main_image              VARCHAR(500)    NOT NULL DEFAULT '',
    images_json             TEXT            NOT NULL DEFAULT '[]',
    price                   FLOAT           NOT NULL DEFAULT 0.0,
    currency                VARCHAR(10)     NOT NULL DEFAULT 'USD',
    msrp                    FLOAT           NOT NULL DEFAULT 0.0,
    sale_price              FLOAT           NOT NULL DEFAULT 0.0,
    sale_start              TIMESTAMPTZ     NULL,
    sale_end                TIMESTAMPTZ     NULL,
    quantity                INT             NOT NULL DEFAULT 0,
    status                  VARCHAR(20)     NOT NULL DEFAULT 'draft',
    listing_status          VARCHAR(30)     NOT NULL DEFAULT 'not_listed',
    platform                VARCHAR(50)     NOT NULL DEFAULT '',
    category_id             VARCHAR(36)     NULL,
    is_pms_draft            BOOLEAN         NOT NULL DEFAULT FALSE,
    recommendation_id       VARCHAR(36)     NOT NULL DEFAULT '',
    approval_instance_id    VARCHAR(36)     NOT NULL DEFAULT '',
    published_at            TIMESTAMPTZ     NULL,
    created_by              VARCHAR(36)     NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at              TIMESTAMPTZ     NULL,
    version                 INT             NOT NULL DEFAULT 1
);
COMMENT ON TABLE som.listing IS 'Listing表 - 平台商品刊登';

CREATE INDEX idx_listing_tenant ON som.listing(tenant_id);
CREATE INDEX idx_listing_store ON som.listing(store_id);
CREATE INDEX idx_listing_sku ON som.listing(sku_id);
CREATE INDEX idx_listing_status ON som.listing(status);

CREATE TABLE IF NOT EXISTS som.price_rule (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    name            VARCHAR(200)    NOT NULL,
    rule_type       VARCHAR(50)     NOT NULL,
    platform        VARCHAR(50)     NOT NULL DEFAULT '',
    region          VARCHAR(50)     NOT NULL DEFAULT '',
    category_id     VARCHAR(36)     NULL,
    formula_json    TEXT            NOT NULL DEFAULT '{}',
    min_price       FLOAT           NOT NULL DEFAULT 0.0,
    max_price       FLOAT           NOT NULL DEFAULT 0.0,
    currency        VARCHAR(10)     NOT NULL DEFAULT 'USD',
    priority        INT             NOT NULL DEFAULT 0,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE som.price_rule IS '价格规则表';
COMMENT ON COLUMN som.price_rule.rule_type IS '规则类型: markup/markdown/fixed/competitive';

CREATE TABLE IF NOT EXISTS som.listing_batch_job (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    job_type        VARCHAR(50)     NOT NULL,
    total_count     INT             NOT NULL DEFAULT 0,
    success_count   INT             NOT NULL DEFAULT 0,
    fail_count      INT             NOT NULL DEFAULT 0,
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending',
    result_json     TEXT            NOT NULL DEFAULT '{}',
    created_by      VARCHAR(36)     NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE som.listing_batch_job IS 'Listing批量任务表';

CREATE TABLE IF NOT EXISTS som.operation_monitor (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    store_id        VARCHAR(36)     NOT NULL,
    metric_type     VARCHAR(50)     NOT NULL,
    metric_date     TIMESTAMPTZ     NOT NULL,
    metrics_json    TEXT            NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE som.operation_monitor IS '运营监控数据表';

CREATE INDEX idx_opmonitor_tenant ON som.operation_monitor(tenant_id);
CREATE INDEX idx_opmonitor_store_date ON som.operation_monitor(store_id, metric_date);

CREATE TABLE IF NOT EXISTS som.listing_optimization (
    id                      VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id               VARCHAR(36)     NOT NULL,
    listing_id              VARCHAR(36)     NOT NULL,
    store_id                VARCHAR(36)     NOT NULL,
    opt_type                VARCHAR(30)     NOT NULL,
    status                  VARCHAR(20)     NOT NULL DEFAULT 'pending',
    score_before            FLOAT           NOT NULL DEFAULT 0.0,
    score_after             FLOAT           NOT NULL DEFAULT 0.0,
    suggestions_json        TEXT            NOT NULL DEFAULT '[]',
    applied_suggestions_json TEXT           NOT NULL DEFAULT '[]',
    snapshot_before_json    TEXT            NOT NULL DEFAULT '{}',
    snapshot_after_json     TEXT            NOT NULL DEFAULT '{}',
    created_by              VARCHAR(36)     NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE som.listing_optimization IS 'Listing优化记录表';

CREATE TABLE IF NOT EXISTS som.alert_rule (
    id                  VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id           VARCHAR(36)     NOT NULL,
    name                VARCHAR(200)    NOT NULL,
    metric_type         VARCHAR(50)     NOT NULL,
    condition_type      VARCHAR(30)     NOT NULL,
    threshold           FLOAT           NOT NULL DEFAULT 0.0,
    threshold_max       FLOAT           NOT NULL DEFAULT 0.0,
    time_window         INT             NOT NULL DEFAULT 1,
    severity            VARCHAR(20)     NOT NULL DEFAULT 'warning',
    notify_channels     VARCHAR(200)    NOT NULL DEFAULT 'email',
    notify_targets_json TEXT            NOT NULL DEFAULT '[]',
    platform            VARCHAR(50)     NOT NULL DEFAULT '',
    store_id            VARCHAR(36)     NOT NULL DEFAULT '',
    cooldown_minutes    INT             NOT NULL DEFAULT 60,
    status              VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_by          VARCHAR(36)     NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE som.alert_rule IS '告警规则表';

CREATE TABLE IF NOT EXISTS som.alert_record (
    id                  VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id           VARCHAR(36)     NOT NULL,
    rule_id             VARCHAR(36)     NOT NULL,
    rule_name           VARCHAR(200)    NOT NULL DEFAULT '',
    store_id            VARCHAR(36)     NOT NULL DEFAULT '',
    metric_type         VARCHAR(50)     NOT NULL,
    severity            VARCHAR(20)     NOT NULL DEFAULT 'warning',
    actual_value        FLOAT           NOT NULL DEFAULT 0.0,
    threshold_value     FLOAT           NOT NULL DEFAULT 0.0,
    message             VARCHAR(1000)   NOT NULL DEFAULT '',
    detail_json         TEXT            NOT NULL DEFAULT '{}',
    status              VARCHAR(20)     NOT NULL DEFAULT 'firing',
    notified            BOOLEAN         NOT NULL DEFAULT FALSE,
    notified_at         TIMESTAMPTZ     NULL,
    acknowledged_by     VARCHAR(36)     NOT NULL DEFAULT '',
    acknowledged_at     TIMESTAMPTZ     NULL,
    resolved_at         TIMESTAMPTZ     NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE som.alert_record IS '告警记录表';
COMMENT ON COLUMN som.alert_record.status IS '状态: firing/acknowledged/resolved';

-- ============================================================
-- 4. ADS域 - 广告管理域
-- ============================================================

CREATE TABLE IF NOT EXISTS ads.ad_campaign (
    id                      VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id               VARCHAR(36)     NOT NULL,
    campaign_no             VARCHAR(100)    NOT NULL UNIQUE,
    name                    VARCHAR(500)    NOT NULL,
    platform                VARCHAR(50)     NOT NULL,
    store_id                VARCHAR(36)     NOT NULL,
    campaign_type           VARCHAR(30)     NOT NULL DEFAULT 'sponsored_products',
    targeting_type          VARCHAR(30)     NOT NULL DEFAULT 'manual',
    status                  VARCHAR(20)     NOT NULL DEFAULT 'draft',
    daily_budget            FLOAT           NOT NULL DEFAULT 0.0,
    currency                VARCHAR(10)     NOT NULL DEFAULT 'USD',
    start_date              TIMESTAMPTZ     NULL,
    end_date                TIMESTAMPTZ     NULL,
    total_spend             FLOAT           NOT NULL DEFAULT 0.0,
    total_sales             FLOAT           NOT NULL DEFAULT 0.0,
    total_impressions       INT             NOT NULL DEFAULT 0,
    total_clicks            INT             NOT NULL DEFAULT 0,
    total_orders            INT             NOT NULL DEFAULT 0,
    acos                    FLOAT           NOT NULL DEFAULT 0.0,
    roas                    FLOAT           NOT NULL DEFAULT 0.0,
    platform_campaign_id    VARCHAR(200)    NOT NULL DEFAULT '',
    is_pms_draft            BOOLEAN         NOT NULL DEFAULT FALSE,
    recommendation_id       VARCHAR(36)     NOT NULL DEFAULT '',
    approval_instance_id    VARCHAR(36)     NOT NULL DEFAULT '',
    created_by              VARCHAR(36)     NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at              TIMESTAMPTZ     NULL
);
COMMENT ON TABLE ads.ad_campaign IS '广告活动表';

CREATE INDEX idx_adcamp_tenant ON ads.ad_campaign(tenant_id);
CREATE INDEX idx_adcamp_store ON ads.ad_campaign(store_id);
CREATE INDEX idx_adcamp_status ON ads.ad_campaign(status);

CREATE TABLE IF NOT EXISTS ads.ad_group (
    id                      VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id               VARCHAR(36)     NOT NULL,
    campaign_id             VARCHAR(36)     NOT NULL,
    name                    VARCHAR(500)    NOT NULL,
    default_bid             FLOAT           NOT NULL DEFAULT 0.0,
    status                  VARCHAR(20)     NOT NULL DEFAULT 'enabled',
    sku_id                  VARCHAR(36)     NOT NULL DEFAULT '',
    listing_id              VARCHAR(36)     NOT NULL DEFAULT '',
    platform_ad_group_id    VARCHAR(200)    NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE ads.ad_group IS '广告组表';

CREATE INDEX idx_adgroup_tenant ON ads.ad_group(tenant_id);
CREATE INDEX idx_adgroup_campaign ON ads.ad_group(campaign_id);

CREATE TABLE IF NOT EXISTS ads.ad_keyword (
    id                      VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id               VARCHAR(36)     NOT NULL,
    campaign_id             VARCHAR(36)     NOT NULL,
    ad_group_id             VARCHAR(36)     NOT NULL,
    keyword_text            VARCHAR(500)    NOT NULL,
    match_type              VARCHAR(20)     NOT NULL DEFAULT 'broad',
    bid                     FLOAT           NOT NULL DEFAULT 0.0,
    status                  VARCHAR(20)     NOT NULL DEFAULT 'enabled',
    impressions             INT             NOT NULL DEFAULT 0,
    clicks                  INT             NOT NULL DEFAULT 0,
    spend                   FLOAT           NOT NULL DEFAULT 0.0,
    sales                   FLOAT           NOT NULL DEFAULT 0.0,
    orders                  INT             NOT NULL DEFAULT 0,
    ctr                     FLOAT           NOT NULL DEFAULT 0.0,
    cpc                     FLOAT           NOT NULL DEFAULT 0.0,
    conversion_rate         FLOAT           NOT NULL DEFAULT 0.0,
    platform_keyword_id     VARCHAR(200)    NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE ads.ad_keyword IS '广告关键词表';
COMMENT ON COLUMN ads.ad_keyword.match_type IS '匹配类型: broad/phrase/exact';

CREATE INDEX idx_adkw_tenant ON ads.ad_keyword(tenant_id);
CREATE INDEX idx_adkw_campaign ON ads.ad_keyword(campaign_id);

CREATE TABLE IF NOT EXISTS ads.ad_report (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    campaign_id     VARCHAR(36)     NOT NULL,
    report_date     TIMESTAMPTZ     NOT NULL,
    granularity     VARCHAR(20)     NOT NULL DEFAULT 'daily',
    impressions     INT             NOT NULL DEFAULT 0,
    clicks          INT             NOT NULL DEFAULT 0,
    spend           FLOAT           NOT NULL DEFAULT 0.0,
    sales           FLOAT           NOT NULL DEFAULT 0.0,
    orders          INT             NOT NULL DEFAULT 0,
    units           INT             NOT NULL DEFAULT 0,
    ctr             FLOAT           NOT NULL DEFAULT 0.0,
    cpc             FLOAT           NOT NULL DEFAULT 0.0,
    acos            FLOAT           NOT NULL DEFAULT 0.0,
    roas            FLOAT           NOT NULL DEFAULT 0.0,
    currency        VARCHAR(10)     NOT NULL DEFAULT 'USD',
    store_id        VARCHAR(36)     NOT NULL DEFAULT '',
    platform        VARCHAR(50)     NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE ads.ad_report IS '广告报表数据表';

CREATE INDEX idx_adrpt_tenant ON ads.ad_report(tenant_id);
CREATE INDEX idx_adrpt_date ON ads.ad_report(report_date);

-- ============================================================
-- 5. OMS域 - 订单域
-- ============================================================

CREATE TABLE IF NOT EXISTS oms.sales_order (
    id                  VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id           VARCHAR(36)     NOT NULL,
    order_no            VARCHAR(100)    NOT NULL UNIQUE,
    platform            VARCHAR(50)     NOT NULL,
    store_id            VARCHAR(36)     NOT NULL,
    platform_order_id   VARCHAR(200)    NOT NULL DEFAULT '',
    order_type          VARCHAR(30)     NOT NULL DEFAULT 'standard',
    status              VARCHAR(30)     NOT NULL DEFAULT 'pending',
    order_time          TIMESTAMPTZ     NULL,
    pay_time            TIMESTAMPTZ     NULL,
    ship_time           TIMESTAMPTZ     NULL,
    complete_time       TIMESTAMPTZ     NULL,
    buyer_id            VARCHAR(200)    NOT NULL DEFAULT '',
    buyer_name          VARCHAR(200)    NOT NULL DEFAULT '',
    recipient_name      VARCHAR(200)    NOT NULL DEFAULT '',
    recipient_phone     VARCHAR(50)     NOT NULL DEFAULT '',
    recipient_address   TEXT            NOT NULL DEFAULT '',
    recipient_city      VARCHAR(100)    NOT NULL DEFAULT '',
    recipient_state     VARCHAR(100)    NOT NULL DEFAULT '',
    recipient_country   VARCHAR(50)     NOT NULL DEFAULT '',
    recipient_zip       VARCHAR(30)     NOT NULL DEFAULT '',
    currency            VARCHAR(10)     NOT NULL DEFAULT 'USD',
    item_subtotal       FLOAT           NOT NULL DEFAULT 0.0,
    shipping_fee        FLOAT           NOT NULL DEFAULT 0.0,
    discount_amount     FLOAT           NOT NULL DEFAULT 0.0,
    tax_amount          FLOAT           NOT NULL DEFAULT 0.0,
    total_amount        FLOAT           NOT NULL DEFAULT 0.0,
    settlement_amount   FLOAT           NOT NULL DEFAULT 0.0,
    warehouse_id        VARCHAR(36)     NULL,
    logistics_channel   VARCHAR(100)    NOT NULL DEFAULT '',
    tracking_no         VARCHAR(100)    NOT NULL DEFAULT '',
    is_split            BOOLEAN         NOT NULL DEFAULT FALSE,
    parent_order_id     VARCHAR(36)     NULL,
    is_merged           BOOLEAN         NOT NULL DEFAULT FALSE,
    merged_into_id      VARCHAR(36)     NULL,
    remark              TEXT            NOT NULL DEFAULT '',
    tags_json           TEXT            NOT NULL DEFAULT '[]',
    risk_flags_json     TEXT            NOT NULL DEFAULT '[]',
    raw_data_json       TEXT            NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ     NULL,
    version             INT             NOT NULL DEFAULT 1
);
COMMENT ON TABLE oms.sales_order IS '销售订单表';
COMMENT ON COLUMN oms.sales_order.order_type IS '订单类型: standard/refund/exchange';

CREATE INDEX idx_order_tenant ON oms.sales_order(tenant_id);
CREATE INDEX idx_order_no ON oms.sales_order(order_no);
CREATE INDEX idx_order_store_status ON oms.sales_order(store_id, status);

CREATE TABLE IF NOT EXISTS oms.sales_order_item (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    order_id        VARCHAR(36)     NOT NULL,
    sku_id          VARCHAR(36)     NOT NULL,
    channel_sku     VARCHAR(200)    NOT NULL DEFAULT '',
    product_name    VARCHAR(500)    NOT NULL DEFAULT '',
    quantity        INT             NOT NULL DEFAULT 1,
    unit_price      FLOAT           NOT NULL DEFAULT 0.0,
    discount_amount FLOAT           NOT NULL DEFAULT 0.0,
    item_total      FLOAT           NOT NULL DEFAULT 0.0,
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending',
    platform_item_id VARCHAR(200)   NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE oms.sales_order_item IS '订单明细表';

CREATE INDEX idx_orderitem_tenant ON oms.sales_order_item(tenant_id);
CREATE INDEX idx_orderitem_order ON oms.sales_order_item(order_id);

CREATE TABLE IF NOT EXISTS oms.refund_order (
    id                      VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id               VARCHAR(36)     NOT NULL,
    refund_no               VARCHAR(100)    NOT NULL UNIQUE,
    original_order_id       VARCHAR(36)     NOT NULL,
    refund_type             VARCHAR(30)     NOT NULL,
    reason                  VARCHAR(500)    NOT NULL DEFAULT '',
    status                  VARCHAR(20)     NOT NULL DEFAULT 'pending',
    refund_amount           FLOAT           NOT NULL DEFAULT 0.0,
    currency                VARCHAR(10)     NOT NULL DEFAULT 'USD',
    platform_refund_id      VARCHAR(200)    NOT NULL DEFAULT '',
    items_json              TEXT            NOT NULL DEFAULT '[]',
    approval_instance_id    VARCHAR(36)     NOT NULL DEFAULT '',
    processed_at            TIMESTAMPTZ     NULL,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE oms.refund_order IS '退款单表';
COMMENT ON COLUMN oms.refund_order.refund_type IS '退款类型: refund_only/return_refund/exchange';

CREATE INDEX idx_refund_tenant ON oms.refund_order(tenant_id);
CREATE INDEX idx_refund_order ON oms.refund_order(original_order_id);

CREATE TABLE IF NOT EXISTS oms.promotion (
    id                          VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id                   VARCHAR(36)     NOT NULL,
    promo_no                    VARCHAR(100)    NOT NULL UNIQUE,
    name                        VARCHAR(500)    NOT NULL,
    promo_type                  VARCHAR(30)     NOT NULL,
    status                      VARCHAR(20)     NOT NULL DEFAULT 'draft',
    platform                    VARCHAR(50)     NOT NULL DEFAULT '',
    store_id                    VARCHAR(36)     NOT NULL DEFAULT '',
    start_time                  TIMESTAMPTZ     NULL,
    end_time                    TIMESTAMPTZ     NULL,
    discount_type               VARCHAR(20)     NOT NULL DEFAULT 'percentage',
    discount_value              FLOAT           NOT NULL DEFAULT 0.0,
    min_purchase_amount         FLOAT           NOT NULL DEFAULT 0.0,
    max_discount_amount         FLOAT           NOT NULL DEFAULT 0.0,
    usage_limit                 INT             NOT NULL DEFAULT 0,
    used_count                  INT             NOT NULL DEFAULT 0,
    per_customer_limit          INT             NOT NULL DEFAULT 0,
    applicable_skus_json        TEXT            NOT NULL DEFAULT '[]',
    applicable_categories_json  TEXT            NOT NULL DEFAULT '[]',
    conditions_json             TEXT            NOT NULL DEFAULT '{}',
    priority                    INT             NOT NULL DEFAULT 0,
    can_stack                   BOOLEAN         NOT NULL DEFAULT FALSE,
    created_by                  VARCHAR(36)     NOT NULL DEFAULT '',
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at                  TIMESTAMPTZ     NULL
);
COMMENT ON TABLE oms.promotion IS '促销活动表';

CREATE TABLE IF NOT EXISTS oms.order_split_rule (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    name            VARCHAR(200)    NOT NULL,
    rule_type       VARCHAR(50)     NOT NULL,
    conditions_json TEXT            NOT NULL DEFAULT '{}',
    priority        INT             NOT NULL DEFAULT 0,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE oms.order_split_rule IS '拆单规则表';

CREATE TABLE IF NOT EXISTS oms.order_audit_log (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    order_id        VARCHAR(36)     NOT NULL,
    action          VARCHAR(50)     NOT NULL,
    from_status     VARCHAR(30)     NOT NULL DEFAULT '',
    to_status       VARCHAR(30)     NOT NULL DEFAULT '',
    operator_id     VARCHAR(36)     NOT NULL DEFAULT '',
    operator_name   VARCHAR(200)    NOT NULL DEFAULT '',
    remark          TEXT            NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE oms.order_audit_log IS '订单审计日志表';

CREATE INDEX idx_orderaudit_tenant ON oms.order_audit_log(tenant_id);
CREATE INDEX idx_orderaudit_order ON oms.order_audit_log(order_id);

-- ============================================================
-- 6. SCM域 - 供应链域
-- ============================================================

CREATE TABLE IF NOT EXISTS scm.supplier (
    id                  VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id           VARCHAR(36)     NOT NULL,
    name                VARCHAR(200)    NOT NULL,
    code                VARCHAR(100)    NOT NULL,
    short_name          VARCHAR(100)    NOT NULL DEFAULT '',
    contact_person      VARCHAR(100)    NOT NULL DEFAULT '',
    contact_phone       VARCHAR(50)     NOT NULL DEFAULT '',
    contact_email       VARCHAR(200)    NOT NULL DEFAULT '',
    address             VARCHAR(500)    NOT NULL DEFAULT '',
    region              VARCHAR(100)    NOT NULL DEFAULT '',
    supplier_type       VARCHAR(30)     NOT NULL DEFAULT 'general',
    cooperation_level   VARCHAR(20)     NOT NULL DEFAULT 'normal',
    payment_terms       VARCHAR(100)    NOT NULL DEFAULT '',
    lead_time_days      INT             NOT NULL DEFAULT 0,
    min_order_qty       INT             NOT NULL DEFAULT 0,
    quality_score       FLOAT           NOT NULL DEFAULT 0.0,
    delivery_score      FLOAT           NOT NULL DEFAULT 0.0,
    status              VARCHAR(20)     NOT NULL DEFAULT 'active',
    org_id              VARCHAR(36)     NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ     NULL
);
COMMENT ON TABLE scm.supplier IS '供应商表';
COMMENT ON COLUMN scm.supplier.supplier_type IS '类型: general/factory/trading';
COMMENT ON COLUMN scm.supplier.cooperation_level IS '合作等级: strategic/normal/trial';

CREATE INDEX idx_supplier_tenant ON scm.supplier(tenant_id);

CREATE TABLE IF NOT EXISTS scm.purchase_order (
    id                      VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id               VARCHAR(36)     NOT NULL,
    po_no                   VARCHAR(100)    NOT NULL UNIQUE,
    supplier_id             VARCHAR(36)     NOT NULL,
    warehouse_id            VARCHAR(36)     NOT NULL,
    po_type                 VARCHAR(30)     NOT NULL DEFAULT 'standard',
    purchase_mode           VARCHAR(30)     NOT NULL DEFAULT 'standard_purchase',
    status                  VARCHAR(30)     NOT NULL DEFAULT 'draft',
    currency                VARCHAR(10)     NOT NULL DEFAULT 'CNY',
    total_amount            FLOAT           NOT NULL DEFAULT 0.0,
    paid_amount             FLOAT           NOT NULL DEFAULT 0.0,
    expected_delivery_date  TIMESTAMPTZ     NULL,
    actual_delivery_date    TIMESTAMPTZ     NULL,
    approval_instance_id    VARCHAR(36)     NOT NULL DEFAULT '',
    recommendation_id       VARCHAR(36)     NOT NULL DEFAULT '',
    remark                  TEXT            NOT NULL DEFAULT '',
    created_by              VARCHAR(36)     NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at              TIMESTAMPTZ     NULL,
    version                 INT             NOT NULL DEFAULT 1
);
COMMENT ON TABLE scm.purchase_order IS '采购单表';
COMMENT ON COLUMN scm.purchase_order.purchase_mode IS '采购模式(V4): standard_purchase/consignment/jit_dropship/vmi_subcontracting/centralized';

CREATE INDEX idx_po_tenant ON scm.purchase_order(tenant_id);
CREATE INDEX idx_po_supplier ON scm.purchase_order(supplier_id);
CREATE INDEX idx_po_status ON scm.purchase_order(status);

CREATE TABLE IF NOT EXISTS scm.purchase_order_item (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    po_id           VARCHAR(36)     NOT NULL,
    sku_id          VARCHAR(36)     NOT NULL,
    quantity        INT             NOT NULL DEFAULT 0,
    received_qty    INT             NOT NULL DEFAULT 0,
    unit_price      FLOAT           NOT NULL DEFAULT 0.0,
    item_total      FLOAT           NOT NULL DEFAULT 0.0,
    expected_date   TIMESTAMPTZ     NULL,
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE scm.purchase_order_item IS '采购明细表';

CREATE INDEX idx_poitem_po ON scm.purchase_order_item(po_id);

CREATE TABLE IF NOT EXISTS scm.replenishment_plan (
    id                      VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id               VARCHAR(36)     NOT NULL,
    plan_no                 VARCHAR(100)    NOT NULL UNIQUE,
    warehouse_id            VARCHAR(36)     NOT NULL,
    plan_type               VARCHAR(30)     NOT NULL DEFAULT 'auto',
    status                  VARCHAR(20)     NOT NULL DEFAULT 'draft',
    items_json              TEXT            NOT NULL DEFAULT '[]',
    recommendation_id       VARCHAR(36)     NOT NULL DEFAULT '',
    approval_instance_id    VARCHAR(36)     NOT NULL DEFAULT '',
    created_by              VARCHAR(36)     NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE scm.replenishment_plan IS '补货计划表';

CREATE TABLE IF NOT EXISTS scm.supplier_evaluation (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    supplier_id     VARCHAR(36)     NOT NULL,
    period          VARCHAR(20)     NOT NULL,
    quality_score   FLOAT           NOT NULL DEFAULT 0.0,
    delivery_score  FLOAT           NOT NULL DEFAULT 0.0,
    price_score     FLOAT           NOT NULL DEFAULT 0.0,
    service_score   FLOAT           NOT NULL DEFAULT 0.0,
    overall_score   FLOAT           NOT NULL DEFAULT 0.0,
    remarks         TEXT            NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE scm.supplier_evaluation IS '供应商评估表';

CREATE INDEX idx_supeval_supplier ON scm.supplier_evaluation(supplier_id);

CREATE TABLE IF NOT EXISTS scm.inquiry (
    id                          VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id                   VARCHAR(36)     NOT NULL,
    inquiry_no                  VARCHAR(100)    NOT NULL UNIQUE,
    title                       VARCHAR(500)    NOT NULL,
    status                      VARCHAR(20)     NOT NULL DEFAULT 'draft',
    deadline                    TIMESTAMPTZ     NULL,
    items_json                  TEXT            NOT NULL DEFAULT '[]',
    target_supplier_ids_json    TEXT            NOT NULL DEFAULT '[]',
    created_by                  VARCHAR(36)     NOT NULL DEFAULT '',
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE scm.inquiry IS '询价单表';

CREATE TABLE IF NOT EXISTS scm.inquiry_quote (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    inquiry_id      VARCHAR(36)     NOT NULL,
    supplier_id     VARCHAR(36)     NOT NULL,
    quote_items_json TEXT           NOT NULL DEFAULT '[]',
    total_amount    FLOAT           NOT NULL DEFAULT 0.0,
    currency        VARCHAR(10)     NOT NULL DEFAULT 'CNY',
    lead_time_days  INT             NOT NULL DEFAULT 0,
    remark          TEXT            NOT NULL DEFAULT '',
    status          VARCHAR(20)     NOT NULL DEFAULT 'submitted',
    is_winner       INT             NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE scm.inquiry_quote IS '询价报价表';

CREATE INDEX idx_inqquote_inquiry ON scm.inquiry_quote(inquiry_id);

-- ============================================================
-- 7. WMS域 - 仓储域
-- ============================================================

CREATE TABLE IF NOT EXISTS wms.warehouse (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    name            VARCHAR(200)    NOT NULL,
    code            VARCHAR(100)    NOT NULL,
    warehouse_type  VARCHAR(30)     NOT NULL DEFAULT 'self',
    region          VARCHAR(100)    NOT NULL DEFAULT '',
    address         VARCHAR(500)    NOT NULL DEFAULT '',
    contact_person  VARCHAR(100)    NOT NULL DEFAULT '',
    contact_phone   VARCHAR(50)     NOT NULL DEFAULT '',
    is_default      BOOLEAN         NOT NULL DEFAULT FALSE,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    org_id          VARCHAR(36)     NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ     NULL
);
COMMENT ON TABLE wms.warehouse IS '仓库表';
COMMENT ON COLUMN wms.warehouse.warehouse_type IS '仓库类型: self/third_party/fba/virtual';

CREATE INDEX idx_wh_tenant ON wms.warehouse(tenant_id);

CREATE TABLE IF NOT EXISTS wms.location (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    warehouse_id    VARCHAR(36)     NOT NULL,
    code            VARCHAR(100)    NOT NULL,
    name            VARCHAR(200)    NOT NULL DEFAULT '',
    zone            VARCHAR(50)     NOT NULL DEFAULT '',
    aisle           VARCHAR(20)     NOT NULL DEFAULT '',
    shelf           VARCHAR(20)     NOT NULL DEFAULT '',
    bin             VARCHAR(20)     NOT NULL DEFAULT '',
    location_type   VARCHAR(30)     NOT NULL DEFAULT 'storage',
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE wms.location IS '库位表';
COMMENT ON COLUMN wms.location.location_type IS '库位类型: receiving/storage/picking/packing/shipping/defective';

CREATE INDEX idx_loc_wh ON wms.location(warehouse_id);

CREATE TABLE IF NOT EXISTS wms.inventory (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    warehouse_id    VARCHAR(36)     NOT NULL,
    sku_id          VARCHAR(36)     NOT NULL,
    location_id     VARCHAR(36)     NULL,
    qty_on_hand     INT             NOT NULL DEFAULT 0,
    qty_reserved    INT             NOT NULL DEFAULT 0,
    qty_available   INT             NOT NULL DEFAULT 0,
    qty_inbound     INT             NOT NULL DEFAULT 0,
    qty_outbound    INT             NOT NULL DEFAULT 0,
    qty_defective   INT             NOT NULL DEFAULT 0,
    safety_qty      INT             NOT NULL DEFAULT 0,
    batch_no        VARCHAR(100)    NOT NULL DEFAULT '',
    cost_price      FLOAT           NOT NULL DEFAULT 0.0,
    cost_currency   VARCHAR(10)     NOT NULL DEFAULT 'CNY',
    last_counted_at TIMESTAMPTZ     NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    version         INT             NOT NULL DEFAULT 1
);
COMMENT ON TABLE wms.inventory IS '库存表 - 实时库存快照';
COMMENT ON COLUMN wms.inventory.safety_qty IS '安全库存阈值';

CREATE INDEX idx_inv_wh_sku ON wms.inventory(warehouse_id, sku_id);

CREATE TABLE IF NOT EXISTS wms.inbound_order (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    inbound_no      VARCHAR(100)    NOT NULL UNIQUE,
    warehouse_id    VARCHAR(36)     NOT NULL,
    inbound_type    VARCHAR(30)     NOT NULL DEFAULT 'purchase',
    source_id       VARCHAR(36)     NOT NULL DEFAULT '',
    status          VARCHAR(30)     NOT NULL DEFAULT 'pending',
    items_json      TEXT            NOT NULL DEFAULT '[]',
    received_json   TEXT            NOT NULL DEFAULT '{}',
    remark          TEXT            NOT NULL DEFAULT '',
    created_by      VARCHAR(36)     NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE wms.inbound_order IS '入库单表';
COMMENT ON COLUMN wms.inbound_order.inbound_type IS '入库类型: purchase/return/transfer/other';

CREATE INDEX idx_inbound_wh ON wms.inbound_order(warehouse_id);

CREATE TABLE IF NOT EXISTS wms.outbound_order (
    id              VARCHAR(36)     NOT NULL PRIMARY KEY,
    tenant_id       VARCHAR(36)     NOT NULL,
    outbound_no     VARCHAR(100)    NOT NULL UNIQUE,
    warehouse_id    VARCHAR(36)     NOT NULL,
    outbound_type   VARCHAR(30)     NOT NULL DEFAULT 'sales',
    source_id       VARCHAR(36)     NOT NULL DEFAULT '',
    status          VARCHAR(30)     NOT NULL DEFAULT 'pending',
    items_json      TEXT            NOT