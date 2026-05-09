from unittest.mock import AsyncMock, MagicMock

import pytest

from erp.modules.crm.application.services import (
    TICKET_STATUS_TRANSITIONS,
    CustomerService,
    ServiceTicketService,
)
from erp.modules.crm.domain.models import ServiceTicket
from erp.shared.exceptions import ValidationException


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


class TestTicketStatusTransitions:
    def test_open_can_go_to_in_progress(self):
        assert "in_progress" in TICKET_STATUS_TRANSITIONS["open"]

    def test_in_progress_can_go_to_resolved(self):
        assert "resolved" in TICKET_STATUS_TRANSITIONS["in_progress"]

    def test_resolved_can_go_to_closed(self):
        assert "closed" in TICKET_STATUS_TRANSITIONS["resolved"]

    def test_resolved_can_go_to_reopened(self):
        assert "reopened" in TICKET_STATUS_TRANSITIONS["resolved"]

    def test_closed_can_go_to_reopened(self):
        assert "reopened" in TICKET_STATUS_TRANSITIONS["closed"]

    def test_cancelled_is_terminal(self):
        assert TICKET_STATUS_TRANSITIONS["cancelled"] == []


class TestServiceTicketService:
    @pytest.mark.asyncio
    async def test_update_status_invalid_transition(self, mock_session):
        svc = ServiceTicketService(mock_session)
        ticket = ServiceTicket(id="t1", tenant_id="t1", ticket_no="TK001",
                               customer_id="c1", status="open")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=ticket))
        )
        with pytest.raises(ValidationException, match="Cannot transition"):
            await svc.update_status("t1", "t1", "resolved")

    @pytest.mark.asyncio
    async def test_update_status_sets_first_response_at(self, mock_session):
        svc = ServiceTicketService(mock_session)
        ticket = ServiceTicket(id="t1", tenant_id="t1", ticket_no="TK001",
                               customer_id="c1", status="open", first_response_at=None)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=ticket))
        )
        result = await svc.update_status("t1", "t1", "in_progress")
        assert result.first_response_at is not None

    @pytest.mark.asyncio
    async def test_update_status_sets_resolved_at(self, mock_session):
        svc = ServiceTicketService(mock_session)
        ticket = ServiceTicket(id="t1", tenant_id="t1", ticket_no="TK001",
                               customer_id="c1", status="in_progress", resolved_at=None)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=ticket))
        )
        result = await svc.update_status("t1", "t1", "resolved")
        assert result.resolved_at is not None

    @pytest.mark.asyncio
    async def test_assign_ticket(self, mock_session):
        svc = ServiceTicketService(mock_session)
        ticket = ServiceTicket(id="t1", tenant_id="t1", ticket_no="TK001",
                               customer_id="c1", status="open", assigned_to="", assigned_group="")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=ticket))
        )
        result = await svc.assign("t1", "t1", "user1", "support")
        assert result.assigned_to == "user1"
        assert result.assigned_group == "support"


class TestCustomerSegmentation:
    def test_segment_calculation(self):
        svc = CustomerService.__new__(CustomerService)
        svc._session = None
        assert svc._calculate_segment(0, 0) == "normal"
        assert svc._calculate_segment(5, 500) == "regular"
        assert svc._calculate_segment(10, 5000) == "vip"
        assert svc._calculate_segment(30, 20000) == "vip"
