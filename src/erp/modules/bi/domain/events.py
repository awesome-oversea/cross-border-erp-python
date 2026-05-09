from __future__ import annotations

from dataclasses import dataclass

from erp.shared.events.domain_event import DomainEvent


@dataclass
class MetricValueRecorded(DomainEvent):
    metric_id: str = ""
    metric_code: str = ""
    period_type: str = ""
    numeric_value: float = 0.0

    def __post_init__(self):
        self.event_type = "erp.bi.metric_value.recorded.v1"
        self.domain = "bi"
        self.aggregate_type = "bi_metric_value"


@dataclass
class MetricAlertTriggered(DomainEvent):
    metric_code: str = ""
    alert_type: str = ""
    threshold: float = 0.0
    actual_value: float = 0.0

    def __post_init__(self):
        self.event_type = "erp.bi.metric.alert_triggered.v1"
        self.domain = "bi"
        self.aggregate_type = "bi_metric_alert"


@dataclass
class ReportGenerated(DomainEvent):
    report_id: str = ""
    report_code: str = ""
    category: str = ""

    def __post_init__(self):
        self.event_type = "erp.bi.report.generated.v1"
        self.domain = "bi"
        self.aggregate_type = "bi_report"
