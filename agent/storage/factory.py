from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.storage.workspaces import LocalWorkspaceStore


def resolve_workspace(
    settings: Any,
    tenant_id: str = "",
    user_id: str = "",
    agent_id: str = "",
    workspace_id: str = "",
):
    configured_root = Path(str(getattr(settings.agent, "WORKSPACE_ROOT", ".agents/workspaces")))
    root = configured_root if configured_root.is_absolute() else Path(settings.server.ROOT_PATH) / configured_root
    return LocalWorkspaceStore(root).allocate(
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=agent_id,
        workspace_id=workspace_id,
        create=True,
    )
