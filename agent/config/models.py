from __future__ import annotations

from typing import Any, Optional

from agent.models import ModelClientConfig
from agent.models.constants import normalize_protocol


class AgentConfigError(ValueError):
    """Raised when agent runtime config is incomplete."""


_PROTOCOL_CONFIG_SOURCES: dict[str, dict[str, list[str]]] = {
    "claude-messages": {
        "api_key": ["agent.CLAUDE_API_KEY", "models.anthropic.API_KEY"],
        "base_url": ["agent.CLAUDE_BASE_URL", "models.anthropic.BASE_URL"],
        "model": ["agent.CLAUDE_MODEL", "models.anthropic.MODEL"],
    },
    "gemini": {
        "api_key": ["models.gemini.API_KEY"],
        "base_url": ["models.gemini.BASE_URL"],
        "model": ["models.gemini.MODEL"],
    },
    "openai-responses": {
        "api_key": ["models.openai_responses.API_KEY", "models.openai.API_KEY"],
        "base_url": ["models.openai_responses.BASE_URL", "models.openai.BASE_URL"],
        "model": ["models.openai_responses.MODEL", "models.openai.MODEL"],
    },
    "openai-chat": {
        "api_key": ["models.openai.API_KEY"],
        "base_url": ["models.openai.BASE_URL"],
        "model": ["models.openai.MODEL"],
    },
}


def resolve_model_client_config(
    settings: Any,
    protocol: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> ModelClientConfig:
    active_protocol = normalize_protocol(protocol or settings.agent.PROTOCOL)
    sources = _PROTOCOL_CONFIG_SOURCES.get(active_protocol, _PROTOCOL_CONFIG_SOURCES["openai-chat"])

    resolved_api_key = _coalesce(api_key, _resolve_config_value(settings, sources["api_key"]))
    resolved_base_url = _coalesce(base_url, _resolve_config_value(settings, sources["base_url"]))
    resolved_model = _coalesce(model, _resolve_config_value(settings, sources["model"]))

    if not resolved_api_key or not resolved_model:
        missing = []
        if not resolved_api_key:
            missing.append("API_KEY")
        if not resolved_model:
            missing.append("MODEL")
        raise AgentConfigError("missing agent model configuration: %s" % ", ".join(missing))

    return ModelClientConfig(
        protocol=active_protocol,
        model=resolved_model,
        api_key=resolved_api_key,
        base_url=resolved_base_url,
        timeout=settings.agent.TIMEOUT,
        max_tokens=settings.agent.MAX_TOKENS,
        proxy_url=_proxy_url(settings),
        max_retries=settings.agent.MAX_RETRIES,
        retry_base_delay=settings.agent.RETRY_BASE_DELAY,
    )


def _resolve_config_value(settings: Any, attr_paths: list[str]) -> str:
    for path in attr_paths:
        value = settings
        for part in path.split("."):
            value = getattr(value, part, None)
            if value is None:
                break
        if value is not None:
            result = str(value).strip()
            if result:
                return result
    return ""


def _coalesce(override: Optional[str], configured: Any) -> str:
    value = configured if override is None else override
    return str(value).strip() if value is not None else ""


def _proxy_url(settings: Any) -> str:
    for attr in ("HTTPS_PROXY", "ALL_PROXY", "HTTP_PROXY"):
        value = _coalesce(None, getattr(settings.agent, attr, ""))
        if value:
            return value
    return ""
