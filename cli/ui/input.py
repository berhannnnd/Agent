from __future__ import annotations

import sys
from typing import Iterable

import typer

from agent.config import ModelProfile
from cli.commands import SlashCommand


class ChatInput:
    def __init__(self, commands: Iterable[SlashCommand], model_profiles: Iterable[ModelProfile] = ()):
        self._commands = list(commands)
        self._model_profiles = list(model_profiles)
        self._session = None

    def update_model_profiles(self, profiles: Iterable[ModelProfile]) -> None:
        self._model_profiles = list(profiles)
        if self._session is not None:
            self._session.completer = SlashCommandCompleter(self._commands, self._model_profiles)

    def read(self, prompt_label: str, prompt_suffix: str) -> str:
        if not sys.stdin.isatty():
            return typer.prompt(prompt_label, prompt_suffix=prompt_suffix)
        from prompt_toolkit.formatted_text import FormattedText

        return self._prompt_session().prompt(FormattedText([("ansicyan", prompt_label), ("", prompt_suffix)]))

    def _prompt_session(self):
        if self._session is None:
            try:
                from prompt_toolkit import PromptSession
                from prompt_toolkit.key_binding import KeyBindings
                from prompt_toolkit.shortcuts import CompleteStyle
            except ModuleNotFoundError as exc:  # pragma: no cover - setup should install prompt-toolkit.
                raise RuntimeError("prompt-toolkit is required for interactive CLI input; run make setup") from exc

            bindings = KeyBindings()

            @bindings.add("/")
            def _(event):
                event.current_buffer.insert_text("/")
                event.current_buffer.start_completion(select_first=False)

            @bindings.add("c-space")
            def _(event):
                event.current_buffer.start_completion(select_first=False)

            self._session = PromptSession(
                completer=SlashCommandCompleter(self._commands, self._model_profiles),
                complete_while_typing=True,
                complete_style=CompleteStyle.MULTI_COLUMN,
                key_bindings=bindings,
                refresh_interval=0.05,
                reserve_space_for_menu=8,
            )
        return self._session


class SlashCommandCompleter:
    def __init__(self, commands: Iterable[SlashCommand], model_profiles: Iterable[ModelProfile] = ()):
        self._commands = list(commands)
        self._model_profiles = list(model_profiles)

    def get_completions(self, document, complete_event):
        from prompt_toolkit.completion import Completion

        text = document.text_before_cursor
        if text.startswith("/model "):
            value = text[len("/model ") :]
            if " " in value:
                return
            candidates = [
                (profile.name, profile.protocol, profile.model or "not configured")
                for profile in self._model_profiles
                if profile.name.startswith(value) or profile.protocol.startswith(value) or profile.matches(value)
            ]
            for name, protocol, model in candidates:
                yield Completion(
                    name,
                    start_position=-len(value),
                    display=name,
                    display_meta="%s · %s" % (protocol, model),
                )
            if not candidates:
                for command in ("list",):
                    if command.startswith(value):
                        yield Completion(
                            command,
                            start_position=-len(value),
                            display=command,
                            display_meta="show configured model profiles",
                        )
                return
            return
        if not text.startswith("/") or " " in text:
            return
        for command in self._commands:
            names = (command.name, *command.aliases)
            for name in names:
                if name.startswith(text):
                    yield Completion(
                        name,
                        start_position=-len(text),
                        display=name,
                        display_meta=command.action,
                    )

    async def get_completions_async(self, document, complete_event):
        for completion in self.get_completions(document, complete_event):
            yield completion
