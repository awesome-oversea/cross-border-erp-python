-- IAM Schema: Tenant, Organization, User, Role, Permission, Audit
CREATE SCHEMA IF NOT EXISTS iam;

-- PDM Schema: Product Development, SPU, SKU, Category, Brand
CREATE SCHEMA IF NOT EXISTS pdm;

-- SOM Schema: Sales Operations, Listing, Channel, Store
CREATE SCHEMA IF NOT EXISTS som;

-- ADS Schema: Advertising, Campaign, Keyword, Budget
CREATE SCHEMA IF NOT EXISTS ads;

-- OMS Schema: Order Management, Sales Order, Channel Order
CREATE SCHEMA IF NOT EXISTS oms;

-- SCM Schema: Supply Chain, Supplier, Purchase Order
CREATE SCHEMA IF NOT EXISTS scm;

-- WMS Schema: Warehouse Management, Location, Stock
CREATE SCHEMA IF NOT EXISTS wms;

-- FBA Schema: FBA/Overseas Warehouse, Shipment
CREATE SCHEMA IF NOT EXISTS fba;

-- TMS Schema: Transport/Logistics, Carrier, Tracking
CREATE SCHEMA IF NOT EXISTS tms;

-- CRM Schema: Customer Service, After-sale, Refund
CREATE SCHEMA IF NOT EXISTS crm;

-- FMS Schema: Financial Management, Billing, Cost, Profit
CREATE SCHEMA IF NOT EXISTS fms;

-- BI Schema: Business Intelligence, KPI, Dashboard
CREATE SCHEMA IF NOT EXISTS bi;

-- SYS Schema: System Settings, Parameters, Templates
CREATE SCHEMA IF NOT EXISTS sys;

-- DASHBOARD Schema: Dashboard, Widgets, Layout
CREATE SCHEMA IF NOT EXISTS dashboard;

-- INTEGRATION Schema: Connector, Outbox, Inbox, Idempotency
CREATE SCHEMA IF NOT EXISTS integration;
