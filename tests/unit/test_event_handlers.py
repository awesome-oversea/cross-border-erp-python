from __future__ import annotations

import pytest

from erp.shared.events.domain_event import DomainEvent
from erp.shared.events.handlers import (
    CROSS_DOMAIN_HANDLERS,
    handle_approval_completed,
    handle_approval_submitted,
    handle_campaign_budget_updated,
    handle_cost_event_created,
    handle_fba_low_stock_alert,
    handle_fba_shipment_status_changed,
    handle_generic_event,
    handle_inbound_received,
    handle_inventory_adjusted,
    handle_listing_price_updated,
    handle_low_stock_alert,
    handle_metric_alert_triggered,
    handle_negative_review_alert,
    handle_order_created,
    handle_order_risk_detected,
    handle_order_status_changed,
    handle_outbound_shipped,
    handle_purchase_order_created,
    handle_purchase_order_status_changed,
    handle_refund_created,
    handle_settlement_created,
    handle_shipment_status_changed,
    handle_spu_status_changed,
    handle_supplier_rating_updated,
)
from erp.shared.events.publisher import EventPublisher


@pytest.fixture
def publisher():
    pub = EventPublisher()
    return pub


class TestOrderCreatedHandler:
    @pytest.mark.asyncio
    async def test_handle_order_created(self):
        event = DomainEvent(
            event_type="erp.oms.order.created.v1",
            domain="oms",
            aggregate_type="sales_order",
            aggregate_id="order-001",
            payload={"order_no": "ORD-001", "platform": "amazon"},
        )
        await handle_order_created(event)

    @pytest.mark.asyncio
    async def test_handle_order_created_with_empty_payload(self):
        event = DomainEvent(
            event_type="erp.oms.order.created.v1",
            domain="oms",
            aggregate_id="order-002",
        )
        await handle_order_created(event)


class TestOrderStatusChangedHandler:
    @pytest.mark.asyncio
    async def test_handle_order_shipped(self):
        event = DomainEvent(
            event_type="erp.oms.order.status_changed.v1",
            domain="oms",
            aggregate_id="order-001",
            payload={"to_status": "shipped"},
        )
        await handle_order_status_changed(event)

    @pytest.mark.asyncio
    async def test_handle_order_delivered(self):
        event = DomainEvent(
            event_type="erp.oms.order.status_changed.v1",
            domain="oms",
            aggregate_id="order-001",
            payload={"to_status": "delivered"},
        )
        await handle_order_status_changed(event)

    @pytest.mark.asyncio
    async def test_handle_order_cancelled(self):
        event = DomainEvent(
            event_type="erp.oms.order.status_changed.v1",
            domain="oms",
            aggregate_id="order-001",
            payload={"to_status": "cancelled"},
        )
        await handle_order_status_changed(event)

    @pytest.mark.asyncio
    async def test_handle_order_pending(self):
        event = DomainEvent(
            event_type="erp.oms.order.status_changed.v1",
            domain="oms",
            aggregate_id="order-001",
            payload={"to_status": "pending"},
        )
        await handle_order_status_changed(event)


class TestOrderRiskDetectedHandler:
    @pytest.mark.asyncio
    async def test_handle_high_risk(self):
        event = DomainEvent(
            event_type="erp.oms.order.risk_detected.v1",
            domain="oms",
            aggregate_id="order-001",
            payload={"risk_level": "high", "risk_type": "fraud"},
        )
        await handle_order_risk_detected(event)

    @pytest.mark.asyncio
    async def test_handle_medium_risk(self):
        event = DomainEvent(
            event_type="erp.oms.order.risk_detected.v1",
            domain="oms",
            aggregate_id="order-001",
            payload={"risk_level": "medium"},
        )
        await handle_order_risk_detected(event)


class TestInventoryAdjustedHandler:
    @pytest.mark.asyncio
    async def test_handle_low_stock_after_adjustment(self):
        event = DomainEvent(
            event_type="erp.wms.inventory.adjusted.v1",
            domain="wms",
            aggregate_id="inv-001",
            payload={"sku_id": "SKU-001", "qty_after": 5, "safety_qty": 10},
        )
        await handle_inventory_adjusted(event)

    @pytest.mark.asyncio
    async def test_handle_sufficient_stock(self):
        event = DomainEvent(
            event_type="erp.wms.inventory.adjusted.v1",
            domain="wms",
            aggregate_id="inv-002",
            payload={"sku_id": "SKU-002", "qty_after": 100, "safety_qty": 10},
        )
        await handle_inventory_adjusted(event)


