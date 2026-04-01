from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import asyncio


from api.ws_manager_graph import ws_manager_graph
from langgraph.types import Command

from langchain_anthropic import ChatAnthropic
from graphs.layout_graph import build_facility_layout_graph
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
graph = build_facility_layout_graph(llm)


async def start_layout_graph(session_id: str, data: dict):

    state = {
        "step": "REQUEST_LAYOUT_INPUT",
    }

    async for update in graph.astream(
        state,
        config={"configurable": {"thread_id": session_id}},
    ):
        clean = normalize_graph_event(update, graph_name="layout")

        if clean is None:
            continue

        await ws_manager_graph.send(session_id, clean)


async def handle_layout_resume(session_id: str, data: dict):
    interrupt_id = data.get("interrupt_id")
    value = data.get("value")

    async for update in graph.astream(
        Command(
            resume={"interrupt_id": interrupt_id, "raw_user_input": value},
        ),
        config={"configurable": {"thread_id": session_id}},
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
            snapshot = await graph.aget_state(
                config={"configurable": {"thread_id": session_id}}
            )
            state = snapshot.values

            await ws_manager_graph.send(
                session_id,
                {
                    "type": "finished",
                    "graph_name": "layout",
                    "data": {
                        "system_description": state.get("system_description", ""),
                        "system_functions": state.get("system_functions", []),
                        "assumptions": state.get("assumptions", {}),
                        "constraints": state.get("constraints", {}),
                        "layout": state.get("layout", {}),
                        "total_area": state.get("total_area", 0),
                        "facility_coordinates": state.get("facility_coordinates", {}),
                        "layout_status": state.get("layout_status", ""),
                        "layout_rationale": state.get("layout_rationale", {}),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                },
            )
            continue

        # =========================
        # Normal event handling
        # =========================
        clean = normalize_graph_event(update, graph_name="layout")

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
