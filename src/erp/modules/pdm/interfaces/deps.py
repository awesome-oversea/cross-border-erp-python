"""
PDM 模块依赖注入工厂 - 提供所有应用服务的 FastAPI Depends 工厂函数

本模块将仓储接口的创建与服务的组装集中管理，
路由层通过 Depends(get_xxx_service) 获取已注入仓储的服务实例，
实现控制反转（IoC）和依赖倒置（DIP）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends

from erp.modules.pdm.application.services import (
    BrandService,
    BundleProductService,
    CategoryService,
    ChannelSKUMappingService,
    ImageLibraryService,
    IPRecordService,
    PDMQueryService,
    ProductCollectionService,
    ProductIssueService,
    ProductProjectService,
    QualityStandardService,
    SKUService,
    SPUService,
    SensitiveWordService,
    TitleLibraryService,
    UPCPoolService,
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
from erp.modules.pdm.infrastructure.repositories import (
    SqlBrandRepository,
    SqlBundleProductRepository,
    SqlCategoryRepository,
    SqlChannelSKUMappingRepository,
    SqlImageLibraryRepository,
    SqlIPRecordRepository,
    SqlProductIssueRepository,
    SqlProductProjectRepository,
    SqlQualityStandardRepository,
    SqlSensitiveWordRepository,
    SqlSKURepository,
    SqlSPURepository,
    SqlTitleLibraryRepository,
    SqlUPCPoolRepository,
)
from erp.shared.db.session import get_db_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _get_category_repo(session: AsyncSession) -> CategoryRepository:
    return SqlCategoryRepository(session)


def _get_brand_repo(session: AsyncSession) -> BrandRepository:
    return SqlBrandRepository(session)


def _get_spu_repo(session: AsyncSession) -> SPURepository:
    return SqlSPURepository(session)


def _get_sku_repo(session: AsyncSession) -> SKURepository:
    return SqlSKURepository(session)


def _get_channel_sku_mapping_repo(session: AsyncSession) -> ChannelSKUMappingRepository:
    return SqlChannelSKUMappingRepository(session)


def _get_product_project_repo(session: AsyncSession) -> ProductProjectRepository:
    return SqlProductProjectRepository(session)


def _get_quality_standard_repo(session: AsyncSession) -> QualityStandardRepository:
    return SqlQualityStandardRepository(session)


def _get_ip_record_repo(session: AsyncSession) -> IPRecordRepository:
    return SqlIPRecordRepository(session)


def _get_sensitive_word_repo(session: AsyncSession) -> SensitiveWordRepository:
    return SqlSensitiveWordRepository(session)


def _get_upc_pool_repo(session: AsyncSession) -> UPCPoolRepository:
    return SqlUPCPoolRepository(session)


async def get_category_service(session: AsyncSession = Depends(get_db_session)) -> CategoryService:
    return CategoryService(session=session, category_repo=_get_category_repo(session))


async def get_brand_service(session: AsyncSession = Depends(get_db_session)) -> BrandService:
    return BrandService(session=session, brand_repo=_get_brand_repo(session))


async def get_spu_service(session: AsyncSession = Depends(get_db_session)) -> SPUService:
    return SPUService(session=session, spu_repo=_get_spu_repo(session))


async def get_sku_service(session: AsyncSession = Depends(get_db_session)) -> SKUService:
    return SKUService(session=session, sku_repo=_get_sku_repo(session))


async def get_channel_sku_mapping_service(session: AsyncSession = Depends(get_db_session)) -> ChannelSKUMappingService:
    return ChannelSKUMappingService(session=session, mapping_repo=_get_channel_sku_mapping_repo(session))


async def get_product_project_service(session: AsyncSession = Depends(get_db_session)) -> ProductProjectService:
    return ProductProjectService(session=session, project_repo=_get_product_project_repo(session))


async def get_quality_standard_service(session: AsyncSession = Depends(get_db_session)) -> QualityStandardService:
    return QualityStandardService(session=session, qs_repo=_get_quality_standard_repo(session))


async def get_ip_record_service(session: AsyncSession = Depends(get_db_session)) -> IPRecordService:
    return IPRecordService(session=session, ip_repo=_get_ip_record_repo(session))


async def get_sensitive_word_service(session: AsyncSession = Depends(get_db_session)) -> SensitiveWordService:
    return SensitiveWordService(session=session, word_repo=_get_sensitive_word_repo(session))


async def get_upc_pool_service(session: AsyncSession = Depends(get_db_session)) -> UPCPoolService:
    return UPCPoolService(session=session, upc_repo=_get_upc_pool_repo(session))


async def get_product_collection_service(session: AsyncSession = Depends(get_db_session)) -> ProductCollectionService:
    return ProductCollectionService(session=session)


async def get_pdm_query_service(session: AsyncSession = Depends(get_db_session)) -> PDMQueryService:
    return PDMQueryService(session=session)


def _get_bundle_product_repo(session: AsyncSession) -> BundleProductRepository:
    return SqlBundleProductRepository(session)


def _get_title_library_repo(session: AsyncSession) -> TitleLibraryRepository:
    return SqlTitleLibraryRepository(session)


def _get_image_library_repo(session: AsyncSession) -> ImageLibraryRepository:
    return SqlImageLibraryRepository(session)


def _get_product_issue_repo(session: AsyncSession) -> ProductIssueRepository:
    return SqlProductIssueRepository(session)


async def get_bundle_product_service(session: AsyncSession = Depends(get_db_session)) -> BundleProductService:
    return BundleProductService(repo=_get_bundle_product_repo(session))


async def get_title_library_service(session: AsyncSession = Depends(get_db_session)) -> TitleLibraryService:
    return TitleLibraryService(repo=_get_title_library_repo(session))


async def get_image_library_service(session: AsyncSession = Depends(get_db_session)) -> ImageLibraryService:
    return ImageLibraryService(repo=_get_image_library_repo(session))


async def get_product_issue_service(session: AsyncSession = Depends(get_db_session)) -> ProductIssueService:
    return ProductIssueService(repo=_get_product_issue_repo(session))
