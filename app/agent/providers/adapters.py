# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：adapters.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, List, Optional

from app.agent.schema import Message, ModelRequest, ModelResponse, ModelStreamEvent, ModelUsage, ToolCall, ToolSpec


class ProviderParseError(ValueError):
    """Raised when a provider response cannot be parsed."""


class ProviderAdapter:
    provider = ""
    path = ""
    stream_path = ""

    def request_payload(self, request: ModelRequest, stream: bool = False) -> Dict[str, Any]:
        raise NotImplementedError()

    def parse_response(self, response: Dict[str, Any]) -> ModelResponse:
        raise NotImplementedError()

    def parse_stream_event(self, event: Dict[str, Any]) -> List[ModelStreamEvent]:
        return []


class OpenAIChatCompletionsAdapter(ProviderAdapter):
    provider = "openai-chat"
    path = "/chat/completions"
    stream_path = "/chat/completions"

    def request_payload(self, request: ModelRequest, stream: bool = False) -> Dict[str, Any]:
        payload = {
            "model": request.model,
            "messages": [_openai_chat_message(message) for message in request.messages],
        }
        if request.tools:
            payload["tools"] = [_openai_chat_tool(tool) for tool in request.tools]
            payload["tool_choice"] = "auto"
        if stream:
            payload["stream"] = True
        return payload

    def parse_response(self, response: Dict[str, Any]) -> ModelResponse:
        choice = response["choices"][0]
        message = choice.get("message", {})
        tool_calls = []
        for raw_call in message.get("tool_calls", []) or []:
            function = raw_call.get("function", {})
            tool_calls.append(
                ToolCall(
                    id=raw_call.get("id", ""),
                    name=function.get("name", ""),
                    arguments=_parse_json_object(function.get("arguments") or "{}", "openai chat tool call"),
                    raw=raw_call,
                )
            )
        return ModelResponse(
            message=Message.from_text(
                "assistant",
                message.get("content") or "",
                tool_calls=tool_calls,
                raw=message,
            ),
            usage=_openai_usage(response.get("usage")),
            stop_reason=choice.get("finish_reason", ""),
            raw=response,
        )

    def parse_stream_event(self, event: Dict[str, Any]) -> List[ModelStreamEvent]:
        choices = event.get("choices") or []
        if not choices:
            return []
        delta = choices[0].get("delta") or {}
        events: List[ModelStreamEvent] = []
        if delta.get("content"):
            events.append(ModelStreamEvent(type="text_delta", delta=delta["content"], raw=event))
        for raw_call in delta.get("tool_calls", []) or []:
            function = raw_call.get("function", {})
            events.append(
                ModelStreamEvent(
                    type="tool_call_delta",
                    tool_call=ToolCall(
                        id=raw_call.get("id", ""),
                        name=function.get("name", ""),
                        arguments={"__delta__": function.get("arguments", "")},
                        raw=raw_call,
                    ),
                    raw=event,
                )
            )
        return events


