from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class QueryScope(StrEnum):
    READ_BASIC = "read:basic"
    READ_FINANCIAL = "read:financial"
    READ_INVENTORY = "read:inventory"
    READ_CUSTOMER = "read:customer"
    READ_ADVERTISING = "read:advertising"
    READ_LOGISTICS = "read:logistics"
    READ_FULL = "read:full"


class PMSDataQueryPolicy(Base):
    __tablename__ = "pms_data_query_policy"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    policy_name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    allowed_scopes: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    allowed_fields: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    masked_fields: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    denied_fields: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    row_filter_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    max_rows_per_query: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PMSDataQueryLog(Base):
    __tablename__ = "pms_data_query_log"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    pms_client_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    query_domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    query_scope: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    query_type: Mapped[str] = mapped_column(String(50), nullable=False)
    filters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    requested_fields: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    returned_fields: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    masked_fields: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PMSDataQueryService:
    FIELD_MASKS = {
        "buyer_email": "***@***.***",
        "buyer_phone": "***-****-****",
        "buyer_name": "***",
        "address_line1": "***",
        "address_line2": "***",
        "cost_price": "***",
        "purchase_price": "***",
        "profit_margin": "***",
        "supplier_contact": "***",
        "supplier_phone": "***",
        "payment_info": "***",
        "bank_account": "***",
    }

    DOMAIN_FIELDS = {
        "pdm": {
            "basic": ["id", "code", "name", "category_name", "brand_name", "status", "created_at"],
            "financial": ["cost_price", "cost_currency", "purchase_price"],
            "inventory": ["qty_on_hand", "qty_available", "qty_reserved"],
        },
        "oms": {
            "basic": ["id", "order_no", "platform", "status", "order_date", "currency", "total_amount"],
            "financial": ["item_price", "shipping_fee", "discount_amount", "tax_amount"],
            "customer": ["buyer_id", "buyer_name", "buyer_email", "ship_country"],
            "logistics": ["tracking_number", "carrier", "shipping_method", "shipped_at"],
        },
        "wms": {
            "basic": ["id", "warehouse_name", "warehouse_code", "warehouse_type", "is_active"],
            "inventory": ["sku_id", "sku_code", "qty_on_hand", "qty_available", "qty_reserved", "qty_inbound"],
        },
        "scm": {
            "basic": ["id", "supplier_name", "supplier_code", "status", "rating"],
            "financial": ["purchase_price", "currency", "payment_terms"],
        },
        "fms": {
            "basic": ["id", "cost_type", "amount", "currency", "cost_date"],
            "financial": ["profit_amount", "profit_margin", "revenue", "total_cost"],
        },
        "ads": {
            "basic": ["id", "campaign_name", "status", "budget", "bid"],
            "advertising": ["impressions", "clicks", "spend", "orders", "acos", "roas", "ctr", "cr"],
        },
        "crm": {
            "basic": ["id", "customer_name", "status", "created_at"],
            "customer": ["email", "phone", "total_orders", "total_revenue", "lifecycle_stage"],
        },
        "tms": {
            "basic": ["id", "carrier_name", "tracking_number", "status"],
            "logistics": ["origin", "destination", "weight", "shipping_cost", "delivered_at"],
        },
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_policy(self, tenant_id: str, policy_name: str, domain: str,
                             allowed_scopes: list[str] | None = None,
                             allowed_fields: list[str] | None = None,
                             masked_fields: list[str] | None = None,
                             denied_fields: list[str] | None = None,
                             row_filter: dict | None = None,
                             max_rows_per_query: int = 1000) -> PMSDataQueryPolicy:
        policy = PMSDataQueryPolicy(
            tenant_id=tenant_id, policy_name=policy_name, domain=domain,
            allowed_scopes=json.dumps(allowed_scopes or [], default=str),
            allowed_fields=json.dumps(allowed_fields or [], default=str),
            masked_fields=json.dumps(masked_fields or [], default=str),
            denied_fields=json.dumps(denied_fields or [], default=str),
            row_filter_json=json.dumps(row_filter or {}, default=str),
            max_rows_per_query=max_rows_per_query,
            created_by=actor_id_var.get(""),
        )
        self.session.add(policy)
        await self.session.flush()
        return policy

    async def init_default_policies(self, tenant_id: str) -> list[PMSDataQueryPolicy]:
        defaults = [
            ("PDM基础查询", "pdm", ["read:basic", "read:inventory"],
             ["id", "code", "name", "category_name", "brand_name", "status", "qty_on_hand", "qty_available"],
             ["cost_price", "purchase_price"], ["supplier_id"]),
            ("OMS基础查询", "oms", ["read:basic", "read:logistics"],
             ["id", "order_no", "platform", "status", "order_date", "total_amount", "tracking_number", "carrier"],
             ["buyer_email", "buyer_phone", "buyer_name", "address_line1", "address_line2"],
             ["payment_info", "bank_account"]),
            ("WMS基础查询", "wms", ["read:basic", "read:inventory"],
             ["id", "warehouse_name", "warehouse_code", "sku_id", "qty_on_hand", "qty_available"],
             [], []),
            ("FMS基础查询", "fms", ["read:basic"],
             ["id", "cost_type", "amount", "currency", "cost_date"],
             ["profit_margin"], ["bank_account"]),
            ("ADS基础查询", "ads", ["read:basic", "read:advertising"],
             ["id", "campaign_name", "status", "budget", "impressions", "clicks", "spend", "acos", "roas"],
             [], []),
            ("CRM基础查询", "crm", ["read:basic"],
             ["id", "customer_name", "status", "total_orders", "lifecycle_stage"],
             ["email", "phone"], []),
            ("SCM基础查询", "scm", ["read:basic"],
             ["id", "supplier_name", "supplier_code", "status", "rating"],
             ["supplier_contact", "supplier_phone"], []),
            ("TMS基础查询", "tms", ["read:basic", "read:logistics"],
             ["id", "carrier_name", "tracking_number", "status", "shipping_cost"],
             [], []),
        ]
        policies = []
        for name, domain, scopes, allowed, masked, denied in defaults:
            p = await self.create_policy(
                tenant_id=tenant_id, policy_name=name, domain=domain,
                allowed_scopes=scopes, allowed_fields=allowed,
                masked_fields=masked, denied_fields=denied,
            )
            policies.append(p)
        return policies

    async def query_data(self, tenant_id: str, pms_client_id: str, domain: str,
                          query_scope: str, query_type: str = "list",
                          filters: dict | None = None,
                          requested_fields: list[str] | None = None,
                          page: int = 1, page_size: int = 20) -> dict:
        start = datetime.now(UTC)

        policy = await self._get_policy(tenant_id, domain)
        if not policy or not policy.is_active:
            await self._log_query(tenant_id, pms_client_id, domain, query_scope,
                                   query_type, filters, requested_fields, [], [],
                                   0, False, "No active policy for domain", 0)
            raise ValidationException(message=f"No active query policy for domain '{domain}'")

        allowed_scopes = json.loads(policy.allowed_scopes)
        if query_scope not in allowed_scopes and QueryScope.READ_FULL.value not in allowed_scopes:
            await self._log_query(tenant_id, pms_client_id, domain, query_scope,
                                   query_type, filters, requested_fields, [], [],
                                   0, False, f"Scope '{query_scope}' not allowed", 0)
            raise ValidationException(message=f"Scope '{query_scope}' not allowed for domain '{domain}'")

        allowed_fields = json.loads(policy.allowed_fields)
        masked_fields = json.loads(policy.masked_fields)
        denied_fields = json.loads(policy.denied_fields)

        if requested_fields:
            effective_fields = [f for f in requested_fields if f not in denied_fields]
            if allowed_fields:
                effective_fields = [f for f in effective_fields if f in allowed_fields or f in masked_fields]
        else:
            effective_fields = allowed_fields if allowed_fields else []

        max_rows = min(page_size, policy.max_rows_per_query)

        domain_fields = self.DOMAIN_FIELDS.get(domain, {})
        scope_fields = []
        for scope_key in [query_scope.replace("read:", ""), "basic"]:
            if scope_key in domain_fields:
                scope_fields = domain_fields[scope_key]
                break

        if not effective_fields:
            effective_fields = scope_fields

        effective_fields = [f for f in effective_fields if f not in denied_fields]

        sample_data = self._generate_sample_data(domain, effective_fields, masked_fields, max_rows)

        returned_masked = [f for f in effective_fields if f in masked_fields]

        duration = int((datetime.now(UTC) - start).total_seconds() * 1000)
        await self._log_query(
            tenant_id, pms_client_id, domain, query_scope, query_type,
            filters, requested_fields or [], effective_fields, returned_masked,
            len(sample_data), True, "", duration,
        )

        return {
            "domain": domain,
            "scope": query_scope,
            "fields": effective_fields,
            "masked_fields": returned_masked,
            "data": sample_data,
            "pagination": {
                "page": page, "page_size": max_rows,
                "total": len(sample_data),
            },
        }

    async def list_policies(self, tenant_id: str, domain: str = "") -> list[dict]:
        conditions = [PMSDataQueryPolicy.tenant_id == tenant_id]
        if domain:
            conditions.append(PMSDataQueryPolicy.domain == domain)
        stmt = select(PMSDataQueryPolicy).where(*conditions).order_by(PMSDataQueryPolicy.domain)
        result = await self.session.execute(stmt)
        policies = list(result.scalars().all())
        return [{
            "id": p.id, "policy_name": p.policy_name, "domain": p.domain,
            "allowed_scopes": json.loads(p.allowed_scopes),
            "allowed_fields": json.loads(p.allowed_fields),
            "masked_fields": json.loads(p.masked_fields),
            "denied_fields": json.loads(p.denied_fields),
            "max_rows_per_query": p.max_rows_per_query,
            "is_active": p.is_active,
        } for p in policies]

    async def list_query_logs(self, tenant_id: str, domain: str = "",
                               pms_client_id: str = "",
                               page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        conditions = [PMSDataQueryLog.tenant_id == tenant_id]
        if domain:
            conditions.append(PMSDataQueryLog.query_domain == domain)
        if pms_client_id:
            conditions.append(PMSDataQueryLog.pms_client_id == pms_client_id)

        stmt = select(PMSDataQueryLog).where(*conditions).order_by(PMSDataQueryLog.created_at.desc())
        total_result = await self.session.execute(
            select(func.count()).select_from(PMSDataQueryLog).where(*conditions)
        )
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(stmt.offset(offset).limit(page_size))
        logs = list(result.scalars().all())
        return [{
            "id": log.id, "pms_client_id": log.pms_client_id,
            "query_domain": log.query_domain, "query_scope": log.query_scope,
            "query_type": log.query_type, "row_count": log.row_count,
            "is_success": log.is_success, "duration_ms": log.duration_ms,
            "masked_fields": json.loads(log.masked_fields) if log.masked_fields else [],
            "created_at": log.created_at.isoformat() if log.created_at else None,
        } for log in logs], total

    def _generate_sample_data(self, domain: str, fields: list[str],
                               masked_fields: list[str], count: int) -> list[dict]:
        rows = []
        for i in range(min(count, 3)):
            row = {}
            for f in fields:
                if f in masked_fields:
                    row[f] = self.FIELD_MASKS.get(f, "***")
                elif "id" in f:
                    row[f] = str(uuid.uuid4())[:8]
                elif "name" in f:
                    row[f] = f"Sample_{f}_{i+1}"
                elif "code" in f:
                    row[f] = f"CODE-{i+1:04d}"
                elif "qty" in f or "count" in f or "impressions" in f or "clicks" in f or "orders" in f:
                    row[f] = i * 10 + 5
                elif "amount" in f or "price" in f or "cost" in f or "fee" in f or "spend" in f or "budget" in f:
                    row[f] = round((i + 1) * 15.5, 2)
                elif "rate" in f or "margin" in f or "acos" in f or "roas" in f or "ctr" in f or "cr" in f:
                    row[f] = round((i + 1) * 3.5, 2)
                elif "status" in f:
                    row[f] = "active"
                elif "date" in f or "_at" in f:
                    row[f] = datetime.now(UTC).isoformat()[:10]
                elif "currency" in f:
                    row[f] = "USD"
                elif "platform" in f:
                    row[f] = "amazon"
                elif "country" in f:
                    row[f] = "US"
                elif "type" in f:
                    row[f] = "standard"
                elif "rating" in f:
                    row[f] = 4.5
                else:
                    row[f] = f"val_{i+1}"
            rows.append(row)
        return rows

    async def _log_query(self, tenant_id: str, pms_client_id: str, domain: str,
                          scope: str, query_type: str, filters: dict | None,
                          requested_fields: list[str], returned_fields: list[str],
                          masked_fields: list[str], row_count: int,
                          is_success: bool, error_message: str, duration_ms: int):
        log = PMSDataQueryLog(
            tenant_id=tenant_id, pms_client_id=pms_client_id,
            query_domain=domain, query_scope=scope, query_type=query_type,
            filters_json=json.dumps(filters or {}, default=str),
            requested_fields=json.dumps(requested_fields, default=str),
            returned_fields=json.dumps(returned_fields, default=str),
            masked_fields=json.dumps(masked_fields, default=str),
            row_count=row_count, is_success=is_success,
            error_message=error_message, duration_ms=duration_ms,
            trace_id=trace_id_var.get(""),
        )
        self.session.add(log)
        await self.session.flush()

    async def _get_policy(self, tenant_id: str, domain: str) -> PMSDataQueryPolicy | None:
        stmt = select(PMSDataQueryPolicy).where(
            PMSDataQueryPolicy.tenant_id == tenant_id,
            PMSDataQueryPolicy.domain == domain,
            PMSDataQueryPolicy.is_active,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
