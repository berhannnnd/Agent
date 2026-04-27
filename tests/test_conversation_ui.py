# !/usr/bin/env python
# -*- coding: utf-8 -*-

from fastapi.testclient import TestClient

from app.app import create_app


def test_root_redirects_to_conversation_ui():
    client = TestClient(create_app(), follow_redirects=False)

    response = client.get("/")

    assert response.status_code == 307
    assert response.headers["location"] == "/ui/"


def test_conversation_ui_entrypoint_is_served():
    client = TestClient(create_app())

    response = client.get("/ui/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Agents Conversation Studio" in response.text
    assert 'id="root"' in response.text
