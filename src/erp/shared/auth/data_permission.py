from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from erp.shared.context import tenant_id_var

if TYPE_CHECKING:
    from sqlalchemy.sql import Select
    from sqlalchemy.ext.asyncio import AsyncSession


class DataScopeType(StrEnum):
    ALL = "all"
    ORG = "org"
    ORG_AND_CHILDREN = "org_and_children"
    STORE = "store"
    CHANNEL = "channel"
    WAREHOUSE = "warehouse"
    SELF = "self"
    CUSTOM = "custom"


class DataResourceType(StrEnum):
    ORDER = "order"
    PRODUCT = "product"
    INVENTORY = "inventory"
    SHIPMENT = "shipment"
    PURCHASE = "purchase"
    CUSTOMER = "customer"
    AD_CAMPAIGN = "ad_campaign"
    SETTLEMENT = "settlement"
    LISTING = "listing"


@dataclass
class DataPermissionPolicy:
    scope_type: DataScopeType
    resource_type: DataResourceType
    allowed_org_ids: list[str] = field(default_factory=list)
    allowed_store_ids: list[str] = field(default_factory=list)
    allowed_channel_ids: list[str] = field(default_factory=list)
    allowed_warehouse_ids: list[str] = field(default_factory=list)
    allowed_region_codes: list[str] = field(default_factory=list)
    custom_filter: dict[str, Any] = field(default_factory=dict)


@dataclass
class DataPermissionContext:
    tenant_id: str
    user_id: str
    role_codes: list[str] = field(default_factory=list)
    org_id: str = ""
    org_ids_with_children: list[str] = field(default_factory=list)
    store_ids: list[str] = field(default_factory=list)
    warehouse_ids: list[str] = field(default_factory=list)
    policies: list[DataPermissionPolicy] = field(default_factory=list)

    def has_access_to_org(self, org_id: str) -> bool:
        for policy in self.policies:
            if policy.scope_type == DataScopeType.ALL:
                return True
            if policy.scope_type == DataScopeType.ORG and org_id == self.org_id:
                return True
            if policy.scope_type == DataScopeType.ORG_AND_CHILDREN and org_id in self.org_ids_with_children:
                return True
            if policy.scope_type == DataScopeType.CUSTOM and org_id in policy.allowed_org_ids:
                return True
        return False

    def has_access_to_store(self, store_id: str) -> bool:
        for policy in self.policies:
            if policy.scope_type == DataScopeType.ALL:
                return True
            if policy.scope_type == DataScopeType.STORE and store_id in self.store_ids:
                return True
            if policy.scope_type == DataScopeType.CUSTOM and store_id in policy.allowed_store_ids:
                return True
        return False

    def has_access_to_warehouse(self, warehouse_id: str) -> bool:
        for policy in self.policies:
            if policy.scope_type == DataScopeType.ALL:
                return True
            if policy.scope_type == DataScopeType.WAREHOUSE and warehouse_id in self.warehouse_ids:
                return True
            if policy.scope_type == DataScopeType.CUSTOM and warehouse_id in policy.allowed_warehouse_ids:
                return True
        return False

    def get_filter_for_resource(self, resource_type: DataResourceType) -> dict[str, Any]:
        for policy in self.policies:
            if policy.resource_type != resource_type:
                continue
            if policy.scope_type == DataScopeType.ALL:
                return {}
            if policy.scope_type == DataScopeType.SELF:
                return {"created_by": self.user_id}
            filters: dict[str, Any] = {}
            if policy.scope_type == DataScopeType.ORG:
                filters["org_id"] = self.org_id
            elif policy.scope_type == DataScopeType.ORG_AND_CHILDREN:
                filters["org_id__in"] = self.org_ids_with_children
            elif policy.scope_type == DataScopeType.STORE:
                filters["store_id__in"] = self.store_ids
            elif policy.scope_type == DataScopeType.WAREHOUSE:
                filters["warehouse_id__in"] = self.warehouse_ids
            elif policy.scope_type == DataScopeType.CUSTOM:
                if policy.allowed_org_ids:
                    filters["org_id__in"] = policy.allowed_org_ids
                if policy.allowed_store_ids:
                    filters["store_id__in"] = policy.allowed_store_ids
                if policy.allowed_warehouse_ids:
                    filters["warehouse_id__in"] = policy.allowed_warehouse_ids
                if policy.custom_filter:
                    filters.update(policy.custom_filter)
            return filters
        return {"tenant_id": self.tenant_id}


class DataPermissionService:
    def __init__(self):
        self._role_policies: dict[str, list[DataPermissionPolicy]] = {}

    def register_role_policy(self, role_code: str, policies: list[DataPermissionPolicy]):
        self._role_policies[role_code] = policies

    def build_context(self, tenant_id: str, user_id: str, role_codes: list[str],
                      org_id: str = "", org_ids_with_children: list[str] | None = None,
                      store_ids: list[str] | None = None,
                      warehouse_ids: list[str] | None = None) -> DataPermissionContext:
        policies: list[DataPermissionPolicy] = []
        for role_code in role_codes:
            if role_code in self._role_policies:
                policies.extend(self._role_policies[role_code])
        if not policies:
            policies.append(DataPermissionPolicy(
                scope_type=DataScopeType.SELF,
                resource_type=DataResourceType.ORDER,
            ))
        return DataPermissionContext(
            tenant_id=tenant_id,
            user_id=user_id,
            role_codes=role_codes,
            org_id=org_id,
            org_ids_with_children=org_ids_with_children or [],
            store_ids=store_ids or [],
            warehouse_ids=warehouse_ids or [],
            policies=policies,
        )

    def apply_filter_to_query(
        self,
        stmt: Select,
        model: type,
        resource_type: DataResourceType,
        context: DataPermissionContext | None = None,
    ) -> Select:
        """
        将数据权限过滤条件应用到SQLAlchemy查询上

        这是数据权限10维拦截的核心入口，在仓储层调用。
        自动应用 tenant_id 隔离 + 数据范围过滤。

        参数:
            stmt:          SQLAlchemy Select 语句
            model:         模型类 (需包含 tenant_id/org_id/store_id/warehouse_id/created_by 字段)
            resource_type: 数据资源类型
            context:       数据权限上下文，为None时仅做tenant_id隔离

        返回:
            添加了权限过滤条件的 Select 语句
        """
        ctx: DataPermissionContext | None = context
        if not ctx:
            tid = tenant_id_var.get("")
            if tid:
                stmt = stmt.where(model.tenant_id == tid)  # type: ignore[attr-defined]
            return stmt

        # 1. 基础租户隔离
        stmt = stmt.where(model.tenant_id == ctx.tenant_id)  # type: ignore[attr-defined]

        # 2. 获取数据范围过滤条件
        filters = ctx.get_filter_for_resource(resource_type)
        if not filters:
            return stmt

        # 3. 构建WHERE条件
        from sqlalchemy import or_
        conditions = []
        for field_name, value in filters.items():
            if field_name.endswith("__in"):
                actual_field = field_name.replace("__in", "")
                column = getattr(model, actual_field, None)
                if column is not None and value:
                    conditions.append(column.in_(value))
            elif field_name == "created_by" and value:
                column = getattr(model, field_name, None)
                if column is not None:
                    conditions.append(column == value)
            else:
                column = getattr(model, field_name, None)
                if column is not None and value:
                    conditions.append(column == value)

        if conditions:
            stmt = stmt.where(or_(*conditions) if len(conditions) > 1 else conditions[0])
        return stmt