class TestLowStockAlertHandler:
    @pytest.mark.asyncio
    async def test_handle_low_stock_alert(self):
        event = DomainEvent(
            event_type="erp.wms.inventory.low_stock_alert.v1",
            domain="wms",
            aggregate_id="inv-001",
            payload={"sku_id": "SKU-001", "available_qty": 3, "safety_qty": 10},
        )
        await handle_low_stock_alert(event)


class TestInboundReceivedHandler:
    @pytest.mark.asyncio
    async def test_handle_inbound_received(self):
        event = DomainEvent(
            event_type="erp.wms.inbound.received.v1",
            domain="wms",
            aggregate_id="inbound-001",
            payload={"inbound_no": "INB-001", "warehouse_id": "WH-001"},
        )
        await handle_inbound_received(event)


class TestOutboundShippedHandler:
    @pytest.mark.asyncio
    async def test_handle_outbound_shipped(self):
        event = DomainEvent(
            event_type="erp.wms.outbound.shipped.v1",
            domain="wms",
            aggregate_id="outbound-001",
            payload={"outbound_no": "OUT-001", "tracking_no": "TRK-001"},
        )
        await handle_outbound_shipped(event)


class TestRefundCreatedHandler:
    @pytest.mark.asyncio
    async def test_handle_refund_created(self):
        event = DomainEvent(
            event_type="erp.oms.refund.created.v1",
            domain="oms",
            aggregate_id="refund-001",
            payload={"refund_no": "REF-001", "refund_amount": 99.99},
        )
        await handle_refund_created(event)


class TestPurchaseOrderHandler:
    @pytest.mark.asyncio
    async def test_handle_po_created(self):
        event = DomainEvent(
            event_type="erp.scm.purchase_order.created.v1",
            domain="scm",
            aggregate_id="po-001",
            payload={"supplier_id": "sup-001"},
        )
        await handle_purchase_order_created(event)

    @pytest.mark.asyncio
    async def test_handle_po_received(self):
        event = DomainEvent(
            event_type="erp.scm.purchase_order.status_changed.v1",
            domain="scm",
            aggregate_id="po-001",
            payload={"to_status": "received"},
        )
        await handle_purchase_order_status_changed(event)

    @pytest.mark.asyncio
    async def test_handle_po_cancelled(self):
        event = DomainEvent(
            event_type="erp.scm.purchase_order.status_changed.v1",
            domain="scm",
            aggregate_id="po-001",
            payload={"to_status": "cancelled"},
        )
        await handle_purchase_order_status_changed(event)

    @pytest.mark.asyncio
    async def test_handle_supplier_low_rating(self):
        event = DomainEvent(
            event_type="erp.scm.supplier.rating_updated.v1",
            domain="scm",
            aggregate_id="sup-001",
            payload={"new_rating": 2.5, "old_rating": 4.0},
        )
        await handle_supplier_rating_updated(event)

    @pytest.mark.asyncio
    async def test_handle_supplier_normal_rating(self):
        event = DomainEvent(
            event_type="erp.scm.supplier.rating_updated.v1",
            domain="scm",
            aggregate_id="sup-001",
            payload={"new_rating": 4.0, "old_rating": 3.5},
        )
        await handle_supplier_rating_updated(event)


class TestFbaShipmentHandler:
    @pytest.mark.asyncio
    async def test_handle_fba_received(self):
        event = DomainEvent(
            event_type="erp.fba.shipment.status_changed.v1",
            domain="fba",
            aggregate_id="fba-001",
            payload={"to_status": "received"},
        )
        await handle_fba_shipment_status_changed(event)

    @pytest.mark.asyncio
    async def test_handle_fba_shipped(self):
        event = DomainEvent(
            event_type="erp.fba.shipment.status_changed.v1",
            domain="fba",
            aggregate_id="fba-001",
            payload={"to_status": "shipped"},
        )
        await handle_fba_shipment_status_changed(event)

    @pytest.mark.asyncio
    async def test_handle_fba_low_stock(self):
        event = DomainEvent(
            event_type="erp.fba.inventory.low_stock_alert.v1",
            domain="fba",
            aggregate_id="fba-inv-001",
            payload={"sku_id": "SKU-001", "qty_fulfillable": 5},
        )
        await handle_fba_low_stock_alert(event)


