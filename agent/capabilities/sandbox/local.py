from __future__ import annotations

import asyncio
import os
import re
import uuid
from pathlib import Path

from agent.context.workspace import WorkspaceContext
from agent.governance import SandboxPolicy

from .types import (
    SandboxClient,
    SandboxCommandResult,
    SandboxDirectoryEntry,
    SandboxDirectoryListing,
    SandboxFileRead,
    SandboxFileWrite,
    SandboxGrepMatch,
    SandboxGrepResult,
    SandboxLease,
    SandboxProfile,
)


class LocalSandboxProvider:
    name = "local"

    def acquire(
        self,
        workspace: WorkspaceContext,
        policy: SandboxPolicy,
        profile: SandboxProfile | None = None,
    ) -> "LocalSandboxClient":
        lease = SandboxLease(
            lease_id="local-%s" % uuid.uuid4().hex,
            provider=self.name,
            workspace=workspace,
            profile=profile or SandboxProfile(provider=self.name),
        )
        return LocalSandboxClient(lease=lease, policy=policy)

    def release(self, client: SandboxClient) -> None:
        return None


class LocalSandboxClient:
    def __init__(self, lease: SandboxLease, policy: SandboxPolicy):
        self.lease = lease
        self.policy = policy

    def read_text(self, path: str, max_bytes: int = 20000) -> SandboxFileRead:
        decision = self.policy.authorize_file_read(path)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        resolved = self.policy.resolve_workspace_path(path)
        if not resolved.is_file():
            raise FileNotFoundError(str(path))
        limit = max(1, min(int(max_bytes or 20000), 200000))
        data = resolved.read_bytes()[:limit]
        size = resolved.stat().st_size
        return SandboxFileRead(
            path=self.policy.relative_workspace_path(resolved),
            content=data.decode("utf-8", errors="replace"),
            bytes=len(data),
            truncated=size > limit,
        )

    def list_dir(self, path: str = ".") -> SandboxDirectoryListing:
        decision = self.policy.authorize_file_read(path or ".")
        if not decision.allowed:
            raise PermissionError(decision.reason)
        resolved = self.policy.resolve_workspace_path(path or ".")
        if not resolved.is_dir():
            raise NotADirectoryError(str(path))
        entries = [
            SandboxDirectoryEntry(
                name=child.name,
                path=self.policy.relative_workspace_path(child),
                type="directory" if child.is_dir() else "file",
            )
            for child in sorted(resolved.iterdir(), key=lambda item: item.name)
        ]
        return SandboxDirectoryListing(path=self.policy.relative_workspace_path(resolved), entries=entries)

    def write_text(self, path: str, content: str) -> SandboxFileWrite:
        decision = self.policy.authorize_file_write(path)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        resolved = self.policy.resolve_workspace_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        text = str(content)
        resolved.write_text(text, encoding="utf-8")
        return SandboxFileWrite(
            path=self.policy.relative_workspace_path(resolved),
            bytes=len(text.encode("utf-8")),
        )

    async def run_command(self, command: str, timeout_seconds: float = 20.0) -> SandboxCommandResult:
        decision = self.policy.authorize_process(command)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(self.policy.workspace_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._tool_env(),
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=float(timeout_seconds or 20.0))
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return SandboxCommandResult(command=command, exit_code=-1, stderr="command timed out", timed_out=True)
        return SandboxCommandResult(
            command=command,
            exit_code=int(process.returncode or 0),
            stdout=_decode(stdout, self.policy.max_output_bytes),
            stderr=_decode(stderr, self.policy.max_output_bytes),
        )

    def grep(
        self,
        pattern: str,
        path: str = ".",
        max_results: int = 100,
        case_sensitive: bool = True,
    ) -> SandboxGrepResult:
        decision = self.policy.authorize_file_read(path or ".")
        if not decision.allowed:
            raise PermissionError(decision.reason)
        root = self.policy.resolve_workspace_path(path or ".")
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            matcher = re.compile(pattern, flags)
        except re.error as exc:
            raise ValueError("invalid regex pattern: %s" % exc) from exc
        limit = max(1, min(int(max_results or 100), 1000))
        files = [root] if root.is_file() else sorted(item for item in root.rglob("*") if item.is_file())
        matches: list[SandboxGrepMatch] = []
        truncated = False
        for file_path in files:
            if _should_skip_file(file_path):
                continue
            for line_number, line in _iter_text_lines(file_path):
                if matcher.search(line):
                    matches.append(
                        SandboxGrepMatch(
                            path=self.policy.relative_workspace_path(file_path),
                            line_number=line_number,
                            line=line[:1000],
                        )
                    )
                    if len(matches) >= limit:
                        truncated = True
                        return SandboxGrepResult(
                            pattern=pattern,
                            path=self.policy.relative_workspace_path(root),
                            matches=matches,
                            truncated=truncated,
                        )
        return SandboxGrepResult(
            pattern=pattern,
            path=self.policy.relative_workspace_path(root),
            matches=matches,
            truncated=truncated,
        )

    def _tool_env(self) -> dict[str, str]:
        workspace = str(self.policy.workspace_root)
        return {
            "PATH": os.environ.get("PATH", ""),
            "HOME": workspace,
            "PWD": workspace,
            "AGENT_WORKSPACE": workspace,
        }


def _decode(value: bytes, max_bytes: int) -> str:
    truncated = value[: max(1, max_bytes)]
    suffix = "\n[truncated]" if len(value) > len(truncated) else ""
    return truncated.decode("utf-8", errors="replace") + suffix


def _iter_text_lines(path: Path):
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for index, line in enumerate(handle, start=1):
                yield index, line.rstrip("\n")
    except OSError:
        return


def _should_skip_file(path: Path) -> bool:
    return any(part in {".git", "__pycache__", ".venv", "node_modules"} for part in path.parts)
