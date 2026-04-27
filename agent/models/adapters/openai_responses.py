import json
from copy import deepcopy
from typing import Any, Dict, List, Optional

from agent.models.adapters.base import ProviderAdapter, ProviderParseError
from agent.models.constants import is_azure_openai_endpoint
from agent.schema import Message, ModelRequest, ModelResponse, ModelStreamEvent, ModelUsage, ToolCall


class OpenAIResponsesAdapter(ProviderAdapter):
    provider = "openai-responses"
    path = "/responses"
    stream_path = "/responses"

    def auth_headers(self, api_key: str, base_url: str) -> Dict[str, str]:
        if is_azure_openai_endpoint(base_url):
            return {"api-key": api_key}
        return {"Authorization": "Bearer %s" % api_key}

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


def _parse_json_object(raw: str, context: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderParseError("malformed JSON arguments in %s: %s" % (context, exc.msg))
    if not isinstance(parsed, dict):
        raise ProviderParseError("arguments in %s must be a JSON object" % context)
    return parsed


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


def _openai_response_tool(tool) -> Dict[str, Any]:
    return {"type": "function", "name": tool.name, "description": tool.description, "parameters": tool.parameters}
