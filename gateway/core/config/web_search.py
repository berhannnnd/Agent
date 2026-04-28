from pydantic_settings import BaseSettings, SettingsConfigDict

from gateway.core.config._constants import ENV_FILE
from gateway.core.config.loader import config_value


class WebSearchConfig(BaseSettings):
    """Control-plane web search provider configuration."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="WEB_SEARCH_",
    )

    PROVIDER: str = config_value("web_search", "PROVIDER", "none")
    TAVILY_API_KEY: str = ""
    TAVILY_BASE_URL: str = config_value("web_search", "TAVILY_BASE_URL", "https://api.tavily.com")
    TIMEOUT: float = config_value("web_search", "TIMEOUT", 30.0)
    MAX_RESULTS: int = config_value("web_search", "MAX_RESULTS", 5)
    MAX_CREDITS_PER_RUN: float = config_value("web_search", "MAX_CREDITS_PER_RUN", 10.0)
    ALLOW_DOMAINS: str = config_value("web_search", "ALLOW_DOMAINS", "")
    DENY_DOMAINS: str = config_value("web_search", "DENY_DOMAINS", "")
    ALLOW_ADVANCED: bool = config_value("web_search", "ALLOW_ADVANCED", False)
    ALLOW_RAW_CONTENT: bool = config_value("web_search", "ALLOW_RAW_CONTENT", False)


web_search_config = WebSearchConfig()
