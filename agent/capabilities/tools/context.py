from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.context.workspace import WorkspaceContext
from agent.governance import SandboxPolicy


@dataclass(frozen=True)
class ToolRuntimeContext:
    workspace: WorkspaceContext
    sandbox: SandboxPolicy

    @classmethod
    def for_workspace(cls, workspace: WorkspaceContext) -> "ToolRuntimeContext":
        return cls(workspace=workspace, sandbox=SandboxPolicy.for_workspace(workspace.path))

    @classmethod
    def from_settings(cls, settings: Any, workspace: WorkspaceContext) -> "ToolRuntimeContext":
        allowed_commands = _csv_setting(getattr(settings.agent, "SANDBOX_ALLOWED_COMMANDS", ""))
        sandbox = SandboxPolicy.for_workspace(
            workspace.path,
            allow_file_write=bool(getattr(settings.agent, "SANDBOX_ALLOW_FILE_WRITE", False)),
            allow_process=bool(getattr(settings.agent, "SANDBOX_ALLOW_PROCESS", False)),
            allow_network=bool(getattr(settings.agent, "SANDBOX_ALLOW_NETWORK", False)),
            allowed_commands=allowed_commands,
        )
        return cls(workspace=workspace, sandbox=sandbox)


def _csv_setting(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]
