"""
跨域服务化调用客户端

设计原则:
  1. 每个域暴露自己的服务化接口(Protocol)，不直接import其他域的内部实现
  2. 跨域调用通过 DomainServiceClient 统一调度，保持领域独立性
  3. 客户端通过 AsyncSession + 目标域的 Repository 接口操作数据
  4. 所有跨域调用记录 trace_id/tenant_id/actor_id，保证可追踪
  5. 跨域调用失败时发布补偿事件，不抛出异常阻断主流程

使用方式:
  from erp.shared.integration.client import DomainServiceClient
  client = DomainServiceClient(session)
  await client.wms.reserve_inventory(tenant_id, warehouse_id, sku_id, qty)
  await client.scm.trigger_replenishment(tenant_id, sku_id, qty_needed)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from sqlalchemy import select

from erp.shared.context import actor_id_var, tenant_id_var, trace_id_var
from erp.shared.events.domain_event import DomainEvent
from erp.shared.events.publisher import get_event_publisher
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.integration")


@runtime_checkable
class WmsServicePort(Protocol):
    async def reserve_inventory(self, tenant_id: str, warehouse_id: str,
                                sku_id: str, qty: int, reference_type: str = "",
                                reference_id: str = "") -> dict[str, Any]: ...
    async def release_inventory(self, tenant_id: str, warehouse_id: str,
                                sku_id: str, qty: int, reference_type: str = "",
                                reference_id: str = "") -> dict[str, Any]: ...
    async def get_stock_available(self, tenant_id: str, warehouse_id: str,
                                  sku_id: str) -> int: ...
    async def create_inbound_order(self, tenant_id: str, warehouse_id: str,
                                   source_type: str, source_id: str,
                                   items: list[dict]) -> dict[str, Any]: ...
    async def adjust_stock(self, tenant_id: str, warehouse_id: str, sku_id: str,
                           qty_change: int, movement_type: str, reference_type: str = "",
                           reference_id: str = "") -> dict[str, Any]: ...
    async def create_stock_transfer(self, tenant_id: str, transfer_no: str,
                                    from_warehouse_id: str, to_warehouse_id: str,
                                    items: list[dict], **kwargs) -> dict[str, Any]: ...
    async def ship_stock_transfer(self, tenant_id: str, transfer_id: str) -> dict[str, Any]: ...
    async def receive_stock_transfer(self, tenant_id: str, transfer_id: str,
                                     received_items: list[dict] | None = None) -> dict[str, Any]: ...


@runtime_checkable
class ScmServicePort(Protocol):
    async def trigger_replenishment(self, tenant_id: str, sku_id: str,
                                    qty_needed: int, reason: str = "") -> dict[str, Any]: ...
    async def get_supplier_by_id(self, tenant_id: str,
                                 supplier_id: str) -> dict[str, Any] | None: ...
    async def create_purchase_order(self, tenant_id: str, supplier_id: str,
                                    warehouse_id: str, items: list[dict],
                                    **kwargs) -> dict[str, Any]: ...
    async def create_po_with_mode(self, tenant_id: str, po_no: str, supplier_id: str,
                                  warehouse_id: str, purchase_mode: str,
                                  **kwargs) -> dict[str, Any]: ...
    async def process_consignment_consumption(self, tenant_id: str, po_id: str,
                                              consumed_items: list[dict]) -> dict[str, Any]: ...
    async def process_jit_shipment(self, tenant_id: str, po_id: str,
                                   customer_info: dict, items: list[dict]) -> dict[str, Any]: ...
    async def process_vmi_replenishment(self, tenant_id: str, supplier_id: str,
                                        warehouse_id: str, items: list[dict]) -> dict[str, Any]: ...
    async def process_centralized_order(self, tenant_id: str, demands: list[dict],
                                        supplier_id: str, warehouse_id: str) -> dict[str, Any]: ...


@runtime_checkable
class OmsServicePort(Protocol):
    async def update_order_status(self, tenant_id: str, order_id: str,
                                  new_status: str, remark: str = "") -> dict[str, Any]: ...
    async def get_order_by_id(self, tenant_id: str, order_id: str) -> dict[str, Any] | None: ...
    async def evaluate_order_risk(self, tenant_id: str, order_id: str) -> dict[str, Any]: ...
    async def approve_order(self, tenant_id: str, order_id: str, approver_id: str,
                            approval_level: int = 1, remark: str = "") -> dict[str, Any]: ...
    async def reject_order(self, tenant_id: str, order_id: str, rejector_id: str,
                           reason: str = "") -> dict[str, Any]: ...


@runtime_checkable
class FmsServicePort(Protocol):
    async def create_cost_event(self, tenant_id: str, cost_type: str, amount: float,
                                currency: str = "CNY", exchange_rate: float = 1.0,
                                **kwargs) -> dict[str, Any]: ...
    async def create_settlement(self, tenant_id: str, platform: str,
                                settlement_id: str, amount: float,
                                currency: str = "CNY", **kwargs) -> dict[str, Any]: ...
    async def get_exchange_rate(self, tenant_id: str, from_currency: str,
                                to_currency: str = "CNY") -> float: ...


@runtime_checkable
class TmsServicePort(Protocol):
    async def create_shipment(self, tenant_id: str, order_id: str,
                              warehouse_id: str, provider_id: str,
                              shipping_method_id: str, **kwargs) -> dict[str, Any]: ...
    async def update_tracking(self, tenant_id: str, shipment_id: str,
                              tracking_no: str, events: list | None = None) -> dict[str, Any]: ...


@runtime_checkable
class PdmServicePort(Protocol):
    async def get_sku_by_id(self, tenant_id: str, sku_id: str) -> dict[str, Any] | None: ...
    async def update_spu_status(self, tenant_id: str, spu_id: str,
                                new_status: str) -> dict[str, Any]: ...
    async def record_product_issue(self, tenant_id: str, sku_id: str,
                                   issue_type: str, description: str,
                                   source: str = "") -> dict[str, Any]: ...


@runtime_checkable
class SomServicePort(Protocol):
    async def update_listing_price(self, tenant_id: str, listing_id: str,
                                   new_price: float) -> dict[str, Any]: ...
    async def get_listing_by_id(self, tenant_id: str,
                                listing_id: str) -> dict[str, Any] | None: ...


@runtime_checkable
class AdsServicePort(Protocol):
    async def update_campaign_budget(self, tenant_id: str, campaign_id: str,
                                     new_budget: float) -> dict[str, Any]: ...
    async def pause_campaign(self, tenant_id: str, campaign_id: str) -> dict[str, Any]: ...


@runtime_checkable
class CrmServicePort(Protocol):
    async def create_service_ticket(self, tenant_id: str, customer_id: str,
                                    ticket_type: str, subject: str,
                                    priority: str = "normal",
                                    **kwargs) -> dict[str, Any]: ...
    async def record_negative_review(self, tenant_id: str, customer_id: str,
                                     sku_id: str, rating: int,
                                     content: str = "") -> dict[str, Any]: ...


@runtime_checkable
class FbaServicePort(Protocol):
    async def trigger_replenishment(self, tenant_id: str, sku_id: str,
                                    qty_needed: int) -> dict[str, Any]: ...
    async def update_fba_inventory(self, tenant_id: str, sku_id: str,
                                   qty_change: int, qty_type: str = "qty_fulfillable") -> dict[str, Any]: ...
    async def create_exception(self, tenant_id: str, exception_no: str,
                               exception_type: str, severity: str, title: str,
                               **kwargs) -> dict[str, Any]: ...
    async def auto_detect_discrepancy(self, tenant_id: str, store_id: str,
                                      sku_id: str, expected_qty: int,
                                      actual_qty: int, **kwargs) -> dict[str, Any]: ...


@runtime_checkable
class SysServicePort(Protocol):
    async def submit_approval(self, tenant_id: str, approval_type: str,
                              business_id: str, business_type: str,
                              submitted_by: str, **kwargs) -> dict[str, Any]: ...
    async def create_risk_alert(self, tenant_id: str, alert_type: str,
                                severity: str, title: str,
                                description: str = "", **kwargs) -> dict[str, Any]: ...


@runtime_checkable
class BiServicePort(Protocol):
    async def record_metric(self, tenant_id: str, metric_code: str,
                            numeric_value: float, period_type: str = "daily",
                            **kwargs) -> dict[str, Any]: ...


@runtime_checkable
class IamServicePort(Protocol):
    async def check_permission(self, tenant_id: str, user_id: str,
                               resource: str, action: str) -> bool: ...
    async def get_user_by_id(self, tenant_id: str, user_id: str) -> dict[str, Any] | None: ...


class WmsServiceClient:
    """WMS域服务化客户端 - 通过仓储接口操作库存/入库/出库"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def reserve_inventory(self, tenant_id: str, warehouse_id: str,
                                sku_id: str, qty: int, reference_type: str = "",
                                reference_id: str = "") -> dict[str, Any]:
        from erp.modules.wms.domain.models import Inventory
        stmt = select(Inventory).where(
            Inventory.tenant_id == tenant_id,
            Inventory.warehouse_id == warehouse_id,
            Inventory.sku_id == sku_id,
        )
        inv = (await self._session.execute(stmt)).scalar_one_or_none()
        if not inv:
            logger.warning("wms_reserve_inventory_not_found", tenant_id=tenant_id,
                           warehouse_id=warehouse_id, sku_id=sku_id)
            return {"success": False, "reason": "inventory_not_found"}
        if inv.qty_available < qty:
            logger.warning("wms_reserve_insufficient_stock", tenant_id=tenant_id,
                           sku_id=sku_id, available=inv.qty_available, requested=qty)
            return {"success": False, "reason": "insufficient_stock",
                    "available": inv.qty_available, "requested": qty}
        inv.qty_reserved += qty
        inv.qty_available -= qty
        await self._session.flush()
        logger.info("wms_inventory_reserved", tenant_id=tenant_id, sku_id=sku_id,
                     qty=qty, reference_type=reference_type, reference_id=reference_id)
        return {"success": True, "qty_reserved": qty, "qty_available": inv.qty_available}

    async def release_inventory(self, tenant_id: str, warehouse_id: str,
                                sku_id: str, qty: int, reference_type: str = "",
                                reference_id: str = "") -> dict[str, Any]:
        from erp.modules.wms.domain.models import Inventory
        stmt = select(Inventory).where(
            Inventory.tenant_id == tenant_id,
            Inventory.warehouse_id == warehouse_id,
            Inventory.sku_id == sku_id,
        )
        inv = (await self._session.execute(stmt)).scalar_one_or_none()
        if not inv:
            return {"success": False, "reason": "inventory_not_found"}
        release_qty = min(qty, inv.qty_reserved)
        inv.qty_reserved -= release_qty
        inv.qty_available += release_qty
        await self._session.flush()
        logger.info("wms_inventory_released", tenant_id=tenant_id, sku_id=sku_id, qty=release_qty)
        return {"success": True, "qty_released": release_qty, "qty_available": inv.qty_available}

    async def get_stock_available(self, tenant_id: str, warehouse_id: str,
                                  sku_id: str) -> int:
        from erp.modules.wms.domain.models import Inventory
        stmt = select(Inventory).where(
            Inventory.tenant_id == tenant_id,
            Inventory.warehouse_id == warehouse_id,
            Inventory.sku_id == sku_id,
        )
        inv = (await self._session.execute(stmt)).scalar_one_or_none()
        return inv.qty_available if inv else 0

    async def create_inbound_order(self, tenant_id: str, warehouse_id: str,
                                   source_type: str, source_id: str,
                                   items: list[dict]) -> dict[str, Any]:
        from erp.modules.wms.domain.models import InboundOrder
        import json
        inbound = InboundOrder(
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            inbound_no=f"INB-{source_id[:8]}",
            inbound_type=source_type,
            source_id=source_id,
            status="pending",
            items_json=json.dumps(items, default=str),
        )
        self._session.add(inbound)
        await self._session.flush()
        logger.info("wms_inbound_created", tenant_id=tenant_id,
                     inbound_id=inbound.id, source_type=source_type, source_id=source_id)
        return {"success": True, "inbound_id": inbound.id, "inbound_no": inbound.inbound_no}

    async def adjust_stock(self, tenant_id: str, warehouse_id: str, sku_id: str,
                           qty_change: int, movement_type: str, reference_type: str = "",
                           reference_id: str = "") -> dict[str, Any]:
        from erp.modules.wms.domain.models import Inventory, StockMovement
        stmt = select(Inventory).where(
            Inventory.tenant_id == tenant_id,
            Inventory.warehouse_id == warehouse_id,
            Inventory.sku_id == sku_id,
        )
        inv = (await self._session.execute(stmt)).scalar_one_or_none()
        if not inv:
            inv = Inventory(tenant_id=tenant_id, warehouse_id=warehouse_id, sku_id=sku_id)
            self._session.add(inv)
            await self._session.flush()
        inv.qty_on_hand += qty_change
        if qty_change > 0:
            inv.qty_available += qty_change
        else:
            inv.qty_available = max(0, inv.qty_available + qty_change)
        movement = StockMovement(
            tenant_id=tenant_id, warehouse_id=warehouse_id, sku_id=sku_id,
            movement_type=movement_type, qty_change=qty_change,
            reference_type=reference_type, reference_id=reference_id,
            operator_id=actor_id_var.get(""),
        )
        self._session.add(movement)
        await self._session.flush()
        logger.info("wms_stock_adjusted", tenant_id=tenant_id, sku_id=sku_id,
                     qty_change=qty_change, movement_type=movement_type)
        return {"success": True, "qty_on_hand": inv.qty_on_hand, "qty_available": inv.qty_available}

    async def create_stock_transfer(self, tenant_id: str, transfer_no: str,
                                    from_warehouse_id: str, to_warehouse_id: str,
                                    items: list[dict], **kwargs) -> dict[str, Any]:
        from erp.modules.wms.domain.models import StockTransfer
        import json
        if from_warehouse_id == to_warehouse_id:
            return {"success": False, "reason": "source_and_target_same"}
        transfer = StockTransfer(
            tenant_id=tenant_id,
            transfer_no=transfer_no,
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id,
            items_json=json.dumps(items, default=str),
            transfer_type=kwargs.get("transfer_type", "warehouse"),
            reason=kwargs.get("reason", ""),
            created_by=actor_id_var.get(""),
        )
        self._session.add(transfer)
        await self._session.flush()
        logger.info("wms_stock_transfer_created", tenant_id=tenant_id,
                     transfer_id=transfer.id, from_wh=from_warehouse_id, to_wh=to_warehouse_id)
        return {"success": True, "transfer_id": transfer.id, "transfer_no": transfer_no}

    async def ship_stock_transfer(self, tenant_id: str, transfer_id: str) -> dict[str, Any]:
        from erp.modules.wms.domain.models import StockTransfer, Inventory, StockMovement
        import json
        from datetime import datetime, UTC
        stmt = select(StockTransfer).where(
            StockTransfer.id == transfer_id, StockTransfer.tenant_id == tenant_id,
        )
        transfer = (await self._session.execute(stmt)).scalar_one_or_none()
        if not transfer:
            return {"success": False, "reason": "transfer_not_found"}
        if transfer.status != "approved":
            return {"success": False, "reason": f"invalid_status_{transfer.status}"}
        items = json.loads(transfer.items_json or "[]")
        for item in items:
            inv_stmt = select(Inventory).where(
                Inventory.tenant_id == tenant_id,
                Inventory.warehouse_id == transfer.from_warehouse_id,
                Inventory.sku_id == item.get("sku_id", ""),
            )
            inv = (await self._session.execute(inv_stmt)).scalar_one_or_none()
            if inv:
                inv.qty_on_hand -= item.get("quantity", 0)
                inv.qty_available = max(0, inv.qty_available - item.get("quantity", 0))
                movement = StockMovement(
                    tenant_id=tenant_id, warehouse_id=transfer.from_warehouse_id,
                    sku_id=item.get("sku_id", ""), movement_type="transfer_out",
                    qty_change=-item.get("quantity", 0),
                    reference_type="stock_transfer", reference_id=transfer_id,
                    operator_id=actor_id_var.get(""),
                )
                self._session.add(movement)
        transfer.status = "in_transit"
        transfer.shipped_at = datetime.now(UTC)
        await self._session.flush()
        logger.info("wms_stock_transfer_shipped", tenant_id=tenant_id, transfer_id=transfer_id)
        return {"success": True, "transfer_id": transfer_id, "status": "in_transit"}

    async def receive_stock_transfer(self, tenant_id: str, transfer_id: str,
                                     received_items: list[dict] | None = None) -> dict[str, Any]:
        from erp.modules.wms.domain.models import StockTransfer, Inventory, StockMovement
        import json
        from datetime import datetime, UTC
        stmt = select(StockTransfer).where(
            StockTransfer.id == transfer_id, StockTransfer.tenant_id == tenant_id,
        )
        transfer = (await self._session.execute(stmt)).scalar_one_or_none()
        if not transfer:
            return {"success": False, "reason": "transfer_not_found"}
        if transfer.status != "in_transit":
            return {"success": False, "reason": f"invalid_status_{transfer.status}"}
        items = received_items or json.loads(transfer.items_json or "[]")
        for item in items:
            inv_stmt = select(Inventory).where(
                Inventory.tenant_id == tenant_id,
                Inventory.warehouse_id == transfer.to_warehouse_id,
                Inventory.sku_id == item.get("sku_id", ""),
            )
            inv = (await self._session.execute(inv_stmt)).scalar_one_or_none()
            if not inv:
                inv = Inventory(tenant_id=tenant_id, warehouse_id=transfer.to_warehouse_id,
                                sku_id=item.get("sku_id", ""))
                self._session.add(inv)
                await self._session.flush()
            qty = item.get("quantity", 0)
            inv.qty_on_hand += qty
            inv.qty_available += qty
            movement = StockMovement(
                tenant_id=tenant_id, warehouse_id=transfer.to_warehouse_id,
                sku_id=item.get("sku_id", ""), movement_type="transfer_in",
                qty_change=qty, reference_type="stock_transfer", reference_id=transfer_id,
                operator_id=actor_id_var.get(""),
            )
            self._session.add(movement)
        transfer.status = "completed"
        transfer.received_at = datetime.now(UTC)
        await self._session.flush()
        logger.info("wms_stock_transfer_received", tenant_id=tenant_id, transfer_id=transfer_id)
        return {"success": True, "transfer_id": transfer_id, "status": "completed"}


