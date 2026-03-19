"""Pydantic models for ISO 15926, research output, sessions, and API DTOs."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field


# Enumerations

class EntityType(str, Enum):
    ENGINEERING_PROJECT    = "engineering_project"
    FUNCTIONAL_SYSTEM      = "functional_system"
    FUNCTIONAL_SUBSYSTEM   = "functional_subsystem"
    SCOPE_INCLUSION        = "scope_inclusion"
    SCOPE_EXCLUSION        = "scope_exclusion"
    HUMAN_ACTOR            = "human_actor"
    ORGANIZATIONAL_ACTOR   = "organizational_actor"
    ENGINEERED_SYSTEM      = "engineered_system"
    EXTERNAL_SYSTEM        = "external_system"
    REGULATORY_ACTOR       = "regulatory_actor"
    ENVIRONMENTAL_ENTITY   = "environmental_entity"
    REQUIREMENT_CLASS      = "requirement_class"
    ENGINEERING_CONSTRAINT = "engineering_constraint"
    STAKEHOLDER_NEED       = "stakeholder_need"
    CONCEPT_BASELINE       = "concept_baseline"
    REGULATORY_REFERENCE   = "regulatory_reference"
    REGULATORY_CLAUSE      = "regulatory_clause"
    OPERATIONAL_SCENARIO   = "operational_scenario"


class RequirementType(str, Enum):
    FUNCTIONAL   = "functional"
    PERFORMANCE  = "performance"
    SAFETY       = "safety"
    INTERFACE    = "interface"
    ENVIRONMENTAL= "environmental"
    REGULATORY   = "regulatory"
    OPERATIONAL  = "operational"
    MAINTENANCE  = "maintenance"
    PHYSICAL     = "physical"


class RelationshipClass(str, Enum):
    COMPOSITION_OF_INDIVIDUAL  = "composition_of_individual"
    CONNECTION_OF_INDIVIDUAL   = "connection_of_individual"
    INVOLVEMENT_BY_REFERENCE   = "involvement_by_reference"
    DERIVATION                 = "derivation"
    SATISFACTION               = "satisfaction"
    VERIFICATION               = "verification"
    REFINEMENT                 = "refinement"
    TRACEABILITY               = "traceability"
    CONFLICT                   = "conflict"
    RELATIONSHIP               = "relationship"


class GapSeverity(str, Enum):
    COVERED  = "covered"    # similarity >= 0.80
    PARTIAL  = "partial"    # similarity 0.50 – 0.79
    GAP      = "gap"        # similarity < 0.50
    NO_MATCH = "no_match"   # nothing found


class TRL(str, Enum):
    TRL1 = "TRL 1"
    TRL2 = "TRL 2"
    TRL3 = "TRL 3"
    TRL4 = "TRL 4"
    TRL5 = "TRL 5"
    TRL6 = "TRL 6"
    TRL7 = "TRL 7"
    TRL8 = "TRL 8"
    TRL9 = "TRL 9"
    UNKNOWN = "unknown"


class AgentStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"


class AgentName(str, Enum):
    SUPER       = "super"
    OPERATIONAL = "operational"
    RESEARCH    = "research"


# ISO 15926 model

class ISO15926Meta(BaseModel):
    exported_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: str = "1.0"
    standard: str = "ISO-15926"
    source_document: Optional[str] = None
    generated_by: str = "operational_agent"


class BaseEntity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str = "entity"
    entity_type: Optional[EntityType] = None
    name: str
    description: Optional[str] = None
    is_assumption: bool = False


class EngineeringConstraint(BaseEntity):
    """Core requirement node — maps to engineering_constraint entity_type."""
    entity_type: EntityType = EntityType.ENGINEERING_CONSTRAINT
    statement: str = ""
    rationale: Optional[str] = None
    req_id: str = ""
    requirement_type: Optional[RequirementType] = None
    category_id: Optional[str] = None
    function_id: Optional[str] = None
    priority: Optional[str] = None
    verification_method: Optional[str] = None


class Relationship(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str = "relationship"
    relationship_class: str = "relationship"
    name: Optional[str] = None
    source: Optional[str] = None
    target: Optional[str] = None
    from_id: Optional[str] = None
    to_id: Optional[str] = None
    direction: Optional[str] = None
    interaction_type: Optional[str] = None
    purpose: Optional[str] = None
    is_assumption: bool = False


class PropertyQuantification(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str = "property"
    name: str
    applies_to: str
    value: Optional[Union[float, str]] = None
    unit: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    is_assumption: bool = False


class ISO15926Model(BaseModel):
    meta: ISO15926Meta
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    properties: List[Dict[str, Any]] = Field(default_factory=list)

    def get_requirements(self) -> List[EngineeringConstraint]:
        reqs = []
        for e in self.entities:
            et = e.get("entity_type", "")
            if et == EntityType.ENGINEERING_CONSTRAINT or et == "engineering_constraint":
                try:
                    reqs.append(EngineeringConstraint(**e))
                except Exception:
                    pass
        return reqs

    def get_by_entity_type(self, et: str) -> List[Dict[str, Any]]:
        return [e for e in self.entities if e.get("entity_type") == et]

    def get_function_name(self, function_id: Optional[str]) -> str:
        if not function_id:
            return ""
        for e in self.entities:
            if e.get("id") == function_id or e.get("function_id") == function_id:
                return e.get("name", "")
        return ""


# Research agent output

class StandardMatch(BaseModel):
    """One standard/regulation matched to a requirement."""
    name: str                           
    clause: Optional[str] = None        
    verbatim_excerpt: Optional[str] = None
    similarity_score: float = 0.0       
    authority_level: Optional[str] = None  # international_standard 
    issuing_body: Optional[str] = None  # IAEA / IEC / ISO etc
    source_url: Optional[str] = None
    year: Optional[str] = None


class TechnologyMatch(BaseModel):
    """One technology / product / implementation found for a requirement."""
    name: str                           # e.g. "abc nutron Detector "
    vendor: Optional[str] = None        # e.g. "abc Technologies"
    trl: TRL = TRL.UNKNOWN              # Technology Readiness Level
    description: str = ""               # capability description
    deployment_examples: Optional[str] = None   # e.g. "glassgow"
    source_url: Optional[str] = None
    limitations: Optional[str] = None  # known gaps or constraints


class RequirementResearchRecord(BaseModel):
    """
    research result for ONE requirement.
    """
    # ── Requirement fields (copied from ISO model) ─────────────────────────
    req_id: str
    req_statement: str
    requirement_type: str
    function_name: Optional[str] = None
    rationale: Optional[str] = None
    is_assumption: bool = False
    criticality: str = "medium"         # high / medium / low  (classified)
    domain_tag: Optional[str] = None    # e.g. "nuclear_criticality_safety"

    # ── Standards found ────────────────────────────────────────────────────
    standards: List[StandardMatch] = Field(default_factory=list)
    best_standard: Optional[str] = None         # name of top match
    best_standard_clause: Optional[str] = None
    best_standard_excerpt: Optional[str] = None
    best_similarity_score: float = 0.0

    # ── Technologies found ─────────────────────────────────────────────────
    technologies: List[TechnologyMatch] = Field(default_factory=list)
    top_technology: Optional[str] = None        # name of best-fit tech
    top_tech_vendor: Optional[str] = None
    top_tech_trl: Optional[str] = None

    # ── Gap analysis ───────────────────────────────────────────────────────
    gap_severity: GapSeverity = GapSeverity.NO_MATCH
    gap_description: str = ""
    uncovered_aspects: List[str] = Field(default_factory=list)  # specific missing parts
    recommendation: str = ""

    # ── Meta ───────────────────────────────────────────────────────────────
    all_source_urls: List[str] = Field(default_factory=list)
    researched_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    search_queries_used: List[str] = Field(default_factory=list)


class StandardsFamilySummary(BaseModel):
    family: str          # e.g. "IAEA", "IEC"
    count: int
    standards: List[str] = Field(default_factory=list)


class TRLBreakdown(BaseModel):
    trl9: int = 0
    trl7_8: int = 0
    trl4_6: int = 0
    trl1_3: int = 0
    unknown: int = 0


class ExecutiveSummary(BaseModel):
    total_requirements: int
    covered: int            # similarity >= 0.80
    partial: int            # 0.50 – 0.79
    gaps: int               # < 0.50
    no_match: int           # nothing found
    avg_similarity_score: float
    technologies_found: int
    standards_cited: int
    top_critical_gaps: List[str] = Field(default_factory=list)
    standards_families: List[StandardsFamilySummary] = Field(default_factory=list)
    trl_breakdown: TRLBreakdown = Field(default_factory=TRLBreakdown)
    critical_actions: List[str] = Field(default_factory=list)


class SummaryTableRow(BaseModel):
    """Flat row for CSV / Excel export — one per requirement."""
    req_id: str
    req_type: str
    function: Optional[str]
    criticality: str
    req_statement_short: str            # first 120 chars for now ..we can chneage 
    best_standard: Optional[str]
    standard_clause: Optional[str]
    similarity_score: float
    gap_severity: str
    technologies_count: int
    top_technology: Optional[str]
    top_tech_trl: Optional[str]
    gap_description_short: str          # first 200 chars
    recommendation_short: str           # first 200 chars
    all_standards: str                  # semicolon-joined
    all_source_urls: str                # semicolon-joined


class ResearchResult(BaseModel):
    """Root object returned by /api/v1/sessions/{id}/research"""
    session_id: str
    records: List[dict] = Field(default_factory=list)
    summary_table: List[SummaryTableRow] = Field(default_factory=list)
    executive_summary: Optional[ExecutiveSummary] = None
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Notebook-style enriched candidates (Step 4 output) for Data View right panel
    enriched_candidates: List[Dict[str, Any]] = Field(default_factory=list)

    def build_summary_table(self) -> None:
        rows = []
        for r in self.records:
            rows.append(SummaryTableRow(
                req_id=r.req_id,
                req_type=r.requirement_type,
                function=r.function_name,
                criticality=r.criticality,
                req_statement_short=r.req_statement[:120],
                best_standard=r.best_standard,
                standard_clause=r.best_standard_clause,
                similarity_score=round(r.best_similarity_score, 3),
                gap_severity=r.gap_severity.value,
                technologies_count=len(r.technologies),
                top_technology=r.top_technology,
                top_tech_trl=r.top_tech_trl,
                gap_description_short=r.gap_description[:200],
                recommendation_short=r.recommendation[:200],
                all_standards="; ".join(s.name for s in r.standards),
                all_source_urls="; ".join(r.all_source_urls),
            ))
        self.summary_table = rows

    def build_executive_summary(self) -> None:
        if not self.records:
            return
        covered  = sum(1 for r in self.records if r.gap_severity == GapSeverity.COVERED)
        partial  = sum(1 for r in self.records if r.gap_severity == GapSeverity.PARTIAL)
        gaps     = sum(1 for r in self.records if r.gap_severity == GapSeverity.GAP)
        no_match = sum(1 for r in self.records if r.gap_severity == GapSeverity.NO_MATCH)

        scored = [r for r in self.records if r.best_similarity_score > 0]
        avg    = round(sum(r.best_similarity_score for r in scored) / max(len(scored), 1), 3)

        all_techs = [t for r in self.records for t in r.technologies]
        all_stds  = [s for r in self.records for s in r.standards]

        # Standards families
        families: Dict[str, List[str]] = {}
        for s in all_stds:
            body = s.issuing_body or _infer_body(s.name)
            families.setdefault(body, [])
            if s.name not in families[body]:
                families[body].append(s.name)
        fam_summaries = [
            StandardsFamilySummary(family=k, count=len(v), standards=v)
            for k, v in sorted(families.items(), key=lambda x: -len(x[1]))
        ]

        # TRL breakdown
        trl = TRLBreakdown()
        for t in all_techs:
            if t.trl in (TRL.TRL9,):
                trl.trl9 += 1
            elif t.trl in (TRL.TRL7, TRL.TRL8):
                trl.trl7_8 += 1
            elif t.trl in (TRL.TRL4, TRL.TRL5, TRL.TRL6):
                trl.trl4_6 += 1
            elif t.trl in (TRL.TRL1, TRL.TRL2, TRL.TRL3):
                trl.trl1_3 += 1
            else:
                trl.unknown += 1

        # Top critical gaps
        top_gaps = [
            f"{r.req_id}: {r.gap_description[:100]}"
            for r in sorted(self.records, key=lambda x: x.best_similarity_score)
            if r.gap_severity in (GapSeverity.GAP, GapSeverity.NO_MATCH)
        ][:6]

        # Critical actions
        actions = [r.recommendation[:120] for r in self.records
                   if r.gap_severity in (GapSeverity.GAP, GapSeverity.NO_MATCH)
                   and r.recommendation][:6]

        self.executive_summary = ExecutiveSummary(
            total_requirements=len(self.records),
            covered=covered,
            partial=partial,
            gaps=gaps,
            no_match=no_match,
            avg_similarity_score=avg,
            technologies_found=len(set(t.name for t in all_techs)),
            standards_cited=len(set(s.name for s in all_stds)),
            top_critical_gaps=top_gaps,
            standards_families=fam_summaries,
            trl_breakdown=trl,
            critical_actions=actions,
        )


def _infer_body(name: str) -> str:
    name_upper = name.upper()
    for body in ["IAEA", "IEC", "ISO", "ANSI", "ASTM", "NRC", "IEEE",
                 "MIL", "EURATOM", "NUREG", "NIST"]:
        if body in name_upper:
            return body
    return "OTHER"


# Agent progress events (WebSocket)

class AgentEvent(BaseModel):
    """Every message sent over WebSocket follows this shape."""
    session_id: str
    agent: AgentName
    step: str
    status: AgentStatus
    payload: Optional[Any] = None
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_ws(self) -> dict:
        return self.model_dump()


# Session state (persisted in Redis)

class SessionState(BaseModel):
    session_id: str
    status: AgentStatus = AgentStatus.PENDING
    filename: Optional[str] = None
    domain_context: Optional[str] = None
    iso_model: Optional[dict] = None
    research_result: Optional[dict] = None
    events: List[AgentEvent] = Field(default_factory=list)
    error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# FastAPI DTOs

class StartSessionResponse(BaseModel):
    session_id: str
    ws_url: str
    status_url: str
    model_url: str
    research_url: str
    message: str


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    filename: Optional[str]
    events_count: int
    has_iso_model: bool
    has_research: bool
    error: Optional[str]
    created_at: str
    updated_at: str
