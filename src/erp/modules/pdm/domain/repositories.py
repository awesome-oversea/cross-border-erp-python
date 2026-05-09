from abc import ABC, abstractmethod
from collections.abc import Sequence

from erp.modules.pdm.domain.models import (
    SKU,
    SPU,
    Brand,
    BundleProduct,
    Category,
    ChannelSKUMapping,
    ImageLibrary,
    IPRecord,
    ProductIssue,
    ProductProject,
    QualityStandard,
    SensitiveWord,
    TitleLibrary,
    UPCPool,
)


class CategoryRepository(ABC):
    @abstractmethod
    async def get_by_id(self, cat_id: str, tenant_id: str) -> Category | None: ...

    @abstractmethod
    async def get_by_code(self, code: str, tenant_id: str) -> Category | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str) -> Sequence[Category]: ...

    @abstractmethod
    async def list_children(self, parent_id: str, tenant_id: str) -> Sequence[Category]: ...

    @abstractmethod
    async def create(self, category: Category) -> Category: ...

    @abstractmethod
    async def update(self, category: Category) -> Category: ...

    @abstractmethod
    async def soft_delete(self, cat_id: str, tenant_id: str) -> bool: ...


class BrandRepository(ABC):
    @abstractmethod
    async def get_by_id(self, brand_id: str, tenant_id: str) -> Brand | None: ...

    @abstractmethod
    async def get_by_code(self, code: str, tenant_id: str) -> Brand | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, page: int = 1, page_size: int = 20) -> tuple[Sequence[Brand], int]: ...

    @abstractmethod
    async def create(self, brand: Brand) -> Brand: ...

    @abstractmethod
    async def update(self, brand: Brand) -> Brand: ...

    @abstractmethod
    async def soft_delete(self, brand_id: str, tenant_id: str) -> bool: ...


class SPURepository(ABC):
    @abstractmethod
    async def get_by_id(self, spu_id: str, tenant_id: str) -> SPU | None: ...

    @abstractmethod
    async def get_by_code(self, code: str, tenant_id: str) -> SPU | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[SPU], int]: ...

    @abstractmethod
    async def create(self, spu: SPU) -> SPU: ...

    @abstractmethod
    async def update(self, spu: SPU) -> SPU: ...

    @abstractmethod
    async def soft_delete(self, spu_id: str, tenant_id: str) -> bool: ...


class SKURepository(ABC):
    @abstractmethod
    async def get_by_id(self, sku_id: str, tenant_id: str) -> SKU | None: ...

    @abstractmethod
    async def get_by_code(self, sku_code: str, tenant_id: str) -> SKU | None: ...

    @abstractmethod
    async def list_by_spu(self, spu_id: str, tenant_id: str) -> Sequence[SKU]: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, page: int = 1, page_size: int = 20) -> tuple[Sequence[SKU], int]: ...

    @abstractmethod
    async def create(self, sku: SKU) -> SKU: ...

    @abstractmethod
    async def update(self, sku: SKU) -> SKU: ...

    @abstractmethod
    async def soft_delete(self, sku_id: str, tenant_id: str) -> bool: ...


class ChannelSKUMappingRepository(ABC):
    @abstractmethod
    async def get_by_sku_and_channel(self, sku_id: str, channel: str, tenant_id: str) -> ChannelSKUMapping | None: ...

    @abstractmethod
    async def list_by_sku(self, sku_id: str, tenant_id: str) -> Sequence[ChannelSKUMapping]: ...

    @abstractmethod
    async def list_by_channel(self, channel: str, tenant_id: str) -> Sequence[ChannelSKUMapping]: ...

    @abstractmethod
    async def create(self, mapping: ChannelSKUMapping) -> ChannelSKUMapping: ...

    @abstractmethod
    async def update(self, mapping: ChannelSKUMapping) -> ChannelSKUMapping: ...

    @abstractmethod
    async def delete(self, mapping_id: str, tenant_id: str) -> bool: ...


class ProductProjectRepository(ABC):
    @abstractmethod
    async def get_by_id(self, project_id: str, tenant_id: str) -> ProductProject | None: ...

    @abstractmethod
    async def get_by_code(self, code: str, tenant_id: str) -> ProductProject | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, stage: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[ProductProject], int]: ...

    @abstractmethod
    async def create(self, project: ProductProject) -> ProductProject: ...

    @abstractmethod
    async def update(self, project: ProductProject) -> ProductProject: ...

    @abstractmethod
    async def soft_delete(self, project_id: str, tenant_id: str) -> bool: ...


