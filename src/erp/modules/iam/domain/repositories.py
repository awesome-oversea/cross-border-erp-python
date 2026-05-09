"""
IAM域 - 仓储接口层

定义组织权限域所有数据访问的抽象接口，遵循DDD仓储模式。
每个聚合根对应一个仓储接口，由基础设施层提供SQLAlchemy实现。

设计原则:
- 接口与实现分离，领域层不依赖具体ORM
- 所有查询方法强制传入tenant_id实现多租户隔离
- 软删除通过deleted_at IS NULL条件过滤
- 分页查询返回(数据列表, 总数)元组
"""
from abc import ABC, abstractmethod
from collections.abc import Sequence

from erp.modules.iam.domain.models import (
    AuditLog,
    DataPermissionRule,
    ObjectPermission,
    Organization,
    Permission,
    Position,
    Role,
    RolePermission,
    Tenant,
    User,
    UserPosition,
    UserRole,
)


class TenantRepository(ABC):
    """租户仓储接口 - 租户的CRUD操作"""

    @abstractmethod
    async def get_by_id(self, tenant_id: str) -> Tenant | None:
        """根据ID查询租户"""
        ...

    @abstractmethod
    async def get_by_code(self, code: str) -> Tenant | None:
        """根据编码查询租户"""
        ...

    @abstractmethod
    async def list_all(self, status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[Tenant], int]:
        """分页查询租户列表，可按状态过滤"""
        ...

    @abstractmethod
    async def create(self, tenant: Tenant) -> Tenant:
        """创建租户"""
        ...

    @abstractmethod
    async def update(self, tenant: Tenant) -> Tenant:
        """更新租户"""
        ...

    @abstractmethod
    async def soft_delete(self, tenant_id: str) -> bool:
        """软删除租户，设置deleted_at和status=deleted"""
        ...


class OrganizationRepository(ABC):
    """组织架构仓储接口 - 支持树形结构查询"""

    @abstractmethod
    async def get_by_id(self, org_id: str, tenant_id: str) -> Organization | None:
        """根据ID查询组织"""
        ...

    @abstractmethod
    async def get_by_code(self, code: str, tenant_id: str) -> Organization | None:
        """根据编码查询组织"""
        ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, org_type: str = "") -> Sequence[Organization]:
        """查询租户下所有组织，可按类型过滤"""
        ...

    @abstractmethod
    async def list_children(self, parent_id: str, tenant_id: str) -> Sequence[Organization]:
        """查询指定组织的直接子组织"""
        ...

    @abstractmethod
    async def get_subtree_ids(self, org_id: str, tenant_id: str) -> Sequence[str]:
        """获取指定组织及其所有后代的ID列表，基于物化路径"""
        ...

    @abstractmethod
    async def create(self, org: Organization) -> Organization:
        """创建组织"""
        ...

    @abstractmethod
    async def update(self, org: Organization) -> Organization:
        """更新组织"""
        ...

    @abstractmethod
    async def soft_delete(self, org_id: str, tenant_id: str) -> bool:
        """软删除组织"""
        ...


class PositionRepository(ABC):
    """岗位仓储接口(V4新增) - 组织下岗位的CRUD操作"""

    @abstractmethod
    async def get_by_id(self, position_id: str, tenant_id: str) -> Position | None:
        """根据ID查询岗位"""
        ...

    @abstractmethod
    async def get_by_code(self, code: str, tenant_id: str) -> Position | None:
        """根据编码查询岗位"""
        ...

    @abstractmethod
    async def list_by_org(self, org_id: str, tenant_id: str) -> Sequence[Position]:
        """查询组织下所有岗位"""
        ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "") -> Sequence[Position]:
        """查询租户下所有岗位，可按状态过滤"""
        ...

    @abstractmethod
    async def create(self, position: Position) -> Position:
        """创建岗位"""
        ...

    @abstractmethod
    async def update(self, position: Position) -> Position:
        """更新岗位"""
        ...

    @abstractmethod
    async def soft_delete(self, position_id: str, tenant_id: str) -> bool:
        """软删除岗位"""
        ...


