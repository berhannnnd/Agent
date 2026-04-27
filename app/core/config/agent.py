import os

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config._constants import ENV_FILE


class AgentConfig(BaseSettings):
    """Agent 运行时配置。"""

    model_config = SettingsConfigDict(
        env_file=os.path.abspath(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="AGENT_",
    )

    PROVIDER: str = "openai-chat"
    TIMEOUT: float = 60.0
    MAX_TOKENS: int = 16384
    MAX_TOOL_ITERATIONS: int = 8
    SYSTEM_PROMPT: str = ""
    ENABLED_TOOLS: str = ""
    SKILLS: str = ""
    HTTP_PROXY: str = ""
    HTTPS_PROXY: str = ""
    ALL_PROXY: str = ""
    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 1.0
    MAX_CONTEXT_TOKENS: int = 256000
    MAX_CONCURRENT_TOOLS: int = 10
    MAX_CONCURRENT_REQUESTS: int = 20

    # Claude provider 的备选配置（优先级高于 ANTHROPIC_*）
    CLAUDE_API_KEY: str = ""
    CLAUDE_BASE_URL: str = ""
    CLAUDE_MODEL: str = ""


agent_config = AgentConfig()
