from __future__ import annotations

from typing import Dict, List, Optional

from agent.specs import AgentSpec
from agent.tasks.types import (
    TaskAttemptRecord,
    TaskAttemptStatus,
    TaskRecord,
    TaskStatus,
    TaskStepRecord,
    TaskStepStatus,
)


class InMemoryTaskStore:
    def __init__(self):
        self._tasks: Dict[str, TaskRecord] = {}
        self._steps: Dict[str, TaskStepRecord] = {}
        self._attempts: Dict[str, TaskAttemptRecord] = {}

    async def create_task(
        self,
        spec: AgentSpec,
        title: str,
        input: str,
        metadata: dict[str, str] | None = None,
    ) -> TaskRecord:
        task = TaskRecord.create(spec=spec, title=title, input=input, metadata=metadata)
        self._tasks[task.task_id] = task
        return task

    async def load_task(self, task_id: str) -> Optional[TaskRecord]:
        return self._tasks.get(task_id)

    async def list_tasks(self, tenant_id: str, user_id: str = "", agent_id: str = "") -> List[TaskRecord]:
        return sorted(
            [
                task
                for task in self._tasks.values()
                if task.tenant_id == tenant_id
                and task.user_id in ("", user_id)
                and task.agent_id in ("", agent_id)
            ],
            key=lambda task: (task.created_at, task.task_id),
        )

    async def set_task_status(self, task_id: str, status: TaskStatus) -> Optional[TaskRecord]:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        updated = task.with_status(status)
        self._tasks[task_id] = updated
        return updated

    async def add_step(self, step: TaskStepRecord) -> TaskStepRecord:
        self._steps[step.step_id] = step
        return step

    async def load_step(self, step_id: str) -> Optional[TaskStepRecord]:
        return self._steps.get(step_id)

    async def list_steps(self, task_id: str) -> List[TaskStepRecord]:
        return sorted(
            [step for step in self._steps.values() if step.task_id == task_id],
            key=lambda step: (step.index, step.created_at, step.step_id),
        )

    async def load_step_for_run(self, run_id: str) -> Optional[TaskStepRecord]:
        steps = sorted(
            [step for step in self._steps.values() if step.run_id == run_id],
            key=lambda step: (step.created_at, step.step_id),
            reverse=True,
        )
        return steps[0] if steps else None

    async def update_step_status(
        self,
        step_id: str,
        status: TaskStepStatus,
        *,
        output: str = "",
        error: str = "",
    ) -> Optional[TaskStepRecord]:
        step = self._steps.get(step_id)
        if step is None:
            return None
        updated = step.with_status(status, output=output, error=error)
        self._steps[step_id] = updated
        return updated

    async def add_attempt(self, attempt: TaskAttemptRecord) -> TaskAttemptRecord:
        self._attempts[attempt.attempt_id] = attempt
        return attempt

    async def list_attempts(self, step_id: str) -> List[TaskAttemptRecord]:
        return sorted(
            [attempt for attempt in self._attempts.values() if attempt.step_id == step_id],
            key=lambda attempt: (attempt.started_at, attempt.attempt_id),
        )

    async def finish_attempt(
        self,
        attempt_id: str,
        status: TaskAttemptStatus,
        error: str = "",
    ) -> Optional[TaskAttemptRecord]:
        attempt = self._attempts.get(attempt_id)
        if attempt is None:
            return None
        updated = attempt.finish(status, error=error)
        self._attempts[attempt_id] = updated
        return updated