class UserPositionRepository(ABC):
    """用户岗位关联仓储接口 - 用户与岗位的多对多关系"""

    @abstractmethod
    async def list_by_user(self, user_id: str, tenant_id: str) -> Sequence[UserPosition]:
        """查询用户的所有岗位关联"""
        ...

    @abstractmethod
    async def list_by_position(self, position_id: str, tenant_id: str) -> Sequence[UserPosition]:
        """查询岗位下的所有用户关联"""
        ...

    @abstractmethod
    async def assign(self, user_id: str, position_id: str, tenant_id: str, is_primary: bool = False) -> UserPosition:
        """分配岗位给用户"""
        ...

    @abstractmethod
    async def revoke(self, user_id: str, position_id: str, tenant_id: str) -> bool:
        """撤销用户的岗位"""
        ...

    @abstractmethod
    async def set_primary(self, user_id: str, position_id: str, tenant_id: str) -> bool:
        """设置主岗，同时取消其他主岗标记"""
        ...


class UserRepository(ABC):
    """用户仓储接口 - 用户的CRUD及批量操作"""

    @abstractmethod
    async def get_by_id(self, user_id: str, tenant_id: str) -> User | None:
        """根据ID查询用户"""
        ...

    @abstractmethod
    async def get_by_username(self, username: str, tenant_id: str) -> User | None:
        """根据用户名查询用户，用于登录验证"""
        ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[User], int]:
        """分页查询租户下用户，可按状态过滤"""
        ...

    @abstractmethod
    async def list_by_org(self, org_id: str, tenant_id: str) -> Sequence[User]:
        """查询组织下所有活跃用户"""
        ...

    @abstractmethod
    async def count_by_tenant(self, tenant_id: str) -> int:
        """统计租户下活跃用户数，用于套餐限制校验"""
        ...

    @abstractmethod
    async def batch_update_status(self, user_ids: list[str], tenant_id: str, status: str) -> int:
        """批量更新用户状态"""
        ...

    @abstractmethod
    async def create(self, user: User) -> User:
        """创建用户"""
        ...

    @abstractmethod
    async def update(self, user: User) -> User:
        """更新用户"""
        ...

    @abstractmethod
    async def soft_delete(self, user_id: str, tenant_id: str) -> bool:
        """软删除用户"""
        ...


class RoleRepository(ABC):
    """角色仓储接口 - 角色的CRUD操作"""

    @abstractmethod
    async def get_by_id(self, role_id: str, tenant_id: str) -> Role | None:
        """根据ID查询角色"""
        ...

    @abstractmethod
    async def get_by_code(self, code: str, tenant_id: str) -> Role | None:
        """根据编码查询角色"""
        ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "") -> Sequence[Role]:
        """查询租户下所有角色，可按状态过滤"""
        ...

    @abstractmethod
    async def create(self, role: Role) -> Role:
        """创建角色"""
        ...

    @abstractmethod
    async def update(self, role: Role) -> Role:
        """更新角色"""
        ...

    @abstractmethod
    async def soft_delete(self, role_id: str, tenant_id: str) -> bool:
        """软删除角色"""
        ...


class PermissionRepository(ABC):
    """权限仓储接口 - 权限的CRUD操作，权限为全局数据不分租户"""

    @abstractmethod
    async def get_by_id(self, perm_id: str) -> Permission | None:
        """根据ID查询权限"""
        ...

    @abstractmethod
    async def get_by_code(self, code: str) -> Permission | None:
        """根据编码查询权限"""
        ...

    @abstractmethod
    async def list_all(self, perm_type: str = "") -> Sequence[Permission]:
        """查询所有权限，可按类型过滤"""
        ...

    @abstractmethod
    async def list_by_ids(self, perm_ids: list[str]) -> Sequence[Permission]:
        """根据ID列表批量查询权限"""
        ...

    @abstractmethod
    async def create(self, perm: Permission) -> Permission:
        """创建权限"""
        ...

    @abstractmethod
    async def update(self, perm: Permission) -> Permission:
        """更新权限"""
        ...

    @abstractmethod
    async def soft_delete(self, perm_id: str) -> bool:
        """软删除权限"""
        ...


