from __future__ import annotations

from typing import Any

from agent.context.workspace import WorkspaceContext
from agent.governance import SandboxPolicy

from .docker import DockerSandboxProvider
from .local import LocalSandboxProvider
from .types import SandboxClient, SandboxProfile


PROFILE_ALLOWED_COMMANDS = {
    "restricted": (),
    "coding": ("git", "python", "python3", "pytest", "make"),
    "test": ("python", "python3", "pytest", "make", "npm", "bun"),
    "browser": ("python", "python3", "node", "npm", "npx"),
}


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
    profile_name = str(getattr(agent, "SANDBOX_PROFILE", "restricted") or "restricted").strip().lower()
    return SandboxProfile(
        name=profile_name,
        provider=str(getattr(agent, "SANDBOX_PROVIDER", "local") or "local"),
        image=str(getattr(agent, "SANDBOX_IMAGE", "python:3.12-slim") or "python:3.12-slim"),
        network_mode=str(
            getattr(agent, "SANDBOX_NETWORK", _profile_network_mode(profile_name)) or _profile_network_mode(profile_name)
        ),
        memory=str(getattr(agent, "SANDBOX_MEMORY", "") or ""),
        cpus=str(getattr(agent, "SANDBOX_CPUS", "") or ""),
        ttl_seconds=int(getattr(agent, "SANDBOX_TTL_SECONDS", 0) or 0),
        workdir=str(getattr(agent, "SANDBOX_WORKDIR", "/workspace") or "/workspace"),
    )


def sandbox_policy_from_settings(settings: Any, workspace: WorkspaceContext, profile: SandboxProfile) -> SandboxPolicy:
    agent = getattr(settings, "agent", settings)
    allowed_commands = _merge_unique(
        list(PROFILE_ALLOWED_COMMANDS.get(profile.name, ())),
        _csv_setting(getattr(agent, "SANDBOX_ALLOWED_COMMANDS", "")),
    )
    return SandboxPolicy.for_workspace(
        workspace.path,
        allow_file_write=_bool_setting(
            getattr(agent, "SANDBOX_ALLOW_FILE_WRITE", None),
            default=profile.name in {"coding", "browser"},
        ),
        allow_process=_bool_setting(
            getattr(agent, "SANDBOX_ALLOW_PROCESS", None),
            default=profile.name in {"coding", "test", "browser"},
        ),
        allow_network=_bool_setting(
            getattr(agent, "SANDBOX_ALLOW_NETWORK", None),
            default=profile.name == "browser",
        ),
        allowed_commands=allowed_commands,
    )


def _profile_network_mode(profile_name: str) -> str:
    return "bridge" if profile_name == "browser" else "none"


def _csv_setting(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _bool_setting(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _merge_unique(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen = set()
    for group in groups:
        for item in group:
            if item and item not in seen:
                seen.add(item)
                merged.append(item)
    return merged
