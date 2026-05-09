from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:

    from sqlalchemy.ext.asyncio import AsyncSession


class SysParam(Base):
    __tablename__ = "sys_param"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    param_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    param_value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    value_type: Mapped[str] = mapped_column(String(20), nullable=False, default="string")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_encrypted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SysParamService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def set_param(self, tenant_id: str, category: str, param_key: str,
                        param_value: str, value_type: str = "string",
                        description: str = "", is_system: bool = False,
                        is_encrypted: bool = False, sort_order: int = 0) -> SysParam:
        stmt = select(SysParam).where(
            SysParam.tenant_id == tenant_id,
            SysParam.category == category,
            SysParam.param_key == param_key,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.param_value = param_value
            existing.value_type = value_type
            existing.description = description
            existing.is_encrypted = is_encrypted
            existing.sort_order = sort_order
            await self.session.flush()
            return existing
        param = SysParam(
            tenant_id=tenant_id, category=category, param_key=param_key,
            param_value=param_value, value_type=value_type,
            description=description, is_system=is_system,
            is_encrypted=is_encrypted, sort_order=sort_order,
            created_by=actor_id_var.get(""),
        )
        self.session.add(param)
        await self.session.flush()
        return param

    async def get_param(self, tenant_id: str, category: str, param_key: str) -> SysParam | None:
        stmt = select(SysParam).where(
            SysParam.tenant_id == tenant_id,
            SysParam.category == category,
            SysParam.param_key == param_key,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_param_or_raise(self, tenant_id: str, category: str, param_key: str) -> SysParam:
        param = await self.get_param(tenant_id, category, param_key)
        if not param:
            raise NotFoundException(message=f"SysParam '{category}.{param_key}' not found")
        return param

    async def get_value(self, tenant_id: str, category: str, param_key: str,
                        default: str = "") -> str:
        param = await self.get_param(tenant_id, category, param_key)
        return param.param_value if param else default

    async def get_bool(self, tenant_id: str, category: str, param_key: str,
                       default: bool = False) -> bool:
        val = await self.get_value(tenant_id, category, param_key, str(default).lower())
        return val.lower() in ("true", "1", "yes")

    async def get_int(self, tenant_id: str, category: str, param_key: str,
                      default: int = 0) -> int:
        val = await self.get_value(tenant_id, category, param_key, str(default))
        try:
            return int(val)
        except ValueError:
            return default

    async def list_by_category(self, tenant_id: str, category: str | None = None) -> list[SysParam]:
        stmt = select(SysParam).where(SysParam.tenant_id == tenant_id)
        if category:
            stmt = stmt.where(SysParam.category == category)
        stmt = stmt.order_by(SysParam.category, SysParam.sort_order, SysParam.param_key)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_param(self, tenant_id: str, category: str, param_key: str):
        param = await self.get_param(tenant_id, category, param_key)
        if not param:
            raise NotFoundException(f"Param not found: {category}.{param_key}")
        if param.is_system:
            raise ValidationException(f"System param cannot be deleted: {category}.{param_key}")
        await self.session.delete(param)
        await self.session.flush()

    async def init_defaults(self, tenant_id: str):
        defaults = [
            ("business", "order.auto_audit", "false", "boolean", "订单自动审核"),
            ("business", "order.profit_threshold", "0.05", "number", "订单利润率阈值"),
            ("business", "order.risk_check_enabled", "true", "boolean", "订单风险检查开关"),
            ("business", "inventory.negative_stock_allowed", "false", "boolean", "允许负库存"),
            ("business", "inventory.safety_stock_days", "7", "number", "安全库存天数"),
            ("business", "purchase.auto_approve_amount", "10000", "number", "采购单自动审批金额上限"),
            ("ai", "ai.enabled", "true", "boolean", "AI功能总开关"),
            ("ai", "ai.auto_execute", "false", "boolean", "AI建议自动执行开关"),
            ("ai", "ai.suggestion_ttl_hours", "72", "number", "AI建议有效期(小时)"),
            ("ai", "ai.pms.replenishment.enabled", "true", "boolean", "PMS补货建议接收开关"),
            ("ai", "ai.pms.product.enabled", "true", "boolean", "PMS选品建议接收开关"),
            ("ai", "ai.pms.ads.enabled", "true", "boolean", "PMS广告建议接收开关"),
            ("ai", "ai.pms.risk.enabled", "true", "boolean", "PMS风控建议接收开关"),
            ("ai", "ai.pms.cost.enabled", "true", "boolean", "PMS成本建议接收开关"),
            ("system", "system.currency.default", "CNY", "string", "默认币种"),
            ("system", "system.timezone", "Asia/Shanghai", "string", "系统时区"),
            ("system", "system.date_format", "YYYY-MM-DD", "string", "日期格式"),
            ("system", "system.page_size.default", "20", "number", "默认分页大小"),
        ]
        for cat, key, val, vtype, desc in defaults:
            existing = await self.get_param(tenant_id, cat, key)
            if not existing:
                await self.set_param(tenant_id, cat, key, val, vtype, desc, is_system=True)
