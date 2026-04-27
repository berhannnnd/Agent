# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：test_health.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from fastapi.testclient import TestClient

from app.app import create_app


def test_health():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["status"] == "ok"
