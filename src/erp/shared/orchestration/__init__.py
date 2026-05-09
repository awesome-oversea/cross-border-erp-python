"""
业务闭环编排服务

将跨域调用串联成完整的业务流程，确保端到端闭环:
- 采购闭环: 采购需求 → 询价 → 采购订单 → 收货 → 质检 → 入库 → 付款
- 销售闭环: 客户下单 → 风控审核 → 仓库分配 → 拣货 → 发货 → 物流 → 签收 → 结算
- FBA闭环: 补货建议 → 入库计划 → 货件创建 → 预处理 → 发货 → 在途 → 签收
- 库存闭环: 入库 → 存储 → 调拨 → 盘点 → 出库

设计原则:
  1. 编排层不包含业务逻辑，仅协调各域服务调用
  2. 通过 DomainServiceClient 进行跨域调用，保持领域独立性
  3. 每个步骤失败时记录状态，支持断点续传
  4. 全链路追踪 trace_id/tenant_id/actor_id
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from erp.shared.context import actor_id_var, tenant_id_var, trace_id_var
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from erp.shared.integration import DomainServiceClient

logger = get_logger("erp.orchestration")


class ProcurementOrchestrator:
    """
    采购闭环编排器

    编排采购全流程: 采购需求 → 询价比价 → 采购订单 → 收货确认 → 入库 → 付款
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._client = DomainServiceClient(session)

    async def execute_full_procurement(self, tenant_id: str, supplier_id: str,
                                        warehouse_id: str, items: list[dict],
                                        purchase_mode: str = "standard_purchase",
                                        **kwargs) -> dict[str, Any]:
        """
        执行完整采购闭环

        流程: 创建采购单 → 审批 → 收货 → 入库 → 付款
        """
        trace_id = trace_id_var.get("")
        result: dict[str, Any] = {
            "trace_id": trace_id, "tenant_id": tenant_id,
            "supplier_id": supplier_id, "warehouse_id": warehouse_id,
            "purchase_mode": purchase_mode,
            "steps_completed": [], "steps_failed": [],
        }
        po_result = await self._create_purchase_order(
            tenant_id, supplier_id, warehouse_id, items, purchase_mode, **kwargs
        )
        if not po_result.get("success"):
            result["steps_failed"].append({"step": "create_po", "error": po_result})
            return result
        result["po_id"] = po_result.get("po_id")
        result["po_no"] = po_result.get("po_no")
        result["steps_completed"].append("create_po")
        if po_result.get("status") == "pending_approval":
            approval_result = await self._auto_approve_if_eligible(
                tenant_id, po_result["po_id"], purchase_mode, items
            )
            if approval_result.get("approved"):
                result["steps_completed"].append("auto_approval")
            else:
                result["steps_completed"].append("pending_manual_approval")
                result["note"] = "PO requires manual approval"
                return result
        receiving_result = await self._confirm_receiving(
            tenant_id, po_result["po_id"], items
        )
        if receiving_result.get("success"):
            result["steps_completed"].append("receiving")
        else:
            result["steps_failed"].append({"step": "receiving", "error": receiving_result})
        inbound_result = await self._trigger_inbound(
            tenant_id, warehouse_id, po_result["po_id"], items
        )
        if inbound_result.get("success"):
            result["steps_completed"].append("inbound")
        else:
            result["steps_failed"].append({"step": "inbound", "error": inbound_result})
        payment_result = await self._process_payment(
            tenant_id, po_result["po_id"], supplier_id, items, purchase_mode
        )
        if payment_result.get("success"):
            result["steps_completed"].append("payment")
        else:
            result["steps_failed"].append({"step": "payment", "error": payment_result})
        result["completed_at"] = datetime.now(UTC).isoformat()
        return result

    async def _create_purchase_order(self, tenant_id: str, supplier_id: str,
                                      warehouse_id: str, items: list[dict],
                                      purchase_mode: str, **kwargs) -> dict:
        try:
            import uuid
            po_no = f"PO-{uuid.uuid4().hex[:8].upper()}"
            result = await self._client.scm.create_po_with_mode(
                tenant_id=tenant_id, po_no=po_no, supplier_id=supplier_id,
                warehouse_id=warehouse_id, purchase_mode=purchase_mode,
                items=items, **kwargs,
            )
            return {"success": True, **result}
        except Exception as e:
            logger.error("procurement_create_po_failed", tenant_id=tenant_id, error=str(e))
            return {"success": False, "reason": str(e)}

    async def _auto_approve_if_eligible(self, tenant_id: str, po_id: str,
                                         purchase_mode: str, items: list[dict]) -> dict:
        if purchase_mode in ("jit_dropship", "vmi_subcontracting"):
            return {"approved": True, "reason": "mode_auto_approve"}
        total = sum(i.get("quantity", 0) * i.get("unit_price", 0) for i in items)
        if purchase_mode == "consignment" and total <= 50000:
            return {"approved": True, "reason": "below_threshold"}
        if purchase_mode == "standard_purchase" and total <= 10000:
            return {"approved": True, "reason": "below_threshold"}
        return {"approved": False, "reason": "requires_manual_approval"}

    async def _confirm_receiving(self, tenant_id: str, po_id: str,
                                  items: list[dict]) -> dict:
        try:
            from erp.modules.scm.application.services import PurchaseReceivingService
            svc = PurchaseReceivingService(self._session)
            received_items = [
                {"sku_id": i.get("sku_id", ""), "received_qty": i.get("quantity", 0),
                 "accepted_qty": i.get("quantity", 0)}
                for i in items
            ]
            result = await svc.confirm_receipt(
                tenant_id=tenant_id, po_id=po_id,
                received_items=received_items,
                received_by=actor_id_var.get("system"),
            )
            return {"success": True, "receiving_result": result}
        except Exception as e:
            logger.error("procurement_receiving_failed", tenant_id=tenant_id, error=str(e))
            return {"success": False, "reason": str(e)}

    async def _trigger_inbound(self, tenant_id: str, warehouse_id: str,
                                po_id: str, items: list[dict]) -> dict:
        try:
            inbound_items = [
                {"sku_id": i.get("sku_id", ""), "quantity": i.get("quantity", 0)}
                for i in items
            ]
            result = await self._client.wms.create_inbound_order(
                tenant_id=tenant_id, warehouse_id=warehouse_id,
                source_type="purchase_order", source_id=po_id,
                items=inbound_items,
            )
            return {"success": result.get("success", True), "inbound_result": result}
        except Exception as e:
            logger.error("procurement_inbound_failed", tenant_id=tenant_id, error=str(e))
            return {"success": False, "reason": str(e)}

    async def _process_payment(self, tenant_id: str, po_id: str, supplier_id: str,
                                items: list[dict], purchase_mode: str) -> dict:
        try:
            from erp.modules.scm.application.services import PurchasePaymentService
            svc = PurchasePaymentService(self._session)
            total_amount = sum(i.get("quantity", 0) * i.get("unit_price", 0) for i in items)
            if purchase_mode == "consignment":
                return {"success": True, "reason": "consignment_deferred_payment"}
            result = await svc.record_payment(
                tenant_id=tenant_id, po_id=po_id,
                payment_amount=total_amount,
                payment_method="bank_transfer",
            )
            return {"success": True, "payment_result": result}
        except Exception as e:
            logger.error("procurement_payment_failed", tenant_id=tenant_id, error=str(e))
            return {"success": False, "reason": str(e)}


