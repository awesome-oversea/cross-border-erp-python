from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from erp.middleware.infrastructure.business_models import (
    ContentReviewTask,
    CostEventRecord,
    ForexRate,
    InventoryVoucher,
    PaymentRecord,
    ProfitSettlement,
)
from erp.middleware.infrastructure.models import (
    ApiCallLog,
    ApiEndpoint,
    AuditLog,
    ConnectorCallStatModel,
    FileMetadata,
    MaskingAuditLog,
    MaskingRule,
    NotificationMessage,
    NotificationTemplate,
    PlatformConnectorModel,
    ScheduledJob,
    ScheduledJobLog,
    TranslationGlossary,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowTask,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class NotificationRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save_template(self, template: NotificationTemplate) -> NotificationTemplate:
        self._session.add(template)
        await self._session.flush()
        return template

    async def get_template_by_code(self, code: str) -> NotificationTemplate | None:
        stmt = select(NotificationTemplate).where(NotificationTemplate.code == code)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_templates(self) -> list[NotificationTemplate]:
        stmt = select(NotificationTemplate).where(NotificationTemplate.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def save_message(self, message: NotificationMessage) -> NotificationMessage:
        self._session.add(message)
        await self._session.flush()
        return message

    async def get_messages_by_tenant(self, tenant_id: str, limit: int = 50) -> list[NotificationMessage]:
        stmt = (select(NotificationMessage)
                .where(NotificationMessage.tenant_id == tenant_id)
                .order_by(NotificationMessage.created_at.desc())
                .limit(limit))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_read(self, message_id: str) -> None:
        stmt = (update(NotificationMessage)
                .where(NotificationMessage.id == message_id)
                .values(status="read"))
        await self._session.execute(stmt)


class FileRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, meta: FileMetadata) -> FileMetadata:
        self._session.add(meta)
        await self._session.flush()
        return meta

    async def get_by_file_id(self, file_id: str) -> FileMetadata | None:
        stmt = select(FileMetadata).where(FileMetadata.file_id == file_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str, domain: str = "") -> list[FileMetadata]:
        stmt = select(FileMetadata).where(FileMetadata.tenant_id == tenant_id, FileMetadata.status == "uploaded")
        if domain:
            stmt = stmt.where(FileMetadata.domain == domain)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_file(self, file_id: str) -> None:
        stmt = update(FileMetadata).where(FileMetadata.file_id == file_id).values(status="deleted")
        await self._session.execute(stmt)


class WorkflowRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save_definition(self, defn: WorkflowDefinition) -> WorkflowDefinition:
        self._session.add(defn)
        await self._session.flush()
        return defn

    async def get_definition_by_code(self, flow_code: str) -> WorkflowDefinition | None:
        stmt = select(WorkflowDefinition).where(WorkflowDefinition.flow_code == flow_code)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_instance(self, instance: WorkflowInstance) -> WorkflowInstance:
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def get_instance(self, instance_id: str) -> WorkflowInstance | None:
        stmt = select(WorkflowInstance).where(WorkflowInstance.instance_id == instance_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_task(self, task: WorkflowTask) -> WorkflowTask:
        self._session.add(task)
        await self._session.flush()
        return task

    async def get_tasks_by_instance(self, instance_id: str) -> list[WorkflowTask]:
        stmt = select(WorkflowTask).where(WorkflowTask.instance_id == instance_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_instance_status(self, instance_id: str, status: str, current_node_id: str = "") -> None:
        values: dict = {"status": status}
        if current_node_id:
            values["current_node_id"] = current_node_id
        stmt = update(WorkflowInstance).where(WorkflowInstance.instance_id == instance_id).values(**values)
        await self._session.execute(stmt)

    async def update_task_status(self, task_id: str, status: str, comment: str = "", completed_by: str = "") -> None:
        values: dict = {"status": status, "result_comment": comment, "completed_by": completed_by}
        stmt = update(WorkflowTask).where(WorkflowTask.task_id == task_id).values(**values)
        await self._session.execute(stmt)


class SchedulerRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save_job(self, job: ScheduledJob) -> ScheduledJob:
        self._session.add(job)
        await self._session.flush()
        return job

    async def get_job(self, job_id: str) -> ScheduledJob | None:
        stmt = select(ScheduledJob).where(ScheduledJob.job_id == job_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_jobs(self, tenant_id: str) -> list[ScheduledJob]:
        stmt = select(ScheduledJob).where(ScheduledJob.tenant_id == tenant_id, ScheduledJob.status != "deleted")
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_job_status(self, job_id: str, status: str) -> None:
        stmt = update(ScheduledJob).where(ScheduledJob.job_id == job_id).values(status=status)
        await self._session.execute(stmt)

    async def delete_job(self, job_id: str) -> None:
        stmt = update(ScheduledJob).where(ScheduledJob.job_id == job_id).values(status="deleted")
        await self._session.execute(stmt)

    async def save_log(self, log: ScheduledJobLog) -> ScheduledJobLog:
        self._session.add(log)
        await self._session.flush()
        return log

    async def get_logs(self, job_id: str, limit: int = 50) -> list[ScheduledJobLog]:
        stmt = (select(ScheduledJobLog)
                .where(ScheduledJobLog.job_id == job_id)
                .order_by(ScheduledJobLog.created_at.desc())
                .limit(limit))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class AuditRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, log: AuditLog) -> AuditLog:
        self._session.add(log)
        await self._session.flush()
        return log

    async def query(self, tenant_id: str, domain: str = "", action: str = "",
                    actor_id: str = "", resource_type: str = "", resource_id: str = "",
                    limit: int = 50, offset: int = 0) -> list[AuditLog]:
        stmt = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
        if domain:
            stmt = stmt.where(AuditLog.domain == domain)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if actor_id:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if resource_id:
            stmt = stmt.where(AuditLog.resource_id == resource_id)
        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class TranslationRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, entry: TranslationGlossary) -> TranslationGlossary:
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def get_by_entry_id(self, entry_id: str) -> TranslationGlossary | None:
        stmt = select(TranslationGlossary).where(TranslationGlossary.entry_id == entry_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_domain(self, tenant_id: str, domain: str = "") -> list[TranslationGlossary]:
        stmt = select(TranslationGlossary).where(TranslationGlossary.tenant_id == tenant_id)
        if domain:
            stmt = stmt.where(TranslationGlossary.domain == domain)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class MaskingRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_rules(self, tenant_id: str) -> list[MaskingRule]:
        stmt = select(MaskingRule).where(MaskingRule.tenant_id == tenant_id, MaskingRule.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def save_rule(self, rule: MaskingRule) -> MaskingRule:
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def save_audit(self, log: MaskingAuditLog) -> MaskingAuditLog:
        self._session.add(log)
        await self._session.flush()
        return log


class ApiPlatformRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_endpoints(self, service: str = "", version: str = "", method: str = "") -> list[ApiEndpoint]:
        stmt = select(ApiEndpoint).where(ApiEndpoint.is_active.is_(True))
        if service:
            stmt = stmt.where(ApiEndpoint.service == service)
        if version:
            stmt = stmt.where(ApiEndpoint.version == version)
        if method:
            stmt = stmt.where(ApiEndpoint.method == method)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def save_call_log(self, log: ApiCallLog) -> ApiCallLog:
        self._session.add(log)
        await self._session.flush()
        return log

    async def get_stats(self, tenant_id: str, service: str = "", path: str = "",
                        hours: int = 24) -> dict:
        stmt = select(ApiCallLog).where(ApiCallLog.tenant_id == tenant_id)
        if service:
            stmt = stmt.where(ApiCallLog.service == service)
        if path:
            stmt = stmt.where(ApiCallLog.path == path)
        result = await self._session.execute(stmt)
        logs = list(result.scalars().all())
        total = len(logs)
        errors = sum(1 for log in logs if log.status_code >= 400)
        avg_time = sum(log.response_time_ms for log in logs) / total if total > 0 else 0
        return {"total_calls": total, "error_calls": errors, "avg_response_time_ms": round(avg_time, 2)}


class ConnectorRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_connectors(self, tenant_id: str, connector_type: str = "", platform: str = "") -> list[PlatformConnectorModel]:
        stmt = select(PlatformConnectorModel).where(
            PlatformConnectorModel.tenant_id == tenant_id, PlatformConnectorModel.is_active.is_(True))
        if connector_type:
            stmt = stmt.where(PlatformConnectorModel.connector_type == connector_type)
        if platform:
            stmt = stmt.where(PlatformConnectorModel.platform == platform)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def save(self, connector: PlatformConnectorModel) -> PlatformConnectorModel:
        self._session.add(connector)
        await self._session.flush()
        return connector

    async def save_call_stat(self, stat: ConnectorCallStatModel) -> ConnectorCallStatModel:
        self._session.add(stat)
        await self._session.flush()
        return stat

    async def get_stats(self, tenant_id: str, connector_id: str, hours: int = 24) -> dict:
        stmt = select(ConnectorCallStatModel).where(
            ConnectorCallStatModel.tenant_id == tenant_id,
            ConnectorCallStatModel.connector_id == connector_id)
        result = await self._session.execute(stmt)
        stats = list(result.scalars().all())
        total = len(stats)
        success = sum(1 for s in stats if s.success)
        return {"total_calls": total, "success_calls": success, "failed_calls": total - success}


class ContentReviewRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, task: ContentReviewTask) -> ContentReviewTask:
        self._session.add(task)
        await self._session.flush()
        return task

    async def get_by_task_id(self, task_id: str) -> ContentReviewTask | None:
        stmt = select(ContentReviewTask).where(ContentReviewTask.task_id == task_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_status(self, tenant_id: str, status: str = "", limit: int = 50) -> list[ContentReviewTask]:
        stmt = select(ContentReviewTask).where(ContentReviewTask.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(ContentReviewTask.status == status)
        stmt = stmt.order_by(ContentReviewTask.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, task_id: str, status: str, **kwargs) -> None:
        stmt = update(ContentReviewTask).where(ContentReviewTask.task_id == task_id).values(status=status, **kwargs)
        await self._session.execute(stmt)


class ForexRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, rate: ForexRate) -> ForexRate:
        self._session.add(rate)
        await self._session.flush()
        return rate

    async def get_latest(self, tenant_id: str, base: str, target: str) -> ForexRate | None:
        stmt = (select(ForexRate)
                .where(ForexRate.tenant_id == tenant_id, ForexRate.base_currency == base,
                       ForexRate.target_currency == target)
                .order_by(ForexRate.rate_date.desc())
                .limit(1))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, record: PaymentRecord) -> PaymentRecord:
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_by_payment_id(self, payment_id: str) -> PaymentRecord | None:
        stmt = select(PaymentRecord).where(PaymentRecord.payment_id == payment_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(self, payment_id: str, status: str, **kwargs) -> None:
        stmt = update(PaymentRecord).where(PaymentRecord.payment_id == payment_id).values(status=status, **kwargs)
        await self._session.execute(stmt)


class CostEventRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, event: CostEventRecord) -> CostEventRecord:
        self._session.add(event)
        await self._session.flush()
        return event

    async def list_by_sku(self, tenant_id: str, sku_id: str) -> list[CostEventRecord]:
        stmt = select(CostEventRecord).where(
            CostEventRecord.tenant_id == tenant_id, CostEventRecord.sku_id == sku_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ProfitSettlementRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, settlement: ProfitSettlement) -> ProfitSettlement:
        self._session.add(settlement)
        await self._session.flush()
        return settlement

    async def list_by_sku(self, tenant_id: str, sku_id: str) -> list[ProfitSettlement]:
        stmt = select(ProfitSettlement).where(
            ProfitSettlement.tenant_id == tenant_id, ProfitSettlement.sku_id == sku_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class InventoryVoucherRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, voucher: InventoryVoucher) -> InventoryVoucher:
        self._session.add(voucher)
        await self._session.flush()
        return voucher

    async def get_by_voucher_id(self, voucher_id: str) -> InventoryVoucher | None:
        stmt = select(InventoryVoucher).where(InventoryVoucher.voucher_id == voucher_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(self, voucher_id: str, status: str, **kwargs) -> None:
        stmt = update(InventoryVoucher).where(InventoryVoucher.voucher_id == voucher_id).values(status=status, **kwargs)
        await self._session.execute(stmt)

    async def list_by_warehouse(self, tenant_id: str, warehouse_id: str, limit: int = 50) -> list[InventoryVoucher]:
        stmt = (select(InventoryVoucher)
                .where(InventoryVoucher.tenant_id == tenant_id, InventoryVoucher.warehouse_id == warehouse_id)
                .order_by(InventoryVoucher.created_at.desc()).limit(limit))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
