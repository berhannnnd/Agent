# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：client.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass, replace
from typing import Any, AsyncIterable, Dict, Iterable, List, Optional, Protocol
from urllib.parse import urljoin

import httpx

from app.agent.providers.adapters import GeminiGenerateContentAdapter, adapter_for_provider
from app.agent.schema import Message, ModelRequest, ModelResponse, ModelStreamEvent, ToolCall


# ============ 错误分类 ============

class ModelClientError(RuntimeError):
    """Raised when a model provider request fails."""


class ModelRateLimitError(ModelClientError):
    """HTTP 429 — should retry with backoff."""


class ModelServerError(ModelClientError):
    """HTTP 5xx — should retry with backoff."""


class ModelAuthError(ModelClientError):
    """HTTP 401/403 — do not retry."""


class ModelContextWindowError(ModelClientError):
    """Context window or token limit exceeded — trigger truncation."""


class ModelTimeoutError(ModelClientError):
    """Request or connection timed out — should retry."""


class ModelBadRequestError(ModelClientError):
    """HTTP 400 (other) — do not retry."""


# ============ 重试策略 ============

@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 1.0
    retry_429: bool = True
    retry_5xx: bool = True
    retry_timeout: bool = True


def _should_retry(err: ModelClientError, attempt: int, policy: RetryPolicy) -> bool:
    if attempt >= policy.max_attempts:
        return False
    if isinstance(err, ModelRateLimitError) and policy.retry_429:
        return True
    if isinstance(err, ModelServerError) and policy.retry_5xx:
        return True
    if isinstance(err, ModelTimeoutError) and policy.retry_timeout:
        return True
    return False


def _backoff(base_delay: float, attempt: int) -> float:
    """指数退避 + jitter(0.9~1.1)。attempt 从 1 开始计数。"""
    if attempt <= 1:
        return base_delay
    exp = 2 ** (attempt - 1)
    raw = base_delay * exp
    jitter = random.uniform(0.9, 1.1)
    return raw * jitter


async def _run_with_retry(policy: RetryPolicy, op):
    """运行异步操作，在可重试错误时按策略重试。"""
    last_err = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await op()
        except ModelClientError as err:
            last_err = err
            if not _should_retry(err, attempt, policy):
                raise
            delay = _backoff(policy.base_delay, attempt)
            await asyncio.sleep(delay)
    raise last_err


# ============ Transport ============

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


class ModelTransport(Protocol):
    async def async_post_json(
        self, path: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float
    ) -> Dict[str, Any]:
        raise NotImplementedError()

    async def async_stream_json(
        self, path: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float
    ) -> AsyncIterable[Dict[str, Any]]:
        raise NotImplementedError()


class HttpxModelTransport:
    def __init__(self, base_url: str, proxy_url: str = ""):
        self.base_url = base_url.rstrip("/") + "/"
        self.proxy_url = proxy_url.strip()
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
        self._client = httpx.AsyncClient(
            limits=limits,
            http2=False,
            proxy=self.proxy_url or None,
            trust_env=not bool(self.proxy_url),
        )

    async def async_post_json(
        self, path: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float
    ) -> Dict[str, Any]:
        try:
            response = await self._client.post(
                self._url(path), json=payload, headers=self._headers(headers), timeout=timeout
            )
            if response.status_code < 200 or response.status_code >= 300:
                _raise_from_status(response.status_code, response.text)
            return response.json()
        except httpx.TimeoutException as exc:
            raise ModelTimeoutError("model request timed out: %s" % exc) from exc
        except httpx.HTTPError as exc:
            raise ModelClientError("model request failed: %s" % exc) from exc

    async def async_stream_json(
        self, path: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float
    ) -> AsyncIterable[Dict[str, Any]]:
        try:
            async with self._client.stream(
                "POST", self._url(path), json=payload, headers=self._headers(headers), timeout=timeout
            ) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    body = await response.aread()
                    _raise_from_status(response.status_code, body.decode("utf-8", errors="replace"))
                async for line in response.aiter_lines():
                    parsed = _parse_sse_json_line(line)
                    if parsed is None:
                        continue
                    yield parsed
        except httpx.TimeoutException as exc:
            raise ModelTimeoutError("model stream timed out: %s" % exc) from exc
        except httpx.HTTPError as exc:
            raise ModelClientError("model stream failed: %s" % exc) from exc

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    def _headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        return {"Content-Type": "application/json", **headers}


UrllibModelTransport = HttpxModelTransport


def _raise_from_status(status_code: int, body: str) -> None:
    if status_code == 429:
        raise ModelRateLimitError("rate limited: %s" % body)
    if 500 <= status_code < 600:
        raise ModelServerError("server error %s: %s" % (status_code, body))
    if status_code in (401, 403):
        raise ModelAuthError("auth error %s: %s" % (status_code, body))
    if status_code == 400:
        lowered = body.lower()
        if any(k in lowered for k in ("context", "token", "length", "too long", "maximum")):
            raise ModelContextWindowError("context window exceeded: %s" % body)
        raise ModelBadRequestError("bad request: %s" % body)
    raise ModelClientError("model request failed: HTTP %s %s" % (status_code, body))


# ============ ModelClient ============

class ModelClient:
    def __init__(
        self,
        config: ModelClientConfig,
        transport: Optional[ModelTransport] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        adapter = adapter_for_provider(config.provider)
        normalized_base_url = _normalize_base_url(config.provider, config.base_url)
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
        if self.config.provider == "claude-messages":
            return {
                "x-api-key": self.config.api_key,
                "anthropic-version": "2023-06-01",
            }
        if self.config.provider == "gemini":
            return {"x-goog-api-key": self.config.api_key}
        if _is_azure_openai_endpoint(self.config.base_url):
            return {"api-key": self.config.api_key}
        return {"Authorization": "Bearer %s" % self.config.api_key}


def create_model_client(config: ModelClientConfig) -> ModelClient:
    return ModelClient(config)


def _parse_sse_json_line(line: str) -> Optional[Dict[str, Any]]:
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


def _normalize_base_url(provider: str, base_url: str) -> str:
    normalized = (base_url or _default_base_url(provider)).rstrip("/")
    for suffix in ["/chat/completions", "/responses", "/messages"]:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return normalized.rstrip("/")


def _default_base_url(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized in {"claude", "anthropic", "claude-messages"}:
        return "https://api.anthropic.com/v1"
    if normalized in {"gemini", "google", "gemini-generate-content"}:
        return "https://generativelanguage.googleapis.com/v1beta"
    return "https://api.openai.com/v1"


def _is_azure_openai_endpoint(base_url: str) -> bool:
    return ".openai.azure.com" in base_url.lower()
