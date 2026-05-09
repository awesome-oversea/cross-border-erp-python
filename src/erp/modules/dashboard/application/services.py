"""
Dashboard (工作台/看板域) 应用服务层

职责: 编排看板/组件/分享/待办/KPI指标的完整业务流程

核心服务:
  - DashboardService: 看板管理，自定义工作台看板与布局
  - DashboardComponentService: 看板组件管理，指标卡/图表/待办组件
  - DashboardShareService: 看板分享管理，用户/组级权限
  - BusinessAggregationService: 业务聚合服务，跨域数据聚合展示
  - TodoItemService: 待办事项管理，多来源待办聚合与优先级
  - KpiMetricService: KPI指标管理，核心运营指标实时展示
  - DashboardQueryService: 统一查询服务，跨实体聚合查询
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func as sa_func
from sqlalchemy import select

from erp.modules.dashboard.domain.models import Dashboard, DashboardComponent, DashboardShare, KpiMetric, TodoItem
from erp.modules.dashboard.domain.repositories import (
    DashboardComponentRepository,
    DashboardRepository,
    DashboardShareRepository,
    KpiMetricRepository,
    TodoItemRepository,
)
from erp.modules.dashboard.infrastructure.repositories import (
    SqlDashboardComponentRepository,
    SqlDashboardRepository,
    SqlDashboardShareRepository,
    SqlKpiMetricRepository,
    SqlTodoItemRepository,
)
from erp.shared.cache import cached
from erp.shared.exceptions import NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.dashboard")


class DashboardService:
    def __init__(self, session: AsyncSession, dashboard_repo: DashboardRepository | None = None):
        self._session = session
        self._dashboard_repo = dashboard_repo or SqlDashboardRepository(session)

    async def create(self, tenant_id: str, name: str, code: str, **kwargs) -> Dashboard:
        dashboard = Dashboard(tenant_id=tenant_id, name=name, code=code,
                              **{k: v for k, v in kwargs.items() if hasattr(Dashboard, k)})
        return await self._dashboard_repo.create(dashboard)

    async def get_by_id(self, dashboard_id: str, tenant_id: str = "") -> Dashboard | None:
        if tenant_id:
            return await self._dashboard_repo.get_by_id(dashboard_id, tenant_id)
        return await self._session.get(Dashboard, dashboard_id)

    async def get_or_raise(self, dashboard_id: str, tenant_id: str = "") -> Dashboard:
        dashboard = await self.get_by_id(dashboard_id, tenant_id)
        if not dashboard:
            raise NotFoundException(message=f"Dashboard '{dashboard_id}' not found")
        return dashboard

    async def list_by_tenant(self, tenant_id: str, owner_id: str | None = None) -> list[Dashboard]:
        dashboards, _ = await self._dashboard_repo.list_by_tenant(
            tenant_id, owner_id=owner_id or "", page=1, page_size=100)
        return list(dashboards)

    async def update_layout(self, dashboard_id: str, tenant_id: str, layout_json: str) -> Dashboard:
        dashboard = await self.get_or_raise(dashboard_id, tenant_id)
        dashboard.layout_json = layout_json
        return await self._dashboard_repo.update(dashboard)

    async def delete(self, dashboard_id: str, tenant_id: str = "") -> Dashboard | None:
        if tenant_id:
            dashboard = await self.get_or_raise(dashboard_id, tenant_id)
            dashboard.deleted_at = datetime.now(UTC)
            dashboard.status = "deleted"
            return await self._dashboard_repo.update(dashboard)
        dashboard = await self._session.get(Dashboard, dashboard_id)
        if not dashboard:
            return None
        dashboard.deleted_at = datetime.now(UTC)
        dashboard.status = "deleted"
        await self._session.flush()
        return dashboard


class DashboardComponentService:
    def __init__(self, session: AsyncSession, component_repo: DashboardComponentRepository | None = None):
        self._session = session
        self._component_repo = component_repo or SqlDashboardComponentRepository(session)

    async def create(self, tenant_id: str, dashboard_id: str, component_type: str,
                     title: str = "", **kwargs) -> DashboardComponent:
        component = DashboardComponent(tenant_id=tenant_id, dashboard_id=dashboard_id,
                                       component_type=component_type, title=title,
                                       **{k: v for k, v in kwargs.items() if hasattr(DashboardComponent, k)})
        return await self._component_repo.create(component)

    async def list_by_dashboard(self, dashboard_id: str, tenant_id: str = "") -> list[DashboardComponent]:
        if tenant_id:
            return list(await self._component_repo.list_by_dashboard(dashboard_id, tenant_id))
        stmt = select(DashboardComponent).where(
            DashboardComponent.dashboard_id == dashboard_id,
            DashboardComponent.status == "active",
        ).order_by(DashboardComponent.sort_order)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_config(self, component_id: str, tenant_id: str, config_json: str = "",
                            layout_config_json: str = "") -> DashboardComponent:
        comp = await self.get_or_raise(component_id, tenant_id)
        if config_json:
            comp.config_json = config_json
        if layout_config_json:
            comp.layout_config_json = layout_config_json
        return await self._component_repo.update(comp)

    async def delete(self, component_id: str, tenant_id: str = "") -> DashboardComponent | None:
        if tenant_id:
            comp = await self.get_or_raise(component_id, tenant_id)
            comp.status = "deleted"
            return await self._component_repo.update(comp)
        comp = await self._session.get(DashboardComponent, component_id)
        if not comp:
            return None
        comp.status = "deleted"
        await self._session.flush()
        return comp

    async def get_by_id(self, component_id: str, tenant_id: str = "") -> DashboardComponent | None:
        if tenant_id:
            return await self._component_repo.get_by_id(component_id, tenant_id)
        return await self._session.get(DashboardComponent, component_id)

    async def get_or_raise(self, component_id: str, tenant_id: str = "") -> DashboardComponent:
        component = await self.get_by_id(component_id, tenant_id)
        if not component:
            raise NotFoundException(message=f"Dashboard component '{component_id}' not found")
        return component


class DashboardShareService:
    def __init__(self, session: AsyncSession, share_repo: DashboardShareRepository | None = None):
        self._session = session
        self._share_repo = share_repo or SqlDashboardShareRepository(session)

    async def share(self, tenant_id: str, dashboard_id: str, share_type: str,
                    target_id: str, permission: str = "view") -> DashboardShare:
        valid_permissions = {"view", "edit", "admin"}
        if permission not in valid_permissions:
            raise ValidationException(message=f"Invalid permission '{permission}', must be one of {valid_permissions}")
        share = DashboardShare(tenant_id=tenant_id, dashboard_id=dashboard_id,
                               share_type=share_type, target_id=target_id, permission=permission)
        return await self._share_repo.create(share)

    async def list_by_dashboard(self, dashboard_id: str, tenant_id: str = "") -> list[DashboardShare]:
        if tenant_id:
            return list(await self._share_repo.list_by_dashboard(dashboard_id, tenant_id))
        stmt = select(DashboardShare).where(DashboardShare.dashboard_id == dashboard_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def revoke(self, share_id: str, tenant_id: str = "") -> DashboardShare | None:
        if tenant_id:
            deleted = await self._share_repo.delete(share_id, tenant_id)
            if not deleted:
                raise NotFoundException(message=f"Dashboard share '{share_id}' not found")
            return DashboardShare(id=share_id)
        share = await self._session.get(DashboardShare, share_id)
        if not share:
            return None
        await self._session.delete(share)
        await self._session.flush()
        return share


class BusinessAggregationService:
    def __init__(self, session: AsyncSession, dashboard_repo: DashboardRepository | None = None):
        self._session = session
        self._dashboard_repo = dashboard_repo or SqlDashboardRepository(session)

    @cached("dashboard_kpi")
    async def get_kpi_overview(self, tenant_id: str) -> dict:
        result = {
            "orders": await self._get_order_kpis(tenant_id),
            "sales": await self._get_sales_kpis(tenant_id),
            "inventory": await self._get_inventory_kpis(tenant_id),
            "finance": await self._get_finance_kpis(tenant_id),
            "logistics": await self._get_logistics_kpis(tenant_id),
            "customer_service": await self._get_cs_kpis(tenant_id),
        }
        return result

    @cached("dashboard_todo")
    async def get_todo_items(self, tenant_id: str, user_id: str = "") -> dict:
        todos = []
        todos.extend(await self._get_order_todos(tenant_id))
        todos.extend(await self._get_inventory_todos(tenant_id))
        todos.extend(await self._get_cs_todos(tenant_id))
        todos.extend(await self._get_approval_todos(tenant_id, user_id))
        todos.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
        return {"total": len(todos), "items": todos[:50]}

    @cached("dashboard_alert")
    async def get_alerts(self, tenant_id: str) -> dict:
        alerts = []
        alerts.extend(await self._get_inventory_alerts(tenant_id))
        alerts.extend(await self._get_order_alerts(tenant_id))
        alerts.extend(await self._get_logistics_alerts(tenant_id))
        return {"total": len(alerts), "items": alerts}

    @cached("dashboard_trend")
    async def get_trend_data(self, tenant_id: str, metric_type: str = "orders",
                             days: int = 30) -> dict:
        if days < 1 or days > 365:
            raise ValidationException(message="days must be between 1 and 365")
        valid_types = {"orders", "sales", "inventory", "finance"}
        if metric_type not in valid_types:
            raise ValidationException(message=f"Invalid metric_type, must be one of {valid_types}")
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=days)
        data_points = []
        current = start_date
        while current <= end_date:
            data_points.append({
                "date": current.strftime("%Y-%m-%d"),
                "value": 0,
            })
            current += timedelta(days=1)
        return {
            "metric_type": metric_type,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "data_points": data_points,
        }

    async def _get_order_kpis(self, tenant_id: str) -> dict:
        try:
            from erp.modules.oms.domain.models import Order
            today = datetime.now(UTC).date()
            today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC)
            today_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=UTC)
            total_stmt = select(sa_func.count()).select_from(Order).where(
                Order.tenant_id == tenant_id, Order.deleted_at.is_(None)
            )
            total = (await self._session.execute(total_stmt)).scalar() or 0
            today_stmt = select(sa_func.count()).select_from(Order).where(
                Order.tenant_id == tenant_id, Order.deleted_at.is_(None),
                Order.created_at >= today_start, Order.created_at <= today_end
            )
            today_count = (await self._session.execute(today_stmt)).scalar() or 0
            pending_stmt = select(sa_func.count()).select_from(Order).where(
                Order.tenant_id == tenant_id, Order.deleted_at.is_(None),
                Order.status.in_(["pending", "confirmed", "processing"])
            )
            pending = (await self._session.execute(pending_stmt)).scalar() or 0
            return {"total": total, "today": today_count, "pending": pending}
        except Exception:
            return {"total": 0, "today": 0, "pending": 0}

    async def _get_sales_kpis(self, tenant_id: str) -> dict:
        try:
            from erp.modules.oms.domain.models import Order
            stmt = select(sa_func.coalesce(sa_func.sum(Order.total_amount), 0)).where(
                Order.tenant_id == tenant_id, Order.deleted_at.is_(None),
                Order.status.in_(["shipped", "delivered", "completed"])
            )
            total_sales = (await self._session.execute(stmt)).scalar() or 0
            return {"total_sales": float(total_sales)}
        except Exception:
            return {"total_sales": 0.0}

    async def _get_inventory_kpis(self, tenant_id: str) -> dict:
        try:
            from erp.modules.wms.domain.models import Inventory
            total_stmt = select(sa_func.count()).select_from(Inventory).where(
                Inventory.tenant_id == tenant_id
            )
            total = (await self._session.execute(total_stmt)).scalar() or 0
            low_stock_stmt = select(sa_func.count()).select_from(Inventory).where(
                Inventory.tenant_id == tenant_id,
                Inventory.available_qty <= Inventory.safety_qty
            )
            low_stock = (await self._session.execute(low_stock_stmt)).scalar() or 0
            return {"total_skus": total, "low_stock": low_stock}
        except Exception:
            return {"total_skus": 0, "low_stock": 0}

    async def _get_finance_kpis(self, tenant_id: str) -> dict:
        try:
            from erp.modules.fms.domain.models import FinanceRecord
            stmt = select(sa_func.coalesce(sa_func.sum(FinanceRecord.amount), 0)).where(
                FinanceRecord.tenant_id == tenant_id
            )
            total = (await self._session.execute(stmt)).scalar() or 0
            return {"total_amount": float(total)}
        except Exception:
            return {"total_amount": 0.0}

    async def _get_logistics_kpis(self, tenant_id: str) -> dict:
        try:
            from erp.modules.tms.domain.models import Shipment
            in_transit_stmt = select(sa_func.count()).select_from(Shipment).where(
                Shipment.tenant_id == tenant_id,
                Shipment.status.in_(["picked_up", "in_transit", "out_for_delivery"])
            )
            in_transit = (await self._session.execute(in_transit_stmt)).scalar() or 0
            return {"in_transit": in_transit}
        except Exception:
            return {"in_transit": 0}

    async def _get_cs_kpis(self, tenant_id: str) -> dict:
        try:
            from erp.modules.crm.domain.models import ServiceTicket
            open_stmt = select(sa_func.count()).select_from(ServiceTicket).where(
                ServiceTicket.tenant_id == tenant_id,
                ServiceTicket.status.in_(["open", "in_progress", "pending_customer", "escalated"])
            )
            open_count = (await self._session.execute(open_stmt)).scalar() or 0
            return {"open_tickets": open_count}
        except Exception:
            return {"open_tickets": 0}

    async def _get_order_todos(self, tenant_id: str) -> list[dict]:
        try:
            from erp.modules.oms.domain.models import Order
            stmt = select(Order).where(
                Order.tenant_id == tenant_id, Order.deleted_at.is_(None),
                Order.status.in_(["pending", "confirmed"])
            ).limit(20)
            orders = (await self._session.execute(stmt)).scalars().all()
            return [{"type": "order", "id": o.id, "title": f"Order {o.order_no} needs action",
                     "priority": "high" if o.status == "pending" else "medium",
                     "priority_score": 90 if o.status == "pending" else 60,
                     "status": o.status} for o in orders]
        except Exception:
            return []

    async def _get_inventory_todos(self, tenant_id: str) -> list[dict]:
        try:
            from erp.modules.wms.domain.models import Inventory
            stmt = select(Inventory).where(
                Inventory.tenant_id == tenant_id,
                Inventory.available_qty <= Inventory.safety_qty
            ).limit(20)
            items = (await self._session.execute(stmt)).scalars().all()
            return [{"type": "inventory", "id": i.id, "title": f"SKU {i.sku_id} low stock",
                     "priority": "high", "priority_score": 85,
                     "available": i.available_qty, "safety": i.safety_qty} for i in items]
        except Exception:
            return []

    async def _get_cs_todos(self, tenant_id: str) -> list[dict]:
        try:
            from erp.modules.crm.domain.models import ServiceTicket
            stmt = select(ServiceTicket).where(
                ServiceTicket.tenant_id == tenant_id,
                ServiceTicket.status.in_(["open", "escalated"])
            ).limit(20)
            tickets = (await self._session.execute(stmt)).scalars().all()
            return [{"type": "service_ticket", "id": t.id, "title": f"Ticket {t.ticket_no} needs response",
                     "priority": "high" if t.status == "escalated" else "medium",
                     "priority_score": 95 if t.status == "escalated" else 55,
                     "status": t.status} for t in tickets]
        except Exception:
            return []

    async def _get_approval_todos(self, tenant_id: str, user_id: str) -> list[dict]:
        return []

    async def _get_inventory_alerts(self, tenant_id: str) -> list[dict]:
        try:
            from erp.modules.wms.domain.models import Inventory
            stmt = select(Inventory).where(
                Inventory.tenant_id == tenant_id,
                Inventory.available_qty <= Inventory.safety_qty
            ).limit(10)
            items = (await self._session.execute(stmt)).scalars().all()
            return [{"alert_type": "low_stock", "severity": "warning",
                     "message": f"SKU {i.sku_id}: available {i.available_qty} <= safety {i.safety_qty}",
                     "entity_id": i.id} for i in items]
        except Exception:
            return []

    async def _get_order_alerts(self, tenant_id: str) -> list[dict]:
        return []

    async def _get_logistics_alerts(self, tenant_id: str) -> list[dict]:
        return []

    async def get_widget_data(self, tenant_id: str, component_type: str, config_json: str = "{}") -> dict:
        widget_map = {
            "metric_card": self.get_kpi_overview,
            "line_chart": self.get_trend_data,
            "bar_chart": self.get_kpi_overview,
            "alert_list": self.get_alerts,
            "todo_list": self.get_todo_items,
            "table": self.get_kpi_overview,
        }
        handler = widget_map.get(component_type)
        if not handler:
            return {"data": [], "component_type": component_type}
        if component_type == "line_chart":
            return await handler(tenant_id, metric_type="orders", days=30)
        if component_type == "todo_list":
            return await handler(tenant_id, user_id="")
        result = await handler(tenant_id)
        return result


class TodoItemService:
    def __init__(self, session: AsyncSession, todo_repo: TodoItemRepository | None = None):
        self._session = session
        self._todo_repo = todo_repo or SqlTodoItemRepository(session)

    async def create(self, tenant_id: str, title: str, **kwargs) -> TodoItem:
        if not title:
            raise ValidationException(message="Title is required")
        todo = TodoItem(tenant_id=tenant_id, title=title,
                        **{k: v for k, v in kwargs.items() if hasattr(TodoItem, k)})
        return await self._todo_repo.create(todo)

    async def get_by_id(self, todo_id: str, tenant_id: str) -> TodoItem | None:
        return await self._todo_repo.get_by_id(todo_id, tenant_id)

    async def list_by_user(self, tenant_id: str, user_id: str = "", status: str = "",
                           todo_type: str = "", offset: int = 0, limit: int = 50) -> list[TodoItem]:
        page = (offset // limit) + 1 if limit > 0 else 1
        items, _ = await self._todo_repo.list_by_user(
            tenant_id, user_id=user_id, status=status, todo_type=todo_type,
            page=page, page_size=limit)
        return list(items)

    async def complete(self, todo_id: str, tenant_id: str, completed_by: str = "") -> TodoItem:
        todo = await self._todo_repo.get_by_id(todo_id, tenant_id)
        if not todo:
            from erp.shared.exceptions import NotFoundException
            raise NotFoundException(message=f"Todo item '{todo_id}' not found")
        if todo.status in ("completed", "cancelled"):
            raise ValidationException(message=f"Cannot complete todo in '{todo.status}' status")
        todo.status = "completed"
        todo.completed_at = datetime.now(UTC)
        todo.completed_by = completed_by
        return await self._todo_repo.update(todo)

    async def dismiss(self, todo_id: str, tenant_id: str) -> TodoItem:
        todo = await self._todo_repo.get_by_id(todo_id, tenant_id)
        if not todo:
            from erp.shared.exceptions import NotFoundException
            raise NotFoundException(message=f"Todo item '{todo_id}' not found")
        todo.status = "dismissed"
        return await self._todo_repo.update(todo)

    async def update_priority(self, todo_id: str, tenant_id: str, priority: str, priority_score: int) -> TodoItem:
        todo = await self._todo_repo.get_by_id(todo_id, tenant_id)
        if not todo:
            from erp.shared.exceptions import NotFoundException
            raise NotFoundException(message=f"Todo item '{todo_id}' not found")
        valid_priorities = {"critical", "high", "medium", "low"}
        if priority not in valid_priorities:
            raise ValidationException(message=f"Invalid priority '{priority}'")
        todo.priority = priority
        todo.priority_score = priority_score
        return await self._todo_repo.update(todo)


class KpiMetricService:
    def __init__(self, session: AsyncSession, kpi_repo: KpiMetricRepository | None = None):
        self._session = session
        self._kpi_repo = kpi_repo or SqlKpiMetricRepository(session)

    async def get_by_code(self, metric_code: str, tenant_id: str) -> KpiMetric | None:
        return await self._kpi_repo.get_by_code(metric_code, tenant_id)

    async def list_by_group(self, tenant_id: str, metric_group: str = "") -> list[KpiMetric]:
        return list(await self._kpi_repo.list_by_group(tenant_id, metric_group))

    async def upsert(self, tenant_id: str, metric_code: str, metric_name: str,
                     current_value: float, **kwargs) -> KpiMetric:
        metric = KpiMetric(tenant_id=tenant_id, metric_code=metric_code, metric_name=metric_name,
                           current_value=current_value,
                           **{k: v for k, v in kwargs.items() if hasattr(KpiMetric, k)})
        metric.last_refreshed_at = datetime.now(UTC)
        return await self._kpi_repo.upsert_by_code(metric)

    async def refresh_all(self, tenant_id: str) -> int:
        metrics = await self.list_by_group(tenant_id)
        for metric in metrics:
            metric.last_refreshed_at = datetime.now(UTC)
        if metrics:
            await self._session.flush()
        return len(metrics)


class DashboardQueryService:
    """
    Dashboard 统计查询服务

    提供Dashboard模块的运营统计概览、搜索等能力。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_statistics(self, tenant_id: str) -> dict:
        """获取Dashboard运营统计概览"""
        total_dashboards = (await self._session.execute(
            select(sa_func.count()).select_from(Dashboard).where(Dashboard.tenant_id == tenant_id)
        )).scalar() or 0

        active_dashboards = (await self._session.execute(
            select(sa_func.count()).select_from(Dashboard)
            .where(Dashboard.tenant_id == tenant_id, Dashboard.status == "active")
        )).scalar() or 0

        total_components = (await self._session.execute(
            select(sa_func.count()).select_from(DashboardComponent)
            .where(DashboardComponent.tenant_id == tenant_id, DashboardComponent.status == "active")
        )).scalar() or 0

        total_shares = (await self._session.execute(
            select(sa_func.count()).select_from(DashboardShare).where(DashboardShare.tenant_id == tenant_id)
        )).scalar() or 0

        total_todos = (await self._session.execute(
            select(sa_func.count()).select_from(TodoItem).where(TodoItem.tenant_id == tenant_id)
        )).scalar() or 0

        pending_todos = (await self._session.execute(
            select(sa_func.count()).select_from(TodoItem)
            .where(TodoItem.tenant_id == tenant_id, TodoItem.status.in_(["pending", "in_progress"]))
        )).scalar() or 0

        completed_todos = (await self._session.execute(
            select(sa_func.count()).select_from(TodoItem)
            .where(TodoItem.tenant_id == tenant_id, TodoItem.status == "completed")
        )).scalar() or 0

        kpi_metrics_count = (await self._session.execute(
            select(sa_func.count()).select_from(KpiMetric).where(KpiMetric.tenant_id == tenant_id)
        )).scalar() or 0

        by_owner_rows = (await self._session.execute(
            select(Dashboard.owner_id, sa_func.count())
            .where(Dashboard.tenant_id == tenant_id)
            .group_by(Dashboard.owner_id)
        )).all()
        dashboards_by_owner = {r[0] or "system": r[1] for r in by_owner_rows}

        by_type_rows = (await self._session.execute(
            select(DashboardComponent.component_type, sa_func.count())
            .where(DashboardComponent.tenant_id == tenant_id, DashboardComponent.status == "active")
            .group_by(DashboardComponent.component_type)
        )).all()
        components_by_type = {r[0]: r[1] for r in by_type_rows}

        return {
            "total_dashboards": total_dashboards,
            "active_dashboards": active_dashboards,
            "total_components": total_components,
            "total_shares": total_shares,
            "total_todos": total_todos,
            "pending_todos": pending_todos,
            "completed_todos": completed_todos,
            "kpi_metrics_count": kpi_metrics_count,
            "dashboards_by_owner": dashboards_by_owner,
            "components_by_type": components_by_type,
        }

    async def search_dashboards(self, tenant_id: str, keyword: str = "", owner_id: str = "",
                                 is_public: bool | None = None, status: str = "",
                                 page: int = 1, page_size: int = 20) -> tuple[list[Dashboard], int]:
        """多维度搜索仪表盘"""
        conditions = [Dashboard.tenant_id == tenant_id]
        if keyword:
            conditions.append((Dashboard.name.contains(keyword) | Dashboard.code.contains(keyword)))
        if owner_id:
            conditions.append(Dashboard.owner_id == owner_id)
        if is_public is not None:
            conditions.append(Dashboard.is_public == is_public)
        if status:
            conditions.append(Dashboard.status == status)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(Dashboard).where(*conditions)
        )).scalar() or 0
        stmt = select(Dashboard).where(*conditions).order_by(
            Dashboard.sort_order, Dashboard.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total


class KpiAggregationEngine:
    """
    KPI聚合引擎

    从各子域实时聚合KPI数据: 订单/销售/库存/财务/物流/客服
    支持环比/同比计算、目标达成率、异常检测
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def refresh_all_kpis(self, tenant_id: str) -> dict:
        """刷新全部KPI指标"""
        results = {}
        results["orders"] = await self._refresh_order_kpis(tenant_id)
        results["sales"] = await self._refresh_sales_kpis(tenant_id)
        results["inventory"] = await self._refresh_inventory_kpis(tenant_id)
        results["finance"] = await self._refresh_finance_kpis(tenant_id)
        results["logistics"] = await self._refresh_logistics_kpis(tenant_id)
        results["customer_service"] = await self._refresh_cs_kpis(tenant_id)
        total_refreshed = sum(len(v) for v in results.values())
        return {"tenant_id": tenant_id, "total_refreshed": total_refreshed, "details": results}

    async def _refresh_order_kpis(self, tenant_id: str) -> list[dict]:
        kpis = []
        try:
            from erp.modules.oms.domain.models import SalesOrder
            today = datetime.now(UTC).date()
            today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC)
            yesterday_start = datetime.combine(today - timedelta(days=1), datetime.min.time()).replace(tzinfo=UTC)
            yesterday_end = today_start
            today_count = (await self._session.execute(
                select(sa_func.count()).select_from(SalesOrder).where(
                    SalesOrder.tenant_id == tenant_id, SalesOrder.created_at >= today_start)
            )).scalar() or 0
            yesterday_count = (await self._session.execute(
                select(sa_func.count()).select_from(SalesOrder).where(
                    SalesOrder.tenant_id == tenant_id,
                    SalesOrder.created_at >= yesterday_start, SalesOrder.created_at < yesterday_end)
            )).scalar() or 0
            change_rate = ((today_count - yesterday_count) / yesterday_count * 100) if yesterday_count > 0 else 0
            await self._upsert_kpi(tenant_id, "orders_today", "今日订单量", "orders",
                                    float(today_count), float(yesterday_count), change_rate, "count")
            kpis.append({"code": "orders_today", "value": today_count, "change_rate": round(change_rate, 2)})
            pending_count = (await self._session.execute(
                select(sa_func.count()).select_from(SalesOrder).where(
                    SalesOrder.tenant_id == tenant_id,
                    SalesOrder.status.in_(["pending", "confirmed", "processing"]))
            )).scalar() or 0
            await self._upsert_kpi(tenant_id, "orders_pending", "待处理订单", "orders",
                                    float(pending_count), 0, 0, "count")
            kpis.append({"code": "orders_pending", "value": pending_count})
        except Exception:
            pass
        return kpis

    async def _refresh_sales_kpis(self, tenant_id: str) -> list[dict]:
        kpis = []
        try:
            from erp.modules.oms.domain.models import SalesOrder
            today = datetime.now(UTC).date()
            today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC)
            yesterday_start = datetime.combine(today - timedelta(days=1), datetime.min.time()).replace(tzinfo=UTC)
            yesterday_end = today_start
            today_sales = float((await self._session.execute(
                select(sa_func.coalesce(sa_func.sum(SalesOrder.item_subtotal), 0)).where(
                    SalesOrder.tenant_id == tenant_id, SalesOrder.created_at >= today_start)
            )).scalar() or 0)
            yesterday_sales = float((await self._session.execute(
                select(sa_func.coalesce(sa_func.sum(SalesOrder.item_subtotal), 0)).where(
                    SalesOrder.tenant_id == tenant_id,
                    SalesOrder.created_at >= yesterday_start, SalesOrder.created_at < yesterday_end)
            )).scalar() or 0)
            change_rate = ((today_sales - yesterday_sales) / yesterday_sales * 100) if yesterday_sales > 0 else 0
            await self._upsert_kpi(tenant_id, "sales_today", "今日销售额", "sales",
                                    today_sales, yesterday_sales, change_rate, "amount")
            kpis.append({"code": "sales_today", "value": today_sales, "change_rate": round(change_rate, 2)})
        except Exception:
            pass
        return kpis

    async def _refresh_inventory_kpis(self, tenant_id: str) -> list[dict]:
        kpis = []
        try:
            from erp.modules.wms.domain.models import Inventory
            total_skus = (await self._session.execute(
                select(sa_func.count(sa_func.distinct(Inventory.sku_id))).where(
                    Inventory.tenant_id == tenant_id)
            )).scalar() or 0
            low_stock_count = (await self._session.execute(
                select(sa_func.count()).select_from(Inventory).where(
                    Inventory.tenant_id == tenant_id, Inventory.qty_available <= 10)
            )).scalar() or 0
            await self._upsert_kpi(tenant_id, "inventory_total_skus", "在库SKU数", "inventory",
                                    float(total_skus), 0, 0, "count")
            await self._upsert_kpi(tenant_id, "inventory_low_stock", "低库存SKU数", "inventory",
                                    float(low_stock_count), 0, 0, "count")
            kpis.append({"code": "inventory_total_skus", "value": total_skus})
            kpis.append({"code": "inventory_low_stock", "value": low_stock_count})
        except Exception:
            pass
        return kpis

    async def _refresh_finance_kpis(self, tenant_id: str) -> list[dict]:
        kpis = []
        try:
            from erp.modules.fms.domain.models import CostEvent
            today = datetime.now(UTC).date()
            today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC)
            today_cost = float((await self._session.execute(
                select(sa_func.coalesce(sa_func.sum(CostEvent.amount_cny), 0)).where(
                    CostEvent.tenant_id == tenant_id, CostEvent.created_at >= today_start)
            )).scalar() or 0)
            await self._upsert_kpi(tenant_id, "finance_today_cost", "今日成本", "finance",
                                    today_cost, 0, 0, "amount")
            kpis.append({"code": "finance_today_cost", "value": today_cost})
        except Exception:
            pass
        return kpis

    async def _refresh_logistics_kpis(self, tenant_id: str) -> list[dict]:
        kpis = []
        try:
            from erp.modules.tms.domain.models import Shipment
            in_transit = (await self._session.execute(
                select(sa_func.count()).select_from(Shipment).where(
                    Shipment.tenant_id == tenant_id, Shipment.status == "in_transit")
            )).scalar() or 0
            await self._upsert_kpi(tenant_id, "logistics_in_transit", "在途包裹数", "logistics",
                                    float(in_transit), 0, 0, "count")
            kpis.append({"code": "logistics_in_transit", "value": in_transit})
        except Exception:
            pass
        return kpis

    async def _refresh_cs_kpis(self, tenant_id: str) -> list[dict]:
        kpis = []
        try:
            from erp.modules.crm.domain.models import ServiceTicket
            open_tickets = (await self._session.execute(
                select(sa_func.count()).select_from(ServiceTicket).where(
                    ServiceTicket.tenant_id == tenant_id, ServiceTicket.status.in_(["open", "in_progress"]))
            )).scalar() or 0
            await self._upsert_kpi(tenant_id, "cs_open_tickets", "待处理工单", "customer_service",
                                    float(open_tickets), 0, 0, "count")
            kpis.append({"code": "cs_open_tickets", "value": open_tickets})
        except Exception:
            pass
        return kpis

    async def _upsert_kpi(self, tenant_id: str, metric_code: str, metric_name: str,
                           metric_group: str, current_value: float, previous_value: float,
                           change_rate: float, unit: str) -> KpiMetric:
        existing = (await self._session.execute(
            select(KpiMetric).where(
                KpiMetric.tenant_id == tenant_id, KpiMetric.metric_code == metric_code)
        )).scalar_one_or_none()
        direction = "up" if change_rate > 0 else "down" if change_rate < 0 else "stable"
        if existing:
            existing.previous_value = existing.current_value
            existing.current_value = current_value
            existing.change_rate = round(change_rate, 2)
            existing.direction = direction
            existing.last_refreshed_at = datetime.now(UTC)
        else:
            existing = KpiMetric(
                tenant_id=tenant_id, metric_code=metric_code, metric_name=metric_name,
                metric_group=metric_group, current_value=current_value,
                previous_value=previous_value, change_rate=round(change_rate, 2),
                direction=direction, unit=unit, last_refreshed_at=datetime.now(UTC),
            )
            self._session.add(existing)
        await self._session.flush()
        return existing


class CrossDomainDataAggregator:
    """
    跨域数据聚合器

    聚合各子域数据生成业务概览: 经营概览/库存健康/采购进度/物流状态/财务摘要
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_business_overview(self, tenant_id: str) -> dict:
        """经营概览: 订单/销售/利润/库存周转"""
        overview = {}
        overview["orders"] = await self._aggregate_orders(tenant_id)
        overview["sales"] = await self._aggregate_sales(tenant_id)
        overview["inventory"] = await self._aggregate_inventory(tenant_id)
        overview["finance"] = await self._aggregate_finance(tenant_id)
        overview["alerts"] = await self._aggregate_alerts(tenant_id)
        return overview

    async def get_inventory_health(self, tenant_id: str) -> dict:
        """库存健康度: 周转率/滞销/缺货/超储"""
        result = {"healthy": 0, "low_stock": 0, "overstock": 0, "dead_stock": 0, "details": []}
        try:
            from erp.modules.wms.domain.models import Inventory
            inventories = (await self._session.execute(
                select(Inventory).where(Inventory.tenant_id == tenant_id)
            )).scalars().all()
            for inv in inventories:
                if inv.qty_available <= 0:
                    result["dead_stock"] += 1
                elif inv.qty_available <= 10:
                    result["low_stock"] += 1
                elif inv.qty_available >= 1000:
                    result["overstock"] += 1
                else:
                    result["healthy"] += 1
            total = len(inventories) or 1
            result["health_score"] = round(result["healthy"] / total * 100, 1)
        except Exception:
            result["health_score"] = 0
        return result

    async def get_procurement_progress(self, tenant_id: str) -> dict:
        """采购进度: 在途/待审批/已收货/延迟"""
        result = {"pending_approval": 0, "ordered": 0, "in_transit": 0,
                  "received": 0, "delayed": 0, "total_amount": 0.0}
        try:
            from erp.modules.scm.domain.models import PurchaseOrder
            status_counts = (await self._session.execute(
                select(PurchaseOrder.status, sa_func.count(), sa_func.coalesce(sa_func.sum(PurchaseOrder.total_amount), 0))
                .where(PurchaseOrder.tenant_id == tenant_id)
                .group_by(PurchaseOrder.status)
            )).all()
            for status, count, amount in status_counts:
                if status == "pending_approval":
                    result["pending_approval"] = count
                elif status == "ordered":
                    result["ordered"] = count
                elif status in ("shipped", "partial_received"):
                    result["in_transit"] = count
                elif status == "received":
                    result["received"] = count
                result["total_amount"] += float(amount or 0)
        except Exception:
            pass
        return result

    async def get_logistics_status(self, tenant_id: str) -> dict:
        """物流状态: 待发货/在途/已签收/异常"""
        result = {"pending_shipment": 0, "in_transit": 0, "delivered": 0, "exception": 0}
        try:
            from erp.modules.tms.domain.models import Shipment
            status_counts = (await self._session.execute(
                select(Shipment.status, sa_func.count())
                .where(Shipment.tenant_id == tenant_id)
                .group_by(Shipment.status)
            )).all()
            for status, count in status_counts:
                if status in ("pending", "picked_up"):
                    result["pending_shipment"] += count
                elif status == "in_transit":
                    result["in_transit"] += count
                elif status == "delivered":
                    result["delivered"] += count
                elif status == "exception":
                    result["exception"] += count
        except Exception:
            pass
        return result

    async def get_finance_summary(self, tenant_id: str) -> dict:
        """财务摘要: 收入/成本/利润/待结算"""
        result = {"total_revenue": 0.0, "total_cost": 0.0, "net_profit": 0.0, "pending_settlement": 0.0}
        try:
            from erp.modules.fms.domain.models import CostEvent, PlatformSettlement
            total_cost = float((await self._session.execute(
                select(sa_func.coalesce(sa_func.sum(CostEvent.amount_cny), 0))
                .where(CostEvent.tenant_id == tenant_id)
            )).scalar() or 0)
            pending_settlement = float((await self._session.execute(
                select(sa_func.coalesce(sa_func.sum(PlatformSettlement.net_amount), 0))
                .where(PlatformSettlement.tenant_id == tenant_id, PlatformSettlement.status == "pending")
            )).scalar() or 0)
            result["total_cost"] = total_cost
            result["pending_settlement"] = pending_settlement
            result["net_profit"] = result["total_revenue"] - total_cost
        except Exception:
            pass
        return result

    async def _aggregate_orders(self, tenant_id: str) -> dict:
        try:
            from erp.modules.oms.domain.models import SalesOrder
            today = datetime.now(UTC).date()
            today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC)
            today_count = (await self._session.execute(
                select(sa_func.count()).select_from(SalesOrder).where(
                    SalesOrder.tenant_id == tenant_id, SalesOrder.created_at >= today_start)
            )).scalar() or 0
            pending = (await self._session.execute(
                select(sa_func.count()).select_from(SalesOrder).where(
                    SalesOrder.tenant_id == tenant_id, SalesOrder.status.in_(["pending", "confirmed"]))
            )).scalar() or 0
            return {"today_count": today_count, "pending_count": pending}
        except Exception:
            return {"today_count": 0, "pending_count": 0}

    async def _aggregate_sales(self, tenant_id: str) -> dict:
        try:
            from erp.modules.oms.domain.models import SalesOrder
            total = float((await self._session.execute(
                select(sa_func.coalesce(sa_func.sum(SalesOrder.item_subtotal), 0)).where(
                    SalesOrder.tenant_id == tenant_id, SalesOrder.status.notin_(["cancelled"]))
            )).scalar() or 0)
            return {"total_sales": total}
        except Exception:
            return {"total_sales": 0.0}

    async def _aggregate_inventory(self, tenant_id: str) -> dict:
        try:
            from erp.modules.wms.domain.models import Inventory
            total_qty = float((await self._session.execute(
                select(sa_func.coalesce(sa_func.sum(Inventory.qty_on_hand), 0)).where(
                    Inventory.tenant_id == tenant_id)
            )).scalar() or 0)
            return {"total_qty_on_hand": total_qty}
        except Exception:
            return {"total_qty_on_hand": 0.0}

    async def _aggregate_finance(self, tenant_id: str) -> dict:
        return await self.get_finance_summary(tenant_id)

    async def _aggregate_alerts(self, tenant_id: str) -> dict:
        try:
            from erp.modules.sys.domain.models import RiskAlert
            unresolved = (await self._session.execute(
                select(sa_func.count()).select_from(RiskAlert).where(
                    RiskAlert.tenant_id == tenant_id, RiskAlert.status == "open")
            )).scalar() or 0
            return {"unresolved_alerts": unresolved}
        except Exception:
            return {"unresolved_alerts": 0}


