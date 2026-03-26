import asyncio
import json

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from pydantic import BaseModel
from uuid import uuid4
from graphs.layout_graph import build_graph
from langchain_anthropic import ChatAnthropic
from utils.config import get_settings
from api.ws_manager_graph import manager
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

@app.post("/api/v1/sessions/f2/start")
async def start_graph():
    session_id = str(uuid4())

    asyncio.create_task(
        stream_graph(
            {"last_step": "ASK_OVERALL_SURFACE_AND_FUNCTION"},
            session_id
        )
    )

    return {"session_id": session_id}

async def stream_graph(session_id, state):
    initial_state = {"last_step": "ASK_OVERALL_SURFACE_AND_FUNCTION"}
    def blocking_stream(loop):
        for update in graph.stream(
            initial_state,
            config={"configurable": {"thread_id": session_id}}
        ):
            print(f"[Graph {session_id}] UPDATE:", update)
            clean_update = serialize_interrupt(update)
            asyncio.run_coroutine_threadsafe(
                manager.send(session_id, clean_update),
                loop
            )

    loop = asyncio.get_event_loop()
    await asyncio.to_thread(blocking_stream, loop)
    
async def handle_resume(session_id: str, data: dict):
    interrupt_id = data.get("interrupt_id")
    value = data.get("value")

    loop = asyncio.get_event_loop()

    def run_graph():
        for update in graph.stream(
            Command(
                resume={
                    "interrupt_id": interrupt_id,
                    "value": value
                }
            ),
            config={"configurable": {"thread_id": session_id}}
        ):
            clean = serialize_interrupt(update)

            asyncio.run_coroutine_threadsafe(
                manager.send(session_id, clean),
                loop
            )

    await asyncio.to_thread(run_graph)
    
    
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    try:
        while True:
            # Keep connection alive (or receive user messages here later)
            msg = await websocket.receive_text()
            data = json.loads(msg)
            print("STREAM ACTIVE")
            if data["type"] == "resume":
                asyncio.create_task(handle_resume(session_id, data))

    except Exception as e:
        print("WS error:", e)
        manager.disconnect(session_id)