class OpenAIResponsesAdapter(ProviderAdapter):
    provider = "openai-responses"
    path = "/responses"
    stream_path = "/responses"

    def request_payload(self, request: ModelRequest, stream: bool = False) -> Dict[str, Any]:
        system_text = "\n".join(message.content_text() for message in request.messages if message.role == "system")
        payload: Dict[str, Any] = {
            "model": request.model,
            "input": [
                item
                for message in request.messages
                if message.role != "system"
                for item in _openai_response_inputs(message)
            ],
        }
        if system_text:
            payload["instructions"] = system_text
        if request.tools:
            payload["tools"] = [_openai_response_tool(tool) for tool in request.tools]
        if stream:
            payload["stream"] = True
        return payload

    def parse_response(self, response: Dict[str, Any]) -> ModelResponse:
        text_parts: List[str] = []
        tool_calls: List[ToolCall] = []
        for item in response.get("output", []) or []:
            item_type = item.get("type", "")
            if item_type == "message":
                for content in item.get("content", []) or []:
                    if content.get("type") in ("output_text", "text"):
                        text_parts.append(content.get("text", ""))
            elif item_type == "function_call":
                tool_calls.append(
                    ToolCall(
                        id=item.get("call_id") or item.get("id", ""),
                        name=item.get("name", ""),
                        arguments=_parse_json_object(item.get("arguments") or "{}", "openai response function call"),
                        raw=item,
                    )
                )
        if not text_parts and response.get("output_text"):
            text_parts.append(response.get("output_text", ""))
        return ModelResponse(
            message=Message.from_text(
                "assistant",
                "".join(text_parts),
                tool_calls=tool_calls,
                raw={"output": deepcopy(response.get("output", []) or [])},
            ),
            usage=_openai_responses_usage(response.get("usage")),
            stop_reason=response.get("status", ""),
            raw=response,
        )

    def parse_stream_event(self, event: Dict[str, Any]) -> List[ModelStreamEvent]:
        event_type = event.get("type", "")
        if event_type.endswith("output_text.delta"):
            return [ModelStreamEvent(type="text_delta", delta=event.get("delta", ""), raw=event)]
        if event_type == "response.output_item.added":
            item = event.get("item") or {}
            if item.get("type") == "function_call":
                return [
                    ModelStreamEvent(
                        type="tool_call_delta",
                        tool_call=ToolCall(
                            id=item.get("call_id") or item.get("id", ""),
                            name=item.get("name", ""),
                            arguments={"__delta__": item.get("arguments", "")},
                            raw=event,
                        ),
                        raw=event,
                    )
                ]
        if event_type == "response.function_call_arguments.delta":
            return [
                ModelStreamEvent(
                    type="tool_call_delta",
                    tool_call=ToolCall(
                        id="",
                        name="",
                        arguments={"__delta__": event.get("delta", "")},
                        raw=event,
                    ),
                    raw=event,
                )
            ]
        if event_type.endswith("completed") and "response" in event:
            return [ModelStreamEvent(type="message", response=self.parse_response(event["response"]), raw=event)]
        return []


class ClaudeMessagesAdapter(ProviderAdapter):
    provider = "claude-messages"
    path = "/messages"
    stream_path = "/messages"

    def request_payload(self, request: ModelRequest, stream: bool = False) -> Dict[str, Any]:
        system_text = "\n".join(message.content_text() for message in request.messages if message.role == "system")
        payload: Dict[str, Any] = {
            "model": request.model,
            "max_tokens": int(request.metadata.get("max_tokens", 4096)),
            "messages": _claude_messages([message for message in request.messages if message.role != "system"]),
        }
        if system_text:
            payload["system"] = system_text
        if request.tools:
            payload["tools"] = [_claude_tool(tool) for tool in request.tools]
        if stream:
            payload["stream"] = True
        return payload

    def parse_response(self, response: Dict[str, Any]) -> ModelResponse:
        text_parts: List[str] = []
        tool_calls: List[ToolCall] = []
        for block in response.get("content", []) or []:
            block_type = block.get("type", "")
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=dict(block.get("input") or {}),
                        raw=block,
                    )
                )
        usage = response.get("usage") or {}
        return ModelResponse(
            message=Message.from_text("assistant", "".join(text_parts), tool_calls=tool_calls),
            usage=ModelUsage(
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
                total_tokens=int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0)),
                raw=usage,
            )
            if usage
            else None,
            stop_reason=response.get("stop_reason", ""),
            raw=response,
        )

    def parse_stream_event(self, event: Dict[str, Any]) -> List[ModelStreamEvent]:
        event_type = event.get("type")
        if event_type == "content_block_start":
            block = event.get("content_block") or {}
            if block.get("type") == "tool_use":
                return [
                    ModelStreamEvent(
                        type="tool_call_delta",
                        tool_call=ToolCall(
                            id=block.get("id", ""),
                            name=block.get("name", ""),
                            arguments=dict(block.get("input") or {}),
                            raw=event,
                        ),
                        raw=event,
                    )
                ]
        if event_type == "content_block_delta":
            delta = event.get("delta") or {}
            if delta.get("type") == "text_delta":
                return [ModelStreamEvent(type="text_delta", delta=delta.get("text", ""), raw=event)]
            if delta.get("type") == "input_json_delta":
                return [
                    ModelStreamEvent(
                        type="tool_call_delta",
                        tool_call=ToolCall(
                            id="",
                            name="",
                            arguments={"__delta__": delta.get("partial_json", "")},
                            raw=event,
                        ),
                        raw=event,
                    )
                ]
        return []


