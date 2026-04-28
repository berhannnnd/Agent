from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from rich.console import Console
from rich.table import Table
from rich.text import Text

from agent.schema import RuntimeEvent
from cli.commands import COMMANDS
from cli.ui.activity import ToolActivity, TurnActivity, plural
from cli.ui.adapter import RuntimeEventAdapter
from cli.ui.events import UIEvent


class TerminalUI:
    def __init__(self, console: Console | None = None):
        self.console = console or Console(highlight=False)
        self.event_adapter = RuntimeEventAdapter()

    def startup(
        self,
        session,
        *,
        profile: str,
        permission: str,
        sandbox_provider: str,
        tools: Iterable[str],
        model_profile: str = "",
    ) -> None:
        model_label = _model_label(model_profile, session.runtime.protocol, session.runtime.model)
        if getattr(session, "workspace", None) is not None:
            workspace = _short_path(str(session.workspace.path))
        else:
            workspace = "no workspace"
        tool_list = list(tools)

        self.console.print(Text.assemble(("Agents Code", "bold cyan"), ("  ", "dim"), (model_label, "bold")))
        self.console.print(
            Text.assemble(
                ("  ", "dim"),
                (workspace, "dim"),
                ("  ", "dim"),
                profile,
                (" · ", "dim"),
                permission,
                (" · ", "dim"),
                sandbox_provider,
                (" · ", "dim"),
                str(len(tool_list)),
                " tools",
            )
        )
        self.console.print(
            Text.assemble(("  ", "dim"), ("/help", "dim"), " ", ("/model", "dim"), " ", ("/status", "dim"), " ", ("/doctor", "dim"))
        )

    def help(self) -> None:
        table = Table.grid(padding=(0, 2))
        table.add_column(style="cyan")
        table.add_column(style="dim")
        self.console.print(Text("commands", style="bold"))
        for command in COMMANDS:
            label = ", ".join((command.name, *command.aliases))
            table.add_row(label, command.action)
        self.console.print(table)

    def status(self, session, *, profile: str, permission: str, tools: Iterable[str], model_profile: str = "") -> None:
        rows = {
            "model": "%s · %s" % (session.runtime.protocol, session.runtime.model),
            "profile": profile,
            "permission": permission,
            "messages": str(max(0, len(getattr(session, "messages", [])) - 1)),
            "tokens": _estimate_session_tokens(session),
            "tools": str(len(list(tools))),
        }
        if model_profile:
            rows["model profile"] = model_profile
        endpoint = _model_endpoint(session)
        if endpoint:
            rows["endpoint"] = endpoint
        if getattr(session, "workspace", None) is not None:
            rows["workspace"] = str(session.workspace.path)
        self.key_values("Status", rows)

    def model(self, session, profiles: Iterable[Any] = ()) -> None:
        profile_list = list(profiles)
        if not profile_list:
            self.key_values(
                "Model",
                {
                    "protocol": str(session.runtime.protocol),
                    "model": str(session.runtime.model),
                },
            )
            return
        active_protocol = str(session.runtime.protocol)
        active_model = str(session.runtime.model)
        active_base_url = _model_base_url(session).rstrip("/")
        self.console.print(Text("models", style="bold"))
        for profile in profile_list:
            profile_base_url = str(getattr(profile, "base_url", "") or "").rstrip("/")
            is_active = (
                getattr(profile, "protocol", "") == active_protocol
                and getattr(profile, "model", "") == active_model
                and (not active_base_url or not profile_base_url or active_base_url == profile_base_url)
            )
            status = "ready" if getattr(profile, "configured", False) else "missing key/model"
            marker = "●" if is_active else " "
            name = str(getattr(profile, "name", ""))
            protocol = str(getattr(profile, "protocol", ""))
            model = str(getattr(profile, "model", "")) or "-"
            endpoint = _short_endpoint(str(getattr(profile, "endpoint", "")) or "-", limit=22)
            status_suffix = "" if status == "ready" else "  %s" % status
            self.console.print(
                Text.assemble(
                    ("%s " % marker, "bold cyan" if is_active else "dim"),
                    (name.ljust(16), "bold" if is_active else ""),
                    (" %s · %s" % (protocol, model), "cyan" if is_active else ""),
                    ("  %s" % endpoint, "dim"),
                    (status_suffix, "yellow" if status != "ready" else "dim"),
                )
            )

    def model_switched(self, session, profile: str = "") -> None:
        runtime = "%s · %s" % (session.runtime.protocol, session.runtime.model)
        if profile:
            self.status_line("model", "switched to %s  profile %s" % (runtime, profile), "cyan")
            return
        self.status_line("model", "switched to %s" % runtime, "cyan")

    def doctor(
        self,
        session,
        *,
        profiles: Iterable[Any],
        tools: Iterable[str],
        env_file: str,
        model_profile: str = "",
    ) -> None:
        profile_list = list(profiles)
        workspace = getattr(session, "workspace", None)
        workspace_path = Path(str(workspace.path)) if workspace is not None else None
        rows = {
            "env file": env_file,
            "model": "%s · %s" % (session.runtime.protocol, session.runtime.model),
            "model profile": model_profile or "custom override",
            "endpoint": _model_endpoint(session) or "not exposed",
            "configured profiles": str(len([profile for profile in profile_list if getattr(profile, "configured", False)])),
            "enabled tools": str(len(list(tools))),
            "workspace": str(workspace_path) if workspace_path is not None else "not bound",
            "workspace writable": _yes_no(_path_writable(workspace_path)) if workspace_path is not None else "n/a",
        }
        self.key_values("Doctor", rows)

    def workspace(self, session) -> None:
        workspace = getattr(session, "workspace", None)
        if workspace is None:
            self.notice("No workspace is bound to this session.")
            return
        self.key_values(
            "Workspace",
            {
                "path": str(workspace.path),
                "tenant": workspace.tenant_id,
                "user": workspace.user_id,
                "agent": workspace.agent_id,
                "workspace": workspace.workspace_id,
            },
        )

    def tools(self, tools: Iterable[str]) -> None:
        table = Table.grid(padding=(0, 1))
        table.add_column(style="magenta")
        self.console.print(Text("enabled tools", style="bold"))
        for tool in tools:
            table.add_row(str(tool))
        self.console.print(table)

    def context(self, session) -> None:
        self.key_values(
            "Context",
            {
                "tokens": _estimate_session_tokens(session),
                "limit": str(getattr(session, "max_context_tokens", "")),
                "messages": str(len(getattr(session, "messages", []))),
                "trace items": str(len(getattr(session, "context_trace", []))),
            },
        )

    def trace(self, session) -> None:
        trace = list(getattr(session, "context_trace", []) or [])
        if not trace:
            self.notice("No context trace is available.")
            return
        table = Table.grid(padding=(0, 2))
        table.add_column(style="cyan")
        table.add_column(style="dim")
        table.add_column()
        self.console.print(Text("context trace", style="bold"))
        for item in trace[:20]:
            included = "included" if getattr(item, "included", False) else "skipped"
            reason = getattr(item, "reason", "")
            status = included if not reason else "%s: %s" % (included, reason)
            table.add_row(str(getattr(item, "id", "")), str(getattr(item, "tokens", "")), status)
        if len(trace) > 20:
            table.add_row("...", "", "%s more" % (len(trace) - 20))
        self.console.print(table)

    def key_values(self, title: str, rows: dict[str, str]) -> None:
        table = Table.grid(padding=(0, 2))
        table.add_column(style="cyan")
        table.add_column()
        self.console.print(Text(title.lower(), style="bold"))
        for key, value in rows.items():
            table.add_row(key, str(value))
        self.console.print(table)

    def user_prompt_label(self) -> str:
        return "›"

    def user_prompt_suffix(self) -> str:
        return " "

    def assistant_prefix(self) -> None:
        return

    def assistant_delta(self, text: str, state: TurnActivity) -> None:
        value = str(text)
        while value:
            if not state.assistant_line_open:
                self.console.file.write("  ")
                state.assistant_line_open = True
            newline_index = value.find("\n")
            if newline_index < 0:
                self.console.file.write(value)
                break
            self.console.file.write(value[: newline_index + 1])
            state.assistant_line_open = False
            value = value[newline_index + 1 :]
        self.console.file.flush()

    def newline(self) -> None:
        self.console.print()

    def turn_started(self, session, state: TurnActivity | None = None) -> TurnActivity:
        state = state or TurnActivity()
        state.start_thinking()
        self.status_line("thinking", "%s · %s" % (session.runtime.protocol, session.runtime.model), "cyan")
        return state

    def retry(self, event: UIEvent) -> None:
        next_attempt = str(event.payload.get("next_attempt") or "?")
        max_attempts = str(event.payload.get("max_attempts") or "?")
        delay = float(event.payload.get("delay_seconds") or 0)
        error = _compact(str(event.payload.get("error") or "model request failed"))
        self.status_line("retry", "model request %s/%s in %.1fs  %s" % (next_attempt, max_attempts, delay, error), "yellow")

    def turn_finished(self, *, status: str, state: TurnActivity) -> None:
        state.status = status
        self.finish_assistant_stream(state)
        self.flush_thinking(state)
        self.flush_tool_summary(state)
        if status == "finished" and state.tool_count and not state.assistant_after_tool:
            self.status_line("note", "no final answer after tool use", "yellow")
        elapsed = state.elapsed_seconds()
        suffix = " · %s" % plural(state.tool_count, "tool", "tools") if state.tool_count else ""
        style = "dim" if status in {"finished", "awaiting_approval"} else "red"
        label = "done" if status == "finished" else status.replace("_", " ")
        self.status_line(label, "%.1fs%s" % (elapsed, suffix), style)

    def runtime_event(self, event: RuntimeEvent, state: TurnActivity) -> None:
        ui_event = self.event_adapter.adapt(event)
        if ui_event is not None:
            self.ui_event(ui_event, state)

    def ui_event(self, event: UIEvent, state: TurnActivity) -> None:
        if event.type == "assistant_delta":
            if not state.wrote_text:
                self.flush_thinking(state)
                self.flush_tool_summary(state)
                self.assistant_prefix()
                state.wrote_text = True
            state.record_assistant_text()
            state.streamed_text = True
            self.assistant_delta(event.text, state)
            return
        if event.type == "thinking_delta":
            state.add_reasoning(event.text)
            return
        self.finish_assistant_stream(state)
        if event.type == "assistant_message" and event.text:
            self.flush_thinking(state)
            self.flush_tool_summary(state)
            self.assistant(event.text)
            state.record_assistant_text()
            state.printed_assistant = True
        elif event.type == "model_retry":
            self.retry(event)
        elif event.type == "tool_started":
            self.flush_thinking(state)
            self.tool_start(event, state)
        elif event.type == "tool_finished":
            self.tool_result(event, state)
        elif event.type == "approval_required":
            self.flush_thinking(state)
            self.flush_tool_summary(state)
            self.approval_request(event)
        elif event.type == "approval_decision":
            self.approval_decision(event.name, event.status)
        elif event.type == "error":
            self.flush_tool_summary(state)
            self.error(event.text)
        elif (
            event.type == "done"
            and event.status not in {"awaiting_approval", "error"}
            and event.text
            and not state.streamed_text
            and not state.printed_assistant
        ):
            self.flush_tool_summary(state)
            self.assistant(event.text)
            state.record_assistant_text()
            state.printed_assistant = True

    def assistant(self, content: str) -> None:
        lines = str(content).splitlines() or [""]
        for line in lines:
            self.console.print(Text.assemble(("  ", "dim"), line))

    def tool_start(self, event: UIEvent, state: TurnActivity) -> None:
        arguments = event.payload.get("arguments") or {}
        activity = ToolActivity(
            id=str(event.payload.get("id") or event.name),
            name=event.name,
            arguments=dict(arguments) if isinstance(arguments, dict) else {},
            risk=str(event.payload.get("risk") or "unknown"),
        )
        state.record_tool_start(activity)
        detail = activity.name
        args = _tool_arguments(activity.arguments)
        if args:
            detail = "%s  %s" % (detail, args)
        self.status_line("tool", detail, "magenta")

    def tool_result(self, event: UIEvent, state: TurnActivity) -> None:
        is_error = bool(event.payload.get("is_error"))
        summary = state.record_tool_result(
            event.name,
            event.text,
            tool_id=str(event.payload.get("id") or ""),
            is_error=is_error,
        )
        style = "red" if is_error else "dim"
        self.result_line(summary, style)

    def flush_tool_summary(self, state: TurnActivity) -> None:
        if state.showed_tool_details:
            state.tool_stats = {}
            return
        summary = state.consume_tool_summary()
        if summary:
            self.status_line("tools", summary, "dim")

    def flush_thinking(self, state: TurnActivity) -> None:
        if not state.thinking_active:
            return
        state.thinking_active = False
        if state.reasoning_chars:
            self.status_line("reasoning", "%s chars" % state.reasoning_chars, "dim")

    def approval_request(self, event: UIEvent) -> None:
        self.status_line("approval", "%s · risk %s" % (event.name, str(event.payload.get("risk", "unknown"))), "yellow")
        args = _compact(event.payload.get("arguments") or {})
        if args:
            self.result_line(args, "dim")

    def approval_decision(self, name: str, scope: str) -> None:
        self.status_line("approved", "%s %s" % (name, scope), "yellow")

    def notice(self, message: str) -> None:
        self.status_line("notice", message, "dim")

    def error(self, message: str) -> None:
        self.status_line("error", message, "red")

    def status_line(self, label: str, message: str, style: str = "dim", *, end: str = "\n") -> None:
        label_style = "bold %s" % style if style not in {"dim", "red"} else style
        text = Text("  ")
        text.append(label, style=label_style)
        if message:
            text.append(" ", style="dim")
            text.append(message, style=style)
        self.console.print(text, end=end)

    def result_line(self, message: str, style: str = "dim") -> None:
        self.console.print(Text.assemble(("    ↳ ", "dim"), (message, style)))

    def finish_assistant_stream(self, state: TurnActivity) -> None:
        if not state.wrote_text:
            return
        if state.assistant_line_open:
            self.newline()
        state.wrote_text = False
        state.assistant_line_open = False

