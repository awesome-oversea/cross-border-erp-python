from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from erp.shared.db.base import Base, TenantModel


class NotificationTemplate(Base):
    __tablename__ = "notification_template"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, comment="Template code")
    title_template: Mapped[str] = mapped_column(String(500), nullable=False, comment="Title template")
    body_template: Mapped[str] = mapped_column(Text, nullable=False, comment="Body template")
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="email", comment="email/sms/push/in_app")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NotificationMessage(TenantModel):
    __tablename__ = "notification_message"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    recipient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="email")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sent", comment="sent/read/failed")
    read_at: Mapped[str] = mapped_column(String(30), nullable=False, default="")


class FileMetadata(TenantModel):
    __tablename__ = "file_metadata"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    extension: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_image: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_document: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    domain: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded", comment="uploaded/deleted")
    preview_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")


class WorkflowDefinition(TenantModel):
    __tablename__ = "workflow_definition"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flow_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    flow_name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    nodes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class WorkflowInstance(TenantModel):
    __tablename__ = "workflow_instance"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    definition_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    flow_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    business_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    business_type: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running", comment="running/completed/rejected/cancelled")
    current_node_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    initiator_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")


class WorkflowTask(TenantModel):
    __tablename__ = "workflow_task"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    instance_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String(100), nullable=False)
    node_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    node_type: Mapped[str] = mapped_column(String(30), nullable=False, default="approval")
    assignee_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", comment="pending/approved/rejected")
    result_comment: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    completed_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    completed_at: Mapped[str] = mapped_column(String(30), nullable=False, default="")


class ScheduledJob(TenantModel):
    __tablename__ = "scheduled_job"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    job_name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    handler_class: Mapped[str] = mapped_column(String(200), nullable=False)
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="active/paused/deleted")
    last_run_at: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    next_run_at: Mapped[str] = mapped_column(String(30), nullable=False, default="")


class ScheduledJobLog(TenantModel):
    __tablename__ = "scheduled_job_log"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success", comment="success/failed/timeout")
    started_at: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    finished_at: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")


class AuditLog(TenantModel):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="CREATE/UPDATE/DELETE/LOGIN/EXPORT")
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    resource_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    domain: Mapped[str] = mapped_column(String(30), nullable=False, default="", index=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    actor_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    before_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    after_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    diff_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    ip_address: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    user_agent: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    request_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    request_method: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success", comment="success/failed")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)


class TranslationGlossary(TenantModel):
    __tablename__ = "translation_glossary"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entry_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(30), nullable=False, default="general")
    source_term: Mapped[str] = mapped_column(String(200), nullable=False)
    translations_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class MaskingRule(TenantModel):
    __tablename__ = "masking_rule"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False, default="regex", comment="regex/replacement/custom")
    pattern: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    replacement: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MaskingAuditLog(TenantModel):
    __tablename__ = "masking_audit_log"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    original_value: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    masked_value: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    operator_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")


class ApiEndpoint(TenantModel):
    __tablename__ = "api_endpoint"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    service: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False, default="GET")
    version: Mapped[str] = mapped_column(String(10), nullable=False, default="v1")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ApiCallLog(TenantModel):
    __tablename__ = "api_call_log"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    service: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False, default="GET")
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    caller_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)


class PlatformConnectorModel(TenantModel):
    __tablename__ = "platform_connector"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connector_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    connector_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="marketplace/logistics/payment")
    connector_name: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0.0")
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    health_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    last_health_check_at: Mapped[str] = mapped_column(String(30), nullable=False, default="")


class ConnectorCallStatModel(TenantModel):
    __tablename__ = "connector_call_stat"
    __table_args__ = {"schema": "sys"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connector_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    called_at: Mapped[str] = mapped_column(String(30), nullable=False, default="")
