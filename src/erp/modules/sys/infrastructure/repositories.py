"""
SYS 模块基础设施层 - 仓储的 SQLAlchemy 实现

每个仓储类继承 domain.repositories 中对应的抽象接口，
使用 SQLAlchemy AsyncSession 完成具体的数据库操作。
"""
from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING

from sqlalchemy import func as sa_func
from sqlalchemy import select

from erp.modules.sys.domain.dict_models import DictItem, DictType
from erp.modules.sys.domain.models import DraftDocument, InsightCard, Recommendation, RiskAlert
from erp.modules.sys.domain.param_models import SysParam
from erp.modules.sys.domain.repositories import (
    BizRuleRepository as AbstractBizRuleRepository,
    DictRepository as AbstractDictRepository,
    DraftDocumentRepository as AbstractDraftDocumentRepository,
    InsightCardRepository as AbstractInsightCardRepository,
    RecommendationRepository as AbstractRecommendationRepository,
    RiskAlertRepository as AbstractRiskAlertRepository,
    SysParamRepository as AbstractSysParamRepository,
)
from erp.modules.sys.domain.rule_models import BizRule

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlRecommendationRepository(AbstractRecommendationRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, rec: Recommendation) -> Recommendation:
        self._session.add(rec)
        await self._session.flush()
        return rec

    async def get_by_id(self, rec_id: str, tenant_id: str) -> Recommendation | None:
        stmt = select(Recommendation).where(Recommendation.id == rec_id, Recommendation.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_recommendation_id(self, recommendation_id: str, tenant_id: str) -> Recommendation | None:
        stmt = select(Recommendation).where(
            Recommendation.recommendation_id == recommendation_id, Recommendation.tenant_id == tenant_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_domain(self, tenant_id: str, domain: str = "", status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[list[Recommendation], int]:
        conditions = [Recommendation.tenant_id == tenant_id]
        if domain:
            conditions.append(Recommendation.domain == domain)
        if status:
            conditions.append(Recommendation.status == status)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(Recommendation).where(*conditions))).scalar() or 0
        stmt = select(Recommendation).where(*conditions).order_by(
            Recommendation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return list((await self._session.execute(stmt)).scalars().all()), total

    async def update_status(self, rec_id: str, tenant_id: str, status: str, **kwargs) -> Recommendation | None:
        rec = await self.get_by_id(rec_id, tenant_id)
        if not rec:
            return None
        rec.status = status
        for k, v in kwargs.items():
            if hasattr(rec, k):
                setattr(rec, k, v)
        await self._session.flush()
        return rec

    async def check_idempotency(self, idempotency_key: str, tenant_id: str) -> Recommendation | None:
        if not idempotency_key:
            return None
        stmt = select(Recommendation).where(
            Recommendation.idempotency_key == idempotency_key, Recommendation.tenant_id == tenant_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()


class SqlDraftDocumentRepository(AbstractDraftDocumentRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, draft: DraftDocument) -> DraftDocument:
        self._session.add(draft)
        await self._session.flush()
        return draft

    async def get_by_id(self, draft_id: str, tenant_id: str) -> DraftDocument | None:
        stmt = select(DraftDocument).where(DraftDocument.id == draft_id, DraftDocument.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_recommendation(self, recommendation_id: str, tenant_id: str) -> list[DraftDocument]:
        stmt = select(DraftDocument).where(
            DraftDocument.recommendation_id == recommendation_id, DraftDocument.tenant_id == tenant_id
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def update_status(self, draft_id: str, tenant_id: str, status: str, **kwargs) -> DraftDocument | None:
        draft = await self.get_by_id(draft_id, tenant_id)
        if not draft:
            return None
        draft.status = status
        for k, v in kwargs.items():
            if hasattr(draft, k):
                setattr(draft, k, v)
        await self._session.flush()
        return draft


class SqlDictRepository(AbstractDictRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_type(self, dict_type: DictType) -> DictType:
        self._session.add(dict_type)
        await self._session.flush()
        return dict_type

    async def get_type_by_code(self, code: str, tenant_id: str) -> DictType | None:
        stmt = select(DictType).where(DictType.code == code, DictType.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_types(self, tenant_id: str, page: int = 1, page_size: int = 50) -> tuple[list[DictType], int]:
        conditions = [DictType.tenant_id == tenant_id]
        total = (await self._session.execute(
            select(sa_func.count()).select_from(DictType).where(*conditions))).scalar() or 0
        stmt = select(DictType).where(*conditions).offset((page - 1) * page_size).limit(page_size)
        return list((await self._session.execute(stmt)).scalars().all()), total

    async def create_item(self, item: DictItem) -> DictItem:
        self._session.add(item)
        await self._session.flush()
        return item

    async def list_items_by_type(self, type_code: str, tenant_id: str) -> list[DictItem]:
        stmt = select(DictItem).where(DictItem.type_code == type_code, DictItem.tenant_id == tenant_id)
        return list((await self._session.execute(stmt)).scalars().all())


class SqlSysParamRepository(AbstractSysParamRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, param: SysParam) -> SysParam:
        self._session.add(param)
        await self._session.flush()
        return param

    async def get_by_key(self, param_key: str, tenant_id: str) -> SysParam | None:
        stmt = select(SysParam).where(SysParam.param_key == param_key, SysParam.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_all(self, tenant_id: str, page: int = 1, page_size: int = 50) -> tuple[list[SysParam], int]:
        conditions = [SysParam.tenant_id == tenant_id]
        total = (await self._session.execute(
            select(sa_func.count()).select_from(SysParam).where(*conditions))).scalar() or 0
        stmt = select(SysParam).where(*conditions).offset((page - 1) * page_size).limit(page_size)
        return list((await self._session.execute(stmt)).scalars().all()), total

    async def update_value(self, param_key: str, tenant_id: str, param_value: str) -> SysParam | None:
        param = await self.get_by_key(param_key, tenant_id)
        if not param:
            return None
        param.param_value = param_value
        await self._session.flush()
        return param


class SqlBizRuleRepository(AbstractBizRuleRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, rule: BizRule) -> BizRule:
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def get_by_id(self, rule_id: str, tenant_id: str) -> BizRule | None:
        stmt = select(BizRule).where(BizRule.id == rule_id, BizRule.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_all(self, tenant_id: str, domain: str = "",
                       page: int = 1, page_size: int = 50) -> tuple[list[BizRule], int]:
        conditions = [BizRule.tenant_id == tenant_id]
        if domain:
            conditions.append(BizRule.domain == domain)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(BizRule).where(*conditions))).scalar() or 0
        stmt = select(BizRule).where(*conditions).offset((page - 1) * page_size).limit(page_size)
        return list((await self._session.execute(stmt)).scalars().all()), total

    async def update(self, rule_id: str, tenant_id: str, **kwargs) -> BizRule | None:
        rule = await self.get_by_id(rule_id, tenant_id)
        if not rule:
            return None
        for k, v in kwargs.items():
            if hasattr(rule, k):
                setattr(rule, k, v)
        await self._session.flush()
        return rule


class SqlRiskAlertRepository(AbstractRiskAlertRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, alert: RiskAlert) -> RiskAlert:
        self._session.add(alert)
        await self._session.flush()
        return alert

    async def get_by_id(self, alert_id: str, tenant_id: str) -> RiskAlert | None:
        stmt = select(RiskAlert).where(RiskAlert.id == alert_id, RiskAlert.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_open(self, tenant_id: str, domain: str = "",
                        page: int = 1, page_size: int = 20) -> tuple[list[RiskAlert], int]:
        conditions = [RiskAlert.tenant_id == tenant_id, RiskAlert.status == "open"]
        if domain:
            conditions.append(RiskAlert.domain == domain)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(RiskAlert).where(*conditions))).scalar() or 0
        stmt = select(RiskAlert).where(*conditions).order_by(
            RiskAlert.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return list((await self._session.execute(stmt)).scalars().all()), total

    async def resolve(self, alert_id: str, tenant_id: str, resolution: str) -> RiskAlert | None:
        alert = await self.get_by_id(alert_id, tenant_id)
        if not alert:
            return None
        alert.status = "resolved"
        alert.resolution = resolution
        await self._session.flush()
        return alert


class SqlInsightCardRepository(AbstractInsightCardRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, card: InsightCard) -> InsightCard:
        self._session.add(card)
        await self._session.flush()
        return card

    async def list_active(self, tenant_id: str, domain: str = "",
                          page: int = 1, page_size: int = 20) -> tuple[list[InsightCard], int]:
        conditions = [InsightCard.tenant_id == tenant_id, InsightCard.status == "active"]
        if domain:
            conditions.append(InsightCard.domain == domain)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(InsightCard).where(*conditions))).scalar() or 0
        stmt = select(InsightCard).where(*conditions).order_by(
            InsightCard.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return list((await self._session.execute(stmt)).scalars().all()), total

    async def archive(self, card_id: str, tenant_id: str) -> InsightCard | None:
        from datetime import datetime
        stmt = select(InsightCard).where(InsightCard.id == card_id, InsightCard.tenant_id == tenant_id)
        card = (await self._session.execute(stmt)).scalar_one_or_none()
        if not card:
            return None
        card.status = "archived"
        card.archived_at = datetime.now(UTC)
        await self._session.flush()
        return card
