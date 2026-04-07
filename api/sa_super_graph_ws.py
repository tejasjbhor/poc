import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_anthropic import ChatAnthropic
from langgraph.types import Command

from api.ws_manager_graph import ws_manager_graph
from graphs.sa_super_graph import build_sa_super_graph
from registeries.graph_names import GRAPH_NAMES_REGISTERY
from registeries.observable_workflows import (
    default_observable_workflow_id,
    get_observable_workflow_ids,
)
from utils.config import get_settings
from utils.serializers import normalize_graph_event

sa_super_graph_router = APIRouter()

cfg = get_settings()
_llm = ChatAnthropic(
    model=cfg.anthropic_model,
    api_key=cfg.anthropic_api_key,
    max_tokens=4096,
    temperature=0.2,
)

_graph_name = GRAPH_NAMES_REGISTERY["sa_super_graph"]
graph = build_sa_super_graph(_graph_name, _llm)


def _initial_state(data: dict) -> dict:
    payload = (data.get("payload") or {}) if isinstance(data, dict) else {}
    refs = payload.get("graph_session_refs") or payload.get("session_refs") or {}
    if not isinstance(refs, dict):
        refs = {}
    ingress = dict(payload.get("ingress_context") or {})
    active = str(payload.get("active_agent") or "").strip()
    if active not in set(get_observable_workflow_ids()):
        active = default_observable_workflow_id()
    return {
        "graph_session_refs": refs,
        "ingress_context": ingress,
        "active_agent": active,
        "event_chain": [],
    }


def _merge_refresh_payload(prev: dict, data: dict) -> dict:
    """Merge optional payload into checkpoint state; keep event_chain history."""
    out = dict(prev)
    payload = (data.get("payload") or {}) if isinstance(data, dict) else {}
    new_refs = payload.get("graph_session_refs") or payload.get("session_refs")
    if isinstance(new_refs, dict) and new_refs:
        base = dict(out.get("graph_session_refs") or {})
        base.update(new_refs)
        out["graph_session_refs"] = base
    ic = payload.get("ingress_context")
    if isinstance(ic, dict) and ic:
        out["ingress_context"] = {**(out.get("ingress_context") or {}), **ic}
    aa = str(payload.get("active_agent") or "").strip()
    if aa in set(get_observable_workflow_ids()):
        out["active_agent"] = aa
    out.pop("step", None)
    return out


def _safe_file_id(session_id: str, max_len: int = 120) -> str:
    t = (session_id or "").strip()
    t = re.sub(r"[^\w.\-]+", "_", t, flags=re.UNICODE)
    return (t or "session")[:max_len]


def _snapshot_path(snapshot_dir: str, session_id: str) -> Path:
    root = Path((snapshot_dir or "").strip())
    root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return root / f"sa_super_{ts}_{_safe_file_id(session_id)}.json"


def _trim_snapshots(folder: Path, keep: int) -> None:
    if keep <= 0 or not folder.is_dir():
        return
    files = sorted(
        folder.glob("sa_super_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in files[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def save_snapshot(
    session_id: str,
    finished: dict[str, Any],
    snapshot_dir: str,
    max_files: int,
) -> None:
    """Write ``finished`` JSON to disk if ``snapshot_dir`` is set."""
    root = (snapshot_dir or "").strip()
    if not root:
        return
    path = _snapshot_path(root, session_id)
    data = finished.get("data")
    if isinstance(data, dict):
        data["snapshot_filename"] = path.name
        data["snapshot_dir"] = str(path.parent.resolve())
    with path.open("w", encoding="utf-8") as f:
        json.dump(finished, f, indent=2, ensure_ascii=False, default=str)
    if max_files > 0:
        _trim_snapshots(Path(root), max_files)


def _finished_payload(st: dict) -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "type": "finished",
        "graph_name": "sa_super_graph",
        "data": {
            "graph_session_refs": st.get("graph_session_refs") or {},
            "ingress_context": st.get("ingress_context") or {},
            "active_agent": st.get("active_agent"),
            "event_chain": st.get("event_chain") or [],
            "next_agent": st.get("next_agent"),
            "session_goal": st.get("session_goal"),
            "goal_progress": st.get("goal_progress"),
            "sa_inferred_domain": st.get("sa_inferred_domain"),
            "sa_inferred_task": st.get("sa_inferred_task"),
            "sa_phase": st.get("sa_phase"),
            "sa_thoughts": st.get("sa_thoughts"),
            "sa_checklist": st.get("sa_checklist"),
            "sa_card": st.get("sa_card"),
            "sa_readiness_buffer": st.get("sa_readiness_buffer"),
            "sa_context_for_workflow": st.get("sa_context_for_workflow"),
            "timestamp": ts,
        },
    }


