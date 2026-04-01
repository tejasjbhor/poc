import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.types import Command
from datetime import datetime, timezone

from graphs.internet_search_graph import build_internet_search_graph
from langchain_anthropic import ChatAnthropic

from registeries.internet_search_unified_tool_registery import INTERNET_SEARCH_TOOLS
from utils.config import get_settings
from api.ws_manager_graph import ws_manager_graph
from utils.serializers import normalize_graph_event

# 🔧 import your tools registry


internet_search_router = APIRouter()

# -------------------
# LLM setup
# -------------------
cfg = get_settings()

llm = ChatAnthropic(
    model=cfg.anthropic_model,
    api_key=cfg.anthropic_api_key,
    max_tokens=4096,
    temperature=0.2,
)

# -------------------
# Build graph ONCE
# -------------------
graph = build_internet_search_graph(llm, INTERNET_SEARCH_TOOLS)


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
        clean = normalize_graph_event(update, graph_name="internet_search")

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

        clean = normalize_graph_event(update, graph_name="internet_search")

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