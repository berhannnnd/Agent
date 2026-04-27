# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：test_branding.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from pathlib import Path

from app.core.config import settings


ROOT = Path(__file__).resolve().parents[1]
BRAND_FILES = [
    "README.md",
    "pyproject.toml",
    ".env.example",
    "deploy/docker-compose.yml",
    "_inventory/migration-map.tsv",
]


def test_visible_branding_uses_agents_not_aibox():
    assert settings.server.PROJECT_NAME == "Agents"
    assert "Agents" in settings.LOGO

    for relative_path in BRAND_FILES:
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "AIBOX" not in content
        assert "Aibox" not in content
        assert "AIBox" not in content


def test_settings_status_redacts_secret_values():
    class FakeLogger:
        def __init__(self):
            self.lines = []

        def info(self, message, *args):
            self.lines.append(message % args if args else message)

    logger = FakeLogger()
    original = settings.models.openai.API_KEY
    settings.models.openai.API_KEY = "secret-key"
    try:
        settings.status(logger)
    finally:
        settings.models.openai.API_KEY = original

    output = "\n".join(logger.lines)
    assert "models.openai.API_KEY: ********" in output
    assert "secret-key" not in output
