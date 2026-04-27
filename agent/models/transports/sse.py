import json
from typing import Any, Dict, Optional


def parse_sse_json_line(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line or line.startswith(":"):
        return None
    if line.startswith("data:"):
        line = line[len("data:") :].strip()
    elif ":" in line:
        return None
    if line == "[DONE]":
        return None
    return json.loads(line)
