from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from agent.capabilities.web.policy import WebSearchPolicy
from agent.capabilities.web.types import (
    WebExtractRequest,
    WebExtractResult,
    WebMapRequest,
    WebMapResult,
    WebSearchRequest,
    WebSearchResult,
    WebSource,
    WebUsage,
)


@dataclass(frozen=True)
class TavilyConfig:
    api_key: str
    base_url: str = "https://api.tavily.com"
    timeout_seconds: float = 30.0


class TavilyWebSearchProvider:
    name = "tavily"

    def __init__(
        self,
        config: TavilyConfig,
        policy: WebSearchPolicy,
        client: httpx.AsyncClient | None = None,
    ):
        self.config = config
        self.policy = policy
        self._client = client

    async def search(self, request: WebSearchRequest, *, run_id: str = "") -> WebSearchResult:
        query = str(request.query or "").strip()
        if not query:
            raise ValueError("query is required")
        depth = self.policy.validate_depth(request.search_depth, parameter="search_depth")
        include_raw_content = self.policy.validate_raw_content(request.include_raw_content)
        max_results = self.policy.normalize_max_results(request.max_results)
        payload: dict[str, Any] = {
            "query": query,
            "topic": request.topic or "general",
            "search_depth": depth,
            "max_results": max_results,
            "include_answer": bool(request.include_answer),
            "include_raw_content": include_raw_content,
            "include_favicon": True,
            "include_usage": True,
        }
        if request.time_range:
            payload["time_range"] = request.time_range
        if request.country:
            payload["country"] = request.country
        if request.chunks_per_source:
            payload["chunks_per_source"] = max(1, min(int(request.chunks_per_source), 10))
        include_domains = self.policy.include_domains_for_request(request.include_domains)
        exclude_domains = self.policy.exclude_domains_for_request(request.exclude_domains)
        if include_domains:
            payload["include_domains"] = list(include_domains)
        if exclude_domains:
            payload["exclude_domains"] = list(exclude_domains)
        self.policy.reserve_credits(run_id, _estimate_search_credits(depth, include_raw_content))
        raw = await self._post("/search", payload)
        return WebSearchResult(
            query=query,
            provider=self.name,
            sources=_sources_from_results(raw.get("results") or []),
            provider_answer=str(raw.get("answer") or ""),
            request_id=_request_id(raw),
            usage=_usage(raw),
            response_time=float(raw.get("response_time") or 0),
            warnings=_warnings(raw),
        )

    async def extract(self, request: WebExtractRequest, *, run_id: str = "") -> WebExtractResult:
        urls = self.policy.validate_urls(request.urls)
        depth = self.policy.validate_depth(request.extract_depth, parameter="extract_depth")
        payload: dict[str, Any] = {
            "urls": list(urls),
            "extract_depth": depth,
            "format": request.format or "markdown",
            "include_favicon": True,
            "include_usage": True,
        }
        if request.query:
            payload["query"] = request.query
        if request.chunks_per_source:
            payload["chunks_per_source"] = max(1, min(int(request.chunks_per_source), 10))
        self.policy.reserve_credits(run_id, _estimate_extract_credits(depth, len(urls)))
        raw = await self._post("/extract", payload)
        return WebExtractResult(
            provider=self.name,
            sources=_sources_from_results(raw.get("results") or []),
            request_id=_request_id(raw),
            usage=_usage(raw),
            response_time=float(raw.get("response_time") or 0),
            failed_results=list(raw.get("failed_results") or []),
            warnings=_warnings(raw),
        )

    async def map(self, request: WebMapRequest, *, run_id: str = "") -> WebMapResult:
        urls = self.policy.validate_urls((request.url,))
        payload: dict[str, Any] = {
            "url": urls[0],
            "max_depth": max(1, min(int(request.max_depth or 1), 5)),
            "limit": max(1, min(int(request.limit or 50), 500)),
            "include_usage": True,
        }
        if request.instructions:
            payload["instructions"] = request.instructions
        include_domains = self.policy.include_domains_for_request(request.include_domains)
        exclude_domains = self.policy.exclude_domains_for_request(request.exclude_domains)
        if include_domains:
            payload["include_domains"] = list(include_domains)
        if exclude_domains:
            payload["exclude_domains"] = list(exclude_domains)
        self.policy.reserve_credits(run_id, 1)
        raw = await self._post("/map", payload)
        return WebMapResult(
            provider=self.name,
            url=urls[0],
            urls=[str(url) for url in raw.get("results") or raw.get("urls") or []],
            request_id=_request_id(raw),
            usage=_usage(raw),
            response_time=float(raw.get("response_time") or 0),
            warnings=_warnings(raw),
        )

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.config.api_key:
            raise RuntimeError("Tavily API key is not configured")
        client = self._client
        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=self.config.timeout_seconds)
            close_client = True
        try:
            response = await client.post(
                "%s%s" % (self.config.base_url.rstrip("/"), path),
                headers={"Authorization": "Bearer %s" % self.config.api_key},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise RuntimeError("Tavily returned a non-object response")
            return data
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:1000] if exc.response is not None else str(exc)
            raise RuntimeError("Tavily request failed: %s" % detail) from exc
        finally:
            if close_client:
                await client.aclose()


def _sources_from_results(results: list[dict[str, Any]]) -> list[WebSource]:
    sources: list[WebSource] = []
    for index, item in enumerate(results, start=1):
        url = str(item.get("url") or "")
        sources.append(
            WebSource(
                source_id="S%d" % index,
                title=str(item.get("title") or url),
                url=url,
                domain=urlparse(url).netloc.lower(),
                content=str(item.get("content") or item.get("raw_content") or ""),
                score=float(item.get("score") or 0),
                published_date=str(item.get("published_date") or ""),
                favicon=str(item.get("favicon") or ""),
                raw_content=str(item.get("raw_content") or ""),
            )
        )
    return sources


def _usage(raw: dict[str, Any]) -> WebUsage:
    usage = raw.get("usage")
    if isinstance(usage, dict):
        return WebUsage(credits=float(usage.get("credits") or usage.get("cost") or 0), raw=dict(usage))
    return WebUsage()


def _request_id(raw: dict[str, Any]) -> str:
    return str(raw.get("request_id") or raw.get("id") or "")


def _warnings(raw: dict[str, Any]) -> list[str]:
    warnings = raw.get("warnings") or []
    return [str(item) for item in warnings] if isinstance(warnings, list) else [str(warnings)]


def _estimate_search_credits(depth: str, include_raw_content: bool) -> float:
    return (2.0 if depth == "advanced" else 1.0) + (1.0 if include_raw_content else 0.0)


def _estimate_extract_credits(depth: str, url_count: int) -> float:
    per_url = 2.0 if depth == "advanced" else 1.0
    return per_url * max(1, int(url_count or 1))
