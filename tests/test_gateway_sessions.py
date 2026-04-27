import asyncio

from agent.definitions import AgentSpec
from agent.runs import RunStatus
from agent.runtime import RuntimeCheckpoint
from agent.schema import RuntimeEvent
from gateway.sessions import GatewayRunService, create_checkpoint_store, create_run_store


def test_gateway_run_service_records_lifecycle_events():
    service = GatewayRunService()
    spec = AgentSpec.from_overrides(agent_id="agent-1", user_id="user-1")

    async def execute():
        run = await service.start(spec)
        await service.record_event(run.run_id, RuntimeEvent(type="text_delta", payload={"delta": "ok"}))
        await service.finish(run.run_id)
        return await service.store.load_run(run.run_id)

    record = asyncio.run(execute())

    assert record.status == RunStatus.FINISHED
    assert [event.type for event in record.events] == ["run_created", "text_delta"]
    assert record.events[0].payload["run_id"] == record.run_id


def test_gateway_run_service_marks_error_status():
    service = GatewayRunService()
    spec = AgentSpec.from_overrides(agent_id="agent-1")

    async def execute():
        run = await service.start(spec)
        await service.finish(run.run_id, "broken")
        return await service.store.load_run(run.run_id)

    record = asyncio.run(execute())

    assert record.status == RunStatus.ERROR


def test_gateway_run_service_marks_approval_status():
    service = GatewayRunService()
    spec = AgentSpec.from_overrides(agent_id="agent-1")

    async def execute():
        run = await service.start(spec)
        await service.pause_for_approval(run.run_id)
        return await service.store.load_run(run.run_id)

    record = asyncio.run(execute())

    assert record.status == RunStatus.AWAITING_APPROVAL


def test_gateway_run_store_factory_uses_file_store(tmp_path):
    class AgentConfig:
        RUN_STORE = "file"
        RUN_ROOT = "runs"

    class ServerConfig:
        ROOT_PATH = tmp_path

    class Settings:
        agent = AgentConfig()
        server = ServerConfig()

    store = create_run_store(Settings())
    spec = AgentSpec.from_overrides(agent_id="agent-1")

    async def execute():
        run = await store.create_run(spec, run_id="run-1")
        return await store.load_run(run.run_id)

    record = asyncio.run(execute())

    assert record.run_id == "run-1"
    assert (tmp_path / "runs" / "run-1.json").exists()


def test_gateway_store_factory_uses_sqlite(tmp_path):
    class AgentConfig:
        RUN_STORE = "sqlite"
        DB_PATH = "agents.db"

    class ServerConfig:
        ROOT_PATH = tmp_path

    class Settings:
        agent = AgentConfig()
        server = ServerConfig()

    run_store = create_run_store(Settings())
    checkpoint_store = create_checkpoint_store(Settings())
    spec = AgentSpec.from_overrides(agent_id="agent-1")

    async def execute():
        run = await run_store.create_run(spec, run_id="run-1")
        await checkpoint_store.save(
            RuntimeCheckpoint(
                run_id=run.run_id,
                step="finished",
                iteration=0,
                messages=[],
            )
        )
        return await run_store.load_run(run.run_id), await checkpoint_store.load(run.run_id)

    record, checkpoint = asyncio.run(execute())

    assert record.run_id == "run-1"
    assert checkpoint.step == "finished"
    assert (tmp_path / "agents.db").exists()
