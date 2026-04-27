from __future__ import annotations

from typing import AsyncIterable, List, Optional

from agent.context.window import ContextWindowManager
from agent.context.workspace import WorkspaceContext
from agent.runtime.loop import AgentRuntime
from agent.runtime.types import AgentResult
from agent.schema import Message, RuntimeEvent
from agent.context import ContextTraceItem


class AgentSession:
    def __init__(
        self,
        runtime: AgentRuntime,
        system_prompt: str = "",
        max_context_tokens: int = 256000,
        context_trace: Optional[List[ContextTraceItem]] = None,
        workspace: Optional[WorkspaceContext] = None,
    ):
        self.runtime = runtime
        self.context_trace = list(context_trace or [])
        self.workspace = workspace
        self.context_window = ContextWindowManager(system_prompt, max_context_tokens)
        self.messages: List[Message] = []
        self.clear()

    @property
    def system_prompt(self) -> str:
        return self.context_window.system_prompt

    @property
    def max_context_tokens(self) -> int:
        return self.context_window.max_context_tokens

    def clear(self) -> None:
        self.messages = self.context_window.initial_messages()

    def _estimate_tokens(self, messages: List[Message]) -> int:
        return self.context_window.estimate_tokens(messages)

    def _truncate_messages(self, messages: List[Message]) -> List[Message]:
        return self.context_window.fit(messages)

    async def send(self, text: str) -> AgentResult:
        candidate = self.messages + [Message.from_text("user", text)]
        candidate = self.context_window.fit(candidate)
        result = await self.runtime.run(candidate)
        self.messages = list(result.messages)
        return result

    async def stream(self, text: str) -> AsyncIterable[RuntimeEvent]:
        candidate = self.messages + [Message.from_text("user", text)]
        candidate = self.context_window.fit(candidate)
        async for event in self.runtime.stream(candidate):
            yield event
            if event.type == "done" and event.payload.get("messages"):
                self.messages = [Message.from_dict(message) for message in event.payload["messages"]]
