"""
SYS 模块依赖注入工厂 - 提供所有应用服务的 FastAPI Depends 工厂函数

本模块将仓储接口的创建与服务的组装集中管理，
路由层通过 Depends(get_xxx_service) 获取已注入仓储的服务实例，
实现控制反转（IoC）和依赖倒置（DIP）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends

from erp.modules.sys.application.services import (
    DraftDocumentService,
    InsightCardService,
    RecommendationService,
    RiskAlertService,
)
from erp.modules.sys.domain.repositories import (
    DraftDocumentRepository,
    InsightCardRepository,
    RecommendationRepository,
    RiskAlertRepository,
)
from erp.modules.sys.infrastructure.repositories import (
    SqlDraftDocumentRepository,
    SqlInsightCardRepository,
    SqlRecommendationRepository,
    SqlRiskAlertRepository,
)
from erp.shared.db.session import get_db_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _get_recommendation_repo(session: AsyncSession) -> RecommendationRepository:
    return SqlRecommendationRepository(session)


def _get_draft_repo(session: AsyncSession) -> DraftDocumentRepository:
    return SqlDraftDocumentRepository(session)


def _get_risk_alert_repo(session: AsyncSession) -> RiskAlertRepository:
    return SqlRiskAlertRepository(session)


def _get_insight_card_repo(session: AsyncSession) -> InsightCardRepository:
    return SqlInsightCardRepository(session)


async def get_recommendation_service(
    session: AsyncSession = Depends(get_db_session),
) -> RecommendationService:
    return RecommendationService(session=session, rec_repo=_get_recommendation_repo(session))


async def get_draft_service(
    session: AsyncSession = Depends(get_db_session),
) -> DraftDocumentService:
    return DraftDocumentService(session=session, draft_repo=_get_draft_repo(session))


async def get_risk_alert_service(
    session: AsyncSession = Depends(get_db_session),
) -> RiskAlertService:
    return RiskAlertService(session=session, alert_repo=_get_risk_alert_repo(session))


async def get_insight_card_service(
    session: AsyncSession = Depends(get_db_session),
) -> InsightCardService:
    return InsightCardService(session=session, card_repo=_get_insight_card_repo(session))
