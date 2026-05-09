from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class FlowStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class NodeType(StrEnum):
    START = "start"
    END = "end"
    APPROVAL = "approval"
    CONDITION = "condition"
    NOTIFICATION = "notification"


@dataclass
class FlowNode:
    node_id: str = ""
    node_name: str = ""
    node_type: str = "approval"
    assignee_type: str = "user"
    assignee_ids: list[str] = field(default_factory=list)
    multi_approve_rule: str = "any"
    timeout_hours: int = 72
    next_node_id: str = ""
    condition_expr: str = ""


@dataclass
class FlowDefinition:
    flow_id: str = ""
    flow_code: str = ""
    flow_name: str = ""
    domain: str = ""
    target_type: str = ""
    description: str = ""
    nodes: list[FlowNode] = field(default_factory=list)
    version: int = 1
    status: str = "active"
    created_at: str = ""


@dataclass
class FlowInstance:
    instance_id: str = ""
    flow_id: str = ""
    flow_code: str = ""
    tenant_id: str = ""
    business_id: str = ""
    business_type: str = ""
    status: str = "running"
    current_node_id: str = ""
    initiator_id: str = ""
    created_at: str = ""
    completed_at: str = ""


@dataclass
class FlowTask:
    task_id: str = ""
    instance_id: str = ""
    node_id: str = ""
    node_name: str = ""
    assignee_id: str = ""
    status: str = "pending"
    comment: str = ""
    created_at: str = ""
    completed_at: str = ""


class WorkflowEngine:
    def __init__(self):
        self._definitions: dict[str, FlowDefinition] = {}
        self._instances: dict[str, FlowInstance] = {}
        self._tasks: list[FlowTask] = []

    def create_definition(self, flow_code: str, flow_name: str, domain: str,
                           target_type: str, nodes: list[dict], description: str = "") -> FlowDefinition:
        if flow_code in {d.flow_code for d in self._definitions.values()}:
            raise ValueError(f"Flow code '{flow_code}' already exists")
        flow_nodes = []
        for n in nodes:
            flow_nodes.append(FlowNode(
                node_id=n.get("node_id", str(uuid.uuid4())[:8]),
                node_name=n.get("node_name", ""), node_type=n.get("node_type", "approval"),
                assignee_type=n.get("assignee_type", "user"),
                assignee_ids=n.get("assignee_ids", []),
                multi_approve_rule=n.get("multi_approve_rule", "any"),
                timeout_hours=n.get("timeout_hours", 72),
                next_node_id=n.get("next_node_id", ""),
            ))
        definition = FlowDefinition(
            flow_id=str(uuid.uuid4()), flow_code=flow_code, flow_name=flow_name,
            domain=domain, target_type=target_type, description=description,
            nodes=flow_nodes, status="active",
            created_at=datetime.now(UTC).isoformat(),
        )
        self._definitions[definition.flow_id] = definition
        return definition

    def start_instance(self, flow_code: str, tenant_id: str, business_id: str,
                        business_type: str, initiator_id: str) -> FlowInstance:
        definition = None
        for d in self._definitions.values():
            if d.flow_code == flow_code:
                definition = d
                break
        if not definition:
            raise ValueError(f"Flow '{flow_code}' not found")
        if not definition.nodes:
            raise ValueError("Flow has no nodes")

        first_node = definition.nodes[0]
        instance = FlowInstance(
            instance_id=str(uuid.uuid4()), flow_id=definition.flow_id,
            flow_code=flow_code, tenant_id=tenant_id,
            business_id=business_id, business_type=business_type,
            status="running", current_node_id=first_node.node_id,
            initiator_id=initiator_id,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._instances[instance.instance_id] = instance

        for assignee_id in first_node.assignee_ids:
            task = FlowTask(
                task_id=str(uuid.uuid4()), instance_id=instance.instance_id,
                node_id=first_node.node_id, node_name=first_node.node_name,
                assignee_id=assignee_id, status="pending",
                created_at=datetime.now(UTC).isoformat(),
            )
            self._tasks.append(task)

        return instance

    def complete_task(self, task_id: str, action: str = "approved", comment: str = "") -> dict:
        task = None
        for t in self._tasks:
            if t.task_id == task_id:
                task = t
                break
        if not task:
            return {"success": False, "error": "Task not found"}
        if task.status != "pending":
            return {"success": False, "error": f"Task is already '{task.status}'"}

        task.status = action
        task.comment = comment
        task.completed_at = datetime.now(UTC).isoformat()

        instance = self._instances.get(task.instance_id)
        if not instance:
            return {"success": True, "task_id": task_id, "warning": "Instance not found"}

        definition = self._definitions.get(instance.flow_id)
        if not definition:
            return {"success": True, "task_id": task_id}

        if action == "rejected":
            instance.status = "rejected"
            return {"success": True, "task_id": task_id, "instance_status": "rejected"}

        next_node = None
        for i, node in enumerate(definition.nodes):
            if node.node_id == task.node_id:
                if i + 1 < len(definition.nodes):
                    next_node = definition.nodes[i + 1]
                break

        if not next_node:
            instance.status = "completed"
            instance.completed_at = datetime.now(UTC).isoformat()
            return {"success": True, "task_id": task_id, "instance_status": "completed"}

        instance.current_node_id = next_node.node_id
        for assignee_id in next_node.assignee_ids:
            self._tasks.append(FlowTask(
                task_id=str(uuid.uuid4()), instance_id=instance.instance_id,
                node_id=next_node.node_id, node_name=next_node.node_name,
                assignee_id=assignee_id, status="pending",
                created_at=datetime.now(UTC).isoformat(),
            ))
        return {"success": True, "task_id": task_id, "instance_status": "running", "next_node": next_node.node_name}

    def get_instance(self, instance_id: str) -> FlowInstance | None:
        return self._instances.get(instance_id)

    def get_instance_tasks(self, instance_id: str) -> list[FlowTask]:
        return [t for t in self._tasks if t.instance_id == instance_id]

    def list_definitions(self, domain: str = "") -> list[FlowDefinition]:
        results = list(self._definitions.values())
        if domain:
            results = [d for d in results if d.domain == domain]
        return results