async def send_finished(session_id: str, st: dict) -> None:
    msg = _finished_payload(st)
    settings = get_settings()
    save_snapshot(
        session_id,
        msg,
        settings.sa_super_snapshot_dir,
        settings.sa_super_snapshot_max_files,
    )
    await ws_manager_graph.send(session_id, msg)


async def start_sa_super_graph(session_id: str, data: dict):
    state = _initial_state(data)
    async for update in graph.astream(
        state,
        config={"configurable": {"thread_id": session_id}},
    ):
        clean = normalize_graph_event(update, graph_name=_graph_name)
        if clean is None:
            continue
        await ws_manager_graph.send(session_id, clean)

    snapshot = await graph.aget_state(
        config={"configurable": {"thread_id": session_id}}
    )
    if snapshot and snapshot.values.get("step") == "FINAL":
        await send_finished(session_id, dict(snapshot.values))


async def refresh_sa_super_graph(session_id: str, data: dict):
    """
    Re-run FETCH + SUPER_OBSERVER on the same thread_id.
    Merges optional payload (refs / ingress / active_agent) into the last checkpoint.
    Keeps existing event_chain; new fetch events append (growing history).
    """
    cfg_d = {"configurable": {"thread_id": session_id}}
    snap = await graph.aget_state(config=cfg_d)
    if not snap or not snap.values:
        await start_sa_super_graph(session_id, data)
        return

    state = _merge_refresh_payload(dict(snap.values), data)
    async for update in graph.astream(state, config=cfg_d):
        clean = normalize_graph_event(update, graph_name=_graph_name)
        if clean is None:
            continue
        await ws_manager_graph.send(session_id, clean)

    snapshot = await graph.aget_state(config=cfg_d)
    if snapshot and snapshot.values.get("step") == "FINAL":
        await send_finished(session_id, dict(snapshot.values))


async def handle_sa_super_resume(session_id: str, data: dict):
    interrupt_id = data.get("interrupt_id")
    value = data.get("value")

    async for update in graph.astream(
        Command(
            resume={"interrupt_id": interrupt_id, "raw_user_input": value},
        ),
        config={"configurable": {"thread_id": session_id}},
    ):
        if "__interrupt__" in update:
            step = None
        else:
            _node_name, payload = next(iter(update.items()))
            step = payload.get("step")

        if step == "FINAL":
            snapshot = await graph.aget_state(
                config={"configurable": {"thread_id": session_id}}
            )
            await send_finished(session_id, dict(snapshot.values))
            continue

        clean = normalize_graph_event(update, graph_name=_graph_name)
        if clean is None:
            continue
        await ws_manager_graph.send(session_id, clean)


@sa_super_graph_router.websocket("/ws/system/{session_id}")
async def sa_super_graph_ws(websocket: WebSocket, session_id: str):
    await ws_manager_graph.connect(session_id, websocket)

    try:
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)

            if data.get("type") == "start":
                asyncio.create_task(start_sa_super_graph(session_id, data))

            elif data.get("type") == "refresh":
                asyncio.create_task(refresh_sa_super_graph(session_id, data))

            elif data.get("type") == "resume":
                asyncio.create_task(handle_sa_super_resume(session_id, data))

    except WebSocketDisconnect:
        ws_manager_graph.disconnect(session_id)

    except Exception as e:
        print("WS error:", e)
        ws_manager_graph.disconnect(session_id)