class TestTmsShipmentHandler:
    @pytest.mark.asyncio
    async def test_handle_shipment_delivered(self):
        event = DomainEvent(
            event_type="erp.tms.shipment.status_changed.v1",
            domain="tms",
            aggregate_id="ship-001",
            payload={"to_status": "delivered"},
        )
        await handle_shipment_status_changed(event)

    @pytest.mark.asyncio
    async def test_handle_shipment_exception(self):
        event = DomainEvent(
            event_type="erp.tms.shipment.status_changed.v1",
            domain="tms",
            aggregate_id="ship-001",
            payload={"to_status": "exception"},
        )
        await handle_shipment_status_changed(event)

    @pytest.mark.asyncio
    async def test_handle_shipment_in_transit(self):
        event = DomainEvent(
            event_type="erp.tms.shipment.status_changed.v1",
            domain="tms",
            aggregate_id="ship-001",
            payload={"to_status": "in_transit"},
        )
        await handle_shipment_status_changed(event)


class TestFmsHandler:
    @pytest.mark.asyncio
    async def test_handle_cost_event_created(self):
        event = DomainEvent(
            event_type="erp.fms.cost_event.created.v1",
            domain="fms",
            aggregate_id="cost-001",
            payload={"cost_type": "logistics"},
        )
        await handle_cost_event_created(event)

    @pytest.mark.asyncio
    async def test_handle_settlement_created(self):
        event = DomainEvent(
            event_type="erp.fms.settlement.created.v1",
            domain="fms",
            aggregate_id="settle-001",
            payload={"platform": "amazon"},
        )
        await handle_settlement_created(event)


class TestAdsHandler:
    @pytest.mark.asyncio
    async def test_handle_budget_surge(self):
        event = DomainEvent(
            event_type="erp.ads.campaign.budget_updated.v1",
            domain="ads",
            aggregate_id="camp-001",
            payload={"old_budget": 100.0, "new_budget": 200.0},
        )
        await handle_campaign_budget_updated(event)

    @pytest.mark.asyncio
    async def test_handle_normal_budget_change(self):
        event = DomainEvent(
            event_type="erp.ads.campaign.budget_updated.v1",
            domain="ads",
            aggregate_id="camp-001",
            payload={"old_budget": 100.0, "new_budget": 120.0},
        )
        await handle_campaign_budget_updated(event)


class TestSomHandler:
    @pytest.mark.asyncio
    async def test_handle_price_drop(self):
        event = DomainEvent(
            event_type="erp.som.listing.price_updated.v1",
            domain="som",
            aggregate_id="list-001",
            payload={"old_price": 100.0, "new_price": 70.0},
        )
        await handle_listing_price_updated(event)

    @pytest.mark.asyncio
    async def test_handle_normal_price_change(self):
        event = DomainEvent(
            event_type="erp.som.listing.price_updated.v1",
            domain="som",
            aggregate_id="list-001",
            payload={"old_price": 100.0, "new_price": 95.0},
        )
        await handle_listing_price_updated(event)


class TestCrmHandler:
    @pytest.mark.asyncio
    async def test_handle_negative_review(self):
        event = DomainEvent(
            event_type="erp.crm.review.negative_alert.v1",
            domain="crm",
            aggregate_id="rev-001",
            payload={"rating": 1, "sku_id": "SKU-001"},
        )
        await handle_negative_review_alert(event)


class TestPdmHandler:
    @pytest.mark.asyncio
    async def test_handle_product_discontinued(self):
        event = DomainEvent(
            event_type="erp.pdm.spu.status_changed.v1",
            domain="pdm",
            aggregate_id="spu-001",
            payload={"to_status": "discontinued"},
        )
        await handle_spu_status_changed(event)

    @pytest.mark.asyncio
    async def test_handle_product_active(self):
        event = DomainEvent(
            event_type="erp.pdm.spu.status_changed.v1",
            domain="pdm",
            aggregate_id="spu-001",
            payload={"to_status": "active"},
        )
        await handle_spu_status_changed(event)