class GeminiGenerateContentAdapter(ProviderAdapter):
    provider = "gemini"
    path = ""
    stream_path = ""

    def path_for_model(self, model: str, stream: bool = False) -> str:
        action = "streamGenerateContent?alt=sse" if stream else "generateContent"
        return "/models/%s:%s" % (model, action)

    def request_payload(self, request: ModelRequest, stream: bool = False) -> Dict[str, Any]:
        system_text = "\n".join(message.content_text() for message in request.messages if message.role == "system")
        payload: Dict[str, Any] = {
            "contents": _gemini_contents([message for message in request.messages if message.role != "system"]),
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        if request.tools:
            payload["tools"] = [{"functionDeclarations": [_gemini_function_declaration(tool) for tool in request.tools]}]
        return payload

    def parse_response(self, response: Dict[str, Any]) -> ModelResponse:
        candidate = (response.get("candidates") or [{}])[0]
        content = candidate.get("content", {})
        text_parts: List[str] = []
        tool_calls: List[ToolCall] = []
        for part in content.get("parts", []) or []:
            if "text" in part:
                text_parts.append(part.get("text", ""))
            if "functionCall" in part:
                call = part["functionCall"]
                tool_calls.append(
                    ToolCall(
                        id=call.get("id", "") or call.get("name", ""),
                        name=call.get("name", ""),
                        arguments=dict(call.get("args") or {}),
                        raw=call,
                    )
                )
        usage = response.get("usageMetadata") or {}
        return ModelResponse(
            message=Message.from_text(
                "assistant",
                "".join(text_parts),
                tool_calls=tool_calls,
                raw={"content": deepcopy(content)},
            ),
            usage=ModelUsage(
                input_tokens=int(usage.get("promptTokenCount", 0)),
                output_tokens=int(usage.get("candidatesTokenCount", 0)),
                total_tokens=int(usage.get("totalTokenCount", 0)),
                raw=usage,
            )
            if usage
            else None,
            stop_reason=candidate.get("finishReason", ""),
            raw=response,
        )

    def parse_stream_event(self, event: Dict[str, Any]) -> List[ModelStreamEvent]:
        response = self.parse_response(event)
        events = [ModelStreamEvent(type="text_delta", delta=response.content_text(), raw=event)] if response.content_text() else []
        if response.tool_calls:
            events.extend(
                ModelStreamEvent(type="tool_call_delta", tool_call=call, raw=event)
                for call in response.tool_calls
            )
            events.append(ModelStreamEvent(type="message", response=response, raw=event))
        return events


def adapter_for_provider(provider: str) -> ProviderAdapter:
    normalized = provider.strip().lower()
    if normalized in {"openai", "openai-chat", "openai-chat-completions", "chat-completions"}:
        return OpenAIChatCompletionsAdapter()
    if normalized in {"openai-responses", "responses", "response"}:
        return OpenAIResponsesAdapter()
    if normalized in {"anthropic", "claude", "claude-messages"}:
        return ClaudeMessagesAdapter()
    if normalized in {"gemini", "google", "gemini-generate-content"}:
        return GeminiGenerateContentAdapter()
    raise ValueError("unsupported provider: %s" % provider)


def _parse_json_object(raw: str, context: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderParseError("malformed JSON arguments in %s: %s" % (context, exc.msg))
    if not isinstance(parsed, dict):
        raise ProviderParseError("arguments in %s must be a JSON object" % context)
    return parsed


def _openai_usage(raw: Optional[Dict[str, Any]]) -> Optional[ModelUsage]:
    if not raw:
        return None
    return ModelUsage(
        input_tokens=int(raw.get("prompt_tokens", 0)),
        output_tokens=int(raw.get("completion_tokens", 0)),
        total_tokens=int(raw.get("total_tokens", 0)),
        raw=raw,
    )


def _openai_responses_usage(raw: Optional[Dict[str, Any]]) -> Optional[ModelUsage]:
    if not raw:
        return None
    input_tokens = int(raw.get("input_tokens", 0))
    output_tokens = int(raw.get("output_tokens", 0))
    return ModelUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=int(raw.get("total_tokens", input_tokens + output_tokens)),
        raw=raw,
    )


def _openai_chat_message(message: Message) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"role": message.role, "content": message.content_text()}
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)},
            }
            for call in message.tool_calls
        ]
    if message.tool_call_id:
        payload["tool_call_id"] = message.tool_call_id
    if message.name:
        payload["name"] = message.name
    return payload


