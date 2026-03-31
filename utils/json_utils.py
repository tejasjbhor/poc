import json
from typing import Any

import re


def coerce_json(text: str) -> Any:
    """Extract/parse JSON from an LLM response, tolerating markdown fences."""
    raw = (text or "").strip()
    raw = re.sub(r"^```json\s*|^```\s*|```$", "", raw).strip()
    try:
        return json.loads(raw)
    except Exception:
        # Fallback: extract the first JSON object/array in the string.
        m = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", raw)
        if not m:
            raise
        return json.loads(m.group())
