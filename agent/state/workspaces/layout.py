from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from agent.context.workspace import WorkspaceContext


_SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")

DEFAULT_TENANT_ID = "default"
DEFAULT_USER_ID = "anonymous"
DEFAULT_AGENT_ID = "default"
DEFAULT_WORKSPACE_ID = "default"
LOCAL_SCOPE_DIR = "local"


@dataclass(frozen=True)
class WorkspaceScope:
    tenant_id: str = DEFAULT_TENANT_ID
    user_id: str = DEFAULT_USER_ID
    agent_id: str = DEFAULT_AGENT_ID
    workspace_id: str = DEFAULT_WORKSPACE_ID

    @classmethod
    def from_values(
        cls,
        tenant_id: str = "",
        user_id: str = "",
        agent_id: str = "",
        workspace_id: str = "",
    ) -> "WorkspaceScope":
        return cls(
            tenant_id=safe_workspace_id(tenant_id, default=DEFAULT_TENANT_ID),
            user_id=safe_workspace_id(user_id, default=DEFAULT_USER_ID),
            agent_id=safe_workspace_id(agent_id, default=DEFAULT_AGENT_ID),
            workspace_id=safe_workspace_id(workspace_id, default=DEFAULT_WORKSPACE_ID),
        )

    @property
    def has_explicit_identity(self) -> bool:
        return self.tenant_id not in {DEFAULT_TENANT_ID, LOCAL_SCOPE_DIR} or self.user_id not in {
            DEFAULT_USER_ID,
            LOCAL_SCOPE_DIR,
        }


@dataclass(frozen=True)
class WorkspaceLayout:
    root: Path
    mode: str = "auto"

    def allocate(
        self,
        tenant_id: str = "",
        user_id: str = "",
        agent_id: str = "",
        workspace_id: str = "",
        create: bool = False,
    ) -> WorkspaceContext:
        scope = WorkspaceScope.from_values(
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            workspace_id=workspace_id,
        )
        path = self.path_for(scope)
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return WorkspaceContext(
            tenant_id=scope.tenant_id,
            user_id=scope.user_id,
            agent_id=scope.agent_id,
            workspace_id=scope.workspace_id,
            root=self.root,
            path=path,
            instruction_paths=self.instruction_files_for(scope, path),
        )

    def path_for(self, scope: WorkspaceScope) -> Path:
        mode = _normalize_mode(self.mode)
        if mode == "scoped" or (mode == "auto" and scope.has_explicit_identity):
            return self.root / scope.tenant_id / scope.user_id / scope.agent_id / scope.workspace_id
        return self.root / LOCAL_SCOPE_DIR / self.local_workspace_key(scope)

    def instruction_files_for(self, scope: WorkspaceScope, path: Path) -> tuple[Path, ...]:
        mode = _normalize_mode(self.mode)
        if mode == "scoped" or (mode == "auto" and scope.has_explicit_identity):
            return (
                self.root / scope.tenant_id / scope.user_id / "AGENTS.md",
                self.root / scope.tenant_id / scope.user_id / scope.agent_id / "AGENTS.md",
                path / "AGENTS.md",
            )
        return (
            self.root / LOCAL_SCOPE_DIR / "AGENTS.md",
            self.root / LOCAL_SCOPE_DIR / "agents" / scope.agent_id / "AGENTS.md",
            path / "AGENTS.md",
        )

    @staticmethod
    def local_workspace_key(scope: WorkspaceScope) -> str:
        if scope.workspace_id != DEFAULT_WORKSPACE_ID:
            return scope.workspace_id
        if scope.agent_id != DEFAULT_AGENT_ID:
            return scope.agent_id
        return DEFAULT_WORKSPACE_ID


def safe_workspace_id(value: str, default: str) -> str:
    cleaned = _SAFE_ID.sub("-", str(value or "").strip()).strip(".-")
    return cleaned or default


def _normalize_mode(mode: str) -> str:
    value = str(mode or "auto").strip().lower()
    if value in {"auto", "local", "scoped"}:
        return value
    return "auto"
