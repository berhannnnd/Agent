from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from agent.runtime import AgentResult, AgentSession
from agent.schema import RuntimeEvent
from agent.state.runs import RunRecord
from agent.tasks.engine import TaskEngine
from agent.tasks.types import TaskRecord, TaskStatus, TaskStepRecord, TaskStepStatus, TaskStore


class AgentSessionFactory(Protocol):
    async def create(self, task: TaskRecord) -> AgentSession:
        raise NotImplementedError()


class TaskRunCoordinator(Protocol):
    async def start(self, spec) -> RunRecord:
        raise NotImplementedError()

    async def record_events(self, run_id: str, events: list[RuntimeEvent]) -> None:
        raise NotImplementedError()

    async def pause_for_approval(self, run_id: str) -> None:
        raise NotImplementedError()

    async def finish(self, run_id: str, error: str = "") -> None:
        raise NotImplementedError()


@dataclass(frozen=True)
class TaskExecutionResult:
    task: TaskRecord
    step: TaskStepRecord
    run: RunRecord
    result: AgentResult


class TaskRunner:
    def __init__(
        self,
        store: TaskStore,
        run_coordinator: TaskRunCoordinator,
        session_factory: AgentSessionFactory,
    ):
        self.store = store
        self.engine = TaskEngine(store)
        self.run_coordinator = run_coordinator
        self.session_factory = session_factory

    async def run_task(self, task_id: str, step_name: str = "execute") -> TaskExecutionResult:
        task = await self.store.load_task(task_id)
        if task is None:
            raise KeyError("unknown task: %s" % task_id)
        spec = task.to_agent_spec()
        run = await self.run_coordinator.start(spec)
        step = await self.engine.add_step(
            task.task_id,
            name=step_name,
            input=task.input,
            run_id=run.run_id,
        )
        await self.engine.start_step(step.step_id, run_id=run.run_id)
        session = await self.session_factory.create(task)
        try:
            result = await session.send(step.input, run_id=run.run_id, task_id=task.task_id)
        except Exception as exc:
            await self.engine.fail_step(step.step_id, str(exc))
            await self.run_coordinator.finish(run.run_id, str(exc))
            raise

        await self.run_coordinator.record_events(run.run_id, result.events)
        if result.status == "awaiting_approval" or any(event.type == "tool_approval_required" for event in result.events):
            await self._mark_awaiting_approval(task.task_id, step.step_id)
            await self.run_coordinator.pause_for_approval(run.run_id)
        elif result.status == "finished":
            await self.engine.finish_step(step.step_id, output=result.content)
            await self.engine.finish_task(task.task_id)
            await self.run_coordinator.finish(run.run_id)
        else:
            await self.engine.fail_step(step.step_id, result.content)
            await self.run_coordinator.finish(run.run_id, result.content or "task failed")

        final_task = await self.store.load_task(task.task_id)
        final_step = await self.store.load_step(step.step_id)
        return TaskExecutionResult(
            task=final_task or task,
            step=final_step or step,
            run=run,
            result=result,
        )

    async def cancel_task(self, task_id: str) -> TaskRecord:
        return await self.engine.cancel_task(task_id)

    async def _mark_awaiting_approval(self, task_id: str, step_id: str) -> None:
        await self.store.set_task_status(task_id, TaskStatus.AWAITING_APPROVAL)
        await self.store.update_step_status(step_id, TaskStepStatus.AWAITING_APPROVAL)
