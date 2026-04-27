import json
from typing import Any, Dict, List, Optional

from app.agent.providers.errors import ModelClientError
from app.agent.schema import Message, ModelResponse, ModelStreamEvent, ToolCall


def parse_sse_json_line(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line or line.startswith(":"):
        return None
    if line.startswith("data:"):
        line = line[len("data:") :].strip()
    elif ":" in line:
        return None
    if line == "[DONE]":
        return None
    return json.loads(line)


class _StreamToolCallAccumulator:
    def __init__(self) -> None:
        self._items: Dict[str, Dict[str, Any]] = {}
        self._order: List[str] = []

    def add(self, call: ToolCall) -> None:
        key = self._key_for(call)
        if key not in self._items:
            self._items[key] = {"id": "", "name": "", "arguments": {}, "argument_parts": [], "response_output_item": None}
            self._order.append(key)
        item = self._items[key]
        raw = call.raw if isinstance(call.raw, dict) else {}
        response_item = raw.get("item") if isinstance(raw.get("item"), dict) else None
        if response_item and response_item.get("type") == "function_call":
            item["response_output_item"] = dict(response_item)
        if call.id:
            item["id"] = call.id
        if call.name:
            item["name"] = call.name
        if "__delta__" in call.arguments:
            item["argument_parts"].append(str(call.arguments.get("__delta__", "")))
        elif call.arguments:
            item["arguments"].update(call.arguments)

    def tool_calls(self) -> List[ToolCall]:
        calls: List[ToolCall] = []
        for key in self._order:
            item = self._items[key]
            arguments = dict(item["arguments"])
            argument_text = "".join(item["argument_parts"])
            if argument_text:
                try:
                    parsed = json.loads(argument_text)
                except json.JSONDecodeError as exc:
                    raise ModelClientError("model stream returned malformed tool arguments: %s" % exc.msg) from exc
                if not isinstance(parsed, dict):
                    raise ModelClientError("model stream tool arguments must be a JSON object")
                arguments.update(parsed)
            calls.append(
                ToolCall(
                    id=item["id"] or item["name"] or key,
                    name=item["name"],
                    arguments=arguments,
                    raw=_stream_tool_call_raw(item, arguments),
                )
            )
        return calls

    def _key_for(self, call: ToolCall) -> str:
        raw = call.raw if isinstance(call.raw, dict) else {}
        if "index" in raw:
            return str(raw["index"])
        if "output_index" in raw:
            return str(raw["output_index"])
        if not call.id and not call.name and len(self._order) == 1:
            return self._order[0]
        return call.id or call.name or str(len(self._order))


def _stream_tool_call_raw(item: Dict[str, Any], arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    response_item = item.get("response_output_item")
    if not isinstance(response_item, dict):
        return None
    normalized = dict(response_item)
    normalized["arguments"] = json.dumps(arguments, ensure_ascii=False)
    return {"response_output_item": normalized}


def _stream_raw_response(tool_calls: List[ToolCall]) -> Optional[Dict[str, Any]]:
    output = []
    for call in tool_calls:
        raw = call.raw if isinstance(call.raw, dict) else {}
        item = raw.get("response_output_item")
        if isinstance(item, dict):
            output.append(dict(item))
    if not output:
        return None
    return {"output": output}


def _final_stream_response(
    final_response: Optional[ModelResponse],
    text: str,
    tool_calls: List[ToolCall],
) -> ModelResponse:
    raw_response = _stream_raw_response(tool_calls)
    if final_response is None:
        return ModelResponse(
            message=Message.from_text("assistant", text, tool_calls=tool_calls, raw=raw_response),
            raw=raw_response,
        )
    if tool_calls:
        message_raw = raw_response or final_response.message.raw
        return ModelResponse(
            message=Message.from_text(
                "assistant",
                text or final_response.content_text(),
                tool_calls=tool_calls,
                raw=message_raw,
            ),
            usage=final_response.usage,
            stop_reason=final_response.stop_reason,
            raw=raw_response or final_response.raw,
        )
    if text and not final_response.content_text():
        return ModelResponse(
            message=Message.from_text("assistant", text, raw=final_response.message.raw),
            usage=final_response.usage,
            stop_reason=final_response.stop_reason,
            raw=final_response.raw,
        )
    return final_response
