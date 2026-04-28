from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.capabilities.sandbox.factory import (
    create_sandbox_client,
    create_sandbox_client_from_profile,
    sandbox_policy_from_settings,
    sandbox_profile_from_settings,
)
from agent.capabilities.sandbox.local import LocalSandboxProvider
from agent.capabilities.sandbox.store import SandboxLeaseRecord, SandboxStore
from agent.capabilities.sandbox.types import SandboxClient, SandboxProfile
from agent.capabilities.sandbox.workspace import WorkspaceArtifacts
from agent.context.workspace import WorkspaceContext
from agent.governance import SandboxPolicy


@dataclass
class ToolRuntimeContext:
    workspace: WorkspaceContext
    sandbox: SandboxPolicy
    sandbox_client: SandboxClient | None = None
    sandbox_profile: SandboxProfile | None = None
    sandbox_store: SandboxStore | None = None
    task_id: str = ""
    artifacts: WorkspaceArtifacts | None = None

    def __post_init__(self) -> None:
        if self.artifacts is None:
            self.artifacts = WorkspaceArtifacts.ensure(self.workspace)
        if self.sandbox_profile is None:
            self.sandbox_profile = SandboxProfile(provider="local")
        if self.sandbox_client is None:
            self.sandbox_client = LocalSandboxProvider().acquire(self.workspace, self.sandbox, self.sandbox_profile)

    @classmethod
    def for_workspace(cls, workspace: WorkspaceContext) -> "ToolRuntimeContext":
        sandbox = SandboxPolicy.for_workspace(workspace.path)
        client = LocalSandboxProvider().acquire(workspace, sandbox)
        return cls(workspace=workspace, sandbox=sandbox, sandbox_client=client)

    @classmethod
    def from_settings(
        cls,
        settings: Any,
        workspace: WorkspaceContext,
        sandbox_store: SandboxStore | None = None,
        task_id: str = "",
    ) -> "ToolRuntimeContext":
        profile = sandbox_profile_from_settings(settings)
        sandbox = sandbox_policy_from_settings(settings, workspace, profile)
        client = create_sandbox_client(settings, workspace, sandbox)
        return cls(
            workspace=workspace,
            sandbox=sandbox,
            sandbox_client=client,
            sandbox_profile=profile,
            sandbox_store=sandbox_store,
            task_id=str(task_id or ""),
        )

    async def bind_execution_scope(self, run_id: str = "", task_id: str = "") -> SandboxClient:
        scoped_run_id = str(run_id or "")
        scoped_task_id = str(task_id or self.task_id or "")
        if not scoped_run_id:
            return self.sandbox_client
        lease_id = _scoped_lease_id(scoped_run_id, scoped_task_id)
        if self.sandbox_client and self.sandbox_client.lease.lease_id == lease_id:
            return self.sandbox_client
        metadata = {"run_id": scoped_run_id}
        if scoped_task_id:
            metadata["task_id"] = scoped_task_id
        if self.artifacts is not None:
            metadata.update({"artifacts_root": self.artifacts.root})
        self.sandbox_client = create_sandbox_client_from_profile(
            self.workspace,
            self.sandbox,
            self.sandbox_profile or SandboxProfile(provider="local"),
            lease_id=lease_id,
            metadata=metadata,
        )
        if self.sandbox_store is not None:
            lease = SandboxLeaseRecord.from_lease(self.sandbox_client.lease)
            await self.sandbox_store.save_lease(lease)
            await self.sandbox_store.record_event(lease.to_event("lease_acquired"))
        return self.sandbox_client


def _scoped_lease_id(run_id: str, task_id: str = "") -> str:
    parts = ["sandbox", _safe_token(run_id)]
    if task_id:
        parts.append(_safe_token(task_id))
    return "_".join(parts)


def _safe_token(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("_", "-", ".") else "-" for ch in str(value or "")).strip(".-") or "scope"
