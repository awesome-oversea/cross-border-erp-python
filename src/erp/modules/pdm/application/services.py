"""
PDM 应用服务模块 - 产品域应用层服务

本模块包含 PDM 域的所有应用服务，负责：
  - 编排领域服务与仓储的协作
  - 处理业务流程（创建、查询、状态转换）
  - 数据校验与异常抛出
  - 不包含业务规则，业务规则由 domain/services.py 封装

包含的应用服务：
  - CategoryService: 分类管理
  - BrandService: 品牌管理
  - SPUService: SPU标准产品单元管理
  - SKUService: SKU库存单元管理
  - ChannelSKUMappingService: 渠道SKU映射管理
  - ProductProjectService: 产品项目开发管理
  - ProductCollectionService: 选品采集管理
  - IPRecordService: 知识产权记录管理
  - QualityStandardService: 质量标准管理
  - SensitiveWordService: 敏感词管理
  - UPCPoolService: UPC条码池管理
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import func as sa_func
from sqlalchemy import select

from erp.modules.pdm.domain.models import (
    IPRecord,
    ProductCollection,
    SKU,
    SPU,
    Brand,
    BundleProduct,
    Category,
    ChannelSKUMapping,
    ImageLibrary,
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
from erp.modules.pdm.domain.services import IPRecordDomainService, ProductCollectionDomainService
from erp.shared.context import actor_id_var
from erp.shared.exceptions import DuplicateCodeException, NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.pdm")

SPU_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["pending_review", "cancelled"],
    "pending_review": ["approved", "rejected", "cancelled"],
    "rejected": ["draft", "cancelled"],
    "approved": ["listed", "cancelled"],
    "listed": ["delisted", "discontinued", "cancelled"],
    "delisted": ["listed", "discontinued", "cancelled"],
    "discontinued": [],
    "cancelled": [],
}

PRODUCT_PROJECT_STAGES: list[str] = [
    "proposing", "researching", "designing", "sourcing", "sampling",
    "testing", "pre_production", "mass_production", "launched", "completed",
]

PROJECT_STAGE_TRANSITIONS: dict[str, list[str]] = {
    "proposing": ["researching", "cancelled"],
    "researching": ["designing", "proposing", "cancelled"],
    "designing": ["sourcing", "researching", "cancelled"],
    "sourcing": ["sampling", "designing", "cancelled"],
    "sampling": ["testing", "sourcing", "cancelled"],
    "testing": ["pre_production", "sampling", "cancelled"],
    "pre_production": ["mass_production", "testing", "cancelled"],
    "mass_production": ["launched", "pre_production", "cancelled"],
    "launched": ["completed", "cancelled"],
    "completed": [],
    "cancelled": [],
}

SKU_DIMENSION_LIMITS = {
    "weight_max": 50.0,
    "length_max": 200.0,
    "width_max": 200.0,
    "height_max": 200.0,
    "cost_price_max": 100000.0,
}


class CategoryService:
    """分类应用服务 - 管理产品分类的创建、查询和树形结构"""

    def __init__(self, session: AsyncSession, category_repo: CategoryRepository | None = None):
        self._session = session
        self._category_repo = category_repo

    async def create(self, tenant_id: str, name: str, code: str, parent_id: str | None = None, **kwargs) -> Category:
        if self._category_repo:
            existing = await self._category_repo.get_by_code(code, tenant_id)
        else:
            stmt = select(Category).where(Category.code == code, Category.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Category code '{code}' already exists")

        path = ""
        level = 1
        if parent_id:
            parent = await self._get(parent_id, tenant_id)
            if not parent:
                raise NotFoundException(message=f"Parent category '{parent_id}' not found")
            path = f"{parent.path}/{parent.id}" if parent.path else parent.id
            level = parent.level + 1

        cat = Category(tenant_id=tenant_id, name=name, code=code, parent_id=parent_id, path=path, level=level, **kwargs)
        if self._category_repo:
            return await self._category_repo.create(cat)
        self._session.add(cat)
        await self._session.flush()
        return cat

    async def list_tree(self, tenant_id: str) -> list[dict]:
        if self._category_repo:
            categories = await self._category_repo.list_by_tenant(tenant_id)
        else:
            stmt = select(Category).where(Category.tenant_id == tenant_id, Category.deleted_at.is_(None)).order_by(Category.sort_order)
            categories = (await self._session.execute(stmt)).scalars().all()
        return [self._to_dict(c) for c in categories]

    async def _get(self, cat_id: str, tenant_id: str) -> Category | None:
        if self._category_repo:
            return await self._category_repo.get_by_id(cat_id, tenant_id)
        stmt = select(Category).where(Category.id == cat_id, Category.tenant_id == tenant_id, Category.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _to_dict(c: Category) -> dict:
        return {"id": c.id, "name": c.name, "code": c.code, "parent_id": c.parent_id, "path": c.path, "level": c.level, "status": c.status}

    async def update(self, cat_id: str, tenant_id: str, **kwargs) -> Category:
        cat = await self._get(cat_id, tenant_id)
        if not cat:
            raise NotFoundException(message=f"Category '{cat_id}' not found")
        for k, v in kwargs.items():
            if v is not None and hasattr(cat, k):
                setattr(cat, k, v)
        if self._category_repo:
            return await self._category_repo.update(cat)
        await self._session.flush()
        return cat

    async def soft_delete(self, cat_id: str, tenant_id: str) -> bool:
        cat = await self._get(cat_id, tenant_id)
        if not cat:
            raise NotFoundException(message=f"Category '{cat_id}' not found")
        from datetime import datetime, timezone
        cat.deleted_at = datetime.now(timezone.utc)
        if self._category_repo:
            await self._category_repo.update(cat)
        else:
            await self._session.flush()
        return True


class BrandService:
    """品牌应用服务 - 管理品牌的创建和查询"""

    def __init__(self, session: AsyncSession, brand_repo: BrandRepository | None = None):
        self._session = session
        self._brand_repo = brand_repo

    async def create(self, tenant_id: str, name: str, code: str, **kwargs) -> Brand:
        if self._brand_repo:
            existing = await self._brand_repo.get_by_code(code, tenant_id)
        else:
            stmt = select(Brand).where(Brand.code == code, Brand.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Brand code '{code}' already exists")
        brand = Brand(tenant_id=tenant_id, name=name, code=code, **kwargs)
        if self._brand_repo:
            return await self._brand_repo.create(brand)
        self._session.add(brand)
        await self._session.flush()
        return brand

    async def list_all(self, tenant_id: str, page: int = 1, page_size: int = 20) -> tuple[Sequence[Brand], int]:
        if self._brand_repo:
            return await self._brand_repo.list_by_tenant(tenant_id, page=page, page_size=page_size)
        conditions = [Brand.tenant_id == tenant_id, Brand.deleted_at.is_(None)]
        total = (await self._session.execute(select(sa_func.count()).select_from(Brand).where(*conditions))).scalar() or 0
        stmt = select(Brand).where(*conditions).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def update(self, brand_id: str, tenant_id: str, **kwargs) -> Brand:
        if self._brand_repo:
            brand = await self._brand_repo.get_by_id(brand_id, tenant_id)
        else:
            stmt = select(Brand).where(Brand.id == brand_id, Brand.tenant_id == tenant_id, Brand.deleted_at.is_(None))
            brand = (await self._session.execute(stmt)).scalar_one_or_none()
        if not brand:
            raise NotFoundException(message=f"Brand '{brand_id}' not found")
        for k, v in kwargs.items():
            if v is not None and hasattr(brand, k):
                setattr(brand, k, v)
        if self._brand_repo:
            return await self._brand_repo.update(brand)
        await self._session.flush()
        return brand

    async def soft_delete(self, brand_id: str, tenant_id: str) -> bool:
        if self._brand_repo:
            brand = await self._brand_repo.get_by_id(brand_id, tenant_id)
        else:
            stmt = select(Brand).where(Brand.id == brand_id, Brand.tenant_id == tenant_id, Brand.deleted_at.is_(None))
            brand = (await self._session.execute(stmt)).scalar_one_or_none()
        if not brand:
            raise NotFoundException(message=f"Brand '{brand_id}' not found")
        from datetime import datetime, timezone
        brand.deleted_at = datetime.now(timezone.utc)
        if self._brand_repo:
            await self._brand_repo.update(brand)
        else:
            await self._session.flush()
        return True


class SPUService:
    """SPU应用服务 - 管理标准产品单元的创建、查询和状态转换"""

    def __init__(self, session: AsyncSession, spu_repo: SPURepository | None = None):
        self._session = session
        self._spu_repo = spu_repo

    async def create(self, tenant_id: str, name: str, code: str, **kwargs) -> SPU:
        if self._spu_repo:
            existing = await self._spu_repo.get_by_code(code, tenant_id)
        else:
            stmt = select(SPU).where(SPU.code == code, SPU.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"SPU code '{code}' already exists")
        spu = SPU(tenant_id=tenant_id, name=name, code=code, created_by=actor_id_var.get(""), **kwargs)
        if self._spu_repo:
            return await self._spu_repo.create(spu)
        self._session.add(spu)
        await self._session.flush()
        return spu

    async def get_by_id(self, spu_id: str, tenant_id: str) -> SPU | None:
        if self._spu_repo:
            return await self._spu_repo.get_by_id(spu_id, tenant_id)
        stmt = select(SPU).where(SPU.id == spu_id, SPU.tenant_id == tenant_id, SPU.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, spu_id: str, tenant_id: str) -> SPU:
        spu = await self.get_by_id(spu_id, tenant_id)
        if not spu:
            raise NotFoundException(message=f"SPU '{spu_id}' not found")
        return spu

    async def list_all(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[SPU], int]:
        if self._spu_repo:
            return await self._spu_repo.list_by_tenant(tenant_id, status=status, page=page, page_size=page_size)
        conditions = [SPU.tenant_id == tenant_id, SPU.deleted_at.is_(None)]
        if status:
            conditions.append(SPU.status == status)
        total = (await self._session.execute(select(sa_func.count()).select_from(SPU).where(*conditions))).scalar() or 0
        stmt = select(SPU).where(*conditions).order_by(SPU.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def update_status(self, spu_id: str, tenant_id: str, status: str) -> SPU:
        spu = await self.get_by_id(spu_id, tenant_id)
        if not spu:
            raise NotFoundException(message=f"SPU '{spu_id}' not found")
        allowed = SPU_STATUS_TRANSITIONS.get(spu.status, [])
        if status not in allowed:
            raise ValidationException(
                message=f"Cannot transition SPU from '{spu.status}' to '{status}'"
            )
        if status == "pending_review" and not spu.name:
            raise ValidationException(message="SPU must have a name before submitting for review")
        if status == "approved" and not spu.category_id:
            raise ValidationException(message="SPU must have a category before approval")
        if status == "listed" and not spu.main_image:
            raise ValidationException(message="SPU must have a main image before listing")
        spu.status = status
        if self._spu_repo:
            return await self._spu_repo.update(spu)
        await self._session.flush()
        return spu

    async def update(self, spu: SPU) -> SPU:
        if self._spu_repo:
            return await self._spu_repo.update(spu)
        await self._session.flush()
        return spu


class SKUService:
    """SKU应用服务 - 管理库存单元的创建、查询和维度校验"""

    def __init__(self, session: AsyncSession, sku_repo: SKURepository | None = None):
        self._session = session
        self._sku_repo = sku_repo

    async def create(self, tenant_id: str, spu_id: str, sku_code: str, **kwargs) -> SKU:
        spu = await self._session.get(SPU, spu_id)
        if not spu or spu.tenant_id != tenant_id:
            raise NotFoundException(message=f"SPU '{spu_id}' not found")
        if spu.status in ("cancelled", "discontinued"):
            raise ValidationException(message=f"Cannot create SKU for SPU in '{spu.status}' status")
        if self._sku_repo:
            existing = await self._sku_repo.get_by_code(sku_code, tenant_id)
        else:
            stmt = select(SKU).where(SKU.sku_code == sku_code, SKU.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"SKU code '{sku_code}' already exists")
        weight = kwargs.get("weight", 0.0)
        length = kwargs.get("length", 0.0)
        width = kwargs.get("width", 0.0)
        height = kwargs.get("height", 0.0)
        cost_price = kwargs.get("cost_price", 0.0)
        if weight < 0 or weight > SKU_DIMENSION_LIMITS["weight_max"]:
            raise ValidationException(
                message=f"Weight must be between 0 and {SKU_DIMENSION_LIMITS['weight_max']} kg"
            )
        if length < 0 or length > SKU_DIMENSION_LIMITS["length_max"]:
            raise ValidationException(
                message=f"Length must be between 0 and {SKU_DIMENSION_LIMITS['length_max']} cm"
            )
        if width < 0 or width > SKU_DIMENSION_LIMITS["width_max"]:
            raise ValidationException(
                message=f"Width must be between 0 and {SKU_DIMENSION_LIMITS['width_max']} cm"
            )
        if height < 0 or height > SKU_DIMENSION_LIMITS["height_max"]:
            raise ValidationException(
                message=f"Height must be between 0 and {SKU_DIMENSION_LIMITS['height_max']} cm"
            )
        if cost_price < 0 or cost_price > SKU_DIMENSION_LIMITS["cost_price_max"]:
            raise ValidationException(
                message=f"Cost price must be between 0 and {SKU_DIMENSION_LIMITS['cost_price_max']}"
            )
        sku = SKU(tenant_id=tenant_id, spu_id=spu_id, sku_code=sku_code, **kwargs)
        if self._sku_repo:
            return await self._sku_repo.create(sku)
        self._session.add(sku)
        await self._session.flush()
        return sku

    async def get_by_id(self, sku_id: str, tenant_id: str) -> SKU | None:
        if self._sku_repo:
            return await self._sku_repo.get_by_id(sku_id, tenant_id)
        stmt = select(SKU).where(SKU.id == sku_id, SKU.tenant_id == tenant_id, SKU.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, sku_id: str, tenant_id: str) -> SKU:
        sku = await self.get_by_id(sku_id, tenant_id)
        if not sku:
            raise NotFoundException(message=f"SKU '{sku_id}' not found")
        return sku

    async def list_by_spu(self, spu_id: str, tenant_id: str) -> Sequence[SKU]:
        if self._sku_repo:
            return await self._sku_repo.list_by_spu(spu_id, tenant_id)
        stmt = select(SKU).where(SKU.spu_id == spu_id, SKU.tenant_id == tenant_id, SKU.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalars().all()

    async def list_all(self, tenant_id: str, page: int = 1, page_size: int = 20) -> tuple[Sequence[SKU], int]:
        if self._sku_repo:
            return await self._sku_repo.list_by_tenant(tenant_id, page=page, page_size=page_size)
        conditions = [SKU.tenant_id == tenant_id, SKU.deleted_at.is_(None)]
        total = (await self._session.execute(select(sa_func.count()).select_from(SKU).where(*conditions))).scalar() or 0
        stmt = select(SKU).where(*conditions).order_by(SKU.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def update(self, sku_id: str, tenant_id: str, **kwargs) -> SKU:
        sku = await self.get_by_id(sku_id, tenant_id)
        if not sku:
            raise NotFoundException(message=f"SKU '{sku_id}' not found")
        for k, v in kwargs.items():
            if v is not None and hasattr(sku, k):
                setattr(sku, k, v)
        if self._sku_repo:
            return await self._sku_repo.update(sku)
        await self._session.flush()
        return sku

    async def soft_delete(self, sku_id: str, tenant_id: str) -> bool:
        sku = await self.get_by_id(sku_id, tenant_id)
        if not sku:
            raise NotFoundException(message=f"SKU '{sku_id}' not found")
        from datetime import datetime, timezone
        sku.deleted_at = datetime.now(timezone.utc)
        sku.status = "discontinued"
        if self._sku_repo:
            await self._sku_repo.update(sku)
        else:
            await self._session.flush()
        return True


class ChannelSKUMappingService:
    """渠道SKU映射应用服务 - 管理内部SKU与渠道SKU的映射关系"""

    def __init__(self, session: AsyncSession, mapping_repo: ChannelSKUMappingRepository | None = None):
        self._session = session
        self._mapping_repo = mapping_repo

    async def create_mapping(self, tenant_id: str, sku_id: str, channel: str, channel_sku: str, **kwargs) -> ChannelSKUMapping:
        if self._mapping_repo:
            existing = await self._mapping_repo.get_by_sku_and_channel(sku_id, channel, tenant_id)
        else:
            stmt = select(ChannelSKUMapping).where(
                ChannelSKUMapping.sku_id == sku_id,
                ChannelSKUMapping.channel == channel,
                ChannelSKUMapping.tenant_id == tenant_id,
            )
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"SKU mapping for channel '{channel}' already exists")
        mapping = ChannelSKUMapping(tenant_id=tenant_id, sku_id=sku_id, channel=channel, channel_sku=channel_sku, **kwargs)
        if self._mapping_repo:
            return await self._mapping_repo.create(mapping)
        self._session.add(mapping)
        await self._session.flush()
        return mapping

    async def get_by_sku(self, sku_id: str, tenant_id: str) -> Sequence[ChannelSKUMapping]:
        if self._mapping_repo:
            return await self._mapping_repo.list_by_sku(sku_id, tenant_id)
        stmt = select(ChannelSKUMapping).where(ChannelSKUMapping.sku_id == sku_id, ChannelSKUMapping.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()


class ProductProjectService:
    """产品项目应用服务 - 管理产品开发项目的创建和阶段流转"""

    def __init__(self, session: AsyncSession, project_repo: ProductProjectRepository | None = None):
        self._session = session
        self._project_repo = project_repo

    async def create(self, tenant_id: str, name: str, code: str, **kwargs) -> ProductProject:
        if self._project_repo:
            existing = await self._project_repo.get_by_code(code, tenant_id)
        else:
            stmt = select(ProductProject).where(ProductProject.code == code, ProductProject.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Project code '{code}' already exists")
        project = ProductProject(tenant_id=tenant_id, name=name, code=code, **kwargs)
        if self._project_repo:
            return await self._project_repo.create(project)
        self._session.add(project)
        await self._session.flush()
        return project

    async def get_by_id(self, project_id: str, tenant_id: str) -> ProductProject | None:
        if self._project_repo:
            return await self._project_repo.get_by_id(project_id, tenant_id)
        stmt = select(ProductProject).where(ProductProject.id == project_id, ProductProject.tenant_id == tenant_id, ProductProject.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, project_id: str, tenant_id: str) -> ProductProject:
        project = await self.get_by_id(project_id, tenant_id)
        if not project:
            raise NotFoundException(message=f"Product project '{project_id}' not found")
        return project

    async def update_stage(self, project_id: str, tenant_id: str, stage: str) -> ProductProject:
        project = await self.get_by_id(project_id, tenant_id)
        if not project:
            raise NotFoundException(message=f"Product project '{project_id}' not found")
        if stage not in PRODUCT_PROJECT_STAGES and stage != "cancelled":
            raise ValidationException(
                message=f"Invalid stage '{stage}', allowed: {[*PRODUCT_PROJECT_STAGES, 'cancelled']}"
            )
        allowed = PROJECT_STAGE_TRANSITIONS.get(project.stage, [])
        if stage not in allowed:
            raise ValidationException(
                message=f"Cannot transition project from '{project.stage}' to '{stage}'"
            )
        project.stage = stage
        if self._project_repo:
            return await self._project_repo.update(project)
        await self._session.flush()
        return project

    async def list_all(self, tenant_id: str, stage: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[ProductProject], int]:
        if self._project_repo:
            return await self._project_repo.list_by_tenant(tenant_id, stage=stage, page=page, page_size=page_size)
        conditions = [ProductProject.tenant_id == tenant_id, ProductProject.deleted_at.is_(None)]
        if stage:
            conditions.append(ProductProject.stage == stage)
        total = (await self._session.execute(select(sa_func.count()).select_from(ProductProject).where(*conditions))).scalar() or 0
        stmt = select(ProductProject).where(*conditions).order_by(ProductProject.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def get_by_recommendation_id(self, recommendation_id: str, tenant_id: str) -> ProductProject | None:
        stmt = select(ProductProject).where(
            ProductProject.recommendation_id == recommendation_id,
            ProductProject.tenant_id == tenant_id,
            ProductProject.deleted_at.is_(None),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()


class ProductCollectionService:
    """选品采集应用服务 - 管理产品采集、分析、选品评分和SPU转换"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, tenant_id: str, source_platform: str, source_url: str,
                     title: str = "", **kwargs) -> ProductCollection:
        errors = ProductCollectionDomainService.validate_collection(source_platform, source_url)
        if errors:
            raise ValidationException(message="; ".join(errors))
        collection = ProductCollection(
            tenant_id=tenant_id, source_platform=source_platform,
            source_url=source_url, title=title,
            collected_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(ProductCollection, k)},
        )
        sales_data = kwargs.get("sales_data", {})
        review_data = kwargs.get("review_data", {})
        price = kwargs.get("price", 0.0)
        if sales_data:
            collection.sales_data_json = json.dumps(sales_data, default=str)
        if review_data:
            collection.review_data_json = json.dumps(review_data, default=str)
        collection.score = ProductCollectionDomainService.calculate_selection_score(
            sales_data, review_data, price
        )
        self._session.add(collection)
        await self._session.flush()
        return collection

    async def get_by_id(self, collection_id: str, tenant_id: str) -> ProductCollection | None:
        stmt = select(ProductCollection).where(
            ProductCollection.id == collection_id, ProductCollection.tenant_id == tenant_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, collection_id: str, tenant_id: str) -> ProductCollection:
        collection = await self.get_by_id(collection_id, tenant_id)
        if not collection:
            raise NotFoundException(message=f"Product collection '{collection_id}' not found")
        return collection

    async def list_all(self, tenant_id: str, status: str = "", source_platform: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[ProductCollection], int]:
        conditions = [ProductCollection.tenant_id == tenant_id]
        if status:
            conditions.append(ProductCollection.status == status)
        if source_platform:
            conditions.append(ProductCollection.source_platform == source_platform)
        total = (await self._session.execute(select(sa_func.count()).select_from(ProductCollection).where(*conditions))).scalar() or 0
        stmt = select(ProductCollection).where(*conditions).order_by(
            ProductCollection.score.desc(), ProductCollection.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def update_status(self, collection_id: str, tenant_id: str, new_status: str) -> ProductCollection:
        collection = await self.get_by_id(collection_id, tenant_id)
        if not collection:
            raise NotFoundException(message=f"Product collection '{collection_id}' not found")
        if not ProductCollectionDomainService.can_transition(collection.status, new_status):
            raise ValidationException(
                message=f"Cannot transition collection from '{collection.status}' to '{new_status}'"
            )
        collection.status = new_status
        await self._session.flush()
        return collection

    async def analyze(self, collection_id: str, tenant_id: str) -> ProductCollection:
        collection = await self.get_by_id(collection_id, tenant_id)
        if not collection:
            raise NotFoundException(message=f"Product collection '{collection_id}' not found")
        if collection.status != "collected":
            raise ValidationException(message="Only 'collected' items can be analyzed")
        sales_data = json.loads(collection.sales_data_json or "{}")
        review_data = json.loads(collection.review_data_json or "{}")
        collection.score = ProductCollectionDomainService.calculate_selection_score(
            sales_data, review_data, collection.price
        )
        collection.status = "analyzing"
        await self._session.flush()
        return collection

    async def convert_to_spu(self, collection_id: str, tenant_id: str) -> SPU:
        collection = await self.get_by_id(collection_id, tenant_id)
        if not collection:
            raise NotFoundException(message=f"Product collection '{collection_id}' not found")
        if collection.status != "selected":
            raise ValidationException(message="Only 'selected' items can be converted")
        collection.status = "converting"
        spu = SPU(
            tenant_id=tenant_id, name=collection.title, name_en=collection.title_en,
            code=f"SPU-{collection.source_platform}-{collection.source_product_id[:20]}",
            main_image=collection.main_image,
            images_json=collection.images_json,
            attributes_json=collection.attributes_json,
            created_by=actor_id_var.get(""),
        )
        self._session.add(spu)
        collection.converted_spu_id = spu.id
        collection.status = "converted"
        await self._session.flush()
        return spu


class IPRecordService:
    """知识产权记录应用服务 - 管理IP记录的创建和商标冲突检测"""

    def __init__(self, session: AsyncSession, ip_repo: IPRecordRepository | None = None):
        self._session = session
        self._ip_repo = ip_repo

    async def create(self, tenant_id: str, ip_type: str, ip_name: str = "",
                     ip_number: str = "", sku_id: str | None = None,
                     spu_id: str | None = None, risk_level: str = "none",
                     **kwargs) -> IPRecord:
        errors = IPRecordDomainService.validate_ip_record(ip_type, risk_level)
        if errors:
            raise ValidationException(message="; ".join(errors))
        record = IPRecord(
            tenant_id=tenant_id, ip_type=ip_type, ip_name=ip_name,
            ip_number=ip_number, sku_id=sku_id, spu_id=spu_id,
            risk_level=risk_level,
            **{k: v for k, v in kwargs.items() if hasattr(IPRecord, k)},
        )
        if self._ip_repo:
            return await self._ip_repo.create(record)
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_by_id(self, record_id: str, tenant_id: str) -> IPRecord | None:
        if self._ip_repo:
            return await self._ip_repo.get_by_id(record_id, tenant_id)
        stmt = select(IPRecord).where(IPRecord.id == record_id, IPRecord.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_sku(self, sku_id: str, tenant_id: str) -> Sequence[IPRecord]:
        if self._ip_repo:
            return await self._ip_repo.list_by_sku(sku_id, tenant_id)
        stmt = select(IPRecord).where(IPRecord.sku_id == sku_id, IPRecord.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_spu(self, spu_id: str, tenant_id: str) -> Sequence[IPRecord]:
        if self._ip_repo:
            return await self._ip_repo.list_by_spu(spu_id, tenant_id)
        stmt = select(IPRecord).where(IPRecord.spu_id == spu_id, IPRecord.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def check_trademark_conflict(self, tenant_id: str, product_name: str) -> dict:
        stmt = select(IPRecord).where(
            IPRecord.tenant_id == tenant_id,
            IPRecord.ip_type == "trademark",
            IPRecord.status == "active",
        )
        trademarks = (await self._session.execute(stmt)).scalars().all()
        tm_data = [{"ip_name": t.ip_name, "ip_number": t.ip_number, "risk_level": t.risk_level} for t in trademarks]
        conflicts = IPRecordDomainService.check_trademark_conflict(product_name, tm_data)
        return {
            "product_name": product_name,
            "has_conflict": len(conflicts) > 0,
            "conflicts": conflicts,
        }


class QualityStandardService:
    """质量标准应用服务 - 管理产品质量标准的创建和查询"""

    def __init__(self, session: AsyncSession, qs_repo: QualityStandardRepository | None = None):
        self._session = session
        self._qs_repo = qs_repo

    async def create(self, tenant_id: str, name: str, **kwargs) -> QualityStandard:
        qs = QualityStandard(tenant_id=tenant_id, name=name, **kwargs)
        if self._qs_repo:
            return await self._qs_repo.create(qs)
        self._session.add(qs)
        await self._session.flush()
        return qs

    async def get_by_id(self, qs_id: str, tenant_id: str) -> QualityStandard | None:
        if self._qs_repo:
            return await self._qs_repo.get_by_id(qs_id, tenant_id)
        stmt = select(QualityStandard).where(QualityStandard.id == qs_id, QualityStandard.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, category_id: str = "") -> Sequence[QualityStandard]:
        if self._qs_repo:
            return await self._qs_repo.list_by_tenant(tenant_id, category_id=category_id)
        conditions = [QualityStandard.tenant_id == tenant_id]
        if category_id:
            conditions.append(QualityStandard.category_id == category_id)
        stmt = select(QualityStandard).where(*conditions).order_by(QualityStandard.created_at.desc())
        return (await self._session.execute(stmt)).scalars().all()


class SensitiveWordService:
    """敏感词应用服务 - 管理平台敏感词的创建、查询和删除"""

    def __init__(self, session: AsyncSession, word_repo: SensitiveWordRepository | None = None):
        self._session = session
        self._word_repo = word_repo

    async def create(self, tenant_id: str, word: str, **kwargs) -> SensitiveWord:
        sw = SensitiveWord(tenant_id=tenant_id, word=word, **kwargs)
        if self._word_repo:
            return await self._word_repo.create(sw)
        self._session.add(sw)
        await self._session.flush()
        return sw

    async def list_by_tenant(self, tenant_id: str, word_type: str = "", platform: str = "") -> Sequence[SensitiveWord]:
        if self._word_repo:
            return await self._word_repo.list_by_tenant(tenant_id, word_type=word_type, platform=platform)
        conditions = [SensitiveWord.tenant_id == tenant_id]
        if word_type:
            conditions.append(SensitiveWord.word_type == word_type)
        if platform:
            conditions.append(SensitiveWord.platform == platform)
        stmt = select(SensitiveWord).where(*conditions).order_by(SensitiveWord.created_at.desc())
        return (await self._session.execute(stmt)).scalars().all()

    async def delete(self, word_id: str, tenant_id: str) -> bool:
        if self._word_repo:
            return await self._word_repo.delete(word_id, tenant_id)
        from sqlalchemy import delete as sa_delete
        stmt = sa_delete(SensitiveWord).where(SensitiveWord.id == word_id, SensitiveWord.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class UPCPoolService:
    """UPC条码池应用服务 - 管理UPC条码的创建、分配和释放"""

    def __init__(self, session: AsyncSession, upc_repo: UPCPoolRepository | None = None):
        self._session = session
        self._upc_repo = upc_repo

    async def batch_create(self, tenant_id: str, upc_codes: list[str]) -> list[UPCPool]:
        created = []
        for code in upc_codes:
            upc = UPCPool(tenant_id=tenant_id, upc_code=code, status="available")
            if self._upc_repo:
                created.append(await self._upc_repo.create(upc))
            else:
                self._session.add(upc)
                created.append(upc)
        await self._session.flush()
        return created

    async def allocate(self, upc_code: str, sku_id: str, tenant_id: str) -> UPCPool | None:
        if self._upc_repo:
            return await self._upc_repo.allocate(upc_code, sku_id, tenant_id)
        stmt = select(UPCPool).where(UPCPool.upc_code == upc_code, UPCPool.tenant_id == tenant_id, UPCPool.status == "available")
        upc = (await self._session.execute(stmt)).scalar_one_or_none()
        if not upc:
            return None
        upc.sku_id = sku_id
        upc.status = "allocated"
        from datetime import UTC, datetime
        upc.allocated_at = datetime.now(UTC)
        await self._session.flush()
        return upc

    async def release(self, upc_code: str, tenant_id: str) -> bool:
        if self._upc_repo:
            return await self._upc_repo.release(upc_code, tenant_id)
        stmt = select(UPCPool).where(UPCPool.upc_code == upc_code, UPCPool.tenant_id == tenant_id, UPCPool.status == "allocated")
        upc = (await self._session.execute(stmt)).scalar_one_or_none()
        if not upc:
            return False
        upc.sku_id = None
        upc.status = "available"
        upc.allocated_at = None
        await self._session.flush()
        return True

    async def list_available(self, tenant_id: str, limit: int = 100) -> Sequence[UPCPool]:
        if self._upc_repo:
            return await self._upc_repo.list_available(tenant_id, limit=limit)
        stmt = select(UPCPool).where(UPCPool.tenant_id == tenant_id, UPCPool.status == "available").limit(limit)
        return (await self._session.execute(stmt)).scalars().all()


class PDMQueryService:
    """
    PDM 统计查询服务

    提供PDM模块的运营统计概览、各子域统计数据聚合。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_statistics(self, tenant_id: str) -> dict:
        """获取PDM运营统计概览"""
        total_categories = (await self._session.execute(
            select(sa_func.count()).select_from(Category).where(Category.tenant_id == tenant_id)
        )).scalar() or 0

        total_brands = (await self._session.execute(
            select(sa_func.count()).select_from(Brand).where(Brand.tenant_id == tenant_id)
        )).scalar() or 0

        total_spus = (await self._session.execute(
            select(sa_func.count()).select_from(SPU).where(SPU.tenant_id == tenant_id)
        )).scalar() or 0

        active_spus = (await self._session.execute(
            select(sa_func.count()).select_from(SPU)
            .where(SPU.tenant_id == tenant_id, SPU.status == "active")
        )).scalar() or 0

        total_skus = (await self._session.execute(
            select(sa_func.count()).select_from(SKU).where(SKU.tenant_id == tenant_id)
        )).scalar() or 0

        active_skus = (await self._session.execute(
            select(sa_func.count()).select_from(SKU)
            .where(SKU.tenant_id == tenant_id, SKU.status == "active")
        )).scalar() or 0

        total_channel_mappings = (await self._session.execute(
            select(sa_func.count()).select_from(ChannelSKUMapping)
            .where(ChannelSKUMapping.tenant_id == tenant_id)
        )).scalar() or 0

        total_product_projects = (await self._session.execute(
            select(sa_func.count()).select_from(ProductProject).where(ProductProject.tenant_id == tenant_id)
        )).scalar() or 0

        active_projects = (await self._session.execute(
            select(sa_func.count()).select_from(ProductProject)
            .where(ProductProject.tenant_id == tenant_id, ProductProject.status == "active")
        )).scalar() or 0

        total_ip_records = (await self._session.execute(
            select(sa_func.count()).select_from(IPRecord).where(IPRecord.tenant_id == tenant_id)
        )).scalar() or 0

        high_risk_ip = (await self._session.execute(
            select(sa_func.count()).select_from(IPRecord)
            .where(IPRecord.tenant_id == tenant_id, IPRecord.risk_level == "high")
        )).scalar() or 0

        total_quality_standards = (await self._session.execute(
            select(sa_func.count()).select_from(QualityStandard).where(QualityStandard.tenant_id == tenant_id)
        )).scalar() or 0

        total_sensitive_words = (await self._session.execute(
            select(sa_func.count()).select_from(SensitiveWord).where(SensitiveWord.tenant_id == tenant_id)
        )).scalar() or 0

        available_upc_count = (await self._session.execute(
            select(sa_func.count()).select_from(UPCPool)
            .where(UPCPool.tenant_id == tenant_id, UPCPool.status == "available")
        )).scalar() or 0

        by_category_rows = (await self._session.execute(
            select(SPU.category_id, sa_func.count())
            .where(SPU.tenant_id == tenant_id)
            .group_by(SPU.category_id)
        )).all()
        spus_by_category = {str(r[0] or "uncategorized"): r[1] for r in by_category_rows}

        by_status_rows = (await self._session.execute(
            select(SPU.status, sa_func.count())
            .where(SPU.tenant_id == tenant_id)
            .group_by(SPU.status)
        )).all()
        spus_by_status = {r[0] or "unknown": r[1] for r in by_status_rows}

        return {
            "total_categories": total_categories,
            "total_brands": total_brands,
            "total_spus": total_spus,
            "active_spus": active_spus,
            "total_skus": total_skus,
            "active_skus": active_skus,
            "total_channel_mappings": total_channel_mappings,
            "total_product_projects": total_product_projects,
            "active_projects": active_projects,
            "total_ip_records": total_ip_records,
            "high_risk_ip": high_risk_ip,
            "total_quality_standards": total_quality_standards,
            "total_sensitive_words": total_sensitive_words,
            "available_upc_count": available_upc_count,
            "spus_by_category": spus_by_category,
            "spus_by_status": spus_by_status,
        }

    async def search_spus(self, tenant_id: str, keyword: str = "", category_id: str = "",
                           brand_id: str = "", status: str = "", spu_type: str = "",
                           page: int = 1, page_size: int = 20) -> tuple[list[SPU], int]:
        """多维度搜索SPU"""
        conditions = [SPU.tenant_id == tenant_id]
        if keyword:
            conditions.append((SPU.code.contains(keyword) | SPU.name.contains(keyword)))
        if category_id:
            conditions.append(SPU.category_id == category_id)
        if brand_id:
            conditions.append(SPU.brand_id == brand_id)
        if status:
            conditions.append(SPU.status == status)
        if spu_type:
            conditions.append(SPU.spu_type == spu_type)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(SPU).where(*conditions)
        )).scalar() or 0
        stmt = select(SPU).where(*conditions).order_by(
            SPU.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total


class ProductLifecycleService:
    """
    产品生命周期管理服务

    管理产品从开发→上架→成熟→衰退→下架的全生命周期:
    - 阶段自动识别
    - 阶段转换审批
    - 生命周期报表
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def identify_lifecycle_stage(self, tenant_id: str, spu_id: str) -> dict:
        """识别产品生命周期阶段"""
        spu = (await self._session.execute(
            select(SPU).where(SPU.id == spu_id, SPU.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not spu:
            raise NotFoundException(message=f"SPU '{spu_id}' not found")
        skus = (await self._session.execute(
            select(SKU).where(SKU.spu_id == spu_id, SKU.tenant_id == tenant_id)
        )).scalars().all()
        active_skus = sum(1 for s in skus if s.status == "active")
        inactive_skus = sum(1 for s in skus if s.status == "inactive")
        if spu.status == "draft":
            stage = "development"
        elif spu.status == "active" and active_skus > 0:
            from datetime import UTC, datetime
            days_since_created = (datetime.now(UTC) - spu.created_at).days if spu.created_at else 0
            if days_since_created <= 30:
                stage = "launch"
            elif days_since_created <= 180:
                stage = "growth"
            elif days_since_created <= 365:
                stage = "mature"
            else:
                stage = "decline"
        elif spu.status == "inactive" or inactive_skus == len(skus):
            stage = "discontinued"
        else:
            stage = "unknown"
        return {
            "spu_id": spu_id, "spu_name": spu.name, "current_status": spu.status,
            "lifecycle_stage": stage, "total_skus": len(skus),
            "active_skus": active_skus, "inactive_skus": inactive_skus,
        }

    async def get_lifecycle_distribution(self, tenant_id: str) -> dict:
        """获取产品生命周期分布"""
        spus = (await self._session.execute(
            select(SPU).where(SPU.tenant_id == tenant_id)
        )).scalars().all()
        distribution: dict[str, int] = {
            "development": 0, "launch": 0, "growth": 0,
            "mature": 0, "decline": 0, "discontinued": 0,
        }
        for spu in spus:
            result = await self.identify_lifecycle_stage(tenant_id, str(spu.id))
            stage = result["lifecycle_stage"]
            if stage in distribution:
                distribution[stage] += 1
        total = sum(distribution.values())
        return {
            "total_spus": total, "distribution": distribution,
            "percentages": {k: round(v / total * 100, 1) for k, v in distribution.items()} if total > 0 else {},
        }


class SKUCostAnalysisService:
    """
    SKU成本分析服务

    分析SKU的采购成本/物流成本/平台费用/利润率:
    - 成本构成分解
    - 利润率计算
    - 成本趋势分析
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def analyze_sku_cost(self, tenant_id: str, sku_id: str) -> dict:
        """分析SKU成本构成"""
        sku = (await self._session.execute(
            select(SKU).where(SKU.id == sku_id, SKU.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not sku:
            raise NotFoundException(message=f"SKU '{sku_id}' not found")
        purchase_cost = float(sku.cost_price or 0)
        shipping_cost = float(sku.weight or 0) * 5.0 if sku.weight else 0
        platform_fee_rate = 0.15
        selling_price = float(sku.retail_price or 0)
        platform_fee = selling_price * platform_fee_rate
        packaging_cost = 1.5
        total_cost = purchase_cost + shipping_cost + platform_fee + packaging_cost
        profit = selling_price - total_cost
        profit_margin = (profit / selling_price * 100) if selling_price > 0 else 0
        return {
            "sku_id": sku_id, "sku_code": sku.sku_code, "sku_name": sku.name,
            "selling_price": round(selling_price, 2),
            "cost_breakdown": {
                "purchase_cost": round(purchase_cost, 2),
                "shipping_cost": round(shipping_cost, 2),
                "platform_fee": round(platform_fee, 2),
                "packaging_cost": round(packaging_cost, 2),
            },
            "total_cost": round(total_cost, 2),
            "profit": round(profit, 2),
            "profit_margin": round(profit_margin, 2),
            "health": "excellent" if profit_margin >= 30 else "good" if profit_margin >= 15 else "warning" if profit_margin >= 5 else "poor",
        }

    async def batch_analyze_costs(self, tenant_id: str, spu_id: str = "") -> dict:
        """批量分析SKU成本"""
        conditions = [SKU.tenant_id == tenant_id]
        if spu_id:
            conditions.append(SKU.spu_id == spu_id)
        skus = (await self._session.execute(
            select(SKU).where(*conditions)
        )).scalars().all()
        results = []
        for sku in skus:
            analysis = await self.analyze_sku_cost(tenant_id, str(sku.id))
            results.append(analysis)
        if not results:
            return {"total_skus": 0, "avg_profit_margin": 0, "health_distribution": {}}
        avg_margin = sum(r["profit_margin"] for r in results) / len(results)
        health_dist = {}
        for r in results:
            h = r["health"]
            health_dist[h] = health_dist.get(h, 0) + 1
        return {
            "total_skus": len(results), "avg_profit_margin": round(avg_margin, 2),
            "health_distribution": health_dist,
            "low_margin_skus": [r for r in results if r["profit_margin"] < 10],
        }


class ComplianceCheckService:
    """
    产品合规检查应用服务

    编排产品合规性检查: 敏感词扫描 → IP风险检测 → 质量标准匹配 → 合规报告生成
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def check_listing_compliance(self, tenant_id: str, sku_id: str,
                                        title: str, description: str = "",
                                        bullet_points: list[str] | None = None) -> dict:
        """
        检查Listing合规性

        流程: 敏感词扫描 → IP侵权检测 → 质量标准匹配 → 汇总报告
        """
        sensitive_result = await self._scan_sensitive_words(tenant_id, title, description, bullet_points)
        ip_result = await self._check_ip_risks(tenant_id, sku_id)
        quality_result = await self._check_quality_standards(tenant_id, sku_id)
        is_compliant = not sensitive_result["found"] and ip_result["risk_level"] in ("none", "low")
        overall_risk = "none"
        if sensitive_result["severity"] == "critical" or ip_result["risk_level"] == "high":
            overall_risk = "high"
            is_compliant = False
        elif sensitive_result["severity"] == "warning" or ip_result["risk_level"] == "medium":
            overall_risk = "medium"
        elif sensitive_result["found"] or ip_result["risk_level"] == "low":
            overall_risk = "low"
        return {
            "sku_id": sku_id, "is_compliant": is_compliant,
            "overall_risk": overall_risk,
            "sensitive_word_check": sensitive_result,
            "ip_risk_check": ip_result,
            "quality_check": quality_result,
        }

    async def _scan_sensitive_words(self, tenant_id: str, title: str,
                                     description: str, bullet_points: list[str] | None) -> dict:
        """扫描敏感词"""
        words = list((await self._session.execute(
            select(SensitiveWord).where(SensitiveWord.tenant_id == tenant_id, SensitiveWord.status == "active")
        )).scalars().all())
        if not words:
            return {"found": False, "matches": [], "severity": "none"}
        text_to_check = f"{title} {description}"
        if bullet_points:
            text_to_check += " " + " ".join(bullet_points)
        text_lower = text_to_check.lower()
        matches: list[dict] = []
        max_severity = "none"
        for w in words:
            if w.word.lower() in text_lower:
                severity = "warning"
                if w.word_type == "prohibited":
                    severity = "critical"
                elif w.word_type == "trademark":
                    severity = "warning"
                matches.append({"word": w.word, "word_type": w.word_type, "severity": severity})
                if severity == "critical":
                    max_severity = "critical"
                elif severity == "warning" and max_severity != "critical":
                    max_severity = "warning"
        return {"found": len(matches) > 0, "matches": matches, "severity": max_severity}

    async def _check_ip_risks(self, tenant_id: str, sku_id: str) -> dict:
        """检查IP风险"""
        ip_records = list((await self._session.execute(
            select(IPRecord).where(
                IPRecord.tenant_id == tenant_id,
                IPRecord.sku_id == sku_id,
                IPRecord.status == "active",
            )
        )).scalars().all())
        if not ip_records:
            return {"risk_level": "none", "records": [], "has_risk": False}
        max_risk = "none"
        records: list[dict] = []
        risk_order = {"none": 0, "low": 1, "medium": 2, "high": 3}
        for ip in ip_records:
            records.append({
                "ip_type": ip.ip_type, "ip_name": ip.ip_name,
                "risk_level": ip.risk_level, "status": ip.status,
            })
            if risk_order.get(ip.risk_level, 0) > risk_order.get(max_risk, 0):
                max_risk = ip.risk_level
        return {"risk_level": max_risk, "records": records, "has_risk": max_risk in ("medium", "high")}

    async def _check_quality_standards(self, tenant_id: str, sku_id: str) -> dict:
        """检查质量标准"""
        sku = (await self._session.execute(
            select(SKU).where(SKU.id == sku_id, SKU.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not sku:
            return {"matched": False, "issues": ["SKU not found"]}
        spu = (await self._session.execute(
            select(SPU).where(SPU.id == sku.spu_id, SPU.tenant_id == tenant_id)
        )).scalar_one_or_none()
        issues: list[str] = []
        if not sku.barcode:
            issues.append("Missing barcode")
        if sku.weight <= 0:
            issues.append("Weight not set")
        if sku.cost_price <= 0:
            issues.append("Cost price not set")
        if spu and spu.category_id:
            standard = (await self._session.execute(
                select(QualityStandard).where(
                    QualityStandard.tenant_id == tenant_id,
                    QualityStandard.category_id == spu.category_id,
                    QualityStandard.status == "active",
                )
            )).scalar_one_or_none()
            if standard:
                import json as _json
                try:
                    items = _json.loads(standard.items_json or "[]")
                except Exception:
                    items = []
                for item in items:
                    if item.get("required") and not item.get("value"):
                        issues.append(f"Quality item '{item.get('name', 'unknown')}' not fulfilled")
        return {"matched": len(issues) == 0, "issues": issues}

    async def batch_compliance_check(self, tenant_id: str, sku_ids: list[str]) -> dict:
        """批量合规检查"""
        results = []
        compliant_count = 0
        for sku_id in sku_ids:
            sku = (await self._session.execute(
                select(SKU).where(SKU.id == sku_id, SKU.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if not sku:
                results.append({"sku_id": sku_id, "is_compliant": False, "overall_risk": "high", "error": "SKU not found"})
                continue
            check = await self.check_listing_compliance(
                tenant_id, sku_id, title=sku.name or "",
            )
            results.append(check)
            if check["is_compliant"]:
                compliant_count += 1
        return {
            "total_checked": len(sku_ids), "compliant_count": compliant_count,
            "non_compliant_count": len(sku_ids) - compliant_count,
            "compliance_rate": round(compliant_count / len(sku_ids) * 100, 1) if sku_ids else 0,
            "results": results,
        }


class SKUAutoGenerationService:
    """
    SKU自动生成应用服务

    编排SKU自动生成: SPU信息提取 → 规格组合生成 → 编码规则 → 批量创建
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def generate_skus_from_variants(self, tenant_id: str, spu_id: str,
                                           variant_matrix: dict) -> dict:
        """
        根据变体矩阵自动生成SKU

        variant_matrix: {"颜色": ["红","蓝"], "尺码": ["S","M","L"]}
        流程: 验证SPU → 生成规格组合 → 编码 → 批量创建
        """
        spu = (await self._session.execute(
            select(SPU).where(SPU.id == spu_id, SPU.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not spu:
            raise NotFoundException(message=f"SPU '{spu_id}' not found")
        import json as _json
        combinations = self._generate_combinations(variant_matrix)
        created_skus: list[dict] = []
        skipped: list[dict] = []
        for combo in combinations:
            variant_attrs = dict(combo)
            sku_code = await self._generate_sku_code(tenant_id, spu, variant_attrs)
            existing = (await self._session.execute(
                select(SKU).where(SKU.sku_code == sku_code, SKU.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if existing:
                skipped.append({"sku_code": sku_code, "variant_attrs": variant_attrs, "reason": "already exists"})
                continue
            sku = SKU(
                tenant_id=tenant_id, spu_id=spu_id,
                sku_code=sku_code,
                name=f"{spu.name} {' '.join(variant_attrs.values())}",
                variant_attrs_json=_json.dumps(variant_attrs, ensure_ascii=False),
                cost_price=spu.cost_price if hasattr(spu, "cost_price") else 0,
                cost_currency="CNY",
                status="active",
            )
            self._session.add(sku)
            created_skus.append({"sku_code": sku_code, "variant_attrs": variant_attrs})
        if created_skus:
            await self._session.flush()
        return {
            "spu_id": spu_id, "total_combinations": len(combinations),
            "created_count": len(created_skus), "skipped_count": len(skipped),
            "created_skus": created_skus, "skipped": skipped,
        }

    async def _generate_sku_code(self, tenant_id: str, spu: SPU,
                                  variant_attrs: dict) -> str:
        """生成SKU编码: SPU编码 + 变体缩写"""
        base_code = spu.spu_code if hasattr(spu, "spu_code") and spu.spu_code else str(spu.id)[:8]
        variant_suffix = "-".join(
            v[:3].upper() for v in variant_attrs.values() if v
        )
        return f"{base_code}-{variant_suffix}" if variant_suffix else base_code

    def _generate_combinations(self, variant_matrix: dict) -> list[tuple]:
        """生成规格笛卡尔积"""
        keys = list(variant_matrix.keys())
        values = list(variant_matrix.values())
        if not values:
            return [()]
        from itertools import product as iter_product
        combos = []
        for combo in iter_product(*values):
            combos.append(tuple(zip(keys, combo)))
        return combos

    async def preview_sku_generation(self, tenant_id: str, spu_id: str,
                                      variant_matrix: dict) -> dict:
        """预览SKU生成结果(不实际创建)"""
        spu = (await self._session.execute(
            select(SPU).where(SPU.id == spu_id, SPU.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not spu:
            raise NotFoundException(message=f"SPU '{spu_id}' not found")
        combinations = self._generate_combinations(variant_matrix)
        preview: list[dict] = []
        for combo in combinations:
            variant_attrs = dict(combo)
            sku_code = await self._generate_sku_code(tenant_id, spu, variant_attrs)
            existing = (await self._session.execute(
                select(SKU).where(SKU.sku_code == sku_code, SKU.tenant_id == tenant_id)
            )).scalar_one_or_none()
            preview.append({
                "sku_code": sku_code,
                "name": f"{spu.name} {' '.join(variant_attrs.values())}",
                "variant_attrs": variant_attrs,
                "will_create": existing is None,
            })
        return {
            "spu_id": spu_id, "total_combinations": len(combinations),
            "new_count": sum(1 for p in preview if p["will_create"]),
            "existing_count": sum(1 for p in preview if not p["will_create"]),
            "preview": preview,
        }


class BundleProductService:
    """
    组合产品(Bundle)应用服务

    管理组合产品的子SKU组成关系: 添加/移除/调整子组件。
    组合产品是一种SPU，由多个子SKU按数量和折扣组合而成。
    """

    def __init__(self, repo: BundleProductRepository):
        self._repo = repo

    async def list_by_spu(self, spu_id: str, tenant_id: str) -> list[dict]:
        items = await self._repo.list_by_spu(spu_id, tenant_id)
        return [
            {
                "id": b.id, "tenant_id": b.tenant_id, "spu_id": b.spu_id,
                "component_sku_id": b.component_sku_id, "quantity": b.quantity,
                "discount_pct": b.discount_pct, "sort_order": b.sort_order,
            }
            for b in items
        ]

    async def add_component(self, tenant_id: str, spu_id: str, component_sku_id: str,
                            quantity: int = 1, discount_pct: float = 0.0, sort_order: int = 0) -> dict:
        bundle = BundleProduct(
            tenant_id=tenant_id, spu_id=spu_id, component_sku_id=component_sku_id,
            quantity=quantity, discount_pct=discount_pct, sort_order=sort_order,
        )
        bundle = await self._repo.create(bundle)
        return {"id": bundle.id, "spu_id": bundle.spu_id, "component_sku_id": bundle.component_sku_id}

    async def update_component(self, bundle_id: str, tenant_id: str, **kwargs) -> dict:
        items = await self._repo.list_by_spu("", tenant_id)
        bundle = None
        for b in items:
            if b.id == bundle_id:
                bundle = b
                break
        if not bundle:
            stmt = select(BundleProduct).where(BundleProduct.id == bundle_id, BundleProduct.tenant_id == tenant_id)
            bundle = (await self._repo._session.execute(stmt)).scalar_one_or_none() if hasattr(self._repo, '_session') else None
        if not bundle:
            raise NotFoundException(message=f"Bundle component '{bundle_id}' not found")
        for k, v in kwargs.items():
            if v is not None and hasattr(bundle, k):
                setattr(bundle, k, v)
        bundle = await self._repo.update(bundle)
        return {"id": bundle.id}

    async def remove_component(self, bundle_id: str, tenant_id: str) -> bool:
        result = await self._repo.delete(bundle_id, tenant_id)
        if not result:
            raise NotFoundException(message=f"Bundle component '{bundle_id}' not found")
        return result


class TitleLibraryService:
    """
    标题库应用服务

    管理Listing标题模板与优化参考，支持多语言多平台。
    提供标题的CRUD、SEO评分排序、使用计数递增。
    """

    def __init__(self, repo: TitleLibraryRepository):
        self._repo = repo

    async def create(self, tenant_id: str, req) -> dict:
        title = TitleLibrary(
            tenant_id=tenant_id,
            category_id=req.category_id,
            platform=req.platform,
            language=req.language,
            title=req.title,
            keywords_json=req.keywords_json,
            score=req.score,
            created_by=actor_id_var.get(""),
        )
        title = await self._repo.create(title)
        return {"id": title.id, "title": title.title, "score": title.score}

    async def get(self, title_id: str, tenant_id: str) -> dict:
        title = await self._repo.get_by_id(title_id, tenant_id)
        if not title:
            raise NotFoundException(message=f"Title '{title_id}' not found")
        return {
            "id": title.id, "tenant_id": title.tenant_id, "category_id": title.category_id,
            "platform": title.platform, "language": title.language, "title": title.title,
            "keywords_json": title.keywords_json, "usage_count": title.usage_count,
            "score": title.score, "status": title.status, "created_by": title.created_by,
        }

    async def list(self, tenant_id: str, platform: str = "", language: str = "",
                   page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        items, total = await self._repo.list_by_tenant(tenant_id, platform, language, page, page_size)
        return [
            {
                "id": t.id, "category_id": t.category_id, "platform": t.platform,
                "language": t.language, "title": t.title, "keywords_json": t.keywords_json,
                "usage_count": t.usage_count, "score": t.score, "status": t.status,
            }
            for t in items
        ], total

    async def update(self, title_id: str, tenant_id: str, req) -> dict:
        title = await self._repo.get_by_id(title_id, tenant_id)
        if not title:
            raise NotFoundException(message=f"Title '{title_id}' not found")
        data = req.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(title, k, v)
        title = await self._repo.update(title)
        return {"id": title.id}

    async def delete(self, title_id: str, tenant_id: str) -> bool:
        result = await self._repo.soft_delete(title_id, tenant_id)
        if not result:
            raise NotFoundException(message=f"Title '{title_id}' not found")
        return result


class ImageLibraryService:
    """
    图片库应用服务

    管理产品图片统一管理，支持多平台多类型。
    提供图片的CRUD、按SKU/SPU查询、分页列表。
    """

    def __init__(self, repo: ImageLibraryRepository):
        self._repo = repo

    async def create(self, tenant_id: str, req) -> dict:
        image = ImageLibrary(
            tenant_id=tenant_id,
            sku_id=req.sku_id,
            spu_id=req.spu_id,
            image_type=req.image_type,
            url=req.url,
            thumbnail_url=req.thumbnail_url,
            alt_text=req.alt_text,
            tags_json=req.tags_json,
            platform=req.platform,
            created_by=actor_id_var.get(""),
        )
        image = await self._repo.create(image)
        return {"id": image.id, "url": image.url, "image_type": image.image_type}

    async def get(self, image_id: str, tenant_id: str) -> dict:
        image = await self._repo.get_by_id(image_id, tenant_id)
        if not image:
            raise NotFoundException(message=f"Image '{image_id}' not found")
        return {
            "id": image.id, "tenant_id": image.tenant_id, "sku_id": image.sku_id,
            "spu_id": image.spu_id, "image_type": image.image_type, "url": image.url,
            "thumbnail_url": image.thumbnail_url, "alt_text": image.alt_text,
            "tags_json": image.tags_json, "platform": image.platform, "status": image.status,
        }

    async def list_by_sku(self, sku_id: str, tenant_id: str) -> list[dict]:
        items = await self._repo.list_by_sku(sku_id, tenant_id)
        return [
            {"id": i.id, "image_type": i.image_type, "url": i.url, "thumbnail_url": i.thumbnail_url, "status": i.status}
            for i in items
        ]

    async def list_by_spu(self, spu_id: str, tenant_id: str) -> list[dict]:
        items = await self._repo.list_by_spu(spu_id, tenant_id)
        return [
            {"id": i.id, "image_type": i.image_type, "url": i.url, "thumbnail_url": i.thumbnail_url, "status": i.status}
            for i in items
        ]

    async def list(self, tenant_id: str, image_type: str = "", platform: str = "",
                   page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        items, total = await self._repo.list_by_tenant(tenant_id, image_type, platform, page, page_size)
        return [
            {
                "id": i.id, "sku_id": i.sku_id, "spu_id": i.spu_id,
                "image_type": i.image_type, "url": i.url, "thumbnail_url": i.thumbnail_url,
                "platform": i.platform, "status": i.status,
            }
            for i in items
        ], total

    async def update(self, image_id: str, tenant_id: str, req) -> dict:
        image = await self._repo.get_by_id(image_id, tenant_id)
        if not image:
            raise NotFoundException(message=f"Image '{image_id}' not found")
        data = req.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(image, k, v)
        image = await self._repo.update(image)
        return {"id": image.id}

    async def delete(self, image_id: str, tenant_id: str) -> bool:
        result = await self._repo.soft_delete(image_id, tenant_id)
        if not result:
            raise NotFoundException(message=f"Image '{image_id}' not found")
        return result


class ProductIssueService:
    """
    产品问题记录应用服务

    管理产品质量问题的跟踪与处理: 创建问题 → 分配处理人 → 处理中 → 已解决 → 已关闭。
    支持按严重程度、状态筛选，按SKU关联查询。
    """

    VALID_ISSUE_TYPES = {"quality", "packaging", "labeling", "safety", "compliance"}
    VALID_SEVERITIES = {"critical", "high", "medium", "low"}
    VALID_STATUSES = {"open", "in_progress", "resolved", "closed"}

    def __init__(self, repo: ProductIssueRepository):
        self._repo = repo

    async def create(self, tenant_id: str, req) -> dict:
        if req.issue_type not in self.VALID_ISSUE_TYPES:
            raise ValidationException(message=f"Invalid issue_type '{req.issue_type}'")
        if req.severity not in self.VALID_SEVERITIES:
            raise ValidationException(message=f"Invalid severity '{req.severity}'")
        issue = ProductIssue(
            tenant_id=tenant_id,
            sku_id=req.sku_id,
            spu_id=req.spu_id,
            issue_type=req.issue_type,
            severity=req.severity,
            description=req.description,
            evidence_json=req.evidence_json,
            assigned_to=req.assigned_to,
            created_by=actor_id_var.get(""),
        )
        issue = await self._repo.create(issue)
        return {"id": issue.id, "issue_type": issue.issue_type, "severity": issue.severity, "status": issue.status}

    async def get(self, issue_id: str, tenant_id: str) -> dict:
        issue = await self._repo.get_by_id(issue_id, tenant_id)
        if not issue:
            raise NotFoundException(message=f"Product issue '{issue_id}' not found")
        return {
            "id": issue.id, "tenant_id": issue.tenant_id, "sku_id": issue.sku_id,
            "spu_id": issue.spu_id, "issue_type": issue.issue_type, "severity": issue.severity,
            "description": issue.description, "evidence_json": issue.evidence_json,
            "status": issue.status, "assigned_to": issue.assigned_to, "resolution": issue.resolution,
        }

    async def list(self, tenant_id: str, status: str = "", severity: str = "",
                   page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        items, total = await self._repo.list_by_tenant(tenant_id, status, severity, page, page_size)
        return [
            {
                "id": i.id, "sku_id": i.sku_id, "spu_id": i.spu_id,
                "issue_type": i.issue_type, "severity": i.severity, "status": i.status,
                "assigned_to": i.assigned_to,
            }
            for i in items
        ], total

    async def list_by_sku(self, sku_id: str, tenant_id: str) -> list[dict]:
        items = await self._repo.list_by_sku(sku_id, tenant_id)
        return [
            {"id": i.id, "issue_type": i.issue_type, "severity": i.severity, "status": i.status}
            for i in items
        ]

    async def update(self, issue_id: str, tenant_id: str, req) -> dict:
        issue = await self._repo.get_by_id(issue_id, tenant_id)
        if not issue:
            raise NotFoundException(message=f"Product issue '{issue_id}' not found")
        data = req.model_dump(exclude_unset=True)
        if "status" in data and data["status"] not in self.VALID_STATUSES:
            raise ValidationException(message=f"Invalid status '{data['status']}'")
        if "severity" in data and data["severity"] not in self.VALID_SEVERITIES:
            raise ValidationException(message=f"Invalid severity '{data['severity']}'")
        for k, v in data.items():
            setattr(issue, k, v)
        if data.get("status") == "resolved":
            from datetime import UTC, datetime
            issue.resolved_at = datetime.now(UTC)
        issue = await self._repo.update(issue)
        return {"id": issue.id, "status": issue.status}

    async def search_skus(self, tenant_id: str, keyword: str = "", spu_id: str = "",
                           status: str = "", page: int = 1, page_size: int = 20) -> tuple[list[SKU], int]:
        """多维度搜索SKU"""
        conditions = [SKU.tenant_id == tenant_id]
        if keyword:
            conditions.append((SKU.sku_code.contains(keyword) | SKU.name.contains(keyword)))
        if spu_id:
            conditions.append(SKU.spu_id == spu_id)
        if status:
            conditions.append(SKU.status == status)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(SKU).where(*conditions)
        )).scalar() or 0
        stmt = select(SKU).where(*conditions).order_by(
            SKU.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total
