from typing import Any, Dict, List, Optional

from app.agent.providers.adapters.base import ProviderAdapter
from app.agent.schema import Message, ModelRequest, ModelResponse, ModelStreamEvent, ModelUsage, ToolCall


class ClaudeMessagesAdapter(ProviderAdapter):
    provider = "claude-messages"
    path = "/messages"
    stream_path = "/messages"

    def auth_headers(self, api_key: str, base_url: str) -> Dict[str, str]:
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }

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


def _claude_tool(tool) -> Dict[str, Any]:
    return {"name": tool.name, "description": tool.description, "input_schema": tool.parameters}


def _claude_tool_result_block(message: Message) -> Dict[str, Any]:
    block = {"type": "tool_result", "tool_use_id": message.tool_call_id, "content": message.content_text()}
    raw = message.raw if isinstance(message.raw, dict) else {}
    if raw.get("is_error"):
        block["is_error"] = True
    return block
