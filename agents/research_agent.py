"""Research agent."""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import HumanMessage
import structlog

# LangChain "agent" stack may fail to import in some environments if
# langgraph versions are incompatible. We guard those imports so the
# module can still be imported for mock/non-LLM flows.
try:
    from langchain.agents import AgentExecutor, create_react_agent  # type: ignore
    from langchain_core.prompts import PromptTemplate  # type: ignore

    _LANGCHAIN_AGENT_AVAILABLE = True
except Exception:  # pragma: no cover
    AgentExecutor = None  # type: ignore
    create_react_agent = None  # type: ignore
    PromptTemplate = None  # type: ignore
    _LANGCHAIN_AGENT_AVAILABLE = False

from schemas.models import (
    AgentEvent, AgentName, AgentStatus,
    EngineeringConstraint,
    GapSeverity, ISO15926Model,
    RequirementResearchRecord, ResearchResult,
    StandardMatch, TechnologyMatch, TRL,
)
from tools.agent_tools import (
    # --- legacy Tavily-based tools kept for compatibility (unused) ---
    # classify_requirement,
    # search_standards_web,
    # search_technologies_web,
    #
    # --- Agent-2 ---
    classify_requirement_json,
    search_web_ddg,
    search_arxiv,
    search_semantic_scholar,
    search_openalex,
    search_crossref,
    search_osti,
    fetch_page_content,
    build_research_record,
)
from utils.config import get_settings
from state.session_store import session_store

log = structlog.get_logger(__name__)
cfg = get_settings()

BroadcastFn = Callable[[str, dict], Coroutine]


async def _emit_progress(
    session_id: str,
    broadcast: BroadcastFn,
    note: str,
    step: str = "progress",
) -> None:
    await broadcast(
        session_id,
        AgentEvent(
            session_id=session_id,
            agent=AgentName.RESEARCH,
            step=step,
            status=AgentStatus.RUNNING,
            payload={"note": note},
        ).to_ws(),
    )


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

This agent uses an "Agent-2" style approach (from the working notebook):
- Uses public sources (DuckDuckGo HTML + ArXiv API), no Tavily required.
- Tool calls MUST match tool input expectations exactly.

MANDATORY PROCESS for each requirement:
1. Call classify_requirement_json with a JSON STRING:
   {"req_id":"REQ-001","req_statement":"...","requirement_type":"...","rationale":"...","domain_context":"..."}
2. Call search_web_ddg with search_query_standards → find standards/regulations pages
3. Optionally call fetch_page_content on 1–2 best URLs from step 2
4. Call search_arxiv with search_query_arxiv → find technical papers
5. Call search_web_ddg with search_query_technologies → find vendors/products/solutions
6. Optionally call fetch_page_content on best tech URL
7. Call build_research_record ONCE with the complete assembled record JSON

