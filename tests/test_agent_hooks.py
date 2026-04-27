# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：test_agent_hooks.py
# @Date   ：2026/04/27 00:00
# @Author ：Zegen
#
# 2026/04/27   Create
# =====================================================

import asyncio

import pytest

from app.agent.hooks import (
    AgentHooks,
    ApprovalHooks,
    CompositeHooks,
    IntentGuide,
    IntentGuidanceHooks,
    SystemPromptGuidanceHooks,
    ThinkingHooks,
    ToolApprovalError,
)
from app.agent.schema import Message, ModelResponse, ToolCall


class TestIntentGuidanceHooks:
    def test_inserts_guidance_when_keyword_matches(self):
        hooks = IntentGuidanceHooks([
            IntentGuide(keywords=["天气"], tool_name="weather", prompt="你可以使用 weather 工具。"),
        ])
        messages = [Message.from_text("user", "今天天气怎么样？")]

        result = asyncio.run(hooks.before_request(messages))

        assert len(result) == 2
        assert result[1].content_text() == "你可以使用 weather 工具。"

    def test_no_insert_when_no_match(self):
        hooks = IntentGuidanceHooks([
            IntentGuide(keywords=["天气"], tool_name="weather", prompt="你可以使用 weather 工具。"),
        ])
        messages = [Message.from_text("user", "你好")]

        result = asyncio.run(hooks.before_request(messages))

        assert len(result) == 1

    def test_no_duplicate_guidance(self):
        hooks = IntentGuidanceHooks([
            IntentGuide(keywords=["天气"], tool_name="weather", prompt="你可以使用 weather 工具。"),
        ])
        messages = [
            Message.from_text("user", "今天天气怎么样？"),
            Message.from_text("user", "你可以使用 weather 工具。"),
        ]

        result = asyncio.run(hooks.before_request(messages))

        assert len(result) == 2


class TestSystemPromptGuidanceHooks:
    def test_appends_guidance_after_existing_system(self):
        async def provider(messages):
            return "请使用中文回答。"

        hooks = SystemPromptGuidanceHooks(provider)
        messages = [
            Message.from_text("system", "You are a helpful assistant."),
            Message.from_text("user", "hi"),
        ]

        result = asyncio.run(hooks.before_request(messages))

        assert len(result) == 3
        assert result[1].role == "system"
        assert result[1].content_text() == "请使用中文回答。"

    def test_inserts_system_at_front_when_none_exists(self):
        async def provider(messages):
            return "Be concise."

        hooks = SystemPromptGuidanceHooks(provider)
        messages = [Message.from_text("user", "hi")]

        result = asyncio.run(hooks.before_request(messages))

        assert result[0].role == "system"
        assert result[0].content_text() == "Be concise."

    def test_skips_duplicate_guidance(self):
        async def provider(messages):
            return "Same guidance."

        hooks = SystemPromptGuidanceHooks(provider)
        messages = [Message.from_text("user", "hi")]

        result1 = asyncio.run(hooks.before_request(messages))
        result2 = asyncio.run(hooks.before_request(result1))

        assert len(result2) == len(result1)


class TestThinkingHooks:
    def test_extracts_thinking_from_raw(self):
        captured = []
        hooks = ThinkingHooks(on_thinking=captured.append)
        response = ModelResponse(
            message=Message.from_text("assistant", "answer"),
            raw={"reasoning_content": "Let me think..."},
        )

        result = asyncio.run(hooks.after_response(response))

        assert captured == ["Let me think..."]
        assert result.message.content_text() == "answer"

    def test_no_thinking_when_raw_empty(self):
        captured = []
        hooks = ThinkingHooks(on_thinking=captured.append)
        response = ModelResponse(message=Message.from_text("assistant", "answer"))

        asyncio.run(hooks.after_response(response))

        assert captured == []


class TestApprovalHooks:
    def test_allows_approved_tools(self):
        hooks = ApprovalHooks(should_approve=lambda name, args: name != "dangerous")
        response = ModelResponse(
            message=Message.from_text(
                "assistant",
                "",
                tool_calls=[ToolCall(id="1", name="safe", arguments={})],
            )
        )

        result = asyncio.run(hooks.after_response(response))

        assert result.message.tool_calls[0].name == "safe"

    def test_rejects_unapproved_tools(self):
        hooks = ApprovalHooks(should_approve=lambda name, args: name != "dangerous")
        response = ModelResponse(
            message=Message.from_text(
                "assistant",
                "",
                tool_calls=[ToolCall(id="1", name="dangerous", arguments={})],
            )
        )

        with pytest.raises(ToolApprovalError) as exc_info:
            asyncio.run(hooks.after_response(response))

        assert exc_info.value.tool_name == "dangerous"


class TestCompositeHooks:
    def test_chains_before_request(self):
        class AddSystemHook(AgentHooks):
            async def before_request(self, messages):
                return [Message.from_text("system", "sys")] + messages

        class AddUserHook(AgentHooks):
            async def before_request(self, messages):
                return messages + [Message.from_text("user", "extra")]

        composite = CompositeHooks([AddSystemHook(), AddUserHook()])
        messages = [Message.from_text("user", "hi")]

        result = asyncio.run(composite.before_request(messages))

        assert [m.role for m in result] == ["system", "user", "user"]

    def test_uses_last_hook_for_format_tool_result(self):
        class UppercaseHook(AgentHooks):
            def format_tool_result(self, result):
                return Message.from_text("tool", result.content.upper())

        composite = CompositeHooks([AgentHooks(), UppercaseHook()])
        from app.agent.schema import ToolResult

        result = composite.format_tool_result(ToolResult(tool_call_id="1", name="echo", content="hi"))

        assert result.content_text() == "HI"

    def test_first_on_error_recovery_wins(self):
        class RecoveryHook(AgentHooks):
            async def on_error(self, error, messages):
                from app.agent.runtime import AgentResult
                return AgentResult(content="recovered", messages=messages)

        composite = CompositeHooks([AgentHooks(), RecoveryHook()])

        result = asyncio.run(composite.on_error(ValueError("boom"), []))

        assert result is not None
        assert result.content == "recovered"
