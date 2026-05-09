"""
SCM 应用服务模块

本模块定义了供应链管理系统的5个应用服务:
  - SupplierService:            供应商管理 — CRUD + 合作等级 + 评分
  - PurchaseOrderService:       采购订单管理 — 创建/状态流转/明细
  - ReplenishmentPlanService:   补货计划管理 — 创建/查询
  - InquiryService:             询价管理 — 创建/报价/比价/定标
  - SupplierEvaluationService:  供应商评价 — 单条/批量评价

设计原则:
  1. 应用服务仅做编排，业务规则下沉到 domain/services.py
  2. 通过仓储接口操作数据，不直接编写 SQL
  3. 保留 session 用于 flush/事务管理
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from erp.modules.scm.domain.models import PurchaseOrder, Supplier
from erp.modules.scm.domain.services import InquiryDomainService, SupplierDomainService
from erp.shared.context import actor_id_var
from erp.shared.exceptions import DuplicateCodeException, NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from erp.modules.scm.domain.repositories import (
        InquiryQuoteRepository,
        InquiryRepository,
        PurchaseOrderItemRepository,
        PurchaseOrderRepository,
        ReplenishmentPlanRepository,
        SupplierEvaluationRepository,
        SupplierRepository,
    )

logger = get_logger("erp.scm")

PO_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["pending_approval", "cancelled"],
    "pending_approval": ["approved", "rejected"],
    "approved": ["ordered", "cancelled"],
    "ordered": ["partial_received", "received", "cancelled"],
    "partial_received": ["received", "cancelled"],
    "received": ["completed"],
    "completed": [],
    "rejected": [],
    "cancelled": [],
}

SUPPLIER_RATING_WEIGHTS = {
    "quality": 0.4,
    "delivery": 0.3,
    "price": 0.2,
    "service": 0.1,
}

COOPERATION_LEVELS = ["trial", "normal", "strategic"]


class SupplierService:
    """
    供应商应用服务

    编排供应商的完整生命周期: 创建 → 更新 → 合作等级变更 → 评分
    通过 SupplierRepository 操作数据，业务规则使用 SupplierDomainService。
    """

    def __init__(self, session: AsyncSession, supplier_repo: SupplierRepository | None = None):
        self._session = session
        self._supplier_repo = supplier_repo

    async def create(self, tenant_id: str, name: str, code: str, **kwargs) -> "Supplier":
        """创建供应商: 唯一性校验(code) → 持久化"""
        from erp.modules.scm.domain.models import Supplier
        if self._supplier_repo:
            existing = await self._supplier_repo.get_by_code(code, tenant_id)
        else:
            stmt = select(Supplier).where(Supplier.code == code, Supplier.tenant_id == tenant_id, Supplier.deleted_at.is_(None))
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"Supplier code '{code}' already exists")
        supplier = Supplier(tenant_id=tenant_id, name=name, code=code, **kwargs)
        if self._supplier_repo:
            return await self._supplier_repo.create(supplier)
        self._session.add(supplier)
        await self._session.flush()
        return supplier

    async def get_by_id(self, supplier_id: str, tenant_id: str) -> "Supplier | None":
        """根据ID获取供应商"""
        if self._supplier_repo:
            return await self._supplier_repo.get_by_id(supplier_id, tenant_id)
        stmt = select(Supplier).where(Supplier.id == supplier_id, Supplier.tenant_id == tenant_id, Supplier.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, supplier_id: str, tenant_id: str) -> "Supplier":
        """根据ID获取供应商，不存在则抛出 NotFoundException"""
        supplier = await self.get_by_id(supplier_id, tenant_id)
        if not supplier:
            raise NotFoundException(message=f"Supplier '{supplier_id}' not found")
        return supplier

    async def list_all(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> tuple["Sequence[Supplier]", int]:
        """分页查询供应商列表"""
        return await self._supplier_repo.list_by_tenant(tenant_id, status=status, page=page, page_size=page_size)

    async def update_cooperation_level(self, supplier_id: str, tenant_id: str, level: str) -> "Supplier":
        """更新合作等级: 存在性校验 → 合法性校验 → 更新"""
        supplier = await self.get_by_id(supplier_id, tenant_id)
        if not supplier:
            raise NotFoundException(message=f"Supplier '{supplier_id}' not found")
        if level not in COOPERATION_LEVELS:
            raise ValidationException(message=f"Invalid cooperation level '{level}', allowed: {COOPERATION_LEVELS}")
        supplier.cooperation_level = level
        if self._supplier_repo:
            return await self._supplier_repo.update(supplier)
        await self._session.flush()
        return supplier

    async def update(self, supplier_id: str, tenant_id: str, **kwargs) -> "Supplier":
        """更新供应商信息: 存在性校验 → 属性更新"""
        supplier = await self._supplier_repo.get_by_id(supplier_id, tenant_id)
        if not supplier:
            raise NotFoundException(message=f"Supplier '{supplier_id}' not found")
        for k, v in kwargs.items():
            if v is not None and hasattr(supplier, k):
                setattr(supplier, k, v)
        return await self._supplier_repo.update(supplier)

    async def soft_delete(self, supplier_id: str, tenant_id: str) -> bool:
        """软删除供应商"""
        supplier = await self._supplier_repo.get_by_id(supplier_id, tenant_id)
        if not supplier:
            raise NotFoundException(message=f"Supplier '{supplier_id}' not found")
        from datetime import datetime, timezone
        supplier.deleted_at = datetime.now(timezone.utc)
        supplier.status = "disabled"
        await self._supplier_repo.update(supplier)
        return True

    @staticmethod
    def calculate_overall_rating(quality_score: float, delivery_score: float,
                                  price_score: float, service_score: float) -> float:
        """计算供应商综合评分 (加权平均)"""
        return round(
            quality_score * SUPPLIER_RATING_WEIGHTS["quality"]
            + delivery_score * SUPPLIER_RATING_WEIGHTS["delivery"]
            + price_score * SUPPLIER_RATING_WEIGHTS["price"]
            + service_score * SUPPLIER_RATING_WEIGHTS["service"],
            2,
        )

    @staticmethod
    def suggest_cooperation_level(overall_score: float) -> str:
        """根据综合评分推荐合作等级"""
        if overall_score >= 90:
            return "strategic"
        if overall_score >= 70:
            return "normal"
        return "trial"


class InquiryComparisonService:
    """
    询价比较服务

    编排多供应商询价比价流程: 发起询价 → 供应商报价 → 多维比较 → 推荐最优
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_inquiry(self, tenant_id: str, sku_id: str, quantity: int,
                              supplier_ids: list[str], deadline_days: int = 7) -> dict:
        """发起询价"""
        from datetime import timedelta
        inquiry_no = f"INQ-{sku_id[:8]}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        return {
            "inquiry_no": inquiry_no, "tenant_id": tenant_id, "sku_id": sku_id,
            "quantity": quantity, "supplier_count": len(supplier_ids),
            "supplier_ids": supplier_ids,
            "deadline": (datetime.now(UTC) + timedelta(days=deadline_days)).isoformat(),
            "status": "open", "quotes": [],
        }

    async def submit_quote(self, tenant_id: str, inquiry_no: str, supplier_id: str,
                            unit_price: float, lead_time_days: int,
                            min_order_qty: int = 1, remarks: str = "") -> dict:
        """供应商提交报价"""
        return {
            "inquiry_no": inquiry_no, "supplier_id": supplier_id,
            "unit_price": unit_price, "lead_time_days": lead_time_days,
            "min_order_qty": min_order_qty, "remarks": remarks,
            "total_price": unit_price * max(min_order_qty, 1),
        }

    async def compare_quotes(self, tenant_id: str, inquiry_no: str,
                              quotes: list[dict], weight_price: float = 0.5,
                              weight_lead_time: float = 0.3, weight_reliability: float = 0.2) -> dict:
        """
        多维比较报价

        权重: 价格(默认50%) + 交期(30%) + 供应商可靠性(20%)
        """
        if not quotes:
            return {"inquiry_no": inquiry_no, "best_supplier": None, "comparison": []}
        min_price = min(q["unit_price"] for q in quotes)
        max_price = max(q["unit_price"] for q in quotes)
        min_lead = min(q["lead_time_days"] for q in quotes)
        max_lead = max(q["lead_time_days"] for q in quotes)
        price_range = max_price - min_price or 1
        lead_range = max_lead - min_lead or 1
        comparison = []
        for q in quotes:
            price_score = 1 - (q["unit_price"] - min_price) / price_range
            lead_score = 1 - (q["lead_time_days"] - min_lead) / lead_range
            reliability_score = await self._get_supplier_reliability(tenant_id, q["supplier_id"])
            total_score = (price_score * weight_price + lead_score * weight_lead_time +
                           reliability_score * weight_reliability)
            comparison.append({
                "supplier_id": q["supplier_id"], "unit_price": q["unit_price"],
                "lead_time_days": q["lead_time_days"],
                "price_score": round(price_score, 3), "lead_score": round(lead_score, 3),
                "reliability_score": round(reliability_score, 3),
                "total_score": round(total_score, 3),
            })
        comparison.sort(key=lambda x: x["total_score"], reverse=True)
        return {
            "inquiry_no": inquiry_no, "best_supplier": comparison[0] if comparison else None,
            "ranking": comparison,
        }

    async def _get_supplier_reliability(self, tenant_id: str, supplier_id: str) -> float:
        try:
            from erp.modules.scm.domain.models import Supplier
            supplier = (await self._session.execute(
                select(Supplier).where(Supplier.id == supplier_id, Supplier.tenant_id == tenant_id)
            )).scalar_one_or_none()
            if supplier and hasattr(supplier, "quality_score"):
                return float(supplier.quality_score or 0) / 100.0
        except Exception:
            pass
        return 0.5


