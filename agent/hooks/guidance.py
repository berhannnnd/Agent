from __future__ import annotations

from dataclasses import dataclass
from typing import List

from agent.hooks.base import AgentHooks
from agent.schema import Message


@dataclass(frozen=True)
class IntentGuide:
    """意图引导规则。

    当用户消息匹配任意关键词时，在对话中插入引导提示，
    建议模型使用指定工具。
    """

    keywords: List[str]
    tool_name: str
    prompt: str


class IntentGuidanceHooks(AgentHooks):
    """基于意图识别的工具引导 Hook。

    示例::

        hooks = IntentGuidanceHooks([
            IntentGuide(
                keywords=["天气", "temperature"],
                tool_name="weather",
                prompt="你可以使用 weather 工具查询天气信息。",
            ),
        ])
    """

    def __init__(self, guides: List[IntentGuide]):
        self.guides = guides

    async def before_request(self, messages: List[Message]) -> List[Message]:
        if not messages or not self.guides:
            return messages

        last_user_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].role == "user":
                last_user_idx = i
                break

        if last_user_idx < 0:
            return messages

        user_text = messages[last_user_idx].content_text().lower()

        for guide in self.guides:
            if not any(kw.lower() in user_text for kw in guide.keywords):
                continue

            # 避免重复插入：检查该 user 消息后是否已有相同引导
            if last_user_idx + 1 < len(messages):
                next_text = messages[last_user_idx + 1].content_text()
                if guide.tool_name in next_text:
                    break

            new_messages = list(messages)
            new_messages.insert(
                last_user_idx + 1,
                Message.from_text("user", guide.prompt),
            )
            return new_messages

        return messages


class SystemPromptGuidanceHooks(AgentHooks):
    """动态追加 system prompt 引导的 Hook。

    在每条请求前，根据最近的用户消息动态追加一段 system 提示，
    不会重复追加已存在的提示。
    """

    def __init__(self, guidance_provider):
        self.guidance_provider = guidance_provider
        _sentinel = []
        self._last_guidance = _sentinel

    async def before_request(self, messages: List[Message]) -> List[Message]:
        if not messages:
            return messages

        guidance = await self.guidance_provider(messages)
        if not guidance or guidance == self._last_guidance:
            return messages
        self._last_guidance = guidance

        new_messages = []
        system_appended = False
        for msg in messages:
            new_messages.append(msg)
            if msg.role == "system" and not system_appended:
                new_messages.append(Message.from_text("system", guidance))
                system_appended = True

        if not system_appended:
            new_messages.insert(0, Message.from_text("system", guidance))

        return new_messages
