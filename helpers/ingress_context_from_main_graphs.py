from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping

from registeries.observable_workflows import get_observable_graph_map


def _message_to_dict(msg: Any) -> dict[str, Any]:
    role = getattr(msg, "type", "") or ""
    content = getattr(msg, "content", "")
    if hasattr(content, "text"):
        content = content.text
    out: dict[str, Any] = {"role": role, "content": str(content) if content is not None else ""}
    ak = getattr(msg, "additional_kwargs", None) or {}
    if isinstance(ak, dict) and ak.get("agent"):
        out["agent"] = ak["agent"]
    return out


def json_safe_value(value: Any, depth: int = 0) -> Any:
    if depth > 24:
        return "<max_depth>"
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    mod = type(value).__module__ or ""
    name = type(value).__name__
    if mod.startswith("langchain_core.messages") or name in (
        "HumanMessage",
        "AIMessage",
        "SystemMessage",
        "BaseMessage",
    ):
        return _message_to_dict(value)
    if isinstance(value, Mapping):
        return {
            str(k): json_safe_value(v, depth + 1) for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [json_safe_value(v, depth + 1) for v in value]
    return str(value)[:8000]


def json_safe_state(values: dict[str, Any]) -> dict[str, Any]:
    return {str(k): json_safe_value(v) for k, v in values.items()}


async def aget_checkpoint_json(graph: Any, thread_id: str) -> dict[str, Any] | None:
    if not thread_id or not str(thread_id).strip():
        return None
    snap = await graph.aget_state(config={"configurable": {"thread_id": thread_id.strip()}})
    if not snap or not snap.values:
        return None
    return json_safe_state(dict(snap.values))


async def build_graph_checkpoint_event_chain(
    session_refs: Mapping[str, Any],
) -> list[dict[str, Any]]:
    graphs = get_observable_graph_map()

    events: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    for key in graphs:
        tid = session_refs.get(key)
        if tid is None or str(tid).strip() == "":
            events.append(
                {
                    "kind": "graph_checkpoint",
                    "graph": key,
                    "thread_id": None,
                    "state": None,
                    "skipped": True,
                    "at": now,
                }
            )
            continue
        tid_s = str(tid).strip()
        try:
            state_json = await aget_checkpoint_json(graphs[key], tid_s)
            events.append(
                {
                    "kind": "graph_checkpoint",
                    "graph": key,
                    "thread_id": tid_s,
                    "state": state_json,
                    "at": now,
                }
            )
        except Exception as exc:  # noqa: BLE001
            events.append(
                {
                    "kind": "graph_checkpoint",
                    "graph": key,
                    "thread_id": tid_s,
                    "state": None,
                    "error": str(exc)[:500],
                    "at": now,
                }
            )

    return events

