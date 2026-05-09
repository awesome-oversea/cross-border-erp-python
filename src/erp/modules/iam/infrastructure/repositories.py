from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

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
from erp.modules.iam.domain.repositories import (
    AuditLogRepository,
    DataPermissionRuleRepository,
    ObjectPermissionRepository,
    OrganizationRepository,
    PermissionRepository,
    PositionRepository,
    RolePermissionRepository,
    RoleRepository,
    TenantRepository,
    UserPositionRepository,
    UserRepository,
    UserRoleRepository,
)


class SqlTenantRepository(TenantRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, tenant_id: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.code == code, Tenant.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[Tenant], int]:
        conditions = [Tenant.deleted_at.is_(None)]
        if status:
            conditions.append(Tenant.status == status)
        count_stmt = select(func.count()).select_from(Tenant).where(*conditions)
        total = (await self._session.execute(count_stmt)).scalar() or 0
        stmt = select(Tenant).where(*conditions).order_by(Tenant.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(stmt)
        return result.scalars().all(), total

    async def create(self, tenant: Tenant) -> Tenant:
        self._session.add(tenant)
        await self._session.flush()
        return tenant

    async def update(self, tenant: Tenant) -> Tenant:
        await self._session.flush()
        return tenant

    async def soft_delete(self, tenant_id: str) -> bool:
        stmt = update(Tenant).where(Tenant.id == tenant_id).values(deleted_at=datetime.now(UTC), status="deleted")
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlOrganizationRepository(OrganizationRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, org_id: str, tenant_id: str) -> Organization | None:
        stmt = select(Organization).where(
            Organization.id == org_id, Organization.tenant_id == tenant_id, Organization.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str, tenant_id: str) -> Organization | None:
        stmt = select(Organization).where(
            Organization.code == code, Organization.tenant_id == tenant_id, Organization.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, org_type: str = "") -> Sequence[Organization]:
        conditions = [Organization.tenant_id == tenant_id, Organization.deleted_at.is_(None)]
        if org_type:
            conditions.append(Organization.org_type == org_type)
        stmt = select(Organization).where(*conditions).order_by(Organization.sort_order, Organization.created_at)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_children(self, parent_id: str, tenant_id: str) -> Sequence[Organization]:
        stmt = select(Organization).where(
            Organization.parent_id == parent_id, Organization.tenant_id == tenant_id, Organization.deleted_at.is_(None)
        ).order_by(Organization.sort_order)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_subtree_ids(self, org_id: str, tenant_id: str) -> Sequence[str]:
        stmt = select(Organization.id).where(
            Organization.tenant_id == tenant_id,
            Organization.deleted_at.is_(None),
            Organization.path.contains(org_id),
        )
        result = await self._session.execute(stmt)
        ids = list(result.scalars().all())
        if org_id not in ids:
            ids.append(org_id)
        return ids

    async def create(self, org: Organization) -> Organization:
        self._session.add(org)
        await self._session.flush()
        return org

    async def update(self, org: Organization) -> Organization:
        await self._session.flush()
        return org

    async def soft_delete(self, org_id: str, tenant_id: str) -> bool:
        stmt = update(Organization).where(
            Organization.id == org_id, Organization.tenant_id == tenant_id
        ).values(deleted_at=datetime.now(UTC), status="disabled")
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, user_id: str, tenant_id: str) -> User | None:
        stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id, User.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str, tenant_id: str) -> User | None:
        stmt = select(User).where(User.username == username, User.tenant_id == tenant_id, User.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[User], int]:
        conditions = [User.tenant_id == tenant_id, User.deleted_at.is_(None)]
        if status:
            conditions.append(User.status == status)
        count_stmt = select(func.count()).select_from(User).where(*conditions)
        total = (await self._session.execute(count_stmt)).scalar() or 0
        stmt = select(User).where(*conditions).order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(stmt)
        return result.scalars().all(), total

    async def list_by_org(self, org_id: str, tenant_id: str) -> Sequence[User]:
        stmt = select(User).where(
            User.org_id == org_id, User.tenant_id == tenant_id, User.deleted_at.is_(None), User.status == "active"
        ).order_by(User.display_name)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_by_tenant(self, tenant_id: str) -> int:
        stmt = select(func.count()).select_from(User).where(
            User.tenant_id == tenant_id, User.deleted_at.is_(None), User.status == "active"
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def batch_update_status(self, user_ids: list[str], tenant_id: str, status: str) -> int:
        stmt = update(User).where(
            User.id.in_(user_ids), User.tenant_id == tenant_id, User.deleted_at.is_(None)
        ).values(status=status)
        result = await self._session.execute(stmt)
        return result.rowcount

    async def create(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user

    async def update(self, user: User) -> User:
        await self._session.flush()
        return user

    async def soft_delete(self, user_id: str, tenant_id: str) -> bool:
        stmt = update(User).where(User.id == user_id, User.tenant_id == tenant_id).values(
            deleted_at=datetime.now(UTC), status="disabled"
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlRoleRepository(RoleRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, role_id: str, tenant_id: str) -> Role | None:
        stmt = select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id, Role.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str, tenant_id: str) -> Role | None:
        stmt = select(Role).where(Role.code == code, Role.tenant_id == tenant_id, Role.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "") -> Sequence[Role]:
        conditions = [Role.tenant_id == tenant_id, Role.deleted_at.is_(None)]
        if status:
            conditions.append(Role.status == status)
        stmt = select(Role).where(*conditions).order_by(Role.sort_order, Role.created_at)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create(self, role: Role) -> Role:
        self._session.add(role)
        await self._session.flush()
        return role

    async def update(self, role: Role) -> Role:
        await self._session.flush()
        return role

    async def soft_delete(self, role_id: str, tenant_id: str) -> bool:
        stmt = update(Role).where(Role.id == role_id, Role.tenant_id == tenant_id).values(
            deleted_at=datetime.now(UTC), status="disabled"
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlPermissionRepository(PermissionRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, perm_id: str) -> Permission | None:
        stmt = select(Permission).where(Permission.id == perm_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Permission | None:
        stmt = select(Permission).where(Permission.code == code)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, perm_type: str = "") -> Sequence[Permission]:
        conditions = []
        if perm_type:
            conditions.append(Permission.perm_type == perm_type)
        stmt = select(Permission).where(*conditions).order_by(Permission.sort_order, Permission.created_at)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_by_ids(self, perm_ids: list[str]) -> Sequence[Permission]:
        if not perm_ids:
            return []
        stmt = select(Permission).where(Permission.id.in_(perm_ids)).order_by(Permission.sort_order)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create(self, perm: Permission) -> Permission:
        self._session.add(perm)
        await self._session.flush()
        return perm

    async def update(self, perm: Permission) -> Permission:
        await self._session.flush()
        return perm

    async def soft_delete(self, perm_id: str) -> bool:
        stmt = update(Permission).where(Permission.id == perm_id).values(
            status="disabled"
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlUserRoleRepository(UserRoleRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_user(self, user_id: str, tenant_id: str) -> Sequence[UserRole]:
        stmt = select(UserRole).where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_by_role(self, role_id: str, tenant_id: str) -> Sequence[UserRole]:
        stmt = select(UserRole).where(UserRole.role_id == role_id, UserRole.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def assign(self, user_id: str, role_id: str, tenant_id: str) -> UserRole:
        ur = UserRole(user_id=user_id, role_id=role_id, tenant_id=tenant_id)
        self._session.add(ur)
        await self._session.flush()
        return ur

    async def revoke(self, user_id: str, role_id: str, tenant_id: str) -> bool:
        stmt = delete(UserRole).where(
            UserRole.user_id == user_id, UserRole.role_id == role_id, UserRole.tenant_id == tenant_id
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlRolePermissionRepository(RolePermissionRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_role(self, role_id: str) -> Sequence[RolePermission]:
        stmt = select(RolePermission).where(RolePermission.role_id == role_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_by_roles(self, role_ids: list[str]) -> Sequence[RolePermission]:
        if not role_ids:
            return []
        stmt = select(RolePermission).where(RolePermission.role_id.in_(role_ids))
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def assign(self, role_id: str, permission_id: str) -> RolePermission:
        rp = RolePermission(role_id=role_id, permission_id=permission_id)
        self._session.add(rp)
        await self._session.flush()
        return rp

    async def revoke(self, role_id: str, permission_id: str) -> bool:
        stmt = delete(RolePermission).where(
            RolePermission.role_id == role_id, RolePermission.permission_id == permission_id
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlAuditLogRepository(AuditLogRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, log: AuditLog) -> AuditLog:
        self._session.add(log)
        await self._session.flush()
        return log

    async def list_by_tenant(
        self, tenant_id: str, module: str = "", action: str = "", page: int = 1, page_size: int = 20
    ) -> tuple[Sequence[AuditLog], int]:
        conditions = [AuditLog.tenant_id == tenant_id]
        if module:
            conditions.append(AuditLog.module == module)
        if action:
            conditions.append(AuditLog.action == action)
        count_stmt = select(func.count()).select_from(AuditLog).where(*conditions)
        total = (await self._session.execute(count_stmt)).scalar() or 0
        stmt = select(AuditLog).where(*conditions).order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(stmt)
        return result.scalars().all(), total

    async def get_stats(self, tenant_id: str, days: int = 30) -> dict:
        from datetime import timedelta
        since = datetime.now(UTC) - timedelta(days=days)
        base_conditions = [AuditLog.tenant_id == tenant_id, AuditLog.created_at >= since]

        total_stmt = select(func.count()).select_from(AuditLog).where(*base_conditions)
        total = (await self._session.execute(total_stmt)).scalar() or 0

        by_action_stmt = (
            select(AuditLog.action, func.count().label("cnt"))
            .where(*base_conditions)
            .group_by(AuditLog.action)
        )
        action_result = await self._session.execute(by_action_stmt)
        by_action = {row[0]: row[1] for row in action_result.all()}

        by_module_stmt = (
            select(AuditLog.module, func.count().label("cnt"))
            .where(*base_conditions)
            .group_by(AuditLog.module)
        )
        module_result = await self._session.execute(by_module_stmt)
        by_module = {row[0]: row[1] for row in module_result.all()}

        by_date_stmt = (
            select(func.date(AuditLog.created_at).label("d"), func.count().label("cnt"))
            .where(*base_conditions)
            .group_by(func.date(AuditLog.created_at))
            .order_by(func.date(AuditLog.created_at))
        )
        date_result = await self._session.execute(by_date_stmt)
        by_date = {str(row[0]): row[1] for row in date_result.all()}

        return {"total": total, "by_action": by_action, "by_module": by_module, "by_date": by_date}


class SqlPositionRepository(PositionRepository):
    """岗位仓储SQL实现 - 岗位的CRUD操作"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, position_id: str, tenant_id: str) -> Position | None:
        stmt = select(Position).where(
            Position.id == position_id, Position.tenant_id == tenant_id, Position.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str, tenant_id: str) -> Position | None:
        stmt = select(Position).where(
            Position.code == code, Position.tenant_id == tenant_id, Position.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_org(self, org_id: str, tenant_id: str) -> Sequence[Position]:
        stmt = select(Position).where(
            Position.org_id == org_id, Position.tenant_id == tenant_id, Position.deleted_at.is_(None)
        ).order_by(Position.sort_order, Position.created_at)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_by_tenant(self, tenant_id: str, status: str = "") -> Sequence[Position]:
        conditions = [Position.tenant_id == tenant_id, Position.deleted_at.is_(None)]
        if status:
            conditions.append(Position.status == status)
        stmt = select(Position).where(*conditions).order_by(Position.sort_order, Position.created_at)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create(self, position: Position) -> Position:
        self._session.add(position)
        await self._session.flush()
        return position

    async def update(self, position: Position) -> Position:
        await self._session.flush()
        return position

    async def soft_delete(self, position_id: str, tenant_id: str) -> bool:
        stmt = update(Position).where(
            Position.id == position_id, Position.tenant_id == tenant_id
        ).values(deleted_at=datetime.now(UTC), status="disabled")
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlUserPositionRepository(UserPositionRepository):
    """用户岗位关联仓储SQL实现 - 用户与岗位的多对多关系"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_user(self, user_id: str, tenant_id: str) -> Sequence[UserPosition]:
        stmt = select(UserPosition).where(
            UserPosition.user_id == user_id, UserPosition.tenant_id == tenant_id
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_by_position(self, position_id: str, tenant_id: str) -> Sequence[UserPosition]:
        stmt = select(UserPosition).where(
            UserPosition.position_id == position_id, UserPosition.tenant_id == tenant_id
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def assign(self, user_id: str, position_id: str, tenant_id: str, is_primary: bool = False) -> UserPosition:
        up = UserPosition(user_id=user_id, position_id=position_id, tenant_id=tenant_id, is_primary=is_primary)
        self._session.add(up)
        await self._session.flush()
        return up

    async def revoke(self, user_id: str, position_id: str, tenant_id: str) -> bool:
        stmt = delete(UserPosition).where(
            UserPosition.user_id == user_id, UserPosition.position_id == position_id, UserPosition.tenant_id == tenant_id
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def set_primary(self, user_id: str, position_id: str, tenant_id: str) -> bool:
        clear_stmt = update(UserPosition).where(
            UserPosition.user_id == user_id, UserPosition.tenant_id == tenant_id
        ).values(is_primary=False)
        await self._session.execute(clear_stmt)
        set_stmt = update(UserPosition).where(
            UserPosition.user_id == user_id, UserPosition.position_id == position_id, UserPosition.tenant_id == tenant_id
        ).values(is_primary=True)
        result = await self._session.execute(set_stmt)
        return result.rowcount > 0


class SqlObjectPermissionRepository(ObjectPermissionRepository):
    """对象级权限仓储SQL实现 - 行级权限的CRUD操作"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_subject(self, subject_type: str, subject_id: str, tenant_id: str) -> Sequence[ObjectPermission]:
        stmt = select(ObjectPermission).where(
            ObjectPermission.subject_type == subject_type,
            ObjectPermission.subject_id == subject_id,
            ObjectPermission.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_by_resource(self, resource_type: str, resource_id: str, tenant_id: str) -> Sequence[ObjectPermission]:
        stmt = select(ObjectPermission).where(
            ObjectPermission.resource_type == resource_type,
            ObjectPermission.resource_id == resource_id,
            ObjectPermission.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def check_permission(
        self, subject_type: str, subject_id: str, resource_type: str, resource_id: str, action: str, tenant_id: str
    ) -> ObjectPermission | None:
        stmt = select(ObjectPermission).where(
            ObjectPermission.subject_type == subject_type,
            ObjectPermission.subject_id == subject_id,
            ObjectPermission.resource_type == resource_type,
            ObjectPermission.resource_id == resource_id,
            ObjectPermission.action == action,
            ObjectPermission.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def grant(self, obj_perm: ObjectPermission) -> ObjectPermission:
        self._session.add(obj_perm)
        await self._session.flush()
        return obj_perm

    async def revoke(self, perm_id: str, tenant_id: str) -> bool:
        stmt = delete(ObjectPermission).where(
            ObjectPermission.id == perm_id, ObjectPermission.tenant_id == tenant_id
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlDataPermissionRuleRepository(DataPermissionRuleRepository):
    """数据权限规则仓储SQL实现 - 10维度数据隔离规则的CRUD操作"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_role(self, role_id: str, tenant_id: str) -> Sequence[DataPermissionRule]:
        stmt = select(DataPermissionRule).where(
            DataPermissionRule.role_id == role_id, DataPermissionRule.tenant_id == tenant_id
        ).order_by(DataPermissionRule.priority.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_by_user(self, user_id: str, tenant_id: str) -> Sequence[DataPermissionRule]:
        stmt = select(DataPermissionRule).where(
            DataPermissionRule.user_id == user_id, DataPermissionRule.tenant_id == tenant_id
        ).order_by(DataPermissionRule.priority.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_by_dimension(self, dimension: str, tenant_id: str) -> Sequence[DataPermissionRule]:
        stmt = select(DataPermissionRule).where(
            DataPermissionRule.dimension == dimension, DataPermissionRule.tenant_id == tenant_id,
            DataPermissionRule.status == "active",
        ).order_by(DataPermissionRule.priority.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create(self, rule: DataPermissionRule) -> DataPermissionRule:
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def update(self, rule: DataPermissionRule) -> DataPermissionRule:
        await self._session.flush()
        return rule

    async def delete(self, rule_id: str, tenant_id: str) -> bool:
        stmt = delete(DataPermissionRule).where(
            DataPermissionRule.id == rule_id, DataPermissionRule.tenant_id == tenant_id
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0
