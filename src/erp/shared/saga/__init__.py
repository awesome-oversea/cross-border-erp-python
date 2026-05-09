"""
Saga编排框架 (P1-022)

跨域分布式事务编排，支持 Choreography 和 Orchestration 两种模式。
核心概念:
  - Saga: 一个跨域业务流程，由多个 Step 组成
  - Step: 业务步骤，包含正向操作和逆向补偿操作
  - SagaInstance: Saga运行时实例，跟踪执行状态
  - SagaLog: 执行日志，用于恢复和审计

设计原则:
  1. 一期以 Choreography(编排)模式为主，通过领域事件驱动
  2. 关键场景(订单-库存-财务)使用 Orchestration(编排)模式
  3. 每个 Step 必须有对应的补偿动作
  4. 支持超时和重试
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class SagaStatus(StrEnum):
    PENDING = "pending"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


class StepStatus(StrEnum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"


@dataclass
class SagaStep:
    """
    业务步骤定义

    Attributes:
        step_id:    步骤唯一标识
        name:       步骤名称
        action:     正向操作(async callable)
        compensate: 逆向补偿操作(async callable)
        timeout_s:  超时秒数
    """
    step_id: str
    name: str
    action: callable = None  # type: ignore[assignment]
    compensate: callable = None  # type: ignore[assignment]
    timeout_s: int = 30
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class SagaDefinition:
    """
    Saga定义

    定义完整的跨域业务流程，包含步骤列表和补偿策略。
    """
    saga_id: str
    name: str
    domain: str
    steps: list[SagaStep] = field(default_factory=list)
    version: str = "v1"
    timeout_s: int = 300

    def add_step(self, step: SagaStep) -> SagaDefinition:
        self.steps.append(step)
        return self


@dataclass
class SagaInstance:
    """
    Saga运行时实例

    跟踪Saga的执行状态、当前步骤、执行结果和错误信息。
    支持暂停/恢复/补偿等生命周期管理。
    """
    instance_id: str = ""
    saga_id: str = ""
    tenant_id: str = ""
    trace_id: str = ""
    status: SagaStatus = SagaStatus.PENDING
    current_step: int = -1
    step_statuses: dict[str, StepStatus] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""


class SagaOrchestrator:
    """
    Saga编排器 — Orchestration模式

    集中控制Saga的执行流程，按顺序执行步骤，
    任一步骤失败时自动回滚已完成的步骤。
    """

    def __init__(self):
        self._sagas: dict[str, SagaDefinition] = {}
        self._instances: dict[str, SagaInstance] = {}

    def register(self, saga: SagaDefinition) -> None:
        self._sagas[saga.saga_id] = saga

    def get(self, saga_id: str) -> SagaDefinition | None:
        return self._sagas.get(saga_id)

    async def start(self, saga_id: str, tenant_id: str = "", trace_id: str = "", **kwargs) -> SagaInstance:
        """启动Saga流程: 按步骤顺序执行,失败时自动回滚已成功步骤"""
        """启动Saga流程"""
        saga = self._sagas.get(saga_id)
        if not saga:
            raise ValueError(f"Saga '{saga_id}' not found")

        instance = SagaInstance(
            instance_id=str(uuid.uuid4()),
            saga_id=saga_id,
            tenant_id=tenant_id,
            trace_id=trace_id,
            status=SagaStatus.STARTED,
            current_step=-1,
            started_at=datetime.now(UTC).isoformat(),
        )
        self._instances[instance.instance_id] = instance

        for idx, step in enumerate(saga.steps):
            instance.current_step = idx
            instance.step_statuses[step.step_id] = StepStatus.EXECUTING
            try:
                if step.action:
                    result = await step.action(instance, **kwargs)
                    instance.results[step.step_id] = result
                instance.step_statuses[step.step_id] = StepStatus.COMPLETED
            except Exception as e:
                instance.step_statuses[step.step_id] = StepStatus.FAILED
                instance.errors[step.step_id] = str(e)
                instance.status = SagaStatus.FAILED
                await self._compensate(instance, saga, idx)
                return instance

        instance.status = SagaStatus.COMPLETED
        instance.completed_at = datetime.now(UTC).isoformat()
        self._instances[instance.instance_id] = instance
        return instance

    async def _compensate(self, instance: SagaInstance, saga: SagaDefinition, failed_idx: int) -> None:
        """回滚已执行成功的步骤"""
        instance.status = SagaStatus.COMPENSATING
        for idx in range(failed_idx - 1, -1, -1):
            step = saga.steps[idx]
            if step.step_statuses.get(step.step_id) == StepStatus.COMPLETED and step.compensate:
                try:
                    await step.compensate(instance)
                    instance.step_statuses[step.step_id] = StepStatus.COMPENSATED
                except Exception as e:
                    instance.errors[f"compensate_{step.step_id}"] = str(e)
        instance.status = SagaStatus.COMPENSATED
        instance.completed_at = datetime.now(UTC).isoformat()

    def get_instance(self, instance_id: str) -> SagaInstance | None:
        return self._instances.get(instance_id)


# ---------------------------------------------------------------------------
# 预定义跨域Saga (关键业务流程)
# ---------------------------------------------------------------------------

def register_default_sagas(orchestrator: SagaOrchestrator) -> None:
    """注册系统预置跨域Saga流程"""

    # 订单履约Saga: 订单 → 库存 → 物流
    order_fulfillment = SagaDefinition(
        saga_id="order_fulfillment",
        name="订单履约流程",
        domain="oms",
        steps=[
            SagaStep(step_id="validate_order", name="校验订单"),
            SagaStep(step_id="reserve_inventory", name="预占库存"),
            SagaStep(step_id="allocate_warehouse", name="分配仓库"),
            SagaStep(step_id="create_shipment", name="创建发货单"),
            SagaStep(step_id="charge_payment", name="扣款处理"),
        ],
    )
    orchestrator.register(order_fulfillment)

    # 采购入库Saga: 采购 → 收货 → 入库 → 财务
    purchase_receipt = SagaDefinition(
        saga_id="purchase_receipt",
        name="采购入库流程",
        domain="scm",
        steps=[
            SagaStep(step_id="validate_po", name="校验采购单"),
            SagaStep(step_id="receive_goods", name="确认收货"),
            SagaStep(step_id="quality_inspect", name="质检处理"),
            SagaStep(step_id="warehouse_inbound", name="仓库入库"),
            SagaStep(step_id="cost_recording", name="成本记录"),
            SagaStep(step_id="payment_request", name="发起付款"),
        ],
    )
    orchestrator.register(purchase_receipt)

    # FBA补货Saga: 补货建议 → 备货 → 装箱 → 发运
    fba_replenishment = SagaDefinition(
        saga_id="fba_replenishment",
        name="FBA补货流程",
        domain="fba",
        steps=[
            SagaStep(step_id="create_plan", name="创建补货计划"),
            SagaStep(step_id="approve_plan", name="审批补货计划"),
            SagaStep(step_id="allocate_stock", name="分配库存"),
            SagaStep(step_id="pack_boxes", name="装箱打包"),
            SagaStep(step_id="create_shipment", name="创建FBA货件"),
            SagaStep(step_id="hand_carrier", name="交接物流商"),
        ],
    )
    orchestrator.register(fba_replenishment)

    # 退款Saga: 退款 → 库存回写 → 财务事件
    refund_process = SagaDefinition(
        saga_id="refund_process",
        name="退款处理流程",
        domain="crm",
        steps=[
            SagaStep(step_id="validate_refund", name="校验退款"),
            SagaStep(step_id="approve_refund", name="审批退款"),
            SagaStep(step_id="return_inventory", name="库存回写"),
            SagaStep(step_id="create_cost_event", name="生成财务事件"),
            SagaStep(step_id="notify_platform", name="通知平台"),
        ],
    )
    orchestrator.register(refund_process)


_default_orchestrator = SagaOrchestrator()
register_default_sagas(_default_orchestrator)


def get_saga_orchestrator() -> SagaOrchestrator:
    return _default_orchestrator
