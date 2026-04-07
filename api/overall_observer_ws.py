import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.types import Command
from datetime import datetime, timezone

from graphs.overall_observer_graph import build_overall_observer_graph
from graphs.system_definition_graph import build_system_definition_graph

from llm_config import get_chat_model
from registeries.graph_registery import GRAPH_NAMES_REGISTERY
from api.ws_manager_graph import ws_manager_graph
from utils.serializers import normalize_finished_event, normalize_graph_event


overall_observer_router = APIRouter()

_graph_name = GRAPH_NAMES_REGISTERY["overall_observer"]

# -------------------
# Build graph ONCE
# -------------------
graph = build_overall_observer_graph(_graph_name, get_chat_model())


# -------------------
# Graph execution
# -------------------
async def start_graph(session_id: str, data: dict):

    state = {
        # "step": "DECIDE_ROUTE",
        # "raw_user_input": data.get("payload"),
    }

    config = {
        "configurable": {
            "thread_id": session_id,
            "graph_name": _graph_name,
        }
    }

    async for update in graph.astream(
        state,
        config=config,
        subgraphs=True,
        version="v2",
    ):
        clean = normalize_graph_event(update["data"], config)

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
        subgraphs=True,
        version="v2",
    ):
        # TODO Not a clean solution, to be improved
        if "__interrupt__" in update["data"]:
            step = None
            step_graph_name = None
        else:
            node_name, payload = next(iter(update["data"].items()))  # 👈 step 1
            print(payload)
            step = payload["step"] or payload["next_step"]  # 👈 step 2
            step_graph_name = payload["graph_name"]

        if step == "FINAL" and step_graph_name != _graph_name:
            snapshot = await graph.aget_state(config=config)
            print(snapshot)
            state = snapshot.values
            await normalize_finished_event(session_id, state, step_graph_name)
            continue

        clean = normalize_graph_event(update["data"], config)

        if clean is None:
            continue

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
