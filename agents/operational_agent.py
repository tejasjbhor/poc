"""Operational agent for ISO 15926 parsing."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable, Coroutine

import asyncio

from langchain.agents import AgentExecutor, create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.prompts import PromptTemplate
import structlog

from schemas.models import AgentEvent, AgentName, AgentStatus, ISO15926Model, ISO15926Meta
from tools.agent_tools import extract_pdf_text, extract_pdf_sections, get_iso15926_schema
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

async def run_operational_agent(
    session_id: str,
    broadcast: BroadcastFn,
) -> ISO15926Model:
    """
    Operational agent without file input, using preloaded/mock data.
    """

    try:
        await broadcast(session_id, AgentEvent(
            session_id=session_id, agent=AgentName.OPERATIONAL,
            step="started", status=AgentStatus.RUNNING,
            payload={"note": "Operational Agent Started"}
        ).to_ws())
        
        # Step 2: got data (mock)
        await broadcast(session_id, AgentEvent(
            session_id=session_id,
            agent=AgentName.OPERATIONAL,
            step="got_data",
            status=AgentStatus.RUNNING,
            payload={"note": "Using preloaded mock data"}
        ).to_ws())
        
        # Step 2.5: analyzing system data
        await broadcast(session_id, AgentEvent(
            session_id=session_id,
            agent=AgentName.OPERATIONAL,
            step="analyzing_system_data",
            status=AgentStatus.RUNNING,
            payload={"note": "Processing system description..."}
        ).to_ws())

        await asyncio.sleep(5)
        
        meta = ISO15926Meta(source_document="mock_document")
        model = ISO15926Model(meta=meta, entities=[], relationships=[], properties=[])
        
        await broadcast(session_id, AgentEvent(
            session_id=session_id, agent=AgentName.OPERATIONAL,
            step="system_description_ready", status=AgentStatus.RUNNING,
            payload={
            "note": "System Description Ready",
            "entities": len(model.entities),
            "relationships": len(model.relationships),
            "requirements": len(model.get_requirements()),
            }
        ).to_ws())
        
        # Step 4: finished
        await broadcast(session_id, AgentEvent(
            session_id=session_id,
            agent=AgentName.OPERATIONAL,
            step="finished",
            status=AgentStatus.COMPLETED,
            payload={"note": "Operational Agent Finished"},
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


        
        
