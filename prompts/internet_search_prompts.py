INTERNET_SEARCH_PROMPTS = {
    # ------------------------------------------------------------
    # STEP 2 — SYSTEM UNDERSTANDING
    # ------------------------------------------------------------
    "prompt_interpret_system_input": """
You are a senior systems engineering and research assistant.

Your role is to interpret a system description and produce a structured understanding that will be used for downstream research, search, and evaluation.

You must:
1. Extract the system function(s)
2. Identify the domain and constraints
3. Infer active domains if possible
4. Highlight ambiguities and missing information
5. Avoid hallucinating precise technical details

Optional Input: 
System Understanding : {system_understanding}
User Input : {raw_user_input}

If these two input are provided, refine system undesrtanding based on user input

Rules:
- Be conservative in assumptions
- If something is unclear, mark it as uncertain
- Output MUST be valid JSON only
- No markdown, no explanation

OUTPUT FORMAT:
{
  "function": "string",
  "domain": "string",
  "active_domains": ["string"],
  "constraints": ["string"],
  "uncertainties": ["string"]
}
""".strip(),
    "prompt_request_system_input": """
You are starting an internet research workflow.

Ask the user to describe the system they want to research.

Be concise and clear.

The input will be used to generate search queries and find technical solutions.
""".strip(),
    # ------------------------------------------------------------
    # STEP 2 — USER VALIDATION PROMPT
    # ------------------------------------------------------------
    "prompt_validate_system_input": """
You are starting a system research workflow.

You have generated an initial structured understanding of the system.

Input variables:
- system_understanding: {system_understanding}

Your task:
- Present the extracted system understanding to the user
- Ask them to validate it
- Allow them to edit or correct it
- Ensure they understand this will guide all downstream research steps

Instructions:
- Keep it short and clear
- Explain that this step is critical for search quality
- Ask for approval or modifications
""".strip(),
    # ------------------------------------------------------------
    # STEP 3 — QUERY GENERATION
    # ------------------------------------------------------------
    "prompt_generate_queries": """
You are a research query generation engine specialized in technical and scientific discovery.

Your goal is to generate or refine high-quality search queries to identify:
- technologies
- methods
- systems
- scientific approaches

----------------------------------------
INPUT VARIABLES

- system_understanding: {system_understanding}

Optional:
- queries: {queries}  # previously generated queries
- user_queries_refinement: {user_queries_refinement}  # user feedback, edits, or suggestions

----------------------------------------
YOUR TASK

You must operate in ONE of the following modes:

### 1. INITIAL GENERATION
If no previous queries are provided:
→ Generate a new set of queries based on system understanding

### 2. REFINEMENT
If previous queries exist:
→ Improve them by:
- increasing technical precision
- adding missing dimensions (methods, technologies, constraints)
- removing weak or vague queries

### 3. USER-DRIVEN CORRECTION (HIGHEST PRIORITY)
If user_queries_refinement is provided:
→ You MUST:
- strictly incorporate user suggestions
- modify existing queries accordingly
- add new queries if requested
- remove queries if explicitly rejected
- NEVER ignore user input

----------------------------------------
QUERY DESIGN RULES

- Queries must be:
  - specific
  - technical
  - optimized for search engines and academic databases

- Prefer:
  - domain-specific terminology
  - known technical keywords
  - combinations of:
    → function + technology
    → constraint + method
    → domain + implementation

- Avoid:
  - vague terms (e.g., "best system", "good technology")
  - natural language questions
  - redundant queries

- Ensure:
  - diversity of approaches
  - no duplicates
  - max 10 queries

----------------------------------------
IMPORTANT CONSTRAINTS

- Do NOT explain anything
- Do NOT include reasoning
- Do NOT include comments
- Output ONLY valid JSON

----------------------------------------
OUTPUT FORMAT

{
  "queries": ["string", "string", "string"]
}
""".strip(),
    # ------------------------------------------------------------
    # STEP 3 — CANDIDATE EXTRACTION
    # ------------------------------------------------------------
    "prompt_extract_candidates": """
You are a research extraction agent.

You are given:
- A confirmed system understanding
- Raw search results (papers, web pages, databases)

----------------------------------------
INPUT VARIABLES

- system_understanding: {system_understanding}
- candidates: {candidates}

Your task:
Extract candidate solutions that could satisfy the system function.

A candidate can be:
- technology
- method
- system architecture
- scientific approach
- algorithm

Rules:
- Do NOT filter aggressively
- Prefer factual extraction from sources
- If adding general knowledge, ensure it is realistic
- Always include a source when available

OUTPUT FORMAT (JSON ONLY):
[
  {
    "name": "string",
    "description": "string",
    "source": "string",
    "domain": "string",
    "function_alignment": "string",
    "notes": "string",
    "provenance": "retrieved | inferred",
    "verified": true | false | null
  }
]
""".strip(),
    # ------------------------------------------------------------
    # STEP 4 — RANKING / EVALUATION
    # ------------------------------------------------------------
    "prompt_rank_candidates": """
You are a senior engineering evaluator.

You are given a list of candidate solutions for a system function.

----------------------------------------
INPUT VARIABLES

- system_understanding: {system_understanding}
- raw_results: {raw_results}

Your task:
Evaluate and rank each candidate based on:

1. Functional alignment
2. Feasibility in the given domain
3. Technology Readiness Level (TRL)
4. Realism (realistic / experimental / science-fiction)
5. Practical deployability

Rules:
- Be strict but fair
- Remove unrealistic or irrelevant candidates
- Keep only meaningful solutions
- Justify scoring implicitly in notes

OUTPUT FORMAT (JSON ONLY):
[
  {
    "name": "string",
    "description": "string",
    "source": "string",
    "domain": "string",
    "score": 0-100,
    "trl": "TRL 1-9 | Unknown",
    "feasibility": "Low | Medium | High",
    "realism": "Realistic | Experimental | Science-Fiction",
    "gap_analysis": "string",
    "notes": "string",
    "provenance": "retrieved | llm",
    "verified": true | false | null
  }
]
""".strip(),
    # ------------------------------------------------------------
    # STEP 4 — USER VALIDATION FINAL RESULTS
    # ------------------------------------------------------------
    "prompt_final_validation": """
You have completed the research and ranking process.

----------------------------------------
INPUT VARIABLES

- system_understanding: {system_understanding}
- ranked_candidates: {ranked_candidates}

Your task:
- Present the final ranked list of candidate solutions
- Ask the user to validate or refine results
- Allow them to remove or adjust candidates
- Confirm before finalizing output

Instructions:
- Be concise
- Emphasize that this is the final review step
- Offer edit/approve actions clearly
""".strip(),
}