RECORD JSON structure for build_research_record:
{{
  "req_id": "REQ-XXX",
  "req_statement": "<full statement>",
  "requirement_type": "<type>",
  "domain_tag": "<from classify_requirement_json>",
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


# Step 2 (system understanding) prompt + helpers (ported from notebook)

_SYSTEM_PROMPT_STEP2 = """You are a research agent analyzing a system. The user has provided a JSON description of the system,
including functions, domain, constraints, and active domains.

Your task:
1. Summarize the system understanding in a concise, structured way.
2. Ask the user to confirm if your understanding is correct.
3. Highlight any uncertain areas (e.g., ambiguous functions, missing constraints, unclear domains).
4. Use clear, structured language for easy validation.
5. Wait for user feedback before proceeding to research.

Return ONLY valid JSON (no markdown, no preamble) in this exact shape:
{
  "function": "...",
  "domain": "...",
  "active_domains": ["..."],
  "constraints": ["..."],
  "uncertainties": ["..."]
}
"""

SYSTEM_PROMPT_STEP3 = """You are a research agent tasked with finding possible technologies, methods, systems, or approaches
to achieve a specific system function.

Input:
- Confirmed system understanding JSON.

Your task:
1. Generate search queries based on:
   - Function
   - Domain
   - Constraints
   - Active domains
2. Return ONLY valid JSON with this exact shape:
{
  "queries": ["...", "..."]
}

Rules:
- Queries must be specific and target reliable sources.
- Avoid science-fiction or impossible solutions.
"""

SYSTEM_PROMPT_STEP3_EXTRACT = """You are a research agent. You are given:
- Confirmed system understanding JSON
- Raw search results (web + ArXiv)

Your task:
1. Extract candidate solutions (technologies, methods, systems, approaches).
2. Return ONLY a JSON array of candidates with fields:
[
  {
    "name": "Solution name",
    "description": "Brief description of the solution",
    "source": "URL or reference",
    "domain": "...",
    "function_alignment": "...",
    "notes": "Additional comments"
  }
]

Rules:
- Do not filter yet; collect plausible candidates.
- Prefer sources from the provided raw results.
- If you must add a candidate from general knowledge, still include a best-effort canonical source URL.
- Never invent a paper id; if you cite ArXiv, it must appear in the raw results.
"""

SYSTEM_PROMPT_STEP4 = """You are a research agent tasked with evaluating a list of candidate solutions for a system function.

Input:
- Confirmed system understanding JSON.
- Candidate solutions JSON array.

Your task:
1. Evaluate each candidate solution according to:
   - Does it achieve the intended function? (Gap analysis)
   - Technology Readiness Level (TRL) if known
   - Feasibility within domain and constraints
   - Realism: is it implementable or science-fiction?
2. Assign a score 0-100 to each candidate based on the criteria above.
3. Return ONLY a filtered and ranked JSON array, sorted by score, with fields:
[
  {
    "name": "Solution name",
    "description": "Brief description",
    "source": "URL or reference (copy from input if present)",
    "domain": "domain tag if known",
    "score": 0-100,
    "TRL": "Low/Medium/High/Unknown",
    "feasibility": "Low/Medium/High",
    "realism": "Realistic/Experimental/Science-Fiction",
    "gap_analysis": "1-2 sentences explaining alignment/gap",
    "notes": "Short explanation of why this candidate was selected or rejected",
    "provenance": "retrieved|llm",
    "verified": true|false|null
  }
]

Rules:
- Keep `source`, `domain`, `provenance`, `verified` from the input candidate if available.
- Be concise and factual.
- Do not invent unsupported details.
"""


def coerce_json(text: str) -> Any:
    """Extract/parse JSON from an LLM response, tolerating markdown fences."""
    raw = (text or "").strip()
    raw = re.sub(r"^```json\s*|^```\s*|```$", "", raw).strip()
    try:
        return json.loads(raw)
    except Exception:
        # Fallback: extract the first JSON object/array in the string.
        m = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", raw)
        if not m:
            raise
        return json.loads(m.group())

def _build_step4_filter_prompt(understanding_json: str, candidates_json: str) -> str:
    """Prompt from notebook build_step4_filter_prompt (adapted for our candidate shape)."""
    return f"""You are a research agent evaluating candidate solutions.

CONFIRMED UNDERSTANDING:
{understanding_json}

CANDIDATE SOLUTIONS FROM SEARCH:
{candidates_json}

Your task:
1. Evaluate each candidate:
   - Does it achieve the intended function? (gap analysis)
   - Technology Readiness Level (TRL 1-9)
   - Feasibility within domain constraints
   - Realism: Realistic / Experimental / Science-Fiction
2. Assign a score 0-100 to each candidate
3. Return a filtered, ranked JSON array sorted by score:

Return ONLY a JSON array (no preamble):
[
  {{
    "name": "...",
    "description": "...",
    "score": 0-100,
    "trl": "TRL N",
    "feasibility": "Low|Medium|High",
    "realism": "Realistic|Experimental|Science-Fiction",
    "notes": "..."
  }}
]
"""


def _parse_trl_like(value: Any) -> TRL:
    """Best-effort conversion of LLM TRL strings to our TRL enum."""
    if value is None:
        return TRL.UNKNOWN
    raw = str(value).strip()
    if not raw:
        return TRL.UNKNOWN
    # Most notebook outputs look like "TRL 4" or just "4".
    raw_up = raw.upper().replace("-", " ").strip()
    m = re.search(r"(?:TRL\s*)?(\d)\b", raw_up)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 9:
            try:
                return TRL(f"TRL {n}")
            except Exception:
                return TRL.UNKNOWN
    # Direct match fallback (e.g., already "unknown")
    try:
        return TRL(raw)
    except Exception:
        return TRL.UNKNOWN


def _tech_to_step4_candidate(t: TechnologyMatch, domain_tag: Optional[str]) -> Dict[str, Any]:
    return {
        "name": t.name,
        "vendor": t.vendor,
        "trl": t.trl.value,
        "description": t.description,
        "source": t.source_url,
        "domain": domain_tag,
        "notes": t.limitations,
    }


async def _rank_technologies_step4(
    llm: ChatAnthropic,
    system_understanding: Dict[str, Any],
    record: RequirementResearchRecord,
    req: EngineeringConstraint,
) -> None:
    """Rank/enrich technologies in-place using notebook Step 4 prompt."""
    if not record.technologies or len(record.technologies) < 2:
        return

    # Notebook step uses a requirement-level "understanding" object.
    # We embed both: system understanding + requirement context.
    understanding_obj = {
        "system": system_understanding,
        "function": record.function_name or req.function_id,
        "domain": record.domain_tag,
        "description": (record.req_statement or "")[:300],
        "constraints": [
            (record.rationale or "")[:200],
            *(system_understanding.get("constraints") or [])[:3],
        ],
    }
    understanding_json = json.dumps(understanding_obj, indent=2, ensure_ascii=False)
    candidates_json = json.dumps(
        [_tech_to_step4_candidate(t, record.domain_tag) for t in record.technologies],
        indent=2,
        ensure_ascii=False,
    )[:12000]

    prompt = _build_step4_filter_prompt(understanding_json, candidates_json)
    resp = await llm.ainvoke([HumanMessage(content=prompt)])
    ranked_raw = coerce_json(getattr(resp, "content", "") or "")

    if not isinstance(ranked_raw, list):
        return

    # Index original technologies for preserving vendor/examples.
    by_name_and_source: Dict[tuple, TechnologyMatch] = {}
    by_name: Dict[str, TechnologyMatch] = {}
    for t in record.technologies:
        by_name[t.name] = t
        by_name_and_source[(t.name, t.source_url)] = t

    ranked_techs: List[TechnologyMatch] = []
    for item in ranked_raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or ""
        src = item.get("source") or item.get("source_url") or item.get("url") or item.get("reference")
        # Notebook step4 output uses only name/description/notes/trl; source is not required.
        base = None
        if name and src:
            base = by_name_and_source.get((name, src))
        if base is None and name:
            base = by_name.get(name)

        # Best-effort build; keep required fields safe.
        trl_enum = _parse_trl_like(item.get("trl") or item.get("TRL") or (base.trl.value if base else None))
        limitations = item.get("notes") or item.get("gap_analysis") or item.get("limitations")
        description = item.get("description") or (base.description if base else "") or ""
        source_url = src or (base.source_url if base else None)
        vendor = item.get("vendor") or (base.vendor if base else None)

        ranked_techs.append(
            TechnologyMatch(
                name=name or (base.name if base else "Unknown technology"),
                vendor=vendor,
                trl=trl_enum,
                description=description,
                deployment_examples=base.deployment_examples if base else None,
                source_url=source_url,
                limitations=limitations,
            )
        )

    if ranked_techs:
        record.technologies = ranked_techs
        record.top_technology = ranked_techs[0].name if ranked_techs else None
        record.top_tech_vendor = ranked_techs[0].vendor if ranked_techs else None
        record.top_tech_trl = ranked_techs[0].trl.value if ranked_techs else None

# Public runner

async def run_research_agent(
    iso_model: Any[dict],
    session_id: str,
    user_input_queue: asyncio.Queue,
    broadcast: BroadcastFn,
    timeout: float = 300.0,
    poll_interval: float = 0.5,
) -> ResearchResult:
    """
    Run per-requirement deep research for all requirements in the ISO model.

    For early API testing, if no Anthropic API key is configured this
    function runs in a lightweight mock mode and returns an empty
    `ResearchResult` instead of calling external LLM tools.
    """

    await broadcast(session_id, AgentEvent(
            session_id=session_id,
            agent=AgentName.RESEARCH,
            step="started",
            status=AgentStatus.RUNNING,
            payload={"note": "Research Agent Started."}
        ).to_ws())

    # Step 2 (system understanding) must happen once per session.
    # We pause here until the frontend sends: {"type":"confirm_step2"}.
    #
    # Note: if no LLM key is configured, we still broadcast a best-effort
    # understanding and wait for confirmation (if the session store exists).
    await broadcast(session_id, AgentEvent(
            session_id=session_id,
            agent=AgentName.RESEARCH,
            step="started",
            status=AgentStatus.RUNNING,
            payload={"note": "Sending system description to LLM for analysis."}
        ).to_ws())

    system_understanding: Dict[str, Any] = {}
    confirmed_step2 = False
    existing_state = await session_store.get(session_id)
    if existing_state:
        for ev in existing_state.events:
            if ev.agent == AgentName.RESEARCH and ev.step == "step2_confirmed":
                confirmed_step2 = True
            if (
                ev.agent == AgentName.RESEARCH
                and ev.step == "step2_needs_confirmation"
                and isinstance(ev.payload, dict)
                and isinstance(ev.payload.get("system_understanding"), dict)
            ):
                system_understanding = ev.payload["system_understanding"]

    if not confirmed_step2:
        if cfg.anthropic_api_key:
            llm_step2 = ChatAnthropic(
                model=cfg.anthropic_model,
                api_key=cfg.anthropic_api_key,
                max_tokens=1024,
                temperature=0.2,
            )
            prompt = _SYSTEM_PROMPT_STEP2 + "\n\nINPUT JSON:\n" + json.dumps(
                iso_model, indent=2, ensure_ascii=False
            )
            resp = await llm_step2.ainvoke([HumanMessage(content=prompt)])
            try:
                parsed = coerce_json(getattr(resp, "content", "") or "")
                if isinstance(parsed, dict):
                    system_understanding = parsed
            except Exception:
                system_understanding = {}

        await broadcast(session_id, AgentEvent(
                session_id=session_id,
                agent=AgentName.RESEARCH,
                step="started",
                status=AgentStatus.RUNNING,
                payload={"note": "Got LLM response."}
            ).to_ws())

        await broadcast(session_id, AgentEvent(
            session_id=session_id,
            agent=AgentName.RESEARCH,
            step="request_user_input",
            status=AgentStatus.WAITING_FOR_USER_INPUT,
            payload = {
                "type": "user_input_request",
                "input_type": "validation",
                "label": "Validate generated data",
                "instructions": "Please review the generated structure and approve to continue.",
                "data": system_understanding,  # 👈 the structured JSON to display
                "ui_hint": {
                    "render_as": "validation",
                    "actions": ["approve"],
                    "primary_action": "approve",
                    "approve_label": "Approve and continue"
                }
            }
        ).to_ws())

        while not user_input_queue.empty():
            try:
                user_input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            
        # Poll for confirmation event.
        # Step: wait for validation input
        elapsed = 0.0
        input_data = None

        while input_data is None:
            try:
                input_data = user_input_queue.get_nowait()
            except asyncio.QueueEmpty:
                if elapsed >= timeout:
                    break
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

        # Handle timeout
        if input_data is None:
            await broadcast(session_id, AgentEvent(
                session_id=session_id,
                agent=AgentName.RESEARCH,
                step="step2_timeout",
                status=AgentStatus.FAILED,
                payload={"note": "Timed out waiting for user validation. Proceeding best-effort."},
            ).to_ws())

        else:
            # Handle validation response
            if input_data.get("type") == "validation" and input_data.get("action") == "approve":

                await broadcast(session_id, AgentEvent(
                    session_id=session_id,
                    agent=AgentName.RESEARCH,
                    step="step2_confirmed",
                    status=AgentStatus.RUNNING,
                    payload={"note": "User approved the data. Continuing..."},
                ).to_ws())

                confirmed_step2 = True

            else:
                # Unexpected input
                await broadcast(session_id, AgentEvent(
                    session_id=session_id,
                    agent=AgentName.RESEARCH,
                    step="step2_invalid_input",
                    status=AgentStatus.FAILED,
                    payload={"note": "Invalid input received for validation step."},
                ).to_ws())

        if not confirmed_step2:
            await broadcast(session_id, AgentEvent(
                session_id=session_id,
                agent=AgentName.RESEARCH,
                step="step2_timeout",
                status=AgentStatus.FAILED,
                payload={"note": "Timed out waiting for frontend confirmation. Proceeding best-effort."},
            ).to_ws())


        if not confirmed_step2:
            await broadcast(session_id, AgentEvent(
                session_id=session_id,
                agent=AgentName.RESEARCH,
                step="step2_timeout",
                status=AgentStatus.FAILED,
                payload={"note": "Timed out waiting for frontend confirmation. Proceeding best-effort."},
            ).to_ws())

    log.info("research_agent.starting", session_id=session_id)

    records: List[RequirementResearchRecord] = []

    # Separate LLM handle for Step 4 ranking (keeps per-requirement agent LLM stable).
    llm_step4 = None
    if cfg.anthropic_api_key:
        llm_step4 = ChatAnthropic(
            model=cfg.anthropic_model,
            api_key=cfg.anthropic_api_key,
            max_tokens=2048,
            temperature=0.2,
        )
    ##_emit_progress, and other chnages to adopt ..

    # dynamic query generation + source searches .
    # await _emit_progress(session_id, broadcast, "Step 3: Generating queries and searching...", "step3")  # commented: test results on right first

    queries: List[str] = []
    if cfg.anthropic_api_key and system_understanding:
        try:
            prompt_queries = (
                SYSTEM_PROMPT_STEP3
                + "\n\nINPUT JSON:\n"
                + json.dumps(system_understanding, ensure_ascii=False)
            )
            q_resp = await ChatAnthropic(
                model=cfg.anthropic_model,
                api_key=cfg.anthropic_api_key,
                max_tokens=1000,
                temperature=0.2,
            ).ainvoke([HumanMessage(content=prompt_queries)])
            q_raw = coerce_json(getattr(q_resp, "content", "") or "")
            if isinstance(q_raw, dict) and isinstance(q_raw.get("queries"), list):
                queries = [str(x).strip() for x in q_raw.get("queries", []) if str(x).strip()][:15]
            elif isinstance(q_raw, list):
                queries = [str(x).strip() for x in q_raw if str(x).strip()][:15]
        except Exception:
            queries = []

    if not queries:
        basis = (system_understanding.get("domain") if isinstance(system_understanding, dict) else "") or "systems engineering"
        queries = [
            f"{basis} standards and regulations",
            f"{basis} technology implementations",
            f"{basis} safety requirements",
            f"{basis} operational constraints",
            f"{basis} design verification",
            f"{basis} best practices",
        ]

    # await _emit_progress(session_id, broadcast, "Step 3a: Generated search queries", "step3a")  # commented: test results on right first
    # for i, q in enumerate(queries, 1):
    #     await _emit_progress(session_id, broadcast, f"  {i:02d}. {q}", f"step3a_q{i:02d}")

    totals = {"arxiv": 0, "semantic": 0, "openalex": 0, "crossref": 0, "osti": 0, "web": 0}
    raw_results: Dict[str, Any] = {
        "queries": [],
        "web": [],
        "arxiv": [],
        "semantic_scholar": [],
        "openalex": [],
        "crossref": [],
        "osti": [],
    }
    technologies: List[TechnologyMatch] = []
    search_queries_used: List[str] = []
    for idx, q in enumerate(queries[:6], 1):
        search_queries_used.append(q)
        # await _emit_progress(session_id, broadcast, f"Step 3b: Searching ({idx}/{min(len(queries),6)}): {q}", "step3b")  # commented: test results on right first

        try:
            arxiv = json.loads(await search_arxiv.ainvoke({"query": q}))
            c = len((arxiv or {}).get("papers", []) or [])
            totals["arxiv"] += c
            raw_results["arxiv"].append({"query": q, "results": arxiv})
            # await _emit_progress(session_id, broadcast, f"  - ArXiv: ok ({c})", "step3b_src")
            for p in ((arxiv or {}).get("papers", []) or [])[:2]:
                technologies.append(TechnologyMatch(
                    name=str(p.get("title", "ArXiv Paper")),
                    trl=TRL.UNKNOWN,
                    description=str(p.get("abstract", "")),
                    source_url=p.get("url"),
                    limitations="Research source; vendor maturity not guaranteed.",
                ))
        except Exception as exc:
            pass  # await _emit_progress(session_id, broadcast, f"  - ArXiv: error ({exc})", "step3b_src")

        try:
            sem = json.loads(await search_semantic_scholar.ainvoke({"query": q}))
            c = len((sem or {}).get("papers", []) or [])
            totals["semantic"] += c
            raw_results["semantic_scholar"].append({"query": q, "results": sem})
            # await _emit_progress(session_id, broadcast, f"  - Semantic Scholar: ok ({c})", "step3b_src")
        except Exception as exc:
            pass  # await _emit_progress(session_id, broadcast, f"  - Semantic Scholar: error ({exc})", "step3b_src")

        try:
            oa = json.loads(await search_openalex.ainvoke({"query": q}))
            c = len((oa or {}).get("works", []) or [])
            totals["openalex"] += c
            raw_results["openalex"].append({"query": q, "results": oa})
            # await _emit_progress(session_id, broadcast, f"  - OpenAlex: ok ({c})", "step3b_src")
        except Exception as exc:
            pass  # await _emit_progress(session_id, broadcast, f"  - OpenAlex: error ({exc})", "step3b_src")

        try:
            cr = json.loads(await search_crossref.ainvoke({"query": q}))
            c = len((cr or {}).get("items", []) or [])
            totals["crossref"] += c
            raw_results["crossref"].append({"query": q, "results": cr})
            # await _emit_progress(session_id, broadcast, f"  - Crossref: ok ({c})", "step3b_src")
        except Exception as exc:
            pass  # await _emit_progress(session_id, broadcast, f"  - Crossref: error ({exc})", "step3b_src")

        try:
            osti = json.loads(await search_osti.ainvoke({"query": q}))
            c = len((osti or {}).get("records", []) or [])
            totals["osti"] += c
            raw_results["osti"].append({"query": q, "results": osti})
            # await _emit_progress(session_id, broadcast, f"  - OSTI: ok ({c})", "step3b_src")
        except Exception as exc:
            pass  # await _emit_progress(session_id, broadcast, f"  - OSTI: error ({exc})", "step3b_src")

        try:
            web = json.loads(await search_web_ddg.ainvoke({"query": q}))
            c = len((web or {}).get("results", []) or [])
            totals["web"] += c
            raw_results["web"].append({"query": q, "results": web})
            # await _emit_progress(session_id, broadcast, f"  - Web (DDG): ok ({c})", "step3b_src")
        except Exception as exc:
            pass  # await _emit_progress(session_id, broadcast, f"  - Web (DDG): error ({exc})", "step3b_src")

    # await _emit_progress(session_id, broadcast, "Step 3b: Retrieved items (totals)", "step3b_totals")
    # await _emit_progress(session_id, broadcast, f"  - ArXiv papers          : {totals['arxiv']}", "step3b_totals")
    # await _emit_progress(session_id, broadcast, f"  - Semantic Scholar papers: {totals['semantic']}", "step3b_totals")
    # await _emit_progress(session_id, broadcast, f"  - OpenAlex works        : {totals['openalex']}", "step3b_totals")
    # await _emit_progress(session_id, broadcast, f"  - Crossref items        : {totals['crossref']}", "step3b_totals")
    # await _emit_progress(session_id, broadcast, f"  - OSTI records          : {totals['osti']}", "step3b_totals")
    # await _emit_progress(session_id, broadcast, f"  - Web results (DDG)     : {totals['web']}", "step3b_totals")
    raw_results["queries"] = search_queries_used
    candidates: List[Dict[str, Any]] = []
    if cfg.anthropic_api_key and system_understanding:
        try:
            extract_prompt = (
                SYSTEM_PROMPT_STEP3_EXTRACT
                + "\n\nCONFIRMED SYSTEM UNDERSTANDING JSON:\n"
                + json.dumps(system_understanding, ensure_ascii=False)
                + "\n\nRAW SEARCH RESULTS JSON:\n"
                + json.dumps(raw_results, ensure_ascii=False)[:30000]
            )
            e_resp = await ChatAnthropic(
                model=cfg.anthropic_model,
                api_key=cfg.anthropic_api_key,
                max_tokens=2200,
                temperature=0.2,
            ).ainvoke([HumanMessage(content=extract_prompt)])
            e_raw = coerce_json(getattr(e_resp, "content", "") or "")
            if isinstance(e_raw, list):
                candidates = [c for c in e_raw if isinstance(c, dict)]
        except Exception:
            candidates = []

    if not candidates:
        for t in technologies[:16]:
            candidates.append({
                "name": t.name,
                "description": t.description,
                "source": t.source_url,
                "domain": system_understanding.get("domain", "") if isinstance(system_understanding, dict) else "",
                "function_alignment": t.description[:180],
                "notes": t.limitations or "",
                "provenance": "retrieved",
                "verified": None,
            })

    # await _emit_progress(session_id, broadcast, "Step 3c: Candidates built", "step3c")
    # await _emit_progress(session_id, broadcast, "Step 4: Enriching candidates (no ranking)...", "step4")

    ranked_candidates = candidates
    if cfg.anthropic_api_key and candidates and system_understanding:
        try:
            rank_prompt = (
                SYSTEM_PROMPT_STEP4
                + "\n\nCONFIRMED SYSTEM UNDERSTANDING JSON:\n"
                + json.dumps(system_understanding, ensure_ascii=False)
                + "\n\nCANDIDATE SOLUTIONS JSON:\n"
                + json.dumps(candidates, ensure_ascii=False)
            )
            r_resp = await ChatAnthropic(
                model=cfg.anthropic_model,
                api_key=cfg.anthropic_api_key,
                max_tokens=2600,
                temperature=0.2,
            ).ainvoke([HumanMessage(content=rank_prompt)])
            r_raw = coerce_json(getattr(r_resp, "content", "") or "")
            if isinstance(r_raw, list):
                ranked_candidates = [c for c in r_raw if isinstance(c, dict)]
        except Exception:
            ranked_candidates = candidates

    rec = RequirementResearchRecord(
        req_id="REQ-001",
        req_statement=str(system_understanding.get("function", "System function")),
        requirement_type="functional",
        function_name=str(system_understanding.get("function", "")) or None,
        rationale=str(system_understanding.get("domain", "")) or None,
        criticality="medium",
        domain_tag=str(system_understanding.get("domain", "")) or None,
        standards=[],
        technologies=[],
        gap_severity=GapSeverity.NO_MATCH if not technologies else GapSeverity.PARTIAL,
        gap_description="Automated dynamic search completed; standards linkage still needs deeper validation.",
        recommendation="Review top candidates and align with project-specific standards clauses.",
        search_queries_used=search_queries_used,
    )
    for c in ranked_candidates[:16]:
        trl_text = str(c.get("TRL") or c.get("trl") or "Unknown").lower()
        if "high" in trl_text:
            trl = TRL.TRL8
        elif "medium" in trl_text:
            trl = TRL.TRL5
        elif "low" in trl_text:
            trl = TRL.TRL2
        else:
            trl = TRL.UNKNOWN
        rec.technologies.append(
            TechnologyMatch(
                name=str(c.get("name") or "Candidate"),
                trl=trl,
                description=str(c.get("description") or c.get("function_alignment") or ""),
                source_url=c.get("source"),
                limitations=str(c.get("gap_analysis") or c.get("notes") or ""),
            )
        )
    if rec.technologies:
        rec.top_technology = rec.technologies[0].name
        rec.top_tech_trl = rec.technologies[0].trl.value
        rec.all_source_urls = [t.source_url for t in rec.technologies if t.source_url]
    records.append(rec)

    # ── Assemble final result ─────────────────────────────────────────────
    result = ResearchResult(
        session_id=session_id,
        records=records,
        enriched_candidates=ranked_candidates,
    )
    result.build_summary_table()
    result.build_executive_summary()

    await broadcast(session_id, AgentEvent(
        session_id=session_id, agent=AgentName.RESEARCH,
        step="completed", status=AgentStatus.COMPLETED,
        payload={
            "note": "Search completed. Showing Results",
            "total": len(records),
            "covered": result.executive_summary.covered if result.executive_summary else 0,
            "partial": result.executive_summary.partial if result.executive_summary else 0,
            "gaps": result.executive_summary.gaps if result.executive_summary else 0,
            "no_match": result.executive_summary.no_match if result.executive_summary else 0,
            "technologies_found": result.executive_summary.technologies_found if result.executive_summary else 0,
            "enriched_candidates": ranked_candidates,
        },
    ).to_ws())

    # Display  candidates 
    await broadcast(session_id, AgentEvent(
        session_id=session_id,
        agent=AgentName.RESEARCH,
        step="request_user_input",
        status=AgentStatus.WAITING_FOR_USER_INPUT,
        payload={
            "type": "user_input_request",
            "input_type": "validation",
            "label": "Research Results — Enriched Candidates",
            "instructions": "Review the technology candidates and approve to dismiss.",
            "data": {"enriched_candidates": ranked_candidates},
            "ui_hint": {
                "approve_label": "Approve",
            },
        },
    ).to_ws())

    log.info("research_agent.completed", session_id=session_id,
             records=len(records))
    return result
