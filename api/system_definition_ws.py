import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.types import Command
from datetime import datetime, timezone

from graphs.system_definition_graph import build_system_definition_graph
from langchain_anthropic import ChatAnthropic

from utils.config import get_settings
from api.ws_manager_graph import ws_manager_graph
from utils.serializers import normalize_graph_event


system_definition_router = APIRouter()
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
graph = build_system_definition_graph(llm)


# -------------------
# Graph execution
# -------------------
async def start_graph(session_id: str, data: dict):

    state = {
        "step": "REQUEST_SYSTEM_INPUT",
        # "raw_user_input": data.get("payload"),
    }

    async for update in graph.astream(
        state,
        config={"configurable": {"thread_id": session_id}},
    ):
        clean = normalize_graph_event(update, graph_name="system_definition")

        if clean is None:
            continue

        await ws_manager_graph.send(session_id, clean)


async def handle_resume(session_id: str, data: dict):
    interrupt_id = data.get("interrupt_id")
    value = data.get("value")

    async for update in graph.astream(
        Command(
            resume={"interrupt_id": interrupt_id, "raw_user_input": value},
        ),
        config={"configurable": {"thread_id": session_id}},
    ):
        # TODO Not a clean solution, to be improved
        if "__interrupt__" in update:
            step = None
        else:
            node_name, payload = next(iter(update.items()))  # 👈 step 1
            step = payload.get("step")  # 👈 step 2

        if step == "FINAL":
            snapshot = await graph.aget_state(
                config={"configurable": {"thread_id": session_id}}
            )
            state = snapshot.values
            await ws_manager_graph.send(
                session_id,
                {
                    "type": "finished",
                    "graph_name": "system_definition",
                    "data": {
                        "system_description": state.get("system_description"),
                        "system_functions": state.get("system_functions"),
                        "assumptions": state.get("assumptions"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                },
            )
            continue

        clean = normalize_graph_event(update, graph_name="system_definition")

        if clean is None:
            continue

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
