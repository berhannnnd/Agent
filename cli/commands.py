from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SlashCommand:
    name: str
    action: str
    aliases: tuple[str, ...] = ()


COMMANDS = [
    SlashCommand("/help", "show terminal commands"),
    SlashCommand("/status", "show protocol, workspace, permission, and token estimate"),
    SlashCommand("/model", "show or switch .env/config model profiles", aliases=("/models",)),
    SlashCommand("/doctor", "check local model, workspace, and tool readiness"),
    SlashCommand("/workspace", "show workspace path and scope"),
    SlashCommand("/tools", "show enabled tools"),
    SlashCommand("/context", "show context window usage"),
    SlashCommand("/trace", "show context assembly trace"),
    SlashCommand("/clear", "reset conversation messages"),
    SlashCommand("/exit", "leave the chat", aliases=("/quit",)),
]


def command_names() -> list[str]:
    return [command.name for command in COMMANDS]


def command_lookup() -> dict[str, SlashCommand]:
    lookup: dict[str, SlashCommand] = {}
    for command in COMMANDS:
        lookup[command.name] = command
        for alias in command.aliases:
            lookup[alias] = command
    return lookup
