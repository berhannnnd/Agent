# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：__init__.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

__all__ = [
    "AgentConfigError",
    "AgentModelSpec",
    "AgentSpec",
    "AgentRuntime",
    "AgentSession",
    "WorkspaceRef",
    "create_agent_session",
    "create_agent_session_async",
]


def __getattr__(name):
    if name in {"create_agent_session", "create_agent_session_async"}:
        from agent import assembly

        return getattr(assembly, name)
    if name == "AgentConfigError":
        from agent.config import AgentConfigError

        return AgentConfigError
    if name in {"AgentModelSpec", "AgentSpec", "WorkspaceRef"}:
        from agent import definitions

        return getattr(definitions, name)
    if name in {"AgentRuntime", "AgentSession"}:
        from agent import runtime

        return getattr(runtime, name)
    raise AttributeError(name)