class ScmServiceClient:
    """SCM域服务化客户端 - 通过仓储接口操作采购/补货"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def trigger_replenishment(self, tenant_id: str, sku_id: str,
                                    qty_needed: int, reason: str = "") -> dict[str, Any]:
        from erp.modules.scm.domain.models import ReplenishmentPlan
        import uuid
        import json
        plan = ReplenishmentPlan(
            tenant_id=tenant_id,
            plan_no=f"RP-{str(uuid.uuid4())[:8]}",
            plan_type="auto" if reason.startswith("low_stock") else "manual",
            items_json=json.dumps([{"sku_id": sku_id, "qty": qty_needed}]),
            status="draft",
        )
        self._session.add(plan)
        await self._session.flush()
        logger.info("scm_replenishment_triggered", tenant_id=tenant_id,
                     sku_id=sku_id, qty_needed=qty_needed, plan_id=plan.id)
        return {"success": True, "plan_id": plan.id, "plan_no": plan.plan_no}

    async def get_supplier_by_id(self, tenant_id: str,
                                 supplier_id: str) -> dict[str, Any] | None:
        from erp.modules.scm.domain.models import Supplier
        stmt = select(Supplier).where(
            Supplier.id == supplier_id, Supplier.tenant_id == tenant_id,
            Supplier.deleted_at.is_(None),
        )
        supplier = (await self._session.execute(stmt)).scalar_one_or_none()
        if not supplier:
            return None
        return {"id": supplier.id, "name": supplier.name, "code": supplier.code,
                "status": supplier.status, "cooperation_level": supplier.cooperation_level}

    async def create_purchase_order(self, tenant_id: str, supplier_id: str,
                                    warehouse_id: str, items: list[dict],
                                    **kwargs) -> dict[str, Any]:
        from erp.modules.scm.domain.models import PurchaseOrder
        import uuid
        po = PurchaseOrder(
            tenant_id=tenant_id,
            po_no=f"PO-{str(uuid.uuid4())[:8]}",
            supplier_id=supplier_id,
            warehouse_id=warehouse_id,
            status="draft",
            purchase_mode=kwargs.get("purchase_type", "standard_purchase"),
            created_by=actor_id_var.get(""),
        )
        self._session.add(po)
        await self._session.flush()
        logger.info("scm_po_created", tenant_id=tenant_id, po_id=po.id,
                     supplier_id=supplier_id, warehouse_id=warehouse_id)
        return {"success": True, "po_id": po.id, "po_no": po.po_no}

    async def create_po_with_mode(self, tenant_id: str, po_no: str, supplier_id: str,
                                  warehouse_id: str, purchase_mode: str,
                                  **kwargs) -> dict[str, Any]:
        from erp.modules.scm.application.services import PurchaseModeService
        svc = PurchaseModeService(self._session)
        try:
            po = await svc.create_po_with_mode(
                tenant_id=tenant_id, po_no=po_no, supplier_id=supplier_id,
                warehouse_id=warehouse_id, purchase_mode=purchase_mode, **kwargs,
            )
            return {"success": True, "po_id": po.id, "po_no": po.po_no, "status": po.status}
        except Exception as e:
            logger.error("scm_create_po_with_mode_failed", tenant_id=tenant_id,
                         purchase_mode=purchase_mode, error=str(e))
            return {"success": False, "reason": str(e)}

    async def process_consignment_consumption(self, tenant_id: str, po_id: str,
                                              consumed_items: list[dict]) -> dict[str, Any]:
        from erp.modules.scm.application.services import PurchaseModeService
        svc = PurchaseModeService(self._session)
        try:
            return await svc.process_consignment_consumption(tenant_id, po_id, consumed_items)
        except Exception as e:
            logger.error("scm_consignment_consumption_failed", tenant_id=tenant_id,
                         po_id=po_id, error=str(e))
            return {"success": False, "reason": str(e)}

    async def process_jit_shipment(self, tenant_id: str, po_id: str,
                                   customer_info: dict, items: list[dict]) -> dict[str, Any]:
        from erp.modules.scm.application.services import PurchaseModeService
        svc = PurchaseModeService(self._session)
        try:
            return await svc.process_jit_shipment(tenant_id, po_id, customer_info, items)
        except Exception as e:
            logger.error("scm_jit_shipment_failed", tenant_id=tenant_id,
                         po_id=po_id, error=str(e))
            return {"success": False, "reason": str(e)}

    async def process_vmi_replenishment(self, tenant_id: str, supplier_id: str,
                                        warehouse_id: str, items: list[dict]) -> dict[str, Any]:
        from erp.modules.scm.application.services import PurchaseModeService
        svc = PurchaseModeService(self._session)
        try:
            return await svc.process_vmi_replenishment(tenant_id, supplier_id, warehouse_id, items)
        except Exception as e:
            logger.error("scm_vmi_replenishment_failed", tenant_id=tenant_id,
                         supplier_id=supplier_id, error=str(e))
            return {"success": False, "reason": str(e)}

    async def process_centralized_order(self, tenant_id: str, demands: list[dict],
                                        supplier_id: str, warehouse_id: str) -> dict[str, Any]:
        from erp.modules.scm.application.services import PurchaseModeService
        svc = PurchaseModeService(self._session)
        try:
            return await svc.process_centralized_order(tenant_id, demands, supplier_id, warehouse_id)
        except Exception as e:
            logger.error("scm_centralized_order_failed", tenant_id=tenant_id,
                         supplier_id=supplier_id, error=str(e))
            return {"success": False, "reason": str(e)}


class OmsServiceClient:
    """OMS域服务化客户端 - 通过仓储接口操作订单"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def update_order_status(self, tenant_id: str, order_id: str,
                                  new_status: str, remark: str = "") -> dict[str, Any]:
        from erp.modules.oms.domain.models import SalesOrder
        stmt = select(SalesOrder).where(
            SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id,
        )
        order = (await self._session.execute(stmt)).scalar_one_or_none()
        if not order:
            return {"success": False, "reason": "order_not_found"}
        order.status = new_status
        await self._session.flush()
        logger.info("oms_order_status_updated", tenant_id=tenant_id,
                     order_id=order_id, new_status=new_status)
        return {"success": True, "order_id": order_id, "status": new_status}

    async def get_order_by_id(self, tenant_id: str, order_id: str) -> dict[str, Any] | None:
        from erp.modules.oms.domain.models import SalesOrder
        stmt = select(SalesOrder).where(
            SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id,
        )
        order = (await self._session.execute(stmt)).scalar_one_or_none()
        if not order:
            return None
        return {"id": order.id, "order_no": order.order_no, "status": order.status,
                "item_subtotal": order.item_subtotal, "platform": order.platform}

    async def evaluate_order_risk(self, tenant_id: str, order_id: str) -> dict[str, Any]:
        from erp.modules.oms.application.services import OrderRiskControlService
        svc = OrderRiskControlService(self._session)
        try:
            return await svc.evaluate_risk(tenant_id, order_id)
        except Exception as e:
            logger.error("oms_evaluate_risk_failed", tenant_id=tenant_id,
                         order_id=order_id, error=str(e))
            return {"success": False, "reason": str(e)}

    async def approve_order(self, tenant_id: str, order_id: str, approver_id: str,
                            approval_level: int = 1, remark: str = "") -> dict[str, Any]:
        from erp.modules.oms.application.services import OrderRiskControlService
        svc = OrderRiskControlService(self._session)
        try:
            return await svc.approve_order(tenant_id, order_id, approver_id, approval_level, remark)
        except Exception as e:
            logger.error("oms_approve_order_failed", tenant_id=tenant_id,
                         order_id=order_id, error=str(e))
            return {"success": False, "reason": str(e)}

    async def reject_order(self, tenant_id: str, order_id: str, rejector_id: str,
                           reason: str = "") -> dict[str, Any]:
        from erp.modules.oms.application.services import OrderRiskControlService
        svc = OrderRiskControlService(self._session)
        try:
            return await svc.reject_order(tenant_id, order_id, rejector_id, reason)
        except Exception as e:
            logger.error("oms_reject_order_failed", tenant_id=tenant_id,
                         order_id=order_id, error=str(e))
            return {"success": False, "reason": str(e)}


