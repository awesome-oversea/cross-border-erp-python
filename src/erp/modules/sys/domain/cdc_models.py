from __future__ import annotations

import abc
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.context import actor_id_var, tenant_id_var
from erp.shared.db.base import Base
from erp.shared.exceptions import ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CDCOperation(StrEnum):
    INSERT = "c"
    UPDATE = "u"
    DELETE = "d"
    SNAPSHOT = "r"


class CDCStatus(StrEnum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


@dataclass
class CDCEvent:
    event_id: str = ""
    source_schema: str = ""
    source_table: str = ""
    operation: str = ""
    before_data: dict = field(default_factory=dict)
    after_data: dict = field(default_factory=dict)
    changed_columns: list = field(default_factory=list)
    tenant_id: str = ""
    timestamp: str = ""
    lsn: str = ""
    transaction_id: str = ""


class CDCEventRecord(Base):
    __tablename__ = "cdc_event_record"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_schema: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_table: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(5), nullable=False, index=True)
    before_data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    after_data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    changed_columns_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    lsn: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    transaction_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    handler_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    handler_result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CDCPipelineConfig(Base):
    __tablename__ = "cdc_pipeline_config"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    pipeline_name: Mapped[str] = mapped_column(String(200), nullable=False)
    pipeline_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_schema: Mapped[str] = mapped_column(String(50), nullable=False)
    source_table: Mapped[str] = mapped_column(String(100), nullable=False)
    handler_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                               comment="kafka/direct/lambda")
    handler_config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    topic_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    filter_condition_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    transform_config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CDCHandler(abc.ABC):
    @abc.abstractmethod
    async def handle(self, event: CDCEvent) -> dict:
        ...



class KafkaCDCHandler(CDCHandler):
    def __init__(self, topic_name: str, bootstrap_servers: str = "localhost:9092"):
        self.topic_name = topic_name
        self.bootstrap_servers = bootstrap_servers

    async def handle(self, event: CDCEvent) -> dict:
        message = {
            "event_id": event.event_id,
            "source": f"{event.source_schema}.{event.source_table}",
            "operation": event.operation,
            "before": event.before_data,
            "after": event.after_data,
            "changed_columns": event.changed_columns,
            "tenant_id": event.tenant_id,
            "timestamp": event.timestamp,
            "lsn": event.lsn,
        }
        return {
            "handler": "kafka",
            "topic": self.topic_name,
            "message_size": len(json.dumps(message)),
            "status": "sent_to_kafka",
        }


class DirectCDCHandler(CDCHandler):
    def __init__(self, callback=None):
        self.callback = callback

    async def handle(self, event: CDCEvent) -> dict:
        if self.callback:
            await self.callback(event)
        return {
            "handler": "direct",
            "status": "processed",
            "source": f"{event.source_schema}.{event.source_table}",
        }


class CDCIngestionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ingest_event(self, event: CDCEvent) -> CDCEventRecord:
        record = CDCEventRecord(
            tenant_id=event.tenant_id or tenant_id_var.get(""),
            source_schema=event.source_schema,
            source_table=event.source_table,
            operation=event.operation,
            before_data_json=json.dumps(event.before_data, default=str),
            after_data_json=json.dumps(event.after_data, default=str),
            changed_columns_json=json.dumps(event.changed_columns, default=str),
            lsn=event.lsn,
            transaction_id=event.transaction_id,
            status=CDCStatus.PENDING.value,
            occurred_at=datetime.fromisoformat(event.timestamp) if event.timestamp else datetime.now(UTC),
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def process_pending_events(self, tenant_id: str = "",
                                      batch_size: int = 100) -> dict:
        conditions = [CDCEventRecord.status == CDCStatus.PENDING.value]
        if tenant_id:
            conditions.append(CDCEventRecord.tenant_id == tenant_id)

        stmt = select(CDCEventRecord).where(*conditions).order_by(
            CDCEventRecord.occurred_at.asc()
        ).limit(batch_size)
        result = await self.session.execute(stmt)
        events = list(result.scalars().all())

        processed = 0
        failed = 0
        skipped = 0

        for record in events:
            try:
                pipelines = await self._get_active_pipelines(
                    record.source_schema, record.source_table
                )
                if not pipelines:
                    record.status = CDCStatus.SKIPPED.value
                    skipped += 1
                    continue

                for pipeline in pipelines:
                    handler = self._create_handler(pipeline)
                    event = CDCEvent(
                        event_id=record.id,
                        source_schema=record.source_schema,
                        source_table=record.source_table,
                        operation=record.operation,
                        before_data=json.loads(record.before_data_json),
                        after_data=json.loads(record.after_data_json),
                        changed_columns=json.loads(record.changed_columns_json),
                        tenant_id=record.tenant_id,
                        timestamp=record.occurred_at.isoformat(),
                        lsn=record.lsn,
                    )
                    result_data = await handler.handle(event)
                    record.handler_name = pipeline.pipeline_name
                    record.handler_result_json = json.dumps(result_data, default=str)

                record.status = CDCStatus.PROCESSED.value
                record.processed_at = datetime.now(UTC)
                processed += 1
            except Exception as e:
                record.retry_count += 1
                record.error_message = str(e)[:500]
                if record.retry_count >= record.max_retries:
                    record.status = CDCStatus.FAILED.value
                else:
                    record.status = CDCStatus.RETRYING.value
                failed += 1

        await self.session.flush()
        return {"processed": processed, "failed": failed, "skipped": skipped, "total": len(events)}

    async def retry_failed_events(self, tenant_id: str = "",
                                   batch_size: int = 50) -> dict:
        conditions = [CDCEventRecord.status == CDCStatus.FAILED.value]
        if tenant_id:
            conditions.append(CDCEventRecord.tenant_id == tenant_id)

        stmt = select(CDCEventRecord).where(*conditions).order_by(
            CDCEventRecord.occurred_at.asc()
        ).limit(batch_size)
        result = await self.session.execute(stmt)
        events = list(result.scalars().all())

        retried = 0
        for record in events:
            record.status = CDCStatus.PENDING.value
            record.retry_count = 0
            record.error_message = ""
            retried += 1

        await self.session.flush()
        return {"retried": retried}

    async def create_pipeline(self, tenant_id: str, pipeline_name: str,
                               pipeline_code: str, source_schema: str,
                               source_table: str, handler_type: str = "kafka",
                               handler_config: dict | None = None,
                               topic_name: str = "",
                               filter_condition: dict | None = None,
                               transform_config: dict | None = None,
                               batch_size: int = 100,
                               max_retries: int = 3,
                               description: str = "") -> CDCPipelineConfig:
        existing = await self._get_pipeline_by_code(tenant_id, pipeline_code)
        if existing:
            raise ValidationException(message=f"Pipeline code '{pipeline_code}' already exists")

        pipeline = CDCPipelineConfig(
            tenant_id=tenant_id, pipeline_name=pipeline_name,
            pipeline_code=pipeline_code, source_schema=source_schema,
            source_table=source_table, handler_type=handler_type,
            handler_config_json=json.dumps(handler_config or {}, default=str),
            topic_name=topic_name or f"erp.cdc.{source_schema}.{source_table}.v1",
            filter_condition_json=json.dumps(filter_condition or {}, default=str),
            transform_config_json=json.dumps(transform_config or {}, default=str),
            batch_size=batch_size, max_retries=max_retries,
            description=description,
            created_by=actor_id_var.get(""),
        )
        self.session.add(pipeline)
        await self.session.flush()
        return pipeline

    async def list_pipelines(self, tenant_id: str, source_schema: str = "",
                              is_active: bool | None = None,
                              page: int = 1, page_size: int = 20) -> tuple[list[CDCPipelineConfig], int]:
        conditions = [CDCPipelineConfig.tenant_id == tenant_id]
        if source_schema:
            conditions.append(CDCPipelineConfig.source_schema == source_schema)
        if is_active is not None:
            conditions.append(CDCPipelineConfig.is_active == is_active)

        from sqlalchemy import func as sa_func
        count_stmt = select(sa_func.count()).select_from(CDCPipelineConfig).where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(CDCPipelineConfig).where(*conditions).order_by(
            CDCPipelineConfig.source_schema, CDCPipelineConfig.source_table
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_event_stats(self, tenant_id: str = "",
                               source_schema: str = "",
                               hours: int = 24) -> dict:

        from sqlalchemy import func as sa_func

        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        conditions = [CDCEventRecord.occurred_at >= cutoff]
        if tenant_id:
            conditions.append(CDCEventRecord.tenant_id == tenant_id)
        if source_schema:
            conditions.append(CDCEventRecord.source_schema == source_schema)

        base = select(CDCEventRecord).where(*conditions)
        total = (await self.session.execute(select(sa_func.count()).select_from(base.subquery()))).scalar() or 0
        by_status_stmt = select(CDCEventRecord.status, sa_func.count()).select_from(
            CDCEventRecord
        ).where(*conditions).group_by(CDCEventRecord.status)
        status_rows = (await self.session.execute(by_status_stmt)).all()
        by_status = {row[0]: row[1] for row in status_rows}

        by_table_stmt = select(
            CDCEventRecord.source_schema, CDCEventRecord.source_table, sa_func.count()
        ).select_from(CDCEventRecord).where(*conditions).group_by(
            CDCEventRecord.source_schema, CDCEventRecord.source_table
        ).order_by(sa_func.count().desc()).limit(20)
        table_rows = (await self.session.execute(by_table_stmt)).all()
        by_table = [{"schema": r[0], "table": r[1], "count": r[2]} for r in table_rows]

        return {
            "period_hours": hours,
            "total_events": total,
            "by_status": by_status,
            "by_table": by_table,
        }

    async def init_default_pipelines(self, tenant_id: str):
        defaults = [
            ("oms_order_cdc", "OMS订单变更", "oms", "orders", "kafka",
             {}, "erp.oms.order.changed.v1"),
            ("oms_order_item_cdc", "OMS订单明细变更", "oms", "order_items", "kafka",
             {}, "erp.oms.order-item.changed.v1"),
            ("wms_inventory_cdc", "WMS库存变更", "wms", "inventory", "kafka",
             {}, "erp.wms.inventory.changed.v1"),
            ("pdm_product_cdc", "PDM产品变更", "pdm", "products", "kafka",
             {}, "erp.pdm.product.changed.v1"),
            ("fms_cost_event_cdc", "FMS费用事件变更", "fms", "cost_event", "kafka",
             {}, "erp.fms.cost-event.changed.v1"),
            ("iam_user_cdc", "IAM用户变更", "iam", "users", "kafka",
             {}, "erp.iam.user.changed.v1"),
            ("scm_purchase_cdc", "SCM采购单变更", "scm", "purchase_orders", "kafka",
             {}, "erp.scm.purchase-order.changed.v1"),
            ("tms_shipment_cdc", "TMS运单变更", "tms", "shipments", "kafka",
             {}, "erp.tms.shipment.changed.v1"),
            ("crm_ticket_cdc", "CRM工单变更", "crm", "tickets", "kafka",
             {}, "erp.crm.ticket.changed.v1"),
            ("ads_campaign_cdc", "ADS广告活动变更", "ads", "campaigns", "kafka",
             {}, "erp.ads.campaign.changed.v1"),
        ]
        created = []
        for code, name, schema, table, handler_type, config, topic in defaults:
            existing = await self._get_pipeline_by_code(tenant_id, code)
            if not existing:
                pipeline = await self.create_pipeline(
                    tenant_id, name, code, schema, table,
                    handler_type=handler_type, handler_config=config,
                    topic_name=topic,
                )
                created.append(pipeline)
        return created

    def _create_handler(self, pipeline: CDCPipelineConfig) -> CDCHandler:
        if pipeline.handler_type == "kafka":
            config = json.loads(pipeline.handler_config_json)
            return KafkaCDCHandler(
                topic_name=pipeline.topic_name,
                bootstrap_servers=config.get("bootstrap_servers", "localhost:9092"),
            )
        elif pipeline.handler_type == "direct":
            return DirectCDCHandler()
        else:
            return DirectCDCHandler()

    async def _get_pipeline_by_code(self, tenant_id: str, code: str) -> CDCPipelineConfig | None:
        stmt = select(CDCPipelineConfig).where(
            CDCPipelineConfig.tenant_id == tenant_id,
            CDCPipelineConfig.pipeline_code == code,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _get_active_pipelines(self, source_schema: str,
                                     source_table: str) -> list[CDCPipelineConfig]:
        stmt = select(CDCPipelineConfig).where(
            CDCPipelineConfig.source_schema == source_schema,
            CDCPipelineConfig.source_table == source_table,
            CDCPipelineConfig.is_active,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
