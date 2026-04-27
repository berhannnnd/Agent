import asyncio

from agent.definitions import AgentSpec
from agent.runs import InMemoryRunStore, RunStatus
from agent.schema import RuntimeEvent


def test_in_memory_run_store_tracks_agent_scope_and_events():
    store = InMemoryRunStore()
    spec = AgentSpec.from_overrides(
        tenant_id="tenant 1",
        user_id="user 1",
        agent_id="agent 1",
        workspace_id="workspace 1",
    )

    async def execute():
        record = await store.create_run(spec, run_id="run-1")
        record = await store.append_event("run-1", RuntimeEvent(type="text_delta", payload={"delta": "ok"}))
        record = await store.finish_run("run-1", RunStatus.FINISHED)
        loaded = await store.load_run("run-1")
        return record, loaded

    record, loaded = asyncio.run(execute())

    assert record.status == RunStatus.FINISHED
    assert loaded.agent_id == "agent 1"
    assert loaded.tenant_id == "tenant 1"
    assert loaded.user_id == "user 1"
    assert loaded.workspace_id == "workspace 1"
    assert loaded.events[0].payload["delta"] == "ok"
