from __future__ import annotations

from typing import Any, List

from app.agent.hooks.base import AgentHooks
from app.agent.hooks.composite import CompositeHooks
from app.agent.hooks.guidance import IntentGuide, IntentGuidanceHooks


def hooks_from_settings(settings: Any) -> AgentHooks:
    """根据配置创建默认的 AgentHooks 组合。

    当前支持::

        AGENT_GUIDED_TOOLS="weather:查天气,查温度;search:搜索,查找"
    """
    active_hooks: List[AgentHooks] = []

    guides = _parse_guided_tools(getattr(settings.agent, "GUIDED_TOOLS", ""))
    if guides:
        active_hooks.append(IntentGuidanceHooks(guides))

    if not active_hooks:
        return AgentHooks()
    if len(active_hooks) == 1:
        return active_hooks[0]
    return CompositeHooks(active_hooks)


def _parse_guided_tools(raw: str) -> List[IntentGuide]:
    """解析 GUIDED_TOOLS 配置字符串。

    格式: ``tool_name:kw1,kw2;tool_name2:kw3,kw4``

    示例: ``weather:天气,温度;search:搜索,查找``
    """
    guides: List[IntentGuide] = []
    if not raw:
        return guides

    for segment in raw.split(";"):
        segment = segment.strip()
        if not segment:
            continue
        if ":" not in segment:
            continue
        tool_name, keywords_str = segment.split(":", 1)
        tool_name = tool_name.strip()
        keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
        if tool_name and keywords:
            guides.append(
                IntentGuide(
                    keywords=keywords,
                    tool_name=tool_name,
                    prompt=f"你可以使用 {tool_name} 工具来完成这个任务。",
                )
            )

    return guides
