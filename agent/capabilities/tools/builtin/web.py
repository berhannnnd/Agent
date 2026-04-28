from __future__ import annotations

from typing import Any

from agent.capabilities.tools.context import ToolRuntimeContext
from agent.capabilities.web import (
    WebExtractRequest,
    WebMapRequest,
    WebSearchProvider,
    WebSearchRequest,
)


WEB_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query."},
        "topic": {"type": "string", "enum": ["general", "news", "finance"]},
        "search_depth": {"type": "string", "enum": ["basic", "advanced", "fast", "ultra_fast"]},
        "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
        "time_range": {"type": "string", "description": "Optional recency range such as day, week, month, or year."},
        "include_domains": {"type": "array", "items": {"type": "string"}},
        "exclude_domains": {"type": "array", "items": {"type": "string"}},
        "country": {"type": "string"},
        "include_answer": {"type": "boolean"},
        "include_raw_content": {"type": "boolean"},
        "chunks_per_source": {"type": "integer", "minimum": 1, "maximum": 10},
    },
    "required": ["query"],
}

WEB_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "urls": {"type": "array", "items": {"type": "string"}},
        "query": {"type": "string", "description": "Optional extraction intent used for reranking chunks."},
        "extract_depth": {"type": "string", "enum": ["basic", "advanced"]},
        "format": {"type": "string", "enum": ["markdown", "text"]},
        "chunks_per_source": {"type": "integer", "minimum": 1, "maximum": 10},
    },
    "required": ["urls"],
}

WEB_MAP_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {"type": "string", "description": "Root URL to map."},
        "instructions": {"type": "string"},
        "max_depth": {"type": "integer", "minimum": 1, "maximum": 5},
        "limit": {"type": "integer", "minimum": 1, "maximum": 500},
        "include_domains": {"type": "array", "items": {"type": "string"}},
        "exclude_domains": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["url"],
}


async def web_search(
    context: ToolRuntimeContext,
    provider: WebSearchProvider,
    query: str,
    topic: str = "general",
    search_depth: str = "basic",
    max_results: int = 5,
    time_range: str = "",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    country: str = "",
    include_answer: bool = False,
    include_raw_content: bool = False,
    chunks_per_source: int = 3,
) -> dict[str, Any]:
    result = await provider.search(
        WebSearchRequest(
            query=query,
            topic=topic,
            search_depth=search_depth,
            max_results=max_results,
            time_range=time_range,
            include_domains=tuple(include_domains or ()),
            exclude_domains=tuple(exclude_domains or ()),
            country=country,
            include_answer=include_answer,
            include_raw_content=include_raw_content,
            chunks_per_source=chunks_per_source,
        ),
        run_id=context.current_run_id,
    )
    return result.to_dict()


async def web_extract(
    context: ToolRuntimeContext,
    provider: WebSearchProvider,
    urls: list[str],
    query: str = "",
    extract_depth: str = "basic",
    format: str = "markdown",
    chunks_per_source: int = 3,
) -> dict[str, Any]:
    result = await provider.extract(
        WebExtractRequest(
            urls=tuple(urls or ()),
            query=query,
            extract_depth=extract_depth,
            format=format,
            chunks_per_source=chunks_per_source,
        ),
        run_id=context.current_run_id,
    )
    return result.to_dict()


async def web_map(
    context: ToolRuntimeContext,
    provider: WebSearchProvider,
    url: str,
    instructions: str = "",
    max_depth: int = 1,
    limit: int = 50,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> dict[str, Any]:
    result = await provider.map(
        WebMapRequest(
            url=url,
            instructions=instructions,
            max_depth=max_depth,
            limit=limit,
            include_domains=tuple(include_domains or ()),
            exclude_domains=tuple(exclude_domains or ()),
        ),
        run_id=context.current_run_id,
    )
    return result.to_dict()
