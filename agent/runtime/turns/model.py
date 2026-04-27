from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterable, Optional

from agent.context.compiler import ModelRequestCompiler
from agent.hooks import AgentHooks
from agent.models.protocol import ModelStreamEventType
from agent.runtime.config import RuntimeConfig
from agent.runtime.errors import AgentRuntimeError
from agent.runtime.types import ModelClientProtocol
from agent.schema import Message, ModelResponse, RuntimeEvent


@dataclass(frozen=True)
class ModelTurnUpdate:
    event: Optional[RuntimeEvent] = None
    response: Optional[ModelResponse] = None


class ModelTurnRunner:
    """Runs one model turn behind a stable runtime-facing interface."""

    def __init__(
        self,
        model_client: ModelClientProtocol,
        request_compiler: ModelRequestCompiler,
        hooks: AgentHooks,
    ):
        self.model_client = model_client
        self.request_compiler = request_compiler
        self.hooks = hooks

    async def complete(self, messages: list[Message], config: RuntimeConfig) -> ModelResponse:
        working = await self.hooks.before_request(messages)
        request = self.request_compiler.compile(working, config)
        response = await self.model_client.async_complete(request)
        return await self.hooks.after_response(response)

    async def stream(
        self,
        messages: list[Message],
        config: RuntimeConfig,
    ) -> AsyncIterable[ModelTurnUpdate]:
        working = await self.hooks.before_request(messages)
        request = self.request_compiler.compile(working, config)
        final_response: Optional[ModelResponse] = None

        async for event in self.model_client.async_stream(request):
            if event.type == ModelStreamEventType.TEXT_DELTA.value:
                yield ModelTurnUpdate(
                    event=RuntimeEvent(type="text_delta", name="assistant", payload={"delta": event.delta})
                )
            elif event.type == ModelStreamEventType.REASONING_DELTA.value:
                yield ModelTurnUpdate(
                    event=RuntimeEvent(type="reasoning_delta", name="assistant", payload={"delta": event.delta})
                )
            elif event.type == ModelStreamEventType.MESSAGE.value and event.response is not None:
                final_response = event.response

        if final_response is None:
            raise AgentRuntimeError("model stream did not include final message")
        yield ModelTurnUpdate(response=await self.hooks.after_response(final_response))
