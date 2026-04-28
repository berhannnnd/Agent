from __future__ import annotations

from typing import Any

from agent.capabilities.web.policy import WebSearchPolicy
from agent.capabilities.web.providers.tavily import TavilyConfig, TavilyWebSearchProvider
from agent.capabilities.web.types import NullWebSearchProvider, WebSearchProvider


def create_web_search_provider(settings: Any) -> WebSearchProvider:
    config = getattr(settings, "web_search", None)
    provider = str(getattr(config, "PROVIDER", "") or "").strip().lower()
    if provider in {"", "none", "disabled", "off"}:
        return NullWebSearchProvider()
    if provider != "tavily":
        raise ValueError("unknown web search provider: %s" % provider)
    policy = WebSearchPolicy(
        max_results=int(getattr(config, "MAX_RESULTS", 5) or 5),
        max_credits_per_run=float(getattr(config, "MAX_CREDITS_PER_RUN", 10.0) or 0),
        allow_domains=_csv_setting(getattr(config, "ALLOW_DOMAINS", "")),
        deny_domains=_csv_setting(getattr(config, "DENY_DOMAINS", "")),
        allow_advanced=bool(getattr(config, "ALLOW_ADVANCED", False)),
        allow_raw_content=bool(getattr(config, "ALLOW_RAW_CONTENT", False)),
    )
    return TavilyWebSearchProvider(
        TavilyConfig(
            api_key=str(getattr(config, "TAVILY_API_KEY", "") or ""),
            base_url=str(getattr(config, "TAVILY_BASE_URL", "https://api.tavily.com") or "https://api.tavily.com"),
            timeout_seconds=float(getattr(config, "TIMEOUT", 30.0) or 30.0),
        ),
        policy,
    )


def _csv_setting(raw: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(raw or "").split(",") if item.strip())