class SalesOrderOrchestrator:
    """
    销售闭环编排器

    编排销售全流程: 下单 → 风控审核 → 仓库分配 → 库存预留 → 发货 → 物流 → 签收 → 结算
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._client = DomainServiceClient(session)

    async def execute_full_sales_flow(self, tenant_id: str, order_id: str,
                                       **kwargs) -> dict[str, Any]:
        """
        执行完整销售闭环

        流程: 风控评估 → 审批 → 仓库分配 → 库存预留 → 发货 → 物流 → 结算
        """
        trace_id = trace_id_var.get("")
        result: dict[str, Any] = {
            "trace_id": trace_id, "tenant_id": tenant_id,
            "order_id": order_id,
            "steps_completed": [], "steps_failed": [],
        }
        risk_result = await self._evaluate_risk(tenant_id, order_id)
        result["risk_evaluation"] = risk_result
        if risk_result.get("risk_level") == "critical":
            result["steps_failed"].append({"step": "risk_control", "reason": "critical_risk"})
            return result
        result["steps_completed"].append("risk_evaluation")
        if risk_result.get("requires_approval"):
            approval_result = await self._approve_order(tenant_id, order_id, risk_result)
            if not approval_result.get("approved"):
                result["steps_failed"].append({"step": "approval", "reason": "approval_denied"})
                return result
            result["steps_completed"].append("approval")
        else:
            confirm_result = await self._client.oms.update_order_status(
                tenant_id=tenant_id, order_id=order_id, new_status="confirmed"
            )
            result["steps_completed"].append("auto_confirmed")
        order_info = await self._client.oms.get_order_by_id(tenant_id, order_id)
        if not order_info:
            result["steps_failed"].append({"step": "get_order", "reason": "order_not_found"})
            return result
        allocation_result = await self._allocate_warehouse(tenant_id, order_id, order_info)
        if allocation_result.get("success"):
            result["steps_completed"].append("warehouse_allocation")
            result["allocated_warehouse"] = allocation_result.get("warehouse_id")
        else:
            result["steps_failed"].append({"step": "warehouse_allocation", "error": allocation_result})
            return result
        reserve_result = await self._reserve_inventory(
            tenant_id, allocation_result["warehouse_id"], order_info
        )
        if reserve_result.get("success"):
            result["steps_completed"].append("inventory_reserved")
        else:
            result["steps_failed"].append({"step": "inventory_reserve", "error": reserve_result})
            return result
        shipment_result = await self._create_shipment(tenant_id, order_id, allocation_result, order_info)
        if shipment_result.get("success"):
            result["steps_completed"].append("shipment_created")
            result["shipment_id"] = shipment_result.get("shipment_id")
        else:
            result["steps_failed"].append({"step": "shipment", "error": shipment_result})
        settlement_result = await self._create_settlement(tenant_id, order_info)
        if settlement_result.get("success"):
            result["steps_completed"].append("settlement")
        else:
            result["steps_failed"].append({"step": "settlement", "error": settlement_result})
        result["completed_at"] = datetime.now(UTC).isoformat()
        return result

    async def _evaluate_risk(self, tenant_id: str, order_id: str) -> dict:
        try:
            return await self._client.oms.evaluate_order_risk(tenant_id, order_id)
        except Exception as e:
            logger.error("sales_risk_eval_failed", tenant_id=tenant_id, error=str(e))
            return {"risk_level": "medium", "requires_approval": True, "error": str(e)}

    async def _approve_order(self, tenant_id: str, order_id: str,
                              risk_result: dict) -> dict:
        try:
            if risk_result.get("auto_approve"):
                return {"approved": True, "reason": "auto_approved"}
            approval_level = risk_result.get("approval_level", 1)
            result = await self._client.oms.approve_order(
                tenant_id=tenant_id, order_id=order_id,
                approver_id=actor_id_var.get("system"),
                approval_level=approval_level,
            )
            return {"approved": True, "approval_result": result}
        except Exception as e:
            logger.error("sales_approval_failed", tenant_id=tenant_id, error=str(e))
            return {"approved": False, "reason": str(e)}

    async def _allocate_warehouse(self, tenant_id: str, order_id: str,
                                   order_info: dict) -> dict:
        try:
            from erp.modules.oms.application.services import WarehouseAllocationService
            svc = WarehouseAllocationService(self._session)
            items = order_info.get("items", [])
            result = await svc.allocate_warehouse(
                tenant_id=tenant_id, order_id=order_id,
                recipient_country=order_info.get("recipient_country", ""),
                items=items,
            )
            return {"success": True, "warehouse_id": result.get("warehouse_id", ""), "allocation": result}
        except Exception as e:
            logger.error("sales_warehouse_alloc_failed", tenant_id=tenant_id, error=str(e))
            return {"success": False, "reason": str(e)}

    async def _reserve_inventory(self, tenant_id: str, warehouse_id: str,
                                  order_info: dict) -> dict:
        try:
            items = order_info.get("items", [])
            reserved_count = 0
            for item in items:
                result = await self._client.wms.reserve_inventory(
                    tenant_id=tenant_id, warehouse_id=warehouse_id,
                    sku_id=item.get("sku_id", ""), qty=item.get("quantity", 0),
                    reference_type="sales_order", reference_id=order_info.get("id", ""),
                )
                if result.get("success"):
                    reserved_count += 1
            return {"success": reserved_count == len(items), "reserved_count": reserved_count}
        except Exception as e:
            logger.error("sales_inventory_reserve_failed", tenant_id=tenant_id, error=str(e))
            return {"success": False, "reason": str(e)}

    async def _create_shipment(self, tenant_id: str, order_id: str,
                                allocation: dict, order_info: dict) -> dict:
        try:
            warehouse_id = allocation.get("warehouse_id", "")
            result = await self._client.tms.create_shipment(
                tenant_id=tenant_id, order_id=order_id,
                warehouse_id=warehouse_id,
                provider_id=order_info.get("provider_id", ""),
                shipping_method_id=order_info.get("shipping_method_id", ""),
            )
            return {"success": True, "shipment_id": result.get("shipment_id", ""), "shipment": result}
        except Exception as e:
            logger.error("sales_shipment_failed", tenant_id=tenant_id, error=str(e))
            return {"success": False, "reason": str(e)}

    async def _create_settlement(self, tenant_id: str, order_info: dict) -> dict:
        try:
            platform = order_info.get("platform", "")
            store_id = order_info.get("store_id", "")
            amount = order_info.get("item_subtotal", 0)
            if amount <= 0:
                return {"success": True, "reason": "zero_amount_no_settlement"}
            result = await self._client.fms.create_settlement(
                tenant_id=tenant_id, platform=platform,
                settlement_id=f"STL-{order_info.get('order_no', '')}",
                amount=amount, currency=order_info.get("currency", "USD"),
                store_id=store_id,
            )
            return {"success": True, "settlement": result}
        except Exception as e:
            logger.error("sales_settlement_failed", tenant_id=tenant_id, error=str(e))
            return {"success": False, "reason": str(e)}


class FBAReplenishmentOrchestrator:
    """
    FBA补货闭环编排器

    编排FBA补货全流程: 库存分析 → 补货建议 → 入库计划 → 货件拆分 → 预处理 → 发货 → 签收
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._client = DomainServiceClient(session)

    async def execute_full_replenishment(self, tenant_id: str, store_id: str,
                                          days_of_stock: int = 30,
                                          max_units_per_shipment: int = 200,
                                          **kwargs) -> dict[str, Any]:
        """
        执行完整FBA补货闭环

        流程: 库存分析 → 补货建议 → 入库计划 → 货件拆分 → 预处理 → 发货
        """
        trace_id = trace_id_var.get("")
        result: dict[str, Any] = {
            "trace_id": trace_id, "tenant_id": tenant_id,
            "store_id": store_id,
            "steps_completed": [], "steps_failed": [],
        }
        suggestions_result = await self._generate_suggestions(tenant_id, store_id, days_of_stock)
        if not suggestions_result.get("suggestions"):
            result["note"] = "No replenishment needed"
            result["steps_completed"].append("analysis")
            return result
        result["suggestions_count"] = len(suggestions_result["suggestions"])
        result["steps_completed"].append("suggestions")
        plan_result = await self._create_inbound_plan(
            tenant_id, store_id, suggestions_result["suggestions"], **kwargs
        )
        if not plan_result.get("plan_id"):
            result["steps_failed"].append({"step": "inbound_plan", "error": plan_result})
            return result
        result["plan_id"] = plan_result["plan_id"]
        result["plan_no"] = plan_result.get("plan_no", "")
        result["steps_completed"].append("inbound_plan")
        split_result = await self._split_into_shipments(
            tenant_id, plan_result["plan_id"], max_units_per_shipment
        )
        if split_result.get("shipments_created", 0) > 0:
            result["shipments_created"] = split_result["shipments_created"]
            result["steps_completed"].append("split_shipments")
        else:
            result["steps_failed"].append({"step": "split_shipments", "error": split_result})
            return result
        preprocess_result = await self._preprocess_shipments(
            tenant_id, split_result.get("shipments", [])
        )
        result["preprocess_result"] = preprocess_result
        result["steps_completed"].append("preprocess")
        result["completed_at"] = datetime.now(UTC).isoformat()
        return result

    async def _generate_suggestions(self, tenant_id: str, store_id: str,
                                     days_of_stock: int) -> dict:
        try:
            from erp.modules.fba.application.services import InboundPlanOrchestrator
            svc = InboundPlanOrchestrator(self._session)
            return await svc.generate_replenishment_suggestions(
                tenant_id=tenant_id, store_id=store_id, days_of_stock=days_of_stock,
            )
        except Exception as e:
            logger.error("fba_suggestions_failed", tenant_id=tenant_id, error=str(e))
            return {"suggestions": [], "error": str(e)}

    async def _create_inbound_plan(self, tenant_id: str, store_id: str,
                                    suggestions: list[dict], **kwargs) -> dict:
        try:
            from erp.modules.fba.application.services import InboundPlanOrchestrator
            svc = InboundPlanOrchestrator(self._session)
            return await svc.create_plan_from_suggestions(
                tenant_id=tenant_id, store_id=store_id, suggestions=suggestions,
                warehouse_id=kwargs.get("warehouse_id", ""),
                destination=kwargs.get("destination", ""),
            )
        except Exception as e:
            logger.error("fba_plan_failed", tenant_id=tenant_id, error=str(e))
            return {"plan_id": None, "error": str(e)}

    async def _split_into_shipments(self, tenant_id: str, plan_id: str,
                                     max_units: int) -> dict:
        try:
            from erp.modules.fba.application.services import InboundPlanOrchestrator
            svc = InboundPlanOrchestrator(self._session)
            return await svc.split_plan_into_shipments(
                tenant_id=tenant_id, plan_id=plan_id,
                max_units_per_shipment=max_units,
            )
        except Exception as e:
            logger.error("fba_split_failed", tenant_id=tenant_id, error=str(e))
            return {"shipments_created": 0, "error": str(e)}

    async def _preprocess_shipments(self, tenant_id: str,
                                     shipments: list[dict]) -> dict:
        try:
            from erp.modules.fba.application.services import ShipmentPreprocessService
            svc = ShipmentPreprocessService(self._session)
            shipment_ids = [s.get("shipment_id", "") for s in shipments if s.get("shipment_id")]
            if not shipment_ids:
                return {"checked": 0}
            return await svc.batch_preprocess(tenant_id, shipment_ids)
        except Exception as e:
            logger.error("fba_preprocess_failed", tenant_id=tenant_id, error=str(e))
            return {"checked": 0, "error": str(e)}


