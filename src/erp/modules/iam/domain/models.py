"""
IAM域 - 组织权限域 ORM模型

本模块定义了组织权限域的所有数据库实体映射，包含:
- Tenant: 租户表，多租户隔离的顶层实体
- Organization: 组织架构表，支持公司/部门/团队三级
- User: 用户表，系统登录与操作主体
- Position: 岗位表(V4新增)，组织下的岗位管理
- UserPosition: 用户岗位关联表，一个用户可兼多岗
- Role: 角色表，功能权限载体
- Permission: 权限表，菜单/按钮/API/数据四级权限
- UserRole: 用户角色关联表
- RolePermission: 角色权限关联表
- ObjectPermission: 对象级权限表(V4新增)，支持行级权限控制
- DataPermissionRule: 数据权限规则表，10维度数据隔离
- AuditLog: 审计日志表，全操作留痕

技术栈: SQLAlchemy 2.x + async + PostgreSQL
主键策略: UUID由应用层生成
多租户: 所有业务表包含tenant_id字段实现隔离
软删除: deleted_at字段，非物理删除
乐观锁: version字段，防止并发覆盖
审计: created_at/updated_at自动维护
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base


class Tenant(Base):
    """租户表 - 多租户隔离的顶层实体，每个客户对应一个租户"""
    __tablename__ = "tenant"
    __table_args__ = {"schema": "iam"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="租户名称")
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="租户编码，全局唯一")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="租户状态: active/suspended/deleted")
    plan: Mapped[str] = mapped_column(String(30), nullable=False, default="free", comment="套餐类型: free/pro/enterprise")
    max_users: Mapped[int] = mapped_column(default=10, nullable=False, comment="最大用户数")
    max_stores: Mapped[int] = mapped_column(default=5, nullable=False, comment="最大店铺数")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="套餐到期时间")
    contact_name: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="联系人姓名")
    contact_email: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="联系人邮箱")
    contact_phone: Mapped[str] = mapped_column(String(30), nullable=False, default="", comment="联系人电话")
    logo_url: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="Logo地址")
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="租户配置JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class Organization(Base):
    """组织架构表 - 支持公司/部门/团队三级树形结构，使用物化路径加速查询"""
    __tablename__ = "organization"
    __table_args__ = {"schema": "iam"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="父组织ID，顶级为NULL")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="组织名称")
    code: Mapped[str] = mapped_column(String(50), nullable=False, comment="组织编码")
    org_type: Mapped[str] = mapped_column(String(30), nullable=False, default="company", comment="组织类型: company/department/team")
    path: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="物化路径，如/root/child1/child2")
    level: Mapped[int] = mapped_column(default=1, nullable=False, comment="层级深度，从1开始")
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False, comment="排序序号")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    leader_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="负责人用户ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class User(Base):
    """用户表 - 系统登录与操作主体，支持内部/外部用户类型"""
    __tablename__ = "user"
    __table_args__ = {"schema": "iam"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    org_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="主属组织ID")
    username: Mapped[str] = mapped_column(String(80), nullable=False, comment="登录用户名")
    email: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="邮箱地址")
    phone: Mapped[str] = mapped_column(String(30), nullable=False, default="", comment="手机号码")
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False, comment="密码哈希值")
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="显示名称")
    avatar_url: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="头像地址")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled/locked")
    user_type: Mapped[str] = mapped_column(String(20), nullable=False, default="internal", comment="用户类型: internal/external")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最后登录时间")
    last_login_ip: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="最后登录IP")
    login_fail_count: Mapped[int] = mapped_column(default=0, nullable=False, comment="连续登录失败次数")
    must_change_pwd: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否需要强制修改密码")
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最后密码修改时间")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="乐观锁版本号")


class Position(Base):
    """岗位表(V4新增) - 组织下的岗位管理，支持一用户多岗位"""
    __tablename__ = "position"
    __table_args__ = {"schema": "iam"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="所属组织ID")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="岗位名称")
    code: Mapped[str] = mapped_column(String(50), nullable=False, comment="岗位编码，租户内唯一")
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="岗位层级，数字越大级别越高")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序序号")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class UserPosition(Base):
    """用户岗位关联表 - 一个用户可兼任多个岗位，标记主岗"""
    __tablename__ = "user_position"
    __table_args__ = {"schema": "iam"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="用户ID")
    position_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="岗位ID")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否主岗")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")


class Role(Base):
    """角色表 - 功能权限载体，支持系统预置和自定义角色"""
    __tablename__ = "role"
    __table_args__ = {"schema": "iam"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    name: Mapped[str] = mapped_column(String(80), nullable=False, comment="角色名称")
    code: Mapped[str] = mapped_column(String(80), nullable=False, comment="角色编码")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="角色描述")
    role_type: Mapped[str] = mapped_column(String(20), nullable=False, default="custom", comment="角色类型: system/custom")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False, comment="排序序号")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="软删除时间")


class Permission(Base):
    """权限表 - 菜单/按钮/API/数据四级权限，树形结构"""
    __tablename__ = "permission"
    __table_args__ = {"schema": "iam"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="父权限ID")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="权限名称")
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, comment="权限编码，全局唯一")
    perm_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="权限类型: menu/button/api/data")
    resource: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="资源标识符")
    action: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="操作: read/write/delete/approve")
    path: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="物化路径")
    level: Mapped[int] = mapped_column(default=1, nullable=False, comment="层级深度")
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False, comment="排序序号")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态")
    icon: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="图标标识")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class UserRole(Base):
    """用户角色关联表 - 用户与角色的多对多关系"""
    __tablename__ = "user_role"
    __table_args__ = {"schema": "iam"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="用户ID")
    role_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="角色ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")


class RolePermission(Base):
    """角色权限关联表 - 角色与权限的多对多关系"""
    __tablename__ = "role_permission"
    __table_args__ = {"schema": "iam"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    role_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="角色ID")
    permission_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="权限ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")


class ObjectPermission(Base):
    """对象级权限表(V4新增) - 支持行级权限控制，实现细粒度数据访问控制"""
    __tablename__ = "object_permission"
    __table_args__ = {"schema": "iam"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="主体类型: user/role/position/org")
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False, comment="主体ID")
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="资源类型: order/product/customer/...")
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False, comment="资源实例ID")
    action: Mapped[str] = mapped_column(String(50), nullable=False, default="read", comment="操作: read/write/delete/approve")
    effect: Mapped[str] = mapped_column(String(20), nullable=False, default="allow", comment="效果: allow/deny")
    conditions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="附加条件JSON，如时间范围等")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class DataPermissionRule(Base):
    """数据权限规则表 - 10维度数据隔离，控制用户可访问的数据范围"""
    __tablename__ = "data_permission_rule"
    __table_args__ = {"schema": "iam"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    role_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="角色ID，与user_id二选一")
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="用户ID，与role_id二选一")
    dimension: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="维度: tenant/org/department/store/marketplace/channel/warehouse/supplier/category/data_level"
    )
    allowed_values_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="允许的值列表JSON")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="优先级，数字越大优先级越高")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class AuditLog(Base):
    """审计日志表 - 全操作留痕，支持合规审计和问题追溯"""
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "iam"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键ID")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="租户ID")
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="操作用户ID")
    user_name: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="操作用户名称")
    action: Mapped[str] = mapped_column(String(50), nullable=False, comment="操作类型: create/update/delete/login/logout")
    module: Mapped[str] = mapped_column(String(50), nullable=False, comment="所属模块: iam/pdm/oms/...")
    target_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="目标类型: tenant/user/role/...")
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="目标ID")
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="变更详情JSON")
    ip: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="操作IP地址")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="链路追踪ID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="创建时间")
