from copy import deepcopy
from typing import Any, Dict, List, Optional

from agent.models.adapters.base import ProtocolAdapter
from agent.models.protocol import message_event, text_delta, tool_call_delta
from agent.schema import Message, ModelRequest, ModelResponse, ModelStreamEvent, ModelUsage, ToolCall


class GeminiGenerateContentAdapter(ProtocolAdapter):
    protocol = "gemini"
    path = ""
    stream_path = ""

    def auth_headers(self, api_key: str, base_url: str) -> Dict[str, str]:
        return {"x-goog-api-key": api_key}

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
        events = [text_delta(response.content_text(), raw=event)] if response.content_text() else []
        if response.tool_calls:
            events.extend(
                tool_call_delta(call, raw=event)
                for call in response.tool_calls
            )
            events.append(message_event(response, raw=event))
        return events


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


def _gemini_function_declaration(tool) -> Dict[str, Any]:
    return {"name": tool.name, "description": tool.description, "parameters": tool.parameters}


def _gemini_function_response(message: Message) -> Dict[str, Any]:
    return {
        "functionResponse": {
            "id": message.tool_call_id,
            "name": message.name,
            "response": {"result": message.content_text()},
        }
    }
