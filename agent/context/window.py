from __future__ import annotations

from typing import List

from agent.context.compaction import ContextCompactor, HeuristicContextCompactor
from agent.schema import Message


class ContextWindowManager:
    """Maintains a bounded message window while preserving complete turns."""

    def __init__(
        self,
        system_prompt: str = "",
        max_context_tokens: int = 256000,
        compaction_target_tokens: int | None = None,
        compactor: ContextCompactor | None = None,
    ):
        self.system_prompt = system_prompt.strip()
        self.max_context_tokens = max_context_tokens
        self.compaction_target_tokens = compaction_target_tokens or max(1, max_context_tokens // 2)
        self.compactor = compactor or HeuristicContextCompactor()

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
        if self.estimate_tokens(messages) <= self.max_context_tokens:
            return messages

        compacted = self._compact_messages(messages)
        if compacted and self.estimate_tokens(compacted) <= self.max_context_tokens:
            return compacted

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

    def _compact_messages(self, messages: List[Message]) -> List[Message]:
        system_messages: List[Message] = []
        rest = list(messages)
        if rest and rest[0].role == "system":
            system_messages = [rest.pop(0)]
        compaction = self.compactor.compact(rest, self.max_context_tokens, self.compaction_target_tokens)
        if not compaction.summary:
            return []
        return system_messages + [Message.from_text("system", compaction.summary)] + compaction.kept_messages


def _flatten(turns: List[List[Message]]) -> List[Message]:
    return [message for turn in turns for message in turn]
