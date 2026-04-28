from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Glyphs:
    prompt: str = "❯"
    active: str = "●"
    pending: str = "●"
    response: str = "⎿"
    thinking: str = "∴"
    separator: str = "·"
    ellipsis: str = "…"


@dataclass(frozen=True)
class TerminalTheme:
    primary: str = "cyan"
    accent: str = "magenta"
    success: str = "green"
    warning: str = "yellow"
    error: str = "red"
    muted: str = "dim"
    text: str = ""
    glyphs: Glyphs = Glyphs()


DEFAULT_THEME = TerminalTheme()
