import asyncio

from agent.definitions import AgentSpec
from agent.persistence import SQLiteDatabase
from agent.runs import RunStatus, SQLiteRunStore
from agent.runtime import RuntimeCheckpoint, SQLiteCheckpointStore
from agent.schema import Message, RuntimeEvent, ToolCall
from agent.security import ApprovalAuditRecord, SQLiteApprovalAuditStore


def test_sqlite_run_store_persists_records_and_events(tmp_path):
    store = SQLiteRunStore(SQLiteDatabase(tmp_path / "agents.db"))
    spec = AgentSpec.from_overrides(agent_id="agent-1", user_id="user-1", permission_profile="ask")

    async def execute():
        run = await store.create_run(spec, run_id="run-1")
        await store.append_event(run.run_id, RuntimeEvent(type="tool_approval_required", name="echo", payload={"approval_id": "call-1"}))
        await store.set_status(run.run_id, RunStatus.AWAITING_APPROVAL)
        return await SQLiteRunStore(SQLiteDatabase(tmp_path / "agents.db")).load_run("run-1")

    record = asyncio.run(execute())

    assert record.status == RunStatus.AWAITING_APPROVAL
    assert record.user_id == "user-1"
    assert record.events[0].type == "tool_approval_required"
    assert record.to_agent_spec().tool_permissions.mode == "ask"


def test_sqlite_checkpoint_store_persists_pending_tools(tmp_path):
    call = ToolCall(id="call-1", name="echo", arguments={"text": "hi"})
    store = SQLiteCheckpointStore(SQLiteDatabase(tmp_path / "agents.db"))

    async def execute():
        await store.save(
            RuntimeCheckpoint(
                run_id="run-1",
                step="approval_required",
                iteration=2,
                messages=[Message.from_text("assistant", "", tool_calls=[call])],
                events=[RuntimeEvent(type="tool_approval_required", name="echo", payload={"approval_id": "call-1"})],
                pending_tool_calls=[call],
                tool_approvals={"call-1": True},
            )
        )
        return await SQLiteCheckpointStore(SQLiteDatabase(tmp_path / "agents.db")).load("run-1")

    checkpoint = asyncio.run(execute())

    assert checkpoint.step == "approval_required"
    assert checkpoint.iteration == 2
    assert checkpoint.pending_tool_calls[0].name == "echo"
    assert checkpoint.tool_approvals == {"call-1": True}


def test_sqlite_approval_audit_store_records_decisions(tmp_path):
    database = SQLiteDatabase(tmp_path / "agents.db")
    run_store = SQLiteRunStore(database)
    store = SQLiteApprovalAuditStore(database)
    call = ToolCall(id="call-1", name="echo", arguments={"text": "hi"})

    async def execute():
        await run_store.create_run(AgentSpec.from_overrides(agent_id="agent-1"), run_id="run-1")
        await store.record(
            ApprovalAuditRecord.from_tool_call(
                run_id="run-1",
                call=call,
                approved=False,
                reason="not needed",
            )
        )
        return await SQLiteApprovalAuditStore(SQLiteDatabase(tmp_path / "agents.db")).list_for_run("run-1")

    records = asyncio.run(execute())

    assert len(records) == 1
    assert records[0].approval_id == "call-1"
    assert records[0].approved is False
    assert records[0].tool_call["arguments"] == {"text": "hi"}
