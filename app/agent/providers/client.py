from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import AsyncIterable, Dict, Iterable, List, Optional

from app.agent.providers.adapters import GeminiGenerateContentAdapter, adapter_for_provider
from app.agent.providers.constants import normalize_base_url
from app.agent.providers.retry import RetryPolicy, _run_with_retry
from app.agent.providers.stream import _StreamToolCallAccumulator, _final_stream_response
from app.agent.providers.transport import HttpxModelTransport
from app.agent.schema import ModelRequest, ModelResponse, ModelStreamEvent


@dataclass(frozen=True)
class ModelClientConfig:
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""
    timeout: float = 60.0
    max_tokens: int = 4096
    proxy_url: str = ""
    max_retries: int = 3
    retry_base_delay: float = 1.0


class ModelClient:
    def __init__(
        self,
        config: ModelClientConfig,
        transport: Optional[HttpxModelTransport] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        adapter = adapter_for_provider(config.provider)
        normalized_base_url = normalize_base_url(config.provider, config.base_url)
        self.config = replace(config, provider=adapter.provider, base_url=normalized_base_url)
        self.adapter = adapter
        self.transport = transport or HttpxModelTransport(self.config.base_url, proxy_url=self.config.proxy_url)
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=config.max_retries,
            base_delay=config.retry_base_delay,
        )

    async def async_complete(self, request_data: ModelRequest) -> ModelResponse:
        request_data = self._with_config(request_data)
        path = self._path(stream=False)
        payload = self.adapter.request_payload(request_data)

        async def _do():
            response = await self.transport.async_post_json(
                path, payload, self._headers(), self.config.timeout
            )
            return self.adapter.parse_response(response)

        return await _run_with_retry(self.retry_policy, _do)

    async def async_stream(self, request_data: ModelRequest) -> AsyncIterable[ModelStreamEvent]:
        request_data = self._with_config(request_data)
        path = self._path(stream=True)
        payload = self.adapter.request_payload(request_data, stream=True)
        text_parts: List[str] = []
        final_response: Optional[ModelResponse] = None
        tool_call_accumulator = _StreamToolCallAccumulator()

        async for chunk in self.transport.async_stream_json(
            path, payload, self._headers(), self.config.timeout
        ):
            for event in self.adapter.parse_stream_event(chunk):
                if event.type == "text_delta":
                    text_parts.append(event.delta)
                if event.type == "tool_call_delta" and event.tool_call is not None:
                    tool_call_accumulator.add(event.tool_call)
                if event.type == "message" and event.response is not None:
                    final_response = event.response
                yield event
        final_response = _final_stream_response(
            final_response, "".join(text_parts), tool_call_accumulator.tool_calls()
        )
        yield ModelStreamEvent(type="message", response=final_response)

    def complete(self, request_data: ModelRequest) -> ModelResponse:
        """同步兼容方法（内部使用 asyncio.run）。"""
        return asyncio.run(self.async_complete(request_data))

    def stream(self, request_data: ModelRequest) -> Iterable[ModelStreamEvent]:
        """同步兼容方法（内部使用 asyncio.run）。"""
        async def _collect():
            return [event async for event in self.async_stream(request_data)]
        return iter(asyncio.run(_collect()))

    def _with_config(self, request_data: ModelRequest) -> ModelRequest:
        metadata = dict(request_data.metadata)
        metadata.setdefault("max_tokens", self.config.max_tokens)
        return ModelRequest(
            provider=self.config.provider,
            model=self.config.model or request_data.model,
            messages=request_data.messages,
            tools=request_data.tools,
            metadata=metadata,
            raw=request_data.raw,
        )

    def _path(self, stream: bool) -> str:
        if isinstance(self.adapter, GeminiGenerateContentAdapter):
            return self.adapter.path_for_model(self.config.model, stream=stream)
        return self.adapter.stream_path if stream else self.adapter.path

    def _headers(self) -> Dict[str, str]:
        return self.adapter.auth_headers(self.config.api_key, self.config.base_url)


def create_model_client(config: ModelClientConfig) -> ModelClient:
    return ModelClient(config)
