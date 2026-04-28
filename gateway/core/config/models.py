from pydantic_settings import BaseSettings, SettingsConfigDict

from gateway.core.config._constants import ENV_FILE
from gateway.core.config.loader import config_value


class OpenAIConfig(BaseSettings):
    """OpenAI Chat Completions API 配置。"""

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
    """OpenAI Responses API 配置。"""

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
    """Anthropic Claude API 配置。"""

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
    """Google Gemini API 配置。"""

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
    """聚合所有模型提供商配置。"""

    def __init__(self):
        self.openai = OpenAIConfig()
        self.openai_responses = OpenAIResponsesConfig()
        self.anthropic = AnthropicConfig()
        self.gemini = GeminiConfig()


models_config = ModelConfigs()
