from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.capabilities.sandbox.factory import create_sandbox_client
from agent.capabilities.sandbox.local import LocalSandboxProvider
from agent.capabilities.sandbox.types import SandboxClient
from agent.context.workspace import WorkspaceContext
from agent.governance import SandboxPolicy


@dataclass(frozen=True)
class ToolRuntimeContext:
    workspace: WorkspaceContext
    sandbox: SandboxPolicy
    sandbox_client: SandboxClient | None = None

    def __post_init__(self) -> None:
        if self.sandbox_client is None:
            client = LocalSandboxProvider().acquire(self.workspace, self.sandbox)
            object.__setattr__(self, "sandbox_client", client)

    @classmethod
    def for_workspace(cls, workspace: WorkspaceContext) -> "ToolRuntimeContext":
        sandbox = SandboxPolicy.for_workspace(workspace.path)
        client = LocalSandboxProvider().acquire(workspace, sandbox)
        return cls(workspace=workspace, sandbox=sandbox, sandbox_client=client)

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
        client = create_sandbox_client(settings, workspace, sandbox)
        return cls(workspace=workspace, sandbox=sandbox, sandbox_client=client)


def _csv_setting(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]
