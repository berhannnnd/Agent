import asyncio

from agent.specs import AgentSpec
from agent.runtime import AgentResult
from agent.schema import Message, RuntimeEvent
from agent.state.runs import InMemoryRunStore, RunStatus
from agent.tasks import (
    InMemoryTaskStore,
    SQLiteTaskStore,
    TaskAttemptRecord,
    TaskAttemptStatus,
    TaskEngine,
    TaskRunner,
    InMemoryTaskQueue,
    TaskWorker,
    TaskStatus,
    TaskStepRecord,
    TaskStepStatus,
)
from agent.persistence import SQLiteDatabase


def test_task_engine_tracks_step_attempt_lifecycle():
    store = InMemoryTaskStore()
    engine = TaskEngine(store)
    spec = AgentSpec.from_overrides(
        tenant_id="tenant-1",
        user_id="user-1",
        agent_id="agent-1",
        workspace_id="workspace-1",
    )

    async def execute():
        task = await engine.create_task(spec, title="Implement feature", input="Build the task engine")
        step = await engine.add_step(task.task_id, name="plan", input="Create a plan", run_id="run-1")
        started = await engine.start_step(step.step_id)
        finished = await engine.finish_step(step.step_id, output="done")
        completed = await engine.finish_task(task.task_id)
        return task, step, started, finished, completed, await store.list_attempts(step.step_id)

    task, step, started, finished, completed, attempts = asyncio.run(execute())

    assert task.status == TaskStatus.CREATED
    assert step.index == 0
    assert started.step.status == TaskStepStatus.RUNNING
    assert attempts[0].status == TaskAttemptStatus.SUCCEEDED
    assert finished.task.status == TaskStatus.RUNNING
    assert completed.status == TaskStatus.FINISHED
    assert finished.step.output == "done"


def test_sqlite_task_store_persists_tasks_steps_and_attempts(tmp_path):
    database = SQLiteDatabase(tmp_path / "agents.db")
    store = SQLiteTaskStore(database)
    spec = AgentSpec.from_overrides(tenant_id="tenant-1", user_id="user-1", agent_id="agent-1")

    async def execute():
        task = await store.create_task(spec, title="Long job", input="Do several steps", metadata={"kind": "test"})
        step = await store.add_step(
            TaskStepRecord.create(task_id=task.task_id, index=0, name="first", run_id="run-1")
        )
        attempt = await store.add_attempt(
            TaskAttemptRecord.create(task_id=task.task_id, step_id=step.step_id, run_id="run-1")
        )
        await store.finish_attempt(attempt.attempt_id, TaskAttemptStatus.FAILED, error="boom")
        await store.update_step_status(step.step_id, TaskStepStatus.FAILED, error="boom")
        await store.set_task_status(task.task_id, TaskStatus.ERROR)

        reopened = SQLiteTaskStore(SQLiteDatabase(tmp_path / "agents.db"))
        return (
            await reopened.load_task(task.task_id),
            await reopened.list_steps(task.task_id),
            await reopened.list_attempts(step.step_id),
        )

    task, steps, attempts = asyncio.run(execute())

    assert task.status == TaskStatus.ERROR
    assert task.metadata == {"kind": "test"}
    assert task.to_agent_spec().agent_id == "agent-1"
    assert steps[0].status == TaskStepStatus.FAILED
    assert steps[0].error == "boom"
    assert attempts[0].status == TaskAttemptStatus.FAILED
    assert attempts[0].ended_at is not None


class FakeRunCoordinator:
    def __init__(self):
        self.store = InMemoryRunStore()

    async def start(self, spec):
        run = await self.store.create_run(spec, run_id="run-task")
        return await self.store.set_status(run.run_id, RunStatus.RUNNING)

    async def record_events(self, run_id, events):
        for event in events:
            await self.store.append_event(run_id, event)

    async def pause_for_approval(self, run_id):
        await self.store.set_status(run_id, RunStatus.AWAITING_APPROVAL)

    async def finish(self, run_id, error=""):
        await self.store.set_status(run_id, RunStatus.ERROR if error else RunStatus.FINISHED)


class FakeSessionFactory:
    async def create(self, task):
        return FakeTaskSession()


class FakeTaskSession:
    async def send(self, text, run_id=None, task_id=None):
        return AgentResult(
            content="done: %s" % text,
            messages=[Message.from_text("assistant", "done")],
            events=[RuntimeEvent(type="model_message", name="assistant", payload={"content": "done"})],
        )


def test_task_runner_executes_task_through_run_coordinator():
    store = InMemoryTaskStore()
    coordinator = FakeRunCoordinator()

    async def execute():
        spec = AgentSpec.from_overrides(tenant_id="tenant-1", user_id="user-1", agent_id="agent-1")
        task = await store.create_task(spec, title="Run it", input="work")
        result = await TaskRunner(store, coordinator, FakeSessionFactory()).run_task(task.task_id)
        run = await coordinator.store.load_run(result.run.run_id)
        steps = await store.list_steps(task.task_id)
        return result, run, steps

    result, run, steps = asyncio.run(execute())

    assert result.task.status == TaskStatus.FINISHED
    assert result.step.status == TaskStepStatus.SUCCEEDED
    assert result.step.output == "done: work"
    assert run.status == RunStatus.FINISHED
    assert [event.type for event in run.events] == ["model_message"]
    assert steps[0].run_id == "run-task"


def test_task_worker_runs_queued_tasks_until_empty():
    store = InMemoryTaskStore()
    queue = InMemoryTaskQueue()
    coordinator = FakeRunCoordinator()

    async def execute():
        spec = AgentSpec.from_overrides(tenant_id="tenant-1", user_id="user-1", agent_id="agent-1")
        first = await store.create_task(spec, title="First", input="one")
        second = await store.create_task(spec, title="Second", input="two")
        await queue.enqueue(first.task_id)
        await queue.enqueue(second.task_id)
        results = await TaskWorker(queue, TaskRunner(store, coordinator, FakeSessionFactory())).run_until_empty()
        return results, await queue.size()

    results, size = asyncio.run(execute())

    assert [result.task.status for result in results] == [TaskStatus.FINISHED, TaskStatus.FINISHED]
    assert size == 0
