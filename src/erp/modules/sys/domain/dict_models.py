from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException

if TYPE_CHECKING:

    from sqlalchemy.ext.asyncio import AsyncSession


class DataDict(Base):
    __tablename__ = "data_dict"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    dict_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    dict_value: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    label: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    label_en: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    parent_key: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    remark: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DictType(Base):
    __tablename__ = "dict_type"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    remark: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DictItem(Base):
    __tablename__ = "dict_item"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    type_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    item_key: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    item_value: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    label: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DataDictService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, tenant_id: str, category: str, dict_key: str,
                     dict_value: str, label: str = "", label_en: str = "",
                     parent_key: str = "", sort_order: int = 0,
                     is_active: bool = True, remark: str = "") -> DataDict:
        stmt = select(DataDict).where(
            DataDict.tenant_id == tenant_id,
            DataDict.category == category,
            DataDict.dict_key == dict_key,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.dict_value = dict_value
            existing.label = label
            existing.label_en = label_en
            existing.parent_key = parent_key
            existing.sort_order = sort_order
            existing.is_active = is_active
            existing.remark = remark
            await self.session.flush()
            return existing
        item = DataDict(
            tenant_id=tenant_id, category=category, dict_key=dict_key,
            dict_value=dict_value, label=label, label_en=label_en,
            parent_key=parent_key, sort_order=sort_order,
            is_active=is_active, remark=remark,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def list_by_category(self, tenant_id: str, category: str,
                                parent_key: str | None = None,
                                is_active: bool | None = None) -> list[DataDict]:
        stmt = select(DataDict).where(DataDict.tenant_id == tenant_id, DataDict.category == category)
        if parent_key is not None:
            stmt = stmt.where(DataDict.parent_key == parent_key)
        if is_active is not None:
            stmt = stmt.where(DataDict.is_active == is_active)
        stmt = stmt.order_by(DataDict.sort_order, DataDict.dict_key)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_value(self, tenant_id: str, category: str, dict_key: str,
                        default: str = "") -> str:
        stmt = select(DataDict).where(
            DataDict.tenant_id == tenant_id,
            DataDict.category == category,
            DataDict.dict_key == dict_key,
            DataDict.is_active,
        )
        item = (await self.session.execute(stmt)).scalar_one_or_none()
        return item.dict_value if item else default

    async def delete_item(self, tenant_id: str, category: str, dict_key: str):
        stmt = select(DataDict).where(
            DataDict.tenant_id == tenant_id,
            DataDict.category == category,
            DataDict.dict_key == dict_key,
        )
        item = (await self.session.execute(stmt)).scalar_one_or_none()
        if not item:
            raise NotFoundException(f"Dict item not found: {category}.{dict_key}")
        await self.session.delete(item)
        await self.session.flush()

    async def init_defaults(self, tenant_id: str):
        defaults = [
            ("country", "CN", "CN", "中国", "China", "", 1),
            ("country", "US", "US", "美国", "United States", "", 2),
            ("country", "UK", "GB", "英国", "United Kingdom", "", 3),
            ("country", "DE", "DE", "德国", "Germany", "", 4),
            ("country", "JP", "JP", "日本", "Japan", "", 5),
            ("country", "FR", "FR", "法国", "France", "", 6),
            ("country", "IT", "IT", "意大利", "Italy", "", 7),
            ("country", "ES", "ES", "西班牙", "Spain", "", 8),
            ("country", "CA", "CA", "加拿大", "Canada", "", 9),
            ("country", "AU", "AU", "澳大利亚", "Australia", "", 10),
            ("currency", "CNY", "CNY", "人民币", "Chinese Yuan", "", 1),
            ("currency", "USD", "USD", "美元", "US Dollar", "", 2),
            ("currency", "EUR", "EUR", "欧元", "Euro", "", 3),
            ("currency", "GBP", "GBP", "英镑", "British Pound", "", 4),
            ("currency", "JPY", "JPY", "日元", "Japanese Yen", "", 5),
            ("currency", "CAD", "CAD", "加元", "Canadian Dollar", "", 6),
            ("currency", "AUD", "AUD", "澳元", "Australian Dollar", "", 7),
            ("marketplace", "amazon_us", "amazon_us", "Amazon美国站", "Amazon US", "", 1),
            ("marketplace", "amazon_uk", "amazon_uk", "Amazon英国站", "Amazon UK", "", 2),
            ("marketplace", "amazon_de", "amazon_de", "Amazon德国站", "Amazon DE", "", 3),
            ("marketplace", "amazon_jp", "amazon_jp", "Amazon日本站", "Amazon JP", "", 4),
            ("marketplace", "ebay_us", "ebay_us", "eBay美国站", "eBay US", "", 5),
            ("marketplace", "shopify", "shopify", "Shopify", "Shopify", "", 6),
            ("marketplace", "tiktok_shop", "tiktok_shop", "TikTok Shop", "TikTok Shop", "", 7),
            ("marketplace", "aliexpress", "aliexpress", "速卖通", "AliExpress", "", 8),
            ("channel_type", "b2c", "b2c", "B2C", "B2C", "", 1),
            ("channel_type", "b2b", "b2b", "B2B", "B2B", "", 2),
            ("channel_type", "wholesale", "wholesale", "批发", "Wholesale", "", 3),
            ("language", "zh", "zh", "中文", "Chinese", "", 1),
            ("language", "en", "en", "英文", "English", "", 2),
            ("language", "de", "de", "德语", "German", "", 3),
            ("language", "ja", "ja", "日语", "Japanese", "", 4),
            ("language", "fr", "fr", "法语", "French", "", 5),
            ("language", "es", "es", "西班牙语", "Spanish", "", 6),
            ("language", "it", "it", "意大利语", "Italian", "", 7),
            ("unit", "piece", "piece", "件", "Piece", "", 1),
            ("unit", "set", "set", "套", "Set", "", 2),
            ("unit", "box", "box", "箱", "Box", "", 3),
            ("unit", "kg", "kg", "千克", "Kilogram", "", 4),
            ("unit", "g", "g", "克", "Gram", "", 5),
            ("logistics_type", "express", "express", "快递", "Express", "", 1),
            ("logistics_type", "air", "air", "空运", "Air", "", 2),
            ("logistics_type", "sea", "sea", "海运", "Sea", "", 3),
            ("logistics_type", "rail", "rail", "铁路", "Rail", "", 4),
            ("logistics_type", "fba", "fba", "FBA", "FBA", "", 5),
        ]
        for cat, key, val, label, label_en, parent, sort in defaults:
            existing = await self.get_value(tenant_id, cat, key, "")
            if not existing:
                await self.upsert(tenant_id, cat, key, val, label, label_en, parent, sort)
