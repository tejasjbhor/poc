"""Research agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable, Coroutine, List, Optional

from langchain.agents import AgentExecutor, create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.prompts import PromptTemplate
import structlog

from schemas.models import (
    AgentEvent, AgentName, AgentStatus,
    EngineeringConstraint,
    GapSeverity, ISO15926Model,
    RequirementResearchRecord, ResearchResult,
    StandardMatch, TechnologyMatch, TRL,
)
from tools.agent_tools import (
    classify_requirement,
    search_standards_web,
    search_technologies_web,
    fetch_page_content,
    build_research_record,
)
from utils.config import get_settings

log = structlog.get_logger(__name__)
cfg = get_settings()

BroadcastFn = Callable[[str, dict], Coroutine]


# Progress callback

class ResearchCallback(AsyncCallbackHandler):
    def __init__(self, session_id: str, req_id: str, broadcast: BroadcastFn):
        self.session_id = session_id
        self.req_id = req_id
        self.broadcast = broadcast

    async def _emit(self, step: str, status: AgentStatus, payload=None, error=None):
        ev = AgentEvent(
            session_id=self.session_id,
            agent=AgentName.RESEARCH,
            step=f"{self.req_id}:{step}",
            status=status,
            payload=payload,
            error=error,
        )
        await self.broadcast(self.session_id, ev.to_ws())

    async def on_agent_action(self, action, **_):
        await self._emit(
            step=f"tool:{action.tool}",
            status=AgentStatus.RUNNING,
            payload={"input_preview": str(action.tool_input)[:150]},
        )

    async def on_tool_end(self, output, **_):
        await self._emit(
            step="tool_result",
            status=AgentStatus.RUNNING,
            payload={"preview": str(output)[:200]},
        )

    async def on_chain_error(self, error, **_):
        await self._emit(step="error", status=AgentStatus.RUNNING, error=str(error))


# Prompt

_SYSTEM = """You are the Research Agent for a Systems Engineering platform.

Your task: for ONE engineering requirement, find:
  A) The governing standards / regulations that apply to it
  B) Existing technologies / products / systems that implement it
  C) Perform a gap analysis

PROCESS for each requirement:
1. Call classify_requirement → get domain_tag, criticality, search queries
2. Call search_standards_web with search_query_standards → find governing standards
3. Call fetch_page_content on the top 1-2 URLs → get actual clause text
4. If no good results, call search_standards_web again with search_query_fallback
5. Call search_technologies_web with search_query_technologies → find implementations
6. Call fetch_page_content on top technology URL for more detail
7. Call build_research_record with the complete assembled record JSON

RECORD JSON structure for build_research_record:
{{
  "req_id": "REQ-XXX",
  "req_statement": "<full statement>",
  "requirement_type": "<type>",
  "domain_tag": "<from classify>",
  "criticality": "<high/medium/low>",
  "function_name": "<subsystem name>",
  "rationale": "<rationale>",
  "is_assumption": false,
  "standards": [
  {{
      "name": "<full standard name e.g. ANSI/ANS-8.3-1997 (R2020)>",
      "clause": "<specific section e.g. section 5.2 Alarm system response>",
      "verbatim_excerpt": "<exact quote from standard, max 300 chars>",
      "similarity_score": 0.0-1.0,
      "issuing_body": "<IAEA/IEC/ISO/ANSI/ASTM/NRC/IEEE>",
      "authority_level": "<international_standard/national_standard/guidance/technical_report>",
      "source_url": "<URL>",
      "year": "<publication year>"
    }}
  ],
  "technologies": [
    {{
      "name": "<technology or product name>",
      "vendor": "<company name>",
      "trl": "<TRL 1-9 or unknown>",
      "description": "<what it does and how it meets the requirement>",
      "deployment_examples": "<where it has been used>",
      "source_url": "<URL>",
      "limitations": "<known gaps or constraints>"
    }}
  ],
  "gap_description": "<what part of the requirement is NOT covered by any standard or technology>",
  "recommendation": "<specific actionable recommendation: which tech + which standard + what to define project-specifically>",
  "search_queries_used": ["<query1>", "<query2>"]
}}

SIMILARITY SCORING GUIDE:
  0.9-1.0 = standard directly addresses this exact requirement
  0.7-0.9 = standard addresses same topic with minor scope differences
  0.5-0.7 = standard addresses related topic, partial coverage
  0.3-0.5 = standard tangentially related, significant gaps
  0.0-0.3 = only loosely related

TRL GUIDE:
  TRL 9 = proven at industrial/operational scale
  TRL 7-8 = demonstrated at pilot/prototype scale
  TRL 4-6 = validated in lab / sub-system level
  TRL 1-3 = research / concept stage

Always respond with the final record from build_research_record.
"""

_REACT_TEMPLATE = """{system}

Tools:
{tools}

Tool names: {tool_names}

