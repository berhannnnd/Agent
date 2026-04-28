from __future__ import annotations

from typing import Any, Iterable

from rich.console import Console
from rich.table import Table
from rich.text import Text

from cli.ui.activity import ToolActivity, plural
from cli.ui.formatters import short_endpoint, tool_use_label
from cli.ui.theme import DEFAULT_THEME, TerminalTheme


class TranscriptRenderer:
    """Nexus-style terminal transcript renderer for the Python CLI."""

    def __init__(self, console: Console | None = None, theme: TerminalTheme = DEFAULT_THEME):
        self.console = console or Console(highlight=False)
        self.theme = theme

    def startup(self, *, title: str, model: str, workspace: str, meta: Iterable[str], commands: Iterable[str]) -> None:
        self.console.print(Text.assemble((title, "bold %s" % self.theme.primary), ("  ", self.theme.muted), (model, "bold")))
        self.console.print(Text.assemble(("  ", self.theme.muted), (workspace, self.theme.muted), ("  ", self.theme.muted), self.join_meta(meta)))
        self.console.print(Text.assemble(("  ", self.theme.muted), (self.join_plain(commands), self.theme.muted)))

    def join_meta(self, values: Iterable[str]) -> Text:
        text = Text()
        for index, value in enumerate([str(v) for v in values if str(v)]):
            if index:
                text.append(" %s " % self.theme.glyphs.separator, style=self.theme.muted)
            text.append(value)
        return text

    def join_plain(self, values: Iterable[str]) -> str:
        return " ".join([str(v) for v in values if str(v)])

    def title(self, value: str) -> None:
        self.console.print(Text(value.lower(), style="bold"))

    def key_values(self, title: str, rows: dict[str, str]) -> None:
        table = Table.grid(padding=(0, 2))
        table.add_column(style=self.theme.primary)
        table.add_column()
        self.title(title)
        for key, value in rows.items():
            table.add_row(key, str(value))
        self.console.print(table)

    def command_table(self, rows: Iterable[tuple[str, str]]) -> None:
        table = Table.grid(padding=(0, 2))
        table.add_column(style=self.theme.primary)
        table.add_column(style=self.theme.muted)
        self.title("commands")
        for name, description in rows:
            table.add_row(name, description)
        self.console.print(table)

    def item_list(self, title: str, items: Iterable[str], *, style: str = "magenta") -> None:
        table = Table.grid(padding=(0, 1))
        table.add_column(style=style)
        self.title(title)
        for item in items:
            table.add_row(str(item))
        self.console.print(table)

    def model_profiles(self, rows: Iterable[dict[str, Any]]) -> None:
        self.title("models")
        for row in rows:
            active = bool(row.get("active"))
            status = str(row.get("status") or "")
            status_suffix = "" if status == "ready" else "  %s" % status
            marker = self.theme.glyphs.active if active else " "
            self.console.print(
                Text.assemble(
                    ("%s " % marker, "bold %s" % self.theme.primary if active else self.theme.muted),
                    (str(row.get("name") or "").ljust(16), "bold" if active else ""),
                    (" %s · %s" % (row.get("protocol") or "", row.get("model") or "-"), self.theme.primary if active else ""),
                    ("  %s" % short_endpoint(str(row.get("endpoint") or "-"), limit=22), self.theme.muted),
                    (status_suffix, self.theme.warning if status != "ready" else self.theme.muted),
                )
            )

    def status(self, label: str, message: str = "", style: str = "dim", *, end: str = "\n") -> None:
        label_style = "bold %s" % style if style not in {"dim", "red"} else style
        text = Text("  ")
        text.append(label, style=label_style)
        if message:
            text.append(" ")
            text.append(message, style=style)
        self.console.print(text, end=end)

    def thinking(self, model: str) -> None:
        self.status(self.theme.glyphs.thinking, "Thinking  %s" % model, self.theme.primary)

    def reasoning(self, chars: int) -> None:
        if chars:
            self.response("thinking captured %s" % plural(chars, "char", "chars"))

    def retry(self, message: str) -> None:
        self.status("retry", message, self.theme.warning)

    def assistant_text(self, content: str) -> None:
        lines = str(content).splitlines() or [""]
        for line in lines:
            self.console.print(Text.assemble(("  ", self.theme.muted), line))

    def assistant_delta(self, text: str, *, line_open: bool) -> bool:
        value = str(text)
        open_line = line_open
        while value:
            if not open_line:
                self.console.file.write("  ")
                open_line = True
            newline_index = value.find("\n")
            if newline_index < 0:
                self.console.file.write(value)
                break
            self.console.file.write(value[: newline_index + 1])
            open_line = False
            value = value[newline_index + 1 :]
        self.console.file.flush()
        return open_line

    def tool_start(self, activity: ToolActivity) -> None:
        self.status(self.theme.glyphs.pending, tool_use_label(activity.name, activity.arguments), self.theme.accent)

    def tool_result(self, message: str, *, is_error: bool = False) -> None:
        self.response(message, style=self.theme.error if is_error else self.theme.muted)

    def response(self, message: str, *, style: str = "dim") -> None:
        self.console.print(Text.assemble(("  %s  " % self.theme.glyphs.response, self.theme.muted), (message, style)))

    def approval(self, tool_name: str, risk: str) -> None:
        self.status("permission", "%s · risk %s" % (tool_name, risk), self.theme.warning)

    def finish(self, status: str, elapsed_seconds: float, tool_count: int) -> None:
        suffix = " · %s" % plural(tool_count, "tool", "tools") if tool_count else ""
        label = "done" if status == "finished" else status.replace("_", " ")
        style = self.theme.muted if status in {"finished", "awaiting_approval"} else self.theme.error
        self.status(label, "in %.1fs%s" % (elapsed_seconds, suffix), style)
