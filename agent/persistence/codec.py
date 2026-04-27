from __future__ import annotations

import json
from typing import Any


def json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def json_dict(value: str | None) -> dict:
    payload = json.loads(value or "{}")
    return dict(payload) if isinstance(payload, dict) else {}


def json_list(value: str | None) -> list:
    payload = json.loads(value or "[]")
    return list(payload) if isinstance(payload, list) else []
