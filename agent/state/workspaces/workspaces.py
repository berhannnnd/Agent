from __future__ import annotations

import re
from pathlib import Path

from agent.context.workspace import WorkspaceContext


_SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")


class LocalWorkspaceStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def allocate(
        self,
        tenant_id: str = "",
        user_id: str = "",
        agent_id: str = "",
        workspace_id: str = "",
        create: bool = False,
    ) -> WorkspaceContext:
        safe_tenant_id = _safe_id(tenant_id, default="default")
        safe_user_id = _safe_id(user_id, default="anonymous")
        safe_agent_id = _safe_id(agent_id, default="default")
        safe_workspace_id = _safe_id(workspace_id, default="default")
        path = self.root / safe_tenant_id / safe_user_id / safe_agent_id / safe_workspace_id
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return WorkspaceContext(
            tenant_id=safe_tenant_id,
            user_id=safe_user_id,
            agent_id=safe_agent_id,
            workspace_id=safe_workspace_id,
            root=self.root,
            path=path,
        )


def _safe_id(value: str, default: str) -> str:
    cleaned = _SAFE_ID.sub("-", str(value or "").strip()).strip(".-")
    return cleaned or default
