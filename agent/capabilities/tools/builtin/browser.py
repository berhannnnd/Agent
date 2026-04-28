from __future__ import annotations

import json
import shlex
from typing import Any

from agent.capabilities.tools.context import ToolRuntimeContext


BROWSER_OPEN_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {"type": "string", "description": "HTTP or HTTPS URL to fetch inside the sandbox."},
        "output_path": {
            "type": "string",
            "description": "Workspace-relative file path for the fetched page.",
        },
        "max_bytes": {"type": "integer", "minimum": 1, "maximum": 2000000},
    },
    "required": ["url"],
}

BROWSER_DOWNLOAD_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {"type": "string", "description": "HTTP or HTTPS URL to download inside the sandbox."},
        "path": {"type": "string", "description": "Workspace-relative output file path."},
        "max_bytes": {"type": "integer", "minimum": 1, "maximum": 20000000},
    },
    "required": ["url", "path"],
}


async def browser_open(
    context: ToolRuntimeContext,
    url: str,
    output_path: str = "artifacts/downloads/browser-open.html",
    max_bytes: int = 200000,
) -> dict[str, Any]:
    return await _fetch_to_workspace(
        context,
        url=url,
        output_path=output_path or "artifacts/downloads/browser-open.html",
        max_bytes=max_bytes,
        text_mode=True,
    )


async def browser_download(
    context: ToolRuntimeContext,
    url: str,
    path: str,
    max_bytes: int = 20000000,
) -> dict[str, Any]:
    return await _fetch_to_workspace(
        context,
        url=url,
        output_path=path,
        max_bytes=max_bytes,
        text_mode=False,
    )


async def _fetch_to_workspace(
    context: ToolRuntimeContext,
    *,
    url: str,
    output_path: str,
    max_bytes: int,
    text_mode: bool,
) -> dict[str, Any]:
    network = context.sandbox.authorize_network()
    if not network.allowed:
        raise PermissionError(network.reason)
    write = context.sandbox.authorize_file_write(output_path)
    if not write.allowed:
        raise PermissionError(write.reason)
    output_path = context.sandbox.relative_workspace_path(output_path)
    _validate_url(url)
    limit = max(1, min(int(max_bytes or 200000), 20000000))
    script = r"""
import json
import pathlib
import sys
import urllib.request

url = sys.argv[1]
output = pathlib.Path(sys.argv[2])
limit = int(sys.argv[3])
text_mode = sys.argv[4] == "1"
request = urllib.request.Request(url, headers={"User-Agent": "AgentsSandbox/0.1"})
with urllib.request.urlopen(request, timeout=20) as response:
    body = response.read(limit + 1)
    truncated = len(body) > limit
    body = body[:limit]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(body)
    payload = {
        "url": url,
        "path": output.as_posix(),
        "status": getattr(response, "status", 0),
        "content_type": response.headers.get("content-type", ""),
        "bytes": len(body),
        "truncated": truncated,
    }
    if text_mode:
        payload["text_preview"] = body[:4000].decode("utf-8", errors="replace")
    sys.stdout.write(json.dumps(payload))
"""
    command = "python3 -c %s %s %s %s %s" % (
        shlex.quote(script),
        shlex.quote(str(url)),
        shlex.quote(str(output_path)),
        shlex.quote(str(limit)),
        "1" if text_mode else "0",
    )
    result = await context.sandbox_client.run_command(command, timeout_seconds=30.0)
    if result.exit_code != 0:
        raise RuntimeError(result.stderr or result.stdout or "browser fetch failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("browser fetch returned invalid JSON") from exc


def _validate_url(url: str) -> None:
    if not str(url).startswith(("http://", "https://")):
        raise ValueError("browser tools only support http:// and https:// URLs")