def _estimate_session_tokens(session) -> str:
    try:
        return str(session._estimate_tokens(getattr(session, "messages", [])))
    except Exception:
        return "unknown"


def _compact(value) -> str:
    text = str(value)
    return text if len(text) <= 220 else text[:217] + "..."


def _tool_arguments(arguments: Any | None) -> str:
    if not arguments:
        return ""
    try:
        text = json.dumps(arguments, ensure_ascii=False)
    except TypeError:
        text = str(arguments)
    return _compact(text)


def _short_path(path: str) -> str:
    try:
        value = Path(path).expanduser()
        home = Path.home()
        return "~/%s" % value.relative_to(home) if value.is_relative_to(home) else str(value)
    except Exception:
        return str(path)


def _model_base_url(session) -> str:
    runtime = getattr(session, "runtime", None)
    model_client = getattr(runtime, "model_client", None)
    config = getattr(model_client, "config", None)
    return str(getattr(config, "base_url", "") or "")


def _model_endpoint(session) -> str:
    base_url = _model_base_url(session)
    if not base_url:
        return ""
    parsed = urlparse(base_url)
    return parsed.netloc or base_url


def _short_endpoint(endpoint: str, limit: int = 36) -> str:
    value = str(endpoint or "")
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _path_writable(path: Path | None) -> bool:
    if path is None:
        return False
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".agents-cli-write-check"
        probe.write_text("", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _model_label(profile: str, protocol: str, model: str) -> str:
    base = "%s · %s" % (protocol, model)
    if not profile or profile in {protocol, model}:
        return base
    return "%s · %s" % (profile, base)
