from __future__ import annotations

import shlex
from typing import Any

from agent.capabilities.tools.context import ToolRuntimeContext


GIT_STATUS_SCHEMA = {
    "type": "object",
    "properties": {
        "short": {"type": "boolean", "description": "Use short porcelain output."},
    },
}

GIT_DIFF_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Optional workspace-relative path to diff."},
        "staged": {"type": "boolean", "description": "Show staged changes."},
        "max_bytes": {"type": "integer", "minimum": 1, "maximum": 200000},
    },
}


async def git_status(context: ToolRuntimeContext, short: bool = True) -> dict[str, Any]:
    command = "git status --short" if short else "git status"
    return (await context.sandbox_client.run_command(command, timeout_seconds=20.0)).to_dict()


async def git_diff(
    context: ToolRuntimeContext,
    path: str = "",
    staged: bool = False,
    max_bytes: int = 20000,
) -> dict[str, Any]:
    command = "git diff"
    if staged:
        command += " --staged"
    if path:
        decision = context.sandbox.authorize_file_read(path)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        command += " -- %s" % shlex.quote(path)
    result = await context.sandbox_client.run_command(command, timeout_seconds=20.0)
    payload = result.to_dict()
    limit = max(1, min(int(max_bytes or 20000), 200000))
    stdout = str(payload["stdout"])
    payload["stdout"] = stdout[:limit]
    payload["truncated"] = len(stdout) > limit
    return payload
