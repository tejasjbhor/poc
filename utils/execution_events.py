from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Mapping
from uuid import uuid4


ExecutionStack = tuple[dict[str, str], ...]
_EXECUTION_STACK: ContextVar[ExecutionStack] = ContextVar(
    "graph_execution_stack",
    default=(),
)


@dataclass(slots=True)
class NodeExecutionContext:
    graph_name: str
    node_name: str
    session_id: str | None
    run_id: str
    started_at: str
    started_perf: float
    parent_frame: dict[str, str] | None
    stack: ExecutionStack
    token: Token


@dataclass(slots=True)
class GraphExecutionContext:
    graph_name: str
    session_id: str | None
    run_id: str
    trigger: str
    started_at: str
    started_perf: float
    parent_frame: dict[str, str] | None
    stack: ExecutionStack


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_stack(stack: ExecutionStack) -> list[dict[str, str]]:
    return [
        {
            "graph_name": frame["graph_name"],
            "node_name": frame["node_name"],
            "run_id": frame["run_id"],
        }
        for frame in stack
    ]


def _build_graph_path(stack: ExecutionStack, current_graph_name: str | None = None) -> list[str]:
    graph_path: list[str] = []

    for frame in stack:
        graph_name = frame["graph_name"]
        if not graph_path or graph_path[-1] != graph_name:
            graph_path.append(graph_name)

    if current_graph_name and (not graph_path or graph_path[-1] != current_graph_name):
        graph_path.append(current_graph_name)

    return graph_path


def _summarize_mapping(mapping: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(mapping, Mapping):
        return {}

    summary: dict[str, Any] = {
        "result_keys": sorted(str(key) for key in mapping.keys()),
    }

    for key in ("step", "next_step", "last_step", "graph_name"):
        value = mapping.get(key)
        if value is not None:
            summary[key] = value

    return summary


def _serialize_error(error: BaseException) -> dict[str, Any]:
    return {
        "type": error.__class__.__name__,
        "message": str(error),
    }


def begin_node_execution(
    graph_name: str,
    node_name: str,
    session_id: str | None,
) -> NodeExecutionContext:
    current_stack = _EXECUTION_STACK.get()
    parent_frame = current_stack[-1] if current_stack else None
    frame = {
        "graph_name": graph_name,
        "node_name": node_name,
        "run_id": uuid4().hex,
    }
    next_stack = current_stack + (frame,)
    token = _EXECUTION_STACK.set(next_stack)

    return NodeExecutionContext(
        graph_name=graph_name,
        node_name=node_name,
        session_id=session_id,
        run_id=frame["run_id"],
        started_at=utc_now_iso(),
        started_perf=perf_counter(),
        parent_frame=parent_frame,
        stack=next_stack,
        token=token,
    )


def finish_node_execution(context: NodeExecutionContext) -> None:
    _EXECUTION_STACK.reset(context.token)


def begin_graph_execution(
    graph_name: str,
    session_id: str | None,
    trigger: str,
) -> GraphExecutionContext:
    current_stack = _EXECUTION_STACK.get()
    parent_frame = current_stack[-1] if current_stack else None

    return GraphExecutionContext(
        graph_name=graph_name,
        session_id=session_id,
        run_id=uuid4().hex,
        trigger=trigger,
        started_at=utc_now_iso(),
        started_perf=perf_counter(),
        parent_frame=parent_frame,
        stack=current_stack,
    )


def build_node_execution_message(
    context: NodeExecutionContext,
    status: str,
    result: Mapping[str, Any] | None = None,
    error: BaseException | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    graph_path = _build_graph_path(context.stack)
    payload: dict[str, Any] = {
        "event_id": uuid4().hex,
        "kind": "node",
        "status": status,
        "session_id": context.session_id,
        "graph_name": context.graph_name,
        "node_name": context.node_name,
        "run_id": context.run_id,
        "parent_graph_name": context.parent_frame["graph_name"]
        if context.parent_frame
        else None,
        "parent_node_name": context.parent_frame["node_name"]
        if context.parent_frame
        else None,
        "parent_run_id": context.parent_frame["run_id"] if context.parent_frame else None,
        "depth": len(context.stack) - 1,
        "graph_depth": max(len(graph_path) - 1, 0),
        "graph_path": graph_path,
        "node_path": _serialize_stack(context.stack),
        "timestamp": utc_now_iso(),
        "started_at": context.started_at,
    }

    if status in {"completed", "failed", "paused"}:
        ended_at = utc_now_iso()
        payload.update(
            {
                "ended_at": ended_at,
                "duration_ms": round((perf_counter() - context.started_perf) * 1000, 2),
            }
        )

    if result is not None:
        payload.update(_summarize_mapping(result))

    if error is not None:
        payload["error"] = _serialize_error(error)

    if extra:
        payload.update(extra)

    return {
        "type": "execution",
        "graph_name": context.graph_name,
        "data": payload,
    }


def build_graph_execution_message(
    context: GraphExecutionContext,
    status: str,
    result: Mapping[str, Any] | None = None,
    error: BaseException | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    graph_path = _build_graph_path(context.stack, context.graph_name)
    payload: dict[str, Any] = {
        "event_id": uuid4().hex,
        "kind": "graph",
        "status": status,
        "trigger": context.trigger,
        "session_id": context.session_id,
        "graph_name": context.graph_name,
        "run_id": context.run_id,
        "parent_graph_name": context.parent_frame["graph_name"]
        if context.parent_frame
        else None,
        "parent_node_name": context.parent_frame["node_name"]
        if context.parent_frame
        else None,
        "parent_run_id": context.parent_frame["run_id"] if context.parent_frame else None,
        "depth": max(len(graph_path) - 1, 0),
        "graph_path": graph_path,
        "node_path": _serialize_stack(context.stack),
        "timestamp": utc_now_iso(),
        "started_at": context.started_at,
    }

    if status in {"completed", "failed", "paused"}:
        ended_at = utc_now_iso()
        payload.update(
            {
                "ended_at": ended_at,
                "duration_ms": round((perf_counter() - context.started_perf) * 1000, 2),
            }
        )

    if result is not None:
        payload.update(_summarize_mapping(result))

    if error is not None:
        payload["error"] = _serialize_error(error)

    if extra:
        payload.update(extra)

    return {
        "type": "execution",
        "graph_name": context.graph_name,
        "data": payload,
    }
