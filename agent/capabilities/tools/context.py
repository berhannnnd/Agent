from __future__ import annotations

from dataclasses import dataclass

from agent.context.workspace import WorkspaceContext
from agent.governance import SandboxPolicy


@dataclass(frozen=True)
class ToolRuntimeContext:
    workspace: WorkspaceContext
    sandbox: SandboxPolicy

    @classmethod
    def for_workspace(cls, workspace: WorkspaceContext) -> "ToolRuntimeContext":
        return cls(workspace=workspace, sandbox=SandboxPolicy.for_workspace(workspace.path))
