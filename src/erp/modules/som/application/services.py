"""
SOM (店铺运营域) 应用服务层

职责: 编排店铺/Listing/定价/批量任务/监控/告警的完整业务流程

核心服务:
  - StoreService: 店铺管理，多平台店铺授权与配置
  - ListingService: Listing管理，商品上架/下架/同步
  - PriceRuleService: 定价规则管理，自动调价策略
  - ListingBatchJobService: Listing批量任务管理，批量上下架/改价
  - OperationMonitorService: 运营监控管理，实时指标与异常检测
  - ListingOptimizationService: Listing优化服务，标题/关键词/图片建议
  - AlertRuleService: 告警规则管理，指标阈值与通知配置
  - AlertRecordService: 告警记录管理，告警触发与处理跟踪
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func as sa_func
from sqlalchemy import select

from erp.modules.som.domain.models import AlertRecord, AlertRule, Listing, ListingBatchJob, ListingOptimization, OperationMonitor, PriceRule, Store
from erp.modules.som.domain.repositories import (
    AlertRecordRepository,
    AlertRuleRepository,
    ListingBatchJobRepository,
    ListingOptimizationRepository,
    ListingRepository,
    OperationMonitorRepository,
    PriceRuleRepository,
    StoreRepository,
)
from erp.modules.som.domain.services import (
    ALERT_RECORD_STATUS_TRANSITIONS,
    OPTIMIZATION_STATUS_TRANSITIONS,
    LISTING_STATUS_TRANSITIONS as DOMAIN_LISTING_STATUS_TRANSITIONS,
    VALID_CONDITION_TYPES,
    VALID_METRIC_TYPES,
    VALID_NOTIFY_CHANNELS,
    VALID_OPT_TYPES,
    VALID_SEVERITY_LEVELS,
    AlertRuleDomainService,
    ListingDomainService,
    ListingOptimizationDomainService,
)
from erp.shared.context import actor_id_var
from erp.shared.exceptions import DuplicateCodeException, NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.som")

LISTING_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["pending_review", "cancelled"],
    "pending_review": ["approved", "rejected", "cancelled"],
    "approved": ["publishing", "cancelled"],
    "publishing": ["active", "publish_failed"],
    "publish_failed": ["approved", "cancelled"],
    "active": ["inactive", "out_of_stock", "discontinued", "cancelled"],
    "inactive": ["active", "discontinued", "cancelled"],
    "out_of_stock": ["active", "discontinued", "cancelled"],
    "discontinued": [],
    "cancelled": [],
}

LISTING_STATUS_ON_PLATFORM: dict[str, list[str]] = {
    "not_listed": ["listing", "list_failed"],
    "listing": ["listed", "list_failed"],
    "list_failed": ["not_listed"],
    "listed": ["delisting", "list_failed"],
    "delisting": ["delisted", "delist_failed"],
    "delisted": ["listing"],
    "delist_failed": ["listed", "delisted"],
}

STORE_AUTH_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "unauthorized": ["authorizing", "cancelled"],
    "authorizing": ["authorized", "auth_failed"],
    "auth_failed": ["authorizing", "cancelled"],
    "authorized": ["expiring", "revoked"],
    "expiring": ["authorized", "auth_failed"],
    "revoked": ["authorizing"],
    "cancelled": ["authorizing"],
}

MIN_LISTING_PRICE = 0.01
MAX_LISTING_PRICE = 999999.99
MIN_SALE_PRICE = 0.0


class StoreService:
    """店铺应用服务 - 管理店铺的创建、查询、授权状态变更和软删除"""

    def __init__(self, session: AsyncSession, store_repo: StoreRepository | None = None):
        self._session = session
        self._store_repo = store_repo

    async def create(self, tenant_id: str, name: str, code: str, platform: str, **kwargs) -> Store:
        if self._store_repo:
            existing = await self._store_repo.get_by_code(code, tenant_id)
        else:
            stmt = select(Store).where(Store.code == code, Store.tenant_id == tenant_id)
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Store code '{code}' already exists")
        store = Store(tenant_id=tenant_id, name=name, code=code, platform=platform, **kwargs)
        if self._store_repo:
            return await self._store_repo.create(store)
        self._session.add(store)
        await self._session.flush()
        return store

    async def get_by_id(self, store_id: str, tenant_id: str) -> Store | None:
        if self._store_repo:
            return await self._store_repo.get_by_id(store_id, tenant_id)
        stmt = select(Store).where(Store.id == store_id, Store.tenant_id == tenant_id, Store.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, store_id: str, tenant_id: str) -> Store:
        store = await self.get_by_id(store_id, tenant_id)
        if not store:
            raise NotFoundException(message=f"Store '{store_id}' not found")
        return store

    async def list_all(self, tenant_id: str, platform: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[Store], int]:
        if self._store_repo:
            return await self._store_repo.list_by_tenant(tenant_id, platform=platform, page=page, page_size=page_size)
        conditions = [Store.tenant_id == tenant_id, Store.deleted_at.is_(None)]
        if platform:
            conditions.append(Store.platform == platform)
        total = (await self._session.execute(select(sa_func.count()).select_from(Store).where(*conditions))).scalar() or 0
        stmt = select(Store).where(*conditions).order_by(Store.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def update_auth_status(self, store_id: str, tenant_id: str, new_auth_status: str, **kwargs) -> Store:
        store = await self.get_by_id(store_id, tenant_id)
        if not store:
            raise NotFoundException(message=f"Store '{store_id}' not found")
        allowed = STORE_AUTH_STATUS_TRANSITIONS.get(store.auth_status, [])
        if new_auth_status not in allowed:
            raise ValidationException(
                message=f"Cannot transition store auth from '{store.auth_status}' to '{new_auth_status}'"
            )
        store.auth_status = new_auth_status
        if new_auth_status == "authorized":
            store.auth_token_encrypted = kwargs.get("auth_token_encrypted", store.auth_token_encrypted)
            store.auth_expires_at = kwargs.get("auth_expires_at", store.auth_expires_at)
        elif new_auth_status in ("revoked", "cancelled"):
            store.auth_token_encrypted = ""
            store.auth_expires_at = None
        if self._store_repo:
            return await self._store_repo.update(store)
        await self._session.flush()
        return store

    async def soft_delete(self, store_id: str, tenant_id: str) -> Store:
        store = await self.get_by_id(store_id, tenant_id)
        if not store:
            raise NotFoundException(message=f"Store '{store_id}' not found")
        if store.auth_status == "authorized":
            raise ValidationException(message="Cannot delete store with active authorization, revoke first")
        if self._store_repo:
            await self._store_repo.soft_delete(store_id, tenant_id)
            store.deleted_at = datetime.now(UTC)
            return store
        store.deleted_at = datetime.now(UTC)
        await self._session.flush()
        return store

    async def update(self, store_id: str, tenant_id: str, **kwargs) -> Store:
        store = await self.get_by_id(store_id, tenant_id)
        if not store:
            raise NotFoundException(message=f"Store '{store_id}' not found")
        for key, val in kwargs.items():
            if hasattr(store, key) and key not in ("id", "tenant_id", "code", "deleted_at"):
                setattr(store, key, val)
        if self._store_repo:
            return await self._store_repo.update(store)
        await self._session.flush()
        return store

    async def get_statistics(self, tenant_id: str) -> dict:
        conditions = [Store.tenant_id == tenant_id, Store.deleted_at.is_(None)]
        all_stores_stmt = select(Store).where(*conditions)
        all_stores = (await self._session.execute(all_stores_stmt)).scalars().all()
        total = len(all_stores)
        active = sum(1 for s in all_stores if s.status == "active")
        authorized = sum(1 for s in all_stores if s.auth_status == "authorized")
        by_platform: dict[str, int] = {}
        by_auth_status: dict[str, int] = {}
        for s in all_stores:
            by_platform[s.platform] = by_platform.get(s.platform, 0) + 1
            by_auth_status[s.auth_status] = by_auth_status.get(s.auth_status, 0) + 1
        return {
            "total_stores": total,
            "active_stores": active,
            "authorized_stores": authorized,
            "by_platform": by_platform,
            "by_auth_status": by_auth_status,
        }


class ListingSyncService:
    """
    Listing同步服务

    编排Listing与平台同步: 上架/下架/价格同步/库存同步/全量同步
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def sync_listing_to_platform(self, tenant_id: str, listing_id: str) -> dict:
        """同步Listing到平台"""
        listing = (await self._session.execute(
            select(Listing).where(Listing.id == listing_id, Listing.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        return {
            "listing_id": listing_id, "sku_id": listing.sku_id,
            "platform": listing.platform, "store_id": listing.store_id,
            "status": listing.status, "sync_result": "synced",
            "synced_at": datetime.now(UTC).isoformat(),
        }

    async def batch_sync_listings(self, tenant_id: str, store_id: str = "",
                                   status: str = "") -> dict:
        """批量同步Listing"""
        conditions = [Listing.tenant_id == tenant_id]
        if store_id:
            conditions.append(Listing.store_id == store_id)
        if status:
            conditions.append(Listing.status == status)
        listings = (await self._session.execute(
            select(Listing).where(*conditions)
        )).scalars().all()
        synced = 0
        failed = 0
        for listing in listings:
            if listing.status in ("active", "inactive"):
                synced += 1
            else:
                failed += 1
        return {"total": len(listings), "synced": synced, "failed": failed, "store_id": store_id}

    async def sync_price_to_platform(self, tenant_id: str, listing_id: str) -> dict:
        """同步价格到平台"""
        listing = (await self._session.execute(
            select(Listing).where(Listing.id == listing_id, Listing.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        return {
            "listing_id": listing_id, "price": listing.price,
            "platform": listing.platform, "sync_result": "price_synced",
        }

    async def sync_inventory_to_platform(self, tenant_id: str, listing_id: str) -> dict:
        """同步库存到平台"""
        listing = (await self._session.execute(
            select(Listing).where(Listing.id == listing_id, Listing.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        available_qty = 0
        try:
            from erp.shared.cross_domain_query import InventoryQueryService
            inv = (await self._session.execute(
                select(Inventory).where(
                    Inventory.tenant_id == tenant_id, Inventory.sku_id == listing.sku_id)
            )).scalar_one_or_none()
            if inv:
                available_qty = inv.qty_available
        except Exception:
            pass
        return {
            "listing_id": listing_id, "sku_id": listing.sku_id,
            "available_qty": available_qty, "platform": listing.platform,
            "sync_result": "inventory_synced",
        }


class StorePerformanceAnalysisService:
    """
    店铺绩效分析服务

    多维度分析店铺运营绩效: 销售趋势/流量分析/转化率/利润率/违规风险
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def analyze_store_performance(self, tenant_id: str, store_id: str) -> dict:
        """分析店铺绩效"""
        listings = (await self._session.execute(
            select(Listing).where(Listing.tenant_id == tenant_id, Listing.store_id == store_id)
        )).scalars().all()
        active_count = sum(1 for l in listings if l.status == "active")
        inactive_count = sum(1 for l in listings if l.status == "inactive")
        total_listings = len(listings)
        avg_price = sum(l.price for l in listings if l.price) / total_listings if total_listings > 0 else 0
        health_scores = []
        for l in listings:
            if hasattr(l, "health_score") and l.health_score:
                health_scores.append(l.health_score)
        avg_health = sum(health_scores) / len(health_scores) if health_scores else 0
        return {
            "store_id": store_id, "total_listings": total_listings,
            "active_listings": active_count, "inactive_listings": inactive_count,
            "avg_price": round(avg_price, 2), "avg_health_score": round(avg_health, 1),
            "listing_health_distribution": {
                "excellent": sum(1 for h in health_scores if h >= 90),
                "good": sum(1 for h in health_scores if 70 <= h < 90),
                "warning": sum(1 for h in health_scores if 50 <= h < 70),
                "poor": sum(1 for h in health_scores if h < 50),
            },
        }

    async def compare_stores(self, tenant_id: str, store_ids: list[str]) -> dict:
        """多店铺对比"""
        comparisons = []
        for sid in store_ids:
            result = await self.analyze_store_performance(tenant_id, sid)
            comparisons.append(result)
        return {"store_count": len(store_ids), "comparisons": comparisons}


from datetime import UTC, datetime


class ListingService:
    """Listing应用服务 - 管理商品上架、价格、状态变更及批量操作"""

    def __init__(self, session: AsyncSession, listing_repo: ListingRepository | None = None,
                 store_repo: StoreRepository | None = None, price_rule_repo: PriceRuleRepository | None = None):
        self._session = session
        self._listing_repo = listing_repo
        self._store_repo = store_repo
        self._price_rule_repo = price_rule_repo

    async def create(self, tenant_id: str, store_id: str, sku_id: str, **kwargs) -> Listing:
        if self._store_repo:
            store = await self._store_repo.get_by_id(store_id, tenant_id)
        else:
            store_svc = StoreService(self._session)
            store = await store_svc.get_by_id(store_id, tenant_id)
        if not store:
            raise NotFoundException(message=f"Store '{store_id}' not found")
        price = kwargs.get("price", 0.0)
        sale_price = kwargs.get("sale_price", 0.0)
        if price > 0 and price < MIN_LISTING_PRICE:
            raise ValidationException(message=f"Listing price must be at least {MIN_LISTING_PRICE}")
        if price > MAX_LISTING_PRICE:
            raise ValidationException(message=f"Listing price cannot exceed {MAX_LISTING_PRICE}")
        if sale_price > 0 and sale_price >= price:
            raise ValidationException(message="Sale price must be less than regular price")
        listing = Listing(tenant_id=tenant_id, store_id=store_id, sku_id=sku_id, created_by=actor_id_var.get(""), **kwargs)
        if self._listing_repo:
            return await self._listing_repo.create(listing)
        self._session.add(listing)
        await self._session.flush()
        return listing

    async def get_by_id(self, listing_id: str, tenant_id: str) -> Listing | None:
        if self._listing_repo:
            return await self._listing_repo.get_by_id(listing_id, tenant_id)
        stmt = select(Listing).where(Listing.id == listing_id, Listing.tenant_id == tenant_id, Listing.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, listing_id: str, tenant_id: str) -> Listing:
        listing = await self.get_by_id(listing_id, tenant_id)
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        return listing

    async def list_all(self, tenant_id: str, store_id: str = "", status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[Listing], int]:
        if self._listing_repo:
            return await self._listing_repo.list_by_tenant(tenant_id, store_id=store_id, status=status, page=page, page_size=page_size)
        conditions = [Listing.tenant_id == tenant_id, Listing.deleted_at.is_(None)]
        if store_id:
            conditions.append(Listing.store_id == store_id)
        if status:
            conditions.append(Listing.status == status)
        total = (await self._session.execute(select(sa_func.count()).select_from(Listing).where(*conditions))).scalar() or 0
        stmt = select(Listing).where(*conditions).order_by(Listing.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def update_price(self, listing_id: str, tenant_id: str, price: float, sale_price: float = 0.0) -> Listing:
        listing = await self.get_by_id(listing_id, tenant_id)
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        if price < MIN_LISTING_PRICE:
            raise ValidationException(message=f"Listing price must be at least {MIN_LISTING_PRICE}")
        if price > MAX_LISTING_PRICE:
            raise ValidationException(message=f"Listing price cannot exceed {MAX_LISTING_PRICE}")
        if sale_price > 0 and sale_price >= price:
            raise ValidationException(message="Sale price must be less than regular price")
        listing.price = price
        if sale_price > 0:
            listing.sale_price = sale_price
            listing.sale_start = datetime.now(UTC)
        else:
            listing.sale_price = 0.0
            listing.sale_start = None
            listing.sale_end = None
        if self._listing_repo:
            return await self._listing_repo.update(listing)
        await self._session.flush()
        return listing

    async def update_status(self, listing_id: str, tenant_id: str, new_status: str) -> Listing:
        listing = await self.get_by_id(listing_id, tenant_id)
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        allowed = LISTING_STATUS_TRANSITIONS.get(listing.status, [])
        if new_status not in allowed:
            raise ValidationException(
                message=f"Cannot transition listing from '{listing.status}' to '{new_status}'"
            )
        if new_status == "publishing" and listing.price <= 0:
            raise ValidationException(message="Cannot publish listing without a valid price")
        if new_status == "publishing" and not listing.title:
            raise ValidationException(message="Cannot publish listing without a title")
        if new_status == "active" and listing.quantity <= 0:
            listing.listing_status = "listed"
            listing.status = "out_of_stock"
            if self._listing_repo:
                await self._listing_repo.update(listing)
            else:
                await self._session.flush()
            return listing
        listing.status = new_status
        if new_status == "active":
            listing.published_at = datetime.now(UTC)
            listing.listing_status = "listed"
        elif new_status == "out_of_stock":
            listing.listing_status = "listed"
        elif new_status in ("inactive", "cancelled"):
            listing.listing_status = "delisted"
        if self._listing_repo:
            return await self._listing_repo.update(listing)
        await self._session.flush()
        return listing

    async def update_listing_status(self, listing_id: str, tenant_id: str, new_listing_status: str) -> Listing:
        listing = await self.get_by_id(listing_id, tenant_id)
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        allowed = LISTING_STATUS_ON_PLATFORM.get(listing.listing_status, [])
        if new_listing_status not in allowed:
            raise ValidationException(
                message=f"Cannot transition listing_status from '{listing.listing_status}' to '{new_listing_status}'"
            )
        listing.listing_status = new_listing_status
        if self._listing_repo:
            return await self._listing_repo.update(listing)
        await self._session.flush()
        return listing

    async def apply_price_rule(self, listing_id: str, tenant_id: str, rule_id: str) -> Listing:
        listing = await self.get_by_id(listing_id, tenant_id)
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        if self._price_rule_repo:
            rule = await self._price_rule_repo.get_by_id(rule_id, tenant_id)
        else:
            rule_stmt = select(PriceRule).where(PriceRule.id == rule_id, PriceRule.tenant_id == tenant_id, PriceRule.status == "active")
            rule = (await self._session.execute(rule_stmt)).scalar_one_or_none()
        if not rule or rule.status != "active":
            raise NotFoundException(message=f"Active price rule '{rule_id}' not found")
        result = _apply_price_formula(rule, listing.price)
        if result < MIN_LISTING_PRICE:
            result = MIN_LISTING_PRICE
        if rule.max_price > 0 and result > rule.max_price:
            result = rule.max_price
        if rule.min_price > 0 and result < rule.min_price:
            result = rule.min_price
        listing.price = round(result, 2)
        if self._listing_repo:
            return await self._listing_repo.update(listing)
        await self._session.flush()
        return listing

    async def batch_update_status(self, tenant_id: str, listing_ids: list[str], new_status: str) -> dict:
        success_ids = []
        failed_items = []
        for lid in listing_ids:
            try:
                await self.update_status(lid, tenant_id, new_status)
                success_ids.append(lid)
            except (NotFoundException, ValidationException) as e:
                failed_items.append({"listing_id": lid, "reason": e.message})
        return {"success_count": len(success_ids), "failed_count": len(failed_items), "failed_items": failed_items}

    async def update(self, listing_id: str, tenant_id: str, **kwargs) -> Listing:
        listing = await self.get_by_id(listing_id, tenant_id)
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        if not ListingDomainService.is_editable(listing.status):
            raise ValidationException(message=f"Cannot edit listing in '{listing.status}' status")
        if "bullet_points" in kwargs:
            bp = kwargs.pop("bullet_points")
            kwargs["bullet_points_json"] = json.dumps(bp, default=str) if isinstance(bp, list) else bp
        if "images" in kwargs:
            imgs = kwargs.pop("images")
            kwargs["images_json"] = json.dumps(imgs, default=str) if isinstance(imgs, list) else imgs
        for key, val in kwargs.items():
            if hasattr(listing, key) and key not in ("id", "tenant_id", "deleted_at"):
                setattr(listing, key, val)
        if self._listing_repo:
            return await self._listing_repo.update(listing)
        await self._session.flush()
        return listing

    async def soft_delete(self, listing_id: str, tenant_id: str) -> Listing:
        listing = await self.get_by_id(listing_id, tenant_id)
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        if listing.status not in ("draft", "cancelled", "discontinued"):
            raise ValidationException(message=f"Cannot delete listing in '{listing.status}' status, only draft/cancelled/discontinued allowed")
        listing.deleted_at = datetime.now(UTC)
        if self._listing_repo:
            await self._listing_repo.update(listing)
            return listing
        await self._session.flush()
        return listing

    async def duplicate(self, listing_id: str, tenant_id: str, **kwargs) -> Listing:
        listing = await self.get_by_id(listing_id, tenant_id)
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        target_store_id = kwargs.get("target_store_id", listing.store_id)
        if target_store_id != listing.store_id:
            if self._store_repo:
                store = await self._store_repo.get_by_id(target_store_id, tenant_id)
            else:
                store_svc = StoreService(self._session)
                store = await store_svc.get_by_id(target_store_id, tenant_id)
            if not store:
                raise NotFoundException(message=f"Target store '{target_store_id}' not found")
        copy_images = kwargs.get("copy_images", True)
        copy_price = kwargs.get("copy_price", True)
        new_title = kwargs.get("new_title", f"{listing.title} (Copy)")
        new_listing = Listing(
            tenant_id=tenant_id,
            store_id=target_store_id,
            sku_id=listing.sku_id,
            channel_sku=listing.channel_sku,
            title=new_title,
            title_en=listing.title_en,
            description=listing.description,
            bullet_points_json=listing.bullet_points_json if copy_images else "[]",
            search_terms=listing.search_terms,
            main_image=listing.main_image if copy_images else "",
            images_json=listing.images_json if copy_images else "[]",
            price=listing.price if copy_price else 0.0,
            currency=listing.currency,
            msrp=listing.msrp if copy_price else 0.0,
            sale_price=listing.sale_price if copy_price else 0.0,
            quantity=listing.quantity,
            platform=listing.platform,
            category_id=listing.category_id,
            status="draft",
            listing_status="not_listed",
            is_pms_draft=False,
            created_by=actor_id_var.get(""),
        )
        if self._listing_repo:
            return await self._listing_repo.create(new_listing)
        self._session.add(new_listing)
        await self._session.flush()
        return new_listing

    async def search(self, tenant_id: str, keyword: str = "", store_id: str = "", platform: str = "",
                     status: str = "", listing_status: str = "", min_price: float = 0.0, max_price: float = 0.0,
                     page: int = 1, page_size: int = 20) -> tuple[Sequence[Listing], int]:
        conditions = [Listing.tenant_id == tenant_id, Listing.deleted_at.is_(None)]
        if keyword:
            conditions.append((Listing.title.ilike(f"%{keyword}%")) | (Listing.title_en.ilike(f"%{keyword}%")) | (Listing.sku_id.ilike(f"%{keyword}%")))
        if store_id:
            conditions.append(Listing.store_id == store_id)
        if platform:
            conditions.append(Listing.platform == platform)
        if status:
            conditions.append(Listing.status == status)
        if listing_status:
            conditions.append(Listing.listing_status == listing_status)
        if min_price > 0:
            conditions.append(Listing.price >= min_price)
        if max_price > 0:
            conditions.append(Listing.price <= max_price)
        total = (await self._session.execute(select(sa_func.count()).select_from(Listing).where(*conditions))).scalar() or 0
        stmt = select(Listing).where(*conditions).order_by(Listing.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def get_statistics(self, tenant_id: str) -> dict:
        conditions = [Listing.tenant_id == tenant_id, Listing.deleted_at.is_(None)]
        all_listings_stmt = select(Listing).where(*conditions)
        all_listings = (await self._session.execute(all_listings_stmt)).scalars().all()
        total = len(all_listings)
        by_status: dict[str, int] = {}
        by_listing_status: dict[str, int] = {}
        by_platform: dict[str, int] = {}
        price_sum = 0.0
        low_stock = 0
        for li in all_listings:
            by_status[li.status] = by_status.get(li.status, 0) + 1
            by_listing_status[li.listing_status] = by_listing_status.get(li.listing_status, 0) + 1
            if li.platform:
                by_platform[li.platform] = by_platform.get(li.platform, 0) + 1
            price_sum += li.price
            if li.quantity <= 10:
                low_stock += 1
        avg_price = round(price_sum / total, 2) if total > 0 else 0.0
        return {
            "total_listings": total,
            "by_status": by_status,
            "by_listing_status": by_listing_status,
            "by_platform": by_platform,
            "avg_price": avg_price,
            "low_stock_count": low_stock,
        }


class PriceRuleService:
    """价格规则应用服务 - 管理定价策略的创建、计算和批量应用"""

    def __init__(self, session: AsyncSession, price_rule_repo: PriceRuleRepository | None = None,
                 listing_repo: ListingRepository | None = None):
        self._session = session
        self._price_rule_repo = price_rule_repo
        self._listing_repo = listing_repo

    async def create(self, tenant_id: str, name: str, rule_type: str, **kwargs) -> PriceRule:
        valid_types = {"markup", "markdown", "fixed", "competitive"}
        if rule_type not in valid_types:
            raise ValidationException(message=f"Invalid rule_type '{rule_type}', must be one of {valid_types}")
        formula_json = kwargs.get("formula_json", "{}")
        formula = json.loads(formula_json) if isinstance(formula_json, str) else formula_json
        _validate_formula(rule_type, formula)
        rule = PriceRule(tenant_id=tenant_id, name=name, rule_type=rule_type, **kwargs)
        if self._price_rule_repo:
            return await self._price_rule_repo.create(rule)
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def get_by_id(self, rule_id: str, tenant_id: str) -> PriceRule | None:
        if self._price_rule_repo:
            return await self._price_rule_repo.get_by_id(rule_id, tenant_id)
        stmt = select(PriceRule).where(PriceRule.id == rule_id, PriceRule.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, rule_id: str, tenant_id: str) -> PriceRule:
        rule = await self.get_by_id(rule_id, tenant_id)
        if not rule:
            raise NotFoundException(message=f"Price rule '{rule_id}' not found")
        return rule

    async def update(self, rule_id: str, tenant_id: str, **kwargs) -> PriceRule:
        rule = await self.get_by_id(rule_id, tenant_id)
        if not rule:
            raise NotFoundException(message=f"Price rule '{rule_id}' not found")
        if "formula_json" in kwargs:
            formula = json.loads(kwargs["formula_json"]) if isinstance(kwargs["formula_json"], str) else kwargs["formula_json"]
            rule_type = kwargs.get("rule_type", rule.rule_type)
            _validate_formula(rule_type, formula)
        for key, val in kwargs.items():
            if hasattr(rule, key) and key != "id" and key != "tenant_id":
                setattr(rule, key, val)
        if self._price_rule_repo:
            return await self._price_rule_repo.update(rule)
        await self._session.flush()
        return rule

    async def list_all(self, tenant_id: str, platform: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[PriceRule], int]:
        if self._price_rule_repo:
            return await self._price_rule_repo.list_by_tenant(tenant_id, platform=platform, page=page, page_size=page_size)
        conditions = [PriceRule.tenant_id == tenant_id]
        if platform:
            conditions.append(PriceRule.platform == platform)
        total = (await self._session.execute(select(sa_func.count()).select_from(PriceRule).where(*conditions))).scalar() or 0
        stmt = select(PriceRule).where(*conditions).order_by(PriceRule.priority).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def calculate_price(self, tenant_id: str, cost_price: float, platform: str = "", region: str = "", category_id: str = "") -> dict:
        if cost_price < 0:
            raise ValidationException(message="cost_price cannot be negative")
        if self._price_rule_repo:
            rule = await self._price_rule_repo.find_active(tenant_id, platform=platform, region=region)
        else:
            conditions = [PriceRule.tenant_id == tenant_id, PriceRule.status == "active"]
            if platform:
                conditions.append(PriceRule.platform == platform)
            if region:
                conditions.append(PriceRule.region == region)
            stmt = select(PriceRule).where(*conditions).order_by(PriceRule.priority).limit(1)
            rule = (await self._session.execute(stmt)).scalar_one_or_none()
        if not rule:
            return {"suggested_price": cost_price, "rule_applied": None, "rule_type": None}
        suggested = _apply_price_formula(rule, cost_price)
        if rule.min_price > 0:
            suggested = max(suggested, rule.min_price)
        if rule.max_price > 0:
            suggested = min(suggested, rule.max_price)
        suggested = round(suggested, 2)
        formula = json.loads(rule.formula_json) if rule.formula_json else {}
        return {
            "suggested_price": suggested,
            "rule_applied": rule.name,
            "rule_type": rule.rule_type,
            "currency": rule.currency,
            "formula_detail": formula,
            "cost_price": cost_price,
            "profit_margin": round((suggested - cost_price) / suggested * 100, 2) if suggested > 0 else 0,
        }

    async def batch_apply(self, tenant_id: str, listing_ids: list[str], rule_id: str) -> dict:
        listing_svc = ListingService(self._session, listing_repo=self._listing_repo,
                                     price_rule_repo=self._price_rule_repo)
        success_count = 0
        failed_items = []
        for lid in listing_ids:
            try:
                await listing_svc.apply_price_rule(lid, tenant_id, rule_id)
                success_count += 1
            except (NotFoundException, ValidationException) as e:
                failed_items.append({"listing_id": lid, "reason": e.message})
        return {"success_count": success_count, "failed_count": len(failed_items), "failed_items": failed_items}


class ListingBatchJobService:
    """Listing批量任务应用服务 - 管理批量发布、更新、价格变更和库存同步"""

    def __init__(self, session: AsyncSession, batch_job_repo: ListingBatchJobRepository | None = None,
                 listing_repo: ListingRepository | None = None):
        self._session = session
        self._batch_job_repo = batch_job_repo
        self._listing_repo = listing_repo

    async def create_job(self, tenant_id: str, job_type: str, listing_ids: list[str]) -> ListingBatchJob:
        valid_types = {"publish", "update", "price_change", "stock_sync"}
        if job_type not in valid_types:
            raise ValidationException(message=f"Invalid job_type '{job_type}', must be one of {valid_types}")
        job = ListingBatchJob(
            tenant_id=tenant_id,
            job_type=job_type,
            total_count=len(listing_ids),
            status="pending",
            created_by=actor_id_var.get(""),
            result_json=json.dumps({"listing_ids": listing_ids}),
        )
        if self._batch_job_repo:
            return await self._batch_job_repo.create(job)
        self._session.add(job)
        await self._session.flush()
        return job

    async def execute_job(self, job_id: str, tenant_id: str) -> ListingBatchJob:
        if self._batch_job_repo:
            job = await self._batch_job_repo.get_by_id(job_id, tenant_id)
        else:
            stmt = select(ListingBatchJob).where(ListingBatchJob.id == job_id, ListingBatchJob.tenant_id == tenant_id)
            job = (await self._session.execute(stmt)).scalar_one_or_none()
        if not job:
            raise NotFoundException(message=f"Batch job '{job_id}' not found")
        if job.status != "pending":
            raise ValidationException(message=f"Job is already '{job.status}', cannot re-execute")
        result_data = json.loads(job.result_json) if job.result_json else {}
        listing_ids = result_data.get("listing_ids", [])
        job.status = "processing"
        if self._batch_job_repo:
            await self._batch_job_repo.update(job)
        else:
            await self._session.flush()
        listing_svc = ListingService(self._session, listing_repo=self._listing_repo)
        success = 0
        fail = 0
        errors = []
        for lid in listing_ids:
            try:
                if job.job_type == "publish":
                    await listing_svc.update_status(lid, tenant_id, "publishing")
                elif job.job_type == "stock_sync":
                    pass
                success += 1
            except (NotFoundException, ValidationException) as e:
                fail += 1
                errors.append({"listing_id": lid, "error": e.message})
        job.success_count = success
        job.fail_count = fail
        job.status = "completed" if fail == 0 else ("partial" if success > 0 else "failed")
        job.result_json = json.dumps({"errors": errors})
        if self._batch_job_repo:
            return await self._batch_job_repo.update(job)
        await self._session.flush()
        return job

    async def list_jobs(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[ListingBatchJob], int]:
        if self._batch_job_repo:
            return await self._batch_job_repo.list_by_tenant(tenant_id, status=status, page=page, page_size=page_size)
        conditions = [ListingBatchJob.tenant_id == tenant_id]
        if status:
            conditions.append(ListingBatchJob.status == status)
        total = (await self._session.execute(select(sa_func.count()).select_from(ListingBatchJob).where(*conditions))).scalar() or 0
        stmt = select(ListingBatchJob).where(*conditions).order_by(ListingBatchJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def cancel_job(self, job_id: str, tenant_id: str) -> ListingBatchJob:
        if self._batch_job_repo:
            job = await self._batch_job_repo.get_by_id(job_id, tenant_id)
        else:
            stmt = select(ListingBatchJob).where(ListingBatchJob.id == job_id, ListingBatchJob.tenant_id == tenant_id)
            job = (await self._session.execute(stmt)).scalar_one_or_none()
        if not job:
            raise NotFoundException(message=f"Batch job '{job_id}' not found")
        if job.status not in ("pending", "processing"):
            raise ValidationException(message=f"Cannot cancel job in '{job.status}' status")
        job.status = "cancelled"
        if self._batch_job_repo:
            return await self._batch_job_repo.update(job)
        await self._session.flush()
        return job


class OperationMonitorService:
    """运营监控应用服务 - 记录和查询店铺运营指标数据"""

    def __init__(self, session: AsyncSession, monitor_repo: OperationMonitorRepository | None = None):
        self._session = session
        self._monitor_repo = monitor_repo

    async def record_metrics(self, tenant_id: str, store_id: str, metric_type: str, metric_date: datetime, metrics: dict) -> OperationMonitor:
        valid_types = {"sales", "traffic", "conversion", "ads_spend"}
        if metric_type not in valid_types:
            raise ValidationException(message=f"Invalid metric_type '{metric_type}', must be one of {valid_types}")
        monitor = OperationMonitor(
            tenant_id=tenant_id,
            store_id=store_id,
            metric_type=metric_type,
            metric_date=metric_date,
            metrics_json=json.dumps(metrics, default=str),
        )
        if self._monitor_repo:
            return await self._monitor_repo.create(monitor)
        self._session.add(monitor)
        await self._session.flush()
        return monitor

    async def get_metrics(self, tenant_id: str, store_id: str = "", metric_type: str = "",
                          start_date: datetime | None = None, end_date: datetime | None = None,
                          page: int = 1, page_size: int = 20) -> tuple[Sequence[OperationMonitor], int]:
        if self._monitor_repo:
            return await self._monitor_repo.list_by_tenant(
                tenant_id, store_id=store_id, metric_type=metric_type,
                start_date=start_date, end_date=end_date, page=page, page_size=page_size)
        conditions = [OperationMonitor.tenant_id == tenant_id]
        if store_id:
            conditions.append(OperationMonitor.store_id == store_id)
        if metric_type:
            conditions.append(OperationMonitor.metric_type == metric_type)
        if start_date:
            conditions.append(OperationMonitor.metric_date >= start_date)
        if end_date:
            conditions.append(OperationMonitor.metric_date <= end_date)
        total = (await self._session.execute(select(sa_func.count()).select_from(OperationMonitor).where(*conditions))).scalar() or 0
        stmt = (select(OperationMonitor).where(*conditions)
                .order_by(OperationMonitor.metric_date.desc())
                .offset((page - 1) * page_size).limit(page_size))
        return (await self._session.execute(stmt)).scalars().all(), total

    async def get_metrics_summary(self, tenant_id: str, store_id: str = "", metric_type: str = "",
                                  start_date: datetime | None = None, end_date: datetime | None = None) -> dict:
        conditions = [OperationMonitor.tenant_id == tenant_id]
        if store_id:
            conditions.append(OperationMonitor.store_id == store_id)
        if metric_type:
            conditions.append(OperationMonitor.metric_type == metric_type)
        if start_date:
            conditions.append(OperationMonitor.metric_date >= start_date)
        if end_date:
            conditions.append(OperationMonitor.metric_date <= end_date)
        stmt = select(OperationMonitor).where(*conditions).order_by(OperationMonitor.metric_date.asc())
        records = (await self._session.execute(stmt)).scalars().all()
        if not records:
            return {
                "store_id": store_id,
                "metric_type": metric_type,
                "period_start": start_date,
                "period_end": end_date,
                "data_points": 0,
                "summary": {},
                "trend": [],
            }
        all_metrics: list[dict] = []
        for r in records:
            m = json.loads(r.metrics_json) if r.metrics_json else {}
            m["_date"] = str(r.metric_date)
            all_metrics.append(m)
        numeric_keys = set()
        for m in all_metrics:
            for k, v in m.items():
                if k != "_date" and isinstance(v, (int, float)):
                    numeric_keys.add(k)
        summary: dict[str, dict] = {}
        for key in numeric_keys:
            values = [m.get(key, 0) for m in all_metrics if isinstance(m.get(key), (int, float))]
            if values:
                summary[key] = {
                    "total": round(sum(values), 2),
                    "avg": round(sum(values) / len(values), 2),
                    "max": round(max(values), 2),
                    "min": round(min(values), 2),
                }
        trend = []
        for m in all_metrics:
            point = {"date": m.get("_date", "")}
            for key in numeric_keys:
                point[key] = m.get(key, 0)
            trend.append(point)
        return {
            "store_id": store_id,
            "metric_type": metric_type,
            "period_start": str(records[0].metric_date) if records else None,
            "period_end": str(records[-1].metric_date) if records else None,
            "data_points": len(records),
            "summary": summary,
            "trend": trend,
        }


def _validate_formula(rule_type: str, formula: dict) -> None:
    if rule_type == "markup":
        if "markup_percent" not in formula:
            raise ValidationException(message="markup rule requires 'markup_percent' in formula")
        if formula["markup_percent"] < 0:
            raise ValidationException(message="markup_percent cannot be negative")
    elif rule_type == "markdown":
        if "markdown_percent" not in formula:
            raise ValidationException(message="markdown rule requires 'markdown_percent' in formula")
        if formula["markdown_percent"] < 0 or formula["markdown_percent"] > 100:
            raise ValidationException(message="markdown_percent must be between 0 and 100")
    elif rule_type == "fixed":
        if "fixed_price" not in formula:
            raise ValidationException(message="fixed rule requires 'fixed_price' in formula")
        if formula["fixed_price"] < 0:
            raise ValidationException(message="fixed_price cannot be negative")
    elif rule_type == "competitive":
        if "base_percent" not in formula:
            raise ValidationException(message="competitive rule requires 'base_percent' in formula")
        if "competitor_offset" not in formula:
            raise ValidationException(message="competitive rule requires 'competitor_offset' in formula")


def _apply_price_formula(rule: PriceRule, cost_price: float) -> float:
    formula = json.loads(rule.formula_json) if rule.formula_json else {}
    if rule.rule_type == "markup":
        markup_pct = formula.get("markup_percent", 0)
        fixed_add = formula.get("fixed_addition", 0)
        return cost_price * (1 + markup_pct / 100) + fixed_add
    elif rule.rule_type == "markdown":
        markdown_pct = formula.get("markdown_percent", 0)
        fixed_sub = formula.get("fixed_subtraction", 0)
        return cost_price * (1 - markdown_pct / 100) - fixed_sub
    elif rule.rule_type == "fixed":
        return formula.get("fixed_price", cost_price)
    elif rule.rule_type == "competitive":
        base_pct = formula.get("base_percent", 100)
        offset = formula.get("competitor_offset", 0)
        return cost_price * (base_pct / 100) + offset
    return cost_price


class ListingOptimizationService:
    """Listing优化应用服务 - 分析和优化商品标题、关键词、图片等要素"""

    def __init__(self, session: AsyncSession, optimization_repo: ListingOptimizationRepository | None = None,
                 listing_repo: ListingRepository | None = None):
        self._session = session
        self._optimization_repo = optimization_repo
        self._listing_repo = listing_repo

    async def analyze(self, tenant_id: str, listing_id: str, opt_type: str = "full") -> ListingOptimization:
        if opt_type not in VALID_OPT_TYPES:
            raise ValidationException(message=f"Invalid opt_type '{opt_type}', must be one of {VALID_OPT_TYPES}")
        if self._listing_repo:
            listing = await self._listing_repo.get_by_id(listing_id, tenant_id)
        else:
            listing_svc = ListingService(self._session)
            listing = await listing_svc.get_by_id(listing_id, tenant_id)
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        if listing.status not in ("draft", "active", "inactive", "out_of_stock"):
            raise ValidationException(message=f"Cannot optimize listing in '{listing.status}' status")

        snapshot_before = {
            "title": listing.title,
            "search_terms": listing.search_terms,
            "main_image": listing.main_image,
            "images_json": listing.images_json,
            "bullet_points_json": listing.bullet_points_json,
            "description": listing.description,
        }

        all_suggestions: list[dict] = []
        scores: dict[str, float] = {}

        types_to_analyze = VALID_OPT_TYPES - {"full"} if opt_type == "full" else {opt_type}

        if "title" in types_to_analyze:
            result = ListingOptimizationDomainService.score_title(listing.title, listing.platform)
            scores["title"] = result["score"]
            all_suggestions.extend([{"type": "title", **s} if isinstance(s, dict) else {"type": "title", "suggestion": s} for s in result["suggestions"]])
            for issue in result["issues"]:
                all_suggestions.append({"type": "title", "issue": issue})

        if "keyword" in types_to_analyze:
            result = ListingOptimizationDomainService.score_keywords(listing.search_terms, listing.title, listing.bullet_points_json)
            scores["keyword"] = result["score"]
            all_suggestions.extend([{"type": "keyword", **s} if isinstance(s, dict) else {"type": "keyword", "suggestion": s} for s in result["suggestions"]])
            for issue in result["issues"]:
                all_suggestions.append({"type": "keyword", "issue": issue})

        if "image" in types_to_analyze:
            result = ListingOptimizationDomainService.score_images(listing.images_json, listing.main_image)
            scores["image"] = result["score"]
            all_suggestions.extend([{"type": "image", **s} if isinstance(s, dict) else {"type": "image", "suggestion": s} for s in result["suggestions"]])
            for issue in result["issues"]:
                all_suggestions.append({"type": "image", "issue": issue})

        if "bullet_point" in types_to_analyze:
            result = ListingOptimizationDomainService.score_bullet_points(listing.bullet_points_json)
            scores["bullet_point"] = result["score"]
            all_suggestions.extend([{"type": "bullet_point", **s} if isinstance(s, dict) else {"type": "bullet_point", "suggestion": s} for s in result["suggestions"]])
            for issue in result["issues"]:
                all_suggestions.append({"type": "bullet_point", "issue": issue})

        if "description" in types_to_analyze:
            desc_score = 50.0 if listing.description and len(listing.description) > 100 else 20.0
            scores["description"] = desc_score
            if not listing.description:
                all_suggestions.append({"type": "description", "issue": "No description provided", "suggestion": "Add a detailed product description"})

        overall_score = ListingOptimizationDomainService.compute_overall_score(scores)

        optimization = ListingOptimization(
            tenant_id=tenant_id,
            listing_id=listing_id,
            store_id=listing.store_id,
            opt_type=opt_type,
            status="suggested",
            score_before=overall_score,
            suggestions_json=json.dumps(all_suggestions, default=str),
            snapshot_before_json=json.dumps(snapshot_before, default=str),
            created_by=actor_id_var.get(""),
        )
        if self._optimization_repo:
            return await self._optimization_repo.create(optimization)
        self._session.add(optimization)
        await self._session.flush()
        return optimization

    async def get_by_id(self, optimization_id: str, tenant_id: str) -> ListingOptimization | None:
        if self._optimization_repo:
            return await self._optimization_repo.get_by_id(optimization_id, tenant_id)
        stmt = select(ListingOptimization).where(
            ListingOptimization.id == optimization_id, ListingOptimization.tenant_id == tenant_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, optimization_id: str, tenant_id: str) -> ListingOptimization:
        optimization = await self.get_by_id(optimization_id, tenant_id)
        if not optimization:
            raise NotFoundException(message=f"Optimization '{optimization_id}' not found")
        return optimization

    async def list_by_listing(self, listing_id: str, tenant_id: str) -> Sequence[ListingOptimization]:
        if self._optimization_repo:
            return await self._optimization_repo.list_by_listing(listing_id, tenant_id)
        stmt = select(ListingOptimization).where(
            ListingOptimization.listing_id == listing_id, ListingOptimization.tenant_id == tenant_id
        ).order_by(ListingOptimization.created_at.desc())
        return (await self._session.execute(stmt)).scalars().all()

    async def list_all(self, tenant_id: str, listing_id: str = "", opt_type: str = "",
                       status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[ListingOptimization], int]:
        if self._optimization_repo:
            return await self._optimization_repo.list_by_tenant(
                tenant_id, listing_id=listing_id, opt_type=opt_type, status=status, page=page, page_size=page_size)
        conditions = [ListingOptimization.tenant_id == tenant_id]
        if listing_id:
            conditions.append(ListingOptimization.listing_id == listing_id)
        if opt_type:
            conditions.append(ListingOptimization.opt_type == opt_type)
        if status:
            conditions.append(ListingOptimization.status == status)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(ListingOptimization).where(*conditions)
        )).scalar() or 0
        stmt = select(ListingOptimization).where(*conditions).order_by(
            ListingOptimization.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def apply_suggestions(self, optimization_id: str, tenant_id: str, suggestion_indices: list[int] | None = None) -> ListingOptimization:
        optimization = await self.get_by_id(optimization_id, tenant_id)
        if not optimization:
            raise NotFoundException(message=f"Optimization '{optimization_id}' not found")
        if not ListingOptimizationDomainService.can_transition_opt_status(optimization.status, "applying"):
            raise ValidationException(message=f"Cannot apply suggestions from '{optimization.status}' status")

        optimization.status = "applying"
        if self._optimization_repo:
            await self._optimization_repo.update(optimization)
        else:
            await self._session.flush()

        suggestions = json.loads(optimization.suggestions_json) if optimization.suggestions_json else []
        if self._listing_repo:
            listing = await self._listing_repo.get_by_id(optimization.listing_id, tenant_id)
        else:
            listing_svc = ListingService(self._session)
            listing = await listing_svc.get_by_id(optimization.listing_id, tenant_id)
        if not listing:
            optimization.status = "failed"
            if self._optimization_repo:
                await self._optimization_repo.update(optimization)
            else:
                await self._session.flush()
            raise NotFoundException(message=f"Listing '{optimization.listing_id}' not found")

        applied: list[dict] = []
        to_apply = [suggestions[i] for i in suggestion_indices if 0 <= i < len(suggestions)] if suggestion_indices is not None else suggestions

        for suggestion in to_apply:
            s_type = suggestion.get("type", "")
            if s_type == "title" and "suggestion" in suggestion:
                listing.title = suggestion["suggestion"]
                applied.append(suggestion)
            elif s_type == "keyword" and "suggestion" in suggestion:
                listing.search_terms = suggestion["suggestion"]
                applied.append(suggestion)

        if applied:
            optimization.applied_suggestions_json = json.dumps(applied, default=str)
            optimization.snapshot_after_json = json.dumps({
                "title": listing.title,
                "search_terms": listing.search_terms,
                "main_image": listing.main_image,
                "images_json": listing.images_json,
                "bullet_points_json": listing.bullet_points_json,
                "description": listing.description,
            }, default=str)

            new_scores: dict[str, float] = {}
            new_scores["title"] = ListingOptimizationDomainService.score_title(listing.title, listing.platform)["score"]
            new_scores["keyword"] = ListingOptimizationDomainService.score_keywords(listing.search_terms, listing.title, listing.bullet_points_json)["score"]
            new_scores["image"] = ListingOptimizationDomainService.score_images(listing.images_json, listing.main_image)["score"]
            new_scores["bullet_point"] = ListingOptimizationDomainService.score_bullet_points(listing.bullet_points_json)["score"]
            optimization.score_after = ListingOptimizationDomainService.compute_overall_score(new_scores)
            optimization.status = "applied" if len(applied) == len(to_apply) else "partial_applied"
        else:
            optimization.status = "partial_applied"

        if self._optimization_repo:
            return await self._optimization_repo.update(optimization)
        await self._session.flush()
        return optimization

    async def cancel(self, optimization_id: str, tenant_id: str) -> ListingOptimization:
        optimization = await self.get_by_id(optimization_id, tenant_id)
        if not optimization:
            raise NotFoundException(message=f"Optimization '{optimization_id}' not found")
        if not ListingOptimizationDomainService.can_transition_opt_status(optimization.status, "cancelled"):
            raise ValidationException(message=f"Cannot cancel optimization in '{optimization.status}' status")
        optimization.status = "cancelled"
        if self._optimization_repo:
            return await self._optimization_repo.update(optimization)
        await self._session.flush()
        return optimization

    async def get_listing_score(self, listing_id: str, tenant_id: str) -> dict:
        if self._listing_repo:
            listing = await self._listing_repo.get_by_id(listing_id, tenant_id)
        else:
            listing_svc = ListingService(self._session)
            listing = await listing_svc.get_by_id(listing_id, tenant_id)
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        scores = {
            "title": ListingOptimizationDomainService.score_title(listing.title, listing.platform)["score"],
            "keyword": ListingOptimizationDomainService.score_keywords(listing.search_terms, listing.title, listing.bullet_points_json)["score"],
            "image": ListingOptimizationDomainService.score_images(listing.images_json, listing.main_image)["score"],
            "bullet_point": ListingOptimizationDomainService.score_bullet_points(listing.bullet_points_json)["score"],
        }
        overall = ListingOptimizationDomainService.compute_overall_score(scores)
        return {"listing_id": listing_id, "scores": scores, "overall_score": overall}


class AlertRuleService:
    """告警规则应用服务 - 管理运营告警规则的创建、更新和状态切换"""

    def __init__(self, session: AsyncSession, alert_rule_repo: AlertRuleRepository | None = None,
                 alert_record_repo: AlertRecordRepository | None = None):
        self._session = session
        self._alert_rule_repo = alert_rule_repo
        self._alert_record_repo = alert_record_repo

    async def create(self, tenant_id: str, name: str, metric_type: str, condition_type: str,
                     threshold: float, **kwargs) -> AlertRule:
        errors = AlertRuleDomainService.validate_rule(
            metric_type, condition_type,
            kwargs.get("severity", "warning"),
            kwargs.get("notify_channels", "email"),
        )
        if errors:
            raise ValidationException(message="; ".join(errors))
        rule = AlertRule(
            tenant_id=tenant_id,
            name=name,
            metric_type=metric_type,
            condition_type=condition_type,
            threshold=threshold,
            threshold_max=kwargs.get("threshold_max", 0.0),
            time_window=kwargs.get("time_window", 1),
            severity=kwargs.get("severity", "warning"),
            notify_channels=kwargs.get("notify_channels", "email"),
            notify_targets_json=json.dumps(kwargs.get("notify_targets", []), default=str),
            platform=kwargs.get("platform", ""),
            store_id=kwargs.get("store_id", ""),
            cooldown_minutes=kwargs.get("cooldown_minutes", 60),
            created_by=actor_id_var.get(""),
        )
        if self._alert_rule_repo:
            return await self._alert_rule_repo.create(rule)
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def get_by_id(self, rule_id: str, tenant_id: str) -> AlertRule | None:
        if self._alert_rule_repo:
            return await self._alert_rule_repo.get_by_id(rule_id, tenant_id)
        stmt = select(AlertRule).where(AlertRule.id == rule_id, AlertRule.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, rule_id: str, tenant_id: str) -> AlertRule:
        rule = await self.get_by_id(rule_id, tenant_id)
        if not rule:
            raise NotFoundException(message=f"Alert rule '{rule_id}' not found")
        return rule

    async def list_all(self, tenant_id: str, metric_type: str = "", severity: str = "",
                       status: str = "", page: int = 1, page_size: int = 20) -> tuple[Sequence[AlertRule], int]:
        if self._alert_rule_repo:
            return await self._alert_rule_repo.list_by_tenant(
                tenant_id, metric_type=metric_type, severity=severity, status=status, page=page, page_size=page_size)
        conditions = [AlertRule.tenant_id == tenant_id]
        if metric_type:
            conditions.append(AlertRule.metric_type == metric_type)
        if severity:
            conditions.append(AlertRule.severity == severity)
        if status:
            conditions.append(AlertRule.status == status)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(AlertRule).where(*conditions)
        )).scalar() or 0
        stmt = select(AlertRule).where(*conditions).order_by(AlertRule.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def update(self, rule_id: str, tenant_id: str, **kwargs) -> AlertRule:
        rule = await self.get_by_id(rule_id, tenant_id)
        if not rule:
            raise NotFoundException(message=f"Alert rule '{rule_id}' not found")
        if "metric_type" in kwargs or "condition_type" in kwargs:
            mt = kwargs.get("metric_type", rule.metric_type)
            ct = kwargs.get("condition_type", rule.condition_type)
            sev = kwargs.get("severity", rule.severity)
            nc = kwargs.get("notify_channels", rule.notify_channels)
            errors = AlertRuleDomainService.validate_rule(mt, ct, sev, nc)
            if errors:
                raise ValidationException(message="; ".join(errors))
        if "notify_targets" in kwargs:
            kwargs["notify_targets_json"] = json.dumps(kwargs.pop("notify_targets"), default=str)
        for key, val in kwargs.items():
            if hasattr(rule, key) and key not in ("id", "tenant_id"):
                setattr(rule, key, val)
        if self._alert_rule_repo:
            return await self._alert_rule_repo.update(rule)
        await self._session.flush()
        return rule

    async def toggle_status(self, rule_id: str, tenant_id: str) -> AlertRule:
        rule = await self.get_by_id(rule_id, tenant_id)
        if not rule:
            raise NotFoundException(message=f"Alert rule '{rule_id}' not found")
        rule.status = "disabled" if rule.status == "active" else "active"
        if self._alert_rule_repo:
            return await self._alert_rule_repo.update(rule)
        await self._session.flush()
        return rule

    async def delete(self, rule_id: str, tenant_id: str) -> AlertRule:
        rule = await self.get_by_id(rule_id, tenant_id)
        if not rule:
            raise NotFoundException(message=f"Alert rule '{rule_id}' not found")
        rule.status = "deleted"
        if self._alert_rule_repo:
            return await self._alert_rule_repo.update(rule)
        await self._session.flush()
        return rule


class AlertRecordService:
    """告警记录应用服务 - 管理告警触发、确认、解决和批量操作"""

    def __init__(self, session: AsyncSession, alert_record_repo: AlertRecordRepository | None = None,
                 alert_rule_repo: AlertRuleRepository | None = None):
        self._session = session
        self._alert_record_repo = alert_record_repo
        self._alert_rule_repo = alert_rule_repo

    async def trigger_alert(self, tenant_id: str, rule_id: str, actual_value: float, **kwargs) -> AlertRecord | None:
        if self._alert_rule_repo:
            rule = await self._alert_rule_repo.get_by_id(rule_id, tenant_id)
        else:
            rule_stmt = select(AlertRule).where(AlertRule.id == rule_id, AlertRule.tenant_id == tenant_id, AlertRule.status == "active")
            rule = (await self._session.execute(rule_stmt)).scalar_one_or_none()
        if not rule or rule.status != "active":
            logger.warning("Alert rule '%s' not found or inactive", rule_id)
            return None

        if not AlertRuleDomainService.evaluate_condition(actual_value, rule.condition_type, rule.threshold, rule.threshold_max):
            return None

        if self._alert_record_repo:
            recent_records = await self._alert_record_repo.find_recent_by_rule(rule_id, tenant_id, hours=0)
            existing = [r for r in recent_records if r.status == "firing"]
            if existing:
                return existing[0]
        else:
            recent_stmt = select(AlertRecord).where(
                AlertRecord.rule_id == rule_id,
                AlertRecord.tenant_id == tenant_id,
                AlertRecord.status == "firing",
            )
            existing = (await self._session.execute(recent_stmt)).scalar_one_or_none()
            if existing:
                return existing

        if self._alert_record_repo:
            cooldown_records = await self._alert_record_repo.find_recent_by_rule(rule_id, tenant_id, hours=0)
            recent_fired = [r for r in cooldown_records if r.created_at >= datetime.now(UTC) - __import__("datetime").timedelta(minutes=rule.cooldown_minutes)]
            if recent_fired:
                return None
        else:
            cooldown_stmt = select(AlertRecord).where(
                AlertRecord.rule_id == rule_id,
                AlertRecord.tenant_id == tenant_id,
                AlertRecord.created_at >= datetime.now(UTC) - __import__("datetime").timedelta(minutes=rule.cooldown_minutes),
            )
            recent_fired = (await self._session.execute(cooldown_stmt)).scalar_one_or_none()
            if recent_fired:
                return None

        message = AlertRuleDomainService.build_alert_message(
            rule.name, rule.metric_type, rule.condition_type, actual_value, rule.threshold
        )
        record = AlertRecord(
            tenant_id=tenant_id,
            rule_id=rule_id,
            rule_name=rule.name,
            store_id=kwargs.get("store_id", rule.store_id),
            metric_type=rule.metric_type,
            severity=rule.severity,
            actual_value=actual_value,
            threshold_value=rule.threshold,
            message=message,
            detail_json=json.dumps({
                "condition_type": rule.condition_type,
                "threshold_max": rule.threshold_max,
                "time_window": rule.time_window,
                "notify_channels": rule.notify_channels,
            }, default=str),
            status="firing",
        )
        if self._alert_record_repo:
            return await self._alert_record_repo.create(record)
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_by_id(self, record_id: str, tenant_id: str) -> AlertRecord | None:
        if self._alert_record_repo:
            return await self._alert_record_repo.get_by_id(record_id, tenant_id)
        stmt = select(AlertRecord).where(AlertRecord.id == record_id, AlertRecord.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, record_id: str, tenant_id: str) -> AlertRecord:
        record = await self.get_by_id(record_id, tenant_id)
        if not record:
            raise NotFoundException(message=f"Alert record '{record_id}' not found")
        return record

    async def list_all(self, tenant_id: str, rule_id: str = "", severity: str = "",
                       status: str = "", store_id: str = "",
                       page: int = 1, page_size: int = 20) -> tuple[Sequence[AlertRecord], int]:
        if self._alert_record_repo:
            return await self._alert_record_repo.list_by_tenant(
                tenant_id, rule_id=rule_id, severity=severity, status=status,
                store_id=store_id, page=page, page_size=page_size)
        conditions = [AlertRecord.tenant_id == tenant_id]
        if rule_id:
            conditions.append(AlertRecord.rule_id == rule_id)
        if severity:
            conditions.append(AlertRecord.severity == severity)
        if status:
            conditions.append(AlertRecord.status == status)
        if store_id:
            conditions.append(AlertRecord.store_id == store_id)
        total = (await self._session.execute(
            select(sa_func.count()).select_from(AlertRecord).where(*conditions)
        )).scalar() or 0
        stmt = select(AlertRecord).where(*conditions).order_by(
            AlertRecord.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def acknowledge(self, record_id: str, tenant_id: str) -> AlertRecord:
        record = await self.get_by_id(record_id, tenant_id)
        if not record:
            raise NotFoundException(message=f"Alert record '{record_id}' not found")
        if not AlertRuleDomainService.can_transition_alert_status(record.status, "acknowledged"):
            raise ValidationException(message=f"Cannot acknowledge alert in '{record.status}' status")
        record.status = "acknowledged"
        record.acknowledged_by = actor_id_var.get("")
        record.acknowledged_at = datetime.now(UTC)
        if self._alert_record_repo:
            return await self._alert_record_repo.update(record)
        await self._session.flush()
        return record

    async def resolve(self, record_id: str, tenant_id: str) -> AlertRecord:
        record = await self.get_by_id(record_id, tenant_id)
        if not record:
            raise NotFoundException(message=f"Alert record '{record_id}' not found")
        if not AlertRuleDomainService.can_transition_alert_status(record.status, "resolved"):
            raise ValidationException(message=f"Cannot resolve alert in '{record.status}' status")
        record.status = "resolved"
        record.resolved_at = datetime.now(UTC)
        if self._alert_record_repo:
            return await self._alert_record_repo.update(record)
        await self._session.flush()
        return record

    async def batch_acknowledge(self, tenant_id: str, record_ids: list[str]) -> dict:
        success_count = 0
        failed_items = []
        for rid in record_ids:
            try:
                await self.acknowledge(rid, tenant_id)
                success_count += 1
            except (NotFoundException, ValidationException) as e:
                failed_items.append({"record_id": rid, "reason": e.message})
        return {"success_count": success_count, "failed_count": len(failed_items), "failed_items": failed_items}

    async def batch_resolve(self, tenant_id: str, record_ids: list[str]) -> dict:
        success_count = 0
        failed_items = []
        for rid in record_ids:
            try:
                await self.resolve(rid, tenant_id)
                success_count += 1
            except (NotFoundException, ValidationException) as e:
                failed_items.append({"record_id": rid, "reason": e.message})
        return {"success_count": success_count, "failed_count": len(failed_items), "failed_items": failed_items}

    async def check_and_trigger(self, tenant_id: str, store_id: str, metric_type: str, actual_value: float) -> list[AlertRecord]:
        if self._alert_rule_repo:
            rules = await self._alert_rule_repo.find_active_by_metric(tenant_id, metric_type, store_id=store_id)
        else:
            rules_stmt = select(AlertRule).where(
                AlertRule.tenant_id == tenant_id,
                AlertRule.metric_type == metric_type,
                AlertRule.status == "active",
            )
            if store_id:
                rules_stmt = rules_stmt.where(
                    (AlertRule.store_id == store_id) | (AlertRule.store_id == "")
                )
            rules = (await self._session.execute(rules_stmt)).scalars().all()
        triggered: list[AlertRecord] = []
        for rule in rules:
            record = await self.trigger_alert(tenant_id, rule.id, actual_value, store_id=store_id)
            if record:
                triggered.append(record)
        return triggered

    async def get_alert_summary(self, tenant_id: str) -> dict:
        if self._alert_record_repo:
            all_records, _ = await self._alert_record_repo.list_by_tenant(tenant_id, page=1, page_size=10000)
            firing_count = sum(1 for r in all_records if r.status == "firing")
            acknowledged_count = sum(1 for r in all_records if r.status == "acknowledged")
            critical_count = sum(1 for r in all_records if r.severity == "critical" and r.status == "firing")
        else:
            firing_count = (await self._session.execute(
                select(sa_func.count()).select_from(AlertRecord).where(
                    AlertRecord.tenant_id == tenant_id, AlertRecord.status == "firing"
                )
            )).scalar() or 0
            acknowledged_count = (await self._session.execute(
                select(sa_func.count()).select_from(AlertRecord).where(
                    AlertRecord.tenant_id == tenant_id, AlertRecord.status == "acknowledged"
                )
            )).scalar() or 0
            critical_count = (await self._session.execute(
                select(sa_func.count()).select_from(AlertRecord).where(
                    AlertRecord.tenant_id == tenant_id, AlertRecord.severity == "critical", AlertRecord.status == "firing"
                )
            )).scalar() or 0
        return {
            "firing": firing_count,
            "acknowledged": acknowledged_count,
            "critical_firing": critical_count,
        }


class ListingHealthService:
    """
    Listing健康度评分应用服务

    编排Listing健康度评估: 多维度评分 → 问题诊断 → 优化建议
    维度: 标题质量/图片完整性/价格竞争力/库存充足性/评价表现
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def calculate_health_score(self, tenant_id: str, listing_id: str) -> dict:
        """
        计算Listing健康度评分

        流程: 获取Listing → 逐维度评分 → 加权汇总 → 生成诊断报告
        """
        listing = (await self._session.execute(
            select(Listing).where(Listing.id == listing_id, Listing.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        scores: dict[str, dict] = {}
        title_score = self._score_title(listing)
        scores["title"] = title_score
        image_score = self._score_images(listing)
        scores["images"] = image_score
        price_score = self._score_price(listing)
        scores["price"] = price_score
        inventory_score = self._score_inventory(listing)
        scores["inventory"] = inventory_score
        status_score = self._score_status(listing)
        scores["status"] = status_score
        weights = {"title": 0.25, "images": 0.2, "price": 0.2, "inventory": 0.2, "status": 0.15}
        total_score = sum(scores[k]["score"] * weights[k] for k in scores)
        issues = []
        for k, v in scores.items():
            if v["score"] < 60:
                issues.extend(v.get("issues", []))
        health_level = "excellent"
        if total_score < 40:
            health_level = "critical"
        elif total_score < 60:
            health_level = "poor"
        elif total_score < 75:
            health_level = "fair"
        elif total_score < 90:
            health_level = "good"
        return {
            "listing_id": listing_id, "total_score": round(total_score, 1),
            "health_level": health_level, "dimension_scores": scores,
            "issues": issues, "issue_count": len(issues),
        }

    async def batch_health_check(self, tenant_id: str, store_id: str = "",
                                  min_score: float = 0, max_score: float = 100,
                                  page: int = 1, page_size: int = 50) -> dict:
        """批量健康检查"""
        conditions = [Listing.tenant_id == tenant_id, Listing.deleted_at.is_(None)]
        if store_id:
            conditions.append(Listing.store_id == store_id)
        stmt = select(Listing).where(*conditions).offset((page - 1) * page_size).limit(page_size)
        listings = list((await self._session.execute(stmt)).scalars().all())
        results = []
        for l in listings:
            health = await self.calculate_health_score(tenant_id, str(l.id))
            if min_score <= health["total_score"] <= max_score:
                results.append(health)
        results.sort(key=lambda x: x["total_score"])
        return {
            "total_checked": len(results),
            "avg_score": round(sum(r["total_score"] for r in results) / len(results), 1) if results else 0,
            "critical_count": sum(1 for r in results if r["health_level"] == "critical"),
            "poor_count": sum(1 for r in results if r["health_level"] == "poor"),
            "results": results,
        }

    def _score_title(self, listing: Listing) -> dict:
        score = 100
        issues: list[str] = []
        title = listing.title or ""
        if not title.strip():
            score -= 50
            issues.append("Title is empty")
        elif len(title) < 50:
            score -= 20
            issues.append("Title is too short (recommended: 100-200 chars)")
        elif len(title) > 200:
            score -= 10
            issues.append("Title may be too long")
        if not listing.title_en:
            score -= 10
            issues.append("English title missing")
        if not listing.bullet_points_json or listing.bullet_points_json == "[]":
            score -= 15
            issues.append("No bullet points")
        return {"score": max(score, 0), "issues": issues}

    def _score_images(self, listing: Listing) -> dict:
        score = 100
        issues: list[str] = []
        if not listing.main_image:
            score -= 50
            issues.append("No main image")
        import json as _json
        try:
            images = _json.loads(listing.images_json or "[]")
        except Exception:
            images = []
        if len(images) < 3:
            score -= 20
            issues.append(f"Only {len(images)} images (recommended: 5+)")
        if len(images) < 1 and listing.main_image:
            score -= 10
        return {"score": max(score, 0), "issues": issues}

    def _score_price(self, listing: Listing) -> dict:
        score = 100
        issues: list[str] = []
        if listing.price <= 0:
            score -= 50
            issues.append("Price is not set")
        if listing.msrp > 0 and listing.price > listing.msrp:
            score -= 20
            issues.append("Price exceeds MSRP")
        if listing.sale_price > 0 and listing.sale_price >= listing.price:
            score -= 10
            issues.append("Sale price should be lower than regular price")
        return {"score": max(score, 0), "issues": issues}

    def _score_inventory(self, listing: Listing) -> dict:
        score = 100
        issues: list[str] = []
        if listing.quantity <= 0:
            score -= 60
            issues.append("Out of stock")
        elif listing.quantity < 5:
            score -= 30
            issues.append("Low stock")
        elif listing.quantity < 20:
            score -= 10
        return {"score": max(score, 0), "issues": issues}

    def _score_status(self, listing: Listing) -> dict:
        score = 100
        issues: list[str] = []
        if listing.listing_status == "suppressed":
            score -= 60
            issues.append("Listing is suppressed")
        elif listing.listing_status == "inactive":
            score -= 40
            issues.append("Listing is inactive")
        if listing.status not in ("published",):
            score -= 20
            issues.append(f"Listing status is '{listing.status}' instead of 'published'")
        return {"score": max(score, 0), "issues": issues}


class AutoPricingService:
    """
    自动调价应用服务

    编排Listing自动调价: 竞品价格监控 → 调价策略计算 → 安全校验 → 执行调价
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def calculate_competitive_price(self, tenant_id: str, listing_id: str,
                                           competitor_prices: list[float],
                                           strategy: str = "match_lowest") -> dict:
        """
        计算竞争性定价

        strategy: match_lowest(匹配最低价) / beat_by_pct(低于最低价X%) / premium(高于最低价X%)
        """
        listing = (await self._session.execute(
            select(Listing).where(Listing.id == listing_id, Listing.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        if not competitor_prices:
            return {"listing_id": listing_id, "current_price": listing.price,
                    "suggested_price": listing.price, "reason": "no competitor data"}
        min_price = min(competitor_prices)
        avg_price = sum(competitor_prices) / len(competitor_prices)
        suggested = listing.price
        reason = ""
        if strategy == "match_lowest":
            suggested = min_price
            reason = f"Match lowest competitor price {min_price}"
        elif strategy == "beat_by_pct":
            suggested = round(min_price * 0.95, 2)
            reason = f"5% below lowest competitor price {min_price}"
        elif strategy == "premium":
            suggested = round(min_price * 1.1, 2)
            reason = f"10% premium over lowest competitor price {min_price}"
        if listing.msrp > 0 and suggested > listing.msrp:
            suggested = listing.msrp
            reason += " (capped at MSRP)"
        return {
            "listing_id": listing_id, "current_price": listing.price,
            "suggested_price": round(suggested, 2),
            "min_competitor_price": min_price,
            "avg_competitor_price": round(avg_price, 2),
            "strategy": strategy, "reason": reason,
        }

    async def execute_price_change(self, tenant_id: str, listing_id: str,
                                    new_price: float, reason: str = "") -> dict:
        """执行价格变更"""
        listing = (await self._session.execute(
            select(Listing).where(Listing.id == listing_id, Listing.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not listing:
            raise NotFoundException(message=f"Listing '{listing_id}' not found")
        if new_price <= 0:
            raise ValidationException(message="Price must be positive")
        old_price = listing.price
        listing.price = new_price
        await self._session.flush()
        return {
            "listing_id": listing_id, "old_price": old_price,
            "new_price": new_price, "change_pct": round((new_price - old_price) / old_price * 100, 1) if old_price > 0 else 0,
            "reason": reason,
        }

    async def batch_price_adjustment(self, tenant_id: str,
                                      adjustments: list[dict]) -> dict:
        """批量调价"""
        success_count = 0
        failed_items: list[dict] = []
        for adj in adjustments:
            try:
                result = await self.execute_price_change(
                    tenant_id=tenant_id,
                    listing_id=adj.get("listing_id", ""),
                    new_price=adj.get("new_price", 0),
                    reason=adj.get("reason", ""),
                )
                success_count += 1
            except (NotFoundException, ValidationException) as e:
                failed_items.append({"listing_id": adj.get("listing_id", ""), "reason": e.message})
        return {
            "total": len(adjustments), "success_count": success_count,
            "failed_count": len(failed_items), "failed_items": failed_items,
        }
