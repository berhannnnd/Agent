import asyncio
import shlex
import sys
from pathlib import Path

from agent.capabilities.sandbox import (
    InMemorySandboxStore,
    LocalSandboxProvider,
    SQLiteSandboxStore,
    SandboxEventRecord,
    SandboxLeaseRecord,
)
from agent.capabilities.tools import ToolRegistry, ToolRuntimeContext, register_builtin_tools
from agent.context.workspace import WorkspaceContext
from agent.governance import SandboxPolicy
from agent.persistence import SQLiteDatabase


def _workspace(tmp_path: Path) -> WorkspaceContext:
    path = tmp_path / "tenant" / "user" / "agent" / "workspace"
    path.mkdir(parents=True)
    return WorkspaceContext(
        tenant_id="tenant",
        user_id="user",
        agent_id="agent",
        workspace_id="workspace",
        root=tmp_path,
        path=path,
    )


def test_local_sandbox_client_keeps_data_in_workspace(tmp_path):
    workspace = _workspace(tmp_path)
    policy = SandboxPolicy.for_workspace(workspace.path, allow_file_write=True)
    client = LocalSandboxProvider().acquire(workspace, policy)

    written = client.write_text("notes/todo.txt", "ship sandbox tools")
    read = client.read_text("notes/todo.txt")
    listed = client.list_dir("notes")

    assert written.path == "notes/todo.txt"
    assert read.content == "ship sandbox tools"
    assert listed.entries[0].path == "notes/todo.txt"
    assert (workspace.path / "notes" / "todo.txt").read_text(encoding="utf-8") == "ship sandbox tools"


def test_builtin_tools_route_through_sandbox_client(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace.path / "note.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    policy = SandboxPolicy.for_workspace(
        workspace.path,
        allow_file_write=True,
        allow_process=True,
        allowed_commands=(Path(sys.executable).name,),
    )
    context = ToolRuntimeContext(workspace=workspace, sandbox=policy)
    registry = ToolRegistry()
    register_builtin_tools(registry, context)

    async def execute():
        grep = await registry.execute("search.grep", {"pattern": "beta"})
        write = await registry.execute("filesystem.write", {"path": "new.txt", "content": "ok"})
        test_run = await registry.execute(
            "test.run",
            {"command": "%s -c %s" % (shlex.quote(sys.executable), shlex.quote("print('tests ok')"))},
        )
        return grep, write, test_run

    grep, write, test_run = asyncio.run(execute())

    assert grep.is_error is False
    assert "note.txt" in grep.content
    assert write.is_error is False
    assert (workspace.path / "new.txt").read_text(encoding="utf-8") == "ok"
    assert test_run.is_error is False
    assert "tests ok" in test_run.content


def test_sandbox_policy_blocks_escaped_workspace_paths(tmp_path):
    workspace = _workspace(tmp_path)
    policy = SandboxPolicy.for_workspace(workspace.path, allow_file_write=True)
    client = LocalSandboxProvider().acquire(workspace, policy)

    try:
        client.write_text("../outside.txt", "no")
    except PermissionError as exc:
        assert "escapes workspace" in str(exc)
    else:
        raise AssertionError("escaped write was not blocked")


def test_sandbox_store_records_leases_and_events(tmp_path):
    database = SQLiteDatabase(tmp_path / "agents.db")
    store = SQLiteSandboxStore(database)
    workspace = _workspace(tmp_path)
    policy = SandboxPolicy.for_workspace(workspace.path)
    client = LocalSandboxProvider().acquire(workspace, policy)
    lease = SandboxLeaseRecord.from_lease(client.lease)

    async def persist():
        await store.save_lease(lease)
        await store.record_event(SandboxEventRecord(lease_id=lease.lease_id, event_type="acquired", payload={"tool": "filesystem.read"}))
        loaded = await store.load_lease(lease.lease_id)
        events = await store.list_events(lease.lease_id)
        await store.mark_released(lease.lease_id)
        released = await store.load_lease(lease.lease_id)
        return loaded, events, released

    loaded, events, released = asyncio.run(persist())

    assert loaded is not None
    assert loaded.provider == "local"
    assert events[0].event_type == "acquired"
    assert released is not None
    assert released.status == "released"


def test_in_memory_sandbox_store_records_release(tmp_path):
    store = InMemorySandboxStore()
    workspace = _workspace(tmp_path)
    policy = SandboxPolicy.for_workspace(workspace.path)
    client = LocalSandboxProvider().acquire(workspace, policy)
    lease = SandboxLeaseRecord.from_lease(client.lease)

    async def persist():
        await store.save_lease(lease)
        await store.mark_released(lease.lease_id)
        return await store.load_lease(lease.lease_id)

    loaded = asyncio.run(persist())

    assert loaded is not None
    assert loaded.status == "released"
