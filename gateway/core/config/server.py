import os
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from gateway.core.config._constants import ENV_FILE, ROOT_PATH


class ServerConfig(BaseSettings):
    """服务器与 HTTP 配置。"""

    model_config = SettingsConfigDict(
        env_file=os.path.abspath(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DEBUG: bool = False
    PROJECT_NAME: str = "Agents"
    API_PREFIX: str = "/api"
    SERVER_TYPE: str = "uvicorn"
    HOST: str = "0.0.0.0"
    PORT: int = 8010
    WORKERS: int = 1
    DOMAIN: str = "http://localhost:8010"
    ENABLE_ENGINES: bool = True
    ENABLE_SWAGGER_DOC: bool = False
    BACKEND_CORS_ORIGINS: list[str] = ["*"]
    ACCESS_TOKEN: Optional[str] = None
    CACHE_FILE_DIR: str = os.path.abspath(os.path.join(os.getcwd(), "cache"))
    ROOT_PATH: str = ROOT_PATH

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_mode(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"debug", "dev", "development"}:
                return True
        return value

    def update_dependent_settings(self) -> None:
        self.CACHE_FILE_DIR = os.path.abspath(self.CACHE_FILE_DIR)
        self.DOMAIN = f"http://localhost:{self.PORT}"


server_config = ServerConfig()
