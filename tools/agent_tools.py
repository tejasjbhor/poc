"""Tool definitions used by Operational and Research agents."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

from langchain_core.tools import tool
import structlog

log = structlog.get_logger(__name__)


# Operational agent tools

@tool
async def extract_pdf_text(pdf_bytes_hex: str) -> str:
    """
    Extract all text from a PDF supplied as a hex-encoded byte string.
    Returns page-delimited text. Caps at 120 000 characters for large docs.

    Args:
        pdf_bytes_hex: the PDF file bytes encoded as a hexadecimal string
    """
    try:
        import fitz
        raw = bytes.fromhex(pdf_bytes_hex)
        doc = fitz.open(stream=raw, filetype="pdf")
        pages = []
        for i, page in enumerate(doc):
            pages.append(f"[PAGE {i+1}]\n{page.get_text('text')}")
        doc.close()
        text = "\n\n".join(pages)
        log.info("pdf.extracted", pages=len(pages), chars=len(text))
        return text[:120_000]
    except Exception as exc:
        return f"ERROR extracting PDF: {exc}"


@tool
async def extract_pdf_sections(pdf_bytes_hex: str, keywords: str) -> str:
    """
    Extract only pages from a PDF that contain any of the given keywords.
    Use this to focus on requirement-dense sections of large documents.

    Args:
        pdf_bytes_hex: PDF file bytes as hexadecimal string
        keywords: comma-separated keywords e.g. "shall,requirement,constraint,must"
    """
    try:
        import fitz
        raw = bytes.fromhex(pdf_bytes_hex)
        kws = [k.strip().lower() for k in keywords.split(",")]
        doc = fitz.open(stream=raw, filetype="pdf")
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text("text")
            if any(k in text.lower() for k in kws):
                pages.append(f"[PAGE {i+1}]\n{text}")
        doc.close()
        result = "\n\n".join(pages)
        log.info("pdf.sections", matching=len(pages))
        return result[:100_000]
    except Exception as exc:
        return f"ERROR: {exc}"


@tool
async def get_iso15926_schema() -> str:
    """
    Return the ISO 15926-2 canonical entity types, relationship types,
    and required fields as a JSON reference.
    Always call this first before analysing a document.
    """
    schema = {
        "entity_types": [
            "engineering_project", "functional_system", "functional_subsystem",
            "scope_inclusion", "scope_exclusion", "human_actor",
            "organizational_actor", "engineered_system", "external_system",
            "regulatory_actor", "environmental_entity", "requirement_class",
            "engineering_constraint", "stakeholder_need", "concept_baseline",
            "regulatory_reference", "regulatory_clause", "operational_scenario"
        ],
        "relationship_types": [
            "composition_of_individual", "connection_of_individual",
            "involvement_by_reference", "derivation", "satisfaction",
            "verification", "refinement", "traceability", "conflict"
        ],
        "engineering_constraint_required_fields": [
            "id", "name", "statement", "req_id",
            "requirement_type", "category_id", "function_id", "rationale"
        ],
        "requirement_types": [
            "functional", "performance", "safety", "interface",
            "environmental", "regulatory", "operational", "maintenance", "physical"
        ],
        "iso_types": [
            "possible_individual", "class", "class_of_information", "activity"
        ],
        "instructions": (
            "Extract ALL statements containing 'shall', 'must', 'is required to', "
            "'will', 'should' as engineering_constraint entities. "
            "Assign a sequential req_id like REQ-001, REQ-002 etc. "
            "Identify functional decomposition as functional_system / functional_subsystem. "
            "Identify all actors (human, organizational, regulatory, external). "
            "Create relationships between entities."
        )
    }
    return json.dumps(schema, indent=2)


# Research agent tools

@tool
async def classify_requirement(
    req_id: str,
    req_statement: str,
    requirement_type: str,
    rationale: str = "",
    domain_context: str = ""
) -> str:
    """
    Classify a single requirement to determine its domain tag, criticality,
    and the best search queries to use when researching it.

    Returns a JSON object with: domain_tag, criticality, search_query_standards,
    search_query_technologies, priority_databases.

    Args:
        req_id: requirement identifier e.g. REQ-001
        req_statement: the full requirement statement
        requirement_type: one of safety/performance/functional/interface/regulatory/environmental/maintenance
        rationale: optional rationale text
        domain_context: optional domain hint e.g. "nuclear reprocessing PUREX"
    """
    # Domain routing rules
    stmt_lower = req_statement.lower()
    rat_lower  = rationale.lower()
    ctx_lower  = domain_context.lower()
    combined   = f"{stmt_lower} {rat_lower} {ctx_lower}"

    # --- criticality ---
    if any(w in combined for w in ["criticality", "shutdown", "life safety",
                                    "nuclear", "radiation", "radioactive",
                                    "fissile", "containment", "explosion"]):
        criticality = "high"
    elif any(w in combined for w in ["shall", "must", "required", "critical"]):
        criticality = "medium"
    else:
        criticality = "low"

    # --- domain tag ---
    if any(w in combined for w in ["criticality", "fissile", "neutron", "nuclear safety"]):
        domain_tag = "nuclear_criticality_safety"
        priority_dbs = ["IAEA", "ANSI/ANS", "NRC NUREG", "IEC 61513"]
    elif any(w in combined for w in ["radiation", "dose", "alara", "shielding", "radioprotection"]):
        domain_tag = "radiation_protection"
        priority_dbs = ["IAEA GSR", "ICRP", "IEC 60780", "NRC"]
    elif any(w in combined for w in ["yield", "throughput", "efficiency", "capacity", "extraction"]):
        domain_tag = "process_performance"
        priority_dbs = ["ASTM", "IAEA-TECDOC", "ISO process standards"]
    elif any(w in combined for w in ["control", "interface", "remote", "operator", "hmi", "scada", "plc"]):
        domain_tag = "instrumentation_control"
        priority_dbs = ["IEC 62645", "IEC 61784", "IEC 61772", "ISA-88"]
    elif any(w in combined for w in ["waste", "effluent", "discharge", "environment"]):
        domain_tag = "environmental_waste"
        priority_dbs = ["IAEA GSG-1", "Basel Convention", "ISO 14001"]
    elif any(w in combined for w in ["maintenance", "repair", "remote handling", "telemanipulator"]):
        domain_tag = "remote_maintenance"
        priority_dbs = ["IAEA SSG-28", "IEC 60780", "MIL-STD-1472"]
    elif any(w in combined for w in ["safeguard", "accountancy", "material", "nuclear material"]):
        domain_tag = "nuclear_safeguards"
        priority_dbs = ["IAEA INFCIRC/153", "EURATOM 302/2005"]
    elif requirement_type in ("regulatory",):
        domain_tag = "regulatory_compliance"
        priority_dbs = ["IAEA", "National nuclear law", "EU directives"]
    else:
        domain_tag = "general_engineering"
        priority_dbs = ["ISO", "IEC", "IEEE", "ASTM"]

    # --- search query generation ---
    # Keep queries specific and targeted
    base = req_statement[:120].strip()

    # Standards query: domain + requirement essence + standard family
    std_query = f"{base} {priority_dbs[0]} standard requirements"

    # Technology query: what systems/products implement this
    if domain_tag == "nuclear_criticality_safety":
        tech_query = f"criticality detection system neutron detector nuclear reprocessing technology"
    elif domain_tag == "radiation_protection":
        tech_query = f"radiation monitoring system dosimetry technology nuclear facility"
    elif domain_tag == "process_performance":
        tech_query = f"solvent extraction equipment technology PUREX plutonium"
    elif domain_tag == "instrumentation_control":
        tech_query = f"nuclear instrumentation control system DCS remote operations technology"
    elif domain_tag == "environmental_waste":
        tech_query = f"radioactive waste characterisation treatment technology"
    elif domain_tag == "remote_maintenance":
        tech_query = f"remote handling telemanipulator nuclear hot cell maintenance technology"
    elif domain_tag == "nuclear_safeguards":
        tech_query = f"nuclear material accountancy safeguards technology IAEA"
    else:
        tech_query = f"{base} technology implementation solution"

    result = {
        "req_id": req_id,
        "domain_tag": domain_tag,
        "criticality": criticality,
        "priority_databases": priority_dbs,
        "search_query_standards": std_query,
        "search_query_technologies": tech_query,
        "search_query_fallback": f"{requirement_type} requirement {domain_tag} standard",
    }
    return json.dumps(result)


@tool
async def search_standards_web(query: str, max_results: int = 5) -> str:
    """
    Search the web for standards, regulations, and normative documents
    that govern an engineering requirement. Uses Tavily search API.

    Args:
        query: targeted search query for standards (e.g. "ANSI ANS-8 criticality alarm nuclear")
        max_results: number of results, 3–8
    """
    try:
        from tavily import AsyncTavilyClient
        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            return json.dumps({"error": "TAVILY_API_KEY not set", "results": []})

        client = AsyncTavilyClient(api_key=api_key)
        resp = await client.search(
            query=query,
            max_results=min(int(max_results), 8),
            search_depth="advanced",
            include_answer=True,
            include_domains=[
                "iaea.org", "iec.ch", "iso.org", "ansi.org", "nrc.gov",
                "nist.gov", "ieee.org", "astm.org", "euratom.europa.eu",
                "world-nuclear.org", "ans.org", "icrp.org"
            ]
        )
        output = {
            "answer": resp.get("answer", ""),
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:600],
                    "score": round(r.get("score", 0), 3),
                }
                for r in resp.get("results", [])
            ]
        }
        log.info("standards_search.done", query=query[:60],
                 results=len(output["results"]))
        return json.dumps(output)
    except Exception as exc:
        log.error("standards_search.error", exc=str(exc))
        return json.dumps({"error": str(exc), "results": []})


@tool
async def search_technologies_web(query: str, max_results: int = 5) -> str:
    """
    Search the web for technologies, products, systems, and implementations
    that exist to satisfy an engineering requirement.

    Args:
        query: targeted technology search (e.g. "He-3 neutron detector criticality alarm system vendor")
        max_results: number of results, 3–8
    """
    try:
        from tavily import AsyncTavilyClient
        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            return json.dumps({"error": "TAVILY_API_KEY not set", "results": []})

        client = AsyncTavilyClient(api_key=api_key)
        resp = await client.search(
            query=query,
            max_results=min(int(max_results), 8),
            search_depth="advanced",
            include_answer=True,
        )
        output = {
            "answer": resp.get("answer", ""),
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:600],
                    "score": round(r.get("score", 0), 3),
                }
                for r in resp.get("results", [])
            ]
        }
        log.info("tech_search.done", query=query[:60],
                 results=len(output["results"]))
        return json.dumps(output)
    except Exception as exc:
        return json.dumps({"error": str(exc), "results": []})


@tool
async def fetch_page_content(url: str, max_chars: int = 3000) -> str:
    """
    Fetch the full text content of a webpage URL.
    Use this to get the actual clause text from a standard reference page.

    Args:
        url: the URL to fetch
        max_chars: maximum characters to return (default 3000)
    """
    try:
        import httpx
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; SysEngResearchAgent/1.0; "
                "+https://github.com/syseng-mas)"
            )
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            # Very basic HTML stripping
            text = resp.text
            import re
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:int(max_chars)]
    except Exception as exc:
        return f"ERROR fetching {url}: {exc}"


@tool
async def build_research_record(record_json: str) -> str:
    """
    Validate and serialise the final research record for one requirement.
    Call this ONCE per requirement after all searches are done.

    Args:
        record_json: JSON string with all fields for RequirementResearchRecord.
          Required: req_id, req_statement, requirement_type, domain_tag,
                    criticality, standards (list), technologies (list),
                    gap_severity, gap_description, recommendation.
          Each standard: {name, clause, verbatim_excerpt, similarity_score,
                          issuing_body, authority_level, source_url, year}
          Each technology: {name, vendor, trl, description,
                            deployment_examples, source_url, limitations}
    """
    try:
        data = json.loads(record_json)

        # Derive convenience fields
        stds = data.get("standards", [])
        techs = data.get("technologies", [])

        if stds:
            best = max(stds, key=lambda s: s.get("similarity_score", 0))
            data.setdefault("best_standard", best.get("name"))
            data.setdefault("best_standard_clause", best.get("clause"))
            data.setdefault("best_standard_excerpt", best.get("verbatim_excerpt"))
            data.setdefault("best_similarity_score", best.get("similarity_score", 0.0))
        else:
            data.setdefault("best_similarity_score", 0.0)

        if techs:
            top = techs[0]
            data.setdefault("top_technology", top.get("name"))
            data.setdefault("top_tech_vendor", top.get("vendor"))
            data.setdefault("top_tech_trl", top.get("trl"))

        # Derive gap_severity from best_similarity_score
        score = data.get("best_similarity_score", 0.0)
        if not data.get("standards"):
            data["gap_severity"] = "no_match"
        elif score >= 0.80:
            data["gap_severity"] = "covered"
        elif score >= 0.50:
            data["gap_severity"] = "partial"
        else:
            data["gap_severity"] = "gap"

        # Collect source URLs
        urls = []
        for s in stds:
            if s.get("source_url"):
                urls.append(s["source_url"])
        for t in techs:
            if t.get("source_url"):
                urls.append(t["source_url"])
        data["all_source_urls"] = list(dict.fromkeys(urls))  # dedupe
        data["researched_at"] = datetime.now(timezone.utc).isoformat()

        return json.dumps({"status": "ok", "record": data})
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})
