from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class WebUsage:
    credits: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"credits": self.credits}
        if self.raw:
            payload["raw"] = dict(self.raw)
        return payload


@dataclass(frozen=True)
class WebSource:
    source_id: str
    title: str
    url: str
    domain: str
    content: str = ""
    score: float = 0.0
    published_date: str = ""
    favicon: str = ""
    raw_content: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_id": self.source_id,
            "title": self.title,
            "url": self.url,
            "domain": self.domain,
            "content": self.content,
            "score": self.score,
        }
        if self.published_date:
            payload["published_date"] = self.published_date
        if self.favicon:
            payload["favicon"] = self.favicon
        if self.raw_content:
            payload["raw_content"] = self.raw_content
        return payload


@dataclass(frozen=True)
class WebSearchRequest:
    query: str
    topic: str = "general"
    search_depth: str = "basic"
    max_results: int = 5
    time_range: str = ""
    include_domains: tuple[str, ...] = field(default_factory=tuple)
    exclude_domains: tuple[str, ...] = field(default_factory=tuple)
    country: str = ""
    include_answer: bool = False
    include_raw_content: bool = False
    chunks_per_source: int = 3


@dataclass(frozen=True)
class WebSearchResult:
    query: str
    provider: str
    sources: list[WebSource]
    provider_answer: str = ""
    request_id: str = ""
    usage: WebUsage = field(default_factory=WebUsage)
    response_time: float = 0.0
    warnings: list[str] = field(default_factory=list)
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "provider": self.provider,
            "request_id": self.request_id,
            "usage": self.usage.to_dict(),
            "response_time": self.response_time,
            "sources": [source.to_dict() for source in self.sources],
            "provider_answer": self.provider_answer,
            "warnings": list(self.warnings),
            "cached": self.cached,
        }


@dataclass(frozen=True)
class WebExtractRequest:
    urls: tuple[str, ...]
    query: str = ""
    extract_depth: str = "basic"
    format: str = "markdown"
    chunks_per_source: int = 3


@dataclass(frozen=True)
class WebExtractResult:
    provider: str
    sources: list[WebSource]
    request_id: str = ""
    usage: WebUsage = field(default_factory=WebUsage)
    response_time: float = 0.0
    failed_results: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "request_id": self.request_id,
            "usage": self.usage.to_dict(),
            "response_time": self.response_time,
            "sources": [source.to_dict() for source in self.sources],
            "failed_results": list(self.failed_results),
            "warnings": list(self.warnings),
            "cached": self.cached,
        }


@dataclass(frozen=True)
class WebMapRequest:
    url: str
    instructions: str = ""
    max_depth: int = 1
    limit: int = 50
    include_domains: tuple[str, ...] = field(default_factory=tuple)
    exclude_domains: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class WebMapResult:
    provider: str
    url: str
    urls: list[str]
    request_id: str = ""
    usage: WebUsage = field(default_factory=WebUsage)
    response_time: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "url": self.url,
            "request_id": self.request_id,
            "usage": self.usage.to_dict(),
            "response_time": self.response_time,
            "urls": list(self.urls),
            "warnings": list(self.warnings),
        }


class WebSearchProvider(Protocol):
    name: str

    async def search(self, request: WebSearchRequest, *, run_id: str = "") -> WebSearchResult:
        raise NotImplementedError()

    async def extract(self, request: WebExtractRequest, *, run_id: str = "") -> WebExtractResult:
        raise NotImplementedError()

    async def map(self, request: WebMapRequest, *, run_id: str = "") -> WebMapResult:
        raise NotImplementedError()


class NullWebSearchProvider:
    name = "none"

    async def search(self, request: WebSearchRequest, *, run_id: str = "") -> WebSearchResult:
        raise RuntimeError("web search provider is not configured")

    async def extract(self, request: WebExtractRequest, *, run_id: str = "") -> WebExtractResult:
        raise RuntimeError("web search provider is not configured")

    async def map(self, request: WebMapRequest, *, run_id: str = "") -> WebMapResult:
        raise RuntimeError("web search provider is not configured")
