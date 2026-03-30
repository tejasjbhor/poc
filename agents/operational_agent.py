"""Operational agent for ISO 15926 parsing."""

from __future__ import annotations

import json
from typing import Callable, Coroutine, Optional

import asyncio

from langchain.callbacks import AsyncCallbackHandler
import structlog

from schemas.models import AgentEvent, AgentName, AgentStatus
from utils.config import get_settings

log = structlog.get_logger(__name__)
cfg = get_settings()

BroadcastFn = Callable[[str, dict], Coroutine]


# Progress callback

class OperationalCallback(AsyncCallbackHandler):
    def __init__(self, session_id: str, broadcast: BroadcastFn):
        self.session_id = session_id
        self.broadcast = broadcast

    async def _emit(self, step: str, status: AgentStatus, payload=None, error=None):
        ev = AgentEvent(
            session_id=self.session_id,
            agent=AgentName.OPERATIONAL,
            step=step,
            status=status,
            payload=payload,
            error=error,
        )
        await self.broadcast(self.session_id, ev.to_ws())

    async def on_agent_action(self, action, **_):
        await self._emit(
            step=f"tool:{action.tool}",
            status=AgentStatus.RUNNING,
            payload={"input_preview": str(action.tool_input)[:200]},
        )

    async def on_tool_end(self, output, **_):
        await self._emit(
            step="tool_result",
            status=AgentStatus.RUNNING,
            payload={"preview": str(output)[:200]},
        )

    async def on_chain_error(self, error, **_):
        await self._emit(step="error", status=AgentStatus.FAILED, error=str(error))


# Prompt

_SYSTEM = """You are the Operational Agent for a Systems Engineering platform.

Your role: parse an engineering standards document and produce a structured
ISO 15926-2 compliant JSON model.

PROCESS:
1. Call get_iso15926_schema to load the reference schema.
2. Call extract_pdf_text to get the full document text.
3. Call extract_pdf_sections with keywords "shall,must,required,constraint,interface,
   safety,performance,regulatory" to get requirement-dense sections.
4. Analyse the text and build the structured model.

OUTPUT — respond with ONLY this JSON (no prose, no markdown fences):
{{
  "meta": {{
    "exported_at": "<ISO datetime>",
    "version": "1.0",
    "standard": "<detected standard name e.g. ISO 15926>",
    "source_document": "{filename}",
    "generated_by": "operational_agent"
  }},
  "entities": [
    {{
      "id": "<uuid>",
      "type": "entity",
      "entity_type": "<from schema>",
      "name": "<name>",
      "description": "<description>",
      ... entity-specific fields ...
    }}
  ],
  "relationships": [ ... ],
  "properties": []
}}

RULES:
- Extract EVERY "shall", "must", "is required to" statement as an engineering_constraint.
- Assign req_id sequentially: REQ-001, REQ-002 ...
- Each engineering_constraint must have: statement, req_id, requirement_type, rationale.
- Identify functional decomposition hierarchy (functional_system → functional_subsystem).
- Create actors (human_actor, organizational_actor, regulatory_actor, external_system).
- Regulatory references go in regulatory_reference entities.
- Set is_assumption: true where you are inferring rather than reading directly.
- A typical document yields 30–100 entities. Be thorough.
"""

_REACT_TEMPLATE = """{system}

Tools available:
{tools}

Tool names: {tool_names}

Format:
Thought: what to do
Action: tool_name
Action Input: the input
Observation: result
(repeat as needed)
Thought: I have enough information
Final Answer: <complete JSON model — no markdown, no prose>

Begin!
Filename: {filename}
PDF bytes (hex): {pdf_hex}
Domain context: {domain_context}
{agent_scratchpad}"""

# Public runner

from schemas.models import AgentEvent, AgentName, AgentStatus

async def run_operational_agent(
    session_id: str,
    broadcast: BroadcastFn,
    user_input_queue: asyncio.Queue,  # frontend pushes JSON content here
    timeout: float = 300.0,
    poll_interval: float = 0.5,
):
    """
    Waits for a JSON file sent from the frontend via an in-memory queue,
    parses it, broadcasts progress, and returns it as 'model'.
    
    user_input_queue: asyncio.Queue where frontend pushes the JSON string.
    """
    try:
        # Step 0: agent started
        await broadcast(session_id, AgentEvent(
            session_id=session_id,
            agent=AgentName.OPERATIONAL,
            step="started",
            status=AgentStatus.RUNNING,
            payload={"note": "Operational Agent Started. Waiting for JSON upload."}
        ).to_ws())

        # Step 1: broadcast user input request and set status WAITING_FOR_USER_INPUT
        await broadcast(session_id, AgentEvent(
            session_id=session_id,
            agent=AgentName.OPERATIONAL,
            step="request_user_input",
            status=AgentStatus.RUNNING,
            payload={
                "type": "user_input_request",
                "sub_status": "Waiting For User Input",
                "input_type": "multi",
                "allowed_inputs": ["file_upload", "text"],
                "input_format": {
                    "file": "application/json",
                    "text": "free_text"
                },
                "label": "Provide system description",
                "instructions": "Upload a JSON file OR describe your system in text.",
                "ui_hint": {
                    "render_as": "multi_input",
                    "options": ["upload", "text"]
                }
                }
        ).to_ws())

        # Step 1: wait for file content
        elapsed = 0.0
        input_data: Optional[dict] = None
        while input_data is None:
            try:
                input_data = user_input_queue.get_nowait()
            except asyncio.QueueEmpty:
                if elapsed >= timeout:
                    raise TimeoutError("Timed out waiting for user input.")
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

        await broadcast(session_id, AgentEvent(
            session_id=session_id,
            agent=AgentName.OPERATIONAL,
            step="input_received",
            status=AgentStatus.RUNNING,
            payload={"note": "User input received. Processing..."}
        ).to_ws())

        # Step 2: normalize input → model
        if isinstance(input_data, dict) and input_data.get("type") == "file":
            content = input_data.get("content", "")

            await broadcast(session_id, AgentEvent(
                session_id=session_id,
                agent=AgentName.OPERATIONAL,
                step="parsing_file",
                status=AgentStatus.RUNNING,
                payload={"note": "Parsing uploaded JSON file..."}
            ).to_ws())

            model = json.loads(content)

        elif isinstance(input_data, dict) and input_data.get("type") == "text":
            text = input_data.get("content", "")

            await broadcast(session_id, AgentEvent(
                session_id=session_id,
                agent=AgentName.OPERATIONAL,
                step="parsing_text",
                status=AgentStatus.RUNNING,
                payload={"note": "Structuring text input..."}
            ).to_ws())

            # Minimal safe version (no LLM yet)
            model = {
                "description": text
            }

        await broadcast(session_id, AgentEvent(
            session_id=session_id,
            agent=AgentName.OPERATIONAL,
            step="file_parsed",
            status=AgentStatus.RUNNING,
            payload={
                "note": "JSON successfully parsed into model",
            }
        ).to_ws())

        # Step 3: finished
        await broadcast(session_id, AgentEvent(
            session_id=session_id,
            agent=AgentName.OPERATIONAL,
            step="finished",
            status=AgentStatus.COMPLETED,
            payload={"note": "Operational Agent Finished."}
        ).to_ws())

        return model

    except Exception as exc:
        await broadcast(session_id, AgentEvent(
            session_id=session_id,
            agent=AgentName.OPERATIONAL,
            step="failed",
            status=AgentStatus.FAILED,
            payload={"note": "Operational Agent Failed"},
            error=str(exc)
        ).to_ws())
        raise
