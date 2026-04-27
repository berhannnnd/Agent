from __future__ import annotations

from typing import AsyncIterable, List

from agent.schema import ModelRequest, ModelResponse, ModelStreamEvent


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