def _openai_chat_tool(tool: ToolSpec) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {"name": tool.name, "description": tool.description, "parameters": tool.parameters},
    }


def _openai_response_inputs(message: Message) -> List[Dict[str, Any]]:
    if message.role == "tool":
        return [
            {
                "type": "function_call_output",
                "call_id": message.tool_call_id,
                "output": message.content_text(),
            }
        ]
    if message.role == "assistant":
        output = message.raw.get("output") if isinstance(message.raw, dict) else None
        if output:
            return deepcopy(output)
        if message.tool_calls:
            return [
                {
                    "type": "function_call",
                    "call_id": call.id,
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, ensure_ascii=False),
                }
                for call in message.tool_calls
            ]
    return [{"role": message.role, "content": message.content_text()}]


def _openai_response_tool(tool: ToolSpec) -> Dict[str, Any]:
    return {"type": "function", "name": tool.name, "description": tool.description, "parameters": tool.parameters}


def _claude_messages(messages: List[Message]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        if message.role != "tool":
            payload.append(_claude_message(message))
            index += 1
            continue
        blocks = []
        while index < len(messages) and messages[index].role == "tool":
            blocks.append(_claude_tool_result_block(messages[index]))
            index += 1
        payload.append({"role": "user", "content": blocks})
    return payload


def _claude_message(message: Message) -> Dict[str, Any]:
    if message.role == "tool":
        return {"role": "user", "content": [_claude_tool_result_block(message)]}
    content: List[Dict[str, Any]] = []
    if message.content_text():
        content.append({"type": "text", "text": message.content_text()})
    for call in message.tool_calls:
        content.append({"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments})
    return {"role": "assistant" if message.role == "assistant" else "user", "content": content}


def _claude_tool(tool: ToolSpec) -> Dict[str, Any]:
    return {"name": tool.name, "description": tool.description, "input_schema": tool.parameters}


def _claude_tool_result_block(message: Message) -> Dict[str, Any]:
    block = {"type": "tool_result", "tool_use_id": message.tool_call_id, "content": message.content_text()}
    raw = message.raw if isinstance(message.raw, dict) else {}
    if raw.get("is_error"):
        block["is_error"] = True
    return block


def _gemini_contents(messages: List[Message]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        if message.role != "tool":
            payload.append(_gemini_content(message))
            index += 1
            continue
        parts = []
        while index < len(messages) and messages[index].role == "tool":
            parts.append(_gemini_function_response(messages[index]))
            index += 1
        payload.append({"role": "user", "parts": parts})
    return payload


def _gemini_content(message: Message) -> Dict[str, Any]:
    if message.role == "tool":
        return {"role": "user", "parts": [_gemini_function_response(message)]}
    content = message.raw.get("content") if isinstance(message.raw, dict) else None
    if message.role == "assistant" and isinstance(content, dict):
        return deepcopy(content)
    parts: List[Dict[str, Any]] = []
    if message.content_text():
        parts.append({"text": message.content_text()})
    for call in message.tool_calls:
        parts.append({"functionCall": {"id": call.id, "name": call.name, "args": call.arguments}})
    return {"role": "model" if message.role == "assistant" else "user", "parts": parts}


def _gemini_function_declaration(tool: ToolSpec) -> Dict[str, Any]:
    return {"name": tool.name, "description": tool.description, "parameters": tool.parameters}


def _gemini_function_response(message: Message) -> Dict[str, Any]:
    return {
        "functionResponse": {
            "id": message.tool_call_id,
            "name": message.name,
            "response": {"result": message.content_text()},
        }
    }
