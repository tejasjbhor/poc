import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.types import Command

from graphs.overall_observer_graph import build_overall_observer_graph

from services.llm.llm_config import get_chat_model
from registeries.graph_registery import GRAPH_NAMES_REGISTERY
from api.ws_manager_graph import ws_manager_graph
from utils.ws_to_json_safe import ws_to_json_safe
from utils.serializers import normalize_finished_event, normalize_graph_event


overall_observer_router = APIRouter()

_graph_name = GRAPH_NAMES_REGISTERY["overall_observer"]

# -------------------
# Build graph ONCE
# -------------------
graph = build_overall_observer_graph(_graph_name, get_chat_model())

seen_interrupt_ids = set()


# -------------------
# Graph execution
# -------------------
async def start_graph(session_id: str, data: dict):

    config = {
        "configurable": {
            "thread_id": session_id,
            "graph_name": _graph_name,
        }
    }

    async for update in graph.astream(
        {},
        config=config,
        subgraphs=True,
        version="v2",
    ):
        clean = normalize_graph_event(update["data"], seen_interrupt_ids)

        if clean is None:
            continue

        clean = ws_to_json_safe(clean)
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
        subgraphs=True,
        version="v2",
    ):
        # TODO Not a clean solution, to be improved
        if "__interrupt__" in update["data"]:
            step = None
        else:
            node_name, payload = next(iter(update["data"].items()))  # 👈 step 1
            step = payload.get("step") or payload.get("next_step")  # 👈 step 2

        if step == "FINAL":
            snapshot = await graph.aget_state(config=config)
            safe_state = ws_to_json_safe(snapshot.values)
            # print(safe_state)
            if safe_state.get("graph_name") != _graph_name:
                await normalize_finished_event(session_id, safe_state)
            continue

        clean = normalize_graph_event(update["data"], seen_interrupt_ids)

        if clean is None:
            continue

        clean = ws_to_json_safe(clean)
        await ws_manager_graph.send(session_id, clean)


# -------------------
# WebSocket endpoint
# -------------------
@overall_observer_router.websocket("/ws/overall_observer/{session_id}")
async def overall_observer_ws(websocket: WebSocket, session_id: str):
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
