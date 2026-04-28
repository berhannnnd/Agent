from typing import Any, AsyncIterable, Dict
from urllib.parse import urljoin

import httpx

from agent.models.errors import (
    ModelClientError,
    ModelConnectionError,
    ModelRateLimitError,
    ModelServerError,
    ModelAuthError,
    ModelContextWindowError,
    ModelTimeoutError,
    ModelBadRequestError,
)
from agent.models.transports.sse import parse_sse_json_line


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
        except httpx.NetworkError as exc:
            raise ModelConnectionError(_http_error_message("model request connection failed", exc)) from exc
        except httpx.HTTPError as exc:
            raise ModelClientError(_http_error_message("model request failed", exc)) from exc

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
                    parsed = parse_sse_json_line(line)
                    if parsed is None:
                        continue
                    yield parsed
        except httpx.TimeoutException as exc:
            raise ModelTimeoutError("model stream timed out: %s" % exc) from exc
        except httpx.NetworkError as exc:
            raise ModelConnectionError(_http_error_message("model stream connection failed", exc)) from exc
        except httpx.HTTPError as exc:
            raise ModelClientError(_http_error_message("model stream failed", exc)) from exc

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    def _headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        return {"Content-Type": "application/json", **headers}

    async def async_close(self) -> None:
        await self._client.aclose()


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


def _http_error_message(prefix: str, exc: httpx.HTTPError) -> str:
    detail = str(exc).strip() or exc.__class__.__name__
    request = getattr(exc, "request", None)
    if request is not None:
        return "%s: %s %s" % (prefix, detail, request.url)
    return "%s: %s" % (prefix, detail)
