from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ApprovalStatus(StrEnum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    WITHDRAWN = "withdrawn"


class ApprovalAction(StrEnum):
    SUBMIT = "submit"
    APPROVE = "approve"
    REJECT = "reject"
    CANCEL = "cancel"
    WITHDRAW = "withdraw"
    DELEGATE = "delegate"


class ApprovalNodeConfig(BaseModel):
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    node_name: str = ""
    node_type: str = Field(default="user", description="user/role/auto")
    approver_ids: list[str] = Field(default_factory=list)
    approver_role_codes: list[str] = Field(default_factory=list)
    auto_approve_condition: dict[str, Any] | None = None
    min_approvals: int = Field(default=1, description="Minimum approvals needed")
    sort_order: int = 0


class ApprovalFlowDefinition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    flow_code: str = ""
    flow_name: str = ""
    domain: str = ""
    target_type: str = ""
    description: str = ""
    nodes: list[ApprovalNodeConfig] = Field(default_factory=list)
    status: str = "active"
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalInstance(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    flow_id: str = ""
    flow_code: str = ""
    domain: str = ""
    target_type: str = ""
    target_id: str = ""
    title: str = ""
    description: str = ""
    current_node_index: int = 0
    status: ApprovalStatus = ApprovalStatus.DRAFT
    submitted_by: str = ""
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    instance_id: str = ""
    node_id: str = ""
    node_name: str = ""
    assignee_id: str = ""
    assignee_role_code: str = ""
    action: ApprovalAction | None = None
    comment: str = ""
    status: str = "pending"
    delegated_from: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class ApprovalSubmitRequest(BaseModel):
    flow_code: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    target_type: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = Field(default="")


class ApprovalActionRequest(BaseModel):
    action: ApprovalAction
    comment: str = Field(default="")


class ApprovalInstanceResponse(BaseModel):
    id: str
    tenant_id: str
    flow_id: str
    flow_code: str
    domain: str
    target_type: str
    target_id: str
    title: str
    description: str
    current_node_index: int
    status: str
    submitted_by: str
    submitted_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApprovalTaskResponse(BaseModel):
    id: str
    tenant_id: str
    instance_id: str
    node_id: str
    node_name: str
    assignee_id: str
    action: str | None
    comment: str
    status: str
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
