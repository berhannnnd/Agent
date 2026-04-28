from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.state.workspaces.workspaces import LocalWorkspaceStore
from agent.context.workspace import WorkspaceContext


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
        return WorkspaceContext(
            tenant_id=tenant_id or "local",
            user_id=user_id or "local",
            agent_id=agent_id or "default",
            workspace_id=workspace_id or path.name or "workspace",
            root=path,
            path=path,
        )
    configured_root = Path(str(getattr(settings.agent, "WORKSPACE_ROOT", ".agents/workspaces")))
    root = configured_root if configured_root.is_absolute() else Path(settings.server.ROOT_PATH) / configured_root
    return LocalWorkspaceStore(root).allocate(
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=agent_id,
        workspace_id=workspace_id,
        create=True,
    )
