from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.context.workspace import WorkspaceContext
from agent.state.workspaces.layout import DEFAULT_AGENT_ID, DEFAULT_WORKSPACE_ID, LOCAL_SCOPE_DIR, safe_workspace_id
from agent.state.workspaces.workspaces import LocalWorkspaceStore


def resolve_workspace(
    settings: Any,
    tenant_id: str = "",
    user_id: str = "",
    agent_id: str = "",
    workspace_id: str = "",
    workspace_path: str = "",
):
    if workspace_path:
        path = Path(workspace_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path.mkdir(parents=True, exist_ok=True)
        resolved_agent_id = safe_workspace_id(agent_id, default=DEFAULT_AGENT_ID)
        resolved_workspace_id = safe_workspace_id(workspace_id, default=path.name or DEFAULT_WORKSPACE_ID)
        return WorkspaceContext(
            tenant_id=safe_workspace_id(tenant_id, default=LOCAL_SCOPE_DIR),
            user_id=safe_workspace_id(user_id, default=LOCAL_SCOPE_DIR),
            agent_id=resolved_agent_id,
            workspace_id=resolved_workspace_id,
            root=path,
            path=path,
            instruction_paths=(path / "AGENTS.md",),
        )
    configured_root = Path(str(getattr(settings.agent, "WORKSPACE_ROOT", ".agents/workspaces")))
    root = configured_root if configured_root.is_absolute() else Path(settings.server.ROOT_PATH) / configured_root
    return LocalWorkspaceStore(root, layout=getattr(settings.agent, "WORKSPACE_LAYOUT", "auto")).allocate(
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=agent_id,
        workspace_id=workspace_id,
        create=True,
    )
