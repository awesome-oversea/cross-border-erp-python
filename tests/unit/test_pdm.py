from unittest.mock import AsyncMock, MagicMock

import pytest

from erp.modules.pdm.application.services import (
    PROJECT_STAGE_TRANSITIONS,
    SPU_STATUS_TRANSITIONS,
    ProductProjectService,
    SKUService,
    SPUService,
)
from erp.modules.pdm.domain.models import SPU, ProductProject
from erp.shared.exceptions import ValidationException


class TestSPUStatusTransitions:
    def test_draft_can_go_to_pending_review(self):
        assert "pending_review" in SPU_STATUS_TRANSITIONS["draft"]

    def test_pending_review_can_go_to_approved(self):
        assert "approved" in SPU_STATUS_TRANSITIONS["pending_review"]

    def test_approved_can_go_to_listed(self):
        assert "listed" in SPU_STATUS_TRANSITIONS["approved"]

    def test_listed_can_go_to_delisted(self):
        assert "delisted" in SPU_STATUS_TRANSITIONS["listed"]

    def test_discontinued_is_terminal(self):
        assert SPU_STATUS_TRANSITIONS["discontinued"] == []

    def test_cancelled_is_terminal(self):
        assert SPU_STATUS_TRANSITIONS["cancelled"] == []

    def test_rejected_can_go_back_to_draft(self):
        assert "draft" in SPU_STATUS_TRANSITIONS["rejected"]


class TestSPUStatusValidation:
    @pytest.mark.asyncio
    async def test_update_status_invalid_transition(self):
        mock_session = AsyncMock()
        spu = SPU(id="s1", tenant_id="t1", name="Test", code="SPU001", status="draft")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=spu))
        )
        svc = SPUService(mock_session)
        with pytest.raises(ValidationException, match="Cannot transition"):
            await svc.update_status("s1", "t1", "listed")

    @pytest.mark.asyncio
    async def test_update_status_pending_review_requires_name(self):
        mock_session = AsyncMock()
        spu = SPU(id="s1", tenant_id="t1", name="", code="SPU001", status="draft")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=spu))
        )
        svc = SPUService(mock_session)
        with pytest.raises(ValidationException, match="name"):
            await svc.update_status("s1", "t1", "pending_review")

    @pytest.mark.asyncio
    async def test_update_status_approved_requires_category(self):
        mock_session = AsyncMock()
        spu = SPU(id="s1", tenant_id="t1", name="Test", code="SPU001",
                   status="pending_review", category_id=None)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=spu))
        )
        svc = SPUService(mock_session)
        with pytest.raises(ValidationException, match="category"):
            await svc.update_status("s1", "t1", "approved")

    @pytest.mark.asyncio
    async def test_update_status_listed_requires_image(self):
        mock_session = AsyncMock()
        spu = SPU(id="s1", tenant_id="t1", name="Test", code="SPU001",
                   status="approved", category_id="c1", main_image="")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=spu))
        )
        svc = SPUService(mock_session)
        with pytest.raises(ValidationException, match="image"):
            await svc.update_status("s1", "t1", "listed")


class TestSKUValidation:
    @pytest.mark.asyncio
    async def test_create_sku_weight_exceeds_limit(self):
        mock_session = AsyncMock()
        spu = SPU(id="spu1", tenant_id="t1", name="Test", code="SPU001", status="draft")
        mock_session.get = AsyncMock(return_value=spu)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        svc = SKUService(mock_session)
        with pytest.raises(ValidationException, match="Weight"):
            await svc.create("t1", "spu1", "SKU001", weight=100.0)

    @pytest.mark.asyncio
    async def test_create_sku_negative_cost_price(self):
        mock_session = AsyncMock()
        spu = SPU(id="spu1", tenant_id="t1", name="Test", code="SPU001", status="draft")
        mock_session.get = AsyncMock(return_value=spu)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        svc = SKUService(mock_session)
        with pytest.raises(ValidationException, match="Cost price"):
            await svc.create("t1", "spu1", "SKU001", cost_price=-10.0)

    @pytest.mark.asyncio
    async def test_create_sku_for_discontinued_spu(self):
        mock_session = AsyncMock()
        spu = SPU(id="spu1", tenant_id="t1", name="Test", code="SPU001", status="discontinued")
        mock_session.get = AsyncMock(return_value=spu)
        svc = SKUService(mock_session)
        with pytest.raises(ValidationException, match="discontinued"):
            await svc.create("t1", "spu1", "SKU001")


class TestProjectStageTransitions:
    def test_proposing_can_go_to_researching(self):
        assert "researching" in PROJECT_STAGE_TRANSITIONS["proposing"]

    def test_completed_is_terminal(self):
        assert PROJECT_STAGE_TRANSITIONS["completed"] == []

    def test_cancelled_is_terminal(self):
        assert PROJECT_STAGE_TRANSITIONS["cancelled"] == []

    @pytest.mark.asyncio
    async def test_update_stage_invalid_transition(self):
        mock_session = AsyncMock()
        project = ProductProject(id="p1", tenant_id="t1", name="Test", code="PRJ001", stage="proposing")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=project))
        )
        svc = ProductProjectService(mock_session)
        with pytest.raises(ValidationException, match="Cannot transition"):
            await svc.update_stage("p1", "t1", "launched")
