from __future__ import annotations

import asyncio
import json
import shutil
import shlex
import subprocess
import uuid

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


class DockerSandboxProvider:
    name = "docker"

    def acquire(
        self,
        workspace: WorkspaceContext,
        policy: SandboxPolicy,
        profile: SandboxProfile | None = None,
        lease_id: str = "",
        metadata: dict | None = None,
    ) -> "DockerSandboxClient":
        if shutil.which("docker") is None:
            raise RuntimeError("docker CLI is not available")
        active_profile = profile or SandboxProfile(provider=self.name)
        lease = SandboxLease(
            lease_id=lease_id or "docker-%s" % uuid.uuid4().hex,
            provider=self.name,
            workspace=workspace,
            profile=active_profile,
            metadata=dict(metadata or {}),
        )
        return DockerSandboxClient(lease=lease, policy=policy)

    def release(self, client: SandboxClient) -> None:
        return None


class DockerSandboxClient:
    def __init__(self, lease: SandboxLease, policy: SandboxPolicy):
        self.lease = lease
        self.policy = policy

    def read_text(self, path: str, max_bytes: int = 20000) -> SandboxFileRead:
        decision = self.policy.authorize_file_read(path)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        relative = self.policy.relative_workspace_path(self.policy.resolve_workspace_path(path))
        limit = max(1, min(int(max_bytes or 20000), 200000))
        script = """
import json
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
limit = int(sys.argv[2])
if not path.is_file():
    raise FileNotFoundError(sys.argv[1])
data = path.read_bytes()
sys.stdout.write(json.dumps({
    "path": sys.argv[1],
    "content": data[:limit].decode("utf-8", errors="replace"),
    "bytes": min(len(data), limit),
    "truncated": len(data) > limit,
}))
"""
        payload = self._run_python_json(script, [relative, str(limit)])
        return SandboxFileRead(
            path=str(payload["path"]),
            content=str(payload["content"]),
            bytes=int(payload["bytes"]),
            truncated=bool(payload["truncated"]),
        )

    def list_dir(self, path: str = ".") -> SandboxDirectoryListing:
        decision = self.policy.authorize_file_read(path or ".")
        if not decision.allowed:
            raise PermissionError(decision.reason)
        relative = self.policy.relative_workspace_path(self.policy.resolve_workspace_path(path or "."))
        script = """
import json
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
if not path.is_dir():
    raise NotADirectoryError(sys.argv[1])
entries = [
    {"name": child.name, "path": child.as_posix(), "type": "directory" if child.is_dir() else "file"}
    for child in sorted(path.iterdir(), key=lambda item: item.name)
]
sys.stdout.write(json.dumps({"path": path.as_posix(), "entries": entries}))
"""
        payload = self._run_python_json(script, [relative])
        return SandboxDirectoryListing(
            path=str(payload["path"]),
            entries=[
                SandboxDirectoryEntry(name=str(item["name"]), path=str(item["path"]), type=str(item["type"]))
                for item in payload["entries"]
            ],
        )

    def write_text(self, path: str, content: str) -> SandboxFileWrite:
        decision = self.policy.authorize_file_write(path)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        relative = self.policy.relative_workspace_path(self.policy.resolve_workspace_path(path))
        command = "mkdir -p -- %s && cat > %s" % (
            shlex.quote(_posix_parent(relative)),
            shlex.quote(relative),
        )
        result = subprocess.run(
            self._docker_run_args(["sh", "-lc", command]),
            input=str(content).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace") or "docker write failed")
        return SandboxFileWrite(path=relative, bytes=len(str(content).encode("utf-8")))

    async def run_command(self, command: str, timeout_seconds: float = 20.0) -> SandboxCommandResult:
        decision = self.policy.authorize_process(command)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        process = await asyncio.create_subprocess_exec(
            *self._docker_run_args(["sh", "-lc", command]),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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
        relative = self.policy.relative_workspace_path(self.policy.resolve_workspace_path(path or "."))
        script = """
import json
import pathlib
import re
import sys
pattern = sys.argv[1]
root = pathlib.Path(sys.argv[2])
limit = max(1, min(int(sys.argv[3]), 1000))
flags = 0 if sys.argv[4] == "1" else re.IGNORECASE
matcher = re.compile(pattern, flags)
files = [root] if root.is_file() else sorted(item for item in root.rglob("*") if item.is_file())
matches = []
skip = {".git", "__pycache__", ".venv", "node_modules"}
for file_path in files:
    if any(part in skip for part in file_path.parts):
        continue
    try:
        handle = file_path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        continue
    with handle:
        for index, line in enumerate(handle, start=1):
            line = line.rstrip("\\n")
            if matcher.search(line):
                matches.append({"path": file_path.as_posix(), "line_number": index, "line": line[:1000]})
                if len(matches) >= limit:
                    print(json.dumps({"pattern": pattern, "path": root.as_posix(), "matches": matches, "truncated": True}))
                    raise SystemExit(0)
print(json.dumps({"pattern": pattern, "path": root.as_posix(), "matches": matches, "truncated": False}))
"""
        payload = self._run_python_json(script, [pattern, relative, str(max_results or 100), "1" if case_sensitive else "0"])
        return SandboxGrepResult(
            pattern=str(payload["pattern"]),
            path=str(payload["path"]),
            matches=[
                SandboxGrepMatch(
                    path=str(item["path"]),
                    line_number=int(item["line_number"]),
                    line=str(item["line"]),
                )
                for item in payload["matches"]
            ],
            truncated=bool(payload["truncated"]),
        )

    def _run_python_json(self, script: str, args: list[str]) -> dict:
        result = subprocess.run(
            self._docker_run_args(["python3", "-c", script, *args]),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace") or "docker command failed")
        return json.loads(result.stdout.decode("utf-8"))

    def _docker_run_args(self, command: list[str]) -> list[str]:
        profile = self.lease.profile
        args = [
            "docker",
            "run",
            "--rm",
            "-i",
            "-v",
            "%s:%s" % (self.policy.workspace_root.resolve(), profile.workdir),
            "-w",
            profile.workdir,
            "--network",
            profile.network_mode if self.policy.allow_network else "none",
        ]
        if profile.memory:
            args.extend(["--memory", profile.memory])
        if profile.cpus:
            args.extend(["--cpus", profile.cpus])
        args.append(profile.image)
        args.extend(command)
        return args


def _decode(value: bytes, max_bytes: int) -> str:
    truncated = value[: max(1, max_bytes)]
    suffix = "\n[truncated]" if len(value) > len(truncated) else ""
    return truncated.decode("utf-8", errors="replace") + suffix


def _posix_parent(path: str) -> str:
    if "/" not in path:
        return "."
    return path.rsplit("/", 1)[0] or "."
