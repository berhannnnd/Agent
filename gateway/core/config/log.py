import os

from pydantic_settings import BaseSettings, SettingsConfigDict

from gateway.core.config._constants import ENV_FILE
from gateway.core.config.loader import config_value
from gateway.utils.terminal import TermColors


class LogConfig(BaseSettings):
    """日志配置。"""

    model_config = SettingsConfigDict(
        env_file=os.path.abspath(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    LOG_LEVEL: str = config_value("log", "LOG_LEVEL", "INFO")
    LOG_PATH: str = os.path.abspath(os.path.join(os.getcwd(), "logs"))
    LOGGER_FORMAT: str = (
        f"{TermColors.WHITE}[ {TermColors.GRAY}%(asctime)s {TermColors.WHITE}]"
        f"{TermColors.MAGENTA} %(levelname)-7s {TermColors.WHITE}| "
        f"{TermColors.CYAN}%(filename)s %(lineno)4d {TermColors.WHITE} - "
        f"{TermColors.GREEN}%(message)s{TermColors.WHITE}"
    )

    def update_dependent_settings(self) -> None:
        self.LOG_PATH = os.path.abspath(self.LOG_PATH)


log_config = LogConfig()
