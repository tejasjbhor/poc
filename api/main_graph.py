import asyncio
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from pydantic import BaseModel
from graphs.layout_graph import build_graph
from langchain_anthropic import ChatAnthropic
from utils.config import get_settings
from api.ws_manager_graph import ws_manager_graph
from utils.serializers import serialize_interrupt

# Settings
cfg = get_settings()
llm = ChatAnthropic(
    model=cfg.anthropic_model,
    api_key=cfg.anthropic_api_key,
    max_tokens=1024,
    temperature=0.2,
)

# Build graph once
graph = build_graph(llm)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active sessions
sessions = {}


class StartGraphRequest(BaseModel):
    # optional initial state
    raw_user_input: str | None = None


async def start_graph(session_id: str, data: dict):
    state = {
        "last_step": "ASK_OVERALL_SURFACE_AND_FUNCTION",
        "user_input": data.get("payload"),
    }

    async for update in graph.astream(
        state, config={"configurable": {"thread_id": session_id}}
    ):
        clean = serialize_interrupt(update)
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
        clean = serialize_interrupt(update)
        await ws_manager_graph.send(session_id, clean)


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
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