Format:
Thought: what to do next
Action: tool_name
Action Input: input to the tool
Observation: result
(repeat)
Thought: I have completed the research for this requirement
Final Answer: <JSON string returned by build_research_record>

Begin!

Requirement to research:
  req_id: {req_id}
  statement: {req_statement}
  requirement_type: {requirement_type}
  rationale: {rationale}
  function: {function_name}
  domain_context: {domain_context}

{agent_scratchpad}"""


# Agent builder

def _build_executor(session_id: str, req_id: str,
                    broadcast: BroadcastFn) -> AgentExecutor:
    llm = ChatAnthropic(
        model=cfg.anthropic_model,
        api_key=cfg.anthropic_api_key,
        max_tokens=4096,
        temperature=0.2,
    )
    tools = [
        classify_requirement,
        search_standards_web,
        search_technologies_web,
        fetch_page_content,
        build_research_record,
    ]
    prompt = PromptTemplate.from_template(_REACT_TEMPLATE).partial(
        system=_SYSTEM,
    )
    agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        max_iterations=cfg.max_agent_iterations,
        handle_parsing_errors=True,
        callbacks=[ResearchCallback(session_id, req_id, broadcast)],
    )


# Parse one record from agent output

def _parse_record(raw: str, req: EngineeringConstraint,
                  function_name: str) -> RequirementResearchRecord:
    """Parse the JSON returned by build_research_record into a typed record."""
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        cleaned = cleaned.strip()

        outer = json.loads(cleaned)
        # build_research_record returns {"status": "ok", "record": {...}}
        data = outer.get("record", outer)

        # Parse nested standards
        stds = []
        for s in data.get("standards", []):
            try:
                stds.append(StandardMatch(**s))
            except Exception:
                stds.append(StandardMatch(
                    name=s.get("name", "Unknown"),
                    similarity_score=float(s.get("similarity_score", 0)),
                ))

        # Parse nested technologies
        techs = []
        for t in data.get("technologies", []):
            trl_val = t.get("trl", "unknown")
            # Normalise TRL string
            try:
                trl_enum = TRL(trl_val)
            except ValueError:
                # Try mapping "9" → "TRL 9"
                try:
                    trl_enum = TRL(f"TRL {trl_val}")
                except ValueError:
                    trl_enum = TRL.UNKNOWN
            try:
                techs.append(TechnologyMatch(
                    name=t.get("name", ""),
                    vendor=t.get("vendor"),
                    trl=trl_enum,
                    description=t.get("description", ""),
                    deployment_examples=t.get("deployment_examples"),
                    source_url=t.get("source_url"),
                    limitations=t.get("limitations"),
                ))
            except Exception:
                pass

        # Gap severity
        score = float(data.get("best_similarity_score", 0.0))
        if not stds:
            severity = GapSeverity.NO_MATCH
        elif score >= 0.80:
            severity = GapSeverity.COVERED
        elif score >= 0.50:
            severity = GapSeverity.PARTIAL
        else:
            severity = GapSeverity.GAP

        best_std = max(stds, key=lambda s: s.similarity_score) if stds else None

        return RequirementResearchRecord(
            req_id=req.req_id or data.get("req_id", ""),
            req_statement=req.statement or data.get("req_statement", ""),
            requirement_type=(req.requirement_type.value
                              if req.requirement_type else
                              data.get("requirement_type", "unknown")),
            function_name=function_name or data.get("function_name"),
            rationale=req.rationale or data.get("rationale"),
            is_assumption=req.is_assumption,
            criticality=data.get("criticality", "medium"),
            domain_tag=data.get("domain_tag"),
            standards=stds,
            best_standard=best_std.name if best_std else None,
            best_standard_clause=best_std.clause if best_std else None,
            best_standard_excerpt=best_std.verbatim_excerpt if best_std else None,
            best_similarity_score=best_std.similarity_score if best_std else 0.0,
            technologies=techs,
            top_technology=techs[0].name if techs else None,
            top_tech_vendor=techs[0].vendor if techs else None,
            top_tech_trl=techs[0].trl.value if techs else None,
            gap_severity=severity,
            gap_description=data.get("gap_description", ""),
            uncovered_aspects=data.get("uncovered_aspects", []),
            recommendation=data.get("recommendation", ""),
            all_source_urls=data.get("all_source_urls", []),
            search_queries_used=data.get("search_queries_used", []),
            researched_at=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as exc:
        log.error("research_record.parse_failed", req_id=req.req_id, exc=str(exc))
        # Return a minimal record rather than crashing the whole pipeline
        return RequirementResearchRecord(
            req_id=req.req_id or "UNKNOWN",
            req_statement=req.statement or "",
            requirement_type=req.requirement_type.value if req.requirement_type else "unknown",
            function_name=function_name,
            gap_severity=GapSeverity.NO_MATCH,
            gap_description=f"Research failed: {exc}",
            recommendation="Manual research required.",
        )


# Public runner

async def run_research_agent(
    iso_model: ISO15926Model,
    session_id: str,
    broadcast: BroadcastFn,
    domain_context: str = "",
) -> ResearchResult:
    """
    Run per-requirement deep research for all requirements in the ISO model.

    For early API testing, if no Anthropic API key is configured this
    function runs in a lightweight mock mode and returns an empty
    `ResearchResult` instead of calling external LLM tools.
    """
    requirements = iso_model.get_requirements()
    total = len(requirements)

    await broadcast(session_id, AgentEvent(
        session_id=session_id, agent=AgentName.RESEARCH,
        step="starting", status=AgentStatus.RUNNING,
        payload={"total_requirements": total,
                 "standard": iso_model.meta.standard},
    ).to_ws())

    # Mock mode: no external web/LLM calls, just return an empty result so
    # that the FastAPI endpoints and orchestration can be exercised.
    if not cfg.anthropic_api_key:
        result = ResearchResult(
            session_id=session_id,
            source_standard=iso_model.meta.standard,
            source_document=iso_model.meta.source_document,
            records=[],
        )
        await broadcast(session_id, AgentEvent(
            session_id=session_id, agent=AgentName.RESEARCH,
            step="completed_mock", status=AgentStatus.COMPLETED,
            payload={
                "note": "Research agent running in mock mode (no LLM configured)",
                "total": 0,
            },
        ).to_ws())
        log.info("research_agent.completed_mock", session_id=session_id)
        return result

    log.info("research_agent.starting", session_id=session_id,
             requirements=total)

    records: List[RequirementResearchRecord] = []

    for idx, req in enumerate(requirements, 1):
        req_id = req.req_id or f"REQ-{idx:03d}"
        function_name = iso_model.get_function_name(req.function_id)

        await broadcast(session_id, AgentEvent(
            session_id=session_id, agent=AgentName.RESEARCH,
            step=f"researching_{req_id}",
            status=AgentStatus.RUNNING,
            payload={
                "req_id": req_id,
                "progress": f"{idx}/{total}",
                "type": req.requirement_type.value if req.requirement_type else "unknown",
            },
        ).to_ws())

        executor = _build_executor(session_id, req_id, broadcast)

        try:
            result = await executor.ainvoke({
                "req_id": req_id,
                "req_statement": req.statement or req.name,
                "requirement_type": req.requirement_type.value if req.requirement_type else "unknown",
                "rationale": req.rationale or "",
                "function_name": function_name or "",
                "domain_context": domain_context or iso_model.meta.standard,
                "agent_scratchpad": "",
            })

            raw = result.get("output", "{}")
            record = _parse_record(raw, req, function_name)
            records.append(record)

            await broadcast(session_id, AgentEvent(
                session_id=session_id, agent=AgentName.RESEARCH,
                step=f"done_{req_id}",
                status=AgentStatus.RUNNING,
                payload={
                    "req_id": req_id,
                    "gap_severity": record.gap_severity.value,
                    "standards_found": len(record.standards),
                    "technologies_found": len(record.technologies),
                    "best_score": round(record.best_similarity_score, 3),
                    "progress": f"{idx}/{total}",
                },
            ).to_ws())

        except Exception as exc:
            log.error("research_agent.req_failed",
                      session_id=session_id, req_id=req_id, exc=str(exc))
            # Non-fatal: add a no-match record and continue
            records.append(RequirementResearchRecord(
                req_id=req_id,
                req_statement=req.statement or req.name,
                requirement_type=req.requirement_type.value if req.requirement_type else "unknown",
                function_name=function_name,
                gap_severity=GapSeverity.NO_MATCH,
                gap_description=f"Research error: {exc}",
                recommendation="Manual research required.",
            ))
            await broadcast(session_id, AgentEvent(
                session_id=session_id, agent=AgentName.RESEARCH,
                step=f"error_{req_id}",
                status=AgentStatus.RUNNING,
                error=str(exc),
                payload={"req_id": req_id, "progress": f"{idx}/{total}"},
            ).to_ws())

    # ── Assemble final result ─────────────────────────────────────────────
    result = ResearchResult(
        session_id=session_id,
        source_standard=iso_model.meta.standard,
        source_document=iso_model.meta.source_document,
        records=records,
    )
    result.build_summary_table()
    result.build_executive_summary()

    await broadcast(session_id, AgentEvent(
        session_id=session_id, agent=AgentName.RESEARCH,
        step="completed", status=AgentStatus.COMPLETED,
        payload={
            "total": len(records),
            "covered": result.executive_summary.covered if result.executive_summary else 0,
            "partial": result.executive_summary.partial if result.executive_summary else 0,
            "gaps": result.executive_summary.gaps if result.executive_summary else 0,
            "no_match": result.executive_summary.no_match if result.executive_summary else 0,
            "technologies_found": result.executive_summary.technologies_found if result.executive_summary else 0,
        },
    ).to_ws())

    log.info("research_agent.completed", session_id=session_id,
             records=len(records))
    return result
