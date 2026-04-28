import asyncio

from agent.capabilities.memory import InMemoryMemoryStore, MemoryRecord, MemoryScope
from agent.capabilities.tools import ToolRegistry, ToolRuntimeContext, register_builtin_tools
from agent.context import HeuristicContextCompactor, MemoryContextRetriever, MemoryRetrievalScope
from agent.context.workspace import WorkspaceContext
from agent.governance import LocalBase64PayloadProtector, SandboxPolicy, SecretRedactor, classify_tool_risk, ToolRisk
from agent.schema import Message


def test_builtin_tools_are_workspace_scoped_and_sandboxed(tmp_path):
    workspace_path = tmp_path / "tenant" / "user" / "agent" / "workspace"
    workspace_path.mkdir(parents=True)
    (workspace_path / "note.txt").write_text("hello", encoding="utf-8")
    workspace = WorkspaceContext(
        tenant_id="tenant",
        user_id="user",
        agent_id="agent",
        workspace_id="workspace",
        root=tmp_path,
        path=workspace_path,
    )
    registry = ToolRegistry()
    register_builtin_tools(registry, ToolRuntimeContext.for_workspace(workspace))

    async def execute():
        listed = await registry.execute("filesystem.list", {"path": "."})
        read = await registry.execute("filesystem.read", {"path": "note.txt"})
        escaped = await registry.execute("filesystem.read", {"path": "../secret.txt"})
        denied_write = await registry.execute("filesystem.write", {"path": "new.txt", "content": "x"})
        denied_shell = await registry.execute("shell.run", {"command": "echo hi"})
        return listed, read, escaped, denied_write, denied_shell

    listed, read, escaped, denied_write, denied_shell = asyncio.run(execute())

    assert "note.txt" in listed.content
    assert "hello" in read.content
    assert escaped.is_error is True
    assert "escapes workspace" in escaped.content
    assert denied_write.is_error is True
    assert "file write disabled" in denied_write.content
    assert denied_shell.is_error is True
    assert "process execution disabled" in denied_shell.content


def test_sandbox_policy_can_allow_specific_commands(tmp_path):
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    workspace = WorkspaceContext("tenant", "user", "agent", "workspace", tmp_path, workspace_path)
    policy = SandboxPolicy.for_workspace(workspace.path, allow_process=True, allowed_commands=("echo",))
    context = ToolRuntimeContext(workspace=workspace, sandbox=policy)
    registry = ToolRegistry()
    register_builtin_tools(registry, context)

    result = asyncio.run(registry.execute("shell.run", {"command": "echo hi"}))

    assert result.is_error is False
    assert "hi" in result.content
    assert classify_tool_risk("shell.run") == ToolRisk.HIGH


def test_memory_retriever_and_compactor_emit_context_fragments():
    store = InMemoryMemoryStore()

    async def retrieve():
        await store.save(
            MemoryRecord.create(
                tenant_id="tenant",
                user_id="user",
                agent_id="agent",
                workspace_id="workspace",
                scope=MemoryScope.WORKSPACE,
                content="Use concise implementation notes.",
            )
        )
        retriever = MemoryContextRetriever(store)
        return await retriever.fragments_for_scope(
            MemoryRetrievalScope("tenant", "user", agent_id="agent", workspace_id="workspace")
        )

    fragments = asyncio.run(retrieve())
    compaction = HeuristicContextCompactor().compact(
        [
            Message.from_text("user", "old request " * 200),
            Message.from_text("assistant", "old answer " * 200),
            Message.from_text("user", "new request"),
        ],
        max_context_tokens=20,
        target_tokens=10,
    )

    assert fragments[0].text == "Use concise implementation notes."
    assert fragments[0].metadata["scope"] == "workspace"
    assert compaction.dropped_messages > 0
    assert "Prior conversation summary" in compaction.as_fragment().text


def test_governance_security_redacts_and_protects_payloads_for_local_use():
    redacted = SecretRedactor().redact_mapping(
        {
            "api_key": "secret",
            "nested": {"refresh_token": "token", "safe": "value"},
            "items": [{"password": "pw"}],
        }
    )
    protector = LocalBase64PayloadProtector()
    protected = protector.protect(b"payload", key_ref="local://test")

    assert redacted["api_key"] == "[redacted]"
    assert redacted["nested"]["refresh_token"] == "[redacted]"
    assert redacted["nested"]["safe"] == "value"
    assert redacted["items"][0]["password"] == "[redacted]"
    assert protected.algorithm == "local-base64-not-encryption"
    assert protector.unprotect(protected) == b"payload"