class FmsServiceClient:
    """FMS域服务化客户端 - 通过仓储接口操作成本/结算/汇率"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_cost_event(self, tenant_id: str, cost_type: str, amount: float,
                                currency: str = "CNY", exchange_rate: float = 1.0,
                                **kwargs) -> dict[str, Any]:
        from erp.modules.fms.domain.models import CostEvent
        import uuid
        amount_cny = amount * exchange_rate if currency != "CNY" else amount
        event = CostEvent(
            tenant_id=tenant_id,
            event_no=f"CE-{str(uuid.uuid4())[:8]}",
            cost_type=cost_type,
            amount=amount,
            currency=currency,
            exchange_rate=exchange_rate,
            amount_cny=amount_cny,
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(CostEvent, k)},
        )
        self._session.add(event)
        await self._session.flush()
        logger.info("fms_cost_event_created", tenant_id=tenant_id,
                     cost_type=cost_type, amount=amount, event_id=event.id)
        return {"success": True, "event_id": event.id, "event_no": event.event_no}

    async def create_settlement(self, tenant_id: str, platform: str,
                                settlement_id: str, amount: float,
                                currency: str = "CNY", **kwargs) -> dict[str, Any]:
        from erp.modules.fms.domain.models import PlatformSettlement
        import uuid
        settlement = PlatformSettlement(
            tenant_id=tenant_id,
            settlement_no=f"STL-{str(uuid.uuid4())[:8]}",
            platform=platform,
            net_amount=amount,
            currency=currency,
            status="pending",
            store_id=kwargs.get("store_id", ""),
            **{k: v for k, v in kwargs.items() if hasattr(PlatformSettlement, k)},
        )
        self._session.add(settlement)
        await self._session.flush()
        logger.info("fms_settlement_created", tenant_id=tenant_id,
                     platform=platform, amount=amount)
        return {"success": True, "settlement_id": settlement.id}

    async def get_exchange_rate(self, tenant_id: str, from_currency: str,
                                to_currency: str = "CNY") -> float:
        from erp.modules.fms.domain.models import ExchangeRate
        if from_currency == to_currency:
            return 1.0
        stmt = select(ExchangeRate).where(
            ExchangeRate.tenant_id == tenant_id,
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
        ).order_by(ExchangeRate.effective_date.desc())
        rate = (await self._session.execute(stmt)).scalar_one_or_none()
        return rate.rate if rate else 1.0


class TmsServiceClient:
    """TMS域服务化客户端 - 通过仓储接口操作发货/追踪"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_shipment(self, tenant_id: str, order_id: str,
                              warehouse_id: str, provider_id: str,
                              shipping_method_id: str, **kwargs) -> dict[str, Any]:
        from erp.modules.tms.domain.models import Shipment
        import uuid
        shipment = Shipment(
            tenant_id=tenant_id,
            shipment_no=f"SHP-{str(uuid.uuid4())[:8]}",
            order_id=order_id,
            warehouse_id=warehouse_id,
            provider_id=provider_id,
            shipping_method_id=shipping_method_id,
            status="pending",
            **{k: v for k, v in kwargs.items() if hasattr(Shipment, k)},
        )
        self._session.add(shipment)
        await self._session.flush()
        logger.info("tms_shipment_created", tenant_id=tenant_id,
                     order_id=order_id, shipment_id=shipment.id)
        return {"success": True, "shipment_id": shipment.id, "shipment_no": shipment.shipment_no}

    async def update_tracking(self, tenant_id: str, shipment_id: str,
                              tracking_no: str, events: list | None = None) -> dict[str, Any]:
        from erp.modules.tms.domain.models import Shipment
        import json
        stmt = select(Shipment).where(
            Shipment.id == shipment_id, Shipment.tenant_id == tenant_id,
        )
        shipment = (await self._session.execute(stmt)).scalar_one_or_none()
        if not shipment:
            return {"success": False, "reason": "shipment_not_found"}
        shipment.tracking_no = tracking_no
        if events:
            shipment.tracking_events_json = json.dumps(events, default=str)
        await self._session.flush()
        logger.info("tms_tracking_updated", tenant_id=tenant_id,
                     shipment_id=shipment_id, tracking_no=tracking_no)
        return {"success": True, "shipment_id": shipment_id, "tracking_no": tracking_no}


