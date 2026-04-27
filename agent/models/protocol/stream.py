import json
from typing import Any, Dict, List, Optional

from agent.models.errors import ModelClientError
from agent.models.protocol.events import ModelStreamEventType
from agent.schema import Message, ModelResponse, ModelStreamEvent, ModelUsage, ToolCall


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


class ModelStreamState:
    """Accumulates provider-neutral stream events into a final ModelResponse."""

    def __init__(self) -> None:
        self.text_parts: List[str] = []
        self.reasoning_parts: List[str] = []
        self.final_response: Optional[ModelResponse] = None
        self.usage: Optional[ModelUsage] = None
        self.tool_call_accumulator = _StreamToolCallAccumulator()

    def apply(self, event: ModelStreamEvent) -> None:
        if event.type == ModelStreamEventType.TEXT_DELTA.value:
            self.text_parts.append(event.delta)
        elif event.type == ModelStreamEventType.REASONING_DELTA.value:
            self.reasoning_parts.append(event.delta)
        elif event.type == ModelStreamEventType.TOOL_CALL_DELTA.value and event.tool_call is not None:
            self.tool_call_accumulator.add(event.tool_call)
        elif event.type == ModelStreamEventType.USAGE.value and event.usage is not None:
            self.usage = event.usage
        elif event.type == ModelStreamEventType.MESSAGE.value and event.response is not None:
            self.final_response = event.response
            if event.response.usage is not None:
                self.usage = event.response.usage

    def finalize(self) -> ModelResponse:
        return _final_stream_response(
            self.final_response,
            "".join(self.text_parts),
            self.tool_call_accumulator.tool_calls(),
            usage=self.usage,
            reasoning="".join(self.reasoning_parts),
        )


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
    usage: Optional[ModelUsage] = None,
    reasoning: str = "",
) -> ModelResponse:
    raw_response = _stream_raw_response(tool_calls)
    message_raw = _merge_message_raw(raw_response, None, reasoning)
    if final_response is None:
        return ModelResponse(
            message=Message.from_text("assistant", text, tool_calls=tool_calls, raw=message_raw),
            usage=usage,
            raw=raw_response,
        )
    if tool_calls:
        message_raw = _merge_message_raw(raw_response, final_response.message.raw, reasoning)
        return ModelResponse(
            message=Message.from_text(
                "assistant",
                text or final_response.content_text(),
                tool_calls=tool_calls,
                raw=message_raw,
            ),
            usage=usage or final_response.usage,
            stop_reason=final_response.stop_reason,
            raw=raw_response or final_response.raw,
        )
    if text and not final_response.content_text():
        return ModelResponse(
            message=Message.from_text(
                "assistant",
                text,
                raw=_merge_message_raw(None, final_response.message.raw, reasoning),
            ),
            usage=usage or final_response.usage,
            stop_reason=final_response.stop_reason,
            raw=final_response.raw,
        )
    if usage is not None and final_response.usage is None:
        return ModelResponse(
            message=Message.from_text(
                "assistant",
                final_response.content_text(),
                tool_calls=final_response.tool_calls,
                raw=_merge_message_raw(None, final_response.message.raw, reasoning),
            ),
            usage=usage,
            stop_reason=final_response.stop_reason,
            raw=final_response.raw,
        )
    if reasoning:
        return ModelResponse(
            message=Message.from_text(
                "assistant",
                final_response.content_text(),
                tool_calls=final_response.tool_calls,
                raw=_merge_message_raw(None, final_response.message.raw, reasoning),
            ),
            usage=final_response.usage,
            stop_reason=final_response.stop_reason,
            raw=final_response.raw,
        )
    return final_response


def _merge_message_raw(raw_response: Optional[Dict[str, Any]], message_raw: Any, reasoning: str) -> Any:
    raw = raw_response if raw_response is not None else message_raw
    if not reasoning:
        return raw
    if isinstance(raw, dict):
        merged = dict(raw)
    elif raw is None:
        merged = {}
    else:
        merged = {"native": raw}
    merged["reasoning"] = reasoning
    return merged
