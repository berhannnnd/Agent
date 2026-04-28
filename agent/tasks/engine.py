from __future__ import annotations

from dataclasses import dataclass

from agent.specs import AgentSpec
from agent.tasks.types import (
    TaskAttemptRecord,
    TaskAttemptStatus,
    TaskRecord,
    TaskStatus,
    TaskStepRecord,
    TaskStepStatus,
    TaskStore,
)


@dataclass(frozen=True)
class TaskStepResult:
    task: TaskRecord
    step: TaskStepRecord
    attempt: TaskAttemptRecord | None = None


class TaskEngine:
    """Small state-machine facade for long-running task orchestration."""

    def __init__(self, store: TaskStore):
        self.store = store

    async def create_task(
        self,
        spec: AgentSpec,
        *,
        title: str,
        input: str,
        metadata: dict[str, str] | None = None,
    ) -> TaskRecord:
        return await self.store.create_task(spec, title=title, input=input, metadata=metadata)

    async def start_task(self, task_id: str) -> TaskRecord:
        task = await self.store.set_task_status(task_id, TaskStatus.RUNNING)
        if task is None:
            raise KeyError("unknown task: %s" % task_id)
        return task

    async def add_step(
        self,
        task_id: str,
        *,
        name: str,
        input: str = "",
        run_id: str = "",
        metadata: dict[str, str] | None = None,
    ) -> TaskStepRecord:
        steps = await self.store.list_steps(task_id)
        step = TaskStepRecord.create(
            task_id=task_id,
            index=len(steps),
            name=name,
            input=input,
            run_id=run_id,
            metadata=metadata,
        )
        return await self.store.add_step(step)

    async def start_step(self, step_id: str, run_id: str = "") -> TaskStepResult:
        step = await self.store.load_step(step_id)
        if step is None:
            raise KeyError("unknown task step: %s" % step_id)
        task = await self.store.set_task_status(step.task_id, TaskStatus.RUNNING)
        updated_step = await self.store.update_step_status(step_id, TaskStepStatus.RUNNING)
        if task is None or updated_step is None:
            raise KeyError("unknown task for step: %s" % step.task_id)
        attempt = await self.store.add_attempt(
            TaskAttemptRecord.create(task_id=step.task_id, step_id=step_id, run_id=run_id or step.run_id)
        )
        return TaskStepResult(task=task, step=updated_step, attempt=attempt)

    async def finish_step(self, step_id: str, output: str = "") -> TaskStepResult:
        step = await self.store.update_step_status(step_id, TaskStepStatus.SUCCEEDED, output=output)
        if step is None:
            raise KeyError("unknown task step: %s" % step_id)
        for attempt in reversed(await self.store.list_attempts(step_id)):
            if attempt.status == TaskAttemptStatus.RUNNING:
                await self.store.finish_attempt(attempt.attempt_id, TaskAttemptStatus.SUCCEEDED)
                break
        task = await self.store.set_task_status(step.task_id, TaskStatus.RUNNING)
        if task is None:
            raise KeyError("unknown task: %s" % step.task_id)
        return TaskStepResult(task=task, step=step)

    async def finish_task(self, task_id: str) -> TaskRecord:
        task = await self.store.set_task_status(task_id, TaskStatus.FINISHED)
        if task is None:
            raise KeyError("unknown task: %s" % task_id)
        return task

    async def fail_step(self, step_id: str, error: str) -> TaskStepResult:
        step = await self.store.update_step_status(step_id, TaskStepStatus.FAILED, error=error)
        if step is None:
            raise KeyError("unknown task step: %s" % step_id)
        for attempt in reversed(await self.store.list_attempts(step_id)):
            if attempt.status == TaskAttemptStatus.RUNNING:
                await self.store.finish_attempt(attempt.attempt_id, TaskAttemptStatus.FAILED, error=error)
                break
        task = await self.store.set_task_status(step.task_id, TaskStatus.ERROR)
        if task is None:
            raise KeyError("unknown task: %s" % step.task_id)
        return TaskStepResult(task=task, step=step)

    async def cancel_task(self, task_id: str) -> TaskRecord:
        task = await self.store.set_task_status(task_id, TaskStatus.CANCELED)
        if task is None:
            raise KeyError("unknown task: %s" % task_id)
        for step in await self.store.list_steps(task_id):
            if step.status in {TaskStepStatus.PENDING, TaskStepStatus.RUNNING, TaskStepStatus.AWAITING_APPROVAL}:
                await self.store.update_step_status(step.step_id, TaskStepStatus.CANCELED)
                for attempt in await self.store.list_attempts(step.step_id):
                    if attempt.status == TaskAttemptStatus.RUNNING:
                        await self.store.finish_attempt(attempt.attempt_id, TaskAttemptStatus.CANCELED)
        return task
