from __future__ import annotations

from typing import Any, Iterable, List, Optional

from agent.skills import SkillLoader, SkillRegistry


def load_configured_skills(settings: Any, skill_names: Optional[Iterable[str]] = None) -> SkillRegistry:
    names = list(skill_names) if skill_names is not None else _csv_setting(settings.agent.SKILLS)
    skill_names = [name for name in names if name]
    if not skill_names:
        return SkillRegistry([])
    return SkillRegistry.load(SkillLoader(settings.server.ROOT_PATH), skill_names)


def resolve_active_tools(
    settings: Any,
    skill_registry: SkillRegistry,
    enabled_tools: Optional[List[str]] = None,
) -> List[str]:
    if enabled_tools is not None:
        return list(enabled_tools)
    return _merge_unique(_csv_setting(settings.agent.ENABLED_TOOLS), skill_registry.tool_names())


def _csv_setting(raw: str) -> List[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _merge_unique(*groups: List[str]) -> List[str]:
    names: List[str] = []
    seen = set()
    for group in groups:
        for name in group:
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names
