import asyncio

from agent.definitions import AgentProfile, AgentSpec, SQLiteAgentProfileStore
from agent.audit import ApprovalAuditRecord, SQLiteApprovalAuditStore
from agent.identity import SQLiteIdentityStore, TenantRecord, UserRecord
from agent.memory import MemoryRecord, MemoryScope, SQLiteMemoryStore
from agent.persistence import SQLiteDatabase
from agent.runs import RunStatus, SQLiteRunStore
from agent.runtime import RuntimeCheckpoint, SQLiteCheckpointStore
from agent.schema import Message, RuntimeEvent, ToolCall
from agent.security import CredentialRef, SQLiteCredentialRefStore
from agent.storage import SQLiteWorkspaceStore, WorkspaceRecord
from agent.tracing import SQLiteTraceStore, TraceSpan, TraceStatus


def test_sqlite_run_store_persists_records_and_events(tmp_path):
    store = SQLiteRunStore(SQLiteDatabase(tmp_path / "agents.db"))
    spec = AgentSpec.from_overrides(agent_id="agent-1", user_id="user-1", permission_profile="ask")

    async def execute():
        run = await store.create_run(spec, run_id="run-1")
        await store.append_event(
            run.run_id,
            RuntimeEvent(type="tool_approval_required", name="echo", payload={"approval_id": "call-1"}),
        )
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
                events=[
                    RuntimeEvent(
                        type="tool_approval_required",
                        name="echo",
                        payload={"approval_id": "call-1"},
                    )
                ],
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


def test_sqlite_trace_store_persists_run_spans(tmp_path):
    database = SQLiteDatabase(tmp_path / "agents.db")
    run_store = SQLiteRunStore(database)
    store = SQLiteTraceStore(database)

    async def execute():
        await run_store.create_run(AgentSpec.from_overrides(agent_id="agent-1"), run_id="run-1")
        span = TraceSpan.start(
            run_id="run-1",
            span_id="span-1",
            kind="tool",
            name="echo",
            parent_span_id="run-1:run",
            attributes={"tool_call": {"id": "call-1"}},
        )
        await store.save_span(span)
        await store.save_span(
            span.finish(TraceStatus.DONE, attributes={"tool_result": {"content": "ok"}})
        )
        return await SQLiteTraceStore(SQLiteDatabase(tmp_path / "agents.db")).list_for_run("run-1")

    spans = asyncio.run(execute())

    assert len(spans) == 1
    assert spans[0].span_id == "span-1"
    assert spans[0].status == TraceStatus.DONE
    assert spans[0].ended_at is not None
    assert spans[0].attributes["tool_call"] == {"id": "call-1"}
    assert spans[0].attributes["tool_result"] == {"content": "ok"}


def test_sqlite_identity_store_persists_tenants_and_users(tmp_path):
    database = SQLiteDatabase(tmp_path / "agents.db")
    store = SQLiteIdentityStore(database)

    async def execute():
        await store.save_tenant(TenantRecord(tenant_id="tenant-1", display_name="Tenant"))
        await store.save_user(
            UserRecord(
                tenant_id="tenant-1",
                user_id="user-1",
                display_name="User",
                roles=["admin"],
                metadata={"source": "test"},
            )
        )
        reopened = SQLiteIdentityStore(SQLiteDatabase(tmp_path / "agents.db"))
        return await reopened.load_tenant("tenant-1"), await reopened.list_users("tenant-1")

    tenant, users = asyncio.run(execute())

    assert tenant.display_name == "Tenant"
    assert users[0].user_id == "user-1"
    assert users[0].roles == ["admin"]
    assert users[0].metadata == {"source": "test"}


def test_sqlite_agent_profile_store_persists_redacted_specs(tmp_path):
    database = SQLiteDatabase(tmp_path / "agents.db")
    store = SQLiteAgentProfileStore(database)
    spec = AgentSpec.from_overrides(
        tenant_id="tenant-1",
        user_id="user-1",
        agent_id="agent-1",
        provider="openai-chat",
        api_key="secret",
        permission_profile="ask",
    )

    async def execute():
        await store.save(AgentProfile.from_spec(spec, name="Researcher"))
        reopened = SQLiteAgentProfileStore(SQLiteDatabase(tmp_path / "agents.db"))
        return await reopened.load("tenant-1", "user-1", "agent-1")

    profile = asyncio.run(execute())

    assert profile.name == "Researcher"
    assert profile.spec["model"]["provider"] == "openai-chat"
    assert "api_key" not in profile.spec["model"]
    assert profile.to_agent_spec().tool_permissions.mode == "ask"


def test_sqlite_workspace_memory_and_credential_refs_persist(tmp_path):
    database = SQLiteDatabase(tmp_path / "agents.db")
    workspace_store = SQLiteWorkspaceStore(database)
    memory_store = SQLiteMemoryStore(database)
    credential_store = SQLiteCredentialRefStore(database)

    async def execute():
        await workspace_store.save(
            WorkspaceRecord(
                tenant_id="tenant-1",
                user_id="user-1",
                agent_id="agent-1",
                workspace_id="workspace-1",
                path=str(tmp_path / "workspaces" / "workspace-1"),
            )
        )
        memory = MemoryRecord.create(
            tenant_id="tenant-1",
            user_id="user-1",
            agent_id="agent-1",
            workspace_id="workspace-1",
            scope=MemoryScope.WORKSPACE,
            content="User prefers concise answers.",
        )
        credential = CredentialRef.create(
            tenant_id="tenant-1",
            user_id="user-1",
            agent_id="agent-1",
            provider="openai",
            name="default",
            secret_ref="vault://tenant-1/openai/default",
        )
        await memory_store.save(memory)
        await credential_store.save(credential)

        reopened_database = SQLiteDatabase(tmp_path / "agents.db")
        return (
            await SQLiteWorkspaceStore(reopened_database).load("tenant-1", "user-1", "agent-1", "workspace-1"),
            await SQLiteMemoryStore(reopened_database).list_for_context("tenant-1", "user-1", "agent-1", "workspace-1"),
            await SQLiteCredentialRefStore(reopened_database).list_for_scope("tenant-1", "user-1", "agent-1"),
        )

    workspace, memories, credentials = asyncio.run(execute())

    assert workspace.workspace_id == "workspace-1"
    assert memories[0].content == "User prefers concise answers."
    assert memories[0].scope == MemoryScope.WORKSPACE
    assert credentials[0].secret_ref == "vault://tenant-1/openai/default"
