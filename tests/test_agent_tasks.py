import asyncio

from agent.specs import AgentSpec
from agent.tasks import (
    InMemoryTaskStore,
    SQLiteTaskStore,
    TaskAttemptRecord,
    TaskAttemptStatus,
    TaskEngine,
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
