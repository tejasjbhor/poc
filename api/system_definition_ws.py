import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.types import Command

from graphs.system_definition_graph import build_system_definition_graph
from langchain_anthropic import ChatAnthropic

from utils.config import get_settings
from api.ws_manager_graph import ws_manager_graph
from utils.serializers import serialize_interrupt


system_definition_router = APIRouter()
# -------------------
# LLM setup
# -------------------
cfg = get_settings()

llm = ChatAnthropic(
    model=cfg.anthropic_model,
    api_key=cfg.anthropic_api_key,
    max_tokens=1024,
    temperature=0.2,
)

# -------------------
# Build graph ONCE
# -------------------
graph = build_system_definition_graph(llm)


# -------------------
# Graph execution
# -------------------
async def start_graph(session_id: str, data: dict):
    state = {
        "last_step": "REQUEST_SYSTEM_INPUT",
        "raw_user_input": data.get("payload"),
    }

    async for update in graph.astream(
        state,
        config={"configurable": {"thread_id": session_id}},
    ):
        clean = serialize_interrupt(update)
        await ws_manager_graph.send(session_id, clean)


async def handle_resume(session_id: str, data: dict):
    interrupt_id = data.get("interrupt_id")
    value = data.get("value")

    async for update in graph.astream(
        Command(
            resume={"interrupt_id": interrupt_id},
            update={"raw_user_input": value},
        ),
        config={"configurable": {"thread_id": session_id}},
    ):
        clean = serialize_interrupt(update)
        await ws_manager_graph.send(session_id, clean)


# -------------------
# WebSocket endpoint
# -------------------
@system_definition_router.websocket("/ws/system/{session_id}")
async def system_definition_ws(websocket: WebSocket, session_id: str):
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
