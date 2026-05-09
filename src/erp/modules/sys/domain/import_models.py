from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import NotFoundException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ImportType(StrEnum):
    ORDER = "order"
    SETTLEMENT = "settlement"
    INVENTORY = "inventory"
    TRACKING = "tracking"
    LISTING = "listing"
    PRODUCT = "product"
    SUPPLIER = "supplier"
    COST = "cost"


class ImportStatus(StrEnum):
    PENDING = "pending"
    VALIDATING = "validating"
    IMPORTING = "importing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ImportTemplate(Base):
    __tablename__ = "import_template"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    import_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    columns_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    required_columns: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    validation_rules_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    sample_file_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ImportJob(Base):
    __tablename__ = "import_job"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    job_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    import_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    file_name: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    file_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    error_file_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    error_summary: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    import_options_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ImportRowError(Base):
    __tablename__ = "import_row_error"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    row_data: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error_type: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[str] = mapped_column(String(500), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ImportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_template(self, tenant_id: str, template_name: str, import_type: str,
                               columns: list[dict], required_columns: list[str] | None = None,
                               validation_rules: dict | None = None,
                               description: str = "") -> ImportTemplate:
        template = ImportTemplate(
            tenant_id=tenant_id, template_name=template_name,
            import_type=import_type, description=description,
            columns_json=json.dumps(columns, default=str),
            required_columns=json.dumps(required_columns or [], default=str),
            validation_rules_json=json.dumps(validation_rules or {}, default=str),
            created_by=actor_id_var.get(""),
        )
        self.session.add(template)
        await self.session.flush()
        return template

    async def init_default_templates(self, tenant_id: str) -> list[ImportTemplate]:
        defaults = [
            {
                "name": "订单导入模板", "type": ImportType.ORDER.value,
                "columns": [
                    {"name": "order_id", "label": "平台订单号", "type": "string", "required": True},
                    {"name": "platform", "label": "平台", "type": "string", "required": True},
                    {"name": "order_date", "label": "下单时间", "type": "datetime", "required": True},
                    {"name": "buyer_id", "label": "买家ID", "type": "string", "required": False},
                    {"name": "sku", "label": "SKU", "type": "string", "required": True},
                    {"name": "quantity", "label": "数量", "type": "integer", "required": True},
                    {"name": "unit_price", "label": "单价", "type": "number", "required": True},
                    {"name": "currency", "label": "币种", "type": "string", "required": True},
                    {"name": "shipping_fee", "label": "运费", "type": "number", "required": False},
                    {"name": "shipping_address", "label": "收货地址", "type": "string", "required": False},
                    {"name": "tracking_number", "label": "追踪号", "type": "string", "required": False},
                ],
                "required": ["order_id", "platform", "order_date", "sku", "quantity", "unit_price", "currency"],
            },
            {
                "name": "账单导入模板", "type": ImportType.SETTLEMENT.value,
                "columns": [
                    {"name": "settlement_id", "label": "结算ID", "type": "string", "required": True},
                    {"name": "platform", "label": "平台", "type": "string", "required": True},
                    {"name": "settlement_date", "label": "结算日期", "type": "date", "required": True},
                    {"name": "order_id", "label": "订单号", "type": "string", "required": True},
                    {"name": "type", "label": "类型", "type": "string", "required": True},
                    {"name": "amount", "label": "金额", "type": "number", "required": True},
                    {"name": "currency", "label": "币种", "type": "string", "required": True},
                    {"name": "fee_type", "label": "费用类型", "type": "string", "required": False},
                    {"name": "fee_amount", "label": "费用金额", "type": "number", "required": False},
                    {"name": "description", "label": "描述", "type": "string", "required": False},
                ],
                "required": ["settlement_id", "platform", "settlement_date", "order_id", "type", "amount", "currency"],
            },
            {
                "name": "库存导入模板", "type": ImportType.INVENTORY.value,
                "columns": [
                    {"name": "warehouse_code", "label": "仓库编码", "type": "string", "required": True},
                    {"name": "sku", "label": "SKU", "type": "string", "required": True},
                    {"name": "qty_on_hand", "label": "在库数量", "type": "integer", "required": True},
                    {"name": "qty_reserved", "label": "预占数量", "type": "integer", "required": False},
                    {"name": "qty_defective", "label": "次品数量", "type": "integer", "required": False},
                    {"name": "cost_price", "label": "成本价", "type": "number", "required": False},
                    {"name": "cost_currency", "label": "成本币种", "type": "string", "required": False},
                    {"name": "location_code", "label": "库位编码", "type": "string", "required": False},
                ],
                "required": ["warehouse_code", "sku", "qty_on_hand"],
            },
            {
                "name": "物流轨迹导入模板", "type": ImportType.TRACKING.value,
                "columns": [
                    {"name": "tracking_number", "label": "追踪号", "type": "string", "required": True},
                    {"name": "carrier", "label": "承运商", "type": "string", "required": True},
                    {"name": "status", "label": "状态", "type": "string", "required": True},
                    {"name": "event_time", "label": "事件时间", "type": "datetime", "required": True},
                    {"name": "location", "label": "位置", "type": "string", "required": False},
                    {"name": "description", "label": "描述", "type": "string", "required": False},
                    {"name": "order_id", "label": "订单号", "type": "string", "required": False},
                ],
                "required": ["tracking_number", "carrier", "status", "event_time"],
            },
        ]
        templates = []
        for d in defaults:
            t = await self.create_template(
                tenant_id=tenant_id, template_name=d["name"], import_type=d["type"],
                columns=d["columns"], required_columns=d["required"],
            )
            t.is_system = True
            templates.append(t)
        await self.session.flush()
        return templates

    async def create_import_job(self, tenant_id: str, import_type: str,
                                 file_name: str = "", file_url: str = "",
                                 file_size: int = 0, template_id: str = "",
                                 import_options: dict | None = None) -> ImportJob:
        job_no = f"IMP-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"
        job = ImportJob(
            tenant_id=tenant_id, job_no=job_no, import_type=import_type,
            template_id=template_id, file_name=file_name,
            file_url=file_url, file_size=file_size,
            import_options_json=json.dumps(import_options or {}, default=str),
            trace_id=trace_id_var.get(""), created_by=actor_id_var.get(""),
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def validate_csv(self, job_id: str, tenant_id: str,
                            csv_content: str, encoding: str = "utf-8") -> ImportJob:
        job = await self._get_job(job_id, tenant_id)
        if not job:
            raise NotFoundException(message=f"Import job '{job_id}' not found")

        job.status = ImportStatus.VALIDATING.value
        job.started_at = datetime.now(UTC)
        await self.session.flush()

        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            rows = list(reader)
            job.total_rows = len(rows)

            template = None
            if job.template_id:
                template = await self._get_template(job.template_id, tenant_id)

            required = []
            if template:
                required = json.loads(template.required_columns)

            valid = 0
            invalid = 0
            for i, row in enumerate(rows, start=2):
                errors = self._validate_row(row, required, i)
                if errors:
                    invalid += 1
                    for err in errors:
                        error = ImportRowError(
                            tenant_id=tenant_id, job_id=job_id,
                            row_number=i, row_data=json.dumps(row, default=str),
                            error_type=err["type"], error_message=err["message"],
                            field_name=err.get("field", ""),
                        )
                        self.session.add(error)
                else:
                    valid += 1

            job.valid_rows = valid
            job.invalid_rows = invalid
            job.status = ImportStatus.IMPORTING.value if valid > 0 else ImportStatus.FAILED.value
            await self.session.flush()
            return job
        except Exception as e:
            job.status = ImportStatus.FAILED.value
            job.error_summary = json.dumps({"error": str(e)[:500]}, default=str)
            await self.session.flush()
            return job

    async def complete_import(self, job_id: str, tenant_id: str,
                               imported_rows: int = 0, failed_rows: int = 0,
                               error_file_url: str = "") -> ImportJob:
        job = await self._get_job(job_id, tenant_id)
        if not job:
            raise NotFoundException(message=f"Import job '{job_id}' not found")

        job.imported_rows = imported_rows
        job.failed_rows = failed_rows
        job.error_file_url = error_file_url
        job.completed_at = datetime.now(UTC)

        if failed_rows == 0:
            job.status = ImportStatus.COMPLETED.value
        elif imported_rows > 0:
            job.status = ImportStatus.COMPLETED_WITH_ERRORS.value
        else:
            job.status = ImportStatus.FAILED.value
        await self.session.flush()
        return job

    async def cancel_import(self, job_id: str, tenant_id: str) -> ImportJob:
        job = await self._get_job(job_id, tenant_id)
        if not job:
            raise NotFoundException(message=f"Import job '{job_id}' not found")
        if job.status in (ImportStatus.COMPLETED.value, ImportStatus.FAILED.value):
            raise ValidationException(message="Cannot cancel completed or failed job")
        job.status = ImportStatus.CANCELLED.value
        await self.session.flush()
        return job

    async def list_import_jobs(self, tenant_id: str, import_type: str = "",
                                status: str = "", page: int = 1,
                                page_size: int = 20) -> tuple[list[ImportJob], int]:
        conditions = [ImportJob.tenant_id == tenant_id]
        if import_type:
            conditions.append(ImportJob.import_type == import_type)
        if status:
            conditions.append(ImportJob.status == status)

        stmt = select(ImportJob).where(*conditions).order_by(ImportJob.created_at.desc())
        total_result = await self.session.execute(
            select(func.count()).select_from(ImportJob).where(*conditions)
        )
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(stmt.offset(offset).limit(page_size))
        items = list(result.scalars().all())
        return items, total

    async def get_import_errors(self, job_id: str, tenant_id: str,
                                 page: int = 1, page_size: int = 50) -> tuple[list[ImportRowError], int]:
        conditions = [ImportRowError.tenant_id == tenant_id, ImportRowError.job_id == job_id]
        stmt = select(ImportRowError).where(*conditions).order_by(ImportRowError.row_number)
        total_result = await self.session.execute(
            select(func.count()).select_from(ImportRowError).where(*conditions)
        )
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(stmt.offset(offset).limit(page_size))
        return list(result.scalars().all()), total

    async def list_templates(self, tenant_id: str, import_type: str = "") -> list[ImportTemplate]:
        conditions = [ImportTemplate.tenant_id == tenant_id, ImportTemplate.is_active]
        if import_type:
            conditions.append(ImportTemplate.import_type == import_type)
        stmt = select(ImportTemplate).where(*conditions).order_by(ImportTemplate.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def _validate_row(self, row: dict, required_columns: list[str], row_num: int) -> list[dict]:
        errors = []
        for col in required_columns:
            val = row.get(col, "").strip() if isinstance(row.get(col), str) else row.get(col)
            if val is None or val == "":
                errors.append({
                    "type": "missing_required",
                    "field": col,
                    "message": f"Row {row_num}: Required field '{col}' is missing",
                })
        return errors

    async def _get_job(self, job_id: str, tenant_id: str) -> ImportJob | None:
        stmt = select(ImportJob).where(ImportJob.id == job_id, ImportJob.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_template(self, template_id: str, tenant_id: str) -> ImportTemplate | None:
        stmt = select(ImportTemplate).where(ImportTemplate.id == template_id, ImportTemplate.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
