from __future__ import annotations

import os

from pydantic_settings import BaseSettings, SettingsConfigDict

from agent.config.loader import config_value
from agent.config.paths import ENV_FILE


class AgentConfig(BaseSettings):
    """Agent runtime defaults shared by CLI and gateway."""

    model_config = SettingsConfigDict(
        env_file=os.path.abspath(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="AGENT_",
    )

    PROTOCOL: str = config_value("agent", "PROTOCOL", "openai-chat")
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
    WORKSPACE_LAYOUT: str = config_value("agent", "WORKSPACE_LAYOUT", "auto")
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

    # Claude-compatible protocol fallback config; higher priority than ANTHROPIC_*.
    CLAUDE_API_KEY: str = ""
    CLAUDE_BASE_URL: str = config_value("agent", "CLAUDE_BASE_URL", "")
    CLAUDE_MODEL: str = config_value("agent", "CLAUDE_MODEL", "")


class OpenAIConfig(BaseSettings):
    """OpenAI Chat Completions API configuration."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="OPENAI_",
    )

    API_KEY: str = ""
    BASE_URL: str = config_value("models.openai", "BASE_URL", "https://api.openai.com/v1")
    MODEL: str = config_value("models.openai", "MODEL", "")


class OpenAIResponsesConfig(BaseSettings):
    """OpenAI Responses API configuration."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="OPENAI_RESPONSES_",
    )

    API_KEY: str = ""
    BASE_URL: str = config_value("models.openai_responses", "BASE_URL", "https://api.openai.com/v1")
    MODEL: str = config_value("models.openai_responses", "MODEL", "")


class AnthropicConfig(BaseSettings):
    """Claude Messages-compatible API configuration."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="ANTHROPIC_",
    )

    API_KEY: str = ""
    BASE_URL: str = config_value("models.anthropic", "BASE_URL", "https://api.anthropic.com/v1")
    MODEL: str = config_value("models.anthropic", "MODEL", "")


class GeminiConfig(BaseSettings):
    """Google Gemini API configuration."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="GEMINI_",
    )

    API_KEY: str = ""
    BASE_URL: str = config_value("models.gemini", "BASE_URL", "https://generativelanguage.googleapis.com/v1")
    MODEL: str = config_value("models.gemini", "MODEL", "")


class ModelConfigs:
    """Aggregated model protocol configuration."""

    def __init__(self):
        self.openai = OpenAIConfig()
        self.openai_responses = OpenAIResponsesConfig()
        self.anthropic = AnthropicConfig()
        self.gemini = GeminiConfig()


class MCPConfig(BaseSettings):
    """Model Context Protocol configuration shared by local and hosted entrypoints."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="MCP_",
    )

    SERVER_NAME: str = config_value("mcp", "SERVER_NAME", "")
    SERVER_COMMAND: str = config_value("mcp", "SERVER_COMMAND", "")
    CLIENT_TIMEOUT: float = config_value("mcp", "CLIENT_TIMEOUT", 30.0)
    EXECUTION_MODE: str = config_value("mcp", "EXECUTION_MODE", "trusted_control_plane")
    SANDBOX_PROFILE: str = config_value("mcp", "SANDBOX_PROFILE", "")


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


class RuntimeSettings:
    """Shared non-HTTP settings consumed by the agent SDK and local CLI."""

    def __init__(self):
        self.agent = AgentConfig()
        self.models = ModelConfigs()
        self.mcp = MCPConfig()
        self.web_search = WebSearchConfig()


agent_config = AgentConfig()
models_config = ModelConfigs()
mcp_config = MCPConfig()
web_search_config = WebSearchConfig()
runtime_settings = RuntimeSettings()