class ObjectPermissionRepository(ABC):
    """对象级权限仓储接口(V4新增) - 行级权限的CRUD操作"""

    @abstractmethod
    async def list_by_subject(self, subject_type: str, subject_id: str, tenant_id: str) -> Sequence[ObjectPermission]:
        """查询主体的所有对象权限"""
        ...

    @abstractmethod
    async def list_by_resource(self, resource_type: str, resource_id: str, tenant_id: str) -> Sequence[ObjectPermission]:
        """查询资源的所有对象权限"""
        ...

    @abstractmethod
    async def check_permission(
        self, subject_type: str, subject_id: str, resource_type: str, resource_id: str, action: str, tenant_id: str
    ) -> ObjectPermission | None:
        """检查指定对象权限是否存在"""
        ...

    @abstractmethod
    async def grant(self, obj_perm: ObjectPermission) -> ObjectPermission:
        """授予对象级权限"""
        ...

    @abstractmethod
    async def revoke(self, perm_id: str, tenant_id: str) -> bool:
        """撤销对象级权限"""
        ...


class DataPermissionRuleRepository(ABC):
    """数据权限规则仓储接口 - 10维度数据隔离规则的CRUD操作"""

    @abstractmethod
    async def list_by_role(self, role_id: str, tenant_id: str) -> Sequence[DataPermissionRule]:
        """查询角色的所有数据权限规则"""
        ...

    @abstractmethod
    async def list_by_user(self, user_id: str, tenant_id: str) -> Sequence[DataPermissionRule]:
        """查询用户的所有数据权限规则"""
        ...

    @abstractmethod
    async def list_by_dimension(self, dimension: str, tenant_id: str) -> Sequence[DataPermissionRule]:
        """查询指定维度的所有数据权限规则"""
        ...

    @abstractmethod
    async def create(self, rule: DataPermissionRule) -> DataPermissionRule:
        """创建数据权限规则"""
        ...

    @abstractmethod
    async def update(self, rule: DataPermissionRule) -> DataPermissionRule:
        """更新数据权限规则"""
        ...

    @abstractmethod
    async def delete(self, rule_id: str, tenant_id: str) -> bool:
        """删除数据权限规则"""
        ...


class UserRoleRepository(ABC):
    """用户角色关联仓储接口 - 用户与角色的多对多关系"""

    @abstractmethod
    async def list_by_user(self, user_id: str, tenant_id: str) -> Sequence[UserRole]:
        """查询用户的所有角色关联"""
        ...

    @abstractmethod
    async def list_by_role(self, role_id: str, tenant_id: str) -> Sequence[UserRole]:
        """查询角色下的所有用户关联"""
        ...

    @abstractmethod
    async def assign(self, user_id: str, role_id: str, tenant_id: str) -> UserRole:
        """分配角色给用户"""
        ...

    @abstractmethod
    async def revoke(self, user_id: str, role_id: str, tenant_id: str) -> bool:
        """撤销用户的角色"""
        ...


class RolePermissionRepository(ABC):
    """角色权限关联仓储接口 - 角色与权限的多对多关系"""

    @abstractmethod
    async def list_by_role(self, role_id: str) -> Sequence[RolePermission]:
        """查询角色的所有权限关联"""
        ...

    @abstractmethod
    async def list_by_roles(self, role_ids: list[str]) -> Sequence[RolePermission]:
        """批量查询多个角色的权限关联"""
        ...

    @abstractmethod
    async def assign(self, role_id: str, permission_id: str) -> RolePermission:
        """分配权限给角色"""
        ...

    @abstractmethod
    async def revoke(self, role_id: str, permission_id: str) -> bool:
        """撤销角色的权限"""
        ...


class AuditLogRepository(ABC):
    """审计日志仓储接口 - 只写不改，支持统计查询"""

    @abstractmethod
    async def create(self, log: AuditLog) -> AuditLog:
        """创建审计日志，日志不可修改"""
        ...

    @abstractmethod
    async def list_by_tenant(
        self, tenant_id: str, module: str = "", action: str = "", page: int = 1, page_size: int = 20
    ) -> tuple[Sequence[AuditLog], int]:
        """分页查询租户审计日志，可按模块和操作类型过滤"""
        ...

    @abstractmethod
    async def get_stats(self, tenant_id: str, days: int = 30) -> dict:
        """获取审计日志统计数据，按操作类型、模块、日期分组"""
        ...
