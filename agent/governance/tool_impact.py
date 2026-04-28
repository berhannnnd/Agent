from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from agent.governance.sandbox import classify_tool_risk
from agent.schema import ToolCall


MAX_PREVIEW_CHARS = 4000


@dataclass(frozen=True)
class ToolImpact:
    tool_name: str
    risk: str
    operations: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    writes_files: bool = False
    requires_network: bool = False
    diff_preview: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tool_name": self.tool_name,
            "risk": self.risk,
            "operations": list(self.operations),
            "paths": list(self.paths),
            "commands": list(self.commands),
            "domains": list(self.domains),
            "writes_files": self.writes_files,
            "requires_network": self.requires_network,
        }
        if self.diff_preview:
            payload["diff_preview"] = self.diff_preview
        if self.summary:
            payload["summary"] = self.summary
        return payload


def describe_tool_impact(call: ToolCall) -> ToolImpact:
    name = call.name
    arguments = dict(call.arguments or {})
    risk = classify_tool_risk(name).value
    if name == "filesystem.read":
        return _impact(name, risk, operations=["file_read"], paths=[_string(arguments.get("path"))])
    if name == "filesystem.list":
        return _impact(name, risk, operations=["file_read"], paths=[_string(arguments.get("path") or ".")])
    if name == "search.grep":
        return _impact(name, risk, operations=["file_read"], paths=[_string(arguments.get("path") or ".")])
    if name == "filesystem.write":
        path = _string(arguments.get("path"))
        return _impact(
            name,
            risk,
            operations=["file_write"],
            paths=[path],
            writes_files=True,
            diff_preview=_truncate(_string(arguments.get("content"))),
            summary="write %s" % path if path else "write file",
        )
    if name == "patch.apply":
        return _patch_impact(name, risk, arguments)
    if name in {"shell.run", "test.run"}:
        command = _string(arguments.get("command") or ("pytest" if name == "test.run" else ""))
        return _impact(name, risk, operations=["process"], commands=[command], summary=_program_summary(command))
    if name == "git.status":
        return _impact(name, risk, operations=["process"], commands=["git status --short"])
    if name == "git.diff":
        command = "git diff"
        if arguments.get("staged"):
            command = "git diff --staged"
        path = _string(arguments.get("path"))
        if path:
            command = "%s -- %s" % (command, shlex.quote(path))
        return _impact(name, risk, operations=["process"], commands=[command], paths=[path])
    if name.startswith("browser.") or name.startswith("web."):
        url = _string(arguments.get("url"))
        domain = _domain(url)
        return _impact(
            name,
            risk,
            operations=["network"],
            domains=[domain],
            requires_network=True,
            paths=_browser_paths(name, arguments),
            writes_files=name in {"browser.open", "browser.download"},
            summary="open %s" % domain if domain else "browser network access",
        )
    if name.startswith("mcp_"):
        return _impact(name, risk, operations=["mcp_call"], summary="external MCP tool call")
    return _impact(name, risk, operations=["tool_call"])


def _patch_impact(name: str, risk: str, arguments: dict[str, Any]) -> ToolImpact:
    paths: list[str] = []
    preview_parts: list[str] = []
    operations: list[str] = []
    for edit in _list_of_dicts(arguments.get("edits")):
        path = _string(edit.get("path"))
        if not path:
            continue
        paths.append(path)
        operations.append("file_patch")
        preview_parts.append(
            "%s\n--- old\n%s\n+++ new\n%s"
            % (path, _truncate(_string(edit.get("old_text")), 800), _truncate(_string(edit.get("new_text")), 800))
        )
    for create in _list_of_dicts(arguments.get("creates")):
        path = _string(create.get("path"))
        if not path:
            continue
        paths.append(path)
        operations.append("file_create")
        preview_parts.append("%s\n+++ content\n%s" % (path, _truncate(_string(create.get("content")), 800)))
    return _impact(
        name,
        risk,
        operations=operations or ["file_patch"],
        paths=paths,
        writes_files=not bool(arguments.get("dry_run")),
        diff_preview=_truncate("\n\n".join(preview_parts)),
        summary="patch %d file(s)" % len(set(paths)) if paths else "patch files",
    )


def _impact(
    tool_name: str,
    risk: str,
    *,
    operations: list[str] | None = None,
    paths: list[str] | None = None,
    commands: list[str] | None = None,
    domains: list[str] | None = None,
    writes_files: bool = False,
    requires_network: bool = False,
    diff_preview: str = "",
    summary: str = "",
) -> ToolImpact:
    return ToolImpact(
        tool_name=tool_name,
        risk=risk,
        operations=_unique(operations or []),
        paths=_unique(item for item in (paths or []) if item),
        commands=_unique(item for item in (commands or []) if item),
        domains=_unique(item for item in (domains or []) if item),
        writes_files=writes_files,
        requires_network=requires_network,
        diff_preview=diff_preview,
        summary=summary,
    )


def _browser_paths(name: str, arguments: dict[str, Any]) -> list[str]:
    if name == "browser.open":
        return [_string(arguments.get("output_path") or "artifacts/downloads/browser-open.html")]
    if name == "browser.download":
        return [_string(arguments.get("path") or "artifacts/downloads/download.bin")]
    return []


def _domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower()


def _program_summary(command: str) -> str:
    try:
        parts = shlex.split(command)
    except ValueError:
        return command
    return "run %s" % parts[0] if parts else command


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _truncate(value: str, limit: int = MAX_PREVIEW_CHARS) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[truncated]"


def _string(value: Any) -> str:
    return str(value or "")


def _unique(values) -> list[str]:
    result: list[str] = []
    seen = set()
    for value in values:
        text = str(value or "")
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