class TestBiHandler:
    @pytest.mark.asyncio
    async def test_handle_metric_alert(self):
        event = DomainEvent(
            event_type="erp.bi.metric.alert_triggered.v1",
            domain="bi",
            aggregate_id="metric-001",
            payload={"metric_code": "revenue", "alert_type": "below_threshold", "actual_value": 500.0},
        )
        await handle_metric_alert_triggered(event)


class TestSysHandler:
    @pytest.mark.asyncio
    async def test_handle_approval_submitted(self):
        event = DomainEvent(
            event_type="erp.sys.approval.submitted.v1",
            domain="sys",
            aggregate_id="appr-001",
            payload={"approval_type": "purchase_order"},
        )
        await handle_approval_submitted(event)

    @pytest.mark.asyncio
    async def test_handle_approval_approved(self):
        event = DomainEvent(
            event_type="erp.sys.approval.completed.v1",
            domain="sys",
            aggregate_id="appr-001",
            payload={"result": "approved", "business_id": "po-001"},
        )
        await handle_approval_completed(event)

    @pytest.mark.asyncio
    async def test_handle_approval_rejected(self):
        event = DomainEvent(
            event_type="erp.sys.approval.completed.v1",
            domain="sys",
            aggregate_id="appr-001",
            payload={"result": "rejected"},
        )
        await handle_approval_completed(event)


class TestGenericEventHandler:
    @pytest.mark.asyncio
    async def test_handle_generic_event(self):
        event = DomainEvent(
            event_type="erp.pdm.product.created.v1",
            domain="pdm",
            aggregate_id="product-001",
        )
        await handle_generic_event(event)


class TestCrossDomainHandlerRegistration:
    def test_handler_registry_not_empty(self):
        assert len(CROSS_DOMAIN_HANDLERS) > 0

    def test_all_domains_covered(self):
        domains = set()
        for key in CROSS_DOMAIN_HANDLERS:
            parts = key.split(".")
            if len(parts) >= 2:
                domains.add(parts[1])
        expected = {"oms", "wms", "scm", "fba", "tms", "fms", "ads", "som", "crm", "pdm", "bi", "sys"}
        assert expected.issubset(domains), f"Missing domains: {expected - domains}"

    def test_order_created_handler_registered(self):
        assert "erp.oms.order.created.v1" in CROSS_DOMAIN_HANDLERS
        assert handle_order_created in CROSS_DOMAIN_HANDLERS["erp.oms.order.created.v1"]

    def test_order_status_changed_handler_registered(self):
        assert "erp.oms.order.status_changed.v1" in CROSS_DOMAIN_HANDLERS

    def test_inventory_adjusted_handler_registered(self):
        assert "erp.wms.inventory.adjusted.v1" in CROSS_DOMAIN_HANDLERS

    def test_scm_handlers_registered(self):
        assert "erp.scm.purchase_order.created.v1" in CROSS_DOMAIN_HANDLERS
        assert "erp.scm.purchase_order.status_changed.v1" in CROSS_DOMAIN_HANDLERS
        assert "erp.scm.supplier.rating_updated.v1" in CROSS_DOMAIN_HANDLERS

    def test_fba_handlers_registered(self):
        assert "erp.fba.shipment.status_changed.v1" in CROSS_DOMAIN_HANDLERS
        assert "erp.fba.inventory.low_stock_alert.v1" in CROSS_DOMAIN_HANDLERS

    def test_tms_handlers_registered(self):
        assert "erp.tms.shipment.status_changed.v1" in CROSS_DOMAIN_HANDLERS

    def test_fms_handlers_registered(self):
        assert "erp.fms.cost_event.created.v1" in CROSS_DOMAIN_HANDLERS
        assert "erp.fms.settlement.created.v1" in CROSS_DOMAIN_HANDLERS

    def test_ads_handlers_registered(self):
        assert "erp.ads.campaign.budget_updated.v1" in CROSS_DOMAIN_HANDLERS

    def test_som_handlers_registered(self):
        assert "erp.som.listing.price_updated.v1" in CROSS_DOMAIN_HANDLERS

    def test_crm_handlers_registered(self):
        assert "erp.crm.review.negative_alert.v1" in CROSS_DOMAIN_HANDLERS

    def test_pdm_handlers_registered(self):
        assert "erp.pdm.spu.status_changed.v1" in CROSS_DOMAIN_HANDLERS

    def test_bi_handlers_registered(self):
        assert "erp.bi.metric.alert_triggered.v1" in CROSS_DOMAIN_HANDLERS

    def test_sys_handlers_registered(self):
        assert "erp.sys.approval.submitted.v1" in CROSS_DOMAIN_HANDLERS
        assert "erp.sys.approval.completed.v1" in CROSS_DOMAIN_HANDLERS

    def test_register_cross_domain_handlers(self):
        publisher = EventPublisher()
        original_subscribe = publisher.subscribe
        calls = []
        publisher.subscribe = lambda et, h: (calls.append((et, h)), original_subscribe(et, h))

        for event_type, handlers in CROSS_DOMAIN_HANDLERS.items():
            for handler in handlers:
                publisher.subscribe(event_type, handler)
        publisher.subscribe("*", handle_generic_event)

        event_types = set(c for c, _ in calls)
        assert "erp.oms.order.created.v1" in event_types
        assert "erp.wms.inventory.adjusted.v1" in event_types
        assert "*" in event_types


