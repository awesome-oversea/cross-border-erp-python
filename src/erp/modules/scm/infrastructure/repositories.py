from collections.abc import Sequence
from datetime import UTC, datetime
import inspect

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from erp.modules.scm.domain.models import (
    Inquiry,
    InquiryQuote,
    PurchaseOrder,
    PurchaseOrderItem,
    ReplenishmentPlan,
    Supplier,
    SupplierEvaluation,
)
from erp.modules.scm.domain.repositories import (
    InquiryQuoteRepository,
    InquiryRepository,
    PurchaseOrderItemRepository,
    PurchaseOrderRepository,
    ReplenishmentPlanRepository,
    SupplierEvaluationRepository,
    SupplierRepository,
)


class SqlSupplierRepository(SupplierRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, supplier_id: str, tenant_id: str) -> Supplier | None:
        stmt = select(Supplier).where(Supplier.id == supplier_id, Supplier.tenant_id == tenant_id, Supplier.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        candidate = result.scalar_one_or_none()
        if inspect.isawaitable(candidate):
            candidate = await candidate
        return candidate if isinstance(candidate, Supplier) else None

    async def get_by_code(self, code: str, tenant_id: str) -> Supplier | None:
        stmt = select(Supplier).where(Supplier.code == code, Supplier.tenant_id == tenant_id, Supplier.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        candidate = result.scalar_one_or_none()
        if inspect.isawaitable(candidate):
            candidate = await candidate
        return candidate if isinstance(candidate, Supplier) else None

    async def list_by_tenant(self, tenant_id: str, status: str = "", supplier_type: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Supplier], int]:
        conditions = [Supplier.tenant_id == tenant_id, Supplier.deleted_at.is_(None)]
        if status:
            conditions.append(Supplier.status == status)
        if supplier_type:
            conditions.append(Supplier.supplier_type == supplier_type)
        total = (await self._session.execute(select(func.count()).select_from(Supplier).where(*conditions))).scalar() or 0
        stmt = select(Supplier).where(*conditions).order_by(Supplier.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, supplier: Supplier) -> Supplier:
        self._session.add(supplier)
        await self._session.flush()
        return supplier

    async def update(self, supplier: Supplier) -> Supplier:
        await self._session.flush()
        return supplier

    async def soft_delete(self, supplier_id: str, tenant_id: str) -> bool:
        stmt = update(Supplier).where(Supplier.id == supplier_id, Supplier.tenant_id == tenant_id).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlPurchaseOrderRepository(PurchaseOrderRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, po_id: str, tenant_id: str) -> PurchaseOrder | None:
        stmt = select(PurchaseOrder).where(PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        candidate = result.scalar_one_or_none()
        if inspect.isawaitable(candidate):
            candidate = await candidate
        return candidate if isinstance(candidate, PurchaseOrder) else None

    async def get_by_po_no(self, po_no: str, tenant_id: str) -> PurchaseOrder | None:
        stmt = select(PurchaseOrder).where(PurchaseOrder.po_no == po_no, PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        candidate = result.scalar_one_or_none()
        if inspect.isawaitable(candidate):
            candidate = await candidate
        return candidate if isinstance(candidate, PurchaseOrder) else None

    async def list_by_tenant(self, tenant_id: str, status: str = "", supplier_id: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[PurchaseOrder], int]:
        conditions = [PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.deleted_at.is_(None)]
        if status:
            conditions.append(PurchaseOrder.status == status)
        if supplier_id:
            conditions.append(PurchaseOrder.supplier_id == supplier_id)
        total = (await self._session.execute(select(func.count()).select_from(PurchaseOrder).where(*conditions))).scalar() or 0
        stmt = select(PurchaseOrder).where(*conditions).order_by(PurchaseOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, po: PurchaseOrder) -> PurchaseOrder:
        self._session.add(po)
        await self._session.flush()
        return po

    async def update(self, po: PurchaseOrder) -> PurchaseOrder:
        await self._session.flush()
        return po

    async def soft_delete(self, po_id: str, tenant_id: str) -> bool:
        stmt = update(PurchaseOrder).where(PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == tenant_id).values(deleted_at=datetime.now(UTC))
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlPurchaseOrderItemRepository(PurchaseOrderItemRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_po(self, po_id: str, tenant_id: str) -> Sequence[PurchaseOrderItem]:
        stmt = select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == po_id, PurchaseOrderItem.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def create(self, item: PurchaseOrderItem) -> PurchaseOrderItem:
        self._session.add(item)
        await self._session.flush()
        return item

    async def update(self, item: PurchaseOrderItem) -> PurchaseOrderItem:
        await self._session.flush()
        return item


class SqlReplenishmentPlanRepository(ReplenishmentPlanRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, plan_id: str, tenant_id: str) -> ReplenishmentPlan | None:
        stmt = select(ReplenishmentPlan).where(ReplenishmentPlan.id == plan_id, ReplenishmentPlan.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[ReplenishmentPlan], int]:
        conditions = [ReplenishmentPlan.tenant_id == tenant_id]
        if status:
            conditions.append(ReplenishmentPlan.status == status)
        total = (await self._session.execute(select(func.count()).select_from(ReplenishmentPlan).where(*conditions))).scalar() or 0
        stmt = select(ReplenishmentPlan).where(*conditions).order_by(ReplenishmentPlan.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, plan: ReplenishmentPlan) -> ReplenishmentPlan:
        self._session.add(plan)
        await self._session.flush()
        return plan

    async def update(self, plan: ReplenishmentPlan) -> ReplenishmentPlan:
        await self._session.flush()
        return plan


class SqlSupplierEvaluationRepository(SupplierEvaluationRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_supplier(self, supplier_id: str, tenant_id: str) -> Sequence[SupplierEvaluation]:
        stmt = select(SupplierEvaluation).where(SupplierEvaluation.supplier_id == supplier_id, SupplierEvaluation.tenant_id == tenant_id).order_by(SupplierEvaluation.period.desc())
        return (await self._session.execute(stmt)).scalars().all()

    async def get_by_supplier_period(self, supplier_id: str, period: str, tenant_id: str) -> SupplierEvaluation | None:
        stmt = select(SupplierEvaluation).where(SupplierEvaluation.supplier_id == supplier_id, SupplierEvaluation.period == period, SupplierEvaluation.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create(self, evaluation: SupplierEvaluation) -> SupplierEvaluation:
        self._session.add(evaluation)
        await self._session.flush()
        return evaluation


class SqlInquiryRepository(InquiryRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, inquiry_id: str, tenant_id: str) -> Inquiry | None:
        stmt = select(Inquiry).where(Inquiry.id == inquiry_id, Inquiry.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_inquiry_no(self, inquiry_no: str, tenant_id: str) -> Inquiry | None:
        stmt = select(Inquiry).where(Inquiry.inquiry_no == inquiry_no, Inquiry.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, status: str = "",
                             page: int = 1, page_size: int = 20) -> tuple[Sequence[Inquiry], int]:
        conditions = [Inquiry.tenant_id == tenant_id]
        if status:
            conditions.append(Inquiry.status == status)
        total = (await self._session.execute(select(func.count()).select_from(Inquiry).where(*conditions))).scalar() or 0
        stmt = select(Inquiry).where(*conditions).order_by(Inquiry.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return (await self._session.execute(stmt)).scalars().all(), total

    async def create(self, inquiry: Inquiry) -> Inquiry:
        self._session.add(inquiry)
        await self._session.flush()
        return inquiry

    async def update(self, inquiry: Inquiry) -> Inquiry:
        await self._session.flush()
        return inquiry


class SqlInquiryQuoteRepository(InquiryQuoteRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_by_inquiry(self, inquiry_id: str, tenant_id: str) -> Sequence[InquiryQuote]:
        stmt = select(InquiryQuote).where(InquiryQuote.inquiry_id == inquiry_id, InquiryQuote.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def get_by_id(self, quote_id: str, tenant_id: str) -> InquiryQuote | None:
        stmt = select(InquiryQuote).where(InquiryQuote.id == quote_id, InquiryQuote.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create(self, quote: InquiryQuote) -> InquiryQuote:
        self._session.add(quote)
        await self._session.flush()
        return quote

    async def update(self, quote: InquiryQuote) -> InquiryQuote:
        await self._session.flush()
        return quote
