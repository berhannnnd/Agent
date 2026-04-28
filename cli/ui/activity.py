from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolActivity:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    risk: str = "unknown"
    status: str = "running"
    summary: str = ""
    is_error: bool = False


@dataclass
class TurnActivity:
    started_at: float = field(default_factory=time.monotonic)
    status: str = "finished"
    wrote_text: bool = False
    streamed_text: bool = False
    printed_assistant: bool = False
    assistant_line_open: bool = False
    assistant_after_tool: bool = False
    thinking_active: bool = False
    reasoning_chars: int = 0
    tool_count: int = 0
    showed_tool_details: bool = False
    tool_stats: dict[str, int] = field(default_factory=dict)
    tools: dict[str, ToolActivity] = field(default_factory=dict)

    def start_thinking(self) -> None:
        self.thinking_active = True
        self.reasoning_chars = 0
        self.tool_count = 0

    def add_reasoning(self, delta: str) -> None:
        self.reasoning_chars += len(delta)

    def record_tool_start(self, tool: ToolActivity) -> None:
        self.tools[tool.id] = tool
        self.tool_count += 1
        self.showed_tool_details = True

    def record_assistant_text(self) -> None:
        if self.tool_count:
            self.assistant_after_tool = True

    def record_tool_result(self, name: str, content: Any, *, tool_id: str = "", is_error: bool = False) -> str:
        summary = summarize_tool_result(name, content, is_error=is_error)
        if tool_id and tool_id in self.tools:
            activity = self.tools[tool_id]
            activity.status = "error" if is_error else "finished"
            activity.summary = summary
            activity.is_error = is_error
        record_tool_result_stats(self.tool_stats, name, content, is_error=is_error)
        return summary

    def consume_tool_summary(self) -> str:
        stats = self.tool_stats
        self.tool_stats = {}
        return tool_summary_sentence(stats)

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.started_at


def tool_activity_id(name: str, payload: dict[str, Any]) -> str:
    return str(payload.get("id") or payload.get("tool_call_id") or name)


def record_tool_result_stats(stats: dict[str, int], name: str, content: Any, *, is_error: bool = False) -> None:
    payload = _json_payload(content)
    if is_error:
        stats["failed"] = int(stats.get("failed", 0)) + 1
        return

    if name == "filesystem.list":
        stats["listed"] = int(stats.get("listed", 0)) + 1
        return
    if name == "filesystem.read":
        stats["read"] = int(stats.get("read", 0)) + 1
        return
    if name == "search.grep":
        stats["searched"] = int(stats.get("searched", 0)) + 1
        matches = len(payload.get("matches", [])) if isinstance(payload, dict) else 0
        stats["matches"] = int(stats.get("matches", 0)) + matches
        return
    if name in {"web.search", "web.map"}:
        stats["web"] = int(stats.get("web", 0)) + 1
        return
    if name == "web.extract":
        stats["extracted"] = int(stats.get("extracted", 0)) + 1
        return
    if name == "filesystem.write":
        stats["wrote"] = int(stats.get("wrote", 0)) + 1
        return
    if name == "patch.apply":
        files = payload.get("files", []) if isinstance(payload, dict) else []
        stats["patched"] = int(stats.get("patched", 0)) + max(1, len(files))
        return
    if name in {"shell.run", "test.run", "git.status", "git.diff"}:
        stats["ran"] = int(stats.get("ran", 0)) + 1
        if isinstance(payload, dict) and int(payload.get("exit_code", 0) or 0) != 0:
            stats["failed"] = int(stats.get("failed", 0)) + 1
        return

    stats["used"] = int(stats.get("used", 0)) + 1


def summarize_tool_result(name: str, content: Any, *, is_error: bool = False) -> str:
    stats: dict[str, int] = {}
    record_tool_result_stats(stats, name, content, is_error=is_error)
    return tool_summary_sentence(stats) or str(name)


def tool_summary_sentence(stats: dict[str, int]) -> str:
    if not stats:
        return ""
    parts: list[str] = []
    if stats.get("searched"):
        searched = plural(int(stats["searched"]), "pattern", "patterns")
        matches = int(stats.get("matches", 0))
        suffix = " with %s" % plural(matches, "match", "matches") if matches else ""
        parts.append("searched for %s%s" % (searched, suffix))
    if stats.get("web"):
        parts.append("searched the web %s" % plural(int(stats["web"]), "time", "times"))
    if stats.get("extracted"):
        parts.append("extracted %s" % plural(int(stats["extracted"]), "page", "pages"))
    if stats.get("read"):
        parts.append("read %s" % plural(int(stats["read"]), "file", "files"))
    if stats.get("listed"):
        parts.append("listed %s" % plural(int(stats["listed"]), "directory", "directories"))
    if stats.get("wrote"):
        parts.append("wrote %s" % plural(int(stats["wrote"]), "file", "files"))
    if stats.get("patched"):
        parts.append("patched %s" % plural(int(stats["patched"]), "file", "files"))
    if stats.get("ran"):
        parts.append("ran %s" % plural(int(stats["ran"]), "command", "commands"))
    if stats.get("used"):
        parts.append("used %s" % plural(int(stats["used"]), "tool", "tools"))
    if stats.get("failed"):
        parts.append("%s failed" % plural(int(stats["failed"]), "tool", "tools"))
    if not parts:
        return ""
    sentence = ", ".join(parts)
    return sentence[:1].upper() + sentence[1:]


def plural(count: int, singular: str, plural_text: str) -> str:
    return "%s %s" % (count, singular if count == 1 else plural_text)


def _json_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