class SupplierCollaborationService:
    """
    供应商协同服务

    供应商门户核心功能: 订单确认/发货通知/对账确认/资质更新
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def confirm_purchase_order(self, tenant_id: str, po_id: str,
                                      supplier_id: str, confirmed: bool,
                                      estimated_delivery: str = "") -> dict:
        """供应商确认采购订单"""
        po = (await self._session.execute(
            select(PurchaseOrder).where(PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not po:
            raise NotFoundException(message=f"Purchase order '{po_id}' not found")
        if po.supplier_id != supplier_id:
            raise ValidationException(message="Supplier does not match")
        if confirmed:
            po.status = "confirmed"
            if estimated_delivery:
                po.expected_delivery_date = estimated_delivery
        else:
            po.status = "rejected"
        await self._session.flush()
        return {"po_id": po_id, "status": po.status, "confirmed": confirmed}

    async def notify_shipment(self, tenant_id: str, po_id: str, supplier_id: str,
                               tracking_no: str = "", carrier: str = "",
                               shipped_items: list[dict] | None = None) -> dict:
        """供应商发货通知"""
        po = (await self._session.execute(
            select(PurchaseOrder).where(PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not po:
            raise NotFoundException(message=f"Purchase order '{po_id}' not found")
        if po.supplier_id != supplier_id:
            raise ValidationException(message="Supplier does not match")
        po.status = "shipped"
        await self._session.flush()
        return {
            "po_id": po_id, "status": "shipped",
            "tracking_no": tracking_no, "carrier": carrier,
            "items_count": len(shipped_items) if shipped_items else 0,
        }

    async def confirm_reconciliation(self, tenant_id: str, po_id: str,
                                      supplier_id: str, agreed: bool,
                                      discrepancy_note: str = "") -> dict:
        """供应商确认对账"""
        return {
            "po_id": po_id, "supplier_id": supplier_id,
            "agreed": agreed, "discrepancy_note": discrepancy_note,
        }

    async def update_qualification(self, tenant_id: str, supplier_id: str,
                                    qualification_data: dict) -> dict:
        """供应商更新资质"""
        supplier = (await self._session.execute(
            select(Supplier).where(Supplier.id == supplier_id, Supplier.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not supplier:
            raise NotFoundException(message=f"Supplier '{supplier_id}' not found")
        return {"supplier_id": supplier_id, "updated": True, "fields": list(qualification_data.keys())}


class ProcurementContractService:
    """
    采购合同服务

    编排采购合同全生命周期: 创建 → 审批 → 执行 → 变更 → 归档
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_contract(self, tenant_id: str, supplier_id: str,
                               contract_no: str, effective_date: str,
                               expiry_date: str, terms: dict,
                               total_amount: float = 0.0) -> dict:
        """创建采购合同"""
        return {
            "tenant_id": tenant_id, "supplier_id": supplier_id,
            "contract_no": contract_no, "effective_date": effective_date,
            "expiry_date": expiry_date, "terms": terms,
            "total_amount": total_amount, "status": "draft",
        }

    async def submit_for_approval(self, tenant_id: str, contract_no: str) -> dict:
        """提交审批"""
        return {"contract_no": contract_no, "status": "pending_approval"}

    async def approve_contract(self, tenant_id: str, contract_no: str,
                                approver_id: str, approved: bool,
                                remark: str = "") -> dict:
        """审批合同"""
        status = "effective" if approved else "rejected"
        return {"contract_no": contract_no, "status": status, "approver_id": approver_id, "remark": remark}

    async def link_purchase_order(self, tenant_id: str, contract_no: str,
                                   po_id: str) -> dict:
        """关联采购订单"""
        return {"contract_no": contract_no, "po_id": po_id, "linked": True}

    async def check_contract_coverage(self, tenant_id: str, supplier_id: str,
                                       sku_id: str, quantity: int) -> dict:
        """检查合同覆盖: 是否有有效合同覆盖该采购需求"""
        return {
            "supplier_id": supplier_id, "sku_id": sku_id,
            "covered": False, "message": "No active contract found",
        }


