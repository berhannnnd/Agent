from pydantic_settings import BaseSettings, SettingsConfigDict

from gateway.core.config._constants import ENV_FILE


class WebSearchConfig(BaseSettings):
    """Control-plane web search provider configuration."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="WEB_SEARCH_",
    )

    PROVIDER: str = "none"
    TAVILY_API_KEY: str = ""
    TAVILY_BASE_URL: str = "https://api.tavily.com"
    TIMEOUT: float = 30.0
    MAX_RESULTS: int = 5
    MAX_CREDITS_PER_RUN: float = 10.0
    ALLOW_DOMAINS: str = ""
    DENY_DOMAINS: str = ""
    ALLOW_ADVANCED: bool = False
    ALLOW_RAW_CONTENT: bool = False


web_search_config = WebSearchConfig()
