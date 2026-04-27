import asyncio

from agent.definitions import AgentSpec
from agent.runs import RunStatus
from agent.runtime import RuntimeCheckpoint
from agent.schema import RuntimeEvent
from agent.tracing import InMemoryTraceStore, RuntimeTraceRecorder, TraceStatus
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


def test_gateway_run_service_records_trace_spans():
    trace_store = InMemoryTraceStore()
    service = GatewayRunService(trace_recorder=RuntimeTraceRecorder(trace_store))
    spec = AgentSpec.from_overrides(agent_id="agent-1", user_id="user-1")

    async def execute():
        run = await service.start(spec)
        await service.record_event(
            run.run_id,
            RuntimeEvent(
                type="tool_start",
                name="echo",
                payload={"id": "call-1", "name": "echo", "arguments": {"text": "hi"}},
            ),
        )
        await service.record_event(
            run.run_id,
            RuntimeEvent(
                type="tool_result",
                name="echo",
                payload={"tool_call_id": "call-1", "content": "ok", "is_error": False},
            ),
        )
        await service.finish(run.run_id)
        return run.run_id, await trace_store.list_for_run(run.run_id)

    run_id, spans = asyncio.run(execute())
    by_id = {span.span_id: span for span in spans}

    assert by_id[f"{run_id}:run"].status == TraceStatus.DONE
    assert by_id[f"{run_id}:run"].ended_at is not None
    assert by_id[f"{run_id}:tool:call-1"].status == TraceStatus.DONE
    assert by_id[f"{run_id}:tool:call-1"].attributes["tool_result"]["content"] == "ok"


def test_gateway_run_service_records_approval_trace_state():
    trace_store = InMemoryTraceStore()
    service = GatewayRunService(trace_recorder=RuntimeTraceRecorder(trace_store))
    spec = AgentSpec.from_overrides(agent_id="agent-1")

    async def execute():
        run = await service.start(spec)
        await service.record_event(
            run.run_id,
            RuntimeEvent(type="tool_approval_required", name="echo", payload={"approval_id": "call-1"}),
        )
        await service.pause_for_approval(run.run_id)
        waiting_root = await trace_store.load_span(f"{run.run_id}:run")
        await service.mark_running(run.run_id)
        await service.record_event(
            run.run_id,
            RuntimeEvent(
                type="tool_approval_decision",
                name="echo",
                payload={"approval_id": "call-1", "approved": False},
            ),
        )
        await service.finish(run.run_id)
        return run.run_id, waiting_root, await trace_store.list_for_run(run.run_id)

    run_id, waiting_root, spans = asyncio.run(execute())
    by_id = {span.span_id: span for span in spans}

    assert waiting_root.status == TraceStatus.WAITING
    assert waiting_root.ended_at is None
    assert by_id[f"{run_id}:run"].status == TraceStatus.DONE
    assert by_id[f"{run_id}:approval:call-1"].status == TraceStatus.CANCELED


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