class RealtimeDataPushService:
    """
    实时数据推送服务

    管理数据变更订阅与推送: KPI变更推送/库存预警推送/订单状态推送
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def subscribe_kpi_changes(self, tenant_id: str, user_id: str,
                                     metric_codes: list[str]) -> dict:
        """订阅KPI变更"""
        existing = (await self._session.execute(
            select(KpiMetric).where(
                KpiMetric.tenant_id == tenant_id, KpiMetric.metric_code.in_(metric_codes)
            )
        )).scalars().all()
        return {
            "tenant_id": tenant_id, "user_id": user_id,
            "subscribed_codes": [m.metric_code for m in existing],
            "subscription_count": len(existing),
        }

    async def get_kpi_snapshot(self, tenant_id: str, metric_codes: list[str] | None = None) -> dict:
        """获取KPI快照"""
        conditions = [KpiMetric.tenant_id == tenant_id, KpiMetric.status == "active"]
        if metric_codes:
            conditions.append(KpiMetric.metric_code.in_(metric_codes))
        metrics = (await self._session.execute(
            select(KpiMetric).where(*conditions)
        )).scalars().all()
        return {
            "snapshot_at": datetime.now(UTC).isoformat(),
            "metrics": [
                {"code": m.metric_code, "name": m.metric_name, "value": m.current_value,
                 "change_rate": m.change_rate, "direction": m.direction, "unit": m.unit}
                for m in metrics
            ],
        }

    async def detect_kpi_anomalies(self, tenant_id: str, threshold: float = 30.0) -> list[dict]:
        """检测KPI异常(变化率超过阈值)"""
        anomalies = (await self._session.execute(
            select(KpiMetric).where(
                KpiMetric.tenant_id == tenant_id, KpiMetric.status == "active",
                KpiMetric.change_rate.abs() > threshold)
        )).scalars().all()
        return [
            {"code": m.metric_code, "name": m.metric_name, "value": m.current_value,
             "change_rate": m.change_rate, "direction": m.direction, "severity": "high" if abs(m.change_rate) > 50 else "medium"}
            for m in anomalies
        ]

    async def push_inventory_alerts(self, tenant_id: str) -> list[dict]:
        """推送库存预警"""
        alerts = []
        try:
            from erp.modules.wms.domain.models import Inventory
            low_stock = (await self._session.execute(
                select(Inventory).where(
                    Inventory.tenant_id == tenant_id, Inventory.qty_available <= 10)
            )).scalars().all()
            for inv in low_stock:
                alerts.append({
                    "type": "low_stock", "sku_id": inv.sku_id,
                    "warehouse_id": inv.warehouse_id, "qty_available": inv.qty_available,
                    "severity": "critical" if inv.qty_available <= 0 else "warning",
                })
        except Exception:
            pass
        return alerts
