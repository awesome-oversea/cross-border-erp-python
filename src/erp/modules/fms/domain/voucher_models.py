from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class VoucherTemplate(Base):
    __tablename__ = "voucher_template"
    __table_args__ = {"schema": "fms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    template_code: Mapped[str] = mapped_column(String(100), nullable=False)
    template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    voucher_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True,
                                               comment="purchase/sales/inventory/adjustment/settlement/other")
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False, default="",
                                                comment="Event that triggers this voucher")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    debit_rules_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    credit_rules_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_auto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Voucher(Base):
    __tablename__ = "voucher"
    __table_args__ = {"schema": "fms"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    voucher_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    template_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    template_code: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    voucher_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    source_no: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    period: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    total_debit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    total_credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft",
                                         comment="draft/posted/cancelled/pushed")
    entries_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    push_target: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    push_status: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    push_detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    remark: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class VoucherEngineService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_template(self, tenant_id: str, template_code: str, template_name: str,
                               voucher_type: str, trigger_event: str = "",
                               description: str = "", debit_rules: list | None = None,
                               credit_rules: list | None = None,
                               is_auto: bool = True) -> VoucherTemplate:
        existing = await self._get_template_by_code(tenant_id, template_code)
        if existing:
            raise ValidationException(message=f"Template code '{template_code}' already exists")

        template = VoucherTemplate(
            tenant_id=tenant_id, template_code=template_code,
            template_name=template_name, voucher_type=voucher_type,
            trigger_event=trigger_event, description=description,
            debit_rules_json=json.dumps(debit_rules or [], default=str),
            credit_rules_json=json.dumps(credit_rules or [], default=str),
            is_auto=is_auto,
            created_by=actor_id_var.get(""),
        )
        self.session.add(template)
        await self.session.flush()
        return template

    async def update_template(self, template_id: str, tenant_id: str,
                               template_name: str | None = None,
                               description: str | None = None,
                               debit_rules: list | None = None,
                               credit_rules: list | None = None,
                               is_auto: bool | None = None) -> VoucherTemplate:
        template = await self._get_template_by_id(template_id, tenant_id)
        if not template:
            raise NotFoundException(message=f"Template '{template_id}' not found")
        if template_name is not None:
            template.template_name = template_name
        if description is not None:
            template.description = description
        if debit_rules is not None:
            template.debit_rules_json = json.dumps(debit_rules, default=str)
        if credit_rules is not None:
            template.credit_rules_json = json.dumps(credit_rules, default=str)
        if is_auto is not None:
            template.is_auto = is_auto
        template.version += 1
        await self.session.flush()
        return template

    async def deactivate_template(self, template_id: str, tenant_id: str) -> VoucherTemplate:
        template = await self._get_template_by_id(template_id, tenant_id)
        if not template:
            raise NotFoundException(message=f"Template '{template_id}' not found")
        template.is_active = False
        await self.session.flush()
        return template

    async def generate_voucher(self, tenant_id: str, template_code: str,
                                source_type: str, source_id: str,
                                source_no: str = "", context: dict | None = None,
                                period: str = "") -> Voucher:
        template = await self._get_template_by_code(tenant_id, template_code)
        if not template:
            raise NotFoundException(message=f"Template '{template_code}' not found")
        if not template.is_active:
            raise ValidationException(message=f"Template '{template_code}' is not active")

        ctx = context or {}
        if not period:
            period = datetime.now(UTC).strftime("%Y-%m")

        debit_entries = self._build_entries(json.loads(template.debit_rules_json), ctx, "debit")
        credit_entries = self._build_entries(json.loads(template.credit_rules_json), ctx, "credit")

        all_entries = debit_entries + credit_entries
        total_debit = sum(Decimal(str(e.get("amount", 0))) for e in debit_entries)
        total_credit = sum(Decimal(str(e.get("amount", 0))) for e in credit_entries)

        voucher_no = f"VCH-{template.voucher_type.upper()}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"

        voucher = Voucher(
            tenant_id=tenant_id, voucher_no=voucher_no,
            template_id=template.id, template_code=template.template_code,
            voucher_type=template.voucher_type,
            source_type=source_type, source_id=source_id,
            source_no=source_no, period=period,
            total_debit=total_debit, total_credit=total_credit,
            entries_json=json.dumps(all_entries, default=str),
            is_auto_generated=True,
            trace_id=trace_id_var.get(""),
            created_by=actor_id_var.get(""),
        )
        self.session.add(voucher)
        await self.session.flush()
        return voucher

    async def post_voucher(self, voucher_id: str, tenant_id: str) -> Voucher:
        voucher = await self._get_voucher_by_id(voucher_id, tenant_id)
        if not voucher:
            raise NotFoundException(message=f"Voucher '{voucher_id}' not found")
        if voucher.status != "draft":
            raise ValidationException(message=f"Voucher '{voucher_id}' is not in draft status")
        voucher.status = "posted"
        voucher.posted_at = datetime.now(UTC)
        voucher.posted_by = actor_id_var.get("")
        await self.session.flush()
        return voucher

    async def cancel_voucher(self, voucher_id: str, tenant_id: str) -> Voucher:
        voucher = await self._get_voucher_by_id(voucher_id, tenant_id)
        if not voucher:
            raise NotFoundException(message=f"Voucher '{voucher_id}' not found")
        if voucher.status == "posted":
            raise ValidationException(message="Posted voucher cannot be cancelled directly")
        voucher.status = "cancelled"
        await self.session.flush()
        return voucher

    async def push_to_external(self, voucher_id: str, tenant_id: str,
                                target: str = "kingdee") -> Voucher:
        voucher = await self._get_voucher_by_id(voucher_id, tenant_id)
        if not voucher:
            raise NotFoundException(message=f"Voucher '{voucher_id}' not found")
        if voucher.status != "posted":
            raise ValidationException(message="Only posted vouchers can be pushed")

        push_detail = json.dumps({
            "target": target,
            "voucher_no": voucher.voucher_no,
            "entries": json.loads(voucher.entries_json),
            "total_debit": float(voucher.total_debit),
            "total_credit": float(voucher.total_credit),
            "pushed_at": datetime.now(UTC).isoformat(),
        }, default=str)

        voucher.status = "pushed"
        voucher.pushed_at = datetime.now(UTC)
        voucher.push_target = target
        voucher.push_status = "success"
        voucher.push_detail = push_detail
        await self.session.flush()
        return voucher

    async def list_templates(self, tenant_id: str, voucher_type: str = "",
                              is_active: bool | None = None,
                              page: int = 1, page_size: int = 20) -> tuple[list[VoucherTemplate], int]:
        conditions = [VoucherTemplate.tenant_id == tenant_id]
        if voucher_type:
            conditions.append(VoucherTemplate.voucher_type == voucher_type)
        if is_active is not None:
            conditions.append(VoucherTemplate.is_active == is_active)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(VoucherTemplate).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(VoucherTemplate).where(*conditions).order_by(
            VoucherTemplate.voucher_type, VoucherTemplate.template_code
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_vouchers(self, tenant_id: str, voucher_type: str = "",
                             status: str = "", source_type: str = "",
                             period: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[list[Voucher], int]:
        conditions = [Voucher.tenant_id == tenant_id]
        if voucher_type:
            conditions.append(Voucher.voucher_type == voucher_type)
        if status:
            conditions.append(Voucher.status == status)
        if source_type:
            conditions.append(Voucher.source_type == source_type)
        if period:
            conditions.append(Voucher.period == period)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(Voucher).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(Voucher).where(*conditions).order_by(
            Voucher.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def init_defaults(self, tenant_id: str):
        defaults = [
            ("purchase_receipt", "采购入库凭证", "purchase", "purchase_order_received",
             "采购入库自动生成凭证",
             [{"account": "1401", "account_name": "库存商品", "amount_field": "total_amount", "description": "采购入库"}],
             [{"account": "2202", "account_name": "应付账款", "amount_field": "total_amount", "description": "采购入库"}]),
            ("purchase_payment", "采购付款凭证", "purchase", "purchase_payment_made",
             "采购付款自动生成凭证",
             [{"account": "2202", "account_name": "应付账款", "amount_field": "payment_amount", "description": "采购付款"}],
             [{"account": "1002", "account_name": "银行存款", "amount_field": "payment_amount", "description": "采购付款"}]),
            ("sales_shipment", "销售出库凭证", "sales", "sales_order_shipped",
             "销售出库自动生成凭证",
             [{"account": "6401", "account_name": "主营业务成本", "amount_field": "cost_amount", "description": "销售出库"}],
             [{"account": "1401", "account_name": "库存商品", "amount_field": "cost_amount", "description": "销售出库"}]),
            ("sales_revenue", "销售收入凭证", "sales", "sales_order_confirmed",
             "销售收入确认自动生成凭证",
             [{"account": "1122", "account_name": "应收账款", "amount_field": "total_amount", "description": "销售收入"}],
             [{"account": "6001", "account_name": "主营业务收入", "amount_field": "revenue_amount", "description": "销售收入"},
              {"account": "2221", "account_name": "应交税费-销项", "amount_field": "tax_amount", "description": "销售收入"}]),
            ("sales_payment_received", "销售收款凭证", "sales", "sales_payment_received",
             "销售收款自动生成凭证",
             [{"account": "1002", "account_name": "银行存款", "amount_field": "received_amount", "description": "销售收款"}],
             [{"account": "1122", "account_name": "应收账款", "amount_field": "received_amount", "description": "销售收款"}]),
            ("inventory_adjustment", "库存盘点调整凭证", "inventory", "inventory_adjusted",
             "库存盘点差异自动生成凭证",
             [{"account": "1901", "account_name": "待处理财产损溢", "amount_field": "loss_amount", "description": "盘亏"}],
             [{"account": "1401", "account_name": "库存商品", "amount_field": "loss_amount", "description": "盘亏"}]),
            ("warehouse_fee", "仓储费用凭证", "settlement", "warehouse_fee_settled",
             "仓储费用结算自动生成凭证",
             [{"account": "6602", "account_name": "管理费用-仓储费", "amount_field": "fee_amount", "description": "仓储费"}],
             [{"account": "2202", "account_name": "应付账款", "amount_field": "fee_amount", "description": "仓储费"}]),
            ("logistics_fee", "物流费用凭证", "settlement", "logistics_fee_settled",
             "物流费用结算自动生成凭证",
             [{"account": "6601", "account_name": "销售费用-物流费", "amount_field": "fee_amount", "description": "物流费"}],
             [{"account": "2202", "account_name": "应付账款", "amount_field": "fee_amount", "description": "物流费"}]),
        ]
        for code, name, vtype, trigger, desc, debit, credit in defaults:
            existing = await self._get_template_by_code(tenant_id, code)
            if not existing:
                await self.create_template(tenant_id, code, name, vtype,
                                           trigger_event=trigger, description=desc,
                                           debit_rules=debit, credit_rules=credit)

    def _build_entries(self, rules: list, context: dict, entry_type: str) -> list[dict]:
        entries = []
        for rule in rules:
            amount_field = rule.get("amount_field", "amount")
            amount = context.get(amount_field, 0)
            entry = {
                "account": rule.get("account", ""),
                "account_name": rule.get("account_name", ""),
                "amount": amount,
                "entry_type": entry_type,
                "description": rule.get("description", ""),
            }
            entries.append(entry)
        return entries

    async def _get_template_by_code(self, tenant_id: str, template_code: str) -> VoucherTemplate | None:
        stmt = select(VoucherTemplate).where(
            VoucherTemplate.tenant_id == tenant_id,
            VoucherTemplate.template_code == template_code,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _get_template_by_id(self, template_id: str, tenant_id: str) -> VoucherTemplate | None:
        stmt = select(VoucherTemplate).where(
            VoucherTemplate.id == template_id,
            VoucherTemplate.tenant_id == tenant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _get_voucher_by_id(self, voucher_id: str, tenant_id: str) -> Voucher | None:
        stmt = select(Voucher).where(
            Voucher.id == voucher_id,
            Voucher.tenant_id == tenant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
