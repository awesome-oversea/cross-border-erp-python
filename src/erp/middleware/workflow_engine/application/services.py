from __future__ import annotations

from typing import TYPE_CHECKING

from erp.middleware.workflow_engine.domain.engine import WorkflowEngine
from erp.shared.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.middleware.workflow_engine")

_engine_instance = WorkflowEngine()


class WorkflowEngineService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._engine = _engine_instance

    async def create_definition(self, tenant_id: str, flow_code: str, flow_name: str,
                                 domain: str, target_type: str, nodes: list[dict],
                                 description: str = "") -> dict:
        definition = self._engine.create_definition(flow_code, flow_name, domain, target_type, nodes, description)
        return {"flow_id": definition.flow_id, "flow_code": definition.flow_code,
                "flow_name": definition.flow_name, "domain": definition.domain,
                "target_type": definition.target_type, "version": definition.version,
                "node_count": len(definition.nodes), "status": definition.status}

    async def start_instance(self, tenant_id: str, flow_code: str, business_id: str,
                              business_type: str, initiator_id: str) -> dict:
        instance = self._engine.start_instance(flow_code, tenant_id, business_id, business_type, initiator_id)
        return {"instance_id": instance.instance_id, "flow_code": instance.flow_code,
                "status": instance.status, "current_node_id": instance.current_node_id,
                "initiator_id": instance.initiator_id}

    async def get_instance(self, tenant_id: str, instance_id: str) -> dict | None:
        instance = self._engine.get_instance(instance_id)
        if not instance:
            return None
        tasks = self._engine.get_instance_tasks(instance_id)
        return {"instance_id": instance.instance_id, "flow_code": instance.flow_code,
                "business_id": instance.business_id, "business_type": instance.business_type,
                "status": instance.status, "current_node_id": instance.current_node_id,
                "initiator_id": instance.initiator_id, "created_at": instance.created_at,
                "tasks": [{"task_id": t.task_id, "node_name": t.node_name, "assignee_id": t.assignee_id,
                           "status": t.status, "comment": t.comment, "completed_at": t.completed_at}
                          for t in tasks]}

    async def complete_task(self, tenant_id: str, task_id: str, action: str = "approved",
                             comment: str = "") -> dict:
        return self._engine.complete_task(task_id, action, comment)

    async def list_definitions(self, tenant_id: str, domain: str = "") -> list[dict]:
        definitions = self._engine.list_definitions(domain)
        return [{"flow_id": d.flow_id, "flow_code": d.flow_code, "flow_name": d.flow_name,
                 "domain": d.domain, "target_type": d.target_type, "status": d.status}
                for d in definitions]
