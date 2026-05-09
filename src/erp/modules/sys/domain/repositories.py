"""
SYS 模块抽象仓储接口 - 定义数据访问的抽象契约

本模块声明了 SYS 域所有聚合根的仓储接口，
遵循依赖倒置原则（DIP），应用层和领域层依赖抽象而非具体实现。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from erp.modules.sys.domain.dict_models import DictItem, DictType
from erp.modules.sys.domain.models import DraftDocument, InsightCard, Recommendation, RiskAlert
from erp.modules.sys.domain.param_models import SysParam
from erp.modules.sys.domain.rule_models import BizRule


class RecommendationRepository(ABC):
    @abstractmethod
    async def create(self, rec: Recommendation) -> Recommendation: ...

    @abstractmethod
    async def get_by_id(self, rec_id: str, tenant_id: str) -> Recommendation | None: ...

    @abstractmethod
    async def get_by_recommendation_id(self, recommendation_id: str, tenant_id: str) -> Recommendation | None: ...

    @abstractmethod
    async def list_by_domain(self, tenant_id: str, domain: str = "", status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Recommendation], int]: ...

    @abstractmethod
    async def update_status(self, rec_id: str, tenant_id: str, status: str, **kwargs) -> Recommendation | None: ...

    @abstractmethod
    async def check_idempotency(self, idempotency_key: str, tenant_id: str) -> Recommendation | None: ...


class DraftDocumentRepository(ABC):
    @abstractmethod
    async def create(self, draft: DraftDocument) -> DraftDocument: ...

    @abstractmethod
    async def get_by_id(self, draft_id: str, tenant_id: str) -> DraftDocument | None: ...

    @abstractmethod
    async def list_by_recommendation(self, recommendation_id: str, tenant_id: str) -> Sequence[DraftDocument]: ...

    @abstractmethod
    async def update_status(self, draft_id: str, tenant_id: str, status: str, **kwargs) -> DraftDocument | None: ...


class RiskAlertRepository(ABC):
    @abstractmethod
    async def create(self, alert: RiskAlert) -> RiskAlert: ...

    @abstractmethod
    async def get_by_id(self, alert_id: str, tenant_id: str) -> RiskAlert | None: ...

    @abstractmethod
    async def list_open(self, tenant_id: str, domain: str = "",
                        page: int = 1, page_size: int = 20) -> tuple[Sequence[RiskAlert], int]: ...

    @abstractmethod
    async def resolve(self, alert_id: str, tenant_id: str, resolution: str) -> RiskAlert | None: ...


class InsightCardRepository(ABC):
    @abstractmethod
    async def create(self, card: InsightCard) -> InsightCard: ...

    @abstractmethod
    async def list_active(self, tenant_id: str, domain: str = "",
                          page: int = 1, page_size: int = 20) -> tuple[Sequence[InsightCard], int]: ...

    @abstractmethod
    async def archive(self, card_id: str, tenant_id: str) -> InsightCard | None: ...


class DictRepository(ABC):
    @abstractmethod
    async def create_type(self, dict_type: DictType) -> DictType: ...

    @abstractmethod
    async def get_type_by_code(self, code: str, tenant_id: str) -> DictType | None: ...

    @abstractmethod
    async def list_types(self, tenant_id: str, page: int = 1, page_size: int = 50) -> tuple[Sequence[DictType], int]: ...

    @abstractmethod
    async def create_item(self, item: DictItem) -> DictItem: ...

    @abstractmethod
    async def list_items_by_type(self, type_code: str, tenant_id: str) -> Sequence[DictItem]: ...


class SysParamRepository(ABC):
    @abstractmethod
    async def create(self, param: SysParam) -> SysParam: ...

    @abstractmethod
    async def get_by_key(self, param_key: str, tenant_id: str) -> SysParam | None: ...

    @abstractmethod
    async def list_all(self, tenant_id: str, page: int = 1, page_size: int = 50) -> tuple[Sequence[SysParam], int]: ...

    @abstractmethod
    async def update_value(self, param_key: str, tenant_id: str, param_value: str) -> SysParam | None: ...


class BizRuleRepository(ABC):
    @abstractmethod
    async def create(self, rule: BizRule) -> BizRule: ...

    @abstractmethod
    async def get_by_id(self, rule_id: str, tenant_id: str) -> BizRule | None: ...

    @abstractmethod
    async def list_all(self, tenant_id: str, domain: str = "",
                       page: int = 1, page_size: int = 50) -> tuple[Sequence[BizRule], int]: ...

    @abstractmethod
    async def update(self, rule_id: str, tenant_id: str, **kwargs) -> BizRule | None: ...
