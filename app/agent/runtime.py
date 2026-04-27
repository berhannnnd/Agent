# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：runtime.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterable, List, Optional, Protocol

from app.agent.hooks import AgentHooks
from app.agent.providers.errors import ModelClientError
from app.agent.schema import Message, ModelRequest, ModelResponse, ModelStreamEvent, RuntimeEvent, ToolResult
from app.agent.tools.registry import ToolRegistry


class AgentRuntimeError(RuntimeError):
    """Raised when the agent loop cannot complete safely."""


class ModelClientProtocol(Protocol):
    async def async_complete(self, request_data: ModelRequest) -> ModelResponse:
        raise NotImplementedError()

    async def async_stream(self, request_data: ModelRequest) -> AsyncIterable[ModelStreamEvent]:
        raise NotImplementedError()


@dataclass
class AgentResult:
    content: str
    messages: List[Message]
    tool_results: List[ToolResult] = field(default_factory=list)
    events: List[RuntimeEvent] = field(default_factory=list)


class ScriptedModelClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests: List[ModelRequest] = []

    async def async_complete(self, request_data: ModelRequest) -> ModelResponse:
        self.requests.append(request_data)
        if not self.responses:
            raise RuntimeError("no scripted model responses left")
        response = self.responses.pop(0)
        if isinstance(response, list):
            for event in response:
                if event.type == "message" and event.response is not None:
                    return event.response
            raise RuntimeError("scripted stream did not include final message")
        return response

    async def async_stream(self, request_data: ModelRequest) -> AsyncIterable[ModelStreamEvent]:
        self.requests.append(request_data)
        if not self.responses:
            raise RuntimeError("no scripted model responses left")
        response = self.responses.pop(0)
        if isinstance(response, list):
            for event in response:
                yield event
            return
        yield ModelStreamEvent(type="message", response=response)


class AgentRuntime:
    def __init__(
        self,
        model_client: ModelClientProtocol,
        tools: ToolRegistry,
        provider: str,
        model: str,
        enabled_tools: List[str] = None,
        max_tool_iterations: int = 8,
        hooks: Optional[AgentHooks] = None,
    ):
        self.model_client = model_client
        self.tools = tools
        self.provider = provider
        self.model = model
        self.enabled_tools = list(enabled_tools or [])
        self.max_tool_iterations = max_tool_iterations
        self.hooks = hooks or AgentHooks()

    async def run(self, messages: List[Message]) -> AgentResult:
        working = list(messages)
        tool_results: List[ToolResult] = []
        events: List[RuntimeEvent] = []
        try:
            for _ in range(self.max_tool_iterations):
                working = await self.hooks.before_request(working)
                response = await self.model_client.async_complete(self._request(working))
                response = await self.hooks.after_response(response)
                working.append(response.message)
                calls = response.tool_calls
                events.append(
                    RuntimeEvent(
                        type="model_message",
                        name="assistant",
                        payload={"content": response.content_text(), "tool_call_count": len(calls)},
                    )
                )
                if not calls:
                    return AgentResult(response.content_text(), working, tool_results, events)
                results = await self.tools.execute_many(calls)
                tool_results.extend(results)
                for result in results:
                    events.append(
                        RuntimeEvent(
                            type="tool_result",
                            name=result.name,
                            payload=result.to_dict(),
                        )
                    )
                    working.append(self.hooks.format_tool_result(result))
        except ModelClientError as exc:
            recovery = await self.hooks.on_error(exc, working)
            if recovery is not None:
                return recovery
            error_msg = "model error: %s" % exc
            events.append(RuntimeEvent(type="error", name="model", payload={"message": error_msg}))
            return AgentResult(error_msg, working, tool_results, events)
        except AgentRuntimeError as exc:
            recovery = await self.hooks.on_error(exc, working)
            if recovery is not None:
                return recovery
            error_msg = str(exc)
            events.append(RuntimeEvent(type="error", name="runtime", payload={"message": error_msg}))
            return AgentResult(error_msg, working, tool_results, events)
        except Exception as exc:
            recovery = await self.hooks.on_error(exc, working)
            if recovery is not None:
                return recovery
            error_msg = "unexpected error: %s" % exc
            events.append(RuntimeEvent(type="error", name="runtime", payload={"message": error_msg}))
            return AgentResult(error_msg, working, tool_results, events)
        error_msg = "tool-call loop exceeded max iterations"
        events.append(RuntimeEvent(type="error", name="runtime", payload={"message": error_msg}))
        return AgentResult(error_msg, working, tool_results, events)

    async def stream(self, messages: List[Message]) -> AsyncIterable[RuntimeEvent]:
        working = list(messages)
        error_msg = None
        try:
            for _ in range(self.max_tool_iterations):
                working = await self.hooks.before_request(working)
                final_response = None
                async for event in self.model_client.async_stream(self._request(working)):
                    if event.type == "text_delta":
                        yield RuntimeEvent(type="text_delta", name="assistant", payload={"delta": event.delta})
                    elif event.type == "message" and event.response is not None:
                        final_response = event.response
                if final_response is None:
                    raise AgentRuntimeError("model stream did not include final message")
                final_response = await self.hooks.after_response(final_response)
                working.append(final_response.message)
                calls = final_response.tool_calls
                if not calls:
                    return
                for call in calls:
                    yield RuntimeEvent(type="tool_start", name=call.name, payload=call.to_dict())
                results = await self.tools.execute_many(calls)
                for result in results:
                    yield RuntimeEvent(type="tool_result", name=result.name, payload=result.to_dict())
                    working.append(self.hooks.format_tool_result(result))
        except ModelClientError as exc:
            error_msg = "model error: %s" % exc
            yield RuntimeEvent(type="error", name="model", payload={"message": error_msg})
        except AgentRuntimeError as exc:
            error_msg = str(exc)
            yield RuntimeEvent(type="error", name="runtime", payload={"message": error_msg})
        except Exception as exc:
            error_msg = "unexpected error: %s" % exc
            yield RuntimeEvent(type="error", name="runtime", payload={"message": error_msg})
        finally:
            yield RuntimeEvent(
                type="done",
                name="assistant",
                payload={
                    "content": working[-1].content_text() if working else "",
                    "messages": [message.to_dict() for message in working],
                    "error": error_msg,
                },
            )

    def _request(self, messages: List[Message]) -> ModelRequest:
        tool_names = self.enabled_tools or None
        return ModelRequest(
            provider=self.provider,
            model=self.model,
            messages=list(messages),
            tools=self.tools.specs(tool_names),
        )


