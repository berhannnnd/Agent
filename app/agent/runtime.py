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
from typing import AsyncIterable, List, Protocol

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
    ):
        self.model_client = model_client
        self.tools = tools
        self.provider = provider
        self.model = model
        self.enabled_tools = list(enabled_tools or [])
        self.max_tool_iterations = max_tool_iterations

    async def run(self, messages: List[Message]) -> AgentResult:
        working = list(messages)
        tool_results: List[ToolResult] = []
        events: List[RuntimeEvent] = []
        for _ in range(self.max_tool_iterations):
            response = await self.model_client.async_complete(self._request(working))
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
                working.append(
                    Message.from_text(
                        "tool",
                        result.content,
                        tool_call_id=result.tool_call_id,
                        name=result.name,
                        raw=result.to_dict(),
                    )
                )
        raise AgentRuntimeError("tool-call loop exceeded max iterations")

    async def stream(self, messages: List[Message]) -> AsyncIterable[RuntimeEvent]:
        working = list(messages)
        for _ in range(self.max_tool_iterations):
            final_response = None
            async for event in self.model_client.async_stream(self._request(working)):
                if event.type == "text_delta":
                    yield RuntimeEvent(type="text_delta", name="assistant", payload={"delta": event.delta})
                elif event.type == "message" and event.response is not None:
                    final_response = event.response
            if final_response is None:
                raise AgentRuntimeError("model stream did not include final message")
            working.append(final_response.message)
            calls = final_response.tool_calls
            if not calls:
                yield RuntimeEvent(
                    type="done",
                    name="assistant",
                    payload={
                        "content": final_response.content_text(),
                        "messages": [message.to_dict() for message in working],
                    },
                )
                return
            for call in calls:
                yield RuntimeEvent(type="tool_start", name=call.name, payload=call.to_dict())
            results = await self.tools.execute_many(calls)
            for result in results:
                yield RuntimeEvent(type="tool_result", name=result.name, payload=result.to_dict())
                working.append(
                    Message.from_text(
                        "tool",
                        result.content,
                        tool_call_id=result.tool_call_id,
                        name=result.name,
                        raw=result.to_dict(),
                    )
                )
        raise AgentRuntimeError("tool-call loop exceeded max iterations")

    def _request(self, messages: List[Message]) -> ModelRequest:
        tool_names = self.enabled_tools or None
        return ModelRequest(
            provider=self.provider,
            model=self.model,
            messages=list(messages),
            tools=self.tools.specs(tool_names),
        )


class AgentSession:
    def __init__(self, runtime: AgentRuntime, system_prompt: str = "", max_context_tokens: int = 8000):
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
        """从头部截断消息（保留 system prompt），直到总 token 低于阈值。

        截断以完整轮次为单位，避免留下孤立的 tool call/tool result。
        """
        if not messages:
            return messages

        # 保留 system prompt（如果在开头）
        system_messages = []
        rest_start = 0
        if messages and messages[0].role == "system":
            system_messages = [messages[0]]
            rest_start = 1

        rest = list(messages[rest_start:])
        system_tokens = self._estimate_tokens(system_messages)

        # 如果 system 本身就超了，那也没办法，只能保留
        while rest and system_tokens + self._estimate_tokens(rest) > self.max_context_tokens:
            # 找到最早的一个完整轮次并移除
            # 一轮通常从 user 开始，到下一个 user 之前结束
            # 简单策略：移除从开头到下一个 user 之前的所有消息
            if not rest:
                break

            # 找到第一个 user 消息的位置（轮次起点）
            first_user_idx = None
            for i, msg in enumerate(rest):
                if msg.role == "user":
                    first_user_idx = i
                    break

            if first_user_idx is None:
                # 没有 user 消息，直接移除最早的一条
                rest.pop(0)
                continue

            # 找到下一个 user 消息的位置（下一轮起点）
            next_user_idx = None
            for i in range(first_user_idx + 1, len(rest)):
                if rest[i].role == "user":
                    next_user_idx = i
                    break

            # 移除从开头到 next_user_idx 之前的所有消息（即第一个完整轮次）
            if next_user_idx is not None:
                rest = rest[next_user_idx:]
            else:
                # 只剩最后一轮，不能全删，至少保留最后一条
                if len(rest) > 1:
                    rest.pop(0)
                else:
                    break

        return system_messages + rest

    async def send(self, text: str) -> AgentResult:
        candidate = self.messages + [Message.from_text("user", text)]
        candidate = self._truncate_messages(candidate)
        result = await self.runtime.run(candidate)
        self.messages = list(result.messages)
        return result

    async def stream(self, text: str) -> AsyncIterable[RuntimeEvent]:
        candidate = self.messages + [Message.from_text("user", text)]
        candidate = self._truncate_messages(candidate)
        committed_messages = None
        async for event in self.runtime.stream(candidate):
            if event.type == "done" and event.payload.get("messages"):
                committed_messages = [Message.from_dict(message) for message in event.payload["messages"]]
            yield event
        if committed_messages is not None:
            self.messages = committed_messages