class PdmServiceClient:
    """PDM域服务化客户端 - 通过仓储接口操作产品/SKU"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_sku_by_id(self, tenant_id: str, sku_id: str) -> dict[str, Any] | None:
        from erp.modules.pdm.domain.models import SKU
        stmt = select(SKU).where(SKU.id == sku_id, SKU.tenant_id == tenant_id)
        sku = (await self._session.execute(stmt)).scalar_one_or_none()
        if not sku:
            return None
        return {"id": sku.id, "sku_code": sku.sku_code, "spu_id": sku.spu_id,
                "status": sku.status, "cost_price": sku.cost_price}

    async def update_spu_status(self, tenant_id: str, spu_id: str,
                                new_status: str) -> dict[str, Any]:
        from erp.modules.pdm.domain.models import SPU
        stmt = select(SPU).where(SPU.id == spu_id, SPU.tenant_id == tenant_id)
        spu = (await self._session.execute(stmt)).scalar_one_or_none()
        if not spu:
            return {"success": False, "reason": "spu_not_found"}
        spu.status = new_status
        await self._session.flush()
        return {"success": True, "spu_id": spu_id, "status": new_status}

    async def record_product_issue(self, tenant_id: str, sku_id: str,
                                   issue_type: str, description: str,
                                   source: str = "") -> dict[str, Any]:
        from erp.modules.pdm.domain.models import ProductIssue
        import uuid
        issue = ProductIssue(
            tenant_id=tenant_id,
            sku_id=sku_id,
            issue_type=issue_type,
            description=description,
            status="open",
            created_by=actor_id_var.get(""),
        )
        self._session.add(issue)
        await self._session.flush()
        logger.info("pdm_product_issue_recorded", tenant_id=tenant_id,
                     sku_id=sku_id, issue_type=issue_type)
        return {"success": True, "issue_id": issue.id}


class SomServiceClient:
    """SOM域服务化客户端 - 通过仓储接口操作Listing/定价"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def update_listing_price(self, tenant_id: str, listing_id: str,
                                   new_price: float) -> dict[str, Any]:
        from erp.modules.som.domain.models import Listing
        stmt = select(Listing).where(Listing.id == listing_id, Listing.tenant_id == tenant_id)
        listing = (await self._session.execute(stmt)).scalar_one_or_none()
        if not listing:
            return {"success": False, "reason": "listing_not_found"}
        old_price = listing.price
        listing.price = new_price
        await self._session.flush()
        logger.info("som_listing_price_updated", tenant_id=tenant_id,
                     listing_id=listing_id, old_price=old_price, new_price=new_price)
        return {"success": True, "listing_id": listing_id, "old_price": old_price, "new_price": new_price}

    async def get_listing_by_id(self, tenant_id: str,
                                listing_id: str) -> dict[str, Any] | None:
        from erp.modules.som.domain.models import Listing
        stmt = select(Listing).where(Listing.id == listing_id, Listing.tenant_id == tenant_id)
        listing = (await self._session.execute(stmt)).scalar_one_or_none()
        if not listing:
            return None
        return {"id": listing.id, "sku_id": listing.sku_id, "price": listing.price,
                "status": listing.status, "store_id": listing.store_id}


