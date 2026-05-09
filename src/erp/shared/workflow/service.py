from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, select

from erp.modules.sys.domain.events import ApprovalCompleted, ApprovalSubmitted
from erp.shared.context import actor_id_var, trace_id_var
from erp.shared.events.publisher import get_event_publisher
from erp.shared.exceptions import NotFoundException, ValidationException
from erp.shared.observability.logging import get_logger
from erp.shared.workflow.entities import ApprovalFlowDefinitionEntity, ApprovalInstanceEntity, ApprovalTaskEntity
from erp.shared.workflow.models import (
    ApprovalAction,
    ApprovalActionRequest,
    ApprovalFlowDefinition,
    ApprovalInstance,
    ApprovalInstanceResponse,
    ApprovalNodeConfig,
    ApprovalStatus,
    ApprovalSubmitRequest,
    ApprovalTaskResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("erp.workflow")


class ApprovalService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def define_flow(
        self,
        tenant_id: str,
        flow_code: str,
        flow_name: str,
        domain: str,
        target_type: str,
        nodes: list[ApprovalNodeConfig],
        description: str = "",
    ) -> ApprovalFlowDefinition:
        existing = await self._get_flow_by_code(flow_code, tenant_id)
        if existing:
            raise ValidationException(message=f"Flow code '{flow_code}' already exists")

        entity = ApprovalFlowDefinitionEntity(
            tenant_id=tenant_id,
            flow_code=flow_code,
            flow_name=flow_name,
            domain=domain,
            target_type=target_type,
            description=description,
            nodes_json=json.dumps([n.model_dump() for n in nodes], default=str),
        )
        self._session.add(entity)
        await self._session.flush()

        return ApprovalFlowDefinition(
            id=entity.id,
            tenant_id=tenant_id,
            flow_code=flow_code,
            flow_name=flow_name,
            domain=domain,
            target_type=target_type,
            description=description,
            nodes=nodes,
        )

    async def submit(
        self,
        tenant_id: str,
        req: ApprovalSubmitRequest,
        submitted_by: str = "",
    ) -> ApprovalInstance:
        flow = await self._get_flow_by_code(req.flow_code, tenant_id)
        if not flow:
            raise NotFoundException(message=f"Approval flow '{req.flow_code}' not found")

        nodes = self._parse_nodes(flow.nodes_json)
        if not nodes:
            raise ValidationException(message="Approval flow has no nodes")

        instance = ApprovalInstanceEntity(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            flow_id=flow.id,
            flow_code=req.flow_code,
            domain=req.domain,
            target_type=req.target_type,
            target_id=req.target_id,
            title=req.title,
            description=req.description,
            current_node_index=0,
            status=ApprovalStatus.PENDING.value,
            submitted_by=submitted_by or actor_id_var.get(""),
            submitted_at=datetime.now(UTC),
        )
        self._session.add(instance)
        await self._session.flush()

        first_node = nodes[0]
        task = ApprovalTaskEntity(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            instance_id=instance.id,
            node_id=first_node.node_id,
            node_name=first_node.node_name,
            assignee_id=first_node.approver_ids[0] if first_node.approver_ids else "",
            assignee_role_code=first_node.approver_role_codes[0] if first_node.approver_role_codes else "",
            status="pending",
        )
        self._session.add(task)
        await self._session.flush()

        publisher = get_event_publisher()
        await publisher.publish(ApprovalSubmitted(
            tenant_id=tenant_id,
            aggregate_id=instance.id,
            trace_id=trace_id_var.get(""),
            actor=instance.submitted_by,
            approval_id=instance.id,
            approval_type=req.target_type,
            business_id=req.target_id,
            submitter_id=instance.submitted_by,
            payload={
                "approval_id": instance.id,
                "approval_type": req.target_type,
                "business_id": req.target_id,
                "submitter_id": instance.submitted_by,
                "flow_code": req.flow_code,
                "domain": req.domain,
            },
        ))

        return ApprovalInstance(
            id=instance.id,
            tenant_id=tenant_id,
            flow_id=flow.id,
            flow_code=req.flow_code,
            domain=req.domain,
            target_type=req.target_type,
            target_id=req.target_id,
            title=req.title,
            description=req.description,
            current_node_index=0,
            status=ApprovalStatus.PENDING,
            submitted_by=instance.submitted_by,
            submitted_at=instance.submitted_at,
        )

    async def approve(
        self,
        task_id: str,
        tenant_id: str,
        req: ApprovalActionRequest,
        actor_id: str = "",
    ) -> ApprovalInstance:
        task = await self._get_task(task_id, tenant_id)
        if not task:
            raise NotFoundException(message=f"Task '{task_id}' not found")
        if task.status != "pending":
            raise ValidationException(message="Task is not pending")

        instance = await self._get_instance(task.instance_id, tenant_id)
        if not instance:
            raise NotFoundException(message="Instance not found")
        if instance.status != ApprovalStatus.PENDING.value:
            raise ValidationException(message="Instance is not pending")

        task.action = req.action.value
        task.comment = req.comment
        task.status = "completed"
        task.completed_at = datetime.now(UTC)
        await self._session.flush()

        if req.action == ApprovalAction.REJECT:
            instance.status = ApprovalStatus.REJECTED.value
            instance.completed_at = datetime.now(UTC)
            await self._session.flush()
            publisher = get_event_publisher()
            await publisher.publish(ApprovalCompleted(
                tenant_id=tenant_id,
                aggregate_id=instance.id,
                trace_id=trace_id_var.get(""),
                actor=actor_id,
                approval_id=instance.id,
                approval_type=instance.target_type,
                business_id=instance.target_id,
                result="rejected",
                payload={
                    "approval_id": instance.id,
                    "approval_type": instance.target_type,
                    "business_id": instance.target_id,
                    "result": "rejected",
                    "flow_code": instance.flow_code,
                    "domain": instance.domain,
                },
            ))
            return ApprovalInstance(
                id=instance.id, tenant_id=tenant_id, flow_id=instance.flow_id,
                flow_code=instance.flow_code, domain=instance.domain,
                target_type=instance.target_type, target_id=instance.target_id,
                title=instance.title, description=instance.description,
                current_node_index=instance.current_node_index,
                status=ApprovalStatus.REJECTED,
                submitted_by=instance.submitted_by, submitted_at=instance.submitted_at,
                completed_at=instance.completed_at,
            )

        flow = await self._get_flow_by_id(instance.flow_id, tenant_id)
        nodes = self._parse_nodes(flow.nodes_json) if flow else []

        next_index = instance.current_node_index + 1
        if next_index < len(nodes):
            instance.current_node_index = next_index
            await self._session.flush()

            next_node = nodes[next_index]
            new_task = ApprovalTaskEntity(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                instance_id=instance.id,
                node_id=next_node.node_id,
                node_name=next_node.node_name,
                assignee_id=next_node.approver_ids[0] if next_node.approver_ids else "",
                assignee_role_code=next_node.approver_role_codes[0] if next_node.approver_role_codes else "",
                status="pending",
            )
            self._session.add(new_task)
            await self._session.flush()
        else:
            instance.status = ApprovalStatus.APPROVED.value
            instance.completed_at = datetime.now(UTC)
            await self._session.flush()
            publisher = get_event_publisher()
            await publisher.publish(ApprovalCompleted(
                tenant_id=tenant_id,
                aggregate_id=instance.id,
                trace_id=trace_id_var.get(""),
                actor=actor_id,
                approval_id=instance.id,
                approval_type=instance.target_type,
                business_id=instance.target_id,
                result="approved",
                payload={
                    "approval_id": instance.id,
                    "approval_type": instance.target_type,
                    "business_id": instance.target_id,
                    "result": "approved",
                    "flow_code": instance.flow_code,
                    "domain": instance.domain,
                },
            ))

        return ApprovalInstance(
            id=instance.id, tenant_id=tenant_id, flow_id=instance.flow_id,
            flow_code=instance.flow_code, domain=instance.domain,
            target_type=instance.target_type, target_id=instance.target_id,
            title=instance.title, description=instance.description,
            current_node_index=instance.current_node_index,
            status=ApprovalStatus(instance.status),
            submitted_by=instance.submitted_by, submitted_at=instance.submitted_at,
            completed_at=instance.completed_at,
        )

    async def get_pending_tasks(self, tenant_id: str, assignee_id: str = "") -> list[ApprovalTaskResponse]:
        conditions = [ApprovalTaskEntity.tenant_id == tenant_id, ApprovalTaskEntity.status == "pending"]
        if assignee_id:
            conditions.append(ApprovalTaskEntity.assignee_id == assignee_id)
        stmt = select(ApprovalTaskEntity).where(*conditions).order_by(ApprovalTaskEntity.created_at.desc())
        result = await self._session.execute(stmt)
        return [ApprovalTaskResponse.model_validate(t) for t in result.scalars().all()]

    async def get_instance(self, instance_id: str, tenant_id: str) -> ApprovalInstanceResponse | None:
        instance = await self._get_instance(instance_id, tenant_id)
        if not instance:
            return None
        return ApprovalInstanceResponse.model_validate(instance)

    async def get_instance_or_raise(self, instance_id: str, tenant_id: str) -> ApprovalInstanceResponse:
        result = await self.get_instance(instance_id, tenant_id)
        if not result:
            raise NotFoundException(message=f"Approval instance '{instance_id}' not found")
        return result

    async def get_instance_tasks(self, instance_id: str, tenant_id: str) -> list[ApprovalTaskResponse]:
        stmt = select(ApprovalTaskEntity).where(
            ApprovalTaskEntity.instance_id == instance_id,
            ApprovalTaskEntity.tenant_id == tenant_id,
        ).order_by(ApprovalTaskEntity.created_at)
        result = await self._session.execute(stmt)
        return [ApprovalTaskResponse.model_validate(t) for t in result.scalars().all()]

    async def _get_flow_by_code(self, flow_code: str, tenant_id: str) -> ApprovalFlowDefinitionEntity | None:
        stmt = select(ApprovalFlowDefinitionEntity).where(
            and_(
                ApprovalFlowDefinitionEntity.flow_code == flow_code,
                ApprovalFlowDefinitionEntity.tenant_id == tenant_id,
                ApprovalFlowDefinitionEntity.status == "active",
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_flow_by_id(self, flow_id: str, tenant_id: str) -> ApprovalFlowDefinitionEntity | None:
        stmt = select(ApprovalFlowDefinitionEntity).where(
            ApprovalFlowDefinitionEntity.id == flow_id,
            ApprovalFlowDefinitionEntity.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_instance(self, instance_id: str, tenant_id: str) -> ApprovalInstanceEntity | None:
        stmt = select(ApprovalInstanceEntity).where(
            ApprovalInstanceEntity.id == instance_id,
            ApprovalInstanceEntity.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_task(self, task_id: str, tenant_id: str) -> ApprovalTaskEntity | None:
        stmt = select(ApprovalTaskEntity).where(
            ApprovalTaskEntity.id == task_id,
            ApprovalTaskEntity.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _parse_nodes(nodes_json: str) -> list[ApprovalNodeConfig]:
        try:
            data = json.loads(nodes_json)
            return [ApprovalNodeConfig(**n) for n in data]
        except Exception:
            return []
