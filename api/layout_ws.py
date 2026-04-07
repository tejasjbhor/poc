from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import asyncio


from api.ws_manager_graph import ws_manager_graph
from langgraph.types import Command

from graphs.layout_graph import build_facility_layout_graph
from services.llm.llm_config import get_chat_model
from registeries.graph_registery import GRAPH_NAMES_REGISTERY
from utils.serializers import normalize_finished_event, normalize_graph_event


layout_router = APIRouter()


_graph_name = GRAPH_NAMES_REGISTERY["layout"]

# Build graph once
graph = build_facility_layout_graph(_graph_name, get_chat_model())


async def start_layout_graph(session_id: str, data: dict):

    config = {
        "configurable": {
            "thread_id": session_id,
            "graph_name": _graph_name,
        }
    }

    async for update in graph.astream(
        {},
        config=config,
    ):
        clean = normalize_graph_event(update)

        if clean is None:
            continue

        await ws_manager_graph.send(session_id, clean)


async def handle_layout_resume(session_id: str, data: dict):
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
        # =========================
        # Extract step
        # =========================
        if "__interrupt__" in update:
            step = None
        else:
            node_name, payload = next(iter(update.items()))
            step = payload.get("step")

        # =========================
        # Finalization handling
        # =========================
        if step == "FINAL":
            snapshot = await graph.aget_state(config=config)
            state = snapshot.values
            await normalize_finished_event(
                session_id, state, config["configurable"]["graph_name"]
            )
            continue

        # =========================
        # Normal event handling
        # =========================
        clean = normalize_graph_event(update)

        if clean is None:
            continue

        await ws_manager_graph.send(session_id, clean)


@layout_router.websocket("/ws/layout/{session_id}")
async def layout_ws(websocket: WebSocket, session_id: str):
    await ws_manager_graph.connect(session_id, websocket)

    try:
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)

            if data["type"] == "start":
                asyncio.create_task(start_layout_graph(session_id, data))

            elif data["type"] == "resume":
                asyncio.create_task(handle_layout_resume(session_id, data))

    except WebSocketDisconnect:
        print("Client disconnected")
        ws_manager_graph.disconnect(session_id)

    except Exception as e:
        print("WS error:", e)
        ws_manager_graph.disconnect(session_id)