class AdsServiceClient:
    """ADS域服务化客户端 - 通过仓储接口操作广告活动"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def update_campaign_budget(self, tenant_id: str, campaign_id: str,
                                     new_budget: float) -> dict[str, Any]:
        from erp.modules.ads.domain.models import AdCampaign
        stmt = select(AdCampaign).where(
            AdCampaign.id == campaign_id, AdCampaign.tenant_id == tenant_id,
        )
        campaign = (await self._session.execute(stmt)).scalar_one_or_none()
        if not campaign:
            return {"success": False, "reason": "campaign_not_found"}
        old_budget = campaign.daily_budget
        campaign.daily_budget = new_budget
        await self._session.flush()
        logger.info("ads_campaign_budget_updated", tenant_id=tenant_id,
                     campaign_id=campaign_id, old_budget=old_budget, new_budget=new_budget)
        return {"success": True, "campaign_id": campaign_id,
                "old_budget": old_budget, "new_budget": new_budget}

    async def pause_campaign(self, tenant_id: str, campaign_id: str) -> dict[str, Any]:
        from erp.modules.ads.domain.models import AdCampaign
        stmt = select(AdCampaign).where(
            AdCampaign.id == campaign_id, AdCampaign.tenant_id == tenant_id,
        )
        campaign = (await self._session.execute(stmt)).scalar_one_or_none()
        if not campaign:
            return {"success": False, "reason": "campaign_not_found"}
        campaign.status = "paused"
        await self._session.flush()
        return {"success": True, "campaign_id": campaign_id, "status": "paused"}


class CrmServiceClient:
    """CRM域服务化客户端 - 通过仓储接口操作客户/工单/评价"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_service_ticket(self, tenant_id: str, customer_id: str,
                                    ticket_type: str, subject: str,
                                    priority: str = "normal",
                                    **kwargs) -> dict[str, Any]:
        from erp.modules.crm.domain.models import ServiceTicket
        import uuid
        ticket = ServiceTicket(
            tenant_id=tenant_id,
            ticket_no=f"TK-{str(uuid.uuid4())[:8]}",
            customer_id=customer_id,
            ticket_type=ticket_type,
            subject=subject,
            priority=priority,
            status="open",
            created_by=actor_id_var.get(""),
            **{k: v for k, v in kwargs.items() if hasattr(ServiceTicket, k)},
        )
        self._session.add(ticket)
        await self._session.flush()
        logger.info("crm_service_ticket_created", tenant_id=tenant_id,
                     customer_id=customer_id, ticket_type=ticket_type)
        return {"success": True, "ticket_id": ticket.id, "ticket_no": ticket.ticket_no}

    async def record_negative_review(self, tenant_id: str, customer_id: str,
                                     sku_id: str, rating: int,
                                     content: str = "") -> dict[str, Any]:
        from erp.modules.crm.domain.models import Review
        import uuid
        review = Review(
            tenant_id=tenant_id,
            review_no=f"RV-{str(uuid.uuid4())[:8]}",
            customer_id=customer_id,
            sku_id=sku_id,
            rating=rating,
            content=content,
            status="pending",
        )
        self._session.add(review)
        await self._session.flush()
        logger.info("crm_negative_review_recorded", tenant_id=tenant_id,
                     customer_id=customer_id, sku_id=sku_id, rating=rating)
        return {"success": True, "review_id": review.id}


