from __future__ import annotations
from pathlib import Path

from agent.context.workspace import WorkspaceContext
from agent.state.workspaces.layout import WorkspaceLayout


class LocalWorkspaceStore:
    def __init__(self, root: Path, layout: str = "auto"):
        self.root = Path(root)
        self.layout = WorkspaceLayout(self.root, mode=layout)

    def allocate(
        self,
        tenant_id: str = "",
        user_id: str = "",
        agent_id: str = "",
        workspace_id: str = "",
        create: bool = False,
    ) -> WorkspaceContext:
        return self.layout.allocate(
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            workspace_id=workspace_id,
            create=create,
        )
