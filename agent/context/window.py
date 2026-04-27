from __future__ import annotations

from typing import List

from agent.schema import Message


class ContextWindowManager:
    """Maintains a bounded message window while preserving complete turns."""

    def __init__(self, system_prompt: str = "", max_context_tokens: int = 256000):
        self.system_prompt = system_prompt.strip()
        self.max_context_tokens = max_context_tokens

    def initial_messages(self) -> List[Message]:
        if not self.system_prompt:
            return []
        return [Message.from_text("system", self.system_prompt)]

    def estimate_tokens(self, messages: List[Message]) -> int:
        return sum(message.approx_token_count() for message in messages)

    def fit(self, messages: List[Message]) -> List[Message]:
        """Trim oldest complete user turns until the request fits the budget."""
        if not messages:
            return messages

        system_messages: List[Message] = []
        rest = list(messages)
        if rest and rest[0].role == "system":
            system_messages = [rest.pop(0)]

        while rest and rest[0].role != "user":
            rest.pop(0)

        turns: List[List[Message]] = []
        index = 0
        while index < len(rest):
            turn_start = index
            index += 1
            while index < len(rest) and rest[index].role != "user":
                index += 1
            turns.append(rest[turn_start:index])

        system_tokens = self.estimate_tokens(system_messages)
        while turns and system_tokens + self.estimate_tokens(_flatten(turns)) > self.max_context_tokens:
            turns.pop(0)

        return system_messages + _flatten(turns)


def _flatten(turns: List[List[Message]]) -> List[Message]:
    return [message for turn in turns for message in turn]