class InventoryFlowOrchestrator:
    """
    库存流转闭环编排器

    编排库存流转: 采购入库 → 存储 → 调拨 → 盘点 → 销售出库
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._client = DomainServiceClient(session)

    async def execute_inbound_flow(self, tenant_id: str, warehouse_id: str,
                                    source_type: str, source_id: str,
                                    items: list[dict]) -> dict[str, Any]:
        """
        执行入库闭环

        流程: 创建入库单 → 库存增加 → 记录成本 → 更新BI指标
        """
        result: dict[str, Any] = {
            "tenant_id": tenant_id, "warehouse_id": warehouse_id,
            "source_type": source_type, "source_id": source_id,
            "steps_completed": [], "steps_failed": [],
        }
        inbound_result = await self._client.wms.create_inbound_order(
            tenant_id=tenant_id, warehouse_id=warehouse_id,
            source_type=source_type, source_id=source_id, items=items,
        )
        if inbound_result.get("success"):
            result["steps_completed"].append("inbound_order")
        else:
            result["steps_failed"].append({"step": "inbound_order", "error": inbound_result})
            return result
        for item in items:
            adjust_result = await self._client.wms.adjust_stock(
                tenant_id=tenant_id, warehouse_id=warehouse_id,
                sku_id=item.get("sku_id", ""), qty_change=item.get("quantity", 0),
                movement_type="inbound", reference_type=source_type, reference_id=source_id,
            )
            if adjust_result.get("success"):
                result["steps_completed"].append(f"stock_adjusted_{item.get('sku_id', '')}")
            else:
                result["steps_failed"].append({"step": f"stock_adjust_{item.get('sku_id', '')}", "error": adjust_result})
        try:
            await self._client.bi.record_metric(
                tenant_id=tenant_id, metric_code="inventory_inbound_qty",
                numeric_value=sum(i.get("quantity", 0) for i in items),
                period_type="daily",
            )
            result["steps_completed"].append("bi_metric_recorded")
        except Exception as e:
            result["steps_failed"].append({"step": "bi_metric", "error": str(e)})
        result["completed_at"] = datetime.now(UTC).isoformat()
        return result

    async def execute_outbound_flow(self, tenant_id: str, warehouse_id: str,
                                     order_id: str, items: list[dict]) -> dict[str, Any]:
        """
        执行出库闭环

        流程: 库存扣减 → 创建出库记录 → 记录成本 → 更新BI指标
        """
        result: dict[str, Any] = {
            "tenant_id": tenant_id, "warehouse_id": warehouse_id,
            "order_id": order_id,
            "steps_completed": [], "steps_failed": [],
        }
        for item in items:
            adjust_result = await self._client.wms.adjust_stock(
                tenant_id=tenant_id, warehouse_id=warehouse_id,
                sku_id=item.get("sku_id", ""), qty_change=-item.get("quantity", 0),
                movement_type="outbound", reference_type="sales_order", reference_id=order_id,
            )
            if adjust_result.get("success"):
                result["steps_completed"].append(f"stock_deducted_{item.get('sku_id', '')}")
            else:
                result["steps_failed"].append({"step": f"stock_deduct_{item.get('sku_id', '')}", "error": adjust_result})
        try:
            total_cost = sum(
                i.get("quantity", 0) * i.get("cost_price", 0) for i in items
            )
            if total_cost > 0:
                await self._client.fms.create_cost_event(
                    tenant_id=tenant_id, cost_type="cogs",
                    amount=total_cost, currency="CNY",
                    sku_id=",".join(i.get("sku_id", "") for i in items[:5]),
                    source_type="sales_order", source_id=order_id,
                )
                result["steps_completed"].append("cost_recorded")
        except Exception as e:
            result["steps_failed"].append({"step": "cost_record", "error": str(e)})
        try:
            await self._client.bi.record_metric(
                tenant_id=tenant_id, metric_code="inventory_outbound_qty",
                numeric_value=sum(i.get("quantity", 0) for i in items),
                period_type="daily",
            )
            result["steps_completed"].append("bi_metric_recorded")
        except Exception as e:
            result["steps_failed"].append({"step": "bi_metric", "error": str(e)})
        result["completed_at"] = datetime.now(UTC).isoformat()
        return result

    async def execute_transfer_flow(self, tenant_id: str, transfer_no: str,
                                     from_warehouse_id: str, to_warehouse_id: str,
                                     items: list[dict], **kwargs) -> dict[str, Any]:
        """
        执行调拨闭环

        流程: 创建调拨单 → 审批 → 发货(扣减源仓库) → 收货(增加目标仓库)
        """
        result: dict[str, Any] = {
            "tenant_id": tenant_id, "transfer_no": transfer_no,
            "from_warehouse_id": from_warehouse_id,
            "to_warehouse_id": to_warehouse_id,
            "steps_completed": [], "steps_failed": [],
        }
        create_result = await self._client.wms.create_stock_transfer(
            tenant_id=tenant_id, transfer_no=transfer_no,
            from_warehouse_id=from_warehouse_id, to_warehouse_id=to_warehouse_id,
            items=items, **kwargs,
        )
        if create_result.get("success"):
            result["transfer_id"] = create_result.get("transfer_id")
            result["steps_completed"].append("create_transfer")
        else:
            result["steps_failed"].append({"step": "create_transfer", "error": create_result})
            return result
        ship_result = await self._client.wms.ship_stock_transfer(
            tenant_id=tenant_id, transfer_id=result["transfer_id"],
        )
        if ship_result.get("success"):
            result["steps_completed"].append("ship_transfer")
        else:
            result["steps_failed"].append({"step": "ship_transfer", "error": ship_result})
            return result
        receive_result = await self._client.wms.receive_stock_transfer(
            tenant_id=tenant_id, transfer_id=result["transfer_id"],
        )
        if receive_result.get("success"):
            result["steps_completed"].append("receive_transfer")
        else:
            result["steps_failed"].append({"step": "receive_transfer", "error": receive_result})
        result["completed_at"] = datetime.now(UTC).isoformat()
        return result
