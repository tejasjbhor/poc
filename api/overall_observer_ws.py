import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.types import Command

from api.ws_manager_graph import ws_manager_graph
from graphs.overall_observer_graph import build_overall_observer_graph
from registeries.graph_registery import GRAPH_NAMES_REGISTERY
from services.llm.llm_config import get_chat_model
from utils.execution_events import begin_graph_execution, build_graph_execution_message
from utils.serializers import normalize_finished_event, normalize_graph_event


overall_observer_router = APIRouter()

_graph_name = GRAPH_NAMES_REGISTERY["overall_observer"]

# -------------------
# Build graph ONCE
# -------------------
graph = build_overall_observer_graph(_graph_name, get_chat_model())

seen_interrupt_ids = set()


# -------------------
# Graph execution
# -------------------
async def start_graph(session_id: str, data: dict):
    graph_execution = begin_graph_execution(_graph_name, session_id, trigger="start")
    await ws_manager_graph.send(
        session_id,
        build_graph_execution_message(graph_execution, status="started"),
    )

    state = {
        # "step": "DECIDE_ROUTE",
        # "raw_user_input": data.get("payload"),
    }

    config = {
        "configurable": {
            "thread_id": session_id,
            "graph_name": _graph_name,
        }
    }

    try:
        async for update in graph.astream(
            state,
            config=config,
            subgraphs=True,
            version="v2",
        ):
            clean = normalize_graph_event(update["data"], seen_interrupt_ids)

            if clean is None:
                continue

            await ws_manager_graph.send(session_id, clean)

            if clean.get("type") == "interrupt" and clean.get("graph_name") == _graph_name:
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


async def handle_resume(session_id: str, data: dict):
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
            subgraphs=True,
            version="v2",
        ):
            if "__interrupt__" in update["data"]:
                step = None
                step_graph_name = None
            else:
                node_name, payload = next(iter(update["data"].items()))
                step = payload.get("step") or payload.get("next_step")
                step_graph_name = payload["graph_name"]

            if step == "FINAL":
                snapshot = await graph.aget_state(config=config)
                state = snapshot.values

                if state.get("graph_name") != _graph_name:
                    await normalize_finished_event(session_id, state, step_graph_name)
                else:
                    await ws_manager_graph.send(
                        session_id,
                        build_graph_execution_message(
                            graph_execution,
                            status="completed",
                            result=state,
                        ),
                    )
                continue

            clean = normalize_graph_event(update["data"], seen_interrupt_ids)

            if clean is None:
                continue

            await ws_manager_graph.send(session_id, clean)

            if clean.get("type") == "interrupt" and clean.get("graph_name") == _graph_name:
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


# -------------------
# WebSocket endpoint
# -------------------
@overall_observer_router.websocket("/ws/overall_observer/{session_id}")
async def overall_observer_ws(websocket: WebSocket, session_id: str):
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
