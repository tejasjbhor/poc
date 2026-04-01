from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import asyncio


from api.ws_manager_graph import ws_manager_graph
from graphs.layout_graph import build_graph
from langgraph.types import Command

from graphs.layout_graph import build_graph
from langchain_anthropic import ChatAnthropic
from utils.config import get_settings
from utils.serializers import normalize_graph_event


layout_router = APIRouter()

# Settings
cfg = get_settings()
llm = ChatAnthropic(
    model=cfg.anthropic_model,
    api_key=cfg.anthropic_api_key,
    max_tokens=4096,
    temperature=0.2,
)

# Build graph once
graph = build_graph(llm)


async def start_graph(session_id: str, data: dict):
    state = {
        "last_step": "ASK_OVERALL_SURFACE_AND_FUNCTION",
        "user_input": data.get("payload"),
    }

    async for update in graph.astream(
        state, config={"configurable": {"thread_id": session_id}}
    ):
        clean = normalize_graph_event(update, graph_name="layout")
        await ws_manager_graph.send(session_id, clean)


async def handle_resume(session_id: str, data: dict):
    interrupt_id = data.get("interrupt_id")
    value = data.get("value")

    async for update in graph.astream(
        Command(
            resume={"interrupt_id": interrupt_id}, update={"raw_user_input": value}
        ),
        config={"configurable": {"thread_id": session_id}},
    ):
        clean = normalize_graph_event(update, graph_name="layout")
        await ws_manager_graph.send(session_id, clean)


@layout_router.websocket("/ws/layout/{session_id}")
async def layout_ws(websocket: WebSocket, session_id: str):
    await ws_manager_graph.connect(session_id, websocket)

    try:
        while True:
            # Keep connection alive (or receive user messages here later)
            msg = await websocket.receive_text()
            data = json.loads(msg)

            if data["type"] == "start":
                asyncio.create_task(start_graph(session_id, data))

            if data["type"] == "resume":
                asyncio.create_task(handle_resume(session_id, data))

    except WebSocketDisconnect:
        print("Client disconnected")
        ws_manager_graph.disconnect(session_id)

    except Exception as e:
        print("WS error:", e)
        ws_manager_graph.disconnect(session_id)
