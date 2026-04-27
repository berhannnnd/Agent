"""Provider alias registry and base URL normalization."""

from typing import Dict, FrozenSet


# provider 标准名 → 接受的别名
_PROVIDER_ALIASES: Dict[str, FrozenSet[str]] = {
    "openai-chat": frozenset({"openai", "chat", "openai-chat-completions", "chat-completions"}),
    "openai-responses": frozenset({"responses", "response"}),
    "claude-messages": frozenset({"anthropic", "claude"}),
    "gemini": frozenset({"google", "gemini-generate-content"}),
}

# 标准名 → 默认 base URL
_PROVIDER_DEFAULT_BASE_URL: Dict[str, str] = {
    "claude-messages": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "openai-chat": "https://api.openai.com/v1",
    "openai-responses": "https://api.openai.com/v1",
}

# base URL 路径后缀清理
_URL_PATH_SUFFIXES = ["/chat/completions", "/responses", "/messages"]


def normalize_provider(value: str) -> str:
    """将 provider 别名映射为标准名，未知则返回原值（小写）。"""
    normalized = str(value or "").strip().lower()
    for standard, aliases in _PROVIDER_ALIASES.items():
        if normalized in aliases or normalized == standard:
            return standard
    return normalized or "openai-chat"


def default_base_url(provider: str) -> str:
    """获取 provider 的默认 base URL。"""
    return _PROVIDER_DEFAULT_BASE_URL.get(provider.strip().lower(), "https://api.openai.com/v1")


def normalize_base_url(provider: str, base_url: str) -> str:
    """清理 base URL，移除已知的 API 路径后缀。"""
    normalized = (base_url or default_base_url(provider)).rstrip("/")
    for suffix in _URL_PATH_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return normalized.rstrip("/")


def is_azure_openai_endpoint(base_url: str) -> bool:
    return ".openai.azure.com" in base_url.lower()
