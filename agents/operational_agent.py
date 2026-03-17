"""Operational agent for ISO 15926 parsing."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable, Coroutine

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


# Agent builder

def _build_executor(session_id: str, broadcast: BroadcastFn,
                    filename: str) -> AgentExecutor:
    llm = ChatAnthropic(
        model=cfg.anthropic_model,
        api_key=cfg.anthropic_api_key,
        max_tokens=8192,
        temperature=0.1,
    )
    tools = [extract_pdf_text, extract_pdf_sections, get_iso15926_schema]
    prompt = PromptTemplate.from_template(_REACT_TEMPLATE).partial(
        system=_SYSTEM.format(filename=filename),
        filename=filename,
    )
    agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        max_iterations=cfg.max_agent_iterations,
        handle_parsing_errors=True,
        callbacks=[OperationalCallback(session_id, broadcast)],
    )


# Public runner

async def run_operational_agent(
    pdf_bytes: bytes,
    filename: str,
    session_id: str,
    broadcast: BroadcastFn,
    domain_context: str = "",
) -> ISO15926Model:
    """
    For early API testing, this function falls back to a lightweight
    placeholder implementation when no Anthropic API key is configured.
    """

    await broadcast(session_id, AgentEvent(
        session_id=session_id, agent=AgentName.OPERATIONAL,
        step="starting", status=AgentStatus.RUNNING,
        payload={"filename": filename, "bytes": len(pdf_bytes)},
    ).to_ws())

    
    if not cfg.anthropic_api_key:
        meta = ISO15926Meta(source_document=filename)
        model = ISO15926Model(meta=meta, entities=[], relationships=[], properties=[])
        await broadcast(session_id, AgentEvent(
            session_id=session_id, agent=AgentName.OPERATIONAL,
            step="completed_mock", status=AgentStatus.COMPLETED,
            payload={
                "note": "Operational agent running in mock mode (no LLM configured)",
                "entities": 0,
                "relationships": 0,
                "requirements": 0,
            },
        ).to_ws())
        log.info("operational_agent.completed_mock", session_id=session_id)
        return model

    executor = _build_executor(session_id, broadcast, filename)

    # Hex-encode PDF; cap at ~5 MB raw (10 MB hex) to stay within context , for test only 
    pdf_hex = pdf_bytes.hex()[:10_000_000]

    result = await executor.ainvoke({
        "pdf_hex": pdf_hex,
        "domain_context": domain_context or "",
        "agent_scratchpad": "",
    })

    raw = result.get("output", "")
    log.info("operational_agent.raw_output", session_id=session_id,
             chars=len(raw))

    # ── Parse + validate ──────────────────────────────────────────────────
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)
        # Ensure meta block exists
        data.setdefault("meta", {})
        data["meta"].setdefault("exported_at", datetime.now(timezone.utc).isoformat())
        data["meta"].setdefault("source_document", filename)
        data["meta"].setdefault("generated_by", "operational_agent")

        model = ISO15926Model.model_validate(data)

        req_count = len(model.get_requirements())
        await broadcast(session_id, AgentEvent(
            session_id=session_id, agent=AgentName.OPERATIONAL,
            step="completed", status=AgentStatus.COMPLETED,
            payload={
                "entities": len(model.entities),
                "relationships": len(model.relationships),
                "requirements": req_count,
            },
        ).to_ws())

        log.info("operational_agent.completed", session_id=session_id,
                 entities=len(model.entities), requirements=req_count)
        return model

    except Exception as exc:
        log.error("operational_agent.parse_failed",
                  session_id=session_id, exc=str(exc))
        await broadcast(session_id, AgentEvent(
            session_id=session_id, agent=AgentName.OPERATIONAL,
            step="parse_failed", status=AgentStatus.FAILED, error=str(exc),
        ).to_ws())
        raise RuntimeError(f"Operational agent output parse failed: {exc}") from exc
