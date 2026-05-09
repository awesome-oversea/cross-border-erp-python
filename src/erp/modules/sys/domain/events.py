from __future__ import annotations

from dataclasses import dataclass

from erp.shared.events.domain_event import DomainEvent


@dataclass
class DictItemCreated(DomainEvent):
    dict_type: str = ""
    item_code: str = ""
    item_value: str = ""

    def __post_init__(self):
        self.event_type = "erp.sys.dict_item.created.v1"
        self.domain = "sys"
        self.aggregate_type = "dict_item"


@dataclass
class ParamUpdated(DomainEvent):
    param_key: str = ""
    old_value: str = ""
    new_value: str = ""

    def __post_init__(self):
        self.event_type = "erp.sys.param.updated.v1"
        self.domain = "sys"
        self.aggregate_type = "sys_param"


@dataclass
class WebhookTriggered(DomainEvent):
    webhook_id: str = ""
    event_source: str = ""
    event_action: str = ""

    def __post_init__(self):
        self.event_type = "erp.sys.webhook.triggered.v1"
        self.domain = "sys"
        self.aggregate_type = "webhook"


@dataclass
class ImportJobCompleted(DomainEvent):
    job_id: str = ""
    import_type: str = ""
    total_rows: int = 0
    success_rows: int = 0
    fail_rows: int = 0

    def __post_init__(self):
        self.event_type = "erp.sys.import_job.completed.v1"
        self.domain = "sys"
        self.aggregate_type = "import_job"


@dataclass
class ApprovalSubmitted(DomainEvent):
    approval_id: str = ""
    approval_type: str = ""
    business_id: str = ""
    submitter_id: str = ""

    def __post_init__(self):
        self.event_type = "erp.sys.approval.submitted.v1"
        self.domain = "sys"
        self.aggregate_type = "approval"


@dataclass
class ApprovalCompleted(DomainEvent):
    approval_id: str = ""
    approval_type: str = ""
    business_id: str = ""
    result: str = ""

    def __post_init__(self):
        self.event_type = "erp.sys.approval.completed.v1"
        self.domain = "sys"
        self.aggregate_type = "approval"
