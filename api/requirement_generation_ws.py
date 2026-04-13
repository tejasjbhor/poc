import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.types import Command

from api.ws_manager_graph import ws_manager_graph
from graphs.requirement_generation_graph import build_requirement_generation_graph
from registeries.graph_registery import GRAPH_NAMES_REGISTERY
from services.llm.llm_config import get_chat_model
from utils.serializers import normalize_finished_event, normalize_graph_event


requirement_generation_router = APIRouter()

_graph_name = GRAPH_NAMES_REGISTERY["requirement_generation"]

graph = build_requirement_generation_graph(_graph_name, get_chat_model())


def _initial_state(data: dict) -> dict:
    payload = data.get("payload") or {}
    return {
        "system_description": payload.get("system_description"),
        "system_functions": payload.get("system_functions"),
        "assumptions": payload.get("assumptions") or [],
    }


async def start_graph(session_id: str, data: dict):
    config = {
        "configurable": {
            "thread_id": session_id,
            "graph_name": _graph_name,
        }
    }
    initial = _initial_state(data)
    async for update in graph.astream(initial, config=config):
        clean = normalize_graph_event(update)
        if clean is None:
            continue
        await ws_manager_graph.send(session_id, clean)


async def handle_resume(session_id: str, data: dict):
    interrupt_id = data.get("interrupt_id")
    value = data.get("value")
    config = {
        "configurable": {
            "thread_id": session_id,
            "graph_name": _graph_name,
        }
    }
    async for update in graph.astream(
        Command(
            resume={"interrupt_id": interrupt_id, "raw_user_input": value},
        ),
        config=config,
    ):
        if "__interrupt__" in update:
            step = None
        else:
            _node_name, payload = next(iter(update.items()))
            step = payload.get("step")

        if step == "FINAL":
            snapshot = await graph.aget_state(config=config)
            state = snapshot.values
            await normalize_finished_event(
                session_id, state, config["configurable"]["graph_name"]
            )
            continue

        clean = normalize_graph_event(update)
        if clean is None:
            continue
        await ws_manager_graph.send(session_id, clean)


@requirement_generation_router.websocket("/ws/requirement_generation/{session_id}")
async def requirement_generation_ws(websocket: WebSocket, session_id: str):
    await ws_manager_graph.connect(session_id, websocket)

    try:
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)

            if data["type"] == "start":
                asyncio.create_task(start_graph(session_id, data))

            elif data["type"] == "resume":
                asyncio.create_task(handle_resume(session_id, data))

    except WebSocketDisconnect:
        print("Client disconnected")
        ws_manager_graph.disconnect(session_id)

    except Exception as e:
        print("WS error:", e)
        ws_manager_graph.disconnect(session_id)
