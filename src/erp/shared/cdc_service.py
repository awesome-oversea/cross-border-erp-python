"""
CDC数据同步与数据治理服务 (P6)

包含:
  - ClickHouse同步配置与任务管理 (P6-003)
  - 数据血缘追踪 (P6-011)
  - 审计数据归档策略 (P6-012)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


# ---------------------------------------------------------------------------
# ClickHouse 同步任务配置 (P6-003)
# ---------------------------------------------------------------------------

@dataclass
class CdcSyncTask:
    """CDC同步任务定义"""
    table_name: str = ""
    schema_name: str = ""
    sync_type: str = "full"  # full / incremental / cdc
    sync_interval_s: int = 60
    target_table: str = ""
    field_mapping: dict[str, str] = field(default_factory=dict)
    where_clause: str = ""
    is_active: bool = True


# 预置同步任务: 14域核心表到ClickHouse
DEFAULT_CDC_TASKS = [
    CdcSyncTask(schema_name="oms", table_name="sales_order", sync_type="incremental", sync_interval_s=30,
                target_table="fact_sales_order",
                where_clause="updated_at >= now() - interval 1 day"),
    CdcSyncTask(schema_name="oms", table_name="sales_order_item", sync_type="incremental", sync_interval_s=30,
                target_table="fact_sales_order_item"),
    CdcSyncTask(schema_name="wms", table_name="inventory", sync_type="incremental", sync_interval_s=10,
                target_table="fact_inventory"),
    CdcSyncTask(schema_name="wms", table_name="stock_movement", sync_type="incremental", sync_interval_s=60,
                target_table="fact_stock_movement"),
    CdcSyncTask(schema_name="scm", table_name="purchase_order", sync_type="incremental", sync_interval_s=120,
                target_table="fact_purchase_order"),
    CdcSyncTask(schema_name="fms", table_name="cost_event", sync_type="incremental", sync_interval_s=60,
                target_table="fact_cost_event"),
    CdcSyncTask(schema_name="fms", table_name="profit_record", sync_type="incremental", sync_interval_s=60,
                target_table="fact_profit"),
    CdcSyncTask(schema_name="pdm", table_name="sku", sync_type="incremental", sync_interval_s=300,
                target_table="dim_sku"),
    CdcSyncTask(schema_name="iam", table_name="user", sync_type="incremental", sync_interval_s=300,
                target_table="dim_user"),
    CdcSyncTask(schema_name="scm", table_name="supplier", sync_type="incremental", sync_interval_s=300,
                target_table="dim_supplier"),
]


class CdcSyncManager:
    """CDC同步管理器"""

    @staticmethod
    def get_default_tasks() -> list[CdcSyncTask]:
        return DEFAULT_CDC_TASKS

    @staticmethod
    def validate_task(task: CdcSyncTask) -> list[str]:
        errors = []
        if not task.table_name: errors.append("表名不能为空")
        if not task.schema_name: errors.append("Schema不能为空")
        if task.sync_interval_s < 5: errors.append("同步间隔不能小于5秒")
        return errors

    @staticmethod
    def estimate_volume(row_count: int, avg_row_size_bytes: int) -> dict:
        """估算同步数据量"""
        total_bytes = row_count * avg_row_size_bytes
        return {"rows": row_count, "bytes": total_bytes, "mb": round(total_bytes / 1024 / 1024, 2)}


# ---------------------------------------------------------------------------
# 数据血缘追踪 (P6-011)
# ---------------------------------------------------------------------------

@dataclass
class DataLineageNode:
    """数据血缘节点"""
    node_id: str = ""
    node_type: str = ""  # table / view / report / api / etl
    name: str = ""
    domain: str = ""
    fields: list[str] = field(default_factory=list)


@dataclass
class DataLineageEdge:
    """数据血缘边"""
    source_id: str = ""
    target_id: str = ""
    transformation: str = ""  # direct / aggregate / join / filter
    description: str = ""


class DataLineageService:
    """数据血缘追踪服务"""

    @staticmethod
    def build_lineage(nodes: list[DataLineageNode], edges: list[DataLineageEdge]) -> dict:
        return {"nodes": [{"id": n.node_id, "type": n.node_type, "name": n.name, "domain": n.domain}
                          for n in nodes],
                "edges": [{"from": e.source_id, "to": e.target_id, "label": e.transformation}
                          for e in edges]}

    @staticmethod
    def trace_upstream(edges: list[DataLineageEdge], target_id: str) -> list[str]:
        """向上游追踪 - 找出目标数据的所有来源"""
        visited = set()
        queue = [target_id]
        while queue:
            current = queue.pop(0)
            if current in visited: continue
            visited.add(current)
            for e in edges:
                if e.target_id == current:
                    queue.append(e.source_id)
        return list(visited)

    @staticmethod
    def trace_downstream(edges: list[DataLineageEdge], source_id: str) -> list[str]:
        """向下游追踪 - 找出源数据的所有消费者"""
        visited = set()
        queue = [source_id]
        while queue:
            current = queue.pop(0)
            if current in visited: continue
            visited.add(current)
            for e in edges:
                if e.source_id == current:
                    queue.append(e.target_id)
        return list(visited)


# ---------------------------------------------------------------------------
# 审计数据归档策略 (P6-012)
# ---------------------------------------------------------------------------

ARCHIVE_RULES = {
    "audit_log": {"retention_days": 365, "archive_after_days": 90, "partition_by": "month"},
    "order_audit_log": {"retention_days": 730, "archive_after_days": 180, "partition_by": "month"},
    "stock_movement": {"retention_days": 730, "archive_after_days": 180, "partition_by": "month"},
    "cost_event": {"retention_days": 1825, "archive_after_days": 365, "partition_by": "quarter"},
    "profit_record": {"retention_days": 1825, "archive_after_days": 365, "partition_by": "quarter"},
    "outbox_message": {"retention_days": 90, "archive_after_days": 30, "partition_by": "month"},
    "connector_call_log": {"retention_days": 180, "archive_after_days": 60, "partition_by": "month"},
}


class AuditArchiveService:
    """审计数据归档策略服务"""

    @staticmethod
    def get_rule(table_name: str) -> dict:
        return ARCHIVE_RULES.get(table_name, {"retention_days": 365, "archive_after_days": 90, "partition_by": "month"})

    @staticmethod
    def should_archive(table_name: str, last_updated) -> bool:
        rule = ARCHIVE_RULES.get(table_name, {"archive_after_days": 90})
        if not last_updated: return False
        from datetime import timezone
        age = (datetime.now(UTC) - last_updated.replace(tzinfo=UTC) if hasattr(last_updated, "tzinfo") and last_updated.tzinfo else datetime.now(UTC) - last_updated.replace(tzinfo=UTC)).days if last_updated else 0
        return age >= rule.get("archive_after_days", 90)

    @staticmethod
    def should_purge(table_name: str, created_at) -> bool:
        rule = ARCHIVE_RULES.get(table_name, {"retention_days": 365})
        if not created_at: return False
        age = (datetime.now(UTC) - created_at.replace(tzinfo=UTC) if hasattr(created_at, "tzinfo") and created_at.tzinfo else datetime.now(UTC) - created_at.replace(tzinfo=UTC)).days if created_at else 0
        return age >= rule.get("retention_days", 365)
