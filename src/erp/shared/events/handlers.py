"""
跨域事件处理器

设计原则:
  1. 事件处理器通过 DomainServiceClient 调用目标域的服务化接口
  2. 每个处理器获取独立的 AsyncSession，确保事务隔离
  3. 跨域调用失败时记录错误日志，不抛出异常阻断主流程(最终一致性)
  4. 所有跨域调用记录 trace_id/tenant_id/actor_id，保证可追踪
  5. 保持领域独立性：不直接import目标域的application层

事件驱动链路:
  OMS订单创建 → WMS库存预留
  OMS订单发货 → FMS成本事件 + TMS发货单
  OMS订单取消 → WMS库存释放
  OMS订单风控评估 → 低风险自动审批 / 高风险提交审批
  OMS退款创建 → FMS退款成本事件
  WMS库存调整 → SCM补货触发(低库存)
  WMS入库完成 → FMS采购成本事件
  WMS出库发货 → TMS追踪更新
  WMS调拨创建 → SYS审批提交
  WMS调拨完成 → BI指标记录
  SCM采购到货 → WMS入库单创建
  SCM供应商低评分 → SYS风险预警
  SCM寄售消耗 → FMS成本事件
  SCM JIT直发 → TMS发货单 + BI指标
  SCM VMI补料 → BI指标记录
  SCM集中采购 → SYS审批 + BI指标
  FBA货件接收 → FBA库存同步
  FBA低库存 → FBA补货触发
  FBA异常创建(高/严重) → SYS风险预警
  TMS发货完成 → OMS订单完成
  TMS物流异常 → CRM工单创建
  FMS成本事件 → BI指标记录
  ADS预算激增 → SYS风险预警
  SOM价格下降 → FMS利润重算
  CRM差评 → PDM产品问题记录
  PDM停产 → WMS清仓检查
  审批完成(调拨) → WMS调拨发货
  审批完成(采购) → SCM创建采购单
  审批完成(退款) → FMS退款成本
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from erp.shared.context import tenant_id_var, trace_id_var, actor_id_var
from erp.shared.events.publisher import get_event_publisher
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from erp.shared.events.domain_event import DomainEvent

logger = get_logger("erp.event_handlers")


async def _get_session():
    from erp.shared.db.session import async_session_factory
    return async_session_factory()


async def _get_client(session):
    from erp.shared.integration.client import DomainServiceClient
    return DomainServiceClient(session)


async def handle_order_created(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    order_id = event.aggregate_id
    warehouse_id = event.payload.get("warehouse_id", "")
    items = event.payload.get("items", [])
    logger.info("cross_domain_order_created", order_id=order_id, tenant_id=tenant_id,
                action="trigger_inventory_reserve")
    if not warehouse_id or not items:
        logger.warning("cross_domain_order_created_missing_data", order_id=order_id,
                       warehouse_id=warehouse_id, items_count=len(items))
        return
    try:
        async with await _get_session() as session:
            client = await _get_client(session)
            for item in items:
                sku_id = item.get("sku_id", "")
                qty = item.get("quantity", 0)
                if sku_id and qty > 0:
                    result = await client.wms.reserve_inventory(
                        tenant_id, warehouse_id, sku_id, qty,
                        reference_type="order", reference_id=order_id,
                    )
                    if not result.get("success"):
                        logger.warning("cross_domain_reserve_failed", order_id=order_id,
                                       sku_id=sku_id, reason=result.get("reason"))
            await session.commit()
    except Exception as e:
        logger.error("cross_domain_order_created_handler_failed", order_id=order_id, error=str(e))


async def handle_order_status_changed(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    order_id = event.aggregate_id
    to_status = event.payload.get("to_status", "")
    warehouse_id = event.payload.get("warehouse_id", "")
    items = event.payload.get("items", [])

    if to_status in ("shipped", "delivered"):
        logger.info("cross_domain_order_shipped", order_id=order_id, to_status=to_status,
                    action="trigger_finance_and_tms")
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                shipping_cost = event.payload.get("shipping_cost", 0.0)
                if shipping_cost > 0:
                    await client.fms.create_cost_event(
                        tenant_id, cost_type="shipping_cost", amount=shipping_cost,
                        currency=event.payload.get("currency", "CNY"),
                        order_id=order_id,
                    )
                provider_id = event.payload.get("provider_id", "")
                shipping_method_id = event.payload.get("shipping_method_id", "")
                if provider_id and shipping_method_id:
                    await client.tms.create_shipment(
                        tenant_id, order_id, warehouse_id, provider_id, shipping_method_id,
                        shipping_cost=shipping_cost,
                    )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_order_shipped_handler_failed", order_id=order_id, error=str(e))

    elif to_status == "cancelled":
        logger.info("cross_domain_order_cancelled", order_id=order_id,
                    action="trigger_inventory_release")
        if warehouse_id and items:
            try:
                async with await _get_session() as session:
                    client = await _get_client(session)
                    for item in items:
                        sku_id = item.get("sku_id", "")
                        qty = item.get("quantity", 0)
                        if sku_id and qty > 0:
                            await client.wms.release_inventory(
                                tenant_id, warehouse_id, sku_id, qty,
                                reference_type="order_cancel", reference_id=order_id,
                            )
                    await session.commit()
            except Exception as e:
                logger.error("cross_domain_order_cancelled_handler_failed", order_id=order_id, error=str(e))


async def handle_order_risk_detected(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    order_id = event.aggregate_id
    risk_level = event.payload.get("risk_level", "")
    risk_reason = event.payload.get("risk_reason", "")
    logger.warning("cross_domain_risk_detected", order_id=order_id, risk_level=risk_level,
                    action="create_risk_alert")
    try:
        async with await _get_session() as session:
            client = await _get_client(session)
            await client.sys.create_risk_alert(
                tenant_id, alert_type="order_risk", severity=risk_level,
                title=f"订单风险: {order_id}", description=risk_reason,
                business_id=order_id, business_type="order",
            )
            await session.commit()
    except Exception as e:
        logger.error("cross_domain_risk_detected_handler_failed", order_id=order_id, error=str(e))


async def handle_inventory_adjusted(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    sku_id = event.payload.get("sku_id", "")
    qty_after = event.payload.get("qty_after", 0)
    safety_qty = event.payload.get("safety_qty", 0)
    if qty_after <= safety_qty and sku_id:
        logger.info("cross_domain_low_stock", sku_id=sku_id, qty_after=qty_after,
                    action="trigger_scm_replenishment")
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                qty_needed = safety_qty - qty_after + 10
                await client.scm.trigger_replenishment(
                    tenant_id, sku_id, qty_needed, reason="low_stock_auto_trigger",
                )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_low_stock_handler_failed", sku_id=sku_id, error=str(e))


async def handle_low_stock_alert(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    sku_id = event.payload.get("sku_id", "")
    available_qty = event.payload.get("available_qty", 0)
    safety_qty = event.payload.get("safety_qty", 0)
    logger.info("cross_domain_low_stock_alert", sku_id=sku_id, available_qty=available_qty,
                action="trigger_scm_replenishment")
    if sku_id:
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                qty_needed = max(safety_qty - available_qty, 10)
                await client.scm.trigger_replenishment(
                    tenant_id, sku_id, qty_needed, reason="low_stock_alert",
                )
                await client.bi.record_metric(
                    tenant_id, "low_stock_sku_count", 1.0, period_type="daily",
                )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_low_stock_alert_handler_failed", sku_id=sku_id, error=str(e))


async def handle_inbound_received(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    inbound_id = event.aggregate_id
    source_type = event.payload.get("source_type", "")
    source_id = event.payload.get("source_id", "")
    total_cost = event.payload.get("total_cost", 0.0)
    currency = event.payload.get("currency", "CNY")
    logger.info("cross_domain_inbound_received", inbound_id=inbound_id,
                action="update_fms_cost")
    if total_cost > 0:
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                cost_type = "purchase_cost" if source_type == "purchase" else "inbound_cost"
                await client.fms.create_cost_event(
                    tenant_id, cost_type=cost_type, amount=total_cost,
                    currency=currency, reference_type=source_type, reference_id=source_id,
                )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_inbound_received_handler_failed", inbound_id=inbound_id, error=str(e))


async def handle_outbound_shipped(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    outbound_id = event.aggregate_id
    tracking_no = event.payload.get("tracking_no", "")
    order_id = event.payload.get("order_id", "")
    shipment_id = event.payload.get("shipment_id", "")
    logger.info("cross_domain_outbound_shipped", outbound_id=outbound_id,
                tracking_no=tracking_no, action="update_tms_tracking")
    if tracking_no and shipment_id:
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                await client.tms.update_tracking(
                    tenant_id, shipment_id, tracking_no,
                )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_outbound_shipped_handler_failed", outbound_id=outbound_id, error=str(e))


async def handle_refund_created(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    refund_id = event.aggregate_id
    refund_amount = event.payload.get("refund_amount", 0.0)
    currency = event.payload.get("currency", "CNY")
    order_id = event.payload.get("order_id", "")
    logger.info("cross_domain_refund_created", refund_id=refund_id,
                action="trigger_finance_refund")
    if refund_amount > 0:
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                await client.fms.create_cost_event(
                    tenant_id, cost_type="refund_cost", amount=refund_amount,
                    currency=currency, order_id=order_id,
                    reference_type="refund", reference_id=refund_id,
                )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_refund_created_handler_failed", refund_id=refund_id, error=str(e))


async def handle_purchase_order_created(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    po_id = event.aggregate_id
    supplier_id = event.payload.get("supplier_id", "")
    logger.info("cross_domain_po_created", po_id=po_id, supplier_id=supplier_id,
                action="update_supplier_workload")
    try:
        async with await _get_session() as session:
            client = await _get_client(session)
            await client.bi.record_metric(
                tenant_id, "order_count", 1.0, period_type="daily",
            )
            await session.commit()
    except Exception as e:
        logger.error("cross_domain_po_created_handler_failed", po_id=po_id, error=str(e))


async def handle_purchase_order_status_changed(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    po_id = event.aggregate_id
    to_status = event.payload.get("to_status", "")
    warehouse_id = event.payload.get("warehouse_id", "")
    items = event.payload.get("items", [])

    if to_status == "received" and warehouse_id:
        logger.info("cross_domain_po_received", po_id=po_id, action="trigger_wms_inbound")
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                await client.wms.create_inbound_order(
                    tenant_id, warehouse_id, source_type="purchase",
                    source_id=po_id, items=items,
                )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_po_received_handler_failed", po_id=po_id, error=str(e))

    elif to_status == "cancelled":
        logger.info("cross_domain_po_cancelled", po_id=po_id, action="release_budget")


async def handle_supplier_rating_updated(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    supplier_id = event.aggregate_id
    new_rating = event.payload.get("new_rating", 0.0)
    if new_rating < 3.0:
        logger.warning("cross_domain_supplier_low_rating", supplier_id=supplier_id,
                        new_rating=new_rating, action="trigger_risk_alert")
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                await client.sys.create_risk_alert(
                    tenant_id, alert_type="supplier_low_rating", severity="high",
                    title=f"供应商评分过低: {supplier_id}",
                    description=f"供应商综合评分降至 {new_rating}，建议评估合作等级",
                    business_id=supplier_id, business_type="supplier",
                )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_supplier_rating_handler_failed", supplier_id=supplier_id, error=str(e))


async def handle_fba_shipment_status_changed(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    shipment_id = event.aggregate_id
    to_status = event.payload.get("to_status", "")
    sku_id = event.payload.get("sku_id", "")
    qty_received = event.payload.get("qty_received", 0)

    if to_status == "received" and sku_id:
        logger.info("cross_domain_fba_received", shipment_id=shipment_id,
                    action="sync_fba_inventory")
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                await client.fba.update_fba_inventory(
                    tenant_id, sku_id, qty_received, qty_type="qty_fulfillable",
                )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_fba_received_handler_failed", shipment_id=shipment_id, error=str(e))

    elif to_status == "shipped":
        tracking_no = event.payload.get("tracking_no", "")
        if tracking_no:
            logger.info("cross_domain_fba_shipped", shipment_id=shipment_id,
                        action="update_tms_tracking")
            try:
                async with await _get_session() as session:
                    client = await _get_client(session)
                    tms_shipment_id = event.payload.get("tms_shipment_id", "")
                    if tms_shipment_id:
                        await client.tms.update_tracking(tenant_id, tms_shipment_id, tracking_no)
                    await session.commit()
            except Exception as e:
                logger.error("cross_domain_fba_shipped_handler_failed", shipment_id=shipment_id, error=str(e))


async def handle_fba_low_stock_alert(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    sku_id = event.payload.get("sku_id", "")
    qty_fulfillable = event.payload.get("qty_fulfillable", 0)
    replenishment_threshold = event.payload.get("replenishment_threshold", 30)
    logger.info("cross_domain_fba_low_stock", sku_id=sku_id,
                qty_fulfillable=qty_fulfillable, action="trigger_fba_replenishment")
    if sku_id:
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                qty_needed = max(replenishment_threshold - qty_fulfillable, 10)
                await client.fba.trigger_replenishment(tenant_id, sku_id, qty_needed)
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_fba_low_stock_handler_failed", sku_id=sku_id, error=str(e))


async def handle_shipment_status_changed(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    shipment_id = event.aggregate_id
    to_status = event.payload.get("to_status", "")
    order_id = event.payload.get("order_id", "")

    if to_status == "delivered" and order_id:
        logger.info("cross_domain_shipment_delivered", shipment_id=shipment_id,
                    action="trigger_order_completion")
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                await client.oms.update_order_status(
                    tenant_id, order_id, "completed",
                    remark=f"Shipment {shipment_id} delivered",
                )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_shipment_delivered_handler_failed", shipment_id=shipment_id, error=str(e))

    elif to_status == "exception":
        logger.warning("cross_domain_shipment_exception", shipment_id=shipment_id,
                        action="create_crm_ticket_and_risk_alert")
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                customer_id = event.payload.get("customer_id", "")
                if customer_id:
                    await client.crm.create_service_ticket(
                        tenant_id, customer_id, ticket_type="logistics",
                        subject=f"物流异常: 发货单 {shipment_id}",
                        priority="high",
                    )
                await client.sys.create_risk_alert(
                    tenant_id, alert_type="logistics_exception", severity="high",
                    title=f"物流异常: {shipment_id}",
                    description=f"发货单 {shipment_id} 出现物流异常",
                    business_id=shipment_id, business_type="shipment",
                )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_shipment_exception_handler_failed", shipment_id=shipment_id, error=str(e))


async def handle_cost_event_created(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    cost_type = event.payload.get("cost_type", "")
    amount = event.payload.get("amount", 0.0)
    logger.info("cross_domain_cost_event_created", event_id=event.aggregate_id,
                cost_type=cost_type, action="update_profit_calculation")
    try:
        async with await _get_session() as session:
            client = await _get_client(session)
            await client.bi.record_metric(
                tenant_id, f"cost_{cost_type}", amount, period_type="daily",
            )
            await session.commit()
    except Exception as e:
        logger.error("cross_domain_cost_event_handler_failed", event_id=event.aggregate_id, error=str(e))


async def handle_settlement_created(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    settlement_id = event.aggregate_id
    platform = event.payload.get("platform", "")
    amount = event.payload.get("amount", 0.0)
    logger.info("cross_domain_settlement_created", settlement_id=settlement_id,
                platform=platform, action="reconcile_finance")
    try:
        async with await _get_session() as session:
            client = await _get_client(session)
            await client.bi.record_metric(
                tenant_id, f"settlement_{platform}", amount, period_type="daily",
            )
            await session.commit()
    except Exception as e:
        logger.error("cross_domain_settlement_handler_failed", settlement_id=settlement_id, error=str(e))


async def handle_campaign_budget_updated(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    campaign_id = event.aggregate_id
    new_budget = event.payload.get("new_budget", 0.0)
    old_budget = event.payload.get("old_budget", 0.0)
    if new_budget > old_budget * 1.5:
        logger.warning("cross_domain_budget_surge", campaign_id=campaign_id,
                        old_budget=old_budget, new_budget=new_budget,
                        action="alert_ad_manager_and_risk")
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                await client.sys.create_risk_alert(
                    tenant_id, alert_type="ad_budget_surge", severity="medium",
                    title=f"广告预算激增: {campaign_id}",
                    description=f"预算从 {old_budget} 激增至 {new_budget}，涨幅超过50%",
                    business_id=campaign_id, business_type="ad_campaign",
                )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_budget_surge_handler_failed", campaign_id=campaign_id, error=str(e))


async def handle_listing_price_updated(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    listing_id = event.aggregate_id
    new_price = event.payload.get("new_price", 0.0)
    old_price = event.payload.get("old_price", 0.0)
    sku_id = event.payload.get("sku_id", "")
    if old_price > 0 and new_price < old_price * 0.8:
        logger.info("cross_domain_price_drop", listing_id=listing_id,
                    old_price=old_price, new_price=new_price,
                    action="recalculate_profit_margin")
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                sku_info = await client.pdm.get_sku_by_id(tenant_id, sku_id) if sku_id else None
                cost_price = sku_info.get("cost_price", 0.0) if sku_info else 0.0
                if cost_price > 0 and new_price < cost_price:
                    await client.sys.create_risk_alert(
                        tenant_id, alert_type="price_below_cost", severity="high",
                        title=f"售价低于成本: Listing {listing_id}",
                        description=f"售价 {new_price} 低于成本价 {cost_price}",
                        business_id=listing_id, business_type="listing",
                    )
                await client.bi.record_metric(
                    tenant_id, "price_drop_count", 1.0, period_type="daily",
                )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_price_drop_handler_failed", listing_id=listing_id, error=str(e))


async def handle_negative_review_alert(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    review_id = event.aggregate_id
    rating = event.payload.get("rating", 0)
    sku_id = event.payload.get("sku_id", "")
    customer_id = event.payload.get("customer_id", "")
    content = event.payload.get("content", "")
    logger.warning("cross_domain_negative_review", review_id=review_id,
                    rating=rating, sku_id=sku_id, action="notify_cs_and_record_issue")
    try:
        async with await _get_session() as session:
            client = await _get_client(session)
            if customer_id:
                await client.crm.create_service_ticket(
                    tenant_id, customer_id, ticket_type="complaint",
                    subject=f"差评处理: 评分 {rating}",
                    priority="high" if rating <= 2 else "normal",
                )
            if sku_id:
                await client.pdm.record_product_issue(
                    tenant_id, sku_id, issue_type="quality_complaint",
                    description=f"差评(评分{rating}): {content[:200]}",
                    source="review",
                )
            await session.commit()
    except Exception as e:
        logger.error("cross_domain_negative_review_handler_failed", review_id=review_id, error=str(e))


async def handle_spu_status_changed(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    spu_id = event.aggregate_id
    to_status = event.payload.get("to_status", "")
    if to_status == "discontinued":
        logger.info("cross_domain_product_discontinued", spu_id=spu_id,
                    action="check_inventory_clearance")
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                await client.sys.create_risk_alert(
                    tenant_id, alert_type="product_discontinued", severity="medium",
                    title=f"产品停产需清仓: {spu_id}",
                    description="产品已停产，需检查库存并安排清仓处理",
                    business_id=spu_id, business_type="spu",
                )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_product_discontinued_handler_failed", spu_id=spu_id, error=str(e))


async def handle_metric_alert_triggered(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    metric_code = event.payload.get("metric_code", "")
    alert_type = event.payload.get("alert_type", "")
    actual_value = event.payload.get("actual_value", 0.0)
    threshold = event.payload.get("threshold", 0.0)
    logger.warning("cross_domain_metric_alert", metric_code=metric_code,
                    alert_type=alert_type, actual_value=actual_value,
                    action="create_risk_alert_and_notify")
    try:
        async with await _get_session() as session:
            client = await _get_client(session)
            await client.sys.create_risk_alert(
                tenant_id, alert_type=f"metric_{alert_type}", severity="medium",
                title=f"指标异常: {metric_code}",
                description=f"指标 {metric_code} 当前值 {actual_value}，超过阈值 {threshold}",
            )
            await session.commit()
    except Exception as e:
        logger.error("cross_domain_metric_alert_handler_failed", metric_code=metric_code, error=str(e))


async def handle_approval_submitted(event: DomainEvent) -> None:
    approval_id = event.aggregate_id
    approval_type = event.payload.get("approval_type", "")
    logger.info("cross_domain_approval_submitted", approval_id=approval_id,
                approval_type=approval_type, action="notify_approvers")


async def handle_approval_completed(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    approval_id = event.aggregate_id
    result = event.payload.get("result", "")
    business_id = event.payload.get("business_id", "")
    business_type = event.payload.get("business_type", "")

    if result == "approved":
        logger.info("cross_domain_approval_approved", approval_id=approval_id,
                    business_id=business_id, action="execute_business_flow")
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                if business_type == "purchase_order":
                    await client.scm.create_purchase_order(
                        tenant_id,
                        supplier_id=event.payload.get("supplier_id", ""),
                        warehouse_id=event.payload.get("warehouse_id", ""),
                        items=event.payload.get("items", []),
                        purchase_type=event.payload.get("purchase_type", "market"),
                    )
                elif business_type == "refund":
                    await client.fms.create_cost_event(
                        tenant_id, cost_type="refund_cost",
                        amount=event.payload.get("refund_amount", 0.0),
                        currency=event.payload.get("currency", "CNY"),
                        order_id=business_id,
                    )
                elif business_type == "payment":
                    await client.fms.create_cost_event(
                        tenant_id, cost_type="payment_cost",
                        amount=event.payload.get("payment_amount", 0.0),
                        currency=event.payload.get("currency", "CNY"),
                    )
                elif business_type == "stock_transfer":
                    transfer_id = event.payload.get("transfer_id", "")
                    if transfer_id:
                        await client.wms.ship_stock_transfer(tenant_id, transfer_id)
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_approval_approved_handler_failed",
                         approval_id=approval_id, error=str(e))
    elif result == "rejected":
        logger.info("cross_domain_approval_rejected", approval_id=approval_id,
                    action="notify_submitter")


async def handle_stock_transfer_created(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    transfer_id = event.aggregate_id
    from_warehouse_id = event.payload.get("from_warehouse_id", "")
    to_warehouse_id = event.payload.get("to_warehouse_id", "")
    items = event.payload.get("items", [])
    logger.info("cross_domain_stock_transfer_created", transfer_id=transfer_id,
                from_wh=from_warehouse_id, to_wh=to_warehouse_id,
                action="submit_for_approval")
    try:
        async with await _get_session() as session:
            client = await _get_client(session)
            await client.sys.submit_approval(
                tenant_id, approval_type="stock_transfer",
                business_id=transfer_id, business_type="stock_transfer",
                submitted_by=event.payload.get("created_by", ""),
                title=f"库存调拨审批: {from_warehouse_id} → {to_warehouse_id}",
                description=f"调拨明细: {len(items)} 项",
            )
            await session.commit()
    except Exception as e:
        logger.error("cross_domain_stock_transfer_created_handler_failed",
                     transfer_id=transfer_id, error=str(e))


async def handle_stock_transfer_completed(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    transfer_id = event.aggregate_id
    from_warehouse_id = event.payload.get("from_warehouse_id", "")
    to_warehouse_id = event.payload.get("to_warehouse_id", "")
    logger.info("cross_domain_stock_transfer_completed", transfer_id=transfer_id,
                action="record_bi_metric")
    try:
        async with await _get_session() as session:
            client = await _get_client(session)
            await client.bi.record_metric(
                tenant_id, "stock_transfer_count", 1.0, period_type="daily",
            )
            await session.commit()
    except Exception as e:
        logger.error("cross_domain_stock_transfer_completed_handler_failed",
                     transfer_id=transfer_id, error=str(e))


async def handle_fba_exception_created(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    exception_id = event.aggregate_id
    exception_type = event.payload.get("exception_type", "")
    severity = event.payload.get("severity", "medium")
    sku_id = event.payload.get("sku_id", "")
    logger.warning("cross_domain_fba_exception_created", exception_id=exception_id,
                    exception_type=exception_type, severity=severity,
                    action="create_risk_alert_if_critical")
    if severity in ("high", "critical"):
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                await client.sys.create_risk_alert(
                    tenant_id, alert_type=f"fba_exception_{exception_type}",
                    severity=severity,
                    title=f"FBA异常({severity}): {exception_type}",
                    description=f"FBA异常ID: {exception_id}, SKU: {sku_id}",
                    business_id=exception_id, business_type="fba_exception",
                )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_fba_exception_handler_failed",
                         exception_id=exception_id, error=str(e))


async def handle_order_risk_evaluation(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    order_id = event.aggregate_id
    risk_level = event.payload.get("risk_level", "low")
    risk_score = event.payload.get("risk_score", 0)
    logger.info("cross_domain_order_risk_evaluation", order_id=order_id,
                risk_level=risk_level, risk_score=risk_score,
                action="auto_approve_or_submit_approval")
    try:
        async with await _get_session() as session:
            client = await _get_client(session)
            if risk_level == "low":
                await client.oms.approve_order(
                    tenant_id, order_id, approver_id="system",
                    approval_level=0, remark="Auto-approved: low risk",
                )
            else:
                approval_level = 1
                if risk_level == "high":
                    approval_level = 2
                elif risk_level == "critical":
                    approval_level = 3
                await client.sys.submit_approval(
                    tenant_id, approval_type="order_risk",
                    business_id=order_id, business_type="order",
                    submitted_by="system",
                    title=f"订单风控审批(R{risk_level}): {order_id}",
                    description=f"风险评分: {risk_score}, 风险等级: {risk_level}",
                )
            await session.commit()
    except Exception as e:
        logger.error("cross_domain_order_risk_evaluation_handler_failed",
                     order_id=order_id, error=str(e))


async def handle_consignment_consumption(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    po_id = event.aggregate_id
    consumed_items = event.payload.get("consumed_items", [])
    total_amount = event.payload.get("total_amount", 0.0)
    logger.info("cross_domain_consignment_consumption", po_id=po_id,
                total_amount=total_amount, action="create_fms_cost_event")
    if total_amount > 0:
        try:
            async with await _get_session() as session:
                client = await _get_client(session)
                await client.fms.create_cost_event(
                    tenant_id, cost_type="consignment_consumption",
                    amount=total_amount, currency=event.payload.get("currency", "CNY"),
                    reference_type="purchase_order", reference_id=po_id,
                )
                await session.commit()
        except Exception as e:
            logger.error("cross_domain_consignment_consumption_handler_failed",
                         po_id=po_id, error=str(e))


async def handle_jit_shipment_created(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    po_id = event.aggregate_id
    customer_info = event.payload.get("customer_info", {})
    items = event.payload.get("items", [])
    logger.info("cross_domain_jit_shipment_created", po_id=po_id,
                action="create_tms_shipment_direct")
    try:
        async with await _get_session() as session:
            client = await _get_client(session)
            warehouse_id = event.payload.get("warehouse_id", "")
            provider_id = event.payload.get("provider_id", "")
            if warehouse_id and provider_id:
                await client.tms.create_shipment(
                    tenant_id, order_id=po_id, warehouse_id=warehouse_id,
                    provider_id=provider_id,
                    shipping_method_id=event.payload.get("shipping_method_id", "standard"),
                    shipment_type="direct_to_customer",
                )
            await client.bi.record_metric(
                tenant_id, "jit_shipment_count", 1.0, period_type="daily",
            )
            await session.commit()
    except Exception as e:
        logger.error("cross_domain_jit_shipment_handler_failed", po_id=po_id, error=str(e))


async def handle_vmi_replenishment_triggered(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    po_id = event.aggregate_id
    supplier_id = event.payload.get("supplier_id", "")
    items = event.payload.get("items", [])
    logger.info("cross_domain_vmi_replenishment", po_id=po_id,
                supplier_id=supplier_id, action="record_bi_metric")
    try:
        async with await _get_session() as session:
            client = await _get_client(session)
            await client.bi.record_metric(
                tenant_id, "vmi_replenishment_count", 1.0, period_type="daily",
            )
            await session.commit()
    except Exception as e:
        logger.error("cross_domain_vmi_replenishment_handler_failed",
                     po_id=po_id, error=str(e))


async def handle_centralized_order_created(event: DomainEvent) -> None:
    tenant_id = event.tenant_id
    po_id = event.aggregate_id
    total_amount = event.payload.get("total_amount", 0.0)
    demands_count = event.payload.get("demands_count", 0)
    logger.info("cross_domain_centralized_order_created", po_id=po_id,
                total_amount=total_amount, demands_count=demands_count,
                action="submit_for_approval_and_record_metric")
    try:
        async with await _get_session() as session:
            client = await _get_client(session)
            await client.sys.submit_approval(
                tenant_id, approval_type="centralized_purchase",
                business_id=po_id, business_type="purchase_order",
                submitted_by=event.payload.get("created_by", ""),
                title=f"集中采购审批: {po_id}",
                description=f"汇总 {demands_count} 个需求，总金额 {total_amount}",
            )
            await client.bi.record_metric(
                tenant_id, "centralized_order_count", 1.0, period_type="daily",
            )
            await session.commit()
    except Exception as e:
        logger.error("cross_domain_centralized_order_handler_failed",
                     po_id=po_id, error=str(e))


async def handle_generic_event(event: DomainEvent) -> None:
    logger.debug("generic_event_handler", event_type=event.event_type,
                 domain=event.domain, aggregate_id=event.aggregate_id)


async def handle_procurement_loop_trigger(event: DomainEvent) -> None:
    """采购闭环触发: 当采购订单审批通过时，自动执行收货→入库→付款闭环"""
    tenant_id = event.tenant_id
    po_id = event.aggregate_id
    to_status = event.payload.get("to_status", "")
    if to_status != "approved":
        return
    purchase_mode = event.payload.get("purchase_mode", "standard_purchase")
    warehouse_id = event.payload.get("warehouse_id", "")
    items = event.payload.get("items", [])
    logger.info("orchestration_procurement_loop_triggered", po_id=po_id,
                purchase_mode=purchase_mode, action="execute_procurement_orchestration")
    try:
        async with await _get_session() as session:
            from erp.shared.orchestration import ProcurementOrchestrator
            orchestrator = ProcurementOrchestrator(session)
            result = await orchestrator.execute_full_procurement(
                tenant_id=tenant_id, supplier_id=event.payload.get("supplier_id", ""),
                warehouse_id=warehouse_id, items=items,
                purchase_mode=purchase_mode,
            )
            await session.commit()
            logger.info("orchestration_procurement_loop_completed", po_id=po_id,
                        steps_completed=result.get("steps_completed", []),
                        steps_failed=result.get("steps_failed", []))
    except Exception as e:
        logger.error("orchestration_procurement_loop_failed", po_id=po_id, error=str(e))


async def handle_sales_loop_trigger(event: DomainEvent) -> None:
    """销售闭环触发: 当订单确认时，自动执行仓库分配→库存预留→发货→结算闭环"""
    tenant_id = event.tenant_id
    order_id = event.aggregate_id
    to_status = event.payload.get("to_status", "")
    if to_status != "confirmed":
        return
    logger.info("orchestration_sales_loop_triggered", order_id=order_id,
                action="execute_sales_orchestration")
    try:
        async with await _get_session() as session:
            from erp.shared.orchestration import SalesOrderOrchestrator
            orchestrator = SalesOrderOrchestrator(session)
            result = await orchestrator.execute_full_sales_flow(
                tenant_id=tenant_id, order_id=order_id,
            )
            await session.commit()
            logger.info("orchestration_sales_loop_completed", order_id=order_id,
                        steps_completed=result.get("steps_completed", []),
                        steps_failed=result.get("steps_failed", []))
    except Exception as e:
        logger.error("orchestration_sales_loop_failed", order_id=order_id, error=str(e))


async def handle_fba_replenishment_loop_trigger(event: DomainEvent) -> None:
    """FBA补货闭环触发: 当FBA低库存告警时，自动执行补货建议→入库计划→货件拆分闭环"""
    tenant_id = event.tenant_id
    store_id = event.payload.get("store_id", "")
    sku_id = event.payload.get("sku_id", "")
    logger.info("orchestration_fba_replenishment_loop_triggered", sku_id=sku_id,
                store_id=store_id, action="execute_fba_orchestration")
    try:
        async with await _get_session() as session:
            from erp.shared.orchestration import FBAReplenishmentOrchestrator
            orchestrator = FBAReplenishmentOrchestrator(session)
            result = await orchestrator.execute_full_replenishment(
                tenant_id=tenant_id, store_id=store_id,
            )
            await session.commit()
            logger.info("orchestration_fba_replenishment_loop_completed", sku_id=sku_id,
                        steps_completed=result.get("steps_completed", []),
                        steps_failed=result.get("steps_failed", []))
    except Exception as e:
        logger.error("orchestration_fba_replenishment_loop_failed", sku_id=sku_id, error=str(e))


async def handle_inbound_flow_trigger(event: DomainEvent) -> None:
    """入库闭环触发: 当采购收货确认时，自动执行入库→库存增加→成本记录闭环"""
    tenant_id = event.tenant_id
    po_id = event.aggregate_id
    to_status = event.payload.get("to_status", "")
    if to_status != "received":
        return
    warehouse_id = event.payload.get("warehouse_id", "")
    items = event.payload.get("items", [])
    if not warehouse_id or not items:
        return
    logger.info("orchestration_inbound_flow_triggered", po_id=po_id,
                action="execute_inbound_orchestration")
    try:
        async with await _get_session() as session:
            from erp.shared.orchestration import InventoryFlowOrchestrator
            orchestrator = InventoryFlowOrchestrator(session)
            result = await orchestrator.execute_inbound_flow(
                tenant_id=tenant_id, warehouse_id=warehouse_id,
                source_type="purchase_order", source_id=po_id, items=items,
            )
            await session.commit()
            logger.info("orchestration_inbound_flow_completed", po_id=po_id,
                        steps_completed=result.get("steps_completed", []),
                        steps_failed=result.get("steps_failed", []))
    except Exception as e:
        logger.error("orchestration_inbound_flow_failed", po_id=po_id, error=str(e))


CROSS_DOMAIN_HANDLERS: dict[str, list] = {
    "erp.oms.order.created.v1": [handle_order_created],
    "erp.oms.order.status_changed.v1": [handle_order_status_changed, handle_sales_loop_trigger],
    "erp.oms.order.risk_detected.v1": [handle_order_risk_detected],
    "erp.oms.order.risk_evaluation.v1": [handle_order_risk_evaluation],
    "erp.oms.refund.created.v1": [handle_refund_created],
    "erp.wms.inventory.adjusted.v1": [handle_inventory_adjusted],
    "erp.wms.inventory.low_stock_alert.v1": [handle_low_stock_alert],
    "erp.wms.inbound.received.v1": [handle_inbound_received],
    "erp.wms.outbound.shipped.v1": [handle_outbound_shipped],
    "erp.wms.stock_transfer.created.v1": [handle_stock_transfer_created],
    "erp.wms.stock_transfer.completed.v1": [handle_stock_transfer_completed],
    "erp.scm.purchase_order.created.v1": [handle_purchase_order_created],
    "erp.scm.purchase_order.status_changed.v1": [handle_purchase_order_status_changed, handle_procurement_loop_trigger, handle_inbound_flow_trigger],
    "erp.scm.supplier.rating_updated.v1": [handle_supplier_rating_updated],
    "erp.scm.consignment.consumption.v1": [handle_consignment_consumption],
    "erp.scm.jit.shipment_created.v1": [handle_jit_shipment_created],
    "erp.scm.vmi.replenishment_triggered.v1": [handle_vmi_replenishment_triggered],
    "erp.scm.centralized.order_created.v1": [handle_centralized_order_created],
    "erp.fba.shipment.status_changed.v1": [handle_fba_shipment_status_changed],
    "erp.fba.inventory.low_stock_alert.v1": [handle_fba_low_stock_alert, handle_fba_replenishment_loop_trigger],
    "erp.fba.exception.created.v1": [handle_fba_exception_created],
    "erp.tms.shipment.status_changed.v1": [handle_shipment_status_changed],
    "erp.fms.cost_event.created.v1": [handle_cost_event_created],
    "erp.fms.settlement.created.v1": [handle_settlement_created],
    "erp.ads.campaign.budget_updated.v1": [handle_campaign_budget_updated],
    "erp.som.listing.price_updated.v1": [handle_listing_price_updated],
    "erp.crm.review.negative_alert.v1": [handle_negative_review_alert],
    "erp.pdm.spu.status_changed.v1": [handle_spu_status_changed],
    "erp.bi.metric.alert_triggered.v1": [handle_metric_alert_triggered],
    "erp.sys.approval.submitted.v1": [handle_approval_submitted],
    "erp.sys.approval.completed.v1": [handle_approval_completed],
}


def register_cross_domain_handlers() -> None:
    publisher = get_event_publisher()
    for event_type, handlers in CROSS_DOMAIN_HANDLERS.items():
        for handler in handlers:
            publisher.subscribe(event_type, handler)
    publisher.subscribe("*", handle_generic_event)
    logger.info(
        "cross_domain_handlers_registered",
        handler_count=sum(len(h) for h in CROSS_DOMAIN_HANDLERS.values()) + 1,
    )
