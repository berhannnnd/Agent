from __future__ import annotations

from typing import Any

from agent.context.workspace import WorkspaceContext
from agent.governance import SandboxPolicy

from .docker import DockerSandboxProvider
from .local import LocalSandboxProvider
from .types import SandboxClient, SandboxProfile


def create_sandbox_client(
    settings: Any,
    workspace: WorkspaceContext,
    policy: SandboxPolicy,
    *,
    lease_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> SandboxClient:
    profile = sandbox_profile_from_settings(settings)
    return create_sandbox_client_from_profile(
        workspace,
        policy,
        profile,
        lease_id=lease_id,
        metadata=metadata,
    )


def create_sandbox_client_from_profile(
    workspace: WorkspaceContext,
    policy: SandboxPolicy,
    profile: SandboxProfile,
    *,
    lease_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> SandboxClient:
    provider_name = profile.provider.lower().strip() or "local"
    if provider_name == "docker":
        return DockerSandboxProvider().acquire(workspace, policy, profile, lease_id=lease_id, metadata=metadata)
    if provider_name == "local":
        return LocalSandboxProvider().acquire(workspace, policy, profile, lease_id=lease_id, metadata=metadata)
    raise ValueError("unknown sandbox provider: %s" % profile.provider)


def sandbox_profile_from_settings(settings: Any) -> SandboxProfile:
    agent = getattr(settings, "agent", settings)
    return SandboxProfile(
        provider=str(getattr(agent, "SANDBOX_PROVIDER", "local") or "local"),
        image=str(getattr(agent, "SANDBOX_IMAGE", "python:3.12-slim") or "python:3.12-slim"),
        network_mode=str(getattr(agent, "SANDBOX_NETWORK", "none") or "none"),
        memory=str(getattr(agent, "SANDBOX_MEMORY", "") or ""),
        cpus=str(getattr(agent, "SANDBOX_CPUS", "") or ""),
        ttl_seconds=int(getattr(agent, "SANDBOX_TTL_SECONDS", 0) or 0),
        workdir=str(getattr(agent, "SANDBOX_WORKDIR", "/workspace") or "/workspace"),
    )
