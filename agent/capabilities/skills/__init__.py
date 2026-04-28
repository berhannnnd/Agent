# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：skills.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class SkillManifest:
    name: str
    version: str = "0.1.0"
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    prompt_fragments: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillDependencyError(ValueError):
    """Raised when skill dependency resolution fails."""


class SkillLoader:
    def __init__(self, root: Path):
        self.root = Path(root)

    def load(self, name: str, context: Optional[Dict[str, Any]] = None) -> SkillManifest:
        manifest_path = self.root / "skills" / ("%s.json" % name)
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        render_context = context or {}
        fragments = []
        for relative_path in raw.get("prompt_fragments", []):
            text = (self.root / relative_path).read_text(encoding="utf-8")
            fragments.append(text.format(**render_context).strip())
        return SkillManifest(
            name=raw["name"],
            version=raw.get("version", "0.1.0"),
            description=raw.get("description", ""),
            dependencies=list(raw.get("dependencies", raw.get("requires", []))),
            prompt_fragments=fragments,
            tools=list(raw.get("tools", [])),
            metadata=dict(raw.get("metadata", {})),
        )


class SkillRegistry:
    def __init__(self, skills: Iterable[SkillManifest]):
        self.skills = list(skills)

    @classmethod
    def load(cls, loader: SkillLoader, names: Iterable[str], context: Optional[Dict[str, Any]] = None) -> "SkillRegistry":
        ordered: List[SkillManifest] = []
        resolved = set()
        visiting: List[str] = []

        def visit(name: str) -> None:
            if name in resolved:
                return
            if name in visiting:
                raise SkillDependencyError("skill dependency cycle: %s" % " -> ".join(visiting + [name]))
            visiting.append(name)
            skill = loader.load(name, context=context)
            for dependency in skill.dependencies:
                visit(dependency)
            visiting.pop()
            resolved.add(skill.name)
            ordered.append(skill)

        for name in names:
            visit(name)
        return cls(ordered)

    def names(self) -> List[str]:
        return [skill.name for skill in self.skills]

    def prompt_text(self) -> str:
        return "\n\n".join(fragment for skill in self.skills for fragment in skill.prompt_fragments if fragment)

    def tool_names(self) -> List[str]:
        names: List[str] = []
        seen = set()
        for skill in self.skills:
            for tool_name in skill.tools:
                if tool_name not in seen:
                    seen.add(tool_name)
                    names.append(tool_name)
        return names
