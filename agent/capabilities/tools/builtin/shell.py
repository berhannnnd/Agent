from __future__ import annotations

import asyncio
import os
from typing import Any

from agent.capabilities.tools.context import ToolRuntimeContext


RUN_COMMAND_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "Shell command to run in the workspace."},
        "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 120},
    },
    "required": ["command"],
}


async def run_command(
    context: ToolRuntimeContext,
    command: str,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    decision = context.sandbox.authorize_process(command)
    if not decision.allowed:
        raise PermissionError(decision.reason)
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=str(context.workspace.path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_tool_env(context),
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=float(timeout_seconds or 20.0))
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise TimeoutError("command timed out") from exc
    return {
        "exit_code": process.returncode,
        "stdout": _decode(stdout, context.sandbox.max_output_bytes),
        "stderr": _decode(stderr, context.sandbox.max_output_bytes),
    }


def _tool_env(context: ToolRuntimeContext) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(context.workspace.path),
        "PWD": str(context.workspace.path),
        "AGENT_WORKSPACE": str(context.workspace.path),
    }


def _decode(value: bytes, max_bytes: int) -> str:
    truncated = value[: max(1, max_bytes)]
    suffix = "\n[truncated]" if len(value) > len(truncated) else ""
    return truncated.decode("utf-8", errors="replace") + suffix
