from __future__ import annotations

from typing import Iterable, List

from agent.context.pack import CompiledContext, ContextFragment, ContextLayer, ContextPack, ContextTraceItem


_LAYER_ORDER = {
    ContextLayer.SYSTEM: 0,
    ContextLayer.RUNTIME_POLICY: 10,
    ContextLayer.PROJECT_INSTRUCTIONS: 20,
    ContextLayer.SKILLS: 30,
    ContextLayer.MEMORY: 40,
    ContextLayer.TOOL_HINTS: 50,
    ContextLayer.TASK_CONTEXT: 60,
}

_REQUIRED_LAYERS = {
    ContextLayer.SYSTEM,
    ContextLayer.RUNTIME_POLICY,
    ContextLayer.PROJECT_INSTRUCTIONS,
}


class ContextBuilder:
    def compile(self, pack: ContextPack, budget_tokens: int | None = None) -> CompiledContext:
        fragments = _sort_fragments(pack.fragments)
        included: List[ContextFragment] = []
        trace: List[ContextTraceItem] = []
        total_tokens = 0

        for fragment in fragments:
            tokens = fragment.token_count()
            over_budget = budget_tokens is not None and total_tokens + tokens > budget_tokens
            if over_budget and fragment.layer not in _REQUIRED_LAYERS:
                trace.append(_trace(fragment, tokens, included=False, reason="budget"))
                continue
            included.append(fragment)
            total_tokens += tokens
            reason = "required_over_budget" if over_budget else ""
            trace.append(_trace(fragment, tokens, included=True, reason=reason))

        return CompiledContext(
            system_text="\n\n".join(_render_fragment(fragment) for fragment in included),
            trace=trace,
            token_estimate=total_tokens,
        )


def _sort_fragments(fragments: Iterable[ContextFragment]) -> List[ContextFragment]:
    return sorted(
        [fragment for fragment in fragments if fragment.enabled and fragment.text.strip()],
        key=lambda fragment: (_LAYER_ORDER[fragment.layer], -fragment.priority, fragment.id),
    )


def _render_fragment(fragment: ContextFragment) -> str:
    header = "## %s: %s" % (fragment.layer.value, fragment.id)
    return "%s\n%s" % (header, fragment.text.strip())


def _trace(fragment: ContextFragment, tokens: int, included: bool, reason: str = "") -> ContextTraceItem:
    return ContextTraceItem(
        id=fragment.id,
        layer=fragment.layer,
        source=fragment.source,
        tokens=tokens,
        included=included,
        reason=reason,
    )