class AgentSession:
    def __init__(self, runtime: AgentRuntime, system_prompt: str = "", max_context_tokens: int = 256000):
        self.runtime = runtime
        self.system_prompt = system_prompt.strip()
        self.max_context_tokens = max_context_tokens
        self.messages: List[Message] = []
        self.clear()

    def clear(self) -> None:
        self.messages = []
        if self.system_prompt:
            self.messages.append(Message.from_text("system", self.system_prompt))

    def _estimate_tokens(self, messages: List[Message]) -> int:
        return sum(message.approx_token_count() for message in messages)

    def _truncate_messages(self, messages: List[Message]) -> List[Message]:
        """从头部截断消息（保留 system prompt），以完整轮次为单位。

        丢弃 system 之后、第一个 user 之前的不完整消息，然后按轮次（user → ... → user）移除。
        """
        if not messages:
            return messages

        # 分离 system prompt
        system_messages: List[Message] = []
        rest = list(messages)
        if rest and rest[0].role == "system":
            system_messages = [rest.pop(0)]

        # 丢弃开头不完整的消息（在第一个 user 之前的 assistant/tool）
        while rest and rest[0].role != "user":
            rest.pop(0)

        # 按轮次分组（每个轮次以 user 开头）
        turns: List[List[Message]] = []
        i = 0
        while i < len(rest):
            turn_start = i
            i += 1
            while i < len(rest) and rest[i].role != "user":
                i += 1
            turns.append(rest[turn_start:i])

        # 从最早的轮次开始移除，直到 token 数达标
        system_tokens = self._estimate_tokens(system_messages)
        while turns and system_tokens + self._estimate_tokens([msg for turn in turns for msg in turn]) > self.max_context_tokens:
            turns.pop(0)

        return system_messages + [msg for turn in turns for msg in turn]

    async def send(self, text: str) -> AgentResult:
        candidate = self.messages + [Message.from_text("user", text)]
        candidate = self._truncate_messages(candidate)
        result = await self.runtime.run(candidate)
        self.messages = list(result.messages)
        return result

    async def stream(self, text: str) -> AsyncIterable[RuntimeEvent]:
        candidate = self.messages + [Message.from_text("user", text)]
        candidate = self._truncate_messages(candidate)
        async for event in self.runtime.stream(candidate):
            yield event
            if event.type == "done" and event.payload.get("messages"):
                self.messages = [Message.from_dict(message) for message in event.payload["messages"]]
