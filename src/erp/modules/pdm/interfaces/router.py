"""
PDM 内部路由 - 产品域内部API端点

路径规范：/{service}/api/v1/{resource}
所有端点通过依赖注入获取服务实例，不直接操作数据库会话。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from erp.modules.pdm.application.dtos import (
    BundleProductCreateRequest,
    BundleProductUpdateRequest,
    ImageLibraryCreateRequest,
    ImageLibraryUpdateRequest,
    ProductIssueCreateRequest,
    ProductIssueUpdateRequest,
    SKUSearchRequest,
    SPUSearchRequest,
    TitleLibraryCreateRequest,
    TitleLibraryUpdateRequest,
)
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
    SensitiveWordService,
    SKUService,
    SPUService,
    TitleLibraryService,
    UPCPoolService,
)
from erp.modules.pdm.interfaces.deps import (
    get_brand_service,
    get_bundle_product_service,
    get_category_service,
    get_channel_sku_mapping_service,
    get_image_library_service,
    get_ip_record_service,
    get_pdm_query_service,
    get_product_collection_service,
    get_product_issue_service,
    get_product_project_service,
    get_quality_standard_service,
    get_sensitive_word_service,
    get_sku_service,
    get_spu_service,
    get_title_library_service,
    get_upc_pool_service,
)
from erp.shared.context import tenant_id_var, trace_id_var
from erp.shared.exceptions import NotFoundException, Result

router = APIRouter(prefix="/pdm/v1", tags=["PDM - 产品域管理"])


class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)
    parent_id: str | None = None
    sort_order: int = 0


class BrandCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)
    name_en: str = ""
    logo_url: str = ""


class SPUCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)
    name_en: str = ""
    category_id: str | None = None
    brand_id: str | None = None
    description: str = ""
    main_image: str = ""
    images: list[str] = Field(default_factory=list)
    attributes: dict = Field(default_factory=dict)
    spu_type: str = "normal"
    origin_country: str = ""
    hs_code: str = ""
    declared_value: float = 0.0
    declared_currency: str = "CNY"


class SKUCreateRequest(BaseModel):
    spu_id: str = Field(..., min_length=1)
    sku_code: str = Field(..., min_length=1)
    barcode: str = ""
    name: str = ""
    variant_attrs: dict = Field(default_factory=dict)
    spec: dict = Field(default_factory=dict)
    weight: float = 0.0
    length: float = 0.0
    width: float = 0.0
    height: float = 0.0
    cost_price: float = 0.0
    cost_currency: str = "CNY"
    purchase_price: float = 0.0
    supplier_id: str | None = None
    image: str = ""


class ChannelMappingRequest(BaseModel):
    sku_id: str = Field(..., min_length=1)
    channel: str = Field(..., min_length=1)
    channel_sku: str = Field(..., min_length=1)
    channel_product_id: str = ""
    store_id: str = ""


class ProductProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)
    category_id: str | None = None
    priority: str = "medium"
    owner_id: str = ""
    target_market: str = ""
    target_platform: str = ""
    recommendation_id: str = ""


class SPUStatusUpdateRequest(BaseModel):
    status: str = Field(..., min_length=1)


class IPRecordCreateRequest(BaseModel):
    ip_type: str = Field(..., min_length=1)
    ip_name: str = ""
    ip_number: str = ""
    sku_id: str | None = None
    spu_id: str | None = None
    risk_level: str = "none"


class QualityStandardCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    category_id: str | None = None
    standard_items: dict = Field(default_factory=dict)


class SensitiveWordCreateRequest(BaseModel):
    word: str = Field(..., min_length=1)
    word_type: str = "forbidden"
    platform: str = ""


class UPCBatchCreateRequest(BaseModel):
    upc_codes: list[str] = Field(..., min_length=1)


class UPCAllocateRequest(BaseModel):
    upc_code: str = Field(..., min_length=1)
    sku_id: str = Field(..., min_length=1)


class UPCReleaseRequest(BaseModel):
    upc_code: str = Field(..., min_length=1)


class TrademarkCheckRequest(BaseModel):
    product_name: str = Field(..., min_length=1)


class CollectionCreateRequest(BaseModel):
    source_platform: str = Field(..., min_length=1)
    source_url: str = Field(..., min_length=1)
    title: str = ""
    price: float = 0.0
    sales_data: dict = Field(default_factory=dict)
    review_data: dict = Field(default_factory=dict)


class CollectionStatusUpdateRequest(BaseModel):
    status: str = Field(..., min_length=1)


@router.post("/categories", response_model=None)
async def create_category(req: CategoryCreateRequest, svc: CategoryService = Depends(get_category_service)):
    cat = await svc.create(tenant_id_var.get(""), name=req.name, code=req.code, parent_id=req.parent_id, sort_order=req.sort_order)
    return Result.ok(data={"id": cat.id, "code": cat.code}, trace_id=trace_id_var.get(""))


@router.get("/categories", response_model=None)
async def list_categories(svc: CategoryService = Depends(get_category_service)):
    tree = await svc.list_tree(tenant_id_var.get(""))
    return Result.ok(data=tree, trace_id=trace_id_var.get(""))


@router.put("/categories/{cat_id}", response_model=None)
async def update_category(cat_id: str, name: str = "", sort_order: int = 0,
                          svc: CategoryService = Depends(get_category_service)):
    kwargs = {}
    if name:
        kwargs["name"] = name
    if sort_order:
        kwargs["sort_order"] = sort_order
    cat = await svc.update(cat_id, tenant_id_var.get(""), **kwargs)
    return Result.ok(data={"id": cat.id, "name": cat.name}, trace_id=trace_id_var.get(""))


@router.delete("/categories/{cat_id}", response_model=None)
async def delete_category(cat_id: str, svc: CategoryService = Depends(get_category_service)):
    deleted = await svc.soft_delete(cat_id, tenant_id_var.get(""))
    return Result.ok(data={"deleted": deleted}, trace_id=trace_id_var.get(""))


@router.post("/brands", response_model=None)
async def create_brand(req: BrandCreateRequest, svc: BrandService = Depends(get_brand_service)):
    brand = await svc.create(tenant_id_var.get(""), name=req.name, code=req.code, name_en=req.name_en, logo_url=req.logo_url)
    return Result.ok(data={"id": brand.id, "code": brand.code}, trace_id=trace_id_var.get(""))


@router.get("/brands", response_model=None)
async def list_brands(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                      svc: BrandService = Depends(get_brand_service)):
    items, total = await svc.list_all(tenant_id_var.get(""), page=page, page_size=page_size)
    data = [{"id": b.id, "name": b.name, "code": b.code, "status": b.status} for b in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.put("/brands/{brand_id}", response_model=None)
async def update_brand(brand_id: str, name: str = "", name_en: str = "", logo_url: str = "",
                       svc: BrandService = Depends(get_brand_service)):
    kwargs = {}
    if name:
        kwargs["name"] = name
    if name_en:
        kwargs["name_en"] = name_en
    if logo_url:
        kwargs["logo_url"] = logo_url
    brand = await svc.update(brand_id, tenant_id_var.get(""), **kwargs)
    return Result.ok(data={"id": brand.id, "name": brand.name}, trace_id=trace_id_var.get(""))


@router.delete("/brands/{brand_id}", response_model=None)
async def delete_brand(brand_id: str, svc: BrandService = Depends(get_brand_service)):
    deleted = await svc.soft_delete(brand_id, tenant_id_var.get(""))
    return Result.ok(data={"deleted": deleted}, trace_id=trace_id_var.get(""))


@router.post("/spus", response_model=None)
async def create_spu(req: SPUCreateRequest, svc: SPUService = Depends(get_spu_service)):
    spu = await svc.create(
        tenant_id_var.get(""), name=req.name, code=req.code, name_en=req.name_en,
        category_id=req.category_id, brand_id=req.brand_id, description=req.description,
        main_image=req.main_image, images_json=json.dumps(req.images, default=str),
        attributes_json=json.dumps(req.attributes, default=str), spu_type=req.spu_type,
        origin_country=req.origin_country, hs_code=req.hs_code,
        declared_value=req.declared_value, declared_currency=req.declared_currency,
    )
    return Result.ok(data={"id": spu.id, "code": spu.code, "status": spu.status}, trace_id=trace_id_var.get(""))


@router.get("/spus", response_model=None)
async def list_spus(status: str = Query(default=""), page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                    svc: SPUService = Depends(get_spu_service)):
    items, total = await svc.list_all(tenant_id_var.get(""), status=status, page=page, page_size=page_size)
    data = [{"id": s.id, "name": s.name, "code": s.code, "status": s.status, "category_id": s.category_id} for s in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/spus/{spu_id}", response_model=None)
async def get_spu(spu_id: str, svc: SPUService = Depends(get_spu_service)):
    spu = await svc.get_or_raise(spu_id, tenant_id_var.get(""))
    return Result.ok(data={
        "id": spu.id, "name": spu.name, "code": spu.code, "status": spu.status,
        "category_id": spu.category_id, "brand_id": spu.brand_id,
        "attributes": json.loads(spu.attributes_json) if spu.attributes_json else {},
        "images": json.loads(spu.images_json) if spu.images_json else [],
    }, trace_id=trace_id_var.get(""))


@router.put("/spus/{spu_id}/status", response_model=None)
async def update_spu_status(spu_id: str, req: SPUStatusUpdateRequest, svc: SPUService = Depends(get_spu_service)):
    spu = await svc.update_status(spu_id, tenant_id_var.get(""), status=req.status)
    return Result.ok(data={"id": spu.id, "code": spu.code, "status": spu.status}, trace_id=trace_id_var.get(""))


@router.post("/skus", response_model=None)
async def create_sku(req: SKUCreateRequest, svc: SKUService = Depends(get_sku_service)):
    sku = await svc.create(
        tenant_id_var.get(""), spu_id=req.spu_id, sku_code=req.sku_code,
        barcode=req.barcode, name=req.name,
        variant_attrs_json=json.dumps(req.variant_attrs, default=str),
        spec_json=json.dumps(req.spec, default=str),
        weight=req.weight, length=req.length, width=req.width, height=req.height,
        cost_price=req.cost_price, cost_currency=req.cost_currency,
        purchase_price=req.purchase_price, supplier_id=req.supplier_id, image=req.image,
    )
    return Result.ok(data={"id": sku.id, "sku_code": sku.sku_code, "status": sku.status}, trace_id=trace_id_var.get(""))


@router.get("/skus", response_model=None)
async def list_skus(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                    svc: SKUService = Depends(get_sku_service)):
    items, total = await svc.list_all(tenant_id_var.get(""), page=page, page_size=page_size)
    data = [{"id": s.id, "sku_code": s.sku_code, "spu_id": s.spu_id, "status": s.status, "cost_price": s.cost_price} for s in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/skus/{sku_id}", response_model=None)
async def get_sku(sku_id: str, svc: SKUService = Depends(get_sku_service)):
    sku = await svc.get_or_raise(sku_id, tenant_id_var.get(""))
    return Result.ok(data={
        "id": sku.id, "sku_code": sku.sku_code, "spu_id": sku.spu_id,
        "name": sku.name, "status": sku.status, "barcode": sku.barcode,
        "weight": sku.weight, "length": sku.length, "width": sku.width, "height": sku.height,
        "cost_price": sku.cost_price, "cost_currency": sku.cost_currency,
        "purchase_price": sku.purchase_price, "supplier_id": sku.supplier_id,
        "variant_attrs": json.loads(sku.variant_attrs_json) if sku.variant_attrs_json else {},
        "spec": json.loads(sku.spec_json) if sku.spec_json else {},
    }, trace_id=trace_id_var.get(""))


@router.put("/skus/{sku_id}", response_model=None)
async def update_sku(sku_id: str, name: str = "", cost_price: float = 0.0, purchase_price: float = 0.0,
                     weight: float = 0.0, supplier_id: str = "",
                     svc: SKUService = Depends(get_sku_service)):
    kwargs = {}
    if name:
        kwargs["name"] = name
    if cost_price > 0:
        kwargs["cost_price"] = cost_price
    if purchase_price > 0:
        kwargs["purchase_price"] = purchase_price
    if weight > 0:
        kwargs["weight"] = weight
    if supplier_id:
        kwargs["supplier_id"] = supplier_id
    sku = await svc.update(sku_id, tenant_id_var.get(""), **kwargs)
    return Result.ok(data={"id": sku.id, "sku_code": sku.sku_code}, trace_id=trace_id_var.get(""))


@router.delete("/skus/{sku_id}", response_model=None)
async def delete_sku(sku_id: str, svc: SKUService = Depends(get_sku_service)):
    deleted = await svc.soft_delete(sku_id, tenant_id_var.get(""))
    return Result.ok(data={"deleted": deleted}, trace_id=trace_id_var.get(""))


@router.get("/spus/{spu_id}/skus", response_model=None)
async def list_spu_skus(spu_id: str, svc: SKUService = Depends(get_sku_service)):
    items = await svc.list_by_spu(spu_id, tenant_id_var.get(""))
    data = [{"id": s.id, "sku_code": s.sku_code, "variant_attrs": s.variant_attrs_json, "status": s.status} for s in items]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/channel-mappings", response_model=None)
async def create_channel_mapping(req: ChannelMappingRequest, svc: ChannelSKUMappingService = Depends(get_channel_sku_mapping_service)):
    mapping = await svc.create_mapping(
        tenant_id_var.get(""), sku_id=req.sku_id, channel=req.channel,
        channel_sku=req.channel_sku, channel_product_id=req.channel_product_id, store_id=req.store_id,
    )
    return Result.ok(data={"id": mapping.id, "channel": mapping.channel, "channel_sku": mapping.channel_sku}, trace_id=trace_id_var.get(""))


@router.get("/skus/{sku_id}/channel-mappings", response_model=None)
async def list_sku_channel_mappings(sku_id: str, svc: ChannelSKUMappingService = Depends(get_channel_sku_mapping_service)):
    items = await svc.get_by_sku(sku_id, tenant_id_var.get(""))
    data = [{"id": m.id, "channel": m.channel, "channel_sku": m.channel_sku, "channel_product_id": m.channel_product_id} for m in items]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/product-projects", response_model=None)
async def create_product_project(req: ProductProjectCreateRequest, svc: ProductProjectService = Depends(get_product_project_service)):
    project = await svc.create(
        tenant_id_var.get(""), name=req.name, code=req.code,
        category_id=req.category_id, priority=req.priority, owner_id=req.owner_id,
        target_market=req.target_market, target_platform=req.target_platform,
        recommendation_id=req.recommendation_id,
    )
    return Result.ok(data={"id": project.id, "code": project.code, "stage": project.stage}, trace_id=trace_id_var.get(""))


@router.get("/product-projects", response_model=None)
async def list_product_projects(stage: str = Query(default=""), page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                                svc: ProductProjectService = Depends(get_product_project_service)):
    items, total = await svc.list_all(tenant_id_var.get(""), stage=stage, page=page, page_size=page_size)
    data = [{"id": p.id, "name": p.name, "code": p.code, "stage": p.stage, "status": p.status} for p in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/product-projects/{project_id}", response_model=None)
async def get_product_project(project_id: str, svc: ProductProjectService = Depends(get_product_project_service)):
    project = await svc.get_or_raise(project_id, tenant_id_var.get(""))
    return Result.ok(data={
        "id": project.id, "name": project.name, "code": project.code,
        "stage": project.stage, "status": project.status,
        "category_id": project.category_id, "priority": project.priority,
        "owner_id": project.owner_id, "target_market": project.target_market,
        "target_platform": project.target_platform,
    }, trace_id=trace_id_var.get(""))


@router.put("/product-projects/{project_id}/stage", response_model=None)
async def update_project_stage(project_id: str, req: SPUStatusUpdateRequest, svc: ProductProjectService = Depends(get_product_project_service)):
    project = await svc.update_stage(project_id, tenant_id_var.get(""), stage=req.status)
    return Result.ok(data={"id": project.id, "stage": project.stage}, trace_id=trace_id_var.get(""))


@router.post("/ip-records", response_model=None)
async def create_ip_record(req: IPRecordCreateRequest, svc: IPRecordService = Depends(get_ip_record_service)):
    record = await svc.create(
        tenant_id_var.get(""), ip_type=req.ip_type, ip_name=req.ip_name,
        ip_number=req.ip_number, sku_id=req.sku_id, spu_id=req.spu_id,
        risk_level=req.risk_level,
    )
    return Result.ok(data={"id": record.id, "ip_type": record.ip_type, "risk_level": record.risk_level}, trace_id=trace_id_var.get(""))


@router.post("/ip-records/trademark-check", response_model=None)
async def check_trademark(req: TrademarkCheckRequest, svc: IPRecordService = Depends(get_ip_record_service)):
    result = await svc.check_trademark_conflict(tenant_id_var.get(""), product_name=req.product_name)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.get("/ip-records", response_model=None)
async def list_ip_records(sku_id: str = Query(default=""), spu_id: str = Query(default=""),
                          svc: IPRecordService = Depends(get_ip_record_service)):
    if sku_id:
        items = await svc.list_by_sku(sku_id, tenant_id_var.get(""))
    elif spu_id:
        items = await svc.list_by_spu(spu_id, tenant_id_var.get(""))
    else:
        return Result.ok(data=[], trace_id=trace_id_var.get(""))
    data = [{"id": r.id, "ip_type": r.ip_type, "ip_name": r.ip_name,
             "ip_number": r.ip_number, "risk_level": r.risk_level} for r in items]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/quality-standards", response_model=None)
async def create_quality_standard(req: QualityStandardCreateRequest, svc: QualityStandardService = Depends(get_quality_standard_service)):
    qs = await svc.create(tenant_id_var.get(""), name=req.name, category_id=req.category_id, standard_items_json=json.dumps(req.standard_items, default=str))
    return Result.ok(data={"id": qs.id, "name": qs.name}, trace_id=trace_id_var.get(""))


@router.get("/quality-standards", response_model=None)
async def list_quality_standards(category_id: str = Query(default=""), svc: QualityStandardService = Depends(get_quality_standard_service)):
    items = await svc.list_by_tenant(tenant_id_var.get(""), category_id=category_id)
    data = [{"id": q.id, "name": q.name, "category_id": q.category_id} for q in items]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/sensitive-words", response_model=None)
async def create_sensitive_word(req: SensitiveWordCreateRequest, svc: SensitiveWordService = Depends(get_sensitive_word_service)):
    sw = await svc.create(tenant_id_var.get(""), word=req.word, word_type=req.word_type, platform=req.platform)
    return Result.ok(data={"id": sw.id, "word": sw.word, "word_type": sw.word_type}, trace_id=trace_id_var.get(""))


@router.get("/sensitive-words", response_model=None)
async def list_sensitive_words(word_type: str = Query(default=""), platform: str = Query(default=""),
                               svc: SensitiveWordService = Depends(get_sensitive_word_service)):
    items = await svc.list_by_tenant(tenant_id_var.get(""), word_type=word_type, platform=platform)
    data = [{"id": w.id, "word": w.word, "word_type": w.word_type, "platform": w.platform} for w in items]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.delete("/sensitive-words/{word_id}", response_model=None)
async def delete_sensitive_word(word_id: str, svc: SensitiveWordService = Depends(get_sensitive_word_service)):
    deleted = await svc.delete(word_id, tenant_id_var.get(""))
    return Result.ok(data={"deleted": deleted}, trace_id=trace_id_var.get(""))


@router.post("/upc-pool/batch", response_model=None)
async def batch_create_upc(req: UPCBatchCreateRequest, svc: UPCPoolService = Depends(get_upc_pool_service)):
    created = await svc.batch_create(tenant_id_var.get(""), upc_codes=req.upc_codes)
    return Result.ok(data={"created_count": len(created)}, trace_id=trace_id_var.get(""))


@router.post("/upc-pool/allocate", response_model=None)
async def allocate_upc(req: UPCAllocateRequest, svc: UPCPoolService = Depends(get_upc_pool_service)):
    upc = await svc.allocate(upc_code=req.upc_code, sku_id=req.sku_id, tenant_id=tenant_id_var.get(""))
    if not upc:
        raise NotFoundException(message="UPC not available")
    return Result.ok(data={"upc_code": upc.upc_code, "sku_id": upc.sku_id, "status": upc.status}, trace_id=trace_id_var.get(""))


@router.post("/upc-pool/release", response_model=None)
async def release_upc(req: UPCReleaseRequest, svc: UPCPoolService = Depends(get_upc_pool_service)):
    released = await svc.release(upc_code=req.upc_code, tenant_id=tenant_id_var.get(""))
    return Result.ok(data={"released": released}, trace_id=trace_id_var.get(""))


@router.get("/upc-pool/available", response_model=None)
async def list_available_upc(limit: int = Query(default=100, ge=1, le=500), svc: UPCPoolService = Depends(get_upc_pool_service)):
    items = await svc.list_available(tenant_id_var.get(""), limit=limit)
    data = [{"upc_code": u.upc_code, "status": u.status} for u in items]
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/collections", response_model=None)
async def list_collections(status: str = Query(default=""), source_platform: str = Query(default=""),
                           page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                           svc: ProductCollectionService = Depends(get_product_collection_service)):
    items, total = await svc.list_all(tenant_id_var.get(""), status=status, source_platform=source_platform, page=page, page_size=page_size)
    data = [{"id": c.id, "title": c.title, "source_platform": c.source_platform, "score": c.score, "status": c.status} for c in items]
    return Result.paginate(items=data, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.post("/collections", response_model=None)
async def create_collection(req: CollectionCreateRequest,
                             svc: ProductCollectionService = Depends(get_product_collection_service)):
    collection = await svc.create(
        tenant_id_var.get(""), source_platform=req.source_platform,
        source_url=req.source_url, title=req.title, price=req.price,
        sales_data=req.sales_data, review_data=req.review_data,
    )
    return Result.ok(data={"id": collection.id, "title": collection.title,
                           "source_platform": collection.source_platform,
                           "score": collection.score, "status": collection.status},
                     trace_id=trace_id_var.get(""))


@router.get("/collections/{collection_id}", response_model=None)
async def get_collection(collection_id: str,
                          svc: ProductCollectionService = Depends(get_product_collection_service)):
    c = await svc.get_or_raise(collection_id, tenant_id_var.get(""))
    return Result.ok(data={
        "id": c.id, "title": c.title, "source_platform": c.source_platform,
        "source_url": c.source_url, "price": c.price, "score": c.score,
        "status": c.status, "sales_data": json.loads(c.sales_data_json or "{}"),
        "review_data": json.loads(c.review_data_json or "{}"),
    }, trace_id=trace_id_var.get(""))


@router.put("/collections/{collection_id}/status", response_model=None)
async def update_collection_status(collection_id: str, req: CollectionStatusUpdateRequest,
                                    svc: ProductCollectionService = Depends(get_product_collection_service)):
    c = await svc.update_status(collection_id, tenant_id_var.get(""), new_status=req.status)
    return Result.ok(data={"id": c.id, "status": c.status}, trace_id=trace_id_var.get(""))


@router.post("/collections/{collection_id}/analyze", response_model=None)
async def analyze_collection(collection_id: str,
                              svc: ProductCollectionService = Depends(get_product_collection_service)):
    c = await svc.analyze(collection_id, tenant_id_var.get(""))
    return Result.ok(data={"id": c.id, "score": c.score, "status": c.status}, trace_id=trace_id_var.get(""))


@router.post("/collections/{collection_id}/convert-to-spu", response_model=None)
async def convert_collection_to_spu(collection_id: str,
                                     svc: ProductCollectionService = Depends(get_product_collection_service)):
    spu = await svc.convert_to_spu(collection_id, tenant_id_var.get(""))
    return Result.ok(data={"collection_id": collection_id, "spu_id": spu.id,
                           "spu_code": spu.code, "spu_status": spu.status},
                     trace_id=trace_id_var.get(""))


# ──── 统计与搜索端点 ────


@router.get("/statistics", response_model=None, summary="PDM运营统计概览")
async def get_pdm_statistics(
    svc: PDMQueryService = Depends(get_pdm_query_service),
):
    """获取PDM运营统计概览: 分类/品牌/SPU/SKU等核心指标"""
    result = await svc.get_statistics(tenant_id_var.get(""))
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.post("/spus/search", response_model=None, summary="搜索SPU")
async def search_spus(
    req: SPUSearchRequest,
    svc: PDMQueryService = Depends(get_pdm_query_service),
):
    """多维度搜索SPU: 关键词/分类/品牌/状态/类型"""
    items, total = await svc.search_spus(
        tenant_id_var.get(""), keyword=req.keyword, category_id=req.category_id,
        brand_id=req.brand_id, status=req.status, spu_type=req.spu_type,
        page=req.page, page_size=req.page_size,
    )
    data = [{"id": s.id, "name": s.name, "code": s.code, "status": s.status,
             "category_id": s.category_id, "brand_id": s.brand_id} for s in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))


@router.get("/bundles/{spu_id}", response_model=None, summary="查询组合产品子SKU列表")
async def list_bundle_products(
    spu_id: str,
    svc: BundleProductService = Depends(get_bundle_product_service),
):
    """查询指定SPU下的组合产品(Bundle)子SKU组成关系"""
    tid = tenant_id_var.get("")
    data = await svc.list_by_spu(spu_id, tid)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/bundles", response_model=None, summary="添加组合产品子组件")
async def add_bundle_component(
    req: BundleProductCreateRequest,
    svc: BundleProductService = Depends(get_bundle_product_service),
):
    """向组合产品(Bundle)添加子SKU组件"""
    tid = tenant_id_var.get("")
    data = await svc.add_component(
        tid, req.spu_id, req.component_sku_id, req.quantity, req.discount_pct, req.sort_order
    )
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.put("/bundles/{bundle_id}", response_model=None, summary="更新组合产品子组件")
async def update_bundle_component(
    bundle_id: str,
    req: BundleProductUpdateRequest,
    svc: BundleProductService = Depends(get_bundle_product_service),
):
    """更新组合产品(Bundle)子SKU组件的数量/折扣/排序"""
    tid = tenant_id_var.get("")
    data = req.model_dump(exclude_unset=True)
    result = await svc.update_component(bundle_id, tid, **data)
    return Result.ok(data=result, trace_id=trace_id_var.get(""))


@router.delete("/bundles/{bundle_id}", response_model=None, summary="移除组合产品子组件")
async def remove_bundle_component(
    bundle_id: str,
    svc: BundleProductService = Depends(get_bundle_product_service),
):
    """移除组合产品(Bundle)的子SKU组件"""
    tid = tenant_id_var.get("")
    await svc.remove_component(bundle_id, tid)
    return Result.ok(message="Bundle component removed", trace_id=trace_id_var.get(""))


@router.post("/title-library", response_model=None, summary="创建标题库条目")
async def create_title_library(
    req: TitleLibraryCreateRequest,
    svc: TitleLibraryService = Depends(get_title_library_service),
):
    """创建Listing标题模板，支持多语言多平台"""
    tid = tenant_id_var.get("")
    data = await svc.create(tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/title-library", response_model=None, summary="查询标题库列表")
async def list_title_library(
    platform: str = Query(default="", description="平台过滤"),
    language: str = Query(default="", description="语言过滤"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: TitleLibraryService = Depends(get_title_library_service),
):
    """分页查询标题库，支持按平台/语言过滤，按SEO评分排序"""
    tid = tenant_id_var.get("")
    items, total = await svc.list(tid, platform, language, page, page_size)
    return Result.paginate(items=items, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/title-library/{title_id}", response_model=None, summary="查询标题库详情")
async def get_title_library(
    title_id: str,
    svc: TitleLibraryService = Depends(get_title_library_service),
):
    tid = tenant_id_var.get("")
    data = await svc.get(title_id, tid)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.put("/title-library/{title_id}", response_model=None, summary="更新标题库条目")
async def update_title_library(
    title_id: str,
    req: TitleLibraryUpdateRequest,
    svc: TitleLibraryService = Depends(get_title_library_service),
):
    tid = tenant_id_var.get("")
    data = await svc.update(title_id, tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.delete("/title-library/{title_id}", response_model=None, summary="删除标题库条目")
async def delete_title_library(
    title_id: str,
    svc: TitleLibraryService = Depends(get_title_library_service),
):
    tid = tenant_id_var.get("")
    await svc.delete(title_id, tid)
    return Result.ok(message="Title deleted", trace_id=trace_id_var.get(""))


@router.post("/image-library", response_model=None, summary="创建图片库条目")
async def create_image_library(
    req: ImageLibraryCreateRequest,
    svc: ImageLibraryService = Depends(get_image_library_service),
):
    """上传产品图片到图片库，支持多平台多类型"""
    tid = tenant_id_var.get("")
    data = await svc.create(tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/image-library", response_model=None, summary="查询图片库列表")
async def list_image_library(
    image_type: str = Query(default="", description="图片类型过滤"),
    platform: str = Query(default="", description="平台过滤"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: ImageLibraryService = Depends(get_image_library_service),
):
    tid = tenant_id_var.get("")
    items, total = await svc.list(tid, image_type, platform, page, page_size)
    return Result.paginate(items=items, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/image-library/{image_id}", response_model=None, summary="查询图片详情")
async def get_image_library(
    image_id: str,
    svc: ImageLibraryService = Depends(get_image_library_service),
):
    tid = tenant_id_var.get("")
    data = await svc.get(image_id, tid)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/skus/{sku_id}/images", response_model=None, summary="查询SKU关联图片")
async def list_images_by_sku(
    sku_id: str,
    svc: ImageLibraryService = Depends(get_image_library_service),
):
    tid = tenant_id_var.get("")
    data = await svc.list_by_sku(sku_id, tid)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/spus/{spu_id}/images", response_model=None, summary="查询SPU关联图片")
async def list_images_by_spu(
    spu_id: str,
    svc: ImageLibraryService = Depends(get_image_library_service),
):
    tid = tenant_id_var.get("")
    data = await svc.list_by_spu(spu_id, tid)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.put("/image-library/{image_id}", response_model=None, summary="更新图片库条目")
async def update_image_library(
    image_id: str,
    req: ImageLibraryUpdateRequest,
    svc: ImageLibraryService = Depends(get_image_library_service),
):
    tid = tenant_id_var.get("")
    data = await svc.update(image_id, tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.delete("/image-library/{image_id}", response_model=None, summary="删除图片库条目")
async def delete_image_library(
    image_id: str,
    svc: ImageLibraryService = Depends(get_image_library_service),
):
    tid = tenant_id_var.get("")
    await svc.delete(image_id, tid)
    return Result.ok(message="Image deleted", trace_id=trace_id_var.get(""))


@router.post("/product-issues", response_model=None, summary="创建产品问题记录")
async def create_product_issue(
    req: ProductIssueCreateRequest,
    svc: ProductIssueService = Depends(get_product_issue_service),
):
    """创建产品质量问题记录，支持质量/包装/标签/安全/合规5类"""
    tid = tenant_id_var.get("")
    data = await svc.create(tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/product-issues", response_model=None, summary="查询产品问题列表")
async def list_product_issues(
    status: str = Query(default="", description="状态过滤: open/in_progress/resolved/closed"),
    severity: str = Query(default="", description="严重程度过滤: critical/high/medium/low"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: ProductIssueService = Depends(get_product_issue_service),
):
    tid = tenant_id_var.get("")
    items, total = await svc.list(tid, status, severity, page, page_size)
    return Result.paginate(items=items, total=total, page=page, page_size=page_size, trace_id=trace_id_var.get(""))


@router.get("/product-issues/{issue_id}", response_model=None, summary="查询产品问题详情")
async def get_product_issue(
    issue_id: str,
    svc: ProductIssueService = Depends(get_product_issue_service),
):
    tid = tenant_id_var.get("")
    data = await svc.get(issue_id, tid)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.put("/product-issues/{issue_id}", response_model=None, summary="更新产品问题记录")
async def update_product_issue(
    issue_id: str,
    req: ProductIssueUpdateRequest,
    svc: ProductIssueService = Depends(get_product_issue_service),
):
    """更新产品问题记录: 状态流转、分配处理人、填写解决方案"""
    tid = tenant_id_var.get("")
    data = await svc.update(issue_id, tid, req)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.get("/skus/{sku_id}/issues", response_model=None, summary="查询SKU关联问题记录")
async def list_issues_by_sku(
    sku_id: str,
    svc: ProductIssueService = Depends(get_product_issue_service),
):
    tid = tenant_id_var.get("")
    data = await svc.list_by_sku(sku_id, tid)
    return Result.ok(data=data, trace_id=trace_id_var.get(""))


@router.post("/skus/search", response_model=None, summary="搜索SKU")
async def search_skus(
    req: SKUSearchRequest,
    svc: PDMQueryService = Depends(get_pdm_query_service),
):
    """多维度搜索SKU: 关键词/SPU/状态"""
    items, total = await svc.search_skus(
        tenant_id_var.get(""), keyword=req.keyword, spu_id=req.spu_id,
        status=req.status, page=req.page, page_size=req.page_size,
    )
    data = [{"id": s.id, "sku_code": s.sku_code, "spu_id": s.spu_id,
             "name": s.name, "status": s.status, "cost_price": s.cost_price} for s in items]
    return Result.paginate(items=data, total=total, page=req.page, page_size=req.page_size, trace_id=trace_id_var.get(""))
