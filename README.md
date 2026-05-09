# Cross-Border E-commerce ERP

Enterprise-grade AI-powered cross-border e-commerce ERP platform built with **Python/FastAPI + DDD (Domain-Driven Design)** architecture.

> **AI Product Selection Decision Hub** — Integrating 14 business domains with a strategy middle-platform for intelligent, data-driven operations.

---

## Overview

This ERP system is designed for cross-border e-commerce businesses, covering the full lifecycle from product development, procurement, warehousing, logistics, sales, advertising, finance to customer service. It adopts a **DDD layered architecture** with **15 business domain modules** and an **event-driven** async processing model.

| Domain | Abbr | Description |
|--------|------|-------------|
| IAM | Identity & Access Management | User, role, permission, tenant management |
| PDM | Product Development Management | Product listing, development, quality control |
| SOM | Sales Order Management | Order intake, routing, fulfillment orchestration |
| ADS | Advertising Management | Multi-platform ad campaign, bid optimization |
| OMS | Order Management System | End-to-end order processing, lifecycle tracking |
| SCM | Supply Chain Management | Procurement, supplier collaboration, PO management |
| WMS | Warehouse Management System | Inbound, outbound, inventory, FBA reconciliation |
| FBA | FBA Operations | Amazon FBA inbound, storage fee, reconciliation |
| TMS | Transportation Management | Carrier selection, shipping, tracking, freight audit |
| CRM | Customer Relationship Management | After-sales, RMA, reviews, buyer communication |
| FMS | Financial Management System | Cost events, reconciliation, billing, GL integration |
| BI | Business Intelligence | Analytics, dashboards, KPI reporting, data export |
| SYS | System Management | Config, audit log, integration gateway, monitoring |
| Dashboard | Unified Dashboard | Cross-domain aggregated views, executive reports |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Web Framework** | FastAPI + Pydantic v2 |
| **ORM** | SQLAlchemy 2.x (async) + Alembic |
| **Database** | PostgreSQL (schema-per-domain) |
| **Cache** | Redis 7.x |
| **Search** | Elasticsearch 8.x |
| **Object Storage** | MinIO (S3-compatible) |
| **Message Queue** | Kafka / RabbitMQ |
| **Task Queue** | Celery + Redis |
| **Auth / RBAC** | OAuth2 + JWT, 10-dimension data permissions |
| **Logging** | structlog (structured async logging) |
| **Code Quality** | Ruff (lint+format), mypy (type check), bandit (security) |
| **Testing** | pytest, pytest-asyncio, httpx.AsyncClient |
| **Configuration** | pydantic-settings (BaseSettings + .env) |

---

## Architecture

### DDD Layered Structure (per domain module)

```
modules/{domain}/
├── interfaces/          # Interface layer (FastAPI router, Pydantic DTOs)
│   ├── router.py        # Inbound API
│   ├── out_router.py    # Outbound API (external integration callbacks)
│   └── deps.py          # Domain-level dependency injection
├── application/         # Application layer (use case orchestration)
│   ├── dtos.py          # Request/Response models
│   └── services.py      # Application services
├── domain/              # Domain core (pure Python, zero framework deps)
│   ├── models.py        # Aggregate roots, entities (SQLAlchemy mapped)
│   ├── services.py      # Domain services (pure business logic)
│   ├── events.py        # Domain events (dataclass)
│   └── repositories.py  # Repository interfaces (ABC)
└── infrastructure/      # Infrastructure layer
    └── repositories.py  # Repository implementations
```

### Event-Driven Architecture

- **Domain events** are published via an outbox pattern for eventual consistency
- **Kafka topics** follow the naming convention: `erp.{domain}.{aggregate}.{event}.v1`
- **Async workers** (Celery) handle background processing and integration tasks

### Data Permission Model (10 Dimensions)

Tenant isolation → Organization → Department → Store → Marketplace → Channel → Warehouse → Supplier → Category → Data sensitivity level

---

## Key Features

- **AI-Powered Product Selection** — Strategy middle-platform with 15-state recommendation workflow
- **Multi-platform Integration** — Amazon, TikTok, Walmart, and more
- **Finance-First Design** — Cost event sourcing with full audit trail
- **FBA Optimization** — End-to-end FBA inbound and reconciliation
- **Real-time BI** — Cross-domain analytics and KPI dashboards
- **RBAC + 10-Dimension Permissions** — Fine-grained access control

---

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Redis 7.x
- Kafka (optional, for event-driven features)

### Installation

```bash
# Clone the repository
git clone https://github.com/awesome-oversea/cross-border-erp-python.git
cd cross-border-erp-python

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database and service credentials

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn erp.main:app --reload --host 0.0.0.0 --port 8000
```

### Run Tests

```bash
pytest tests/ -v
```

---

## Project Structure

```
├── src/erp/
│   ├── main.py                 # Application entry point
│   ├── bootstrap/              # App bootstrapping & config
│   ├── shared/                 # Shared kernel (auth, audit, cache, db, etc.)
│   ├── middleware/              # Business & technical middle-platforms
│   ├── modules/                # 14 business domain modules
│   ├── connectors/             # External system connectors
│   ├── api/                    # API aggregation layer
│   └── workers/                # Celery async task workers
├── tests/                      # Test suite
├── migrations/                 # Alembic migration scripts
├── docs/adr/                   # Architecture Decision Records
└── deploy/                     # Deployment configs (Docker, K8s, Helm)
```

---

## Documentation

- [Requirements Specification V4](跨境电商ERP——需求规格说明书V4.md) — Latest requirements specification

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
