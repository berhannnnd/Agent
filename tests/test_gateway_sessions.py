import asyncio

from agent.definitions import AgentSpec
from agent.runs import RunStatus
from agent.schema import RuntimeEvent
from gateway.sessions import GatewayRunService


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
