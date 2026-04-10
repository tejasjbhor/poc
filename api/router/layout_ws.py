import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.types import Command

from api.ws_manager_graph import ws_manager_graph
from graphs.layout_graph import build_facility_layout_graph
from registeries.graph_registery import GRAPH_NAMES_REGISTERY
from utils.ws_to_json_safe import ws_to_json_safe
from services.llm.llm_config import get_chat_model
from utils.execution_events import begin_graph_execution, build_graph_execution_message
from utils.serializers import normalize_finished_event, normalize_graph_event


layout_router = APIRouter()

_graph_name = GRAPH_NAMES_REGISTERY["layout"]

# Build graph once
graph = build_facility_layout_graph(_graph_name, get_chat_model())


async def start_layout_graph(session_id: str, data: dict):
    graph_execution = begin_graph_execution(_graph_name, session_id, trigger="start")
    await ws_manager_graph.send(
        session_id,
        build_graph_execution_message(graph_execution, status="started"),
    )

    config = {
        "configurable": {
            "thread_id": session_id,
            "graph_name": _graph_name,
        }
    }

    try:
        async for update in graph.astream(
            {},
            config=config,
        ):
            clean = normalize_graph_event(update)

            if clean is None:
                continue

            clean = ws_to_json_safe(clean)
            await ws_manager_graph.send(session_id, clean)

            if (
                clean.get("type") == "interrupt"
                and clean.get("graph_name") == _graph_name
            ):
                await ws_manager_graph.send(
                    session_id,
                    build_graph_execution_message(graph_execution, status="paused"),
                )
    except Exception as error:
        await ws_manager_graph.send(
            session_id,
            build_graph_execution_message(
                graph_execution,
                status="failed",
                error=error,
            ),
        )
        raise


async def handle_layout_resume(session_id: str, data: dict):
    interrupt_id = data.get("interrupt_id")
    value = data.get("value")
    graph_execution = begin_graph_execution(_graph_name, session_id, trigger="resume")
    await ws_manager_graph.send(
        session_id,
        build_graph_execution_message(graph_execution, status="started"),
    )

    config = {
        "configurable": {
            "thread_id": session_id,
            "graph_name": _graph_name,
        }
    }

    try:
        async for update in graph.astream(
            Command(
                resume={"interrupt_id": interrupt_id, "raw_user_input": value},
            ),
            config=config,
        ):
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
                await ws_manager_graph.send(
                    session_id,
                    build_graph_execution_message(
                        graph_execution,
                        status="completed",
                        result=state,
                    ),
                )
                safe_state = ws_to_json_safe(snapshot.values)
                await normalize_finished_event(session_id, safe_state)
                continue

            clean = normalize_graph_event(update)
            if clean is None:
                continue

            clean = ws_to_json_safe(clean)
            await ws_manager_graph.send(session_id, clean)

            if (
                clean.get("type") == "interrupt"
                and clean.get("graph_name") == _graph_name
            ):
                await ws_manager_graph.send(
                    session_id,
                    build_graph_execution_message(graph_execution, status="paused"),
                )
    except Exception as error:
        await ws_manager_graph.send(
            session_id,
            build_graph_execution_message(
                graph_execution,
                status="failed",
                error=error,
            ),
        )
        raise


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
