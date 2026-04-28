from pydantic_settings import BaseSettings, SettingsConfigDict

from gateway.core.config._constants import ENV_FILE
from gateway.core.config.loader import config_value


class MCPConfig(BaseSettings):
    """MCP (Model Context Protocol) 配置。"""

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


mcp_config = MCPConfig()
