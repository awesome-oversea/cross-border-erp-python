from abc import ABC, abstractmethod
from collections.abc import Sequence

from erp.modules.ads.domain.models import AdCampaign, AdGroup, AdKeyword, AdReport


class AdCampaignRepository(ABC):
    @abstractmethod
    async def get_by_id(self, campaign_id: str, tenant_id: str) -> AdCampaign | None: ...

    @abstractmethod
    async def get_by_campaign_no(self, campaign_no: str, tenant_id: str) -> AdCampaign | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", platform: str = "", store_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[AdCampaign], int]: ...

    @abstractmethod
    async def create(self, campaign: AdCampaign) -> AdCampaign: ...

    @abstractmethod
    async def update(self, campaign: AdCampaign) -> AdCampaign: ...

    @abstractmethod
    async def soft_delete(self, campaign_id: str, tenant_id: str) -> bool: ...


class AdGroupRepository(ABC):
    @abstractmethod
    async def get_by_id(self, group_id: str, tenant_id: str) -> AdGroup | None: ...

    @abstractmethod
    async def list_by_campaign(self, campaign_id: str, tenant_id: str) -> Sequence[AdGroup]: ...

    @abstractmethod
    async def create(self, group: AdGroup) -> AdGroup: ...

    @abstractmethod
    async def update(self, group: AdGroup) -> AdGroup: ...


class AdKeywordRepository(ABC):
    @abstractmethod
    async def get_by_id(self, keyword_id: str, tenant_id: str) -> AdKeyword | None: ...

    @abstractmethod
    async def list_by_ad_group(self, ad_group_id: str, tenant_id: str) -> Sequence[AdKeyword]: ...

    @abstractmethod
    async def list_by_campaign(self, campaign_id: str, tenant_id: str) -> Sequence[AdKeyword]: ...

    @abstractmethod
    async def create(self, keyword: AdKeyword) -> AdKeyword: ...

    @abstractmethod
    async def update(self, keyword: AdKeyword) -> AdKeyword: ...


class AdReportRepository(ABC):
    @abstractmethod
    async def list_by_campaign(self, campaign_id: str, tenant_id: str,
                               start_date=None, end_date=None) -> Sequence[AdReport]: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, store_id: str = "", platform: str = "",
                             start_date=None, end_date=None,
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[AdReport], int]: ...

    @abstractmethod
    async def create(self, report: AdReport) -> AdReport: ...