class FbaServiceClient:
    """FBA域服务化客户端 - 通过仓储接口操作FBA库存/补货"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def trigger_replenishment(self, tenant_id: str, sku_id: str,
                                    qty_needed: int) -> dict[str, Any]:
        from erp.modules.fba.domain.models import FbaReplenishmentPlan
        import uuid
        plan = FbaReplenishmentPlan(
            tenant_id=tenant_id,
            sku_id=sku_id,
            suggested_qty=qty_needed,
            status="pending",
            created_by=actor_id_var.get(""),
        )
        self._session.add(plan)
        await self._session.flush()
        logger.info("fba_replenishment_triggered", tenant_id=tenant_id,
                     sku_id=sku_id, qty_needed=qty_needed)
        return {"success": True, "plan_id": plan.id}

    async def update_fba_inventory(self, tenant_id: str, sku_id: str,
                                   qty_change: int, qty_type: str = "qty_fulfillable") -> dict[str, Any]:
        from erp.modules.fba.domain.models import FbaInventory
        stmt = select(FbaInventory).where(
            FbaInventory.tenant_id == tenant_id, FbaInventory.sku_id == sku_id,
        )
        inv = (await self._session.execute(stmt)).scalar_one_or_none()
        if not inv:
            return {"success": False, "reason": "fba_inventory_not_found"}
        current = getattr(inv, qty_type, 0)
        setattr(inv, qty_type, current + qty_change)
        await self._session.flush()
        return {"success": True, "sku_id": sku_id, qty_type: qty_type,
                "new_value": current + qty_change}

    async def create_exception(self, tenant_id: str, exception_no: str,
                               exception_type: str, severity: str, title: str,
                               **kwargs) -> dict[str, Any]:
        from erp.modules.fba.application.services import FbaExceptionService
        svc = FbaExceptionService(self._session)
        try:
            exc = await svc.create(
                tenant_id=tenant_id, exception_no=exception_no,
                exception_type=exception_type, severity=severity, title=title, **kwargs,
            )
            return {"success": True, "exception_id": exc.id, "exception_no": exception_no}
        except Exception as e:
            logger.error("fba_create_exception_failed", tenant_id=tenant_id,
                         exception_type=exception_type, error=str(e))
            return {"success": False, "reason": str(e)}

    async def auto_detect_discrepancy(self, tenant_id: str, store_id: str,
                                      sku_id: str, expected_qty: int,
                                      actual_qty: int, **kwargs) -> dict[str, Any]:
        from erp.modules.fba.application.services import FbaExceptionService
        svc = FbaExceptionService(self._session)
        try:
            exc = await svc.auto_detect_inventory_discrepancy(
                tenant_id=tenant_id, store_id=store_id, sku_id=sku_id,
                expected_qty=expected_qty, actual_qty=actual_qty, **kwargs,
            )
            if exc:
                return {"success": True, "exception_id": exc.id, "exception_no": exc.exception_no}
            return {"success": True, "discrepancy": False, "message": "No discrepancy detected"}
        except Exception as e:
            logger.error("fba_auto_detect_discrepancy_failed", tenant_id=tenant_id,
                         sku_id=sku_id, error=str(e))
            return {"success": False, "reason": str(e)}


class SysServiceClient:
    """SYS域服务化客户端 - 通过仓储接口操作审批/风险预警"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def submit_approval(self, tenant_id: str, approval_type: str,
                              business_id: str, business_type: str,
                              submitted_by: str, **kwargs) -> dict[str, Any]:
        from erp.shared.workflow.models import ApprovalSubmitRequest
        from erp.shared.workflow.service import ApprovalService
        service = ApprovalService(self._session)
        req = ApprovalSubmitRequest(
            tenant_id=tenant_id,
            approval_type=approval_type,
            business_id=business_id,
            business_type=business_type,
            submitted_by=submitted_by,
            title=kwargs.get("title", f"{approval_type} - {business_id}"),
            description=kwargs.get("description", ""),
        )
        instance = await service.submit(req)
        logger.info("sys_approval_submitted", tenant_id=tenant_id,
                     approval_type=approval_type, business_id=business_id)
        return {"success": True, "approval_id": instance.id}

    async def create_risk_alert(self, tenant_id: str, alert_type: str,
                                severity: str, title: str,
                                description: str = "", **kwargs) -> dict[str, Any]:
        from erp.modules.sys.domain.models import RiskAlert
        import uuid
        import json
        alert = RiskAlert(
            tenant_id=tenant_id,
            domain=kwargs.get("business_type", "system"),
            risk_type=alert_type,
            risk_level=severity,
            title=title,
            description=description,
            status="open",
            evidence_json=json.dumps({
                "business_id": kwargs.get("business_id", ""),
                "business_type": kwargs.get("business_type", ""),
                "source": kwargs.get("source", "cross_domain_event"),
            }, default=str),
        )
        self._session.add(alert)
        await self._session.flush()
        logger.info("sys_risk_alert_created", tenant_id=tenant_id,
                     alert_type=alert_type, severity=severity)
        return {"success": True, "alert_id": alert.id}


