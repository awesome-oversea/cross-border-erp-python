from unittest.mock import AsyncMock, MagicMock

import pytest

from erp.modules.dashboard.application.services import (
    BusinessAggregationService,
    DashboardComponentService,
    DashboardService,
    DashboardShareService,
)
from erp.modules.dashboard.domain.models import Dashboard, DashboardComponent, DashboardShare
from erp.shared.exceptions import ValidationException


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def dashboard_service(mock_session):
    return DashboardService(mock_session)


@pytest.fixture
def component_service(mock_session):
    return DashboardComponentService(mock_session)


@pytest.fixture
def share_service(mock_session):
    return DashboardShareService(mock_session)


@pytest.fixture
def aggregation_service(mock_session):
    return BusinessAggregationService(mock_session)


class TestDashboardService:
    @pytest.mark.asyncio
    async def test_create_dashboard(self, dashboard_service, mock_session):
        dashboard = await dashboard_service.create("t1", "Main Dashboard", "main_dash")
        assert dashboard.name == "Main Dashboard"
        assert dashboard.code == "main_dash"
        assert dashboard.tenant_id == "t1"

    @pytest.mark.asyncio
    async def test_delete_dashboard(self, dashboard_service, mock_session):
        db = Dashboard(id="d1", tenant_id="t1", name="Test", code="test")
        mock_session.get = AsyncMock(return_value=db)
        result = await dashboard_service.delete("d1")
        assert result.status == "deleted"
        assert result.deleted_at is not None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, dashboard_service, mock_session):
        mock_session.get = AsyncMock(return_value=None)
        result = await dashboard_service.delete("nonexistent")
        assert result is None


class TestDashboardComponentService:
    @pytest.mark.asyncio
    async def test_create_component(self, component_service, mock_session):
        comp = await component_service.create("t1", "d1", "metric_card", title="Sales KPI")
        assert comp.component_type == "metric_card"
        assert comp.title == "Sales KPI"

    @pytest.mark.asyncio
    async def test_delete_component(self, component_service, mock_session):
        comp = DashboardComponent(id="c1", tenant_id="t1", dashboard_id="d1",
                                   component_type="metric_card", title="Test")
        mock_session.get = AsyncMock(return_value=comp)
        result = await component_service.delete("c1")
        assert result.status == "deleted"


class TestDashboardShareService:
    @pytest.mark.asyncio
    async def test_share_with_invalid_permission(self, share_service, mock_session):
        with pytest.raises(ValidationException, match="Invalid permission"):
            await share_service.share("t1", "d1", "user", "u1", permission="delete")

    @pytest.mark.asyncio
    async def test_share_with_valid_permission(self, share_service, mock_session):
        share = await share_service.share("t1", "d1", "user", "u1", permission="view")
        assert share.permission == "view"

    @pytest.mark.asyncio
    async def test_revoke_share(self, share_service, mock_session):
        share = DashboardShare(id="s1", tenant_id="t1", dashboard_id="d1",
                               share_type="user", target_id="u1", permission="view")
        mock_session.get = AsyncMock(return_value=share)
        result = await share_service.revoke("s1")
        assert result is not None

    @pytest.mark.asyncio
    async def test_revoke_nonexistent(self, share_service, mock_session):
        mock_session.get = AsyncMock(return_value=None)
        result = await share_service.revoke("nonexistent")
        assert result is None


class TestBusinessAggregationService:
    @pytest.mark.asyncio
    async def test_get_kpi_overview_structure(self, aggregation_service, mock_session):
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=0)))
        result = await aggregation_service.get_kpi_overview("t1")
        assert "orders" in result
        assert "sales" in result
        assert "inventory" in result
        assert "finance" in result
        assert "logistics" in result
        assert "customer_service" in result

    @pytest.mark.asyncio
    async def test_get_todo_items_structure(self, aggregation_service, mock_session):
        mock_session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
        result = await aggregation_service.get_todo_items("t1")
        assert "total" in result
        assert "items" in result

    @pytest.mark.asyncio
    async def test_get_alerts_structure(self, aggregation_service, mock_session):
        mock_session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
        result = await aggregation_service.get_alerts("t1")
        assert "total" in result
        assert "items" in result

    @pytest.mark.asyncio
    async def test_get_trend_data_invalid_days(self, aggregation_service, mock_session):
        with pytest.raises(ValidationException, match="days must be between"):
            await aggregation_service.get_trend_data("t1", days=0)

    @pytest.mark.asyncio
    async def test_get_trend_data_invalid_metric(self, aggregation_service, mock_session):
        with pytest.raises(ValidationException, match="Invalid metric_type"):
            await aggregation_service.get_trend_data("t1", metric_type="invalid")

    @pytest.mark.asyncio
    async def test_get_trend_data_valid(self, aggregation_service, mock_session):
        result = await aggregation_service.get_trend_data("t1", metric_type="orders", days=7)
        assert result["metric_type"] == "orders"
        assert len(result["data_points"]) >= 7
