from agent.context import ContextBuilder, ContextFragment, ContextLayer, ContextPack, ContextScope
from agent.storage import LocalWorkspaceStore


def test_context_builder_orders_layers_and_records_trace():
    pack = ContextPack.of(
        [
            ContextFragment(
                id="skill.review",
                layer=ContextLayer.SKILLS,
                text="Review code carefully.",
                source="skill:review",
                priority=50,
            ),
            ContextFragment(
                id="runtime.policy",
                layer=ContextLayer.RUNTIME_POLICY,
                text="Do not invent tool results.",
                source="runtime",
                priority=100,
            ),
            ContextFragment(
                id="project.agents",
                layer=ContextLayer.PROJECT_INSTRUCTIONS,
                text="Read files before editing.",
                source="AGENTS.md",
                priority=80,
                scope=ContextScope.PROJECT,
            ),
        ]
    )

    compiled = ContextBuilder().compile(pack)

    assert compiled.system_text.index("runtime.policy") < compiled.system_text.index("project.agents")
    assert compiled.system_text.index("project.agents") < compiled.system_text.index("skill.review")
    assert [item.id for item in compiled.trace] == ["runtime.policy", "project.agents", "skill.review"]
    assert all(item.included for item in compiled.trace)


def test_context_builder_drops_optional_fragments_over_budget():
    pack = ContextPack.of(
        [
            ContextFragment(
                id="system.identity",
                layer=ContextLayer.SYSTEM,
                text="Always keep this.",
                source="system",
                tokens=10,
            ),
            ContextFragment(
                id="memory.summary",
                layer=ContextLayer.MEMORY,
                text="Large optional memory.",
                source="memory",
                tokens=100,
            ),
        ]
    )

    compiled = ContextBuilder().compile(pack, budget_tokens=20)

    assert "system.identity" in compiled.system_text
    assert "memory.summary" not in compiled.system_text
    assert compiled.trace[1].included is False
    assert compiled.trace[1].reason == "budget"


def test_local_workspace_store_builds_stable_safe_paths(tmp_path):
    workspace = LocalWorkspaceStore(tmp_path).allocate(
        tenant_id="tenant 1",
        user_id="user 1",
        agent_id="agent/1",
        workspace_id="workspace 1",
        create=True,
    )

    assert workspace.tenant_id == "tenant-1"
    assert workspace.user_id == "user-1"
    assert workspace.agent_id == "agent-1"
    assert workspace.workspace_id == "workspace-1"
    assert workspace.path == tmp_path / "tenant-1" / "user-1" / "agent-1" / "workspace-1"
    assert workspace.path.exists()
    assert workspace.instruction_files() == [
        tmp_path / "tenant-1" / "user-1" / "AGENTS.md",
        tmp_path / "tenant-1" / "user-1" / "agent-1" / "AGENTS.md",
        tmp_path / "tenant-1" / "user-1" / "agent-1" / "workspace-1" / "AGENTS.md",
    ]
