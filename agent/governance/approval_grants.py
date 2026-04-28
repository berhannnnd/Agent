from __future__ import annotations

import hashlib
import json
from typing import Any

from agent.schema import ToolCall

APPROVAL_ALLOW_ONCE = "allow_once"
APPROVAL_ALLOW_FOR_RUN = "allow_for_run"
APPROVAL_DENY = "deny"

APPROVAL_DECISIONS = {APPROVAL_ALLOW_ONCE, APPROVAL_ALLOW_FOR_RUN, APPROVAL_DENY}


def normalize_approval_decision(raw: Any = None, approved: bool = True) -> str:
    if raw is None:
        return APPROVAL_ALLOW_ONCE if approved else APPROVAL_DENY
    if isinstance(raw, bool):
        return APPROVAL_ALLOW_ONCE if raw else APPROVAL_DENY
    value = str(raw).strip().lower().replace("-", "_")
    aliases = {
        "allow": APPROVAL_ALLOW_ONCE,
        "approve": APPROVAL_ALLOW_ONCE,
        "approved": APPROVAL_ALLOW_ONCE,
        "once": APPROVAL_ALLOW_ONCE,
        "run": APPROVAL_ALLOW_FOR_RUN,
        "allow_run": APPROVAL_ALLOW_FOR_RUN,
        "allow_for_session": APPROVAL_ALLOW_FOR_RUN,
        "deny_once": APPROVAL_DENY,
        "reject": APPROVAL_DENY,
        "rejected": APPROVAL_DENY,
        "denied": APPROVAL_DENY,
    }
    decision = aliases.get(value, value)
    if decision not in APPROVAL_DECISIONS:
        raise ValueError("unknown approval decision: %s" % raw)
    return decision


def approval_is_allowed(decision: str) -> bool:
    return decision != APPROVAL_DENY


def approval_grant_key(call: ToolCall) -> str:
    payload = {
        "name": call.name,
        "arguments": call.arguments,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "tool:%s" % hashlib.sha256(encoded).hexdigest()
