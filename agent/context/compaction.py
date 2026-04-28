from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol

from agent.context.pack import ContextFragment, ContextLayer, ContextScope
from agent.schema import Message


@dataclass(frozen=True)
class ConversationCompaction:
    summary: str
    kept_messages: List[Message]
    dropped_messages: int
    source_token_estimate: int

    def as_fragment(self, fragment_id: str = "conversation.summary") -> ContextFragment:
        return ContextFragment(
            id=fragment_id,
            layer=ContextLayer.MEMORY,
            text=self.summary,
            source="context.compaction",
            priority=90,
            scope=ContextScope.SESSION,
            metadata={
                "dropped_messages": str(self.dropped_messages),
                "source_token_estimate": str(self.source_token_estimate),
            },
        )


class ContextCompactor(Protocol):
    def compact(self, messages: List[Message], max_context_tokens: int, target_tokens: int) -> ConversationCompaction:
        raise NotImplementedError()


class HeuristicContextCompactor:
    """Deterministic compactor used until model-based summarization is wired."""

    def compact(self, messages: List[Message], max_context_tokens: int, target_tokens: int) -> ConversationCompaction:
        total_tokens = sum(message.approx_token_count() for message in messages)
        if total_tokens <= max_context_tokens:
            return ConversationCompaction("", list(messages), 0, total_tokens)

        kept: List[Message] = []
        kept_tokens = 0
        for message in reversed(messages):
            message_tokens = message.approx_token_count()
            if kept and kept_tokens + message_tokens > target_tokens:
                break
            kept.append(message)
            kept_tokens += message_tokens
        kept.reverse()
        dropped = messages[: len(messages) - len(kept)]
        summary = _summarize_messages(dropped)
        return ConversationCompaction(
            summary=summary,
            kept_messages=kept,
            dropped_messages=len(dropped),
            source_token_estimate=total_tokens,
        )


def _summarize_messages(messages: List[Message]) -> str:
    if not messages:
        return ""
    lines = ["Prior conversation summary:"]
    for message in messages:
        text = " ".join(message.content_text().split())
        if not text and message.tool_calls:
            text = "tool calls: %s" % ", ".join(call.name for call in message.tool_calls)
        if not text:
            continue
        lines.append("- %s: %s" % (message.role, text[:500]))
    return "\n".join(lines)
