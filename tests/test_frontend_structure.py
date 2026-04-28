# !/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path


FRONTEND_SRC = Path("web/src")


def test_frontend_is_split_into_focused_modules():
    expected_modules = {
        "App.tsx",
        "components/ActionTimeline.tsx",
        "components/ChatThread.tsx",
        "components/SettingsDrawer.tsx",
        "runtime/agentSession.ts",
        "types.ts",
    }

    for module in expected_modules:
        assert (FRONTEND_SRC / module).is_file(), module


def test_frontend_source_files_stay_small():
    oversized = []
    for path in FRONTEND_SRC.rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".css"}:
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > 260:
            oversized.append(f"{path}: {line_count}")

    assert oversized == []


def test_action_timeline_language_is_product_visible():
    timeline = (FRONTEND_SRC / "components/ActionTimeline.tsx").read_text(encoding="utf-8")

    assert "Agent activity" in timeline
    assert "Tool call" in timeline
    assert "Code execution" in timeline
    assert "Web search" in timeline


def test_tool_approval_panel_exposes_scoped_decisions():
    panel = (FRONTEND_SRC / "components/ToolApprovalPanel.tsx").read_text(encoding="utf-8")

    assert "allow_once" in panel
    assert "allow_for_run" in panel
    assert "Allow once" in panel
    assert "Allow for run" in panel
