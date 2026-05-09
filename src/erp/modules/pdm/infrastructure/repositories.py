from collections.abc import Sequence
from datetime import UTC, datetime
import inspect

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

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
from erp.modules.pdm.domain.repositories import (
    BrandRepository,
    BundleProductRepository,
    CategoryRepository,
    ChannelSKUMappingRepository,
    ImageLibraryRepository,
    IPRecordRepository,
    ProductIssueRepository,
    ProductProjectRepository,
    QualityStandardRepository,
    SensitiveWordRepository,
    SKURepository,
    SPURepository,
    TitleLibraryRepository,
    UPCPoolRepository,
)


class SqlCategoryRepository(CategoryRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, cat_id: str, tenant_id: str) -> Category | None:
        stmt = select(Category).where(Category.id == cat_id, Category.tenant_id == tenant_id, Category.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, code: str, tenant_id: str) -> Category | None:
        stmt = select(Category).where(Category.code == code, Category.tenant_id == tenant_id, Category.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str) -> Sequence[Category]:
        stmt = select(Category).where(Category.tenant_id == tenant_id, Category.deleted_at.is_(None)).order_by(Category.sort_order)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_children(self, parent_id: str, tenant_id: str) -> Sequence[Category]:
        stmt = select(Category).where(Category.parent_id == parent_id, Category.tenant_id == tenant_id, Category.deleted_at.is_(None)).order_by(Category.sort_order)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, category: Category) -> Category:
        self._session.add(category)
        await self._session.flush()
        return category

    async def update(self, category: Category) -> Category:
        await self._session.flush()
        return category

    async def soft_delete(self, cat_id: str, tenant_id: str) -> bool:
        stmt = update(Category).where(Category.id == cat_id, Category.tenant_id == tenant_id).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlBrandRepository(BrandRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, brand_id: str, tenant_id: str) -> Brand | None:
        stmt = select(Brand).where(Brand.id == brand_id, Brand.tenant_id == tenant_id, Brand.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, code: str, tenant_id: str) -> Brand | None:
        stmt = select(Brand).where(Brand.code == code, Brand.tenant_id == tenant_id, Brand.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, page: int = 1, page_size: int = 20) -> tuple[Sequence[Brand], int]:
        conditions = [Brand.tenant_id == tenant_id, Brand.deleted_at.is_(None)]
        total = (await self._session.execute(select(func.count()).select_from(Brand).where(*conditions))).scalar() or 0
        stmt = select(Brand).where(*conditions).order_by(Brand.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, brand: Brand) -> Brand:
        self._session.add(brand)
        await self._session.flush()
        return brand

    async def update(self, brand: Brand) -> Brand:
        await self._session.flush()
        return brand

    async def soft_delete(self, brand_id: str, tenant_id: str) -> bool:
        stmt = update(Brand).where(Brand.id == brand_id, Brand.tenant_id == tenant_id).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlSPURepository(SPURepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, spu_id: str, tenant_id: str) -> SPU | None:
        stmt = select(SPU).where(SPU.id == spu_id, SPU.tenant_id == tenant_id, SPU.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        candidate = result.scalar_one_or_none()
        if inspect.isawaitable(candidate):
            candidate = await candidate
        return candidate if isinstance(candidate, SPU) else None

    async def get_by_code(self, code: str, tenant_id: str) -> SPU | None:
        stmt = select(SPU).where(SPU.code == code, SPU.tenant_id == tenant_id, SPU.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        candidate = result.scalar_one_or_none()
        if inspect.isawaitable(candidate):
            candidate = await candidate
        return candidate if isinstance(candidate, SPU) else None

    async def list_by_tenant(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[SPU], int]:
        conditions = [SPU.tenant_id == tenant_id, SPU.deleted_at.is_(None)]
        if status:
            conditions.append(SPU.status == status)
        total = (await self._session.execute(select(func.count()).select_from(SPU).where(*conditions))).scalar() or 0
        stmt = select(SPU).where(*conditions).order_by(SPU.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, spu: SPU) -> SPU:
        added = self._session.add(spu)
        if inspect.isawaitable(added):
            await added
        await self._session.flush()
        return spu

    async def update(self, spu: SPU) -> SPU:
        await self._session.flush()
        return spu

    async def soft_delete(self, spu_id: str, tenant_id: str) -> bool:
        stmt = update(SPU).where(SPU.id == spu_id, SPU.tenant_id == tenant_id).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlSKURepository(SKURepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, sku_id: str, tenant_id: str) -> SKU | None:
        stmt = select(SKU).where(SKU.id == sku_id, SKU.tenant_id == tenant_id, SKU.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, sku_code: str, tenant_id: str) -> SKU | None:
        stmt = select(SKU).where(SKU.sku_code == sku_code, SKU.tenant_id == tenant_id, SKU.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_spu(self, spu_id: str, tenant_id: str) -> Sequence[SKU]:
        stmt = select(SKU).where(SKU.spu_id == spu_id, SKU.tenant_id == tenant_id, SKU.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_tenant(self, tenant_id: str, page: int = 1, page_size: int = 20) -> tuple[Sequence[SKU], int]:
        conditions = [SKU.tenant_id == tenant_id, SKU.deleted_at.is_(None)]
        total = (await self._session.execute(select(func.count()).select_from(SKU).where(*conditions))).scalar() or 0
        stmt = select(SKU).where(*conditions).order_by(SKU.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, sku: SKU) -> SKU:
        self._session.add(sku)
        await self._session.flush()
        return sku

    async def update(self, sku: SKU) -> SKU:
        await self._session.flush()
        return sku

    async def soft_delete(self, sku_id: str, tenant_id: str) -> bool:
        stmt = update(SKU).where(SKU.id == sku_id, SKU.tenant_id == tenant_id).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlChannelSKUMappingRepository(ChannelSKUMappingRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_sku_and_channel(self, sku_id: str, channel: str, tenant_id: str) -> ChannelSKUMapping | None:
        stmt = select(ChannelSKUMapping).where(
            ChannelSKUMapping.sku_id == sku_id, ChannelSKUMapping.channel == channel, ChannelSKUMapping.tenant_id == tenant_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_sku(self, sku_id: str, tenant_id: str) -> Sequence[ChannelSKUMapping]:
        stmt = select(ChannelSKUMapping).where(ChannelSKUMapping.sku_id == sku_id, ChannelSKUMapping.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_channel(self, channel: str, tenant_id: str) -> Sequence[ChannelSKUMapping]:
        stmt = select(ChannelSKUMapping).where(ChannelSKUMapping.channel == channel, ChannelSKUMapping.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, mapping: ChannelSKUMapping) -> ChannelSKUMapping:
        self._session.add(mapping)
        await self._session.flush()
        return mapping

    async def update(self, mapping: ChannelSKUMapping) -> ChannelSKUMapping:
        await self._session.flush()
        return mapping

    async def delete(self, mapping_id: str, tenant_id: str) -> bool:
        stmt = sa_delete(ChannelSKUMapping).where(ChannelSKUMapping.id == mapping_id, ChannelSKUMapping.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlProductProjectRepository(ProductProjectRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, project_id: str, tenant_id: str) -> ProductProject | None:
        stmt = select(ProductProject).where(ProductProject.id == project_id, ProductProject.tenant_id == tenant_id, ProductProject.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, code: str, tenant_id: str) -> ProductProject | None:
        stmt = select(ProductProject).where(ProductProject.code == code, ProductProject.tenant_id == tenant_id, ProductProject.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        candidate = result.scalar_one_or_none()
        if inspect.isawaitable(candidate):
            candidate = await candidate
        return candidate if isinstance(candidate, ProductProject) else None

    async def list_by_tenant(self, tenant_id: str, stage: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[ProductProject], int]:
        conditions = [ProductProject.tenant_id == tenant_id, ProductProject.deleted_at.is_(None)]
        if stage:
            conditions.append(ProductProject.stage == stage)
        total = (await self._session.execute(select(func.count()).select_from(ProductProject).where(*conditions))).scalar() or 0
        stmt = select(ProductProject).where(*conditions).order_by(ProductProject.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, project: ProductProject) -> ProductProject:
        added = self._session.add(project)
        if inspect.isawaitable(added):
            await added
        await self._session.flush()
        return project

    async def update(self, project: ProductProject) -> ProductProject:
        await self._session.flush()
        return project

    async def soft_delete(self, project_id: str, tenant_id: str) -> bool:
        stmt = update(ProductProject).where(ProductProject.id == project_id, ProductProject.tenant_id == tenant_id).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlQualityStandardRepository(QualityStandardRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, qs_id: str, tenant_id: str) -> QualityStandard | None:
        stmt = select(QualityStandard).where(QualityStandard.id == qs_id, QualityStandard.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, category_id: str = "") -> Sequence[QualityStandard]:
        conditions = [QualityStandard.tenant_id == tenant_id]
        if category_id:
            conditions.append(QualityStandard.category_id == category_id)
        stmt = select(QualityStandard).where(*conditions).order_by(QualityStandard.created_at.desc())
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, qs: QualityStandard) -> QualityStandard:
        self._session.add(qs)
        await self._session.flush()
        return qs

    async def update(self, qs: QualityStandard) -> QualityStandard:
        await self._session.flush()
        return qs


class SqlIPRecordRepository(IPRecordRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, ip_id: str, tenant_id: str) -> IPRecord | None:
        stmt = select(IPRecord).where(IPRecord.id == ip_id, IPRecord.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_sku(self, sku_id: str, tenant_id: str) -> Sequence[IPRecord]:
        stmt = select(IPRecord).where(IPRecord.sku_id == sku_id, IPRecord.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_spu(self, spu_id: str, tenant_id: str) -> Sequence[IPRecord]:
        stmt = select(IPRecord).where(IPRecord.spu_id == spu_id, IPRecord.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, record: IPRecord) -> IPRecord:
        self._session.add(record)
        await self._session.flush()
        return record

    async def update(self, record: IPRecord) -> IPRecord:
        await self._session.flush()
        return record


class SqlSensitiveWordRepository(SensitiveWordRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_tenant(self, tenant_id: str, word_type: str = "", platform: str = "") -> Sequence[SensitiveWord]:
        conditions = [SensitiveWord.tenant_id == tenant_id]
        if word_type:
            conditions.append(SensitiveWord.word_type == word_type)
        if platform:
            conditions.append(SensitiveWord.platform == platform)
        stmt = select(SensitiveWord).where(*conditions).order_by(SensitiveWord.created_at.desc())
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, word: SensitiveWord) -> SensitiveWord:
        self._session.add(word)
        await self._session.flush()
        return word

    async def delete(self, word_id: str, tenant_id: str) -> bool:
        stmt = sa_delete(SensitiveWord).where(SensitiveWord.id == word_id, SensitiveWord.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlUPCPoolRepository(UPCPoolRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_code(self, upc_code: str, tenant_id: str) -> UPCPool | None:
        stmt = select(UPCPool).where(UPCPool.upc_code == upc_code, UPCPool.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_available(self, tenant_id: str, limit: int = 100) -> Sequence[UPCPool]:
        stmt = select(UPCPool).where(UPCPool.tenant_id == tenant_id, UPCPool.status == "available").limit(limit)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, upc: UPCPool) -> UPCPool:
        self._session.add(upc)
        await self._session.flush()
        return upc

    async def allocate(self, upc_code: str, sku_id: str, tenant_id: str) -> UPCPool | None:
        stmt = select(UPCPool).where(UPCPool.upc_code == upc_code, UPCPool.tenant_id == tenant_id, UPCPool.status == "available")
        upc = (await self._session.execute(stmt)).scalar_one_or_none()
        if not upc:
            return None
        upc.sku_id = sku_id
        upc.status = "allocated"
        upc.allocated_at = datetime.now(UTC)
        await self._session.flush()
        return upc

    async def release(self, upc_code: str, tenant_id: str) -> bool:
        stmt = select(UPCPool).where(UPCPool.upc_code == upc_code, UPCPool.tenant_id == tenant_id, UPCPool.status == "allocated")
        upc = (await self._session.execute(stmt)).scalar_one_or_none()
        if not upc:
            return False
        upc.sku_id = None
        upc.status = "available"
        upc.allocated_at = None
        await self._session.flush()
        return True


class SqlBundleProductRepository(BundleProductRepository):
    """组合产品SQL仓储 - Bundle的子SKU组成关系"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_spu(self, spu_id: str, tenant_id: str) -> Sequence[BundleProduct]:
        stmt = select(BundleProduct).where(
            BundleProduct.spu_id == spu_id, BundleProduct.tenant_id == tenant_id
        ).order_by(BundleProduct.sort_order)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, bundle: BundleProduct) -> BundleProduct:
        self._session.add(bundle)
        await self._session.flush()
        return bundle

    async def update(self, bundle: BundleProduct) -> BundleProduct:
        await self._session.flush()
        return bundle

    async def delete(self, bundle_id: str, tenant_id: str) -> bool:
        stmt = sa_delete(BundleProduct).where(BundleProduct.id == bundle_id, BundleProduct.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlTitleLibraryRepository(TitleLibraryRepository):
    """标题库SQL仓储 - Listing标题模板与优化参考"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, title_id: str, tenant_id: str) -> TitleLibrary | None:
        stmt = select(TitleLibrary).where(TitleLibrary.id == title_id, TitleLibrary.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(
        self, tenant_id: str, platform: str = "", language: str = "", page: int = 1, page_size: int = 20
    ) -> tuple[Sequence[TitleLibrary], int]:
        conditions = [TitleLibrary.tenant_id == tenant_id, TitleLibrary.status == "active"]
        if platform:
            conditions.append(TitleLibrary.platform == platform)
        if language:
            conditions.append(TitleLibrary.language == language)
        count_stmt = select(func.count()).select_from(TitleLibrary).where(*conditions)
        total = (await self._session.execute(count_stmt)).scalar() or 0
        stmt = select(TitleLibrary).where(*conditions).order_by(TitleLibrary.score.desc()).offset((page - 1) * page_size).limit(page_size)
        items = (await self._session.execute(stmt)).scalars().all()
        return items, total

    async def create(self, title: TitleLibrary) -> TitleLibrary:
        self._session.add(title)
        await self._session.flush()
        return title

    async def update(self, title: TitleLibrary) -> TitleLibrary:
        await self._session.flush()
        return title

    async def soft_delete(self, title_id: str, tenant_id: str) -> bool:
        stmt = update(TitleLibrary).where(TitleLibrary.id == title_id, TitleLibrary.tenant_id == tenant_id).values(status="disabled")
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlImageLibraryRepository(ImageLibraryRepository):
    """图片库SQL仓储 - 产品图片统一管理"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, image_id: str, tenant_id: str) -> ImageLibrary | None:
        stmt = select(ImageLibrary).where(ImageLibrary.id == image_id, ImageLibrary.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_sku(self, sku_id: str, tenant_id: str) -> Sequence[ImageLibrary]:
        stmt = select(ImageLibrary).where(
            ImageLibrary.sku_id == sku_id, ImageLibrary.tenant_id == tenant_id, ImageLibrary.status == "active"
        ).order_by(ImageLibrary.image_type)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_spu(self, spu_id: str, tenant_id: str) -> Sequence[ImageLibrary]:
        stmt = select(ImageLibrary).where(
            ImageLibrary.spu_id == spu_id, ImageLibrary.tenant_id == tenant_id, ImageLibrary.status == "active"
        ).order_by(ImageLibrary.image_type)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_tenant(
        self, tenant_id: str, image_type: str = "", platform: str = "", page: int = 1, page_size: int = 20
    ) -> tuple[Sequence[ImageLibrary], int]:
        conditions = [ImageLibrary.tenant_id == tenant_id, ImageLibrary.status == "active"]
        if image_type:
            conditions.append(ImageLibrary.image_type == image_type)
        if platform:
            conditions.append(ImageLibrary.platform == platform)
        count_stmt = select(func.count()).select_from(ImageLibrary).where(*conditions)
        total = (await self._session.execute(count_stmt)).scalar() or 0
        stmt = select(ImageLibrary).where(*conditions).order_by(ImageLibrary.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = (await self._session.execute(stmt)).scalars().all()
        return items, total

    async def create(self, image: ImageLibrary) -> ImageLibrary:
        self._session.add(image)
        await self._session.flush()
        return image

    async def update(self, image: ImageLibrary) -> ImageLibrary:
        await self._session.flush()
        return image

    async def soft_delete(self, image_id: str, tenant_id: str) -> bool:
        stmt = update(ImageLibrary).where(ImageLibrary.id == image_id, ImageLibrary.tenant_id == tenant_id).values(status="disabled")
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlProductIssueRepository(ProductIssueRepository):
    """产品问题记录SQL仓储 - 质量问题跟踪与处理"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, issue_id: str, tenant_id: str) -> ProductIssue | None:
        stmt = select(ProductIssue).where(ProductIssue.id == issue_id, ProductIssue.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(
        self, tenant_id: str, status: str = "", severity: str = "", page: int = 1, page_size: int = 20
    ) -> tuple[Sequence[ProductIssue], int]:
        conditions = [ProductIssue.tenant_id == tenant_id]
        if status:
            conditions.append(ProductIssue.status == status)
        if severity:
            conditions.append(ProductIssue.severity == severity)
        count_stmt = select(func.count()).select_from(ProductIssue).where(*conditions)
        total = (await self._session.execute(count_stmt)).scalar() or 0
        stmt = select(ProductIssue).where(*conditions).order_by(ProductIssue.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = (await self._session.execute(stmt)).scalars().all()
        return items, total

    async def list_by_sku(self, sku_id: str, tenant_id: str) -> Sequence[ProductIssue]:
        stmt = select(ProductIssue).where(
            ProductIssue.sku_id == sku_id, ProductIssue.tenant_id == tenant_id
        ).order_by(ProductIssue.created_at.desc())
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, issue: ProductIssue) -> ProductIssue:
        self._session.add(issue)
        await self._session.flush()
        return issue

    async def update(self, issue: ProductIssue) -> ProductIssue:
        await self._session.flush()
        return issue
