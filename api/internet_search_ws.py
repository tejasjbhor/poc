import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.types import Command
from datetime import datetime, timezone

from graphs.internet_search_graph import build_internet_search_graph

from llm_config import get_chat_model
from registeries.graph_names import GRAPH_NAMES_REGISTERY
from api.ws_manager_graph import ws_manager_graph
from utils.serializers import normalize_graph_event

# 🔧 import your tools registry


internet_search_router = APIRouter()

_graph_name = GRAPH_NAMES_REGISTERY["internet_search"]

# -------------------
# Build graph ONCE
# -------------------
graph = build_internet_search_graph(_graph_name, get_chat_model())


# -------------------
# Graph execution
# -------------------
async def start_graph(session_id: str, data: dict):

    state = {
        "step": "REQUEST_SYSTEM_INPUT",
    }

    async for update in graph.astream(
        state,
        config={"configurable": {"thread_id": session_id}},
    ):
        clean = normalize_graph_event(update, graph_name=_graph_name)

        if clean is None:
            continue

        await ws_manager_graph.send(session_id, clean)


# -------------------
# Resume execution
# -------------------
async def handle_resume(session_id: str, data: dict):
    interrupt_id = data.get("interrupt_id")
    value = data.get("value")

    async for update in graph.astream(
        Command(
            resume={
                "interrupt_id": interrupt_id,
                "raw_user_input": value,
            },
        ),
        config={"configurable": {"thread_id": session_id}},
    ):
        # 🔍 detect step
        if "__interrupt__" in update:
            step = None
        else:
            node_name, payload = next(iter(update.items()))
            step = payload.get("step")

        # =========================
        # FINAL OUTPUT
        # =========================
        if step == "FINAL":
            snapshot = await graph.aget_state(
                config={"configurable": {"thread_id": session_id}}
            )
            state = snapshot.values

            await ws_manager_graph.send(
                session_id,
                {
                    "type": "finished",
                    "graph_name": "internet_search",
                    "data": {
                        "system_understanding": state.get("system_understanding"),
                        "queries": state.get("queries"),
                        "ranked_candidates": state.get("ranked_candidates"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                },
            )
            continue

        clean = normalize_graph_event(update, graph_name=_graph_name)

        if clean is None:
            continue

        await ws_manager_graph.send(session_id, clean)


# -------------------
# WebSocket endpoint
# -------------------
@internet_search_router.websocket("/ws/internet-search/{session_id}")
async def internet_research_ws(websocket: WebSocket, session_id: str):
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
