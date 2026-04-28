# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：diagnostics.py
# @Date   ：2026/04/27 00:00
# @Author ：Zegen
#
# 2026/04/27   Create
# =====================================================

from gateway.core.config._constants import logo
from agent.config.settings import agent_config
from agent.config.settings import mcp_config
from agent.config.settings import models_config
from agent.config.settings import web_search_config
from gateway.core.config.log import log_config
from gateway.core.config.server import server_config


class Settings:
    """统一配置入口。各域配置独立管理，避免命名冲突。"""

    def __init__(self):
        self.server = server_config
        self.agent = agent_config
        self.models = models_config
        self.mcp = mcp_config
        self.web_search = web_search_config
        self.log = log_config

    @property
    def LOGO(self) -> str:
        return logo

    def update_dependent_settings(self) -> None:
        self.server.update_dependent_settings()
        self.log.update_dependent_settings()

    def status(self, logger) -> None:
        self.update_dependent_settings()
        logger.info("USE: %s", self.__class__.__name__)
        for name, config in [
            ("server", self.server),
            ("agent", self.agent),
            ("models.openai", self.models.openai),
            ("models.openai_responses", self.models.openai_responses),
            ("models.anthropic", self.models.anthropic),
            ("models.gemini", self.models.gemini),
            ("mcp", self.mcp),
            ("web_search", self.web_search),
            ("log", self.log),
        ]:
            for attr in sorted(config.__class__.model_fields):
                if attr == "LOGO":
                    continue
                logger.info("  %s.%s: %s", name, attr, self._display_value(attr, getattr(config, attr)))

    @staticmethod
    def _display_value(name: str, value):
        normalized = name.upper()
        secret_markers = ("API_KEY", "ACCESS_TOKEN", "SECRET", "PASSWORD", "PASSWD")
        if normalized.endswith("_KEY") or any(marker in normalized for marker in secret_markers):
            return "********" if value else value
        return value


settings = Settings()

__all__ = ["settings", "Settings"]
