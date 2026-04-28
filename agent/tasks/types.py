from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, List, Optional, Protocol
from uuid import uuid4

from agent.specs import AgentSpec


class TaskStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_APPROVAL = "awaiting_approval"
    FINISHED = "finished"
    ERROR = "error"
    CANCELED = "canceled"


class TaskStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELED = "canceled"


class TaskAttemptStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    title: str
    input: str
    agent_id: str = ""
    tenant_id: str = ""
    user_id: str = ""
    workspace_id: str = ""
    status: TaskStatus = TaskStatus.CREATED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, str] = field(default_factory=dict)
    spec: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        spec: AgentSpec,
        title: str,
        input: str,
        task_id: str = "",
        metadata: dict[str, str] | None = None,
    ) -> "TaskRecord":
        resolved = spec.with_workspace_defaults()
        return cls(
            task_id=task_id or "task_%s" % uuid4().hex,
            title=title,
            input=input,
            agent_id=resolved.agent_id or resolved.workspace.agent_id,
            tenant_id=resolved.workspace.tenant_id,
            user_id=resolved.workspace.user_id,
            workspace_id=resolved.workspace.workspace_id,
            metadata=dict(metadata or {}),
            spec=resolved.to_dict(include_secrets=False),
        )

    def with_status(self, status: TaskStatus) -> "TaskRecord":
        return replace(self, status=status, updated_at=time.time())

    def to_agent_spec(self) -> AgentSpec:
        return AgentSpec.from_dict(self.spec)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "input": self.input,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
            "spec": dict(self.spec),
        }


@dataclass(frozen=True)
class TaskStepRecord:
    step_id: str
    task_id: str
    index: int
    name: str
    input: str = ""
    run_id: str = ""
    status: TaskStepStatus = TaskStepStatus.PENDING
    output: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        index: int,
        name: str,
        input: str = "",
        run_id: str = "",
        step_id: str = "",
        metadata: dict[str, str] | None = None,
    ) -> "TaskStepRecord":
        return cls(
            step_id=step_id or "step_%s" % uuid4().hex,
            task_id=task_id,
            index=index,
            name=name,
            input=input,
            run_id=run_id,
            metadata=dict(metadata or {}),
        )

    def with_status(self, status: TaskStepStatus, *, output: str = "", error: str = "") -> "TaskStepRecord":
        return replace(
            self,
            status=status,
            output=output or self.output,
            error=error or self.error,
            updated_at=time.time(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "task_id": self.task_id,
            "index": self.index,
            "name": self.name,
            "input": self.input,
            "run_id": self.run_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TaskAttemptRecord:
    attempt_id: str
    task_id: str
    step_id: str
    run_id: str = ""
    status: TaskAttemptStatus = TaskAttemptStatus.RUNNING
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    error: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        step_id: str,
        run_id: str = "",
        attempt_id: str = "",
        metadata: dict[str, str] | None = None,
    ) -> "TaskAttemptRecord":
        return cls(
            attempt_id=attempt_id or "attempt_%s" % uuid4().hex,
            task_id=task_id,
            step_id=step_id,
            run_id=run_id,
            metadata=dict(metadata or {}),
        )

    def finish(self, status: TaskAttemptStatus, error: str = "") -> "TaskAttemptRecord":
        return replace(self, status=status, error=error, ended_at=time.time())

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "run_id": self.run_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "error": self.error,
            "metadata": dict(self.metadata),
        }


class TaskStore(Protocol):
    async def create_task(self, spec: AgentSpec, title: str, input: str, metadata: dict[str, str] | None = None) -> TaskRecord:
        raise NotImplementedError()

    async def load_task(self, task_id: str) -> Optional[TaskRecord]:
        raise NotImplementedError()

    async def list_tasks(self, tenant_id: str, user_id: str = "", agent_id: str = "") -> List[TaskRecord]:
        raise NotImplementedError()

    async def set_task_status(self, task_id: str, status: TaskStatus) -> Optional[TaskRecord]:
        raise NotImplementedError()

    async def add_step(self, step: TaskStepRecord) -> TaskStepRecord:
        raise NotImplementedError()

    async def load_step(self, step_id: str) -> Optional[TaskStepRecord]:
        raise NotImplementedError()

    async def list_steps(self, task_id: str) -> List[TaskStepRecord]:
        raise NotImplementedError()

    async def update_step_status(
        self,
        step_id: str,
        status: TaskStepStatus,
        *,
        output: str = "",
        error: str = "",
    ) -> Optional[TaskStepRecord]:
        raise NotImplementedError()

    async def add_attempt(self, attempt: TaskAttemptRecord) -> TaskAttemptRecord:
        raise NotImplementedError()

    async def list_attempts(self, step_id: str) -> List[TaskAttemptRecord]:
        raise NotImplementedError()

    async def finish_attempt(
        self,
        attempt_id: str,
        status: TaskAttemptStatus,
        error: str = "",
    ) -> Optional[TaskAttemptRecord]:
        raise NotImplementedError()
