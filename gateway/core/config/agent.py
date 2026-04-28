import os

from pydantic_settings import BaseSettings, SettingsConfigDict

from gateway.core.config._constants import ENV_FILE
from gateway.core.config.loader import config_value


class AgentConfig(BaseSettings):
    """Agent 运行时配置。"""

    model_config = SettingsConfigDict(
        env_file=os.path.abspath(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="AGENT_",
    )

    PROVIDER: str = config_value("agent", "PROVIDER", "openai-chat")
    TIMEOUT: float = config_value("agent", "TIMEOUT", 60.0)
    MAX_TOKENS: int = config_value("agent", "MAX_TOKENS", 16384)
    MAX_TOOL_ITERATIONS: int = config_value("agent", "MAX_TOOL_ITERATIONS", 8)
    SYSTEM_PROMPT: str = config_value("agent", "SYSTEM_PROMPT", "")
    ENABLED_TOOLS: str = config_value("agent", "ENABLED_TOOLS", "")
    SKILLS: str = config_value("agent", "SKILLS", "")
    WORKSPACE_ROOT: str = config_value("agent", "WORKSPACE_ROOT", ".agents/workspaces")
    RUN_STORE: str = config_value("agent", "RUN_STORE", "memory")
    RUN_ROOT: str = config_value("agent", "RUN_ROOT", ".agents/runs")
    DB_PATH: str = config_value("agent", "DB_PATH", ".agents/agents.db")
    HTTP_PROXY: str = config_value("agent", "HTTP_PROXY", "")
    HTTPS_PROXY: str = config_value("agent", "HTTPS_PROXY", "")
    ALL_PROXY: str = config_value("agent", "ALL_PROXY", "")
    MAX_RETRIES: int = config_value("agent", "MAX_RETRIES", 3)
    RETRY_BASE_DELAY: float = config_value("agent", "RETRY_BASE_DELAY", 1.0)
    MAX_CONTEXT_TOKENS: int = config_value("agent", "MAX_CONTEXT_TOKENS", 256000)
    MAX_CONCURRENT_TOOLS: int = config_value("agent", "MAX_CONCURRENT_TOOLS", 10)
    MAX_CONCURRENT_REQUESTS: int = config_value("agent", "MAX_CONCURRENT_REQUESTS", 20)
    TOOL_TIMEOUT: float = config_value("agent", "TOOL_TIMEOUT", 60.0)
    GUIDED_TOOLS: str = config_value("agent", "GUIDED_TOOLS", "")
    BUILTIN_TOOLS: str = config_value("agent", "BUILTIN_TOOLS", "filesystem.read,filesystem.list")
    SANDBOX_PROFILE: str = config_value("agent", "SANDBOX_PROFILE", "restricted")
    SANDBOX_PROVIDER: str = config_value("agent", "SANDBOX_PROVIDER", "local")
    SANDBOX_IMAGE: str = config_value("agent", "SANDBOX_IMAGE", "python:3.12-slim")
    SANDBOX_NETWORK: str = config_value("agent", "SANDBOX_NETWORK", "")
    SANDBOX_MEMORY: str = config_value("agent", "SANDBOX_MEMORY", "")
    SANDBOX_CPUS: str = config_value("agent", "SANDBOX_CPUS", "")
    SANDBOX_TTL_SECONDS: int = config_value("agent", "SANDBOX_TTL_SECONDS", 0)
    SANDBOX_WORKDIR: str = config_value("agent", "SANDBOX_WORKDIR", "/workspace")
    SANDBOX_ALLOW_FILE_WRITE: bool | None = config_value("agent", "SANDBOX_ALLOW_FILE_WRITE", None)
    SANDBOX_ALLOW_PROCESS: bool | None = config_value("agent", "SANDBOX_ALLOW_PROCESS", None)
    SANDBOX_ALLOW_NETWORK: bool | None = config_value("agent", "SANDBOX_ALLOW_NETWORK", None)
    SANDBOX_ALLOWED_COMMANDS: str = config_value("agent", "SANDBOX_ALLOWED_COMMANDS", "")
    MEMORY_CONTEXT_LIMIT: int = config_value("agent", "MEMORY_CONTEXT_LIMIT", 20)
    CONTEXT_COMPACTION_TARGET_TOKENS: int = config_value("agent", "CONTEXT_COMPACTION_TARGET_TOKENS", 32000)

    # Claude provider 的备选配置（优先级高于 ANTHROPIC_*）
    CLAUDE_API_KEY: str = ""
    CLAUDE_BASE_URL: str = config_value("agent", "CLAUDE_BASE_URL", "")
    CLAUDE_MODEL: str = config_value("agent", "CLAUDE_MODEL", "")


agent_config = AgentConfig()