class TestEventPublisherWithHandlers:
    @pytest.mark.asyncio
    async def test_publish_order_created_triggers_handler(self):
        publisher = EventPublisher()
        received = []
        publisher.subscribe("erp.oms.order.created.v1", lambda e: received.append(e))

        event = DomainEvent(
            event_type="erp.oms.order.created.v1",
            domain="oms",
            aggregate_id="order-001",
        )
        await publisher.publish(event)
        assert len(received) == 1
        assert received[0].aggregate_id == "order-001"

    @pytest.mark.asyncio
    async def test_publish_with_wildcard_handler(self):
        publisher = EventPublisher()
        received = []
        publisher.subscribe("*", lambda e: received.append(e.event_type))

        event = DomainEvent(
            event_type="erp.pdm.product.created.v1",
            domain="pdm",
            aggregate_id="prod-001",
        )
        await publisher.publish(event)
        assert "erp.pdm.product.created.v1" in received

    @pytest.mark.asyncio
    async def test_publish_multiple_handlers(self):
        publisher = EventPublisher()
        results = []
        publisher.subscribe("erp.oms.order.created.v1", lambda e: results.append("handler1"))
        publisher.subscribe("erp.oms.order.created.v1", lambda e: results.append("handler2"))

        event = DomainEvent(
            event_type="erp.oms.order.created.v1",
            domain="oms",
        )
        await publisher.publish(event)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_handler_error_does_not_stop_others(self):
        publisher = EventPublisher()
        results = []

        async def failing_handler(e):
            raise ValueError("test error")

        publisher.subscribe("test.event", failing_handler)
        publisher.subscribe("test.event", lambda e: results.append("success"))

        event = DomainEvent(event_type="test.event")
        await publisher.publish(event)
        assert "success" in results

    @pytest.mark.asyncio
    async def test_outbox_entries(self):
        publisher = EventPublisher()
        event = DomainEvent(event_type="test.event", domain="test", payload={"key": "value"})
        await publisher.publish(event)

        entries = publisher.get_outbox_entries()
        assert len(entries) == 1
        assert entries[0]["event_type"] == "test.event"
        assert entries[0]["domain"] == "test"

    @pytest.mark.asyncio
    async def test_clear_outbox(self):
        publisher = EventPublisher()
        event = DomainEvent(event_type="test.event")
        await publisher.publish(event)
        publisher.clear_outbox()
        assert len(publisher.get_outbox_entries()) == 0

    @pytest.mark.asyncio
    async def test_publish_many(self):
        publisher = EventPublisher()
        received = []
        publisher.subscribe("*", lambda e: received.append(e.event_type))

        events = [
            DomainEvent(event_type="event.1"),
            DomainEvent(event_type="event.2"),
            DomainEvent(event_type="event.3"),
        ]
        await publisher.publish_many(events)
        assert len(received) == 3
