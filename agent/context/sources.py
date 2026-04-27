from __future__ import annotations

from typing import Iterable, List

from agent.context.pack import ContextFragment, ContextLayer, ContextPack, ContextScope
from agent.context.workspace import WorkspaceContext
from agent.skills import SkillRegistry


def build_context_pack(
    *,
    system_prompt: str,
    skill_registry: SkillRegistry,
    enabled_tools: Iterable[str],
    workspace: WorkspaceContext,
    memory_fragments: Iterable[ContextFragment] = (),
) -> ContextPack:
    fragments: List[ContextFragment] = []
    fragments.extend(_system_fragments(system_prompt))
    fragments.extend(_runtime_policy_fragments())
    fragments.extend(_workspace_instruction_fragments(workspace))
    fragments.extend(_skill_fragments(skill_registry))
    fragments.extend(memory_fragments)
    fragments.extend(_tool_hint_fragments(enabled_tools))
    return ContextPack.of(fragments)


def _system_fragments(system_prompt: str) -> List[ContextFragment]:
    text = str(system_prompt or "").strip()
    if not text:
        return []
    return [
        ContextFragment(
            id="system.user_configured",
            layer=ContextLayer.SYSTEM,
            text=text,
            source="settings.agent.SYSTEM_PROMPT",
            priority=100,
            scope=ContextScope.SESSION,
        )
    ]


def _runtime_policy_fragments() -> List[ContextFragment]:
    return [
        ContextFragment(
            id="runtime.tool_contract",
            layer=ContextLayer.RUNTIME_POLICY,
            text=(
                "Use tools only when they are needed. Do not invent tool results. "
                "If a tool is denied, failed, or timed out, continue from the returned tool result."
            ),
            source="agent.runtime",
            priority=100,
            scope=ContextScope.GLOBAL,
        )
    ]


def _workspace_instruction_fragments(workspace: WorkspaceContext) -> List[ContextFragment]:
    fragments: List[ContextFragment] = []
    for path in workspace.instruction_files():
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        fragments.append(
            ContextFragment(
                id="workspace.%s" % path.stem.lower(),
                layer=ContextLayer.PROJECT_INSTRUCTIONS,
                text=text,
                source=str(path),
                priority=80,
                scope=ContextScope.PROJECT,
            )
        )
    return fragments


def _skill_fragments(skill_registry: SkillRegistry) -> List[ContextFragment]:
    fragments: List[ContextFragment] = []
    for skill in skill_registry.skills:
        for index, text in enumerate(skill.prompt_fragments):
            fragments.append(
                ContextFragment(
                    id="skill.%s.%s" % (skill.name, index),
                    layer=ContextLayer.SKILLS,
                    text=text,
                    source="skill:%s" % skill.name,
                    priority=60,
                    scope=ContextScope.SESSION,
                )
            )
    return fragments


def _tool_hint_fragments(enabled_tools: Iterable[str]) -> List[ContextFragment]:
    names = [name for name in enabled_tools if name]
    if not names:
        return []
    return [
        ContextFragment(
            id="tools.enabled",
            layer=ContextLayer.TOOL_HINTS,
            text="Enabled tools for this session: %s." % ", ".join(names),
            source="agent.integrations",
            priority=40,
            scope=ContextScope.TOOL,
        )
    ]
