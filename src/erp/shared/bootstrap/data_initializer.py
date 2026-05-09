from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from erp.modules.bi.domain.metric_alert_models import BusinessAlertService, MetricDefinitionService
from erp.modules.iam.domain.models import Organization, Role, Tenant, User
from erp.modules.sys.domain.dict_models import DataDictService
from erp.modules.sys.domain.doc_number_models import DocNumberService
from erp.modules.sys.domain.master_data_governance_models import MasterDataGovernanceService
from erp.modules.sys.domain.param_models import SysParamService
from erp.modules.sys.domain.pms_data_query_models import PMSDataQueryService
from erp.modules.tms.domain.logistics_connector_models import LogisticsConnectorService
from erp.shared.context import actor_id_var, tenant_id_var

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class DataInitializer:
    DEFAULT_TENANT_ID = "tenant-00000000-0000-0000-0000-000000000001"
    DEFAULT_ADMIN_USER_ID = "user-00000000-0000-0000-0000-000000000001"
    DEFAULT_ORG_ID = "org-00000000-0000-0000-0000-000000000001"
    DEFAULT_ROLE_ID = "role-00000000-0000-0000-0000-000000000001"

    def __init__(self, session: AsyncSession):
        self.session = session

    async def initialize_all(self) -> dict:
        results = {}
        results["tenant"] = await self._init_tenant()
        results["organization"] = await self._init_organization()
        results["roles"] = await self._init_roles()
        results["admin_user"] = await self._init_admin_user()
        results["dictionaries"] = await self._init_dictionaries()
        results["parameters"] = await self._init_parameters()
        results["doc_numbers"] = await self._init_doc_numbers()
        results["governance"] = await self._init_governance()
        results["pms_policies"] = await self._init_pms_policies()
        results["logistics_connectors"] = await self._init_logistics_connectors()
        results["metrics"] = await self._init_metrics()
        results["alerts"] = await self._init_alerts()
        return results

    async def _init_tenant(self) -> dict:
        from sqlalchemy import select
        stmt = select(Tenant).where(Tenant.id == self.DEFAULT_TENANT_ID)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return {"id": existing.id, "name": existing.name, "status": "already_exists"}

        tenant = Tenant(
            id=self.DEFAULT_TENANT_ID,
            name="默认租户",
            code="default",
            status="active",
            contact_email="admin@example.com",
            contact_phone="",
            max_users=100,
            max_stores=50,
            expires_at=None,
            contact_name="系统管理员",
            plan="enterprise",
        )
        self.session.add(tenant)
        await self.session.flush()
        return {"id": tenant.id, "name": tenant.name, "status": "created"}

    async def _init_organization(self) -> dict:
        from sqlalchemy import select
        stmt = select(Organization).where(Organization.id == self.DEFAULT_ORG_ID)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return {"id": existing.id, "name": existing.name, "status": "already_exists"}

        org = Organization(
            id=self.DEFAULT_ORG_ID,
            tenant_id=self.DEFAULT_TENANT_ID,
            name="总部",
            code="HQ",
            org_type="company",
            parent_id=None,
            status="active",
        )
        self.session.add(org)
        await self.session.flush()
        return {"id": org.id, "name": org.name, "status": "created"}

    async def _init_roles(self) -> dict:
        from sqlalchemy import select
        stmt = select(Role).where(Role.tenant_id == self.DEFAULT_TENANT_ID)
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none():
            return {"status": "already_exists"}

        roles_data = [
            ("super_admin", "超级管理员", "系统最高权限角色"),
            ("admin", "管理员", "租户管理员角色"),
            ("ops_manager", "运营经理", "运营管理角色"),
            ("ops_staff", "运营专员", "运营执行角色"),
            ("purchase_manager", "采购经理", "采购管理角色"),
            ("purchase_staff", "采购专员", "采购执行角色"),
            ("warehouse_manager", "仓库经理", "仓库管理角色"),
            ("warehouse_staff", "仓库专员", "仓库执行角色"),
            ("finance_manager", "财务经理", "财务管理角色"),
            ("finance_staff", "财务专员", "财务执行角色"),
            ("cs_manager", "客服经理", "客服管理角色"),
            ("cs_staff", "客服专员", "客服执行角色"),
            ("viewer", "只读用户", "只读查看角色"),
        ]
        created = []
        for code, name, desc in roles_data:
            role = Role(
                id=str(uuid.uuid4()),
                tenant_id=self.DEFAULT_TENANT_ID,
                name=name,
                code=code,
                description=desc,
            )
            self.session.add(role)
            created.append(code)
        await self.session.flush()
        return {"created": created}

    async def _init_admin_user(self) -> dict:
        from sqlalchemy import select
        stmt = select(User).where(User.id == self.DEFAULT_ADMIN_USER_ID)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return {"id": existing.id, "username": existing.username, "status": "already_exists"}

        from erp.modules.iam.domain.auth import hash_password
        password_hash = hash_password("Admin@123456")

        user = User(
            id=self.DEFAULT_ADMIN_USER_ID,
            tenant_id=self.DEFAULT_TENANT_ID,
            org_id=self.DEFAULT_ORG_ID,
            username="admin",
            email="admin@example.com",
            phone="",
            password_hash=password_hash,
            display_name="系统管理员",
            status="active",
            user_type="internal",
        )
        self.session.add(user)
        await self.session.flush()
        return {"id": user.id, "username": user.username, "status": "created"}

    async def _init_dictionaries(self) -> dict:
        tenant_id_var.set(self.DEFAULT_TENANT_ID)
        actor_id_var.set(self.DEFAULT_ADMIN_USER_ID)
        svc = DataDictService(self.session)
        await svc.init_defaults(self.DEFAULT_TENANT_ID)
        return {"initialized": True}

    async def _init_parameters(self) -> dict:
        svc = SysParamService(self.session)
        await svc.init_defaults(self.DEFAULT_TENANT_ID)
        return {"initialized": True}

    async def _init_doc_numbers(self) -> dict:
        svc = DocNumberService(self.session)
        await svc.init_defaults(self.DEFAULT_TENANT_ID)
        return {"initialized": True}

    async def _init_governance(self) -> dict:
        svc = MasterDataGovernanceService(self.session)
        rules = await svc.init_default_rules(self.DEFAULT_TENANT_ID)
        return {"initialized_count": len(rules)}

    async def _init_pms_policies(self) -> dict:
        svc = PMSDataQueryService(self.session)
        policies = await svc.init_default_policies(self.DEFAULT_TENANT_ID)
        return {"initialized_count": len(policies)}

    async def _init_logistics_connectors(self) -> dict:
        svc = LogisticsConnectorService(self.session)
        connectors = await svc.init_default_connectors(self.DEFAULT_TENANT_ID)
        return {"initialized_count": len(connectors)}

    async def _init_metrics(self) -> dict:
        svc = MetricDefinitionService(self.session)
        metrics = await svc.init_default_metrics()
        return {"initialized_count": len(metrics)}

    async def _init_alerts(self) -> dict:
        svc = BusinessAlertService(self.session)
        alerts = await svc.init_default_alerts(self.DEFAULT_TENANT_ID)
        return {"initialized_count": len(alerts)}