class QualityStandardRepository(ABC):
    @abstractmethod
    async def get_by_id(self, qs_id: str, tenant_id: str) -> QualityStandard | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, category_id: str = "") -> Sequence[QualityStandard]: ...

    @abstractmethod
    async def create(self, qs: QualityStandard) -> QualityStandard: ...

    @abstractmethod
    async def update(self, qs: QualityStandard) -> QualityStandard: ...


class IPRecordRepository(ABC):
    @abstractmethod
    async def get_by_id(self, ip_id: str, tenant_id: str) -> IPRecord | None: ...

    @abstractmethod
    async def list_by_sku(self, sku_id: str, tenant_id: str) -> Sequence[IPRecord]: ...

    @abstractmethod
    async def list_by_spu(self, spu_id: str, tenant_id: str) -> Sequence[IPRecord]: ...

    @abstractmethod
    async def create(self, record: IPRecord) -> IPRecord: ...

    @abstractmethod
    async def update(self, record: IPRecord) -> IPRecord: ...


class SensitiveWordRepository(ABC):
    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, word_type: str = "", platform: str = "") -> Sequence[SensitiveWord]: ...

    @abstractmethod
    async def create(self, word: SensitiveWord) -> SensitiveWord: ...

    @abstractmethod
    async def delete(self, word_id: str, tenant_id: str) -> bool: ...


class UPCPoolRepository(ABC):
    @abstractmethod
    async def get_by_code(self, upc_code: str, tenant_id: str) -> UPCPool | None: ...

    @abstractmethod
    async def list_available(self, tenant_id: str, limit: int = 100) -> Sequence[UPCPool]: ...

    @abstractmethod
    async def create(self, upc: UPCPool) -> UPCPool: ...

    @abstractmethod
    async def allocate(self, upc_code: str, sku_id: str, tenant_id: str) -> UPCPool | None: ...

    @abstractmethod
    async def release(self, upc_code: str, tenant_id: str) -> bool: ...


class BundleProductRepository(ABC):
    """组合产品仓储接口 - Bundle的子SKU组成关系"""

    @abstractmethod
    async def list_by_spu(self, spu_id: str, tenant_id: str) -> Sequence[BundleProduct]: ...

    @abstractmethod
    async def create(self, bundle: BundleProduct) -> BundleProduct: ...

    @abstractmethod
    async def update(self, bundle: BundleProduct) -> BundleProduct: ...

    @abstractmethod
    async def delete(self, bundle_id: str, tenant_id: str) -> bool: ...


class TitleLibraryRepository(ABC):
    """标题库仓储接口 - Listing标题模板与优化参考"""

    @abstractmethod
    async def get_by_id(self, title_id: str, tenant_id: str) -> TitleLibrary | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, platform: str = "", language: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[TitleLibrary], int]: ...

    @abstractmethod
    async def create(self, title: TitleLibrary) -> TitleLibrary: ...

    @abstractmethod
    async def update(self, title: TitleLibrary) -> TitleLibrary: ...

    @abstractmethod
    async def soft_delete(self, title_id: str, tenant_id: str) -> bool: ...


class ImageLibraryRepository(ABC):
    """图片库仓储接口 - 产品图片统一管理"""

    @abstractmethod
    async def get_by_id(self, image_id: str, tenant_id: str) -> ImageLibrary | None: ...

    @abstractmethod
    async def list_by_sku(self, sku_id: str, tenant_id: str) -> Sequence[ImageLibrary]: ...

    @abstractmethod
    async def list_by_spu(self, spu_id: str, tenant_id: str) -> Sequence[ImageLibrary]: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, image_type: str = "", platform: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[ImageLibrary], int]: ...

    @abstractmethod
    async def create(self, image: ImageLibrary) -> ImageLibrary: ...

    @abstractmethod
    async def update(self, image: ImageLibrary) -> ImageLibrary: ...

    @abstractmethod
    async def soft_delete(self, image_id: str, tenant_id: str) -> bool: ...


class ProductIssueRepository(ABC):
    """产品问题记录仓储接口 - 质量问题跟踪与处理"""

    @abstractmethod
    async def get_by_id(self, issue_id: str, tenant_id: str) -> ProductIssue | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, status: str = "", severity: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[ProductIssue], int]: ...

    @abstractmethod
    async def list_by_sku(self, sku_id: str, tenant_id: str) -> Sequence[ProductIssue]: ...

    @abstractmethod
    async def create(self, issue: ProductIssue) -> ProductIssue: ...

    @abstractmethod
    async def update(self, issue: ProductIssue) -> ProductIssue: ...
