"""Research agent."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Callable, Coroutine, Dict, List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import HumanMessage
import structlog

from utils.user_interaction import request_user_input

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
    RequirementResearchRecord, ResearchResult,
    StandardMatch, TechnologyMatch, TRL, GapSeverity
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
    build_research_record
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
            payload={"note": "Sending system description to LLM for analysis.",
                     "sub_status": "Waiting For LLM"}
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

    llm_step2 = None
    if cfg.anthropic_api_key:
        llm_step2 = ChatAnthropic(
            model=cfg.anthropic_model,
            api_key=cfg.anthropic_api_key,
            max_tokens=1024,
            temperature=0.2,
        )

    if not system_understanding:
        if llm_step2:
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
            step="system_understanding_generated",
            status=AgentStatus.RUNNING,
            payload={"note": "Initial system understanding generated."}
        ).to_ws())

    # 🔁 LOOP until user approves
    while not confirmed_step2:

        # 2. Wait for user input
        input_data = None
        
        input_data = await request_user_input(
            session_id=session_id,
            agent=AgentName.RESEARCH,
            user_input_queue=user_input_queue,
            broadcast=broadcast,
            step="request_user_input",
            data=system_understanding,
            label="Validate generated data",
            instructions="Review, edit if needed, then approve.",
            ui_hint={
                "render_as": "validation",
                "actions": ["approve", "edit"],
                "primary_action": "approve",
                "approve_label": "Approve and continue",
                "edit_label": "Modify and resubmit",
                "editable": True
            },
            timeout=timeout
        )

        if input_data is None:
            break

        action = input_data.get("action")

        # ✅ APPROVE
        if action == "approve":
            confirmed_step2 = True

            await broadcast(session_id, AgentEvent(
                session_id=session_id,
                agent=AgentName.RESEARCH,
                step="step2_confirmed",
                status=AgentStatus.RUNNING,
                payload={"note": "User approved the data. Continuing..."},
            ).to_ws())

        # 🔁 EDIT → RE-RUN LLM
        elif action == "edit":
            updated_data = input_data.get("data", {})

            await broadcast(session_id, AgentEvent(
                session_id=session_id,
                agent=AgentName.RESEARCH,
                step="step2_edit_received",
                status=AgentStatus.RUNNING,
                payload={"note": "User modifications received. Refining...",
                         "sub_status": "Waiting For LLM"},
            ).to_ws())

            if cfg.anthropic_api_key:
                refine_prompt = (
                    _SYSTEM_PROMPT_STEP2
                    + "\n\nPREVIOUS OUTPUT:\n"
                    + json.dumps(system_understanding, indent=2, ensure_ascii=False)
                    + "\n\nUSER MODIFICATIONS:\n"
                    + json.dumps(updated_data, indent=2, ensure_ascii=False)
                    + "\n\nRefine the structure accordingly."
                )

                resp = await llm_step2.ainvoke([HumanMessage(content=refine_prompt)])

                try:
                    parsed = coerce_json(getattr(resp, "content", "") or "")
                    if isinstance(parsed, dict):
                        system_understanding = parsed
                    else:
                        system_understanding = updated_data
                except Exception:
                    system_understanding = updated_data

            else:
                # fallback if no LLM
                system_understanding = updated_data
                
            # 🔥 CRITICAL: restart loop cleanly
            continue

        # ❌ INVALID INPUT
        else:
            await broadcast(session_id, AgentEvent(
                session_id=session_id,
                agent=AgentName.RESEARCH,
                step="step2_invalid_input",
                status=AgentStatus.RUNNING,
                payload={"note": "Invalid input. Please approve or edit."},
            ).to_ws())
    log.info("research_agent.starting", session_id=session_id)

    records: List[RequirementResearchRecord] = []

    # dynamic query generation + source searches .
    # await _emit_progress(session_id, broadcast, "Step 3: Generating queries and searching...", "step3")  # commented: test results on right first

    await broadcast(session_id, AgentEvent(
        session_id=session_id,
        agent=AgentName.RESEARCH,
        step="building_research_queries",
        status=AgentStatus.RUNNING,
        payload={"note": "Building search queries from system understanding.",
                 "sub_status": "Waiting For LLM",},
    ).to_ws())

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

    input_data = await request_user_input(
        session_id=session_id,
        agent=AgentName.RESEARCH,
        user_input_queue=user_input_queue,
        broadcast=broadcast,
        step="request_user_input",
        data=queries,
        label="Validate search queries",
        instructions="Review then approve.",
        ui_hint={
            "render_as": "validation",
            "actions": ["approve"],
            "primary_action": "approve",
            "approve_label": "Approve and continue",
            "editable": False
        },
        timeout=timeout
    )

    if input_data is None:
        pass

    action = input_data.get("action")

    await broadcast(session_id, AgentEvent(
        session_id=session_id,
        agent=AgentName.RESEARCH,
        step="search_queries_ready",
        status=AgentStatus.RUNNING,
        payload={"note": "Search queries ready. Executing internet search",
                 "sub_status": "Waiting For Internet Search",},
    ).to_ws())


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

    await broadcast(session_id, AgentEvent(
        session_id=session_id,
        agent=AgentName.RESEARCH,
        step="extract_relevant_results",
        status=AgentStatus.RUNNING,
        payload={"note": "Internet search done. Extracting credible relevant results",
                 "sub_status": "Waiting For LLM",},
    ).to_ws())

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

    await broadcast(session_id, AgentEvent(
        session_id=session_id,
        agent=AgentName.RESEARCH,
        step="search_queries_ready",
        status=AgentStatus.RUNNING,
        payload={"note": "Ranking relevant results",
                 "sub_status": "Waiting For LLM",},
    ).to_ws())

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

    input_data = await request_user_input(
        session_id=session_id,
        agent=AgentName.RESEARCH,
        user_input_queue=user_input_queue,
        broadcast=broadcast,
        step="request_user_input",
        data=ranked_candidates,
        label="Research Results — Enriched Candidates",
        instructions="Review then approve.",
        ui_hint={
            "render_as": "validation",
            "actions": ["approve"],
            "primary_action": "approve",
            "approve_label": "Approve and continue",
            "editable": False
        },
        timeout=timeout
    )

    if input_data is None:
        pass

    action = input_data.get("action")
    
    # Step 3: finished
    await broadcast(session_id, AgentEvent(
        session_id=session_id,
        agent=AgentName.RESEARCH,
        step="finished",
        status=AgentStatus.COMPLETED,
        payload={"note": "Research Agent Finished."}
    ).to_ws())
    
    
    return ranked_candidates
