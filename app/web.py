# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：web.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.utils import utils

UI_STATIC_DIR = Path(utils.ROOT_PATH) / "web" / "dist"


def register_web_ui(application: FastAPI) -> None:
    """Mount the API test console if the frontend has been built."""
    if not UI_STATIC_DIR.exists():
        return

    @application.get("/", include_in_schema=False)
    async def api_console_root():
        return RedirectResponse("/ui/")

    application.mount(
        "/ui",
        StaticFiles(directory=str(UI_STATIC_DIR), html=True),
        name="api-console",
    )