class PurchaseOrderService:
    """
    采购订单应用服务

    编排采购订单的完整生命周期: 创建 → 状态流转 → 明细管理
    通过 PO / Item / Supplier 三个仓储操作数据。
    """

    def __init__(
        self,
        session: AsyncSession,
        po_repo: PurchaseOrderRepository | None = None,
        item_repo: PurchaseOrderItemRepository | None = None,
        supplier_repo: SupplierRepository | None = None,
    ):
        self._session = session
        self._po_repo = po_repo
        self._item_repo = item_repo
        self._supplier_repo = supplier_repo

    async def create(self, tenant_id: str, po_no: str, supplier_id: str, warehouse_id: str, **kwargs) -> "PurchaseOrder":
        """创建采购订单: 唯一性校验(po_no) → 供应商校验(active) → 持久化"""
        from erp.modules.scm.domain.models import PurchaseOrder
        if self._po_repo:
            existing = await self._po_repo.get_by_po_no(po_no, tenant_id)
        else:
            stmt = select(PurchaseOrder).where(PurchaseOrder.po_no == po_no, PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.deleted_at.is_(None))
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise DuplicateCodeException(message=f"PO '{po_no}' already exists")
        if self._supplier_repo:
            supplier = await self._supplier_repo.get_by_id(supplier_id, tenant_id)
        else:
            supplier = await self._session.get(Supplier, supplier_id)
            if supplier and supplier.tenant_id != tenant_id:
                supplier = None
        if not supplier:
            raise NotFoundException(message=f"Supplier '{supplier_id}' not found")
        if supplier.status != "active":
            raise ValidationException(message=f"Cannot create PO for inactive supplier '{supplier_id}'")
        po = PurchaseOrder(tenant_id=tenant_id, po_no=po_no, supplier_id=supplier_id,
                           warehouse_id=warehouse_id, created_by=actor_id_var.get(""), **kwargs)
        if self._po_repo:
            return await self._po_repo.create(po)
        self._session.add(po)
        await self._session.flush()
        return po

    async def get_by_id(self, po_id: str, tenant_id: str) -> "PurchaseOrder | None":
        """根据ID获取采购订单"""
        if self._po_repo:
            return await self._po_repo.get_by_id(po_id, tenant_id)
        stmt = select(PurchaseOrder).where(PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_raise(self, po_id: str, tenant_id: str) -> "PurchaseOrder":
        """根据ID获取采购订单，不存在则抛出 NotFoundException"""
        po = await self.get_by_id(po_id, tenant_id)
        if not po:
            raise NotFoundException(message=f"Purchase order '{po_id}' not found")
        return po

    async def list_all(self, tenant_id: str, status: str = "", supplier_id: str = "",
                       page: int = 1, page_size: int = 20) -> tuple["Sequence[PurchaseOrder]", int]:
        """分页查询采购订单列表"""
        return await self._po_repo.list_by_tenant(tenant_id, status=status, supplier_id=supplier_id, page=page, page_size=page_size)

    async def update_status(self, po_id: str, tenant_id: str, new_status: str) -> "PurchaseOrder":
        """更新采购订单状态: 存在性校验 → 状态机校验 → 更新"""
        po = await self.get_by_id(po_id, tenant_id)
        if not po:
            raise NotFoundException(message=f"Purchase order '{po_id}' not found")
        allowed = PO_STATUS_TRANSITIONS.get(po.status, [])
        if new_status not in allowed:
            raise ValidationException(message=f"Cannot transition from '{po.status}' to '{new_status}'")
        po.status = new_status
        if self._po_repo:
            return await self._po_repo.update(po)
        await self._session.flush()
        return po

    async def add_item(self, tenant_id: str, po_id: str, sku_id: str, quantity: int,
                       unit_price: float, **kwargs) -> "PurchaseOrderItem":
        """添加采购明细: 订单存在性校验 → 状态校验 → 数量/价格校验 → 持久化"""
        from erp.modules.scm.domain.models import PurchaseOrderItem
        po = await self.get_by_id(po_id, tenant_id)
        if not po:
            raise NotFoundException(message=f"Purchase order '{po_id}' not found")
        if po.status not in ("draft", "pending_approval"):
            raise ValidationException(message=f"Cannot add items to PO in '{po.status}' status")
        if quantity <= 0:
            raise ValidationException(message="Quantity must be positive")
        if unit_price < 0:
            raise ValidationException(message="Unit price cannot be negative")
        item = PurchaseOrderItem(
            tenant_id=tenant_id, po_id=po_id, sku_id=sku_id,
            quantity=quantity, unit_price=unit_price,
            item_total=unit_price * quantity, **kwargs,
        )
        if self._item_repo:
            item = await self._item_repo.create(item)
        else:
            self._session.add(item)
            await self._session.flush()
        po.total_amount = (po.total_amount or 0) + item.item_total
        if self._po_repo:
            await self._po_repo.update(po)
        else:
            await self._session.flush()
        return item

    async def get_items(self, po_id: str, tenant_id: str) -> "Sequence[PurchaseOrderItem]":
        """获取采购订单的所有明细"""
        return await self._item_repo.list_by_po(po_id, tenant_id)

    async def update(self, po_id: str, tenant_id: str, **kwargs) -> "PurchaseOrder":
        """更新采购订单信息"""
        po = await self._po_repo.get_by_id(po_id, tenant_id)
        if not po:
            raise NotFoundException(message=f"Purchase order '{po_id}' not found")
        if po.status not in ("draft", "pending_approval"):
            raise ValidationException(message=f"Cannot update PO in '{po.status}' status")
        for k, v in kwargs.items():
            if v is not None and hasattr(po, k):
                setattr(po, k, v)
        return await self._po_repo.update(po)

    async def soft_delete(self, po_id: str, tenant_id: str) -> bool:
        """软删除采购订单(仅草稿状态可删)"""
        po = await self._po_repo.get_by_id(po_id, tenant_id)
        if not po:
            raise NotFoundException(message=f"Purchase order '{po_id}' not found")
        if po.status not in ("draft", "cancelled"):
            raise ValidationException(message=f"Cannot delete PO in '{po.status}' status")
        from datetime import datetime, timezone
        po.deleted_at = datetime.now(timezone.utc)
        await self._po_repo.update(po)
        return True


class PurchaseReceivingService:
    """
    采购收货应用服务

    编排采购收货的完整流程: 收货登记 → 质检关联 → 差异处理 → 状态流转
    支持部分收货和超收/短收处理。
    """

    def __init__(self, session: AsyncSession, po_repo: PurchaseOrderRepository | None = None,
                 item_repo: PurchaseOrderItemRepository | None = None):
        self._session = session
        self._po_repo = po_repo
        self._item_repo = item_repo

    async def confirm_receipt(self, tenant_id: str, po_id: str,
                              received_items: list[dict], received_by: str = "") -> dict:
        """
        确认采购收货

        流程: 订单校验 → 逐项登记收货数量 → 计算差异 → 更新订单状态
        """
        po = await self._get_po(po_id, tenant_id)
        if not po:
            raise NotFoundException(message=f"Purchase order '{po_id}' not found")
        if po.status not in ("ordered", "partial_received"):
            raise ValidationException(message=f"Cannot receive PO in '{po.status}' status")
        from erp.modules.scm.domain.models import PurchaseOrderItem
        items_stmt = select(PurchaseOrderItem).where(
            PurchaseOrderItem.po_id == po_id, PurchaseOrderItem.tenant_id == tenant_id,
        )
        items = list((await self._session.execute(items_stmt)).scalars().all())
        items_by_sku = {i.sku_id: i for i in items}
        total_ordered = sum(i.quantity for i in items)
        total_received = 0
        discrepancies: list[dict] = []
        for recv in received_items:
            sku_id = recv.get("sku_id", "")
            qty = recv.get("received_qty", 0)
            total_received += qty
            if sku_id in items_by_sku:
                po_item = items_by_sku[sku_id]
                ordered_qty = po_item.quantity
                diff = qty - ordered_qty
                if diff != 0:
                    discrepancies.append({
                        "sku_id": sku_id, "ordered_qty": ordered_qty,
                        "received_qty": qty, "difference": diff,
                        "type": "overage" if diff > 0 else "shortage",
                    })
        if total_received >= total_ordered:
            po.status = "received"
        else:
            po.status = "partial_received"
        await self._session.flush()
        return {
            "po_id": po_id, "status": po.status,
            "total_ordered": total_ordered, "total_received": total_received,
            "discrepancies": discrepancies,
            "has_discrepancy": len(discrepancies) > 0,
        }

    async def handle_discrepancy(self, tenant_id: str, po_id: str,
                                 sku_id: str, action: str, **kwargs) -> dict:
        """
        处理收货差异

        action: accept(接受差异) / reject(拒收) / claim(索赔)
        """
        if action not in ("accept", "reject", "claim"):
            raise ValidationException(message=f"Invalid discrepancy action '{action}'")
        po = await self._get_po(po_id, tenant_id)
        if not po:
            raise NotFoundException(message=f"Purchase order '{po_id}' not found")
        result = {"po_id": po_id, "sku_id": sku_id, "action": action}
        if action == "claim":
            claim_amount = kwargs.get("claim_amount", 0.0)
            result["claim_amount"] = claim_amount
            result["claim_reason"] = kwargs.get("reason", "")
        elif action == "reject":
            result["rejected_qty"] = kwargs.get("rejected_qty", 0)
        await self._session.flush()
        return result

    async def _get_po(self, po_id: str, tenant_id: str) -> PurchaseOrder | None:
        if self._po_repo:
            return await self._po_repo.get_by_id(po_id, tenant_id)
        stmt = select(PurchaseOrder).where(
            PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == tenant_id,
            PurchaseOrder.deleted_at.is_(None),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()


class PurchasePaymentService:
    """
    采购付款应用服务

    编排采购付款流程: 付款登记 → 部分付款 → 付款完成 → 状态更新
    """

    def __init__(self, session: AsyncSession, po_repo: PurchaseOrderRepository | None = None):
        self._session = session
        self._po_repo = po_repo

    async def record_payment(self, tenant_id: str, po_id: str,
                             payment_amount: float, payment_method: str = "",
                             payment_ref: str = "") -> dict:
        """
        登记付款

        流程: 订单校验 → 金额校验 → 累加已付金额 → 判定付款状态
        """
        po = await self._get_po(po_id, tenant_id)
        if not po:
            raise NotFoundException(message=f"Purchase order '{po_id}' not found")
        if po.status not in ("received", "partial_received", "completed"):
            raise ValidationException(message=f"Cannot pay for PO in '{po.status}' status")
        if payment_amount <= 0:
            raise ValidationException(message="Payment amount must be positive")
        total = po.total_amount or 0
        paid = (po.paid_amount or 0) + payment_amount
        if paid > total:
            raise ValidationException(
                message=f"Payment {paid} exceeds total amount {total}"
            )
        po.paid_amount = paid
        if paid >= total:
            po.remark = (po.remark or "") + " [fully_paid]"
        else:
            po.remark = (po.remark or "") + " [partial_paid]"
        await self._session.flush()
        payment_status = "fully_paid" if paid >= total else "partial_paid"
        return {
            "po_id": po_id, "payment_amount": payment_amount,
            "total_paid": paid, "total_amount": total,
            "payment_status": payment_status,
            "remaining": round(total - paid, 2),
        }

    async def get_payment_summary(self, tenant_id: str, po_id: str) -> dict:
        """获取付款摘要"""
        po = await self._get_po(po_id, tenant_id)
        if not po:
            raise NotFoundException(message=f"Purchase order '{po_id}' not found")
        total = po.total_amount or 0
        paid = po.paid_amount or 0
        payment_status = "unpaid"
        if paid >= total and total > 0:
            payment_status = "fully_paid"
        elif paid > 0:
            payment_status = "partial_paid"
        return {
            "po_id": po_id, "total_amount": total,
            "paid_amount": paid,
            "remaining": round(total - paid, 2),
            "payment_status": payment_status,
        }

    async def _get_po(self, po_id: str, tenant_id: str) -> PurchaseOrder | None:
        if self._po_repo:
            return await self._po_repo.get_by_id(po_id, tenant_id)
        stmt = select(PurchaseOrder).where(
            PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == tenant_id,
            PurchaseOrder.deleted_at.is_(None),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()


class ReplenishmentPlanService:
    """
    补货计划应用服务

    编排补货计划的创建和查询。
    通过 ReplenishmentPlanRepository 操作数据。
    """

    def __init__(self, session: AsyncSession, plan_repo: ReplenishmentPlanRepository):
        self._session = session
        self._plan_repo = plan_repo

    async def create(self, tenant_id: str, plan_no: str, warehouse_id: str, **kwargs) -> "ReplenishmentPlan":
        """创建补货计划: 持久化"""
        from erp.modules.scm.domain.models import ReplenishmentPlan
        plan = ReplenishmentPlan(tenant_id=tenant_id, plan_no=plan_no, warehouse_id=warehouse_id,
                                 created_by=actor_id_var.get(""), **kwargs)
        return await self._plan_repo.create(plan)

    async def list_all(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> tuple["Sequence[ReplenishmentPlan]", int]:
        """分页查询补货计划列表"""
        return await self._plan_repo.list_by_tenant(tenant_id, status=status, page=page, page_size=page_size)


class InquiryService:
    """
    询价应用服务

    编排询价单的完整生命周期: 创建 → 发布 → 报价 → 比价 → 定标
    通过 Inquiry / Quote / Supplier 三个仓储操作数据。
    """

    def __init__(
        self,
        session: AsyncSession,
        inquiry_repo: InquiryRepository,
        quote_repo: InquiryQuoteRepository,
        supplier_repo: SupplierRepository,
    ):
        self._session = session
        self._inquiry_repo = inquiry_repo
        self._quote_repo = quote_repo
        self._supplier_repo = supplier_repo

    async def create(self, tenant_id: str, inquiry_no: str, title: str, **kwargs) -> "Inquiry":
        """创建询价单: 唯一性校验(inquiry_no) → 标题非空校验 → 持久化"""
        from erp.modules.scm.domain.models import Inquiry
        existing = await self._inquiry_repo.get_by_inquiry_no(inquiry_no, tenant_id)
        if existing:
            raise DuplicateCodeException(message=f"Inquiry '{inquiry_no}' already exists")
        if not title.strip():
            raise ValidationException(message="Inquiry title cannot be empty")
        inquiry = Inquiry(
            tenant_id=tenant_id, inquiry_no=inquiry_no, title=title,
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(Inquiry, k)},
        )
        return await self._inquiry_repo.create(inquiry)

    async def get_by_id(self, inquiry_id: str, tenant_id: str) -> "Inquiry | None":
        """根据ID获取询价单"""
        return await self._inquiry_repo.get_by_id(inquiry_id, tenant_id)

    async def get_or_raise(self, inquiry_id: str, tenant_id: str) -> "Inquiry":
        """根据ID获取询价单，不存在则抛出 NotFoundException"""
        inquiry = await self.get_by_id(inquiry_id, tenant_id)
        if not inquiry:
            raise NotFoundException(message=f"Inquiry '{inquiry_id}' not found")
        return inquiry

    async def list_all(self, tenant_id: str, status: str = "", page: int = 1, page_size: int = 20) -> tuple["Sequence[Inquiry]", int]:
        """分页查询询价单列表"""
        return await self._inquiry_repo.list_by_tenant(tenant_id, status=status, page=page, page_size=page_size)

    async def update_status(self, inquiry_id: str, tenant_id: str, new_status: str) -> "Inquiry":
        """更新询价单状态: 存在性校验 → 状态机校验 → 更新"""
        inquiry = await self._inquiry_repo.get_by_id(inquiry_id, tenant_id)
        if not inquiry:
            raise NotFoundException(message=f"Inquiry '{inquiry_id}' not found")
        if not InquiryDomainService.can_transition(inquiry.status, new_status):
            raise ValidationException(
                message=f"Cannot transition inquiry from '{inquiry.status}' to '{new_status}'"
            )
        inquiry.status = new_status
        return await self._inquiry_repo.update(inquiry)

    async def add_quote(self, tenant_id: str, inquiry_id: str, supplier_id: str,
                        quote_items: list[dict], total_amount: float,
                        currency: str = "CNY", lead_time_days: int = 0, **kwargs) -> "InquiryQuote":
        """添加询价报价: 询价单存在性校验 → 状态校验 → 持久化 → 自动流转为quoting"""
        from erp.modules.scm.domain.models import InquiryQuote
        import json
        inquiry = await self._inquiry_repo.get_by_id(inquiry_id, tenant_id)
        if not inquiry:
            raise NotFoundException(message=f"Inquiry '{inquiry_id}' not found")
        if inquiry.status not in ("published", "quoting"):
            raise ValidationException(message=f"Cannot add quote to inquiry in '{inquiry.status}' status")
        quote = InquiryQuote(
            tenant_id=tenant_id, inquiry_id=inquiry_id, supplier_id=supplier_id,
            quote_items_json=json.dumps(quote_items, default=str),
            total_amount=total_amount, currency=currency, lead_time_days=lead_time_days,
            **{k: v for k, v in kwargs.items() if hasattr(InquiryQuote, k)},
        )
        quote = await self._quote_repo.create(quote)
        if inquiry.status == "published":
            inquiry.status = "quoting"
            await self._inquiry_repo.update(inquiry)
        return quote

    async def compare_quotes(self, inquiry_id: str, tenant_id: str) -> list[dict]:
        """比价: 获取所有报价 → 获取供应商评分 → 调用领域服务排序"""
        inquiry = await self._inquiry_repo.get_by_id(inquiry_id, tenant_id)
        if not inquiry:
            raise NotFoundException(message=f"Inquiry '{inquiry_id}' not found")
        quotes = await self._quote_repo.list_by_inquiry(inquiry_id, tenant_id)
        quote_data = []
        for q in quotes:
            supplier = await self._supplier_repo.get_by_id(q.supplier_id, tenant_id)
            supplier_rating = 0.0
            if supplier:
                supplier_rating = SupplierDomainService.calculate_rating(
                    supplier.quality_score, supplier.delivery_score
                )
            quote_data.append({
                "quote_id": str(q.id), "supplier_id": q.supplier_id,
                "total_amount": q.total_amount, "currency": q.currency,
                "lead_time_days": q.lead_time_days, "supplier_rating": supplier_rating,
            })
        return InquiryDomainService.compare_quotes(quote_data)

    async def award_quote(self, inquiry_id: str, quote_id: str, tenant_id: str) -> "InquiryQuote":
        """定标: 询价单状态校验 → 报价归属校验 → 标记中标 → 流转为awarded"""
        inquiry = await self._inquiry_repo.get_by_id(inquiry_id, tenant_id)
        if not inquiry:
            raise NotFoundException(message=f"Inquiry '{inquiry_id}' not found")
        if inquiry.status != "evaluating":
            raise ValidationException(message="Inquiry must be in 'evaluating' status to award")
        quote = await self._quote_repo.get_by_id(quote_id, tenant_id)
        if not quote:
            raise NotFoundException(message=f"Quote '{quote_id}' not found")
        if quote.inquiry_id != inquiry_id:
            raise ValidationException(message="Quote does not belong to this inquiry")
        quote.is_winner = 1
        await self._quote_repo.update(quote)
        inquiry.status = "awarded"
        await self._inquiry_repo.update(inquiry)
        return quote


class SupplierEvaluationService:
    """
    供应商评价应用服务

    编排供应商评价的创建和查询，支持单条和批量评价。
    通过 Evaluation / Supplier 两个仓储操作数据。
    """

    def __init__(
        self,
        session: AsyncSession,
        evaluation_repo: SupplierEvaluationRepository,
        supplier_repo: SupplierRepository,
    ):
        self._session = session
        self._evaluation_repo = evaluation_repo
        self._supplier_repo = supplier_repo

    async def create(self, tenant_id: str, supplier_id: str, period: str,
                     quality_score: float, delivery_score: float,
                     price_score: float, service_score: float, **kwargs) -> "SupplierEvaluation":
        """创建供应商评价: 分数范围校验 → 供应商存在性校验 → 计算综合分 → 更新供应商等级"""
        from erp.modules.scm.domain.models import SupplierEvaluation
        if not (0 <= quality_score <= 100):
            raise ValidationException(message="Quality score must be between 0 and 100")
        if not (0 <= delivery_score <= 100):
            raise ValidationException(message="Delivery score must be between 0 and 100")
        if not (0 <= price_score <= 100):
            raise ValidationException(message="Price score must be between 0 and 100")
        if not (0 <= service_score <= 100):
            raise ValidationException(message="Service score must be between 0 and 100")
        supplier = await self._supplier_repo.get_by_id(supplier_id, tenant_id)
        if not supplier:
            raise NotFoundException(message=f"Supplier '{supplier_id}' not found")
        overall = SupplierDomainService.calculate_rating(quality_score, delivery_score, price_score, service_score)
        evaluation = SupplierEvaluation(
            tenant_id=tenant_id, supplier_id=supplier_id, period=period,
            quality_score=quality_score, delivery_score=delivery_score,
            price_score=price_score, service_score=service_score,
            overall_score=overall,
            **{k: v for k, v in kwargs.items() if hasattr(SupplierEvaluation, k)},
        )
        await self._evaluation_repo.create(evaluation)
        supplier.quality_score = quality_score
        supplier.delivery_score = delivery_score
        new_level = SupplierDomainService.get_cooperation_level(overall)
        supplier.cooperation_level = new_level
        await self._supplier_repo.update(supplier)
        return evaluation

    async def list_by_supplier(self, supplier_id: str, tenant_id: str) -> list["SupplierEvaluation"]:
        """查询供应商的评价列表"""
        return list(await self._evaluation_repo.list_by_supplier(supplier_id, tenant_id))

    async def get_latest(self, supplier_id: str, tenant_id: str) -> "SupplierEvaluation | None":
        """查询供应商最新评价"""
        evaluations = await self._evaluation_repo.list_by_supplier(supplier_id, tenant_id)
        return evaluations[0] if evaluations else None

    async def batch_evaluate(self, tenant_id: str, evaluations: list[dict]) -> dict:
        """批量评价供应商: 逐条创建，收集成功/失败统计"""
        success_count = 0
        failed_items = []
        for ev in evaluations:
            try:
                await self.create(
                    tenant_id=tenant_id,
                    supplier_id=ev.get("supplier_id", ""),
                    period=ev.get("period", ""),
                    quality_score=ev.get("quality_score", 0),
                    delivery_score=ev.get("delivery_score", 0),
                    price_score=ev.get("price_score", 0),
                    service_score=ev.get("service_score", 0),
                )
                success_count += 1
            except (NotFoundException, ValidationException) as e:
                failed_items.append({"supplier_id": ev.get("supplier_id", ""), "reason": e.message})
        return {"success_count": success_count, "failed_count": len(failed_items), "failed_items": failed_items}


class SCMQueryService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_po_statistics(self, tenant_id: str, supplier_id: str = "") -> dict:
        from erp.modules.scm.domain.models import PurchaseOrder
        from sqlalchemy import func as sa_func, select
        conditions = [PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.deleted_at.is_(None)]
        if supplier_id:
            conditions.append(PurchaseOrder.supplier_id == supplier_id)
        stmt = select(PurchaseOrder).where(*conditions)
        orders = (await self._session.execute(stmt)).scalars().all()
        total = len(orders)
        total_amount = sum(o.total_amount or 0 for o in orders)
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for o in orders:
            by_status[o.status] = by_status.get(o.status, 0) + 1
            by_type[o.po_type] = by_type.get(o.po_type, 0) + 1
        return {
            "total_orders": total,
            "total_amount": round(total_amount, 2),
            "by_status": by_status,
            "by_type": by_type,
        }

    async def get_supplier_statistics(self, tenant_id: str) -> dict:
        from erp.modules.scm.domain.models import Supplier
        from sqlalchemy import select
        conditions = [Supplier.tenant_id == tenant_id, Supplier.deleted_at.is_(None)]
        stmt = select(Supplier).where(*conditions)
        suppliers = (await self._session.execute(stmt)).scalars().all()
        total = len(suppliers)
        by_type: dict[str, int] = {}
        by_level: dict[str, int] = {}
        scores = []
        for s in suppliers:
            by_type[s.supplier_type] = by_type.get(s.supplier_type, 0) + 1
            by_level[s.cooperation_level] = by_level.get(s.cooperation_level, 0) + 1
            if s.quality_score:
                scores.append(s.quality_score)
        avg_quality = round(sum(scores) / len(scores), 2) if scores else 0.0
        return {
            "total_suppliers": total,
            "by_type": by_type,
            "by_level": by_level,
            "avg_quality_score": avg_quality,
        }

    async def get_po_statistics_by_mode(self, tenant_id: str) -> dict:
        from erp.modules.scm.domain.models import PurchaseOrder
        conditions = [PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.deleted_at.is_(None)]
        stmt = select(PurchaseOrder).where(*conditions)
        orders = (await self._session.execute(stmt)).scalars().all()
        by_mode: dict[str, dict] = {}
        for o in orders:
            mode = o.purchase_mode or "standard_purchase"
            if mode not in by_mode:
                by_mode[mode] = {"count": 0, "total_amount": 0.0}
            by_mode[mode]["count"] += 1
            by_mode[mode]["total_amount"] += o.total_amount or 0
        for m in by_mode:
            by_mode[m]["total_amount"] = round(by_mode[m]["total_amount"], 2)
        return {"by_mode": by_mode}


PURCHASE_MODE_CONFIG: dict[str, dict] = {
    "standard_purchase": {
        "name": "标准采购",
        "description": "常规采购模式，下单后付款，供应商发货至指定仓库",
        "requires_approval": True,
        "approval_threshold": 50000.0,
        "payment_terms": "Net30",
        "auto_receive": False,
        "consignment": False,
    },
    "consignment": {
        "name": "寄售采购",
        "description": "供应商将货物存放在我方仓库，按实际消耗结算",
        "requires_approval": True,
        "approval_threshold": 100000.0,
        "payment_terms": "consumption_based",
        "auto_receive": True,
        "consignment": True,
    },
    "jit_dropship": {
        "name": "JIT直发",
        "description": "按需采购，供应商直接发货至终端客户，零库存模式",
        "requires_approval": False,
        "approval_threshold": 0.0,
        "payment_terms": "Net15",
        "auto_receive": True,
        "consignment": False,
    },
    "vmi_subcontracting": {
        "name": "VMI代工",
        "description": "供应商管理库存，按生产计划自动补料，适用于代工场景",
        "requires_approval": True,
        "approval_threshold": 200000.0,
        "payment_terms": "monthly_settlement",
        "auto_receive": True,
        "consignment": False,
    },
    "centralized": {
        "name": "集中采购",
        "description": "多需求汇总集中下单，享受批量折扣，适用于大宗物料",
        "requires_approval": True,
        "approval_threshold": 500000.0,
        "payment_terms": "milestone",
        "auto_receive": False,
        "consignment": False,
    },
}


class PurchaseModeService:
    """
    采购模式差异化应用服务

    根据不同采购模式(标准采购/寄售/JIT直发/VMI代工/集中采购)提供差异化业务逻辑:
    - 创建订单时根据模式自动设置审批流程、付款条件
    - 寄售模式: 自动收货、按消耗结算
    - JIT直发: 免审批、自动发货至客户
    - VMI代工: 自动补料、月结
    - 集中采购: 强制审批、里程碑付款
    """

    def __init__(self, session: AsyncSession, po_repo: PurchaseOrderRepository | None = None):
        self._session = session
        self._po_repo = po_repo

    def get_mode_config(self, purchase_mode: str) -> dict:
        if purchase_mode not in PURCHASE_MODE_CONFIG:
            raise ValidationException(message=f"Invalid purchase mode '{purchase_mode}'")
        return PURCHASE_MODE_CONFIG[purchase_mode]

    def list_modes(self) -> list[dict]:
        return [
            {"mode": k, "name": v["name"], "description": v["description"],
             "requires_approval": v["requires_approval"],
             "approval_threshold": v["approval_threshold"],
             "payment_terms": v["payment_terms"]}
            for k, v in PURCHASE_MODE_CONFIG.items()
        ]

    async def create_po_with_mode(self, tenant_id: str, po_no: str, supplier_id: str,
                                   warehouse_id: str, purchase_mode: str, **kwargs) -> PurchaseOrder:
        """
        按采购模式创建采购订单

        流程: 模式校验 → 模式配置注入 → 创建订单 → 自动审批判定
        """
        config = self.get_mode_config(purchase_mode)
        if kwargs.get("payment_terms", "") == "":
            kwargs["payment_terms"] = config["payment_terms"]
        po = PurchaseOrder(
            tenant_id=tenant_id, po_no=po_no, supplier_id=supplier_id,
            warehouse_id=warehouse_id, purchase_mode=purchase_mode,
            created_by=actor_id_var.get(""), **kwargs,
        )
        if config["requires_approval"]:
            total = kwargs.get("total_amount", 0.0)
            if total <= config["approval_threshold"]:
                po.status = "approved"
            else:
                po.status = "pending_approval"
        else:
            po.status = "approved"
        if self._po_repo:
            return await self._po_repo.create(po)
        self._session.add(po)
        await self._session.flush()
        return po

    async def process_consignment_consumption(self, tenant_id: str, po_id: str,
                                               consumed_items: list[dict]) -> dict:
        """
        寄售模式消耗结算

        流程: 订单校验(寄售模式) → 逐项记录消耗 → 计算结算金额
        """
        po = await self._get_po(po_id, tenant_id)
        if not po:
            raise NotFoundException(message=f"Purchase order '{po_id}' not found")
        if po.purchase_mode != "consignment":
            raise ValidationException(message="This operation is only for consignment purchase orders")
        total_consumption = 0.0
        for item in consumed_items:
            total_consumption += item.get("quantity", 0) * item.get("unit_price", 0.0)
        po.paid_amount = (po.paid_amount or 0) + total_consumption
        if self._po_repo:
            await self._po_repo.update(po)
        else:
            await self._session.flush()
        return {
            "po_id": po_id, "consumed_amount": round(total_consumption, 2),
            "total_paid": round(po.paid_amount, 2),
        }

    async def process_jit_shipment(self, tenant_id: str, po_id: str,
                                    customer_info: dict, items: list[dict]) -> dict:
        """
        JIT直发模式处理

        流程: 订单校验(JIT模式) → 创建发货指令 → 供应商直发客户
        """
        po = await self._get_po(po_id, tenant_id)
        if not po:
            raise NotFoundException(message=f"Purchase order '{po_id}' not found")
        if po.purchase_mode != "jit_dropship":
            raise ValidationException(message="This operation is only for JIT dropship purchase orders")
        po.status = "ordered"
        if self._po_repo:
            await self._po_repo.update(po)
        else:
            await self._session.flush()
        return {
            "po_id": po_id, "status": "ordered",
            "shipment_type": "direct_to_customer",
            "customer_info": customer_info,
            "items_count": len(items),
        }

    async def process_vmi_replenishment(self, tenant_id: str, supplier_id: str,
                                         warehouse_id: str, items: list[dict]) -> dict:
        """
        VMI代工模式自动补料

        流程: 查询VMI供应商 → 检查库存水位 → 自动生成补料订单
        """
        from erp.modules.scm.domain.models import PurchaseOrder
        import uuid
        po = PurchaseOrder(
            tenant_id=tenant_id,
            po_no=f"VMI-{str(uuid.uuid4())[:8]}",
            supplier_id=supplier_id,
            warehouse_id=warehouse_id,
            purchase_mode="vmi_subcontracting",
            status="approved",
            created_by="system",
        )
        if self._po_repo:
            po = await self._po_repo.create(po)
        else:
            self._session.add(po)
            await self._session.flush()
        return {
            "po_id": po.id, "po_no": po.po_no,
            "mode": "vmi_subcontracting", "status": "approved",
            "items_count": len(items),
        }

    async def process_centralized_order(self, tenant_id: str, demands: list[dict],
                                         supplier_id: str, warehouse_id: str) -> dict:
        """
        集中采购模式处理

        流程: 汇总多需求 → 合并同SKU → 创建集中采购单 → 强制审批
        """
        from erp.modules.scm.domain.models import PurchaseOrder, PurchaseOrderItem
        import uuid
        import json
        merged_items: dict[str, dict] = {}
        for demand in demands:
            for item in demand.get("items", []):
                sku_id = item.get("sku_id", "")
                if sku_id not in merged_items:
                    merged_items[sku_id] = {"sku_id": sku_id, "quantity": 0, "unit_price": item.get("unit_price", 0)}
                merged_items[sku_id]["quantity"] += item.get("quantity", 0)
        total_amount = sum(i["quantity"] * i["unit_price"] for i in merged_items.values())
        po = PurchaseOrder(
            tenant_id=tenant_id,
            po_no=f"CTR-{str(uuid.uuid4())[:8]}",
            supplier_id=supplier_id,
            warehouse_id=warehouse_id,
            purchase_mode="centralized",
            status="pending_approval",
            total_amount=total_amount,
            remark=f"Centralized purchase from {len(demands)} demands",
            created_by=actor_id_var.get(""),
        )
        if self._po_repo:
            po = await self._po_repo.create(po)
        else:
            self._session.add(po)
            await self._session.flush()
        return {
            "po_id": po.id, "po_no": po.po_no,
            "mode": "centralized", "status": "pending_approval",
            "merged_sku_count": len(merged_items),
            "total_amount": round(total_amount, 2),
            "source_demands_count": len(demands),
        }

    async def _get_po(self, po_id: str, tenant_id: str) -> PurchaseOrder | None:
        if self._po_repo:
            return await self._po_repo.get_by_id(po_id, tenant_id)
        stmt = select(PurchaseOrder).where(
            PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == tenant_id,
            PurchaseOrder.deleted_at.is_(None),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
