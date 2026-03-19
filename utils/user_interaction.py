import asyncio
from typing import Any, Dict, Optional

from agents.operational_agent import BroadcastFn
from schemas.models import AgentEvent, AgentStatus

async def request_user_input(
    session_id: str,
    agent: str,
    user_input_queue: asyncio.Queue,
    broadcast: BroadcastFn,
    step: str,
    data: Dict[str, Any],
    label: str,
    instructions: str,
    input_type: str = "validation",
    ui_hint: Optional[Dict[str, Any]] = None,
    timeout: float = 300.0,
) -> Optional[Dict[str, Any]]:
    """
    Generic user input handler:
    - Sends request to frontend
    - Waits for response
    - Handles timeout
    """

    # 1. Send request to frontend
    await broadcast(session_id, AgentEvent(
        session_id=session_id,
        agent=agent,
        step=step,
        status=AgentStatus.RUNNING,
        payload={
            "type": "user_input_request",
            "input_type": input_type,
            "label": label,
            "instructions": instructions,
            "data": data,
            "sub_status": "Waiting For User Input",
            "ui_hint": ui_hint or {}
        }
    ).to_ws())

    while not user_input_queue.empty():
        try:
            user_input_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

    # 2. Wait for response
    try:
        input_data = await asyncio.wait_for(
            user_input_queue.get(),
            timeout=timeout
        )
        return input_data

    except asyncio.TimeoutError:
        # 3. Handle timeout
        await broadcast(session_id, AgentEvent(
            session_id=session_id,
            agent=agent,
            step=f"{step}_timeout",
            status=AgentStatus.FAILED,
            payload={
                "note": "Timed out waiting for user input."
            },
        ).to_ws())
        return None