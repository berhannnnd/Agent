import json
from typing import Any, Dict, List, Optional

from agent.models.adapters.base import ProviderAdapter, ProviderParseError
from agent.models.constants import is_azure_openai_endpoint
from agent.models.protocol import reasoning_delta, text_delta, tool_call_delta, usage_event
from agent.schema import Message, ModelRequest, ModelResponse, ModelStreamEvent, ModelUsage, ToolCall


class OpenAIChatCompletionsAdapter(ProviderAdapter):
    provider = "openai-chat"
    path = "/chat/completions"
    stream_path = "/chat/completions"

    def auth_headers(self, api_key: str, base_url: str) -> Dict[str, str]:
        if is_azure_openai_endpoint(base_url):
            return {"api-key": api_key}
        return {"Authorization": "Bearer %s" % api_key}

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
            events.append(text_delta(delta["content"], raw=event))
        if delta.get("reasoning_content"):
            events.append(reasoning_delta(delta["reasoning_content"], raw=event))
        for raw_call in delta.get("tool_calls", []) or []:
            function = raw_call.get("function", {})
            events.append(
                tool_call_delta(
                    ToolCall(
                        id=raw_call.get("id", ""),
                        name=function.get("name", ""),
                        arguments={"__delta__": function.get("arguments", "")},
                        raw=raw_call,
                    ),
                    raw=event,
                )
            )
        usage = event.get("usage")
        if usage:
            parsed_usage = _openai_usage(usage)
            if parsed_usage is not None:
                events.append(usage_event(parsed_usage, raw=event))
        return events


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


def _openai_chat_tool(tool) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {"name": tool.name, "description": tool.description, "parameters": tool.parameters},
    }
