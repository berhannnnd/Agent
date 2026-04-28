from pydantic_settings import BaseSettings, SettingsConfigDict

from gateway.core.config._constants import ENV_FILE


class MCPConfig(BaseSettings):
    """MCP (Model Context Protocol) 配置。"""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="MCP_",
    )

    SERVER_NAME: str = ""
    SERVER_COMMAND: str = ""
    CLIENT_TIMEOUT: float = 30.0
    EXECUTION_MODE: str = "trusted_control_plane"
    SANDBOX_PROFILE: str = ""


mcp_config = MCPConfig()