class BiServiceClient:
    """BI域服务化客户端 - 通过仓储接口操作指标"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def record_metric(self, tenant_id: str, metric_code: str,
                            numeric_value: float, period_type: str = "daily",
                            **kwargs) -> dict[str, Any]:
        from erp.modules.bi.domain.models import BiMetricValue
        from datetime import datetime, timezone
        val = BiMetricValue(
            tenant_id=tenant_id,
            metric_code=metric_code,
            period_type=period_type,
            period_date=kwargs.get("period_date", datetime.now(timezone.utc)),
            numeric_value=numeric_value,
            **{k: v for k, v in kwargs.items() if hasattr(BiMetricValue, k)},
        )
        self._session.add(val)
        await self._session.flush()
        return {"success": True, "metric_code": metric_code, "value": numeric_value}


class IamServiceClient:
    """IAM域服务化客户端 - 通过仓储接口操作用户/权限"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def check_permission(self, tenant_id: str, user_id: str,
                               resource: str, action: str) -> bool:
        from erp.modules.iam.domain.models import User, UserRole, Role, Permission
        stmt = (
            select(Permission)
            .join(Role, Role.id == Permission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                Role.tenant_id == tenant_id,
                Permission.resource == resource,
                Permission.action == action,
            )
        )
        result = (await self._session.execute(stmt)).scalar_one_or_none()
        return result is not None

    async def get_user_by_id(self, tenant_id: str, user_id: str) -> dict[str, Any] | None:
        from erp.modules.iam.domain.models import User
        stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        user = (await self._session.execute(stmt)).scalar_one_or_none()
        if not user:
            return None
        return {"id": user.id, "username": user.username, "status": user.status,
                "email": user.email}


class DomainServiceClient:
    """
    跨域服务化调用统一入口

    通过组合各域的ServiceClient，提供统一的跨域调用接口。
    每个域的Client仅通过目标域的ORM模型和Session操作数据，
    不import目标域的application层，保持领域独立性。
    """

    def __init__(self, session: AsyncSession):
        self.wms = WmsServiceClient(session)
        self.scm = ScmServiceClient(session)
        self.oms = OmsServiceClient(session)
        self.fms = FmsServiceClient(session)
        self.tms = TmsServiceClient(session)
        self.pdm = PdmServiceClient(session)
        self.som = SomServiceClient(session)
        self.ads = AdsServiceClient(session)
        self.crm = CrmServiceClient(session)
        self.fba = FbaServiceClient(session)
        self.sys = SysServiceClient(session)
        self.bi = BiServiceClient(session)
        self.iam = IamServiceClient(session)
