from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from agent.context.workspace import WorkspaceContext
from agent.governance import SandboxPolicy


@dataclass(frozen=True)
class SandboxProfile:
    provider: str = "local"
    image: str = "python:3.12-slim"
    network_mode: str = "none"
    memory: str = ""
    cpus: str = ""
    ttl_seconds: int = 0
    workdir: str = "/workspace"


@dataclass(frozen=True)
class SandboxLease:
    lease_id: str
    provider: str
    workspace: WorkspaceContext
    profile: SandboxProfile
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SandboxFileRead:
    path: str
    content: str
    bytes: int
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "content": self.content,
            "bytes": self.bytes,
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class SandboxFileWrite:
    path: str
    bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "bytes": self.bytes}


@dataclass(frozen=True)
class SandboxDirectoryEntry:
    name: str
    path: str
    type: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "path": self.path, "type": self.type}


@dataclass(frozen=True)
class SandboxDirectoryListing:
    path: str
    entries: list[SandboxDirectoryEntry]

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "entries": [entry.to_dict() for entry in self.entries]}


@dataclass(frozen=True)
class SandboxCommandResult:
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
        }


@dataclass(frozen=True)
class SandboxGrepMatch:
    path: str
    line_number: int
    line: str

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "line_number": self.line_number, "line": self.line}


@dataclass(frozen=True)
class SandboxGrepResult:
    pattern: str
    path: str
    matches: list[SandboxGrepMatch]
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern,
            "path": self.path,
            "matches": [match.to_dict() for match in self.matches],
            "truncated": self.truncated,
        }


class SandboxClient(Protocol):
    lease: SandboxLease
    policy: SandboxPolicy

    def read_text(self, path: str, max_bytes: int = 20000) -> SandboxFileRead:
        raise NotImplementedError()

    def list_dir(self, path: str = ".") -> SandboxDirectoryListing:
        raise NotImplementedError()

    def write_text(self, path: str, content: str) -> SandboxFileWrite:
        raise NotImplementedError()

    async def run_command(self, command: str, timeout_seconds: float = 20.0) -> SandboxCommandResult:
        raise NotImplementedError()

    def grep(
        self,
        pattern: str,
        path: str = ".",
        max_results: int = 100,
        case_sensitive: bool = True,
    ) -> SandboxGrepResult:
        raise NotImplementedError()


class SandboxProvider(Protocol):
    name: str

    def acquire(
        self,
        workspace: WorkspaceContext,
        policy: SandboxPolicy,
        profile: SandboxProfile | None = None,
        lease_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SandboxClient:
        raise NotImplementedError()

    def release(self, client: SandboxClient) -> None:
        raise NotImplementedError()
